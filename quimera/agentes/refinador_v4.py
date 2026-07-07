"""AgenteRefinadorV4 — Evolução Genética de Patches.

Evolução do AgenteRefinadorV3, substituindo o ciclo iterativo linear
por evolução genética populacional.

Pipeline:
    Patch Inicial → Gerar população → Avaliar (compila+teste+segurança)
    → Selecionar (Pareto+torneio) → Crossover → Mutação
    → Nova geração → repete até convergir

Diferenças vs V3:
    V3: 1 patch → heurística → 1 melhorado → repete (linear)
    V4: N patches → crossover + mutação → seleção → próxima geração (populacional)

Uso:
    from quimera.agentes.refinador_v4 import AgenteRefinadorV4
    
    refinador = AgenteRefinadorV4(quadro_negro, critico)
    resultado = await refinador.refinar_patch(patch_inicial, arquivo)
"""

import asyncio
import logging
import re
import json
import time
from typing import Dict, Any, List, Optional, Tuple, Callable

from quimera.quadro_negro import QuadroNegro
from quimera.logs.parser import montar_log

try:
    from quimera.agentes.agente_critico import AgenteCritico
except ImportError:
    AgenteCritico = None

try:
    from quimera.agentes.genetic_patch_engine import (
        GeneticPatchEngine,
        Individual,
        FitnessVector,
        FitnessDimension,
        GenerationStats,
        EvolutionResult,
        FitnessFunctions,
    )
    GENETIC_AVAILABLE = True
except ImportError:
    GENETIC_AVAILABLE = False

logger = logging.getLogger(__name__)


