#!/usr/bin/env python3
"""
Framework de Plugins Ultra-Avançado para Agente Fiscal de Código
Sistema de plugins extensível com descoberta automática, gerenciamento de dependências
e ciclo de vida completo dos plugins.
"""

import abc
import asyncio
import importlib
import inspect
import json
import logging
import os
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type, Union, Callable
import uuid
from datetime import datetime
import weakref


class PluginStatus(Enum):
    """Status do plugin"""
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    ACTIVE = "active"
    ERROR = "error"
    DISABLED = "disabled"


class PluginPriority(Enum):
    """Prioridade de execução do plugin"""
    CRITICAL = 1000
    HIGH = 750
    NORMAL = 500
    LOW = 250
    BACKGROUND = 100


@dataclass
class PluginInfo:
    """Informações do plugin"""
    name: str
    version: str
    description: str
    author: str
    priority: PluginPriority = PluginPriority.NORMAL
    dependencies: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    requires_config: bool = False
    async_support: bool = False
    production_ready: bool = True
    tags: List[str] = field(default_factory=list)


@dataclass
class PluginMetrics:
    """Métricas de execução do plugin"""
    execution_count: int = 0
    total_execution_time: float = 0.0
    last_execution: Optional[datetime] = None
    error_count: int = 0
    last_error: Optional[str] = None
    average_execution_time: float = 0.0


class PluginHook:
    """Sistema de hooks para plugins"""

    def __init__(self):
        self._hooks: Dict[str, List[Callable]] = {}
        self._lock = threading.RLock()

    def register(self, event: str, callback: Callable):
        """Registra callback para evento"""
        with self._lock:
            if event not in self._hooks:
                self._hooks[event] = []
            self._hooks[event].append(callback)

    def unregister(self, event: str, callback: Callable):
        """Remove callback do evento"""
        with self._lock:
            if event in self._hooks:
                try:
                    self._hooks[event].remove(callback)
                except ValueError:
                    pass

    async def emit(self, event: str, *args, **kwargs):
        """Emite evento para todos os callbacks"""
        callbacks = []
        with self._lock:
            if event in self._hooks:
                callbacks = self._hooks[event].copy()

        for callback in callbacks:
            try:
                if inspect.iscoroutinefunction(callback):
                    await callback(*args, **kwargs)
                else:
                    callback(*args, **kwargs)
            except Exception as e:
                logging.error(f"Erro em hook {event}: {e}")


