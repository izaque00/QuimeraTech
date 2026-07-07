"""CoEvolution Engine — Coevolução de Patches e Testes.

Implementa coevolução competitiva onde patches e testes evoluem juntos:
- Patches evoluem para passar nos testes
- Testes evoluem para quebrar patches
- Ciclo adversarial que produz patches mais robustos e testes mais eficazes

Inspirado por:
- Coevolutionary Genetic Algorithms (Paredis, 1995)
- Adversarial Testing (fuzzing + evolução)
- Novelty Search para diversidade

Arquitetura:
    População de Patches ←→ População de Testes
           ↓                        ↓
    [Fitness contra testes]  [Efetividade contra patches]
           ↓                        ↓
    [Crossover + Mutação]    [Crossover + Mutação]
           ↓                        ↓
    [Nova População]         [Nova População de Testes]
           ↓________________________↓
    [Avaliação Cruzada] → repete

Uso:
    from quimera.agentes.coevolution_engine import CoevolutionEngine
    
    coevo = CoevolutionEngine(
        patch_population_size=20,
        test_population_size=15,
        generations=10,
    )
    
    result = coevo.coevolve(
        original_code=original_c,
        compile_fn=my_compile_fn,
        initial_tests=my_tests,
    )
    
    print(f"Melhor patch fitness: {result.best_patch_fitness}")
    print(f"Testes que quebram >50% dos patches: {len(result.best_tests)}")
"""

import random
import logging
import time
import copy
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple, Set
from enum import Enum

from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)

try:
    from quimera.agentes.genetic_patch_engine import (
        GeneticPatchEngine,
        Individual,
        FitnessVector,
        FitnessDimension,
        SelectionStrategy,
        CrossoverOperator,
        MutationOperator,
        FitnessFunctions,
    )
    GENETIC_AVAILABLE = True
except ImportError:
    GENETIC_AVAILABLE = False


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class TestIndividual:
    """Um teste na população de testes."""
    id: str
    test_code: str
    effectiveness: float = 0.0  # 0-1, fração de patches que quebra
    novelty: float = 0.0        # Quão diferente é dos outros testes
    generation_born: int = 0
    patches_broken: List[str] = field(default_factory=list)

    def fitness(self) -> float:
        """Fitness do teste: efetividade + bônus de novidade."""
        return 0.7 * self.effectiveness + 0.3 * self.novelty


@dataclass
class CoevolutionStats:
    """Estatísticas de uma geração coevolutiva."""
    generation: int
    patch_best_fitness: float
    patch_avg_fitness: float
    test_best_effectiveness: float
    test_avg_effectiveness: float
    patches_passing_all: int
    arms_race_intensity: float  # 0-1, quão competitivo está
    elapsed_ms: float


@dataclass
class CoevolutionResult:
    """Resultado completo da coevolução."""
    best_patch: Individual
    best_patch_fitness: float
    best_tests: List[TestIndividual]  # Testes mais efetivos
    robust_patches: List[Individual]  # Patches que passam todos os testes
    pareto_front: List[Individual]
    generation_stats: List[CoevolutionStats]
    total_generations: int
    total_time_ms: float

    def summary(self) -> str:
        return (
            f"Coevolução: {self.total_generations} gerações, "
            f"melhor fitness={self.best_patch_fitness:.3f}, "
            f"{len(self.robust_patches)} patches robustos, "
            f"{len(self.best_tests)} testes efetivos"
        )


# ============================================================================
# Test Mutation Operators
# ============================================================================

