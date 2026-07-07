"""
Strategy Catalog — Catálogo versionado de políticas + Explicabilidade automática.

Cada estratégia aprovada gera Policy v1, v2, v3... — nunca sobrescreve.
Cada proposta explica automaticamente: por que foi gerada, evidências, torneio, gates.

Autor: Quimera MarkX — OMinivers
"""
import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("quimera.evolution.catalog")


class PolicyStatus(str, Enum):
    ACTIVE = "active"           # Em uso atual
    SUPERSEDED = "superseded"   # Substituída por versão mais nova
    DEPRECATED = "deprecated"   # Removida por ineficaz
    EXPERIMENTAL = "experimental"


class TaskCategory(str, Enum):
    BUFFER_OVERFLOW = "buffer_overflow"
    NULL_DEREFERENCE = "null_dereference"
    TYPE_ERROR = "type_error"
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    MEMORY_LEAK = "memory_leak"
    RACE_CONDITION = "race_condition"
    GENERAL = "general"


@dataclass
class Explanation:
    """Explicabilidade automática — por que esta estratégia existe."""
    trigger: str                            # O que motivou a criação
    evidence: List[str] = field(default_factory=list)  # Evidências que levaram à proposta
    tournament_result: Dict[str, Any] = field(default_factory=dict)  # Resultado do torneio
    validation_summary: str = ""            # Por que passou nos gates
    alternatives_considered: List[str] = field(default_factory=list)


@dataclass
class StrategyPolicy:
    """Uma política de estratégia versionada — NUNCA sobrescrita."""
    id: str = field(default_factory=lambda: f"POL-{uuid.uuid4().hex[:8]}")
    version: int = 1
    name: str = ""
    description: str = ""
    
    # Domínio
    task_category: TaskCategory = TaskCategory.GENERAL
    language: str = "python"
    
    # Configuração
    ga_population: int = 20
    ga_generations: int = 30
    primary_agent: str = "AgenteBase"
    fallback_agents: List[str] = field(default_factory=list)
    pipeline_horizons: List[str] = field(default_factory=lambda: ["H1","H2","H3","H4","H5","H6"])
    
    # Métricas de desempenho
    avg_fitness: float = 0.0
    avg_time_ms: float = 0.0
    avg_patches: int = 0
    success_rate: float = 0.0
    benchmarks_run: int = 0
    
    # Status e histórico
    status: PolicyStatus = PolicyStatus.ACTIVE
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    superseded_by: Optional[str] = None
    explanation: Explanation = field(default_factory=Explanation)
    proposal_id: Optional[str] = None       # ID da proposta que gerou esta política
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d["status"] = self.status.value
        d["task_category"] = self.task_category.value
        return d
    
    def summary(self) -> str:
        return (f"Policy v{self.version} [{self.id}] — {self.name} "
                f"({self.task_category.value}) — fitness: {self.avg_fitness:.3f} — {self.status.value}")