class BasePlugin(abc.ABC):
    """Classe base para todos os plugins"""

    def __init__(self, manager: 'PluginManager'):
        self.manager = manager
        self.hooks = manager.hooks
        self.logger = logging.getLogger(f"plugin.{self.__class__.__name__}")
        self.config = {}
        self.metrics = PluginMetrics()
        self._active = False
        self._id = str(uuid.uuid4())

    @property
    @abc.abstractmethod
    def info(self) -> PluginInfo:
        """Informações do plugin"""
        pass

    @abc.abstractmethod
    async def initialize(self) -> bool:
        """Inicializa o plugin"""
        pass

    @abc.abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Executa a funcionalidade principal do plugin"""
        pass

    async def configure(self, config: Dict[str, Any]):
        """Configura o plugin"""
        self.config = config

    async def cleanup(self):
        """Limpeza antes de descarregar o plugin"""
        pass

    def is_active(self) -> bool:
        """Verifica se plugin está ativo"""
        return self._active

    def activate(self):
        """Ativa o plugin"""
        self._active = True

    def deactivate(self):
        """Desativa o plugin"""
        self._active = False

    async def health_check(self) -> Dict[str, Any]:
        """Verifica saúde do plugin"""
        return {
            "status": "healthy",
            "active": self._active,
            "metrics": {
                "executions": self.metrics.execution_count,
                "errors": self.metrics.error_count,
                "avg_time": self.metrics.average_execution_time
            }
        }


class PluginManager:
    """Gerenciador de plugins avançado"""

    def __init__(self, plugin_dirs: List[str] = None):
        self.plugins: Dict[str, BasePlugin] = {}
        self.plugin_status: Dict[str, PluginStatus] = {}
        self.plugin_dirs = plugin_dirs or []
        self.hooks = PluginHook()
        self.logger = logging.getLogger("PluginManager")
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=10)
        self._dependency_graph: Dict[str, Set[str]] = {}
        self._config_cache: Dict[str, Dict] = {}

    def add_plugin_directory(self, path: str):
        """Adiciona diretório de plugins"""
        plugin_path = Path(path)
        if plugin_path.exists() and plugin_path.is_dir():
            self.plugin_dirs.append(str(plugin_path))
            if str(plugin_path) not in sys.path:
                sys.path.insert(0, str(plugin_path))

    async def discover_plugins(self) -> List[str]:
        """Descobre plugins automaticamente"""
        discovered = []

        for plugin_dir in self.plugin_dirs:
            plugin_path = Path(plugin_dir)
            if not plugin_path.exists():
                continue

            # Procura por arquivos Python
            for py_file in plugin_path.rglob("*.py"):
                if py_file.name.startswith("__"):
                    continue

                try:
                    # Carrega módulo dinamicamente
                    spec = importlib.util.spec_from_file_location(
                        py_file.stem, py_file
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)

                        # Procura por classes que herdam de BasePlugin
                        for name, obj in inspect.getmembers(module):
                            if (inspect.isclass(obj) and
                                issubclass(obj, BasePlugin) and
                                obj != BasePlugin):
                                discovered.append(f"{module.__name__}.{name}")

                except Exception as e:
                    self.logger.warning(f"Erro ao descobrir plugin {py_file}: {e}")

        return discovered

    async def load_plugin(self, plugin_class: str) -> bool:
        """Carrega plugin específico"""
        try:
            with self._lock:
                if plugin_class in self.plugins:
                    return True

                self.plugin_status[plugin_class] = PluginStatus.LOADING

            # Importa e instancia plugin
            module_name, class_name = plugin_class.rsplit(".", 1)
            module = importlib.import_module(module_name)
            plugin_cls = getattr(module, class_name)

            plugin_instance = plugin_cls(self)

            # Verifica dependências
            if not await self._check_dependencies(plugin_instance):
                self.plugin_status[plugin_class] = PluginStatus.ERROR
                return False

            # Carrega configuração
            await self._load_plugin_config(plugin_instance)

            # Inicializa plugin
            if await plugin_instance.initialize():
                with self._lock:
                    self.plugins[plugin_class] = plugin_instance
                    self.plugin_status[plugin_class] = PluginStatus.LOADED
                    plugin_instance.activate()

                await self.hooks.emit("plugin_loaded", plugin_instance)
                self.logger.info(f"Plugin {plugin_class} carregado com sucesso")
                return True
            else:
                self.plugin_status[plugin_class] = PluginStatus.ERROR
                return False

        except Exception as e:
            self.plugin_status[plugin_class] = PluginStatus.ERROR
            self.logger.error(f"Erro ao carregar plugin {plugin_class}: {e}")
            return False

    async def unload_plugin(self, plugin_name: str) -> bool:
        """Descarrega plugin"""
        try:
            with self._lock:
                if plugin_name not in self.plugins:
                    return False

                plugin = self.plugins[plugin_name]
                plugin.deactivate()
                await plugin.cleanup()

                del self.plugins[plugin_name]
                self.plugin_status[plugin_name] = PluginStatus.UNLOADED

            await self.hooks.emit("plugin_unloaded", plugin_name)
            self.logger.info(f"Plugin {plugin_name} descarregado")
            return True

        except Exception as e:
            self.logger.error(f"Erro ao descarregar plugin {plugin_name}: {e}")
            return False

    def _execute_plugin_sync(self, plugin, context):
        """Executa plugin de forma síncroma, detectando event loop aninhado."""
        if plugin.info.async_support:
            try:
                loop = asyncio.get_running_loop()
                # Já em contexto async — não podemos usar asyncio.run
                # Devemos usar create_task ou executar de outra forma
                raise RuntimeError(
                    "Plugin async não pode ser executado via executor "
                    "quando já há um event loop rodando. "
                    "Use execute_plugins() diretamente."
                )
            except RuntimeError:
                # Nenhum event loop rodando — podemos usar asyncio.run
                return asyncio.run(plugin.execute(context))
        else:
            return plugin.execute_sync(context)

    async def execute_plugins(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Executa todos os plugins ativos"""
        results = {}

        # Ordena plugins por prioridade
        active_plugins = [
            (name, plugin) for name, plugin in self.plugins.items()
            if plugin.is_active()
        ]
        active_plugins.sort(key=lambda x: x[1].info.priority.value, reverse=True)

        for plugin_name, plugin in active_plugins:
            try:
                start_time = time.time()

                # Executa plugin
                if plugin.info.async_support:
                    result = await plugin.execute(context)
                else:
                    result = await asyncio.get_event_loop().run_in_executor(
                        self._executor,
                        lambda: self._execute_plugin_sync(plugin, context)
                    )

                # Atualiza métricas
                execution_time = time.time() - start_time
                plugin.metrics.execution_count += 1
                plugin.metrics.total_execution_time += execution_time
                plugin.metrics.last_execution = datetime.now()
                plugin.metrics.average_execution_time = (
                    plugin.metrics.total_execution_time / plugin.metrics.execution_count
                )

                results[plugin_name] = result

            except Exception as e:
                plugin.metrics.error_count += 1
                plugin.metrics.last_error = str(e)

                self.logger.error(f"Erro ao executar plugin {plugin_name}: {e}")
                results[plugin_name] = {"error": str(e)}

        return results

    async def get_plugin_status(self) -> Dict[str, Any]:
        """Retorna status de todos os plugins"""
        status = {}

        for name, plugin in self.plugins.items():
            health = await plugin.health_check()
            status[name] = {
                "status": self.plugin_status.get(name, PluginStatus.UNLOADED).value,
                "info": plugin.info.__dict__,
                "health": health,
                "metrics": plugin.metrics.__dict__
            }

        return status

    async def reload_plugin(self, plugin_name: str) -> bool:
        """Recarrega plugin"""
        if await self.unload_plugin(plugin_name):
            return await self.load_plugin(plugin_name)
        return False

    async def _check_dependencies(self, plugin: BasePlugin) -> bool:
        """Verifica dependências do plugin"""
        for dep in plugin.info.dependencies:
            if dep not in self.plugins:
                self.logger.error(f"Dependência não encontrada: {dep}")
                return False

        for conflict in plugin.info.conflicts:
            if conflict in self.plugins:
                self.logger.error(f"Conflito detectado com plugin: {conflict}")
                return False

        return True

    async def _load_plugin_config(self, plugin: BasePlugin):
        """Carrega configuração do plugin"""
        if not plugin.info.requires_config:
            return

        config_path = Path(f"configs/plugins/{plugin.__class__.__name__.lower()}.json")
        if config_path.exists():
            try:
                with open(config_path) as f:
                    config = json.load(f)
                await plugin.configure(config)
            except Exception as e:
                self.logger.warning(f"Erro ao carregar config para {plugin.__class__.__name__}: {e}")