class TestMutation:
    """Operadores de mutação específicos para testes."""

    @staticmethod
    def tighten_bounds(code: str) -> str:
        """Aperta bounds de arrays/loops no teste."""
        # Torna condições mais estritas: ≤ → <, < N → < N-1
        replacements = [
            (r'<=\s*(\d+)', lambda m: f'< {int(m.group(1)) + 1}'),
            (r'<\s*(\d+)', lambda m: f'< {max(1, int(m.group(1)) - 1)}'),
            (r'>=\s*(\d+)', lambda m: f'> {int(m.group(1)) - 1}'),
        ]
        for pattern, repl_fn in replacements:
            code = re.sub(pattern, repl_fn, code)
        return code

    @staticmethod
    def add_null_check(code: str) -> str:
        """Adiciona verificação de NULL em acessos de ponteiro."""
        ptr_patterns = re.findall(r'(\w+)->(\w+)', code)
        if not ptr_patterns:
            return code
        ptr_name = ptr_patterns[0][0]
        check = f'if ({ptr_name} == NULL) {{ printf("NULL deref!\\n"); return -1; }}'
        lines = code.splitlines()
        # Insere antes da primeira linha de código
        for i, line in enumerate(lines):
            if line.strip() and not line.strip().startswith('#') and not line.strip().startswith('//'):
                lines.insert(i, check)
                break
        return '\n'.join(lines)

    @staticmethod
    def add_edge_case(code: str) -> str:
        """Adiciona caso de borda ao teste."""
        edge_template = """
    // Edge case: empty/boundary
    {
        char edge_buf[1] = {0};
        int result = target_function(edge_buf, 0);
        if (result != EXPECTED_EDGE) {
            printf("EDGE CASE FAILED\\n");
            return -1;
        }
    }
"""
        last_brace = code.rfind('}')
        if last_brace > 0:
            return code[:last_brace] + edge_template + code[last_brace:]
        return code + edge_template

    @staticmethod
    def invert_expected(code: str) -> str:
        """Inverte resultado esperado (teste mais rigoroso)."""
        replacements = [
            (r'== 0', '!= 0'),
            (r'!= 0', '== 0'),
            (r'> 0', '<= 0'),
            (r'< 0', '>= 0'),
            (r'== NULL', '!= NULL'),
        ]
        for old, new in random.sample(replacements, min(3, len(replacements))):
            if old in code:
                code = code.replace(old, new, 1)
                break
        return code

    @staticmethod
    def random_test_mutation(code: str) -> str:
        """Aplica uma mutação de teste aleatória."""
        ops = [
            TestMutation.tighten_bounds,
            TestMutation.add_null_check,
            TestMutation.add_edge_case,
            TestMutation.invert_expected,
        ]
        op = random.choice(ops)
        try:
            return op(code)
        except Exception as e:
            logger.debug(f"Test mutation {op.__name__} failed: {e}")
            return code


# ============================================================================
# Coevolution Engine
# ============================================================================

