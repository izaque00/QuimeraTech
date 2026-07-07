"""
Motor de Recuperação Unificado com Strategy Pattern.

Permite trocar dinamicamente a estratégia de busca RAG
sem modificar o código cliente. Suporta:
- Vector-based retrieval (FAISS, Chroma, etc.)
- Keyword-based retrieval (BM25, TF-IDF)
- Hybrid retrieval (combinação de ambos)
"""

from typing import Protocol, List, Dict, Any, Optional, runtime_checkable
import logging

logger = logging.getLogger(__name__)


@runtime_checkable
class RetrievalStrategy(Protocol):
    """Protocolo para estratégias de recuperação.
    
    Qualquer classe que implemente search() e add_documents()
    pode ser usada como estratégia, sem herança explícita.
    """

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Executa busca nos documentos indexados.
        
        Args:
            query: Texto da consulta.
            top_k: Número máximo de resultados.
        
        Returns:
            Lista de documentos relevantes com metadados.
        """
        ...

    def add_documents(self, documents: List[str]) -> None:
        """Adiciona documentos ao índice.
        
        Args:
            documents: Lista de textos a serem indexados.
        """
        ...


class RetrievalEngine:
    """Motor de recuperação unificado com estratégia plugável.
    
    Example:
        >>> from quimera.core.retrieval_engine import RetrievalEngine, ChromaStrategy
        >>> engine = RetrievalEngine(ChromaStrategy())
        >>> engine.add_documents(["doc1", "doc2"])
        >>> results = engine.search("query", top_k=3)
        >>> 
        >>> # Troca de estratégia em runtime
        >>> engine.strategy = FaissStrategy()
    """

    def __init__(self, strategy: RetrievalStrategy):
        """Inicializa o motor com uma estratégia.
        
        Args:
            strategy: Implementação de RetrievalStrategy.
        """
        self._strategy = strategy
        logger.info(f"RetrievalEngine inicializado com estratégia: {type(strategy).__name__}")

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Executa busca usando a estratégia atual.
        
        Args:
            query: Texto da consulta.
            top_k: Número máximo de resultados.
        
        Returns:
            Lista de documentos relevantes com metadados.
        """
        return self._strategy.search(query, top_k)

    def add_documents(self, documents: List[str]) -> None:
        """Adiciona documentos via estratégia atual.
        
        Args:
            documents: Lista de textos a serem indexados.
        """
        self._strategy.add_documents(documents)

    @property
    def strategy(self) -> RetrievalStrategy:
        """Retorna a estratégia atual."""
        return self._strategy

    @strategy.setter
    def strategy(self, new_strategy: RetrievalStrategy):
        """Altera a estratégia em runtime.
        
        Args:
            new_strategy: Nova implementação de RetrievalStrategy.
        """
        old_name = type(self._strategy).__name__
        self._strategy = new_strategy
        new_name = type(new_strategy).__name__
        logger.info(f"Estratégia de retrieval alterada: {old_name} -> {new_name}")

    def get_strategy_name(self) -> str:
        """Retorna o nome da estratégia atual.
        
        Returns:
            Nome da classe da estratégia ativa.
        """
        return type(self._strategy).__name__


# --- Estratégias de exemplo / base ---

class LocalRetrievalStrategy:
    def __init__(self, index_path=None):
        from quimera.memory.integration import MemoryPipeline
        self.memory = MemoryPipeline(db_path=index_path)
    def retrieve(self, query, top_k=5):
        import asyncio
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self.memory.retrieve_solutions(error_description=query, top_k=top_k))
        return result.solutions

class InMemoryRetrievalStrategy:
    """In-memory fallback when SQLite is unavailable."""
    def __init__(self): self._docs = []
    def search(self, query, top_k=5): return self._docs[:top_k]
    def add_documents(self, docs): self._docs.extend(docs)

StubRetrievalStrategy = LocalRetrievalStrategy  # Legacy alias
