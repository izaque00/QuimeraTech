"""
Base Plugin — Classe base para todos os plugins Quimera MarkX.
"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Optional

class PluginType(Enum):
    SCANNER = "scanner"
    ANALYZER = "analyzer"
    TRANSFORMER = "transformer"
    REPORTER = "reporter"
    SECURITY = "security"
    CUSTOM = "custom"

class BasePlugin(ABC):
    """Classe base abstrata para plugins."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._initialized = False
    
    @property
    @abstractmethod
    def plugin_type(self) -> PluginType:
        """Tipo do plugin."""
        ...
    
    @property
    @abstractmethod
    def plugin_name(self) -> str:
        """Nome do plugin."""
        ...
    
    @abstractmethod
    def initialize(self) -> bool:
        """Inicializa o plugin. Retorna True se ok."""
        ...
    
    @abstractmethod
    def execute(self, input_data: Any) -> Any:
        """Executa a lógica principal do plugin."""
        ...
    
    def shutdown(self) -> None:
        """Limpeza ao desligar."""
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna status do plugin."""
        return {
            "name": self.plugin_name,
            "type": self.plugin_type.value,
            "initialized": self._initialized,
        }
