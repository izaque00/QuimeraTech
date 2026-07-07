"""
Quimera Mark X — Coevolution Engine (Horizonte 4)

Patches e testes evoluem juntos em uma corrida armamentista adversarial.
  - Patches evoluem para PASSAR testes
  - Testes evoluem para QUEBRAR patches  
  - Novelty search para diversidade de testes
  - Métrica de arms race intensity
  - Seleção de patches robustos (passam todos os testes)

De → Para:
  Antes: Testes fixos validam patches
  Agora: Patches e testes coevoluem adversarialmente

Usage:
    engine = CoevolutionEngine(patch_population_size=20, test_population_size=10)
    result = engine.coevolve(original_code, error_context, initial_tests)
"""

import copy
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .genetic_patch_engine import (
    Individual, FitnessVector, GeneticOperators, MutationType,
)

logger = logging.getLogger("quimera.h4.coevolution")


@dataclass
class TestCase:
    """An evolving test case that tries to break patches."""
    id: str
    code: str
    description: str
    effectiveness: float = 0.0       # How well it breaks patches
    novelty: float = 0.0             # How different from other tests
    generation_born: int = 0
    parent_ids: List[str] = field(default_factory=list)


@dataclass
class CoevolutionStats:
    generation: int
    patch_best_fitness: float
    test_best_effectiveness: float
    arms_race_intensity: float
    robust_patches_count: int       # Patches that pass ALL tests
    elapsed_ms: float


@dataclass
class CoevolutionResult:
    robust_patches: List[Individual]
    best_tests: List[TestCase]
    stats: List[CoevolutionStats]
    total_elapsed_ms: float
    arms_race_winner: str  # "patches" or "tests"


# ═══════════════════════════════════════════════════════════════════════════
# Test Case Operators
# ═══════════════════════════════════════════════════════════════════════════

class TestOperators:
    """Mutation operators for test cases."""

    @staticmethod
    def tighten_bounds(code: str) -> str:
        """Make bounds checks stricter."""
        if ">" in code or ">=" in code:
            return code.replace("> 0", "> 255").replace(">= 0", ">= 256")
        return code + "\n// Tightened bounds"

    @staticmethod
    def add_null_check_test(code: str) -> str:
        """Add NULL input test."""
        if "NULL" not in code:
            return code + "\nassert(process(NULL) == -EINVAL);"
        return code

    @staticmethod
    def add_edge_case(code: str) -> str:
        """Add edge case: max/min values."""
        if "MAX" not in code:
            return code + "\nassert(process(SIZE_MAX) == -EOVERFLOW);"
        return code

    @staticmethod
    def invert_expected(code: str) -> str:
        """Invert expected success/failure."""
        return code.replace("== 0", "!= 0").replace("!= 0", "== 0") if "==" in code else code + "\n// Inverted expectation"

    @staticmethod
    def mutate_test(test: TestCase) -> TestCase:
        operators = [
            TestOperators.tighten_bounds,
            TestOperators.add_null_check_test,
            TestOperators.add_edge_case,
            TestOperators.invert_expected,
        ]
        op = random.choice(operators)
        new_code = op(test.code)
        return TestCase(
            id=f"test-gen{test.generation_born + 1}-{random.randint(0, 9999):04d}",
            code=new_code,
            description=test.description + " [mutated]",
            generation_born=test.generation_born + 1,
            parent_ids=[test.id],
        )


# ═══════════════════════════════════════════════════════════════════════════
# Coevolution Engine
# ═══════════════════════════════════════════════════════════════════════════

