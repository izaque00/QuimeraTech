"""GeneticPatchEngine — Evolução Genética de Patches de Código C.

Evolui uma POPULAÇÃO de patches (não apenas 1) usando:
- Crossover: combinar 2 patches → novo patch híbrido
- Mutação: heurísticas de mutação existentes + novas
- Seleção: fitness multi-objetivo (compila + testes + performance + segurança)
- Pareto frontier: trade-off entre objetivos conflitantes (ex: perf vs segurança)
- Coevolução: patches e testes evoluem juntos

Substitui a evolução linear do refinador_v3 por evolução populacional:
    Antes: 1 patch → heurística → 1 patch melhorado → repete
    Agora: N patches → crossover + mutação → seleção → próxima geração

Arquitetura:
    População inicial (N patches)
        ↓
    [Fitness Evaluation] → compila? passa testes? seguro? rápido?
        ↓
    [Selection] → torneio, elite, Pareto frontier
        ↓
    [Crossover] → combinar 2 patches pais → 1 filho
        ↓
    [Mutation] → heurísticas de mutação (do refinador_v3)
        ↓
    [Nova População] → repete até convergência

Uso:
    from quimera.agentes.genetic_patch_engine import GeneticPatchEngine
    
    engine = GeneticPatchEngine(
        population_size=20,
        generations=10,
        elite_size=2,
        mutation_rate=0.3,
        crossover_rate=0.7,
    )
    
    result = engine.evolve(
        original_code=original_c,
        fitness_function=my_fitness_fn,
        initial_patches=seed_patches,
    )
    
    print(f"Melhor patch (geração {result.best_generation}): "
          f"fitness={result.best_fitness:.3f}")
"""

import random
import logging
import time
import copy
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Callable, Set
from enum import Enum
from pathlib import Path
from collections import defaultdict
import math

from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================

class FitnessDimension(Enum):
    """Dimensões do fitness multi-objetivo."""
    COMPILES = "compiles"             # Compila sem erros? (binário)
    TESTS_PASSED = "tests_passed"     # Passa nos testes? (0-1)
    PERFORMANCE = "performance"       # Performance relativa (0-1, maior = melhor)
    SECURITY = "security"             # Score de segurança (0-1)
    READABILITY = "readability"       # Legibilidade do código (0-1)
    MINIMALITY = "minimality"         # Minimalidade (0-1, menor diff = melhor)


@dataclass
class FitnessVector:
    """Vetor de fitness multi-objetivo."""
    scores: Dict[FitnessDimension, float] = field(default_factory=dict)

    def __post_init__(self):
        for dim in FitnessDimension:
            if dim not in self.scores:
                self.scores[dim] = 0.0

    def weighted_sum(self, weights: Optional[Dict[FitnessDimension, float]] = None) -> float:
        """Soma ponderada dos scores."""
        if weights is None:
            weights = {
                FitnessDimension.COMPILES: 0.25,
                FitnessDimension.TESTS_PASSED: 0.25,
                FitnessDimension.PERFORMANCE: 0.10,
                FitnessDimension.SECURITY: 0.25,
                FitnessDimension.READABILITY: 0.10,
                FitnessDimension.MINIMALITY: 0.05,
            }
        return sum(self.scores.get(d, 0.0) * w for d, w in weights.items())

    def dominates(self, other: "FitnessVector") -> bool:
        """Pareto dominance: self domina other se não é pior em nada e é melhor em pelo menos uma."""
        at_least_one_better = False
        for dim in FitnessDimension:
            if self.scores[dim] < other.scores[dim]:
                return False
            if self.scores[dim] > other.scores[dim]:
                at_least_one_better = True
        return at_least_one_better

    def to_dict(self) -> Dict[str, float]:
        return {d.value: s for d, s in self.scores.items()}