class PluginRegistry:
    """Registro global de plugins"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._plugins: Dict[str, Type[BasePlugin]] = {}
            self._initialized = True

    def register(self, plugin_class: Type[BasePlugin]):
        """Registra classe de plugin"""
        name = f"{plugin_class.__module__}.{plugin_class.__name__}"
        self._plugins[name] = plugin_class

    def get_all(self) -> Dict[str, Type[BasePlugin]]:
        """Retorna todos os plugins registrados"""
        return self._plugins.copy()

    def get(self, name: str) -> Optional[Type[BasePlugin]]:
        """Retorna plugin específico"""
        return self._plugins.get(name)


def plugin_decorator(
    name: str,
    version: str,
    description: str,
    author: str,
    **kwargs
):
    """Decorator para registrar plugins automaticamente"""
    def decorator(cls):
        # Adiciona informações ao plugin
        if not hasattr(cls, '_plugin_info'):
            cls._plugin_info = PluginInfo(
                name=name,
                version=version,
                description=description,
                author=author,
                **kwargs
            )

        # Registra no registry
        registry = PluginRegistry()
        registry.register(cls)

        return cls

    return decorator


# Sistema de eventos para plugins
class PluginEventBus:
    """Bus de eventos para comunicação entre plugins"""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = threading.RLock()

    def subscribe(self, event: str, callback: Callable):
        """Inscreve callback em evento"""
        with self._lock:
            if event not in self._subscribers:
                self._subscribers[event] = []
            self._subscribers[event].append(callback)

    def unsubscribe(self, event: str, callback: Callable):
        """Remove inscrição"""
        with self._lock:
            if event in self._subscribers:
                try:
                    self._subscribers[event].remove(callback)
                except ValueError:
                    pass

    async def publish(self, event: str, data: Any):
        """Publica evento"""
        subscribers = []
        with self._lock:
            if event in self._subscribers:
                subscribers = self._subscribers[event].copy()

        for callback in subscribers:
            try:
                if inspect.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logging.error(f"Erro em subscriber para {event}: {e}")


# Instância global do event bus
global_event_bus = PluginEventBus()