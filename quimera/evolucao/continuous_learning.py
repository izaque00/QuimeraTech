"""
ContinuousLearner — Passo 6 da camada de decisão.

Aprende com cada execução: quais estratégias, agentes e combinações
funcionam melhor para cada tipo de erro.

Uso:
    learner = ContinuousLearner()
    learner.learn(
        plan=plan,
        outcome={"success": True, "fitness": 0.85, "duration_ms": 1200},
    )
    learner.learn(plan2, {"success": False, "error": "timeout"})
    
    best = learner.get_best_plan("buffer_overflow")
"""
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("quimera.continuous_learner")


@dataclass
class PlanRecord:
    """Registro de um plano executado."""
    plan_key: str  # "error_type:strategy:primary_agent"
    attempts: int = 0
    successes: int = 0
    total_fitness: float = 0.0
    total_duration_ms: float = 0.0
    last_used: str = ""


class ContinuousLearner:
    """Aprendizado contínuo baseado em resultados reais de execução.
    
    Armazena e analisa:
      - Quais estratégias funcionam melhor por tipo de erro
      - Quais agentes são mais eficazes
      - Quais combinações (estratégia + agente) produzem os melhores resultados
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path) if storage_path else Path("logs/learning_state.json")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._records: Dict[str, PlanRecord] = {}
        self._error_stats: Dict[str, Dict] = defaultdict(lambda: {"total": 0, "successes": 0})
        self._load()
    
    def _load(self):
        if self.storage_path.exists():
            with open(self.storage_path) as f:
                data = json.load(f)
            for key, rec in data.get("records", {}).items():
                self._records[key] = PlanRecord(**rec)
            self._error_stats = defaultdict(
                lambda: {"total": 0, "successes": 0},
                data.get("error_stats", {})
            )
    
    def _save(self):
        with open(self.storage_path, 'w') as f:
            json.dump({
                "records": {k: {
                    "plan_key": r.plan_key,
                    "attempts": r.attempts,
                    "successes": r.successes,
                    "total_fitness": r.total_fitness,
                    "total_duration_ms": r.total_duration_ms,
                    "last_used": r.last_used,
                } for k, r in self._records.items()},
                "error_stats": dict(self._error_stats),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }, f, indent=2)
    
    def learn(self, plan: Dict[str, Any], outcome: Dict[str, Any]):
        """Aprende com o resultado de um plano."""
        error_type = plan.get("error_type", "unknown")
        strategy = plan.get("strategy", "unknown")
        primary_agent = plan.get("primary_agent", "unknown")
        
        plan_key = f"{error_type}:{strategy}:{primary_agent}"
        
        if plan_key not in self._records:
            self._records[plan_key] = PlanRecord(plan_key=plan_key)
        
        rec = self._records[plan_key]
        rec.attempts += 1
        
        if outcome.get("success", False):
            rec.successes += 1
            rec.total_fitness += outcome.get("fitness", 0)
        
        rec.total_duration_ms += outcome.get("duration_ms", 0)
        rec.last_used = datetime.now(timezone.utc).isoformat()
        
        # Update error stats
        self._error_stats[error_type]["total"] += 1
        if outcome.get("success", False):
            self._error_stats[error_type]["successes"] += 1
        
        self._save()
        logger.debug(f"ContinuousLearner: learned {plan_key} → success={outcome.get('success')}")
    
    def get_best_plan(self, error_type: str, min_attempts: int = 3) -> Optional[Dict[str, Any]]:
        """Retorna o melhor plano para um tipo de erro."""
        candidates = []
        for key, rec in self._records.items():
            if key.startswith(error_type + ":") and rec.attempts >= min_attempts:
                success_rate = rec.successes / max(rec.attempts, 1)
                avg_fitness = rec.total_fitness / max(rec.successes, 1) if rec.successes > 0 else 0
                score = success_rate * avg_fitness if avg_fitness > 0 else success_rate
                candidates.append((key, score, rec))
        
        if not candidates:
            return None
        
        best_key, best_score, best_rec = max(candidates, key=lambda x: x[1])
        _, strategy, agent = best_key.split(":", 2)
        
        return {
            "error_type": error_type,
            "strategy": strategy,
            "agent": agent,
            "score": round(best_score, 3),
            "success_rate": f"{best_rec.successes / max(best_rec.attempts, 1):.1%}",
            "avg_fitness": round(best_rec.total_fitness / max(best_rec.successes, 1), 3) if best_rec.successes > 0 else 0,
            "attempts": best_rec.attempts,
        }
    
    def get_error_success_rate(self, error_type: str) -> float:
        """Taxa de sucesso global para um tipo de erro."""
        stats = self._error_stats.get(error_type, {"total": 0, "successes": 0})
        return stats["successes"] / max(stats["total"], 1)
    
    def get_all_best_plans(self, limit: int = 10) -> List[Dict]:
        """Top planos globalmente."""
        scored = []
        for key, rec in self._records.items():
            if rec.attempts >= 3:
                sr = rec.successes / rec.attempts
                af = rec.total_fitness / max(rec.successes, 1) if rec.successes > 0 else 0
                scored.append((key, sr * max(af, 0.1), rec))
        scored.sort(key=lambda x: -x[1])
        return [
            {
                "plan": key.split(":", 2),
                "score": round(s, 3),
                "attempts": r.attempts,
                "success_rate": f"{r.successes / r.attempts:.1%}",
            }
            for key, s, r in scored[:limit]
        ]


# Global
continuous_learner = ContinuousLearner()
