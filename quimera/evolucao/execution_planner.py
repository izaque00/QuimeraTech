"""
ExecutionPlanner — Passo 5 da camada de decisão.

Monta um plano de execução completo combinando:
  StrategySelector (estratégia)
  Dispatcher (agentes candidatos)
  AgentReputation (ranking dos agentes)

O plano é um dicionário que o Pipeline pode executar diretamente.

Uso:
    planner = ExecutionPlanner()
    plan = planner.plan("buffer_overflow", "c")
    → {
        "strategy": "ga_redteam_fuzz",
        "stages": ["accept", "retrieve", "verify", "evolve", "attack", "output", "record"],
        "agents": ["AgenteEstrategista", "AgenteRefinadorV4", "AgenteGerador"],
        "skip_ga": False,
        ...
    }
"""
import logging
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("quimera.execution_planner")


class ExecutionPlanner:
    """Planeja a execução combinando estratégia + agentes + reputação.
    
    Pipeline de planejamento:
      1. StrategySelector.select() → qual estratégia usar
      2. Dispatcher.dispatch() → quais agentes são candidatos
      3. AgentReputation.rank_candidates() → ordem por reputação
      4. Monta o plano final com stages + agents
    """
    
    def __init__(self):
        self._plan_count = 0
    
    def plan(
        self,
        error_type: str,
        language: str = "c",
        error_description: str = "",
        max_agents: int = 5,
        exclude: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """Cria um plano de execução completo."""
        from quimera.evolucao.strategy_selector import strategy_selector
        from quimera.evolucao.dispatcher import dispatcher
        from quimera.evolucao.agent_reputation import agent_reputation
        
        # 1. Estratégia
        strategy = strategy_selector.select(error_type, language)
        
        # 2. Agentes candidatos
        candidates = dispatcher.dispatch(
            error_type=error_type,
            language=language,
            max_agents=max_agents,
            exclude=exclude,
        )
        
        # 3. Rank por reputação
        ranked = agent_reputation.rank_candidates(candidates, error_type)
        
        # 4. Filtrar por capacidades preferidas da estratégia
        preferred = strategy.get("prefer_capabilities", [])
        if preferred:
            from quimera.mind.agent_registry import AgentRegistry
            boosted = []
            for name, score in ranked:
                meta = AgentRegistry.get_metadata(name)
                if meta:
                    caps = meta.get("capabilities", [])
                    if any(c in caps for c in preferred):
                        score += 0.15  # Boost para agentes com a capacidade certa
                boosted.append((name, score))
            boosted.sort(key=lambda x: -x[1])
            ranked = boosted
        
        # 5. Montar plano
        plan = {
            "error_type": error_type,
            "language": language,
            "error_description": error_description,
            "strategy": strategy["name"],
            "strategy_description": strategy["description"],
            "stages": strategy["stages"],
            "skip_ga": strategy.get("skip_ga", False),
            "agents": [name for name, _ in ranked],
            "agent_scores": {name: round(score, 3) for name, score in ranked},
            "primary_agent": ranked[0][0] if ranked else "AgenteBase",
            "plan_id": f"plan-{self._plan_count}",
        }
        
        self._plan_count += 1
        logger.info(f"ExecutionPlanner: [{plan['plan_id']}] {error_type}/{language} → {strategy['name']} ({len(ranked)} agents)")
        return plan
    
    def get_stats(self) -> Dict:
        return {"total_plans": self._plan_count}


# Global
execution_planner = ExecutionPlanner()