@dataclass
class Individual:
    """Um indivíduo na população (um patch)."""
    id: str
    patch_code: str
    fitness: FitnessVector = field(default_factory=FitnessVector)
    generation_born: int = 0
    parents: List[str] = field(default_factory=list)
    mutation_history: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    pareto_rank: int = 0  # 0 = fronteira de Pareto
    crowding_distance: float = 0.0

    def clone(self) -> "Individual":
        """Cria uma cópia profunda."""
        return Individual(
            id=f"{self.id}_clone_{random.randint(0, 9999)}",
            patch_code=self.patch_code,
            fitness=FitnessVector(scores=dict(self.fitness.scores)),
            generation_born=self.generation_born,
            parents=list(self.parents),
            mutation_history=list(self.mutation_history),
            metadata=dict(self.metadata),
            pareto_rank=self.pareto_rank,
            crowding_distance=self.crowding_distance,
        )


@dataclass
class GenerationStats:
    """Estatísticas de uma geração."""
    generation: int
    population_size: int
    best_fitness: float
    avg_fitness: float
    median_fitness: float
    pareto_front_size: int
    diversity: float  # 0-1, dissimilaridade média
    new_best_found: bool
    elapsed_ms: float


@dataclass
class EvolutionResult:
    """Resultado completo da evolução genética."""
    best_individual: Individual
    best_generation: int
    best_fitness: float
    pareto_front: List[Individual]
    generation_stats: List[GenerationStats]
    total_generations: int
    total_time_ms: float
    convergence_generation: Optional[int] = None
    fitness_history: List[float] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"Evolução concluída: {self.total_generations} gerações, "
            f"melhor fitness={self.best_fitness:.3f} (geração {self.best_generation}), "
            f"Pareto front={len(self.pareto_front)} indivíduos, "
            f"tempo={self.total_time_ms/1000:.1f}s"
        )


# ============================================================================
# Genetic Operators
# ============================================================================

class CrossoverOperator:
    """Operadores de crossover (recombinação) de patches."""

    @staticmethod
    def single_point(parent1: str, parent2: str) -> str:
        """Crossover de ponto único: divide e combina."""
        lines1 = parent1.splitlines()
        lines2 = parent2.splitlines()

        if not lines1 or not lines2:
            return parent1 if lines1 else parent2

        max_len = min(len(lines1), len(lines2))
        if max_len < 2:
            return parent1

        point = random.randint(1, max_len - 1)
        child_lines = lines1[:point] + lines2[point:]
        return "\n".join(child_lines)

    @staticmethod
    def two_point(parent1: str, parent2: str) -> str:
        """Crossover de dois pontos."""
        lines1 = parent1.splitlines()
        lines2 = parent2.splitlines()

        max_len = min(len(lines1), len(lines2))
        if max_len < 3:
            return CrossoverOperator.single_point(parent1, parent2)

        p1 = random.randint(1, max_len - 2)
        p2 = random.randint(p1 + 1, max_len - 1)

        child_lines = lines1[:p1] + lines2[p1:p2] + lines1[p2:]
        return "\n".join(child_lines)

    @staticmethod
    def uniform(parent1: str, parent2: str) -> str:
        """Crossover uniforme: cada linha vem de um pai aleatório."""
        lines1 = parent1.splitlines()
        lines2 = parent2.splitlines()

        max_len = max(len(lines1), len(lines2))
        child_lines = []
        for i in range(max_len):
            line1 = lines1[i] if i < len(lines1) else ""
            line2 = lines2[i] if i < len(lines2) else ""
            child_lines.append(line1 if random.random() < 0.5 else line2)
        return "\n".join(child_lines)

    @staticmethod
    def semantic(parent1: str, parent2: str) -> str:
        """Crossover semântico: preserva blocos inteiros."""
        # Divide por blocos (funções, structs, etc.)
        def extract_blocks(code: str) -> List[str]:
            blocks = []
            current = []
            depth = 0
            for line in code.splitlines():
                depth += line.count("{") - line.count("}")
                current.append(line)
                if depth == 0 and current:
                    blocks.append("\n".join(current))
                    current = []
            if current:
                blocks.append("\n".join(current))
            return blocks

        blocks1 = extract_blocks(parent1)
        blocks2 = extract_blocks(parent2)

        if not blocks1 or not blocks2:
            return CrossoverOperator.two_point(parent1, parent2)

        # Metade dos blocos de cada pai
        split = len(blocks1) // 2
        child_blocks = blocks1[:split] + blocks2[split:]
        return "\n".join(child_blocks)


