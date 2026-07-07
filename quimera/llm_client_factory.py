import os
"""
Factory para criação de clientes LLM.

Permite registro dinâmico de provedores e criação desacoplada
de clientes LLM com tratamento de importações opcionais.
"""

from typing import Dict, Callable, Optional, Any


class LLMClientFactory:
    """
    Factory para criar clientes LLM de diferentes provedores.

    Exemplo:
        factory = LLMClientFactory()
        factory.register("openai", lambda **kw: ChatOpenAI(**kw))
        client = factory.create("openai", model="gpt-4", api_key=os.getenv("OPENAI_API_KEY", ""))
    """

    _providers: Dict[str, Callable] = {}

    @classmethod
    def register(cls, name: str, constructor: Callable):
        """Registra um provedor LLM com sua função construtora."""
        cls._providers[name] = constructor

    @classmethod
    def create(cls, provider: str, **kwargs) -> Optional[Any]:
        """Cria um cliente LLM para o provedor especificado."""
        if provider in cls._providers:
            try:
                return cls._providers[provider](**kwargs)
            except ImportError as e:
                logger.debug(f"LLMClientFactory: dependência não instalada para '{provider}': {e}")
                return None
            except Exception as e:
                logger.debug(f"LLMClientFactory: falha ao criar '{provider}': {e}")
                return None
        return None

    @classmethod
    def available_providers(cls) -> list[str]:
        """Retorna a lista de provedores disponíveis (que podem ser instanciados)."""
        available = []
        for name, constructor in cls._providers.items():
            try:
                constructor()
                available.append(name)
            except Exception as e:
                logger.debug(f"LLMClientFactory: provider '{name}' indisponível: {e}")
        return available

    @classmethod
    def registered_providers(cls) -> list[str]:
        """Retorna a lista de todos os provedores registrados."""
        return list(cls._providers.keys())

    @classmethod
    def unregister(cls, name: str) -> bool:
        """Remove um provedor do registro."""
        if name in cls._providers:
            del cls._providers[name]
            return True
        return False
