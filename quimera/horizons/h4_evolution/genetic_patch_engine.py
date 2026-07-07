"""
Quimera Mark X — Genetic Patch Engine (Horizonte 4)

População de patches evoluindo via algoritmo genético com:
  - 4 operadores de crossover (single-point, two-point, uniform, semantic)
  - 6 operadores de mutação (swap, delete, duplicate, rename, operator, constant)
  - 3 estratégias de seleção (tournament, roulette, Pareto NSGA-II)
  - Fitness multi-objetivo: compila + testes + segurança + performance + legibilidade + minimalidade
  - Early stopping + quick_evolve para CI/CD
  - Non-dominated sorting + crowding distance (NSGA-II)

De → Para:
  Antes: 1 patch por vez (refinador linear)
  Agora: População de N patches evoluindo simultaneamente

Usage:
    engine = GeneticPatchEngine(population_size=20, max_generations=50)
    best = engine.evolve(original_code, error_context, language="c")
"""

import copy
import hashlib
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("quimera.h4.genetic")


# ═══════════════════════════════════════════════════════════════════════════
# Data Structures
# ═══════════════════════════════════════════════════════════════════════════

class SelectionStrategy(str, Enum):
    TOURNAMENT = "tournament"
    ROULETTE = "roulette"
    PARETO = "pareto"  # NSGA-II


class CrossoverType(str, Enum):
    SINGLE_POINT = "single_point"
    TWO_POINT = "two_point"
    UNIFORM = "uniform"
    SEMANTIC = "semantic"


class MutationType(str, Enum):
    LINE_SWAP = "line_swap"
    LINE_DELETE = "line_delete"
    LINE_DUPLICATE = "line_duplicate"
    VARIABLE_RENAME = "variable_rename"
    OPERATOR_FLIP = "operator_flip"
    CONSTANT_PERTURB = "constant_perturb"


@dataclass
class FitnessVector:
    """Multi-objective fitness: 6 dimensions, each 0.0-1.0."""
    compiles: float = 0.0        # Does it compile?
    passes_tests: float = 0.0    # Passes test suite?
    security: float = 0.0        # No new vulnerabilities?
    performance: float = 0.0     # Performance regression?
    legibility: float = 0.0      # Code readability
    minimality: float = 0.0      # Minimal diff (not over-engineered)

    @property
    def weighted_score(self) -> float:
        """Weighted aggregate: compiles(0.3) + tests(0.25) + sec(0.2) + perf(0.1) + leg(0.1) + min(0.05)"""
        return (
            self.compiles * 0.30 +
            self.passes_tests * 0.25 +
            self.security * 0.20 +
            self.performance * 0.10 +
            self.legibility * 0.10 +
            self.minimality * 0.05
        )

    def dominates(self, other: "FitnessVector") -> bool:
        """Pareto dominance: self is at least as good in all dimensions AND strictly better in at least one."""
        at_least_as_good = all(
            getattr(self, d) >= getattr(other, d)
            for d in ["compiles", "passes_tests", "security", "performance", "legibility", "minimality"]
        )
        strictly_better = any(
            getattr(self, d) > getattr(other, d)
            for d in ["compiles", "passes_tests", "security", "performance", "legibility", "minimality"]
        )
        return at_least_as_good and strictly_better


@dataclass
class Individual:
    """A single patch in the population."""
    id: str = ""
    patch_code: str = ""
    original_code: str = ""
    fitness: FitnessVector = field(default_factory=FitnessVector)
    generation_born: int = 0
    parent_ids: List[str] = field(default_factory=list)
    pareto_rank: int = 0
    crowding_distance: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def fitness_score(self) -> float:
        return self.fitness.weighted_score


@dataclass
class GenerationStats:
    generation: int
    population_size: int
    best_fitness: float
    avg_fitness: float
    median_fitness: float
    diversity: float
    pareto_front_size: int
    elapsed_ms: float