class MutationOperator:
    """Operadores de mutação de patches."""

    @staticmethod
    def line_swap(code: str) -> str:
        """Troca duas linhas aleatórias."""
        lines = code.splitlines()
        if len(lines) < 2:
            return code
        i, j = random.sample(range(len(lines)), 2)
        lines[i], lines[j] = lines[j], lines[i]
        return "\n".join(lines)

    @staticmethod
    def line_delete(code: str) -> str:
        """Remove uma linha aleatória."""
        lines = code.splitlines()
        if len(lines) <= 1:
            return code
        i = random.randint(0, len(lines) - 1)
        del lines[i]
        return "\n".join(lines)

    @staticmethod
    def line_duplicate(code: str) -> str:
        """Duplica uma linha aleatória."""
        lines = code.splitlines()
        if not lines:
            return code
        i = random.randint(0, len(lines) - 1)
        lines.insert(i, lines[i])
        return "\n".join(lines)

    @staticmethod
    def variable_rename(code: str) -> str:
        """Renomeia uma variável aleatória."""
        import re
        # Encontra identificadores
        identifiers = set(re.findall(r'\b[a-zA-Z_]\w*\b', code))
        reserved = {'if', 'else', 'for', 'while', 'return', 'int', 'char',
                     'void', 'struct', 'sizeof', 'static', 'const', 'unsigned',
                     'long', 'short', 'double', 'float', 'break', 'continue',
                     'goto', 'switch', 'case', 'default', 'do', 'typedef',
                     'enum', 'union', 'extern', 'register', 'volatile'}
        candidates = list(identifiers - reserved)
        if len(candidates) < 1:
            return code
        target = random.choice(candidates)
        new_name = f"{target}_v{random.randint(0, 99)}"
        # Substituição com word boundaries
        return re.sub(rf'\b{target}\b', new_name, code)

    @staticmethod
    def operator_flip(code: str) -> str:
        """Troca um operador: + ↔ -, < ↔ >, == ↔ !=."""
        flips = [("+", "-"), ("<", ">"), ("<=", ">="), ("==", "!="),
                 ("&&", "||"), ("++", "--"), ("*", "/")]
        for a, b in random.sample(flips, len(flips)):
            if a in code:
                # Troca apenas uma ocorrência
                idx = code.find(a)
                return code[:idx] + b + code[idx + len(a):]
        return code

    @staticmethod
    def constant_perturb(code: str) -> str:
        """Perturba uma constante numérica."""
        import re
        numbers = list(re.finditer(r'\b(\d+)\b', code))
        if not numbers:
            return code
        match = random.choice(numbers)
        val = int(match.group(1))
        delta = random.choice([-1, 1, -2, 2, 10, -10, val // 2, -val // 2])
        new_val = max(0, val + delta)
        return code[:match.start()] + str(new_val) + code[match.end():]


# ============================================================================
# Selection Strategies
# ============================================================================

class SelectionStrategy:
    """Estratégias de seleção para evolução genética."""

    @staticmethod
    def tournament(
        population: List[Individual],
        tournament_size: int = 3,
        key: Callable[[Individual], float] = lambda ind: ind.fitness.weighted_sum()
    ) -> Individual:
        """Seleção por torneio."""
        candidates = random.sample(
            population,
            min(tournament_size, len(population))
        )
        return max(candidates, key=key)

    @staticmethod
    def roulette_wheel(
        population: List[Individual],
        key: Callable[[Individual], float] = lambda ind: ind.fitness.weighted_sum()
    ) -> Individual:
        """Seleção por roleta (proporcional ao fitness)."""
        fitnesses = [max(key(ind), 1e-10) for ind in population]
        total = sum(fitnesses)
        r = random.random() * total
        cumulative = 0.0
        for ind, fit in zip(population, fitnesses):
            cumulative += fit
            if cumulative >= r:
                return ind
        return population[-1]

    @staticmethod
    def elitism(population: List[Individual], n: int) -> List[Individual]:
        """Retorna os n melhores indivíduos."""
        sorted_pop = sorted(
            population,
            key=lambda ind: ind.fitness.weighted_sum(),
            reverse=True
        )
        return sorted_pop[:n]

    @staticmethod
    def pareto_selection(
        population: List[Individual],
        n: int
    ) -> List[Individual]:
        """Seleção baseada em Pareto: preserva diversidade de objetivos."""
        # NSGA-II style: non-dominated sorting + crowding distance
        fronts = SelectionStrategy._non_dominated_sort(population)
        selected = []
        for front in fronts:
            if len(selected) + len(front) <= n:
                selected.extend(front)
            else:
                # Preencher o restante com crowding distance
                remaining = n - len(selected)
                front_sorted = sorted(
                    front,
                    key=lambda ind: ind.crowding_distance,
                    reverse=True
                )
                selected.extend(front_sorted[:remaining])
                break
        return selected

    @staticmethod
    def _non_dominated_sort(
        population: List[Individual]
    ) -> List[List[Individual]]:
        """Non-dominated sorting (NSGA-II)."""
        fronts: List[List[Individual]] = [[]]
        domination_counts: Dict[str, int] = {}
        dominated_by: Dict[str, List[Individual]] = defaultdict(list)

        for p in population:
            domination_counts[p.id] = 0
            for q in population:
                if p.id == q.id:
                    continue
                if p.fitness.dominates(q.fitness):
                    dominated_by[p.id].append(q)
                elif q.fitness.dominates(p.fitness):
                    domination_counts[p.id] += 1

        # Primeira fronteira: indivíduos não dominados
        for p in population:
            if domination_counts[p.id] == 0:
                p.pareto_rank = 0
                fronts[0].append(p)

        i = 0
        while i < len(fronts) and fronts[i]:
            next_front = []
            for p in fronts[i]:
                for q in dominated_by[p.id]:
                    domination_counts[q.id] -= 1
                    if domination_counts[q.id] == 0:
                        q.pareto_rank = i + 1
                        next_front.append(q)
            i += 1
            if next_front:
                fronts.append(next_front)

        # Calcular crowding distance
        for front in fronts:
            SelectionStrategy._crowding_distance(front)

        return fronts

    @staticmethod
    def _crowding_distance(front: List[Individual]):
        """Calcula crowding distance para diversidade."""
        if len(front) <= 2:
            for ind in front:
                ind.crowding_distance = float('inf')
            return

        for ind in front:
            ind.crowding_distance = 0.0

        for dim in FitnessDimension:
            front_sorted = sorted(front, key=lambda x: x.fitness.scores[dim])
            f_min = front_sorted[0].fitness.scores[dim]
            f_max = front_sorted[-1].fitness.scores[dim]
            if f_max == f_min:
                continue

            front_sorted[0].crowding_distance = float('inf')
            front_sorted[-1].crowding_distance = float('inf')

            for i in range(1, len(front_sorted) - 1):
                front_sorted[i].crowding_distance += (
                    (front_sorted[i + 1].fitness.scores[dim] -
                     front_sorted[i - 1].fitness.scores[dim]) /
                    (f_max - f_min)
                )


# ============================================================================
# Fitness Functions
# ============================================================================

class FitnessFunctions:
    """Funções de fitness pré-definidas."""

    @staticmethod
    def default_weights() -> Dict[FitnessDimension, float]:
        return {
            FitnessDimension.COMPILES: 0.25,
            FitnessDimension.TESTS_PASSED: 0.25,
            FitnessDimension.SECURITY: 0.25,
            FitnessDimension.PERFORMANCE: 0.10,
            FitnessDimension.READABILITY: 0.10,
            FitnessDimension.MINIMALITY: 0.05,
        }

    @staticmethod
    def security_focused() -> Dict[FitnessDimension, float]:
        return {
            FitnessDimension.COMPILES: 0.15,
            FitnessDimension.TESTS_PASSED: 0.15,
            FitnessDimension.SECURITY: 0.45,
            FitnessDimension.PERFORMANCE: 0.05,
            FitnessDimension.READABILITY: 0.10,
            FitnessDimension.MINIMALITY: 0.10,
        }

    @staticmethod
    def performance_focused() -> Dict[FitnessDimension, float]:
        return {
            FitnessDimension.COMPILES: 0.15,
            FitnessDimension.TESTS_PASSED: 0.15,
            FitnessDimension.SECURITY: 0.10,
            FitnessDimension.PERFORMANCE: 0.45,
            FitnessDimension.READABILITY: 0.10,
            FitnessDimension.MINIMALITY: 0.05,
        }

    @staticmethod
    def evaluate_simple(
        patch: str,
        original_code: str,
        compile_fn: Callable[[str], bool],
    ) -> FitnessVector:
        """Avaliação simples: compila? diff pequeno?"""
        scores: Dict[FitnessDimension, float] = {}

        # Compila?
        try:
            scores[FitnessDimension.COMPILES] = 1.0 if compile_fn(patch) else 0.0
        except Exception:
            scores[FitnessDimension.COMPILES] = 0.0

        # Minimalidade: prefere patches menores (mas não vazios)
        if original_code:
            diff_ratio = len(patch) / max(len(original_code), 1)
            scores[FitnessDimension.MINIMALITY] = max(0.0, 1.0 - abs(diff_ratio - 1.0))
        else:
            scores[FitnessDimension.MINIMALITY] = 0.5

        # Legibilidade básica: penaliza linhas muito longas
        max_line = max((len(l) for l in patch.splitlines()), default=0)
        scores[FitnessDimension.READABILITY] = max(0.0, 1.0 - max_line / 200.0)

        # Preencher restante
        for dim in FitnessDimension:
            if dim not in scores:
                scores[dim] = 0.5

        return FitnessVector(scores=scores)


# ============================================================================
# Coevolution
# ============================================================================

@dataclass
class CoevolutionPair:
    """Um par coevolutivo (patch + teste)."""
    patch: Individual
    test: str  # Código do teste
    patch_fitness: float
    test_effectiveness: float  # Quão bem o teste quebra patches rivais


class CoevolutionManager:
    """Gerencia coevolução de patches e testes.

    Os testes evoluem para quebrar patches, patches evoluem para passar testes.
    """

    def __init__(self, initial_tests: Optional[List[str]] = None):
        self.tests: List[str] = initial_tests or []
        self.test_effectiveness: Dict[str, float] = {}  # test_hash → score
        self.generation = 0

    def evaluate_test(
        self,
        test: str,
        patches: List[Individual],
        test_runner: Callable[[str, str], bool],
    ) -> float:
        """Avalia quão efetivo é um teste em quebrar patches."""
        if not patches:
            return 0.0

        breaks = 0
        for patch in patches:
            try:
                if not test_runner(patch.patch_code, test):
                    breaks += 1
            except Exception:
                breaks += 1

        return breaks / len(patches)

    def evolve_tests(
        self,
        patches: List[Individual],
        test_runner: Callable[[str, str], bool],
        n_new_tests: int = 3,
    ) -> List[str]:
        """Evolui novos testes para quebrar os patches atuais."""
        # Mantém testes que quebram pelo menos 30% dos patches
        effective_tests = []
        for test in self.tests:
            eff = self.evaluate_test(test, patches, test_runner)
            if eff > 0.3:
                effective_tests.append(test)

        # Gera novos testes por mutação dos efetivos
        new_tests = []
        for _ in range(n_new_tests):
            if effective_tests:
                base = random.choice(effective_tests)
                mutated = MutationOperator.variable_rename(base)
                mutated = MutationOperator.constant_perturb(mutated)
                new_tests.append(mutated)

        self.tests = effective_tests + new_tests
        self.generation += 1
        return self.tests


# ============================================================================
# GeneticPatchEngine — Motor Principal
# ============================================================================

class GeneticPatchEngine:
    """Motor de evolução genética de patches.

    Evolui uma população de patches através de gerações usando:
    - Crossover (single-point, two-point, uniform, semantic)
    - Mutação (line swap, delete, duplicate, variable rename, operator flip, constant perturb)
    - Seleção (tournament, roulette, elitism, Pareto)

    Attributes:
        population_size: Tamanho da população.
        generations: Número máximo de gerações.
        elite_size: Número de indivíduos elite preservados.
        mutation_rate: Probabilidade de mutação por indivíduo.
        crossover_rate: Probabilidade de crossover.
        tournament_size: Tamanho do torneio de seleção.
        early_stop_generations: Parar se não melhorar após N gerações.
        fitness_weights: Pesos para fitness multi-objetivo.
    """

    def __init__(
        self,
        population_size: int = 20,
        generations: int = 10,
        elite_size: int = 2,
        mutation_rate: float = 0.3,
        crossover_rate: float = 0.7,
        tournament_size: int = 3,
        early_stop_generations: int = 5,
        fitness_weights: Optional[Dict[FitnessDimension, float]] = None,
        enable_coevolution: bool = False,
        use_pareto: bool = True,
    ):
        if population_size < 4:
            raise ValueError("population_size deve ser >= 4")
        if elite_size >= population_size:
            raise ValueError("elite_size deve ser < population_size")

        self.population_size = population_size
        self.generations = generations
        self.elite_size = elite_size
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.tournament_size = tournament_size
        self.early_stop_generations = early_stop_generations
        self.fitness_weights = fitness_weights or FitnessFunctions.default_weights()
        self.enable_coevolution = enable_coevolution
        self.use_pareto = use_pareto

        # Estado interno
        self._population: List[Individual] = []
        self._generation = 0
        self._best_ever: Optional[Individual] = None
        self._best_fitness_ever: float = 0.0
        self._stats: List[GenerationStats] = []
        self._fitness_history: List[float] = []
        self._generations_without_improvement = 0

        # Coevolução
        self._coevolution = CoevolutionManager() if enable_coevolution else None

        # Callbacks
        self.on_generation_complete: Optional[Callable] = None

    # ------------------------------------------------------------------
    # API Principal
    # ------------------------------------------------------------------

    def evolve(
        self,
        original_code: str,
        fitness_function: Callable[[str], FitnessVector],
        initial_patches: Optional[List[str]] = None,
        test_runner: Optional[Callable[[str, str], bool]] = None,
    ) -> EvolutionResult:
        """Executa evolução genética completa.

        Args:
            original_code: Código C original.
            fitness_function: Função que avalia um patch → FitnessVector.
            initial_patches: Patches iniciais para semear a população.
            test_runner: Função (patch_code, test_code) → bool para coevolução.

        Returns:
            EvolutionResult com melhor indivíduo e estatísticas.
        """
        start_time = time.time()
        self._reset_state()

        # Inicializar população
        self._initialize_population(original_code, initial_patches or [])

        # Avaliar fitness inicial
        self._evaluate_population(fitness_function)

        # Loop de gerações
        for gen in range(self.generations):
            self._generation = gen
            gen_start = time.time()

            # Selecionar elite
            elite = SelectionStrategy.elitism(self._population, self.elite_size)

            # Criar nova população
            new_population = list(elite)  # Preservar elite

            while len(new_population) < self.population_size:
                parent1 = SelectionStrategy.tournament(
                    self._population, self.tournament_size,
                    key=lambda ind: ind.fitness.weighted_sum(self.fitness_weights)
                )
                parent2 = SelectionStrategy.tournament(
                    self._population, self.tournament_size,
                    key=lambda ind: ind.fitness.weighted_sum(self.fitness_weights)
                )

                # Crossover
                if random.random() < self.crossover_rate:
                    child_code = self._apply_crossover(parent1.patch_code, parent2.patch_code)
                else:
                    child_code = parent1.patch_code

                # Mutação
                if random.random() < self.mutation_rate:
                    child_code = self._apply_mutation(child_code)

                child = Individual(
                    id=f"gen{gen}_ind{len(new_population)}",
                    patch_code=child_code,
                    generation_born=gen,
                    parents=[parent1.id, parent2.id],
                )
                new_population.append(child)

            # Avaliar nova população
            self._population = new_population[:self.population_size]
            self._evaluate_population(fitness_function)

            # Registrar estatísticas
            gen_stats = self._compute_generation_stats(
                gen, (time.time() - gen_start) * 1000
            )
            self._stats.append(gen_stats)
            self._fitness_history.append(gen_stats.best_fitness)

            # Early stopping
            if gen_stats.new_best_found:
                self._generations_without_improvement = 0
            else:
                self._generations_without_improvement += 1

            if self._generations_without_improvement >= self.early_stop_generations:
                montar_log(
                    f"GeneticPatchEngine: early stop na geração {gen} "
                    f"(sem melhoria por {self.early_stop_generations} gerações)",
                    "INFO"
                )
                break

            # Coevolução
            if self._coevolution and test_runner:
                self._coevolution.evolve_tests(
                    self._population, test_runner, n_new_tests=2
                )

            # Callback
            if self.on_generation_complete:
                self.on_generation_complete(gen_stats)

            montar_log(
                f"Geração {gen}: best={gen_stats.best_fitness:.3f} "
                f"avg={gen_stats.avg_fitness:.3f} "
                f"Pareto={gen_stats.pareto_front_size} "
                f"diversity={gen_stats.diversity:.3f}",
                "DEBUG"
            )

        total_time = (time.time() - start_time) * 1000

        # Encontrar Pareto front final
        pareto_front = self._get_pareto_front()

        result = EvolutionResult(
            best_individual=self._best_ever,  # type: ignore[arg-type]
            best_generation=self._best_ever.generation_born if self._best_ever else 0,
            best_fitness=self._best_fitness_ever,
            pareto_front=pareto_front,
            generation_stats=self._stats,
            total_generations=self._generation + 1,
            total_time_ms=total_time,
            convergence_generation=self._find_convergence(),
            fitness_history=self._fitness_history,
        )

        montar_log(
            f"GeneticPatchEngine: evolução concluída — {result.summary()}",
            "INFO"
        )

        return result

    def quick_evolve(
        self,
        original_code: str,
        fitness_function: Callable[[str], FitnessVector],
        initial_patches: Optional[List[str]] = None,
    ) -> Individual:
        """Evolução rápida (5 gerações, pop=10). Ideal para CI/CD."""
        # Salva estado atual
        saved_pop = self.population_size
        saved_gen = self.generations
        saved_early = self.early_stop_generations

        self.population_size = 10
        self.generations = 5
        self.early_stop_generations = 2

        try:
            result = self.evolve(original_code, fitness_function, initial_patches)
            return result.best_individual
        finally:
            self.population_size = saved_pop
            self.generations = saved_gen
            self.early_stop_generations = saved_early

    # ------------------------------------------------------------------
    # Inicialização
    # ------------------------------------------------------------------

    def _reset_state(self):
        """Reseta estado interno para nova evolução."""
        self._population = []
        self._generation = 0
        self._best_ever = None
        self._best_fitness_ever = 0.0
        self._stats = []
        self._fitness_history = []
        self._generations_without_improvement = 0

    def _initialize_population(
        self,
        original_code: str,
        initial_patches: List[str],
    ):
        """Inicializa a população."""
        population = []

        # Adicionar código original como indivíduo
        population.append(Individual(
            id=f"gen0_original",
            patch_code=original_code,
            generation_born=0,
        ))

        # Adicionar patches iniciais
        for i, patch in enumerate(initial_patches):
            population.append(Individual(
                id=f"gen0_seed_{i}",
                patch_code=patch,
                generation_born=0,
            ))

        # Gerar indivíduos aleatórios via mutação
        base = original_code if original_code else (
            initial_patches[0] if initial_patches else "int main() { return 0; }"
        )
        while len(population) < self.population_size:
            mutated = self._apply_multiple_mutations(base, 3)
            population.append(Individual(
                id=f"gen0_rand_{len(population)}",
                patch_code=mutated,
                generation_born=0,
            ))

        self._population = population[:self.population_size]

    # ------------------------------------------------------------------
    # Avaliação
    # ------------------------------------------------------------------

    def _evaluate_population(
        self,
        fitness_function: Callable[[str], FitnessVector],
    ):
        """Avalia fitness de toda a população."""
        for individual in self._population:
            if not individual.fitness.scores.get(FitnessDimension.COMPILES):
                try:
                    individual.fitness = fitness_function(individual.patch_code)
                except Exception as e:
                    logger.debug(f"Fitness evaluation failed for {individual.id}: {e}")
                    individual.fitness = FitnessVector()

            # Atualizar best ever
            score = individual.fitness.weighted_sum(self.fitness_weights)
            if score > self._best_fitness_ever:
                self._best_fitness_ever = score
                self._best_ever = individual

    # ------------------------------------------------------------------
    # Operadores Genéticos
    # ------------------------------------------------------------------

    def _apply_crossover(self, parent1: str, parent2: str) -> str:
        """Aplica crossover aleatório."""
        operators = [
            CrossoverOperator.single_point,
            CrossoverOperator.two_point,
            CrossoverOperator.uniform,
            CrossoverOperator.semantic,
        ]
        op = random.choice(operators)
        return op(parent1, parent2)

    def _apply_mutation(self, code: str) -> str:
        """Aplica mutação aleatória."""
        operators = [
            MutationOperator.line_swap,
            MutationOperator.line_delete,
            MutationOperator.line_duplicate,
            MutationOperator.variable_rename,
            MutationOperator.operator_flip,
            MutationOperator.constant_perturb,
        ]
        op = random.choice(operators)
        try:
            return op(code)
        except Exception:
            return code

    def _apply_multiple_mutations(self, code: str, n: int) -> str:
        """Aplica n mutações aleatórias em sequência."""
        for _ in range(n):
            code = self._apply_mutation(code)
        return code

    # ------------------------------------------------------------------
    # Estatísticas e Análise
    # ------------------------------------------------------------------

    def _compute_generation_stats(
        self, generation: int, elapsed_ms: float
    ) -> GenerationStats:
        """Computa estatísticas da geração atual."""
        fitnesses = [
            ind.fitness.weighted_sum(self.fitness_weights)
            for ind in self._population
        ]

        fitnesses_sorted = sorted(fitnesses, reverse=True)
        best = fitnesses_sorted[0] if fitnesses_sorted else 0.0
        avg = sum(fitnesses) / len(fitnesses) if fitnesses else 0.0
        median = fitnesses_sorted[len(fitnesses_sorted) // 2] if fitnesses_sorted else 0.0

        new_best = best > self._best_fitness_ever

        # Diversidade: dissimilaridade média entre indivíduos
        diversity = self._compute_diversity()

        # Pareto front
        pareto_front = self._get_pareto_front()

        return GenerationStats(
            generation=generation,
            population_size=len(self._population),
            best_fitness=best,
            avg_fitness=avg,
            median_fitness=median,
            pareto_front_size=len(pareto_front),
            diversity=diversity,
            new_best_found=new_best,
            elapsed_ms=elapsed_ms,
        )

    def _compute_diversity(self) -> float:
        """Calcula diversidade da população (0-1)."""
        if len(self._population) <= 1:
            return 0.0

        total_dist = 0.0
        count = 0
        for i, ind1 in enumerate(self._population):
            for j, ind2 in enumerate(self._population):
                if i < j:
                    dist = self._levenshtein_ratio(ind1.patch_code, ind2.patch_code)
                    total_dist += dist
                    count += 1

        if count == 0:
            return 0.0
        return min(1.0, total_dist / count)

    @staticmethod
    def _levenshtein_ratio(a: str, b: str) -> float:
        """Similaridade de código normalizada (0=idêntico, 1=totalmente diferente)."""
        if not a and not b:
            return 0.0
        if not a or not b:
            return 1.0

        lines_a = set(a.splitlines())
        lines_b = set(b.splitlines())
        intersection = lines_a & lines_b
        union = lines_a | lines_b
        if not union:
            return 1.0
        jaccard = len(intersection) / len(union)
        return 1.0 - jaccard

    def _get_pareto_front(self) -> List[Individual]:
        """Retorna a fronteira de Pareto atual."""
        if not self._population:
            return []
        fronts = SelectionStrategy._non_dominated_sort(self._population)
        return fronts[0] if fronts else []

    def _find_convergence(self) -> Optional[int]:
        """Encontra geração de convergência (quando fitness estabilizou)."""
        if len(self._fitness_history) < 3:
            return None

        for i in range(2, len(self._fitness_history)):
            if (self._fitness_history[i] - self._fitness_history[i - 2]) < 0.01:
                return i
        return None

    def get_population_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas da população atual."""
        if not self._population:
            return {"size": 0}

        fitnesses = [
            ind.fitness.weighted_sum(self.fitness_weights)
            for ind in self._population
        ]

        return {
            "size": len(self._population),
            "best_fitness": max(fitnesses) if fitnesses else 0.0,
            "avg_fitness": sum(fitnesses) / len(fitnesses) if fitnesses else 0.0,
            "generation": self._generation,
            "best_ever_fitness": self._best_fitness_ever,
        }
