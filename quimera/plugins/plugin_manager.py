"""
Plugin Manager — Descoberta, registro e ciclo de vida de plugins.
Parte do sistema de plugins Quimera MarkX.
"""
import importlib
import logging
import pkgutil
from pathlib import Path
from typing import Dict, List, Optional, Type

logger = logging.getLogger("quimera.plugin_manager")

class PluginManager:
    """Gerencia descoberta, carregamento e execução de plugins."""
    
    def __init__(self):
        self._plugins: Dict[str, object] = {}
        self._plugin_classes: Dict[str, Type] = {}
    
    def discover(self, package_path: str = "quimera.plugins") -> List[str]:
        """Descobre plugins disponíveis no pacote."""
        discovered = []
        try:
            package = importlib.import_module(package_path)
            package_dir = Path(package.__file__).parent
            for _, name, is_pkg in pkgutil.iter_modules([str(package_dir)]):
                discovered.append(name)
                logger.info(f"Plugin discovered: {name}")
        except Exception as e:
            logger.warning(f"Plugin discovery failed: {e}")
        return discovered
    
    def register(self, name: str, plugin_class: Type) -> None:
        """Registra uma classe de plugin."""
        self._plugin_classes[name] = plugin_class
        logger.info(f"Plugin registered: {name}")
    
    def load(self, name: str) -> Optional[object]:
        """Carrega e instancia um plugin pelo nome."""
        if name in self._plugins:
            return self._plugins[name]
        if name in self._plugin_classes:
            instance = self._plugin_classes[name]()
            self._plugins[name] = instance
            return instance
        return None
    
    def list_plugins(self) -> List[str]:
        """Lista todos os plugins registrados."""
        return list(self._plugin_classes.keys())
    
    def unload(self, name: str) -> None:
        """Remove um plugin carregado."""
        self._plugins.pop(name, None)

# Singleton
plugin_manager = PluginManager()

def descobrir_e_registrar():
    """Entry point para descoberta automática de plugins."""
    return plugin_manager.discover()
