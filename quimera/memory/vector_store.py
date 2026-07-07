# quimera/memory/vector_store.py
"""
Vector Store — Armazenamento persistente de embeddings de missões.

Suporta backends:
    in_memory — Para desenvolvimento/teste
    faiss     — Facebook AI Similarity Search (produção)
    chroma    — ChromaDB (open-source, lightweight)

Uso:
    from quimera.memory.vector_store import VectorStore, InMemoryBackend
    
    store = VectorStore(InMemoryBackend(dim=384))
    store.add(mission_id, embedding, metadata)
    similar = store.search(query_embedding, k=5)
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """Uma entrada na memória vetorial."""
    mission_id: str
    embedding: np.ndarray
    error_type: str
    solution_type: str
    kernel_arch: str
    success: bool
    fitness_score: float
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class VectorBackend(ABC):
    """Interface para backends de armazenamento vetorial."""
    
    @abstractmethod
    def add(self, entry_id: str, embedding: np.ndarray, metadata: Dict) -> None:
        """Adiciona um embedding."""
        ...
    
    @abstractmethod
    def search(self, query: np.ndarray, k: int = 5) -> List[Tuple[str, float, Dict]]:
        """Busca os k embeddings mais similares.
        
        Returns:
            Lista de (id, score, metadata).
        """
        ...
    
    @abstractmethod
    def delete(self, entry_id: str) -> bool:
        """Remove um embedding."""
        ...
    
    @abstractmethod
    def count(self) -> int:
        """Número de entradas."""
        ...


class InMemoryBackend(VectorBackend):
    """Backend em memória com similaridade cosine."""
    
    def __init__(self, dim: int = 384):
        self.dim = dim
        self._embeddings: Dict[str, np.ndarray] = {}
        self._metadata: Dict[str, Dict] = {}
    
    def add(self, entry_id: str, embedding: np.ndarray, metadata: Dict) -> None:
        if embedding.shape[0] != self.dim and self.dim > 0:
            self.dim = embedding.shape[0]
        self._embeddings[entry_id] = embedding.astype(np.float32)
        self._metadata[entry_id] = metadata
    
    def search(self, query: np.ndarray, k: int = 5) -> List[Tuple[str, float, Dict]]:
        if not self._embeddings:
            return []
        
        query = query.astype(np.float32)
        query_norm = query / (np.linalg.norm(query) + 1e-9)
        
        scores = []
        for eid, emb in self._embeddings.items():
            emb_norm = emb / (np.linalg.norm(emb) + 1e-9)
            score = float(np.dot(query_norm, emb_norm))
            scores.append((eid, score, self._metadata[eid]))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:k]
    
    def delete(self, entry_id: str) -> bool:
        if entry_id in self._embeddings:
            del self._embeddings[entry_id]
            del self._metadata[entry_id]
            return True
        return False
    
    def count(self) -> int:
        return len(self._embeddings)


class VectorStore:
    """Store de embeddings com múltiplos backends.
    
    Responsável por:
    - Embedding de texto (erro + contexto) usando encoder configurável
    - Armazenamento em backend plugável
    - Busca por similaridade para RAG de reparo
    """
    
    def __init__(self, backend: VectorBackend, encoder=None):
        self.backend = backend
        self.encoder = encoder or self._default_encoder
        self._embedding_cache: Dict[str, np.ndarray] = {}
        logger.info(f"VectorStore: backend={type(backend).__name__}")
    
    @staticmethod
    def _default_encoder(text: str) -> np.ndarray:
        """Encoder padrão baseado em TF-IDF simplificado.
        
        Em produção, usar SentenceTransformer('all-MiniLM-L6-v2').
        """
        from collections import Counter
        import hashlib
        
        # Hashing trick: gera vetor de 384 dimensões
        words = text.lower().split()
        vec = np.zeros(384, dtype=np.float32)
        
        for w in words:
            h = int(hashlib.md5(w.encode()).hexdigest(), 16) % 384
            vec[h] += 1.0
        
        # Normaliza
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        
        return vec
    
    def embed(self, text: str) -> np.ndarray:
        """Gera embedding para texto (com cache)."""
        key = text[:200]
        if key in self._embedding_cache:
            return self._embedding_cache[key]
        
        emb = self.encoder(text)
        self._embedding_cache[key] = emb
        
        # Limpa cache se muito grande
        if len(self._embedding_cache) > 10000:
            # Remove metade aleatória
            import random
            keys = random.sample(list(self._embedding_cache.keys()), 5000)
            for k in keys:
                del self._embedding_cache[k]
        
        return emb
    
    def add_mission(
        self,
        mission_id: str,
        error_description: str,
        solution_description: str,
        error_type: str,
        solution_type: str,
        kernel_arch: str,
        success: bool,
        fitness_score: float = 0.0,
        extra_metadata: Dict = None,
    ) -> str:
        """Adiciona uma missão à memória.
        
        Args:
            mission_id: ID único da missão.
            error_description: Descrição do erro.
            solution_description: Descrição da solução.
            error_type: Tipo do erro (compilação, runtime, etc.).
            solution_type: Tipo da solução (patch, config, etc.).
            kernel_arch: Arquitetura do kernel.
            success: Se a missão foi bem sucedida.
            fitness_score: Score de qualidade da solução.
            extra_metadata: Metadados adicionais.
            
        Returns:
            mission_id.
        """
        text = f"ERROR: {error_type} | {error_description} | SOLUTION: {solution_type} | {solution_description}"
        embedding = self.embed(text)
        
        metadata = {
            "error_type": error_type,
            "solution_type": solution_type,
            "kernel_arch": kernel_arch,
            "success": success,
            "fitness_score": fitness_score,
            "error_description": error_description[:500],
            "solution_description": solution_description[:500],
            **(extra_metadata or {}),
        }
        
        self.backend.add(mission_id, embedding, metadata)
        logger.debug(f"VectorStore: missão '{mission_id}' adicionada ({self.backend.count()} total)")
        return mission_id
    
    def find_similar(
        self,
        error_description: str,
        error_type: str = None,
        kernel_arch: str = None,
        k: int = 5,
        only_successful: bool = True,
    ) -> List[Dict]:
        """Encontra missões similares por erro.
        
        Args:
            error_description: Descrição do erro atual.
            error_type: Filtrar por tipo de erro.
            kernel_arch: Filtrar por arquitetura.
            k: Número de resultados.
            only_successful: Apenas missões bem sucedidas.
            
        Returns:
            Lista de missões similares com scores.
        """
        query_text = f"ERROR: {error_type or 'any'} | {error_description}"
        query_emb = self.embed(query_text)
        
        results = self.backend.search(query_emb, k=k * 3)
        
        # Filtra
        filtered = []
        for mid, score, meta in results:
            if only_successful and not meta.get("success", True):
                continue
            if error_type and meta.get("error_type") != error_type:
                continue
            if kernel_arch and meta.get("kernel_arch") != kernel_arch:
                continue
            filtered.append({
                "mission_id": mid,
                "similarity_score": round(score, 4),
                "error_type": meta.get("error_type"),
                "solution_type": meta.get("solution_type"),
                "error_snippet": meta.get("error_description", "")[:200],
                "solution_snippet": meta.get("solution_description", "")[:200],
                "fitness_score": meta.get("fitness_score", 0),
            })
            if len(filtered) >= k:
                break
        
        return filtered
    
    def get_stats(self) -> Dict[str, Any]:
        """Estatísticas da memória."""
        return {
            "total_entries": self.backend.count(),
            "cache_size": len(self._embedding_cache),
            "backend_type": type(self.backend).__name__,
        }