class CoevolutionEngine:
    """Motor de coevolução adversarial entre patches e testes.

    Mantém duas populações que evoluem competitivamente:
    - Patches tentam passar nos testes
    - Testes tentam quebrar patches

    Attributes:
        patch_population_size: Tamanho da população de patches.
        test_population_size: Tamanho da população de testes.
        generations: Número de gerações coevolutivas.
        arms_race_threshold: Se intensity > threshold, aumentar pressão seletiva.
    """

    def __init__(
        self,
        patch_population_size: int = 20,
        test_population_size: int = 15,
        generations: int = 10,
        elite_size: int = 2,
        mutation_rate: float = 0.3,
        crossover_rate: float = 0.6,
        arms_race_threshold: float = 0.7,
    ):
        if not GENETIC_AVAILABLE:
            raise ImportError("GeneticPatchEngine não disponível")

        self.patch_pop_size = patch_population_size
        self.test_pop_size = test_population_size
        self.generations = generations
        self.elite_size = elite_size
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.arms_race_threshold = arms_race_threshold

        self._patch_engine = GeneticPatchEngine(
            population_size=patch_population_size,
            generations=1,  # Controlamos o loop externamente
            elite_size=elite_size,
            mutation_rate=mutation_rate,
            crossover_rate=crossover_rate,
        )

        self._patch_population: List[Individual] = []
        self._test_population: List[TestIndividual] = []
        self._stats: List[CoevolutionStats] = []

    # ------------------------------------------------------------------
    # API Principal
    # ------------------------------------------------------------------

    def coevolve(
        self,
        original_code: str,
        compile_fn: Callable[[str], bool],
        test_runner: Callable[[str, str], bool],
        initial_patches: Optional[List[str]] = None,
        initial_tests: Optional[List[str]] = None,
    ) -> CoevolutionResult:
        """Executa coevolução adversarial completa.

        Args:
            original_code: Código C original.
            compile_fn: Função (code) → bool (compila?).
            test_runner: Função (patch_code, test_code) → bool (passa?).
            initial_patches: Patches iniciais.
            initial_tests: Testes iniciais.

        Returns:
            CoevolutionResult com melhores patches e testes.
        """
        start_time = time.time()

        # Inicializar populações
        self._initialize_patches(original_code, initial_patches or [], compile_fn)
        self._initialize_tests(initial_tests or [])

        best_patch_ever = None
        best_fitness_ever = 0.0
        best_tests_ever: List[TestIndividual] = []

        # Loop coevolutivo
        for gen in range(self.generations):
            gen_start = time.time()

            # 1. Avaliar patches contra testes atuais
            self._evaluate_patches_against_tests(test_runner)

            # 2. Avaliar testes contra patches atuais
            self._evaluate_tests_against_patches(test_runner)

            # 3. Evoluir patches (seleção + crossover + mutação)
            self._evolve_patches(compile_fn)

            # 4. Evoluir testes (seleção + mutação)
            self._evolve_tests()

            # 5. Calcular intensidade da corrida armamentista
            arms_race = self._calculate_arms_race_intensity()

            # 6. Registrar estatísticas
            gen_stats = self._compute_stats(gen, time.time() - gen_start, arms_race)
            self._stats.append(gen_stats)

            # 7. Atualizar melhores
            current_best = max(
                self._patch_population,
                key=lambda ind: ind.fitness.weighted_sum()
            )
            current_fitness = current_best.fitness.weighted_sum()
            if current_fitness > best_fitness_ever:
                best_fitness_ever = current_fitness
                best_patch_ever = current_best

            effective_tests = [
                t for t in self._test_population if t.effectiveness > 0.5
            ]
            if len(effective_tests) > len(best_tests_ever):
                best_tests_ever = effective_tests

            montar_log(
                f"CoEvolution gen {gen}: "
                f"patch_best={gen_stats.patch_best_fitness:.3f} "
                f"test_best={gen_stats.test_best_effectiveness:.3f} "
                f"arms_race={arms_race:.2f}",
                "DEBUG"
            )

        # Encontrar patches robustos (passam todos os testes)
        robust_patches = self._find_robust_patches(test_runner)

        # Pareto front dos patches
        pareto_front = SelectionStrategy.pareto_selection(
            self._patch_population,
            min(5, len(self._patch_population))
        )

        total_time = (time.time() - start_time) * 1000

        result = CoevolutionResult(
            best_patch=best_patch_ever,  # type: ignore[arg-type]
            best_patch_fitness=best_fitness_ever,
            best_tests=best_tests_ever,
            robust_patches=robust_patches,
            pareto_front=pareto_front,
            generation_stats=self._stats,
            total_generations=self.generations,
            total_time_ms=total_time,
        )

        montar_log(f"CoevolutionEngine: {result.summary()}", "INFO")
        return result

    # ------------------------------------------------------------------
    # Inicialização
    # ------------------------------------------------------------------

    def _initialize_patches(
        self,
        original_code: str,
        initial_patches: List[str],
        compile_fn: Callable[[str], bool],
    ):
        """Inicializa população de patches."""
        population = []

        # Original
        population.append(Individual(
            id="coevo_patch_original",
            patch_code=original_code,
        ))

        # Seeds
        for i, patch in enumerate(initial_patches):
            population.append(Individual(
                id=f"coevo_patch_seed_{i}",
                patch_code=patch,
            ))

        # Aleatórios
        base = original_code or (initial_patches[0] if initial_patches else "")
        for i in range(len(population), self.patch_pop_size):
            mutated = MutationOperator.variable_rename(base)
            mutated = MutationOperator.constant_perturb(mutated)
            population.append(Individual(
                id=f"coevo_patch_rand_{i}",
                patch_code=mutated,
            ))

        self._patch_population = population[:self.patch_pop_size]

    def _initialize_tests(self, initial_tests: List[str]):
        """Inicializa população de testes."""
        tests = []

        for i, test in enumerate(initial_tests):
            tests.append(TestIndividual(
                id=f"coevo_test_seed_{i}",
                test_code=test,
            ))

        # Gerar testes por mutação dos iniciais
        base_tests = initial_tests if initial_tests else [
            'void test_basic() { int result = target(5); assert(result == EXPECTED); }'
        ]

        while len(tests) < self.test_pop_size:
            base = random.choice(base_tests)
            mutated = TestMutation.random_test_mutation(base)
            tests.append(TestIndividual(
                id=f"coevo_test_rand_{len(tests)}",
                test_code=mutated,
            ))

        self._test_population = tests[:self.test_pop_size]

    # ------------------------------------------------------------------
    # Avaliação Cruzada
    # ------------------------------------------------------------------

    def _evaluate_patches_against_tests(
        self,
        test_runner: Callable[[str, str], bool],
    ):
        """Avalia cada patch contra todos os testes."""
        for patch in self._patch_population:
            passed = 0
            total = len(self._test_population)
            for test in self._test_population:
                try:
                    if test_runner(patch.patch_code, test.test_code):
                        passed += 1
                except Exception as e:
                    logger.debug(f"Test runner failed for patch {patch.id}: {e}")
            ratio = passed / max(total, 1)
            patch.fitness.scores[FitnessDimension.TESTS_PASSED] = ratio

    def _evaluate_tests_against_patches(
        self,
        test_runner: Callable[[str, str], bool],
    ):
        """Avalia cada teste contra todos os patches."""
        for test in self._test_population:
            broken = 0
            total = len(self._patch_population)
            test.patches_broken = []
            for patch in self._patch_population:
                try:
                    if not test_runner(patch.patch_code, test.test_code):
                        broken += 1
                        test.patches_broken.append(patch.id)
                except Exception as e:
                    logger.debug(f"Test runner failed for test {test.id}: {e}")
                    broken += 1
                    test.patches_broken.append(patch.id)
            test.effectiveness = broken / max(total, 1)

        # Calcular novelty (quão diferente cada teste é dos outros)
        for test in self._test_population:
            test.novelty = self._calculate_novelty(test, self._test_population)

    def _calculate_novelty(
        self,
        test: TestIndividual,
        population: List[TestIndividual],
    ) -> float:
        """Calcula novidade de um teste baseado em quão único é seu perfil de quebra."""
        if len(population) <= 1:
            return 1.0

        my_set = set(test.patches_broken)
        similarities = []
        for other in population:
            if other.id == test.id:
                continue
            other_set = set(other.patches_broken)
            if not my_set and not other_set:
                similarities.append(1.0)
            elif not my_set or not other_set:
                similarities.append(0.0)
            else:
                jaccard = len(my_set & other_set) / len(my_set | other_set)
                similarities.append(jaccard)

        if not similarities:
            return 1.0
        return 1.0 - (sum(similarities) / len(similarities))

    # ------------------------------------------------------------------
    # Evolução
    # ------------------------------------------------------------------

    def _evolve_patches(self, compile_fn: Callable[[str], bool]):
        """Evolui a população de patches."""
        # Selecionar elite
        elite = SelectionStrategy.elitism(
            self._patch_population,
            min(self.elite_size, len(self._patch_population))
        )

        new_pop = list(elite)
        while len(new_pop) < self.patch_pop_size:
            # Selecionar pais
            p1 = SelectionStrategy.tournament(self._patch_population, 3)
            p2 = SelectionStrategy.tournament(self._patch_population, 3)

            # Crossover
            if random.random() < self.crossover_rate:
                child_code = CrossoverOperator.semantic(p1.patch_code, p2.patch_code)
            else:
                child_code = p1.patch_code

            # Mutação
            if random.random() < self.mutation_rate:
                child_code = MutationOperator.variable_rename(child_code)
                child_code = MutationOperator.constant_perturb(child_code)

            child = Individual(
                id=f"coevo_patch_gen{len(self._stats)}_{len(new_pop)}",
                patch_code=child_code,
                generation_born=len(self._stats),
                parents=[p1.id, p2.id],
            )

            # Avaliar compilação
            child.fitness.scores[FitnessDimension.COMPILES] = (
                1.0 if compile_fn(child_code) else 0.0
            )

            new_pop.append(child)

        self._patch_population = new_pop[:self.patch_pop_size]

    def _evolve_tests(self):
        """Evolui a população de testes."""
        # Manter elite de testes efetivos
        sorted_tests = sorted(
            self._test_population,
            key=lambda t: t.fitness(),
            reverse=True
        )
        elite = sorted_tests[:self.elite_size]
        new_tests = list(elite)

        while len(new_tests) < self.test_pop_size:
            # Selecionar pais por torneio
            candidates = random.sample(
                self._test_population,
                min(3, len(self._test_population))
            )
            parent = max(candidates, key=lambda t: t.fitness())

            # Mutação
            mutated = TestMutation.random_test_mutation(parent.test_code)

            new_tests.append(TestIndividual(
                id=f"coevo_test_gen{len(self._stats)}_{len(new_tests)}",
                test_code=mutated,
                generation_born=len(self._stats),
            ))

        self._test_population = new_tests[:self.test_pop_size]

    # ------------------------------------------------------------------
    # Análise
    # ------------------------------------------------------------------

    def _calculate_arms_race_intensity(self) -> float:
        """Calcula intensidade da corrida armamentista entre patches e testes."""
        if not self._patch_population or not self._test_population:
            return 0.0

        # Intensidade = quão bem os testes estão quebrando patches
        # Se testes quebram >70% dos patches → alta intensidade
        avg_test_effectiveness = sum(
            t.effectiveness for t in self._test_population
        ) / len(self._test_population)

        avg_patch_pass = sum(
            ind.fitness.scores.get(FitnessDimension.TESTS_PASSED, 0)
            for ind in self._patch_population
        ) / len(self._patch_population)

        # Arms race = balance between test effectiveness and patch resilience
        intensity = (avg_test_effectiveness + (1 - avg_patch_pass)) / 2
        return intensity

    def _find_robust_patches(
        self,
        test_runner: Callable[[str, str], bool],
    ) -> List[Individual]:
        """Encontra patches que passam em todos os testes."""
        robust = []
        for patch in self._patch_population:
            all_pass = True
            for test in self._test_population:
                try:
                    if not test_runner(patch.patch_code, test.test_code):
                        all_pass = False
                        break
                except Exception:
                    all_pass = False
                    break
            if all_pass and self._test_population:
                robust.append(patch)
        return robust

    def _compute_stats(
        self,
        generation: int,
        elapsed_s: float,
        arms_race: float,
    ) -> CoevolutionStats:
        """Computa estatísticas da geração."""
        patch_fitnesses = [
            ind.fitness.weighted_sum() for ind in self._patch_population
        ]
        test_effs = [t.effectiveness for t in self._test_population]

        patches_passing = sum(
            1 for ind in self._patch_population
            if ind.fitness.scores.get(FitnessDimension.TESTS_PASSED, 0) > 0.99
        )

        return CoevolutionStats(
            generation=generation,
            patch_best_fitness=max(patch_fitnesses) if patch_fitnesses else 0.0,
            patch_avg_fitness=sum(patch_fitnesses) / len(patch_fitnesses) if patch_fitnesses else 0.0,
            test_best_effectiveness=max(test_effs) if test_effs else 0.0,
            test_avg_effectiveness=sum(test_effs) / len(test_effs) if test_effs else 0.0,
            patches_passing_all=patches_passing,
            arms_race_intensity=arms_race,
            elapsed_ms=elapsed_s * 1000,
        )
