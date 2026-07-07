"""
Validation Gate v2 — Constraints Contextuais + Diversity Dinâmico + Backstop Multicritério.

Princípios:
  1. Constraints dependem do tipo de tarefa (segurança ≠ performance)
  2. Diversity baseado em entropia, não threshold fixo
  3. Backstop multicritério: fitness + crashes + testes + cobertura
  4. Versionamento de políticas: nunca sobrescrever
  5. Métricas de longo prazo: janela deslizante 30 dias

Autor: Quimera MarkX — OMinivers
"""
import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from math import log2
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("quimera.evolution.validation")


class OptimizationDomain(str, Enum):
    PERFORMANCE = "performance"
    PATCH_EFFICIENCY = "patch_efficiency"
    AGENT_SELECTION = "agent_selection"
    FIXED = "fixed"


class TaskContext(str, Enum):
    """Contexto da tarefa — muda os pesos das constraints."""
    SECURITY_CRITICAL = "security_critical"     # Prioriza detecção > performance
    PERFORMANCE_BENCHMARK = "performance_benchmark"  # Prioriza tempo > diversidade
    GENERAL_REPAIR = "general_repair"           # Balanceado
    EXPLORATION = "exploration"                 # Prioriza diversidade > performance


@dataclass
class CompositeConstraint:
    """Constraint composta: par inseparável de métricas."""
    domain: OptimizationDomain
    optimize: str
    must_not_degrade: List[str]
    max_degradation_pct: float
    weight: float = 1.0


# Constraints base — pesos são ajustados por TaskContext
BASE_CONSTRAINTS: List[CompositeConstraint] = [
    CompositeConstraint(OptimizationDomain.PERFORMANCE, "tempo_execucao_ms",
                        ["fitness_global", "taxa_deteccao"], 2.0, 1.0),
    CompositeConstraint(OptimizationDomain.PATCH_EFFICIENCY, "patches_gerados",
                        ["cobertura_vulnerabilidades", "falsos_negativos"], 0.0, 1.2),
    CompositeConstraint(OptimizationDomain.AGENT_SELECTION, "agent_success_rate",
                        ["agent_diversity", "exploration_rate"], 5.0, 0.8),
    CompositeConstraint(OptimizationDomain.FIXED, "estabilidade",
                        ["fitness_global"], 5.0, 2.0),
]

# Pesos por contexto — ajusta a importância relativa de cada domínio
CONTEXT_WEIGHTS: Dict[TaskContext, Dict[OptimizationDomain, float]] = {
    TaskContext.SECURITY_CRITICAL: {
        OptimizationDomain.PERFORMANCE: 0.3,
        OptimizationDomain.PATCH_EFFICIENCY: 2.0,     # Máxima prioridade
        OptimizationDomain.AGENT_SELECTION: 0.5,
        OptimizationDomain.FIXED: 2.0,
    },
    TaskContext.PERFORMANCE_BENCHMARK: {
        OptimizationDomain.PERFORMANCE: 2.0,
        OptimizationDomain.PATCH_EFFICIENCY: 0.5,
        OptimizationDomain.AGENT_SELECTION: 0.3,
        OptimizationDomain.FIXED: 1.0,
    },
    TaskContext.GENERAL_REPAIR: {
        OptimizationDomain.PERFORMANCE: 1.0,
        OptimizationDomain.PATCH_EFFICIENCY: 1.0,
        OptimizationDomain.AGENT_SELECTION: 1.0,
        OptimizationDomain.FIXED: 1.0,
    },
    TaskContext.EXPLORATION: {
        OptimizationDomain.PERFORMANCE: 0.3,
        OptimizationDomain.PATCH_EFFICIENCY: 0.5,
        OptimizationDomain.AGENT_SELECTION: 2.0,      # Diversidade máxima
        OptimizationDomain.FIXED: 0.5,
    },
}


@dataclass
class ValidationResult:
    passed: bool
    score: float
    fitness_global: float
    constraint_results: List[Dict] = field(default_factory=list)
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    requires_backstop: bool = False
    backstop_reasons: List[str] = field(default_factory=list)


# ──── Diversity Guard Dinâmico ────────────────────────────────────