class StrategyCatalog:
    """Catálogo versionado de políticas de estratégia.
    
    Regras:
      - NUNCA sobrescrever: Policy v2 não apaga v1, apenas marca como SUPERSEDED
      - Toda política tem Explanation (por que existe, evidências, torneio)
      - Versionamento automático: ao aprovar proposta, nova versão é criada
    """
    
    def __init__(self, storage_path: str = "logs/strategy_catalog.json"):
        self.storage_path = Path(storage_path)
        self.policies: Dict[str, StrategyPolicy] = {}
        self._version_counters: Dict[str, int] = {}  # name → próximo version
        self._load()
    
    def _load(self):
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text())
                for item in data:
                    p = StrategyPolicy(
                        id=item.get("id", ""), version=item.get("version", 1),
                        name=item.get("name", ""), description=item.get("description", ""),
                        task_category=TaskCategory(item.get("task_category", "general")),
                        language=item.get("language", "python"),
                        ga_population=item.get("ga_population", 20),
                        ga_generations=item.get("ga_generations", 30),
                        primary_agent=item.get("primary_agent", "AgenteBase"),
                        avg_fitness=item.get("avg_fitness", 0.0),
                        avg_time_ms=item.get("avg_time_ms", 0.0),
                        avg_patches=item.get("avg_patches", 0),
                        success_rate=item.get("success_rate", 0.0),
                        benchmarks_run=item.get("benchmarks_run", 0),
                        status=PolicyStatus(item.get("status", "active")),
                        created_at=item.get("created_at", ""),
                        superseded_by=item.get("superseded_by"),
                        proposal_id=item.get("proposal_id"),
                    )
                    self.policies[p.id] = p
                    # Track version counters
                    if p.name not in self._version_counters:
                        self._version_counters[p.name] = p.version + 1
                    else:
                        self._version_counters[p.name] = max(
                            self._version_counters[p.name], p.version + 1
                        )
            except Exception as e:
                logger.warning(f"Failed to load strategy catalog: {e}")
    
    def _save(self):
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = [p.to_dict() for p in self.policies.values()]
        self.storage_path.write_text(json.dumps(data, indent=2, default=str))
    
    # ──── Criação ──────────────────────────────────────────────────
    
    def create_policy(self, name: str, description: str, task_category: TaskCategory,
                      language: str = "python", ga_population: int = 20,
                      ga_generations: int = 30, primary_agent: str = "AgenteBase",
                      fallback_agents: Optional[List[str]] = None,
                      proposal_id: Optional[str] = None,
                      explanation: Optional[Explanation] = None) -> StrategyPolicy:
        """Cria nova versão de política. Se já existe com mesmo nome, versiona."""
        
        # Se já existe política ativa com este nome, marcar como superseded
        for p in self.policies.values():
            if p.name == name and p.status == PolicyStatus.ACTIVE:
                p.status = PolicyStatus.SUPERSEDED
                p.superseded_by = None  # Será preenchido após criação
        
        version = self._version_counters.get(name, 1)
        
        policy = StrategyPolicy(
            version=version, name=name, description=description,
            task_category=task_category, language=language,
            ga_population=ga_population, ga_generations=ga_generations,
            primary_agent=primary_agent,
            fallback_agents=fallback_agents or [],
            proposal_id=proposal_id,
            explanation=explanation or Explanation(trigger="Manual creation"),
        )
        
        self.policies[policy.id] = policy
        self._version_counters[name] = version + 1
        
        # Atualizar referência de superseded
        for p in self.policies.values():
            if p.name == name and p.status == PolicyStatus.SUPERSEDED and not p.superseded_by:
                p.superseded_by = policy.id
        
        self._save()
        logger.info(f"📋 {policy.summary()}")
        return policy
    
    # ──── Queries ──────────────────────────────────────────────────
    
    def get_active(self, task_category: Optional[TaskCategory] = None,
                   language: Optional[str] = None) -> List[StrategyPolicy]:
        """Retorna políticas ativas, opcionalmente filtradas."""
        results = [p for p in self.policies.values() if p.status == PolicyStatus.ACTIVE]
        if task_category:
            results = [p for p in results if p.task_category == task_category]
        if language:
            results = [p for p in results if p.language == language]
        return results
    
    def get_best_for(self, task_category: TaskCategory, language: str = "python") -> Optional[StrategyPolicy]:
        """Melhor política ativa para uma categoria de tarefa."""
        active = self.get_active(task_category=task_category, language=language)
        if not active:
            return None
        return max(active, key=lambda p: p.avg_fitness * 0.6 + p.success_rate * 0.4)
    
    def get_lineage(self, policy_name: str) -> List[StrategyPolicy]:
        """Histórico completo de versões de uma política (v1, v2, v3...)."""
        lineage = [p for p in self.policies.values() if p.name == policy_name]
        return sorted(lineage, key=lambda p: p.version)
    
    def update_metrics(self, policy_id: str, fitness: float, time_ms: float, patches: int):
        """Atualiza métricas de desempenho de uma política."""
        if policy_id not in self.policies:
            return
        p = self.policies[policy_id]
        n = p.benchmarks_run
        p.avg_fitness = (p.avg_fitness * n + fitness) / (n + 1)
        p.avg_time_ms = (p.avg_time_ms * n + time_ms) / (n + 1)
        p.avg_patches = int((p.avg_patches * n + patches) / (n + 1))
        p.benchmarks_run = n + 1
        p.success_rate = p.benchmarks_run / (p.benchmarks_run + 1)  # smoothing
        self._save()
    
    def get_stats(self) -> Dict:
        total = len(self.policies)
        active = len([p for p in self.policies.values() if p.status == PolicyStatus.ACTIVE])
        return {
            "total_policies": total,
            "active_policies": active,
            "superseded_policies": total - active,
            "categories": {c.value: len(self.get_active(task_category=c)) for c in TaskCategory},
            "avg_fitness": round(sum(p.avg_fitness for p in self.policies.values() if p.benchmarks_run > 0) / max(total, 1), 3),
            "total_benchmarks": sum(p.benchmarks_run for p in self.policies.values()),
        }


# Global
strategy_catalog = StrategyCatalog()