@dataclass
class EvolutionResult:
    best_individual: Individual
    pareto_front: List[Individual]
    generations: List[GenerationStats]
    total_elapsed_ms: float
    converged: bool
    convergence_generation: int


# ═══════════════════════════════════════════════════════════════════════════
# Operators
# ═══════════════════════════════════════════════════════════════════════════

VARIABLE_NAMES = ["ptr", "buf", "len", "ret", "tmp", "idx", "i", "n", "size", "count", "data", "src", "dst", "result", "offset"]
C_OPERATORS = ["+", "-", "*", "/", "%", "&", "|", "^", "<<", ">>", "&&", "||", "==", "!=", "<", ">", "<=", ">=", "=", "+=", "-="]
LINE_DELIMITERS = ["\n", ";\n", "}\n", "{\n"]


class GeneticOperators:
    """Crossover and mutation operators for C code patches."""

    @staticmethod
    def _split_lines(code: str) -> List[str]:
        return [l for l in code.split("\n") if l.strip()]

    @staticmethod
    def _join_lines(lines: List[str]) -> str:
        return "\n".join(lines)

    # ── Crossover ────────────────────────────────────────────────────

    @staticmethod
    def single_point(parent1: str, parent2: str) -> Tuple[str, str]:
        lines1, lines2 = GeneticOperators._split_lines(parent1), GeneticOperators._split_lines(parent2)
        if len(lines1) < 2 or len(lines2) < 2:
            return parent1, parent2
        p1 = random.randint(1, min(len(lines1), len(lines2)) - 1)
        child1 = GeneticOperators._join_lines(lines1[:p1] + lines2[p1:])
        child2 = GeneticOperators._join_lines(lines2[:p1] + lines1[p1:])
        return child1, child2

    @staticmethod
    def two_point(parent1: str, parent2: str) -> Tuple[str, str]:
        lines1, lines2 = GeneticOperators._split_lines(parent1), GeneticOperators._split_lines(parent2)
        if len(lines1) < 4 or len(lines2) < 4:
            return GeneticOperators.single_point(parent1, parent2)
        p1, p2 = sorted(random.sample(range(1, min(len(lines1), len(lines2)) - 1), 2))
        child1 = GeneticOperators._join_lines(lines1[:p1] + lines2[p1:p2] + lines1[p2:])
        child2 = GeneticOperators._join_lines(lines2[:p1] + lines1[p1:p2] + lines2[p2:])
        return child1, child2

    @staticmethod
    def uniform(parent1: str, parent2: str) -> Tuple[str, str]:
        lines1, lines2 = GeneticOperators._split_lines(parent1), GeneticOperators._split_lines(parent2)
        child1_lines, child2_lines = [], []
        for l1, l2 in zip(lines1, lines2):
            if random.random() < 0.5:
                child1_lines.append(l1); child2_lines.append(l2)
            else:
                child1_lines.append(l2); child2_lines.append(l1)
        return GeneticOperators._join_lines(child1_lines), GeneticOperators._join_lines(child2_lines)

    @staticmethod
    def semantic(parent1: str, parent2: str) -> Tuple[str, str]:
        """Semantic crossover: preserves complete code blocks (functions, if-blocks)."""
        # Split by semantic blocks (functions, if/for/while blocks)
        def find_blocks(code: str) -> List[str]:
            blocks, current = [], []
            depth = 0
            for line in code.split("\n"):
                current.append(line)
                depth += line.count("{") - line.count("}")
                if depth == 0 and len(current) > 1 and "}" in "\n".join(current):
                    blocks.append("\n".join(current))
                    current = []
            if current:
                blocks.append("\n".join(current))
            return blocks or [code]

        blocks1, blocks2 = find_blocks(parent1), find_blocks(parent2)
        if len(blocks1) < 2 or len(blocks2) < 2:
            return GeneticOperators.single_point(parent1, parent2)

        p = random.randint(1, min(len(blocks1), len(blocks2)) - 1)
        child1 = "\n".join(blocks1[:p] + blocks2[p:])
        child2 = "\n".join(blocks2[:p] + blocks1[p:])
        return child1, child2

    # ── Mutation ──────────────────────────────────────────────────────

    @staticmethod
    def line_swap(code: str) -> str:
        lines = GeneticOperators._split_lines(code)
        if len(lines) < 2:
            return code
        i, j = random.sample(range(len(lines)), 2)
        lines[i], lines[j] = lines[j], lines[i]
        return GeneticOperators._join_lines(lines)

    @staticmethod
    def line_delete(code: str) -> str:
        lines = GeneticOperators._split_lines(code)
        if len(lines) < 2:
            return code
        del lines[random.randint(0, len(lines) - 1)]
        return GeneticOperators._join_lines(lines)

    @staticmethod
    def line_duplicate(code: str) -> str:
        lines = GeneticOperators._split_lines(code)
        if not lines:
            return code
        idx = random.randint(0, len(lines) - 1)
        lines.insert(idx, lines[idx])
        return GeneticOperators._join_lines(lines)

    @staticmethod
    def variable_rename(code: str) -> str:
        old = random.choice(VARIABLE_NAMES)
        new = random.choice([n for n in VARIABLE_NAMES if n != old])
        return code.replace(old, new)

    @staticmethod
    def operator_flip(code: str) -> str:
        if not any(op in code for op in C_OPERATORS):
            return code
        old = random.choice([op for op in C_OPERATORS if op in code])
        new = random.choice([op for op in C_OPERATORS if op != old])
        return code.replace(old, new, 1)

    @staticmethod
    def constant_perturb(code: str) -> str:
        import re
        def _perturb(m):
            val = int(m.group())
            delta = random.choice([-1, 1, 2, -2, 8, -8, 16, -16, 64, -64])
            return str(max(0, val + delta))
        return re.sub(r'\b\d+\b', _perturb, code)

    # ── Composite ─────────────────────────────────────────────────────

    @classmethod
    def crossover(cls, parent1: str, parent2: str, ctype: CrossoverType) -> Tuple[str, str]:
        methods = {
            CrossoverType.SINGLE_POINT: cls.single_point,
            CrossoverType.TWO_POINT: cls.two_point,
            CrossoverType.UNIFORM: cls.uniform,
            CrossoverType.SEMANTIC: cls.semantic,
        }
        return methods.get(ctype, cls.single_point)(parent1, parent2)

    @classmethod
    def mutate(cls, code: str, mtype: MutationType) -> str:
        methods = {
            MutationType.LINE_SWAP: cls.line_swap,
            MutationType.LINE_DELETE: cls.line_delete,
            MutationType.LINE_DUPLICATE: cls.line_duplicate,
            MutationType.VARIABLE_RENAME: cls.variable_rename,
            MutationType.OPERATOR_FLIP: cls.operator_flip,
            MutationType.CONSTANT_PERTURB: cls.constant_perturb,
        }
        return methods.get(mtype, lambda c: c)(code)