class DiversityGuard:
    """Evita dominância de agente usando entropia, não threshold fixo.
    
    Em vez de um número mágico (60%), calcula a entropia da distribuição
    de seleções. Quanto menor a entropia, menos diverso o sistema.
    Abaixo de 50% da entropia máxima → força diversificação.
    """
    
    HISTORY_SIZE = 200
    
    def __init__(self):
        self.selection_history: deque = deque(maxlen=self.HISTORY_SIZE)
    
    def record_selection(self, agent_name: str):
        self.selection_history.append(agent_name)
    
    def _distribution(self) -> Dict[str, float]:
        if not self.selection_history:
            return {}
        total = len(self.selection_history)
        counts: Dict[str, int] = {}
        for a in self.selection_history:
            counts[a] = counts.get(a, 0) + 1
        return {a: c / total for a, c in counts.items()}
    
    def _entropy(self, dist: Dict[str, float]) -> float:
        """Entropia de Shannon da distribuição."""
        if not dist:
            return 0.0
        return -sum(p * log2(p) for p in dist.values() if p > 0)
    
    def _max_entropy(self, dist: Dict[str, float]) -> float:
        """Entropia máxima possível (distribuição uniforme)."""
        n = len(dist)
        return log2(n) if n > 0 else 0.0
    
    def diversity_score(self) -> float:
        """Score de diversidade 0-1 baseado em entropia relativa."""
        dist = self._distribution()
        if not dist or len(dist) <= 1:
            return 0.0
        H = self._entropy(dist)
        H_max = self._max_entropy(dist)
        return H / H_max if H_max > 0 else 0.0
    
    def needs_diversification(self, agent_name: str) -> bool:
        """True se o agente está dominante demais (entropia < 50%)."""
        if len(self.selection_history) < 10:
            return False
        dist = self._distribution()
        if not dist or len(dist) < 2:
            return False
        return self.diversity_score() < 0.5
    
    def get_diversified_agent(self, candidates: List[str]) -> Optional[str]:
        """Seleciona agente que maximiza diversidade."""
        if not candidates:
            return None
        dist = self._distribution()
        # Prioriza o menos usado
        least_used = min(candidates, key=lambda a: dist.get(a, 0.0))
        return least_used
    
    def get_report(self) -> Dict:
        dist = self._distribution()
        dominant = max(dist, key=dist.get) if dist else None
        return {
            "diversity_score": round(self.diversity_score(), 3),
            "entropy": round(self._entropy(dist), 3),
            "max_entropy": round(self._max_entropy(dist), 3),
            "unique_agents": len(dist),
            "distribution": {a: round(p * 100, 1) for a, p in dist.items()},
            "dominant_agent": dominant,
            "needs_diversification": self.needs_diversification(dominant or ""),
        }


# ──── Métricas de Longo Prazo (janela deslizante 30 dias) ──────────

@dataclass
class MetricSnapshot:
    timestamp: float
    fitness: float
    tempo_ms: float
    patches: int
    cobertura: float
    falsos_negativos: int
    crashes: int
    tests_passed: int
    tests_failed: int


class LongTermMetrics:
    """Janela deslizante de métricas para evitar otimismo pontual.
    
    Uma estratégia pode performar bem hoje e regredir amanhã.
    Este tracker mantém 30 dias de histórico para detectar tendências.
    """
    
    WINDOW_DAYS = 30
    MAX_SNAPSHOTS = 1000
    
    def __init__(self, storage_path: Optional[str] = None):
        self.snapshots: deque = deque(maxlen=self.MAX_SNAPSHOTS)
        self.storage_path = storage_path
    
    def record(self, fitness: float, tempo_ms: float, patches: int,
               cobertura: float, falsos_negativos: int,
               crashes: int = 0, tests_passed: int = 0, tests_failed: int = 0):
        self.snapshots.append(MetricSnapshot(
            timestamp=time.time(),
            fitness=fitness, tempo_ms=tempo_ms, patches=patches,
            cobertura=cobertura, falsos_negativos=falsos_negativos,
            crashes=crashes, tests_passed=tests_passed, tests_failed=tests_failed,
        ))
    
    def trend(self, metric: str, days: int = 7) -> Dict:
        """Tendência de uma métrica nos últimos N dias."""
        cutoff = time.time() - days * 86400
        recent = [s for s in self.snapshots if s.timestamp >= cutoff]
        if len(recent) < 2:
            return {"direction": "stable", "confidence": 0.0, "values": []}
        
        values = [getattr(s, metric) for s in recent]
        # Regressão linear simples
        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        den = sum((i - x_mean) ** 2 for i in range(n))
        slope = num / den if den > 0 else 0
        
        return {
            "direction": "improving" if slope > 0 else "degrading" if slope < 0 else "stable",
            "slope": round(slope, 4),
            "current": values[-1],
            "avg_7d": round(y_mean, 2),
            "min_7d": min(values),
            "max_7d": max(values),
            "samples": len(values),
        }
    
    def is_degrading_over_time(self, threshold: float = 3.0) -> bool:
        """True se fitness está degradando consistentemente (>3% na tendência)."""
        t = self.trend("fitness", days=14)
        if t["direction"] == "degrading" and len(t["values"]) >= 5:
            avg = t["avg_7d"]
            if avg > 0:
                return ((t["values"][0] - t["values"][-1]) / avg) * 100 > threshold
        return False
    
    def stability_score(self) -> float:
        """Score de estabilidade 0-1 baseado na variância do fitness."""
        values = [s.fitness for s in self.snapshots]
        if len(values) < 3:
            return 1.0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return max(0.0, 1.0 - (variance * 10))


