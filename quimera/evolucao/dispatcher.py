"""
Dispatcher — Passo 2 da camada de decisão.

Recebe um problema (tipo de erro + linguagem) e consulta o AgentRegistry
para devolver os agentes candidatos, ordenados por prioridade.

NÃO executa nada. Só seleciona.

Uso:
    dispatcher = Dispatcher()
    candidates = dispatcher.dispatch("buffer_overflow", "c")
    → ["AgenteEstrategista", "AgenteRefinadorV4", "AgenteGerador", ...]
"""
import logging
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("quimera.dispatcher")


class Dispatcher:
    """Seleciona agentes candidatos para um problema.
    
    Estratégia de seleção:
      1. AgentRegistry.find_by_error_type() → candidatos por especialidade
      2. AgentRegistry.find_by_language() → filtra por linguagem
      3. Intersecção → agentes que atendem AMBOS os critérios
      4. Ordenação por prioridade (do metadata)
      5. Fallback: se nenhum agente específico, usa AgenteBase
    """
    
    def __init__(self):
        self._dispatch_count: Dict[str, int] = {}
    
    def dispatch(
        self,
        error_type: str,
        language: str = "c",
        min_priority: int = 0,
        max_agents: int = 5,
        exclude: Optional[Set[str]] = None,
    ) -> List[str]:
        """Seleciona agentes candidatos para resolver um problema.
        
        Args:
            error_type: Tipo de erro (ex: 'buffer_overflow', 'ImportError')
            language: Linguagem do código
            min_priority: Prioridade mínima (0-100)
            max_agents: Máximo de agentes a retornar
            exclude: Agentes a excluir (já tentados e falharam)
            
        Returns:
            Lista de nomes de agentes, ordenados por prioridade decrescente
        """
        from quimera.mind.agent_registry import AgentRegistry
        
        exclude = exclude or set()
        
        # Encontrar agentes por tipo de erro
        by_error = set(AgentRegistry.find_by_error_type(error_type, language))
        
        # Encontrar agentes por linguagem
        by_lang = set(AgentRegistry.find_by_language(language))
        
        # Intersecção (prefere agentes que atendem AMBOS os critérios)
        candidates = list(by_error & by_lang) if (by_error & by_lang) else list(by_error | by_lang)
        
        # Filtrar excluídos e prioridade mínima
        filtered = []
        for name in candidates:
            if name in exclude:
                continue
            meta = AgentRegistry.get_metadata(name)
            if meta and meta.get("priority", 0) >= min_priority:
                filtered.append((name, meta.get("priority", 0)))
        
        # Ordenar por prioridade
        filtered.sort(key=lambda x: -x[1])
        
        result = [name for name, _ in filtered[:max_agents]]
        
        # Fallback
        if not result:
            result = ["AgenteBase"]
        
        # Registrar
        key = f"{error_type}:{language}"
        self._dispatch_count[key] = self._dispatch_count.get(key, 0) + 1
        
        logger.debug(f"Dispatcher: {error_type}/{language} → {result}")
        return result
    
    def get_stats(self) -> Dict:
        """Estatísticas de dispatches."""
        return {
            "total_dispatches": sum(self._dispatch_count.values()),
            "unique_combinations": len(self._dispatch_count),
            "top_5": dict(sorted(self._dispatch_count.items(), key=lambda x: -x[1])[:5]),
        }


# Global
dispatcher = Dispatcher()