# ═══════════════════════════════════════════════════════════════════════════
# Genetic Patch Engine
# ═══════════════════════════════════════════════════════════════════════════

class GeneticPatchEngine:
    """Evolves a population of patches using genetic algorithm with NSGA-II."""

    def __init__(
        self,
        population_size: int = 20,
        max_generations: int = 50,
        crossover_rate: float = 0.8,
        mutation_rate: float = 0.15,
        elite_size: int = 2,
        selection_strategy: SelectionStrategy = SelectionStrategy.PARETO,
        fitness_fn: Optional[Callable[[str], FitnessVector]] = None,
        early_stop_generations: int = 10,
        early_stop_threshold: float = 0.001,
    ):
        self.population_size = population_size
        self.max_generations = max_generations
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate
        self.elite_size = elite_size
        self.selection_strategy = selection_strategy
        self.fitness_fn = fitness_fn or self._default_fitness
        self.early_stop_generations = early_stop_generations
        self.early_stop_threshold = early_stop_threshold

        self._generation_history: List[GenerationStats] = []
        self._best_ever: Optional[Individual] = None
        self._diversity_threshold = 0.05

    # ── Default fitness (heuristic-based) ──────────────────────────────

    @staticmethod
    def _default_fitness(code: str) -> FitnessVector:
        """Heuristic fitness when no compiler/test suite is available."""
        return FitnessVector(
            compiles=0.9 if ";" in code and "{" in code and "}" in code else 0.1,
            passes_tests=0.8 if "return" in code and "void" in code else 0.2,
            security=0.85 if "strncpy" in code or "snprintf" in code else (0.3 if "strcpy" in code or "sprintf" in code else 0.7),
            performance=0.7 if "malloc" not in code else 0.5,
            legibility=min(1.0, len(code.split("\n")) / 20.0) if code else 0.1,
            minimality=max(0.1, 1.0 - len(code) / 5000.0) if code else 0.0,
        )

    # ── Selection ──────────────────────────────────────────────────────

    def _select(self, population: List[Individual], k: int = 2) -> Individual:
        if self.selection_strategy == SelectionStrategy.TOURNAMENT:
            candidates = random.sample(population, min(3, len(population)))
            return max(candidates, key=lambda x: x.fitness_score)

        elif self.selection_strategy == SelectionStrategy.ROULETTE:
            total = sum(max(0.001, ind.fitness_score) for ind in population)
            r = random.random() * total
            cum = 0.0
            for ind in population:
                cum += max(0.001, ind.fitness_score)
                if cum >= r:
                    return ind
            return population[-1]

        else:  # PARETO — select from best fronts
            fronts = self._non_dominated_sort(population)
            for front in fronts:
                self._crowding_distance(front)
            # Probability of selecting from front 0 → 70%, front 1 → 20%, rest → 10%
            r = random.random()
            if r < 0.7 and fronts:
                return random.choice(fronts[0])
            elif r < 0.9 and len(fronts) > 1:
                return random.choice(fronts[1])
            else:
                return random.choice(population)

    # ── NSGA-II: Non-Dominated Sorting ─────────────────────────────────

    def _non_dominated_sort(self, population: List[Individual]) -> List[List[Individual]]:
        fronts = []
        dominated_by = {i: set() for i in range(len(population))}
        dominates_count = {i: 0 for i in range(len(population))}

        for i in range(len(population)):
            for j in range(len(population)):
                if i == j:
                    continue
                if population[i].fitness.dominates(population[j].fitness):
                    dominated_by[i].add(j)
                elif population[j].fitness.dominates(population[i].fitness):
                    dominates_count[i] += 1

        front0 = [i for i, c in dominates_count.items() if c == 0]
        current_front = [population[i] for i in front0]
        if current_front:
            fronts.append(current_front)

        visited = set(front0)
        while True:
            next_front = []
            for i in list(visited):
                for j in dominated_by.get(i, set()):
                    if j not in visited:
                        dominates_count[j] -= 1
                        if dominates_count[j] == 0:
                            next_front.append(j)
                            visited.add(j)
            if not next_front:
                break
            fronts.append([population[i] for i in next_front])

        return fronts

    def _crowding_distance(self, front: List[Individual]):
        if len(front) <= 2:
            for ind in front:
                ind.crowding_distance = float("inf") if len(front) <= 1 else 1.0
            return

        for ind in front:
            ind.crowding_distance = 0.0

        for dim in ["compiles", "passes_tests", "security", "performance", "legibility", "minimality"]:
            sorted_front = sorted(front, key=lambda x: getattr(x.fitness, dim))
            min_val = getattr(sorted_front[0].fitness, dim)
            max_val = getattr(sorted_front[-1].fitness, dim)
            if max_val == min_val:
                continue
            sorted_front[0].crowding_distance = float("inf")
            sorted_front[-1].crowding_distance = float("inf")
            for i in range(1, len(sorted_front) - 1):
                sorted_front[i].crowding_distance += (
                    getattr(sorted_front[i + 1].fitness, dim) - getattr(sorted_front[i - 1].fitness, dim)
                ) / (max_val - min_val)

    # ── Diversity ──────────────────────────────────────────────────────

    def _compute_diversity(self, population: List[Individual]) -> float:
        if len(population) < 2:
            return 0.0
        codes = [ind.patch_code for ind in population]
        unique = len(set(c[:100] for c in codes))
        return unique / len(codes)

    # ── Evolution ──────────────────────────────────────────────────────

    def _generate_seed_population(self, original_code: str, error_context: str) -> List[Individual]:
        """Generate initial population from heuristics + LLM if available."""
        population = []

        for i in range(self.population_size):
            code = self._generate_seed_patch(original_code, error_context, i)
            fitness = self.fitness_fn(code)
            ind = Individual(
                id=f"gen0-{i:03d}",
                patch_code=code,
                original_code=original_code,
                fitness=fitness,
                generation_born=0,
            )
            population.append(ind)

        return population

    def _generate_seed_patch(self, code: str, error: str, idx: int) -> str:
        """Generate a diverse seed patch from the original code."""
        lines = code.split("\n")

        strategies = [
            # Strategy 0-4: different mutations
            lambda l: GeneticOperators.variable_rename("\n".join(l)),
            lambda l: GeneticOperators.line_swap("\n".join(l)) if len(l) > 1 else "\n".join(l),
            lambda l: self._add_null_check("\n".join(l)),
            lambda l: self._add_bounds_check("\n".join(l)),
            lambda l: self._replace_unsafe_func("\n".join(l)),
            # Strategy 5-9: combined
            lambda l: self._replace_unsafe_func(self._add_null_check("\n".join(l))),
            lambda l: self._add_bounds_check(GeneticOperators.variable_rename("\n".join(l))),
            lambda l: GeneticOperators.constant_perturb("\n".join(l)),
            lambda l: self._add_error_handling("\n".join(l)),
            lambda l: "\n".join(l),  # Identity
        ]

        strategy = strategies[idx % len(strategies)]
        return strategy(lines) if lines else code

    def _add_null_check(self, code: str) -> str:
        if "NULL" in code or "null" in code:
            return code
        if "malloc" in code:
            return code.replace(
                "malloc(", "if (!(ptr = malloc("
            ).replace(";", "))) return NULL;", 1) if "malloc(" in code else code
        return code

    def _add_bounds_check(self, code: str) -> str:
        if "sizeof" in code and "strcpy" not in code and "strncpy" not in code:
            return code
        if "strcpy" in code:
            return code.replace("strcpy(", "strncpy(").replace(");", ", sizeof(buf)-1);\nbuf[sizeof(buf)-1] = '\\0';", 1)
        return code

    def _replace_unsafe_func(self, code: str) -> str:
        replacements = {
            "strcpy": "strncpy",
            "strcat": "strncat",
            "sprintf": "snprintf",
            "gets": "fgets",
        }
        for old, new in replacements.items():
            if old in code:
                code = code.replace(old + "(", new + "(")
        return code

    def _add_error_handling(self, code: str) -> str:
        if "return" in code and "if" not in code:
            return "if (input == NULL) return -EINVAL;\n" + code
        return code

    # ── Main Evolution Loop ────────────────────────────────────────────

    def evolve(self, original_code: str, error_context: str, language: str = "c") -> EvolutionResult:
        """Run the genetic algorithm to evolve the best patch."""
        t0 = time.monotonic()
        self._generation_history = []
        self._best_ever = None

        # Initialize population
        population = self._generate_seed_population(original_code, error_context)
        best_fitness_no_change = 0

        for gen in range(self.max_generations):
            gen_t0 = time.monotonic()

            # Evaluate fitness (already done in seed, re-evaluate for new generations)
            if gen > 0:
                for ind in population:
                    if not ind.fitness.compiles:  # Re-evaluate if not yet scored
                        ind.fitness = self.fitness_fn(ind.patch_code)

            # Sort by fitness
            population.sort(key=lambda x: x.fitness_score, reverse=True)

            # Track best
            best = population[0]
            if self._best_ever is None or best.fitness_score > self._best_ever.fitness_score:
                self._best_ever = copy.deepcopy(best)
                best_fitness_no_change = 0
            else:
                best_fitness_no_change += 1

            # Non-dominated sorting for Pareto stats
            fronts = self._non_dominated_sort(population)
            pareto_size = len(fronts[0]) if fronts else 0

            # Compute diversity
            diversity = self._compute_diversity(population)

            # Record generation stats
            fitnesses = [ind.fitness_score for ind in population]
            stats = GenerationStats(
                generation=gen,
                population_size=len(population),
                best_fitness=best.fitness_score,
                avg_fitness=sum(fitnesses) / len(fitnesses),
                median_fitness=sorted(fitnesses)[len(fitnesses) // 2],
                diversity=diversity,
                pareto_front_size=pareto_size,
                elapsed_ms=(time.monotonic() - gen_t0) * 1000,
            )
            self._generation_history.append(stats)
            logger.debug(
                f"Gen {gen}: best={stats.best_fitness:.3f} avg={stats.avg_fitness:.3f} "
                f"div={diversity:.2f} pareto={pareto_size}"
            )

            # Early stopping
            if best_fitness_no_change >= self.early_stop_generations:
                logger.info(f"GeneticPatchEngine: converged at generation {gen}")
                break

            # Generate next generation
            new_population: List[Individual] = []

            # Elitism: keep best individuals
            new_population.extend(population[:self.elite_size])

            # Fill rest via selection + crossover + mutation
            while len(new_population) < self.population_size:
                parent1 = self._select(population)
                parent2 = self._select(population)

                if random.random() < self.crossover_rate:
                    ctype = random.choice(list(CrossoverType))
                    child_code, _ = GeneticOperators.crossover(parent1.patch_code, parent2.patch_code, ctype)
                else:
                    child_code = parent1.patch_code

                if random.random() < self.mutation_rate:
                    mtype = random.choice(list(MutationType))
                    child_code = GeneticOperators.mutate(child_code, mtype)

                fitness = self.fitness_fn(child_code)
                child = Individual(
                    id=f"gen{gen + 1}-{len(new_population):03d}",
                    patch_code=child_code,
                    original_code=original_code,
                    fitness=fitness,
                    generation_born=gen + 1,
                    parent_ids=[parent1.id, parent2.id],
                )
                new_population.append(child)

            population = new_population

        # Build result
        pareto_front = fronts[0] if fronts else [self._best_ever] if self._best_ever else []
        converged = best_fitness_no_change >= self.early_stop_generations

        total_elapsed = (time.monotonic() - t0) * 1000
        logger.info(
            f"GeneticPatchEngine: evolution complete — "
            f"{len(self._generation_history)} gens, "
            f"best={self._best_ever.fitness_score:.3f}, "
            f"converged={converged}, "
            f"{total_elapsed:.0f}ms"
        )

        return EvolutionResult(
            best_individual=self._best_ever or population[0],
            pareto_front=pareto_front,
            generations=self._generation_history,
            total_elapsed_ms=total_elapsed,
            converged=converged,
            convergence_generation=len(self._generation_history) - self.early_stop_generations if converged else -1,
        )

    def quick_evolve(self, original_code: str, error_context: str) -> Individual:
        """Fast evolution for CI/CD (reduced pop size and generations)."""
        saved_pop, saved_gen = self.population_size, self.max_generations
        self.population_size = 10
        self.max_generations = 10
        try:
            result = self.evolve(original_code, error_context)
            return result.best_individual
        finally:
            self.population_size = saved_pop
            self.max_generations = saved_gen
