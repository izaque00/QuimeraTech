"""
Modulo core do Quimera - Componentes fundamentais do sistema.

Contem:
- plugin_framework: Sistema de plugins extensivel
- retrieval_engine: Motor de busca RAG com Strategy Pattern
- knowledge_base: Base de conhecimento com RAG
- llm_kernel: Motor de consulta LLM
- model_router: Roteador de modelos (StubRetrievalStrategy = alias legacy)
- kan_engine: Motor de avaliacao simbolica KAN
"""

from quimera.core.plugin_framework import (
    BasePlugin,
    PluginInfo,
    PluginManager,
    PluginRegistry,
    PluginStatus,
    PluginHook,
)
from quimera.core.retrieval_engine import (
    RetrievalEngine,
    RetrievalStrategy,
    StubRetrievalStrategy,
    InMemoryRetrievalStrategy,
)

__all__ = [
    "BasePlugin",
    "PluginInfo",
    "PluginManager",
    "PluginRegistry",
    "PluginStatus",
    "PluginHook",
    "RetrievalEngine",
    "RetrievalStrategy",
    "StubRetrievalStrategy",
    "InMemoryRetrievalStrategy",
]
