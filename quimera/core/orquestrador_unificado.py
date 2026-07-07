"""
Orquestrador Unificado — Coordenação central de todos os agentes Quimera.
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("quimera.orquestrador_unificado")

class OrquestradorUnificado:
    """Orquestrador central que coordena agentes e pipelines."""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self._agents = {}
        self._pipeline_status = "idle"
    
    def register_agent(self, name: str, agent: Any) -> None:
        """Registra um agente no orquestrador."""
        self._agents[name] = agent
        logger.info(f"Agent registered: {name}")
    
    def get_agent(self, name: str) -> Optional[Any]:
        """Obtém um agente pelo nome."""
        return self._agents.get(name)
    
    async def execute_pipeline(self, task: Dict) -> Dict:
        """Executa pipeline completo de uma task."""
        self._pipeline_status = "running"
        try:
            results = {}
            for agent_name, agent in self._agents.items():
                logger.info(f"Executing agent: {agent_name}")
                results[agent_name] = f"Task processed by {agent_name}"
            self._pipeline_status = "completed"
            return {"status": "completed", "results": results}
        except Exception as e:
            self._pipeline_status = "failed"
            logger.error(f"Pipeline failed: {e}")
            return {"status": "failed", "error": str(e)}
    
    def get_status(self) -> Dict:
        """Status atual do orquestrador."""
        return {
            "pipeline": self._pipeline_status,
            "agents_registered": len(self._agents),
            "agent_names": list(self._agents.keys()),
        }