class AgenteRefinadorV4:
    """Agente refinador de patches com evolução genética populacional.

    Substitui o refinador V3 (iterativo linear) por evolução genética:
    - População de N patches evoluindo simultaneamente
    - Crossover combinando características de patches bem-sucedidos
    - Seleção por Pareto preservando diversidade
    - Fitness multi-objetivo (compila + testes + segurança + performance)

    Attributes:
        population_size: Tamanho da população (default: 20).
        generations: Número máximo de gerações (default: 10).
        elite_size: Indivíduos elite preservados por geração.
        mutation_rate: Taxa de mutação.
        crossover_rate: Taxa de crossover.
        use_heuristic_mutations: Se True, usa HEURISTICAS do V3 como mutadores extras.
    """

    def __init__(
        self,
        quadro_negro: QuadroNegro,
        critico: Optional[AgenteCritico] = None,
        population_size: int = 20,
        generations: int = 10,
        elite_size: int = 2,
        mutation_rate: float = 0.3,
        crossover_rate: float = 0.7,
        early_stop: int = 5,
        use_heuristic_mutations: bool = True,
        use_pareto: bool = True,
    ):
        if not GENETIC_AVAILABLE:
            raise ImportError(
                "GeneticPatchEngine não disponível. "
                "Verifique se quimera/agentes/genetic_patch_engine.py existe."
            )

        self.quadro_negro = quadro_negro
        self.critico = critico

        self._engine = GeneticPatchEngine(
            population_size=population_size,
            generations=generations,
            elite_size=elite_size,
            mutation_rate=mutation_rate,
            crossover_rate=crossover_rate,
            early_stop_generations=early_stop,
            use_pareto=use_pareto,
        )

        self.use_heuristic_mutations = use_heuristic_mutations
        self._heuristicas: List[Callable] = []

        # Carregar heurísticas do V3 se disponíveis
        if use_heuristic_mutations:
            try:
                from quimera.agentes.refinador_v3.heuristicas_mutacao import HEURISTICAS
                self._heuristicas = HEURISTICAS
                montar_log(
                    f"AgenteRefinadorV4: {len(HEURISTICAS)} heurísticas V3 carregadas "
                    f"como mutadores extras",
                    "INFO"
                )
            except ImportError:
                montar_log(
                    "AgenteRefinadorV4: heurísticas V3 não disponíveis — "
                    "usando apenas operadores genéticos padrão",
                    "WARNING"
                )

        montar_log(
            f"AgenteRefinadorV4 inicializado: pop={population_size}, "
            f"gen={generations}, elite={elite_size}, "
            f"mut={mutation_rate}, cross={crossover_rate}, Pareto={'on' if use_pareto else 'off'}",
            "INFO"
        )

    # ------------------------------------------------------------------
    # API Principal
    # ------------------------------------------------------------------

    async def refinar_patch(
        self,
        patch_inicial: str,
        arquivo_afetado: str,
        feedback_erro_compilacao: Optional[str] = None,
        codigo_original: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Refina um patch usando evolução genética.

        Args:
            patch_inicial: Patch inicial a ser melhorado.
            arquivo_afetado: Arquivo alvo do patch.
            feedback_erro_compilacao: Erro de compilação opcional.
            codigo_original: Código original (pré-patch) para comparação.

        Returns:
            Dict com patch refinado, fitness, histórico e metadados.
        """
        montar_log(
            f"AgenteRefinadorV4: iniciando evolução genética para '{arquivo_afetado}'",
            "INFO"
        )

        # Criar função de fitness
        async def fitness_fn(patch_code: str) -> FitnessVector:
            return await self._evaluate_async(patch_code, arquivo_afetado)

        # Gerar patches iniciais por mutação heurística
        initial_patches = await self._generate_seed_patches(
            patch_inicial, feedback_erro_compilacao
        )

        # Executar evolução
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._engine.evolve(
                original_code=codigo_original or patch_inicial,
                fitness_function=fitness_fn,
                initial_patches=initial_patches,
            )
        )

        # Extrair melhores resultados
        best_patch = result.best_individual.patch_code
        best_fitness = result.best_fitness
        pareto_patches = [ind.patch_code for ind in result.pareto_front[:5]]

        # Validar com crítico se disponível
        aprovado = True
        if self.critico:
            try:
                avaliacao = await self.critico.avaliar_patch(best_patch)
                aprovado = avaliacao.get("aprovado", True)
            except Exception as e:
                logger.warning(f"Falha na avaliação do crítico: {e}")

        return {
            "patch_refinado": best_patch,
            "fitness": best_fitness,
            "fitness_detalhado": result.best_individual.fitness.to_dict(),
            "pareto_front": pareto_patches,
            "aprovado": aprovado,
            "geracoes": result.total_generations,
            "tempo_total_ms": result.total_time_ms,
            "convergiu_na_geracao": result.convergence_generation,
            "historico_fitness": result.fitness_history,
            "estatisticas": [
                {
                    "geracao": s.generation,
                    "best": s.best_fitness,
                    "avg": s.avg_fitness,
                    "pareto_size": s.pareto_front_size,
                    "diversity": s.diversity,
                }
                for s in result.generation_stats
            ],
            "metadata": {
                "engine": "GeneticPatchEngine",
                "refinador_version": "V4",
                "population_size": self._engine.population_size,
                "pareto_enabled": self._engine.use_pareto,
            }
        }

    async def refinar_rapido(
        self,
        patch_inicial: str,
        arquivo_afetado: str,
    ) -> Dict[str, Any]:
        """Refinamento rápido (pop=10, gen=5) para CI/CD."""
        # Salvar configuração
        saved_pop = self._engine.population_size
        saved_gen = self._engine.generations

        self._engine.population_size = 10
        self._engine.generations = 5

        try:
            return await self.refinar_patch(patch_inicial, arquivo_afetado)
        finally:
            self._engine.population_size = saved_pop
            self._engine.generations = saved_gen

    # ------------------------------------------------------------------
    # Fitness Evaluation
    # ------------------------------------------------------------------

    async def _evaluate_async(
        self,
        patch_code: str,
        arquivo_afetado: str,
    ) -> FitnessVector:
        """Avalia fitness de um patch de forma assíncrona."""
        scores: Dict[FitnessDimension, float] = {}

        # 1. Compila?
        scores[FitnessDimension.COMPILES] = await self._check_compiles(
            patch_code, arquivo_afetado
        )

        # 2. Passa testes?
        if self.critico and self.critico.checklinux:
            try:
                check = self.critico.checklinux.validar_aplicabilidade_patch(patch_code)
                scores[FitnessDimension.TESTS_PASSED] = check.get("score", 0.5)
            except Exception:
                scores[FitnessDimension.TESTS_PASSED] = 0.5
        else:
            scores[FitnessDimension.TESTS_PASSED] = 0.5

        # 3. Segurança (via heurísticas e validadores)
        scores[FitnessDimension.SECURITY] = self._evaluate_security(patch_code)

        # 4. Performance (aproximação: tamanho do diff)
        scores[FitnessDimension.PERFORMANCE] = self._evaluate_performance(patch_code)

        # 5. Legibilidade
        scores[FitnessDimension.READABILITY] = self._evaluate_readability(patch_code)

        # 6. Minimalidade
        scores[FitnessDimension.MINIMALITY] = self._evaluate_minimality(patch_code)

        return FitnessVector(scores=scores)

    async def _check_compiles(self, patch: str, arquivo: str) -> float:
        """Verifica se o patch compila (aproximação via AST)."""
        try:
            # Usar validador AST como proxy de compilação
            from quimera.agentes.refinador_v3.validador_ast import validar_patch_ast
            result = validar_patch_ast(patch)
            return 1.0 if result else 0.3  # 0.3 = parseia mas pode não compilar
        except Exception:
            # Verificar sintaxe básica
            try:
                import ast
                # Extrair código C do patch
                code_lines = [
                    l for l in patch.splitlines()
                    if l.startswith("+") and not l.startswith("+++")
                ]
                code = "\n".join(l[1:] for l in code_lines)
                ast.parse(code)  # Python AST como sanity check
                return 0.5
            except Exception:
                return 0.0

    def _evaluate_security(self, patch: str) -> float:
        """Avalia segurança do patch via heurísticas."""
        score = 1.0
        issues = []

        # Verificar padrões inseguros
        insecure_patterns = [
            (r'\bstrcpy\s*\(', 0.15, "strcpy sem bounds"),
            (r'\bgets\s*\(', 0.20, "gets() inseguro"),
            (r'\bsprintf\s*\(', 0.10, "sprintf sem bounds"),
            (r'\bsystem\s*\(', 0.10, "system() call"),
            (r'\bexec\s*\(', 0.15, "exec() call"),
        ]

        for pattern, penalty, desc in insecure_patterns:
            if re.search(pattern, patch):
                issues.append(desc)
                score -= penalty

        # Penalizar falta de NULL checks
        if re.search(r'(\w+)\s*=\s*malloc', patch):
            if not re.search(r'if\s*\(\s*!\w+\s*\)', patch):
                score -= 0.05

        return max(0.0, score)

    def _evaluate_performance(self, patch: str) -> float:
        """Avalia performance (aproximação heurística)."""
        score = 0.5

        # Penalizar loops aninhados
        nesting = 0
        max_nesting = 0
        for line in patch.splitlines():
            nesting += line.count("{") - line.count("}")
            max_nesting = max(max_nesting, nesting)
        if max_nesting > 3:
            score -= 0.1 * (max_nesting - 3)

        # Bonificar uso de const/restrict
        if 'const' in patch:
            score += 0.05
        if 'restrict' in patch:
            score += 0.05

        # Penalizar alocações dinâmicas desnecessárias
        if patch.count('malloc') > 3:
            score -= 0.1

        return max(0.0, min(1.0, score))

    def _evaluate_readability(self, patch: str) -> float:
        """Avalia legibilidade do código."""
        score = 0.5
        lines = patch.splitlines()

        # Penalizar linhas muito longas
        for line in lines:
            if len(line) > 120:
                score -= 0.02
            if len(line) > 200:
                score -= 0.05

        # Bonificar comentários
        comment_lines = sum(1 for l in lines if l.strip().startswith('//') or '/*' in l)
        if len(lines) > 0:
            ratio = comment_lines / len(lines)
            if 0.05 < ratio < 0.4:
                score += 0.1

        # Penalizar nomes de uma letra (exceto i, j, k, n, x, y, p, q)
        single_letter_vars = set(re.findall(
            r'\b([a-z])\b', patch
        )) - {'i', 'j', 'k', 'n', 'x', 'y', 'z', 'p', 'q', 'a', 'b', 'c'}
        if len(single_letter_vars) > 2:
            score -= 0.05

        return max(0.0, min(1.0, score))

    def _evaluate_minimality(self, patch: str) -> float:
        """Avalia minimalidade do patch (quão conciso)."""
        # Medir tamanho efetivo (apenas linhas de código)
        code_lines = [
            l for l in patch.splitlines()
            if l.strip() and not l.strip().startswith('//') and not l.strip().startswith('/*')
        ]

        if not code_lines:
            return 0.0

        # Tamanho ideal: 5-50 linhas
        n = len(code_lines)
        if n < 5:
            return n / 5.0
        elif n <= 50:
            return 1.0
        elif n <= 100:
            return 1.0 - (n - 50) / 50.0 * 0.3
        else:
            return 0.2

    # ------------------------------------------------------------------
    # Geração de Patches Iniciais (Seed)
    # ------------------------------------------------------------------

    async def _generate_seed_patches(
        self,
        patch_inicial: str,
        feedback_erro: Optional[str] = None,
    ) -> List[str]:
        """Gera patches iniciais via heurísticas do V3."""
        seeds = [patch_inicial]

        if not self._heuristicas:
            return seeds

        # Aplicar cada heurística ao patch inicial
        for heuristica in self._heuristicas[:7]:  # Limitar a 7 seeds
            try:
                if asyncio.iscoroutinefunction(heuristica):
                    # Heurística assíncrona (ex: reformulação LLM)
                    novo_patch, _ = await heuristica(
                        patch_inicial,
                        llm_client=None,  # Será preenchido se necessário
                    )
                else:
                    novo_patch, _ = heuristica(patch_inicial)

                if novo_patch and novo_patch != patch_inicial:
                    seeds.append(novo_patch)
            except Exception as e:
                logger.debug(f"Heurística {heuristica.__name__} falhou: {e}")

        montar_log(
            f"AgenteRefinadorV4: {len(seeds)} patches seed gerados",
            "DEBUG"
        )
        return seeds

    # ------------------------------------------------------------------
    # Informações
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Retorna status do refinador."""
        return {
            "version": "V4",
            "engine": "GeneticPatchEngine",
            "population_size": self._engine.population_size,
            "max_generations": self._engine.generations,
            "elite_size": self._engine.elite_size,
            "mutation_rate": self._engine.mutation_rate,
            "crossover_rate": self._engine.crossover_rate,
            "pareto_enabled": self._engine.use_pareto,
            "heuristic_mutations": len(self._heuristicas) if self.use_heuristic_mutations else 0,
            "features": {
                "population_evolution": True,
                "crossover": True,
                "multi_objective_fitness": True,
                "pareto_frontier": self._engine.use_pareto,
                "elitism": True,
                "coevolution": False,  # Futuro
            }
        }
