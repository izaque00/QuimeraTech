"""
AgentReputation — Passo 3 da camada de decisão.

Mede e armazena o desempenho histórico de cada agente.
Usado pelo Dispatcher para desempatar entre agentes de mesma prioridade.

Uso:
    rep = AgentReputation()
    rep.record("PythonAgent", "ImportError", success=True, fitness=0.95, duration_ms=120)
    rep.record("RustAgent", "ImportError", success=False, duration_ms=500)
    
    score = rep.get_score("PythonAgent", "ImportError")  # → 0.92
"""
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("quimera.reputation")


@dataclass
class AgentStats:
    """Estatísticas acumuladas de um agente."""
    agent_name: str
    total_attempts: int = 0
    successes: int = 0
    total_fitness: float = 0.0
    total_duration_ms: float = 0.0
    last_used: str = ""
    error_types: Dict[str, int] = field(default_factory=dict)  # error_type → attempts


class AgentReputation:
    """Sistema de reputação baseado em histórico real de execuções.
    
    O score combina:
      - 50% success rate (peso principal)
      - 25% fitness médio (qualidade dos patches)
      - 15% recência (último uso recente)
      - 10% velocidade (mais rápido = melhor)
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path) if storage_path else Path("logs/agent_reputation.json")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._agents: Dict[str, AgentStats] = {}
        self._load()
    
    def _load(self):
        if self.storage_path.exists():
            with open(self.storage_path) as f:
                data = json.load(f)
            for name, s in data.items():
                self._agents[name] = AgentStats(**s)
    
    def _save(self):
        with open(self.storage_path, 'w') as f:
            json.dump({
                name: {
                    "agent_name": s.agent_name,
                    "total_attempts": s.total_attempts,
                    "successes": s.successes,
                    "total_fitness": s.total_fitness,
                    "total_duration_ms": s.total_duration_ms,
                    "last_used": s.last_used,
                    "error_types": s.error_types,
                }
                for name, s in self._agents.items()
            }, f, indent=2)
    
    def record(
        self,
        agent_name: str,
        error_type: str,
        success: bool,
        fitness: float = 0.0,
        duration_ms: float = 0.0,
    ):
        """Registra o resultado de uma execução de agente."""
        if agent_name not in self._agents:
            self._agents[agent_name] = AgentStats(agent_name=agent_name)
        
        s = self._agents[agent_name]
        s.total_attempts += 1
        if success:
            s.successes += 1
            s.total_fitness += fitness
        s.total_duration_ms += duration_ms
        s.last_used = datetime.now(timezone.utc).isoformat()
        s.error_types[error_type] = s.error_types.get(error_type, 0) + 1
        
        self._save()
    
    def get_score(self, agent_name: str, error_type: Optional[str] = None) -> float:
        """Calcula o score de reputação (0-1)."""
        s = self._agents.get(agent_name)
        if not s or s.total_attempts == 0:
            return 0.0
        
        # Success rate (50%)
        success_rate = s.successes / max(s.total_attempts, 1)
        
        # Average fitness (25%)
        avg_fitness = s.total_fitness / max(s.successes, 1) if s.successes > 0 else 0.0
        
        # Recency (15%)
        recency = 0.0
        if s.last_used:
            try:
                last = datetime.fromisoformat(s.last_used)
                hours_ago = (datetime.now(timezone.utc) - last).total_seconds() / 3600
                recency = max(0.0, 1.0 - hours_ago / 168)
            except (ValueError, TypeError):
                pass
        
        # Speed (10%)
        avg_ms = s.total_duration_ms / max(s.total_attempts, 1)
        speed = max(0.0, 1.0 - avg_ms / 10000)  # 10s = 0, 0ms = 1
        
        return 0.50 * success_rate + 0.25 * avg_fitness + 0.15 * recency + 0.10 * speed
    
    def rank_candidates(
        self,
        agent_names: List[str],
        error_type: str,
    ) -> List[Tuple[str, float]]:
        """Ordena candidatos por score de reputação (desempate do Dispatcher)."""
        scored = [(name, self.get_score(name, error_type)) for name in agent_names]
        scored.sort(key=lambda x: -x[1])
        return scored
    
    def get_top_agents(self, limit: int = 10) -> List[Tuple[str, float, int]]:
        """Top agentes por score global."""
        scored = [
            (name, self.get_score(name), s.total_attempts)
            for name, s in self._agents.items()
            if s.total_attempts > 0
        ]
        scored.sort(key=lambda x: -x[1])
        return scored[:limit]
    
    def get_stats(self, agent_name: str) -> Dict:
        s = self._agents.get(agent_name)
        if not s:
            return {"error": "unknown agent"}
        return {
            "name": s.agent_name,
            "attempts": s.total_attempts,
            "successes": s.successes,
            "success_rate": f"{s.successes / max(s.total_attempts, 1):.1%}",
            "avg_fitness": round(s.total_fitness / max(s.successes, 1), 3) if s.successes > 0 else 0,
            "avg_duration_ms": round(s.total_duration_ms / max(s.total_attempts, 1), 0),
            "score": round(self.get_score(agent_name), 3),
            "error_types": s.error_types,
        }


# Global
agent_reputation = AgentReputation()
