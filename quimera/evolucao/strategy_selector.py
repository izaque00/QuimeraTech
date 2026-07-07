"""
StrategySelector — Passo 4 da camada de decisão.

Escolhe a ESTRATÉGIA (não o agente) antes da execução.

Mapeia tipo de erro → caminho de resolução:
  - syntax_error → correção direta (AutoCorrecao)
  - buffer_overflow → GA + RedTeam + Fuzz
  - ImportError → resolução de dependências
  - kernel_panic → Kernel Strategy

Uso:
    sel = StrategySelector()
    strategy = sel.select("buffer_overflow", "c")
    → {"name": "ga_redteam_fuzz", "stages": ["evolve", "attack", "verify"], "agents": [...]}
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("quimera.strategy_selector")


class StrategySelector:
    """Seleciona a estratégia de resolução baseada no tipo de erro."""
    
    # Mapeamento: error_type → estratégia + pipeline stages
    STRATEGIES: Dict[str, Dict[str, Any]] = {
        # Erros de compilação → correção direta
        "compilation_error": {
            "name": "direct_fix",
            "description": "Correção direta sem evolução genética",
            "stages": ["accept", "retrieve", "fix", "verify", "output"],
            "prefer_capabilities": ["auto_fix", "simple_patch"],
            "skip_ga": True,
        },
        "syntax_error": {
            "name": "direct_fix",
            "description": "Correção sintática direta",
            "stages": ["accept", "fix", "verify", "output"],
            "prefer_capabilities": ["auto_fix"],
            "skip_ga": True,
        },
        "missing_import": {
            "name": "resolve_deps",
            "description": "Resolução de dependências",
            "stages": ["accept", "retrieve", "resolve", "verify", "output"],
            "prefer_capabilities": ["import_resolution"],
            "skip_ga": True,
        },
        
        # Corrupção de memória → pipeline completo
        "buffer_overflow": {
            "name": "ga_redteam_fuzz",
            "description": "GA + RedTeam + Fuzzing — pipeline completo",
            "stages": ["accept", "retrieve", "verify", "evolve", "attack", "output", "record"],
            "prefer_capabilities": ["genetic_evolution", "security_scan"],
            "skip_ga": False,
        },
        "null_deref": {
            "name": "ga_redteam_fuzz",
            "description": "GA + RedTeam + Fuzzing",
            "stages": ["accept", "retrieve", "verify", "evolve", "attack", "output", "record"],
            "prefer_capabilities": ["genetic_evolution"],
            "skip_ga": False,
        },
        "use_after_free": {
            "name": "ga_redteam_fuzz",
            "description": "GA + RedTeam + Fuzzing",
            "stages": ["accept", "retrieve", "verify", "evolve", "attack", "output", "record"],
            "prefer_capabilities": ["genetic_evolution"],
            "skip_ga": False,
        },
        "format_string": {
            "name": "ga_redteam_fuzz",
            "description": "GA + RedTeam + Fuzzing",
            "stages": ["accept", "retrieve", "verify", "evolve", "attack", "output", "record"],
            "prefer_capabilities": ["genetic_evolution"],
            "skip_ga": False,
        },
        "integer_overflow": {
            "name": "ga_redteam_fuzz",
            "description": "GA + RedTeam + Fuzzing",
            "stages": ["accept", "retrieve", "verify", "evolve", "attack", "output", "record"],
            "prefer_capabilities": ["genetic_evolution"],
            "skip_ga": False,
        },
        "memory_leak": {
            "name": "ga_redteam_fuzz",
            "description": "GA + RedTeam + Fuzzing",
            "stages": ["accept", "retrieve", "verify", "evolve", "attack", "output", "record"],
            "prefer_capabilities": ["genetic_evolution"],
            "skip_ga": False,
        },
        "race_condition": {
            "name": "ga_redteam_fuzz",
            "description": "GA + RedTeam + Fuzzing",
            "stages": ["accept", "retrieve", "verify", "evolve", "attack", "output", "record"],
            "prefer_capabilities": ["genetic_evolution"],
            "skip_ga": False,
        },
        
        # Kernel → kernel strategy
        "kernel_panic": {
            "name": "kernel_strategy",
            "description": "Configuração de kernel + sandbox isolado",
            "stages": ["accept", "configure", "sandbox", "evolve", "output"],
            "prefer_capabilities": ["kernel_config", "sandbox_setup"],
            "skip_ga": False,
        },
        
        # Segurança → AEGIS
        "cve": {
            "name": "security_audit",
            "description": "AEGIS security scan + CVE check",
            "stages": ["accept", "scan", "audit", "output"],
            "prefer_capabilities": ["security_scan", "cve_detection"],
            "skip_ga": True,
        },
        "vulnerability": {
            "name": "security_audit",
            "description": "AEGIS security scan",
            "stages": ["accept", "scan", "audit", "output"],
            "prefer_capabilities": ["security_scan"],
            "skip_ga": True,
        },
    }
    
    # Fallback para qualquer tipo de erro não mapeado
    DEFAULT_STRATEGY = {
        "name": "full_pipeline",
        "description": "Pipeline completo H1→H6 com GA",
        "stages": ["accept", "retrieve", "verify", "evolve", "attack", "output", "record"],
        "prefer_capabilities": [],
        "skip_ga": False,
    }
    
    def select(self, error_type: str, language: str = "c") -> Dict[str, Any]:
        """Seleciona a estratégia para um tipo de erro."""
        strategy = self.STRATEGIES.get(error_type, self.DEFAULT_STRATEGY)
        
        # Adiciona contexto
        result = dict(strategy)
        result["error_type"] = error_type
        result["language"] = language
        result["source"] = "mapped" if error_type in self.STRATEGIES else "default"
        
        logger.debug(f"StrategySelector: {error_type} → {result['name']} ({result['source']})")
        return result
    
    def get_strategy_for_capability(self, capability: str) -> Optional[str]:
        """Encontra a estratégia que prefere uma capacidade específica."""
        for error_type, strategy in self.STRATEGIES.items():
            if capability in strategy.get("prefer_capabilities", []):
                return strategy["name"]
        return None


# Global
strategy_selector = StrategySelector()
