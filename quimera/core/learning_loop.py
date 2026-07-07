# quimera/core/learning_loop.py
"""
Learning Loop — Sistema de aprendizado contínuo do Quimera Mark II.

Persiste recompensas do Bandit, evolui a KnowledgeBase com cada
missão, e aprende qual LLM funciona melhor para cada tipo de tarefa.

Uso:
    from quimera.core.learning_loop import LearningLoop
    
    loop = LearningLoop(db_session)
    await loop.record_mission_result(mission_id, metrics)
    insights = loop.get_insights()
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class MissionRecord:
    """Registro de uma missão para aprendizado."""
    mission_id: str
    timestamp: datetime
    task_type: str
    llm_provider: str
    llm_model: str
    success: bool
    execution_time_ms: float
    attempts: int
    strategy_used: str
    fitness_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderStats:
    """Estatísticas de um provedor LLM."""
    provider: str
    total_calls: int = 0
    successful: int = 0
    avg_time_ms: float = 0.0
    avg_fitness: float = 0.0
    best_for_tasks: List[str] = field(default_factory=list)
    _times: List[float] = field(default_factory=list)
    _fitnesses: List[float] = field(default_factory=list)
    
    def record(self, success: bool, time_ms: float, fitness: float):
        self.total_calls += 1
        if success:
            self.successful += 1
        self._times.append(time_ms)
        self._fitnesses.append(fitness)
        self.avg_time_ms = sum(self._times) / len(self._times)
        self.avg_fitness = sum(self._fitnesses) / len(self._fitnesses)
    
    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.successful / self.total_calls


class LearningLoop:
    """Sistema de aprendizado contínuo.
    
    Aprende com cada missão executada:
    1. Qual LLM funciona melhor para cada tipo de tarefa
    2. Quais heurísticas de mutação são mais eficazes
    3. Padrões de falha e suas soluções
    4. Evolução da KnowledgeBase com feedback real
    """
    
    def __init__(self, db_session=None, persistence_path: str = None):
        self.db = db_session
        self.persistence_path = persistence_path
        self._missions: List[MissionRecord] = []
        self._provider_stats: Dict[str, ProviderStats] = {}
        self._task_llm_map: Dict[str, str] = {}  # task_type → best_provider
        self._heuristic_rewards: Dict[str, List[float]] = {}
        self._failure_patterns: Dict[str, int] = {}
        logger.info("LearningLoop inicializado")
    
    async def record_mission_result(self, record: MissionRecord):
        """Registra resultado de uma missão para aprendizado."""
        self._missions.append(record)
        
        # Atualiza estatísticas do provedor
        key = f"{record.llm_provider}:{record.llm_model}"
        if key not in self._provider_stats:
            self._provider_stats[key] = ProviderStats(provider=key)
        self._provider_stats[key].record(
            record.success, record.execution_time_ms, record.fitness_score
        )
        
        # Atualiza mapeamento task→LLM
        if record.success and record.fitness_score > 0.7:
            current_best = self._task_llm_map.get(record.task_type)
            if not current_best or self._provider_stats[key].avg_fitness > self._provider_stats.get(current_best, ProviderStats(provider="")).avg_fitness:
                self._task_llm_map[record.task_type] = key
        
        # Registra padrões de falha
        if not record.success:
            fail_key = f"{record.task_type}:{record.llm_provider}"
            self._failure_patterns[fail_key] = self._failure_patterns.get(fail_key, 0) + 1
        
        # Persiste se configurado
        if self.db or self.persistence_path:
            await self._persist()
        
        logger.debug(f"LearningLoop: missão '{record.mission_id}' registrada (success={record.success})")
    
    async def record_heuristic_reward(self, heuristic_name: str, reward: float):
        """Registra recompensa de uma heurística de mutação."""
        if heuristic_name not in self._heuristic_rewards:
            self._heuristic_rewards[heuristic_name] = []
        self._heuristic_rewards[heuristic_name].append(reward)
    
    def get_best_llm_for_task(self, task_type: str) -> Optional[str]:
        """Retorna o melhor provedor LLM para um tipo de tarefa."""
        return self._task_llm_map.get(task_type)
    
    def get_best_heuristic(self) -> Optional[str]:
        """Retorna a heurística com maior recompensa média."""
        if not self._heuristic_rewards:
            return None
        best = None
        best_avg = -1
        for name, rewards in self._heuristic_rewards.items():
            avg = sum(rewards) / len(rewards)
            if avg > best_avg:
                best_avg = avg
                best = name
        return best
    
    def get_insights(self) -> Dict[str, Any]:
        """Gera insights a partir do histórico de aprendizado."""
        return {
            "total_missions": len(self._missions),
            "success_rate": sum(1 for m in self._missions if m.success) / max(len(self._missions), 1),
            "best_providers": {
                task: prov for task, prov in self._task_llm_map.items()
            },
            "provider_stats": {
                k: {
                    "total": s.total_calls,
                    "success_rate": s.success_rate,
                    "avg_time_ms": s.avg_time_ms,
                    "avg_fitness": s.avg_fitness,
                }
                for k, s in sorted(
                    self._provider_stats.items(),
                    key=lambda x: x[1].success_rate,
                    reverse=True,
                )[:5]
            },
            "best_heuristic": self.get_best_heuristic(),
            "failure_patterns": dict(sorted(
                self._failure_patterns.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:5]),
        }
    
    async def _persist(self):
        """Persiste dados de aprendizado."""
        try:
            data = {
                "missions": [
                    {
                        "mission_id": m.mission_id,
                        "timestamp": m.timestamp.isoformat(),
                        "task_type": m.task_type,
                        "llm_provider": m.llm_provider,
                        "success": m.success,
                        "fitness_score": m.fitness_score,
                    }
                    for m in self._missions[-100:]  # últimas 100
                ],
                "task_llm_map": self._task_llm_map,
                "heuristic_rewards": {
                    k: v[-50:] for k, v in self._heuristic_rewards.items()
                },
            }
            if self.persistence_path:
                with open(self.persistence_path, 'w') as f:
                    json.dump(data, f, indent=2)
            if self.db:
                # Persistir via db/repository
                pass
        except Exception as e:
            logger.warning(f"LearningLoop: falha ao persistir: {e}")
    
    @classmethod
    async def load(cls, persistence_path: str, **kwargs):
        """Carrega estado de aprendizado de arquivo."""
        loop = cls(persistence_path=persistence_path, **kwargs)
        try:
            import os
            if os.path.exists(persistence_path):
                with open(persistence_path) as f:
                    data = json.load(f)
                loop._task_llm_map = data.get("task_llm_map", {})
                loop._heuristic_rewards = data.get("heuristic_rewards", {})
                logger.info(f"LearningLoop: estado carregado ({len(loop._task_llm_map)} task mappings)")
        except Exception as e:
            logger.warning(f"LearningLoop: não foi possível carregar estado: {e}")
        return loop
