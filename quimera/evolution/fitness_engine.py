"""
Fitness Engine — Fonte única de verdade para avaliação global do Quimera.

Princípios:
  - ÚNICO dono da função de fitness global
  - Todos consultam aqui (pipeline, evolution, planner, benchmarks)
  - Pesos ajustáveis por TaskContext (segurança ≠ performance)
  - NUNCA modificado diretamente por planner ou learner

Autor: Quimera MarkX — OMinivers
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("quimera.evolution.fitness")


class TaskContext(str, Enum):
    """Contexto da tarefa — altera os pesos do fitness global."""
    SECURITY_CRITICAL = "security_critical"
    PERFORMANCE_BENCHMARK = "performance_benchmark"
    GENERAL_REPAIR = "general_repair"
    EXPLORATION = "exploration"


@dataclass
class FitnessWeights:
    """Pesos da função de fitness global — varia por contexto."""
    repair_rate: float = 0.30           # % de vulnerabilidades corrigidas
    precision: float = 0.25             # Precisão (evitar falsos positivos)
    efficiency: float = 0.20            # Tempo de execução (invertido)
    coverage: float = 0.15              # Cobertura de análise estática
    stability: float = 0.10             # Estabilidade / sem crashes


# Pesos por contexto — segurança prioriza precisão, performance prioriza velocidade
CONTEXT_WEIGHTS: Dict[TaskContext, FitnessWeights] = {
    TaskContext.SECURITY_CRITICAL: FitnessWeights(
        repair_rate=0.25, precision=0.40, efficiency=0.10, coverage=0.15, stability=0.10,
    ),
    TaskContext.PERFORMANCE_BENCHMARK: FitnessWeights(
        repair_rate=0.20, precision=0.15, efficiency=0.45, coverage=0.10, stability=0.10,
    ),
    TaskContext.GENERAL_REPAIR: FitnessWeights(
        repair_rate=0.30, precision=0.25, efficiency=0.20, coverage=0.15, stability=0.10,
    ),
    TaskContext.EXPLORATION: FitnessWeights(
        repair_rate=0.20, precision=0.15, efficiency=0.15, coverage=0.35, stability=0.15,
    ),
}


@dataclass
class FitnessScore:
    """Resultado da avaliação de fitness global."""
    global_score: float                  # 0.0 – 1.0
    components: Dict[str, float] = field(default_factory=dict)  # scores individuais
    context: TaskContext = TaskContext.GENERAL_REPAIR
    weights_used: FitnessWeights = field(default_factory=FitnessWeights)
    
    def summary(self) -> str:
        return (f"Fitness: {self.global_score:.3f} [{self.context.value}] "
                f"(repair={self.components.get('repair_rate',0):.2f}, "
                f"prec={self.components.get('precision',0):.2f}, "
                f"eff={self.components.get('efficiency',0):.2f})")


class FitnessEngine:
    """Motor de fitness global — fonte única de verdade.
    
    Todos os componentes do Quimera consultam ESTA classe para obter
    o fitness de qualquer execução. Nenhum outro módulo calcula fitness.
    
    Uso:
        engine = FitnessEngine()
        score = engine.evaluate(metrics, context=TaskContext.SECURITY_CRITICAL)
    """
    
    def __init__(self):
        self.weights = CONTEXT_WEIGHTS
        self.history: List[FitnessScore] = []
        self.baseline: Optional[float] = None
    
    def evaluate(self, metrics: Dict[str, float],
                 context: TaskContext = TaskContext.GENERAL_REPAIR) -> FitnessScore:
        """Avalia fitness global a partir de métricas brutas.
        
        Métricas esperadas:
            repair_rate: float (0-1) — % vulnerabilidades corrigidas
            precision: float (0-1) — (verd_positivos) / (verd_positivos + falsos_positivos)
            efficiency: float (0-1) — normalizado: base_time / actual_time
            coverage: float (0-1) — cobertura de análise estática
            stability: float (0-1) — 1.0 se 0 crashes, decai com crashes
        """
        weights = self.weights.get(context, self.weights[TaskContext.GENERAL_REPAIR])
        
        components = {
            "repair_rate": metrics.get("repair_rate", 0.0),
            "precision": metrics.get("precision", 0.0),
            "efficiency": metrics.get("efficiency", 0.0),
            "coverage": metrics.get("coverage", 0.0),
            "stability": metrics.get("stability", 0.0),
        }
        
        global_score = (
            weights.repair_rate * components["repair_rate"] +
            weights.precision * components["precision"] +
            weights.efficiency * components["efficiency"] +
            weights.coverage * components["coverage"] +
            weights.stability * components["stability"]
        )
        
        # Clamp
        global_score = max(0.0, min(1.0, global_score))
        
        score = FitnessScore(
            global_score=global_score,
            components=components,
            context=context,
            weights_used=weights,
        )
        
        self.history.append(score)
        
        # Estabelecer baseline na primeira avaliação
        if self.baseline is None:
            self.baseline = global_score
        
        return score
    
    def evaluate_from_pipeline(self, pipeline_result: Dict[str, Any],
                               context: TaskContext = TaskContext.GENERAL_REPAIR) -> FitnessScore:
        """Avalia fitness a partir do resultado bruto do pipeline H1→H6.
        
        Converte métricas do pipeline para o formato do FitnessEngine.
        """
        total_vulns = float(pipeline_result.get("vulnerabilities_found", 0) or 1)
        fixed = float(pipeline_result.get("vulnerabilities_fixed", 0))
        false_pos = float(pipeline_result.get("false_positives", 0))
        time_ms = float(pipeline_result.get("execution_time_ms", 1) or 1)
        crashes = int(pipeline_result.get("crashes", 0))
        coverage = float(pipeline_result.get("static_coverage", 0))
        
        # Normalizar
        repair_rate = fixed / max(total_vulns, 1)
        precision = fixed / max(fixed + false_pos, 1)
        efficiency = min(1.0, 5000.0 / max(time_ms, 1))  # 5s baseline
        stability = max(0.0, 1.0 - crashes * 0.2)
        
        return self.evaluate({
            "repair_rate": repair_rate,
            "precision": precision,
            "efficiency": efficiency,
            "coverage": coverage,
            "stability": stability,
        }, context=context)
    
    def compare(self, score_a: FitnessScore, score_b: FitnessScore) -> Dict:
        """Compara dois scores de fitness."""
        delta = score_b.global_score - score_a.global_score
        pct_change = (delta / max(score_a.global_score, 0.001)) * 100
        
        return {
            "score_a": round(score_a.global_score, 3),
            "score_b": round(score_b.global_score, 3),
            "delta": round(delta, 3),
            "pct_change": round(pct_change, 1),
            "winner": "B" if delta > 0 else "A" if delta < 0 else "tie",
            "significant": abs(pct_change) >= 3.0,
        }
    
    def get_baseline(self) -> Optional[float]:
        return self.baseline
    
    def degradation_from_baseline(self, current: float) -> float:
        """% de degradação em relação ao baseline."""
        if self.baseline is None or self.baseline == 0:
            return 0.0
        return ((self.baseline - current) / self.baseline) * 100
    
    def get_history(self, context: Optional[TaskContext] = None,
                    limit: int = 50) -> List[FitnessScore]:
        if context:
            return [s for s in self.history if s.context == context][-limit:]
        return self.history[-limit:]
    
    def avg_recent(self, n: int = 10) -> float:
        """Média dos últimos N scores."""
        recent = self.history[-n:]
        if not recent:
            return 0.0
        return sum(s.global_score for s in recent) / len(recent)


# Global — instância única
fitness_engine = FitnessEngine()