# ──── Validation Gate v2 ──────────────────────────────────────────

class ValidationGate:
    """Validação com constraints contextuais, diversity dinâmico e backstop multicritério."""
    
    BACKSTOP_CRITERIA = {
        "fitness_drop_pct": 5.0,        # Fitness caiu >5%
        "crash_increase_pct": 10.0,     # Crashes subiram >10%
        "test_failure_increase_pct": 5.0,  # Testes falhando >5% a mais
        "coverage_drop_pct": 3.0,       # Cobertura caiu >3%
    }
    
    def __init__(self):
        self.diversity_guard = DiversityGuard()
        self.long_term = LongTermMetrics()
        self.baseline_fitness: Optional[float] = None
        self.baseline_metrics: Dict[str, float] = {}
    
    def set_baseline(self, metrics: Dict[str, float]):
        self.baseline_metrics = metrics.copy()
        self.baseline_fitness = metrics.get("fitness_global", 0.0)
    
    def get_constraints_for_context(self, context: TaskContext) -> List[CompositeConstraint]:
        """Retorna constraints com pesos ajustados ao contexto."""
        weights = CONTEXT_WEIGHTS.get(context, CONTEXT_WEIGHTS[TaskContext.GENERAL_REPAIR])
        adjusted = []
        for c in BASE_CONSTRAINTS:
            w = weights.get(c.domain, c.weight)
            adjusted.append(CompositeConstraint(
                domain=c.domain, optimize=c.optimize,
                must_not_degrade=c.must_not_degrade[:],
                max_degradation_pct=c.max_degradation_pct, weight=w,
            ))
        return adjusted
    
    def validate(self, current_metrics: Dict[str, float],
                 context: TaskContext = TaskContext.GENERAL_REPAIR,
                 baseline: Optional[Dict[str, float]] = None) -> ValidationResult:
        """Validação completa com constraints contextuais e backstop multicritério."""
        
        constraints = self.get_constraints_for_context(context)
        ref = baseline or self.baseline_metrics
        violations, warnings, c_results, backstop_reasons = [], [], [], []
        
        # Registrar no rastreador de longo prazo
        self.long_term.record(
            fitness=current_metrics.get("fitness_global", 0),
            tempo_ms=current_metrics.get("tempo_execucao_ms", 0),
            patches=int(current_metrics.get("patches_gerados", 0)),
            cobertura=current_metrics.get("cobertura_vulnerabilidades", 0),
            falsos_negativos=int(current_metrics.get("falsos_negativos", 0)),
            crashes=int(current_metrics.get("crashes", 0)),
            tests_passed=int(current_metrics.get("tests_passed", 0)),
            tests_failed=int(current_metrics.get("tests_failed", 0)),
        )
        
        # Constraints compostas
        for constraint in constraints:
            result = {"domain": constraint.domain.value, "optimize": constraint.optimize,
                      "current": current_metrics.get(constraint.optimize), "degraded": []}
            
            for protected in constraint.must_not_degrade:
                curr = current_metrics.get(protected)
                base = ref.get(protected) if ref else curr
                
                if curr is not None and base is not None and base > 0:
                    degradation = ((base - curr) / base) * 100
                    if degradation > constraint.max_degradation_pct:
                        degradation = round(degradation, 1)
                        violations.append(
                            f"[{constraint.domain.value}] {protected} degradou {degradation}% "
                            f"(max: {constraint.max_degradation_pct}%). "
                            f"Rejeitado: otimizar '{constraint.optimize}' não justifica "
                            f"perda em '{protected}'."
                        )
                        result["degraded"].append({
                            "metric": protected, "degradation_pct": degradation,
                            "threshold": constraint.max_degradation_pct,
                        })
                    elif degradation > constraint.max_degradation_pct * 0.5:
                        warnings.append(
                            f"[{constraint.domain.value}] {protected} próximo do limite: "
                            f"{round(degradation, 1)}% (threshold: {constraint.max_degradation_pct}%)"
                        )
            c_results.append(result)
        
        # Backstop multicritério
        requires_backstop = False
        
        fitness_curr = current_metrics.get("fitness_global", 0)
        fitness_base = ref.get("fitness_global", fitness_curr) if ref else fitness_curr
        
        if fitness_base > 0:
            fitness_drop = ((fitness_base - fitness_curr) / fitness_base) * 100
            if fitness_drop > self.BACKSTOP_CRITERIA["fitness_drop_pct"]:
                requires_backstop = True
                backstop_reasons.append(f"Fitness caiu {fitness_drop:.1f}%")
        
        crashes_curr = current_metrics.get("crashes", 0)
        crashes_base = ref.get("crashes", crashes_curr) if ref else crashes_curr
        if crashes_base > 0:
            crash_increase = ((crashes_curr - crashes_base) / crashes_base) * 100
            if crash_increase > self.BACKSTOP_CRITERIA["crash_increase_pct"]:
                requires_backstop = True
                backstop_reasons.append(f"Crashes subiram {crash_increase:.0f}%")
        
        tests_failed_curr = current_metrics.get("tests_failed", 0)
        tests_total_curr = current_metrics.get("tests_total", 1)
        tests_failed_base = ref.get("tests_failed", 0) if ref else 0
        tests_total_base = ref.get("tests_total", 1) if ref else 1
        if tests_total_base > 0:
            fail_rate_curr = tests_failed_curr / max(tests_total_curr, 1) * 100
            fail_rate_base = tests_failed_base / max(tests_total_base, 1) * 100
            if fail_rate_curr - fail_rate_base > self.BACKSTOP_CRITERIA["test_failure_increase_pct"]:
                requires_backstop = True
                backstop_reasons.append(f"Taxa de falha em testes subiu {fail_rate_curr - fail_rate_base:.1f}pp")
        
        coverage_curr = current_metrics.get("cobertura_vulnerabilidades", 0)
        coverage_base = ref.get("cobertura_vulnerabilidades", coverage_curr) if ref else coverage_curr
        if coverage_base > 0:
            coverage_drop = ((coverage_base - coverage_curr) / coverage_base) * 100
            if coverage_drop > self.BACKSTOP_CRITERIA["coverage_drop_pct"]:
                requires_backstop = True
                backstop_reasons.append(f"Cobertura caiu {coverage_drop:.1f}%")
        
        # Degradação de longo prazo
        if self.long_term.is_degrading_over_time():
            warnings.append("⚠️ Tendência de degradação detectada nos últimos 14 dias")
        
        # Score final
        total_weight = sum(c.weight for c in constraints)
        score = 100.0 - len(violations) * (100.0 / max(total_weight * 2, 1))
        score = max(0.0, min(100.0, score))
        
        passed = len(violations) == 0 and not requires_backstop
        
        return ValidationResult(
            passed=passed, score=score, fitness_global=fitness_curr,
            constraint_results=c_results, violations=violations,
            warnings=warnings, requires_backstop=requires_backstop,
            backstop_reasons=backstop_reasons,
        )
    
    def record_agent_selection(self, agent_name: str):
        self.diversity_guard.record_selection(agent_name)
    
    def get_diversity_report(self) -> Dict:
        return self.diversity_guard.get_report()
    
    def get_long_term_trend(self, metric: str = "fitness", days: int = 7) -> Dict:
        return self.long_term.trend(metric, days)


# Global
validation_gate = ValidationGate()