class CoevolutionEngine:
    """Adversarial coevolution of patches and tests."""

    def __init__(
        self,
        patch_population_size: int = 20,
        test_population_size: int = 10,
        max_generations: int = 20,
        crossover_rate: float = 0.7,
        mutation_rate: float = 0.2,
    ):
        self.patch_pop_size = patch_population_size
        self.test_pop_size = test_population_size
        self.max_generations = max_generations
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate

        self._stats: List[CoevolutionStats] = []
        self._novelty_archive: List[str] = []  # For novelty search

    # ── Fitness Evaluation ─────────────────────────────────────────────

    @staticmethod
    def evaluate_patch_against_tests(patch: str, tests: List[TestCase]) -> float:
        """Score a patch based on how many tests it passes."""
        if not tests:
            return 0.8  # No tests → neutral score
        passed = 0
        for test in tests:
            if CoevolutionEngine._simulate_test(patch, test):
                passed += 1
        return passed / len(tests)

    @staticmethod
    def evaluate_test_effectiveness(test: TestCase, patches: List[Individual]) -> float:
        """Score a test based on how many patches it breaks."""
        if not patches:
            return 0.0
        broken = 0
        for patch in patches:
            if not CoevolutionEngine._simulate_test(patch.patch_code, test):
                broken += 1
        return broken / len(patches)

    @staticmethod
    def _simulate_test(patch: str, test: TestCase) -> bool:
        """Simulate whether a patch passes a test (heuristic).

        In production, this compiles patch + test in sandbox and runs it.
        """
        # Heuristic: check for common anti-patterns
        if test.code and "NULL" in test.code:
            if "NULL" not in patch and "null" not in patch:
                return False
        if test.code and "overflow" in test.code.lower():
            if "sizeof" not in patch and "strncpy" not in patch:
                return False
        if test.code and "INVERT" in test.code:
            return random.random() < 0.3  # Inverted tests are hard to pass
        return random.random() < 0.7  # Default pass rate

    # ── Novelty Search ─────────────────────────────────────────────────

    def _compute_novelty(self, test: TestCase) -> float:
        """How different is this test from the archive (novelty search)."""
        if not self._novelty_archive:
            return 1.0
        # Simple Jaccard-like novelty: unique tokens / total tokens
        test_tokens = set(test.code.split())
        max_similarity = 0.0
        for archived in self._novelty_archive[-20:]:
            archived_tokens = set(archived.split())
            intersection = len(test_tokens & archived_tokens)
            union = len(test_tokens | archived_tokens)
            similarity = intersection / max(union, 1)
            max_similarity = max(max_similarity, similarity)
        return 1.0 - max_similarity

    # ── Coevolution ────────────────────────────────────────────────────

    def coevolve(
        self,
        original_code: str,
        error_context: str,
        initial_tests: Optional[List[TestCase]] = None,
        seed_patches: Optional[List[Individual]] = None,
    ) -> CoevolutionResult:
        """Run adversarial coevolution between patches and tests."""
        t0 = time.monotonic()
        self._stats = []
        self._novelty_archive = []

        # Initialize populations
        patches = seed_patches or self._generate_seed_patches(original_code, error_context)
        tests = initial_tests or self._generate_seed_tests(error_context)

        for gen in range(self.max_generations):
            gen_t0 = time.monotonic()

            # Evaluate all
            for p in patches:
                p.fitness.passes_tests = self.evaluate_patch_against_tests(p.patch_code, tests)

            for t in tests:
                t.effectiveness = self.evaluate_test_effectiveness(t, patches)
                t.novelty = self._compute_novelty(t)

            # Sort
            patches.sort(key=lambda p: p.fitness.passes_tests, reverse=True)
            tests.sort(key=lambda t: t.effectiveness * 0.7 + t.novelty * 0.3, reverse=True)

            # Count robust patches (pass ALL tests)
            robust = [
                p for p in patches
                if self.evaluate_patch_against_tests(p.patch_code, tests) >= 1.0
            ]

            # Arms race intensity
            patch_avg = sum(p.fitness.passes_tests for p in patches) / len(patches)
            test_avg = sum(t.effectiveness for t in tests) / len(tests)
            intensity = abs(patch_avg - test_avg)  # 0 = balanced, 1 = one side dominating

            # Record stats
            stats = CoevolutionStats(
                generation=gen,
                patch_best_fitness=patches[0].fitness.passes_tests if patches else 0,
                test_best_effectiveness=tests[0].effectiveness if tests else 0,
                arms_race_intensity=intensity,
                robust_patches_count=len(robust),
                elapsed_ms=(time.monotonic() - gen_t0) * 1000,
            )
            self._stats.append(stats)
            logger.debug(
                f"Coevo Gen {gen}: patch_best={stats.patch_best_fitness:.2f} "
                f"test_best={stats.test_best_effectiveness:.2f} "
                f"intensity={intensity:.2f} robust={len(robust)}"
            )

            # Archive for novelty
            for t in tests[:3]:
                self._novelty_archive.append(t.code)

            # Early stop: robust patches found
            if len(robust) >= 3:
                logger.info(f"CoevolutionEngine: {len(robust)} robust patches found at gen {gen}")
                break

            # Evolve patches (elitism + crossover + mutation)
            new_patches = patches[:2]  # Elitism
            while len(new_patches) < self.patch_pop_size:
                p1 = random.choice(patches[:self.patch_pop_size // 2])
                p2 = random.choice(patches[:self.patch_pop_size // 2])
                if random.random() < self.crossover_rate:
                    child_code, _ = GeneticOperators.single_point(p1.patch_code, p2.patch_code)
                else:
                    child_code = p1.patch_code
                if random.random() < self.mutation_rate:
                    child_code = GeneticOperators.mutate(child_code, MutationType.LINE_SWAP)
                child = Individual(
                    id=f"coevo-p-gen{gen + 1}-{len(new_patches):03d}",
                    patch_code=child_code,
                    original_code=original_code,
                    generation_born=gen + 1,
                    parent_ids=[p1.id, p2.id],
                )
                new_patches.append(child)
            patches = new_patches

            # Evolve tests (keep effective + mutate)
            new_tests = tests[:2]  # Elitism
            while len(new_tests) < self.test_pop_size:
                parent = random.choice(tests[:self.test_pop_size // 2])
                mutated = TestOperators.mutate_test(parent)
                new_tests.append(mutated)
            tests = new_tests

        # Determine winner
        if robust:
            winner = "patches"
        else:
            winner = "tests" if tests and tests[0].effectiveness > 0.7 else "draw"

        total_elapsed = (time.monotonic() - t0) * 1000
        logger.info(
            f"CoevolutionEngine: complete — {len(self._stats)} gens, "
            f"robust={len(robust)}, winner={winner}, {total_elapsed:.0f}ms"
        )

        return CoevolutionResult(
            robust_patches=robust,
            best_tests=tests[:5],
            stats=self._stats,
            total_elapsed_ms=total_elapsed,
            arms_race_winner=winner,
        )

    def _generate_seed_patches(self, original_code: str, error: str) -> List[Individual]:
        from .genetic_patch_engine import GeneticPatchEngine
        engine = GeneticPatchEngine(population_size=self.patch_pop_size, max_generations=1)
        return engine._generate_seed_population(original_code, error)

    def _generate_seed_tests(self, error_context: str) -> List[TestCase]:
        tests = [
            TestCase("t0", "assert(process(normal_input) == 0);", "Normal input"),
            TestCase("t1", "assert(process(NULL) == -EINVAL);", "NULL input"),
            TestCase("t2", "assert(process(large_input) == -EOVERFLOW);", "Large input"),
            TestCase("t3", "assert(process(empty) == -EINVAL);", "Empty input"),
            TestCase("t4", "assert(process(negative) == -EINVAL);", "Negative input"),
            TestCase("t5", "// Boundary: max size\nassert(process(max_buf) == 0);", "Boundary max"),
            TestCase("t6", "// Boundary: min size\nassert(process(min_buf) == 0);", "Boundary min"),
            TestCase("t7", "// Concurrent access\nassert(thread_safe_test() == 0);", "Thread safety"),
            TestCase("t8", "// Repeated calls\nfor(i=0;i<1000;i++) assert(process(buf)==0);", "Stress test"),
            TestCase("t9", "// Malformed input\nassert(process(corrupted) == -EINVAL);", "Malformed input"),
        ]
        return tests[:self.test_pop_size]
