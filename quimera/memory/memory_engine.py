# quimera/memory/memory_engine.py
"""
Memory Engine — Motor de memória de longo prazo com cache LRU.

Integra VectorStore com cache LRU, persistência em disco,
e pipeline de Retrieval-Augmented Repair (RAR).

RAR Pipeline:
    1. Recebe novo erro
    2. Gera embedding do erro
    3. Busca top-K missões similares na VectorStore
    4. Recupera soluções que funcionaram
    5. Adapta solução ao contexto atual
    6. Valida em sandbox
    7. Aplica patch

Uso:
    from quimera.memory.memory_engine import MemoryEngine
    from quimera.memory.vector_store import VectorStore, InMemoryBackend
    
    store = VectorStore(InMemoryBackend(dim=384))
    engine = MemoryEngine(store)
    
    # Buscar soluções similares
    candidates = engine.retrieve_solutions(error_text, error_type="compilation")
    
    # Registrar após missão
    engine.record_mission(mission_id, error, solution, success=True)
"""

import json
import logging
import os
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from quimera.memory.vector_store import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class LRUEntry:
    """Entrada no cache LRU."""
    key: str
    value: Any
    timestamp: float = field(default_factory=time.time)
    hits: int = 0


class LRUCache:
    """Cache LRU (Least Recently Used) com limite de tamanho."""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: OrderedDict = OrderedDict()
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            self._cache.move_to_end(key)
            entry = self._cache[key]
            entry.hits += 1
            self._hits += 1
            return entry.value
        self._misses += 1
        return None
    
    def put(self, key: str, value: Any):
        if key in self._cache:
            self._cache.move_to_end(key)
            self._cache[key].value = value
            self._cache[key].timestamp = time.time()
        else:
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
            self._cache[key] = LRUEntry(key=key, value=value)
    
    def stats(self) -> Dict:
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{self._hits/max(total,1):.1%}",
        }


@dataclass
class SolutionCandidate:
    """Candidato de solução encontrado pela memória."""
    mission_id: str
    similarity_score: float
    error_type: str
    solution_type: str
    solution_description: str
    fitness_score: float
    adapted_solution: Optional[str] = None


class MemoryEngine:
    """Motor de memória de longo prazo.
    
    Combina:
    - VectorStore para armazenamento semântico
    - LRU Cache para resultados frequentes
    - Retrieval-Augmented Repair (RAR)
    - Persistência em disco (JSON)
    """
    
    def __init__(
        self,
        vector_store: Optional["VectorStore"] = None,
        cache_size: int = 1000,
        persistence_path: Optional[str] = None,
        solution_adapter: Optional[Callable] = None,
    ):
        if vector_store is None:
            from quimera.memory.vector_store import VectorStore, InMemoryBackend
            vector_store = VectorStore(InMemoryBackend(dim=384))
        self.store = vector_store
        self.cache = LRUCache(max_size=cache_size)
        self.persistence_path = persistence_path
        self.solution_adapter = solution_adapter
        self._total_retrievals = 0
        self._total_hits = 0
        
        # Carrega do disco se existir
        if persistence_path and os.path.exists(persistence_path):
            self._load()
        
        logger.info(f"MemoryEngine: cache={cache_size}, path={persistence_path}")
    
    def retrieve_solutions(
        self,
        error_description: str,
        error_type: str = None,
        kernel_arch: str = None,
        k: int = 5,
        min_similarity: float = 0.3,
    ) -> List[SolutionCandidate]:
        """Recupera soluções similares da memória (RAR).
        
        Args:
            error_description: Texto descritivo do erro.
            error_type: Tipo do erro.
            kernel_arch: Arquitetura do kernel.
            k: Número máximo de candidatos.
            min_similarity: Score mínimo de similaridade.
            
        Returns:
            Lista de SolutionCandidate ordenados por similaridade.
        """
        self._total_retrievals += 1
        
        # 1. Verifica cache LRU
        cache_key = f"{error_type}:{error_description[:100]}"
        cached = self.cache.get(cache_key)
        if cached:
            self._total_hits += 1
            logger.debug(f"MemoryEngine: cache hit ({self.cache.stats()['hit_rate']})")
            return cached
        
        # 2. Busca na VectorStore
        similar = self.store.find_similar(
            error_description=error_description,
            error_type=error_type,
            kernel_arch=kernel_arch,
            k=k * 2,
            only_successful=True,
        )
        
        # 3. Filtra por similaridade mínima
        candidates = []
        for s in similar:
            if s["similarity_score"] < min_similarity:
                continue
            candidates.append(SolutionCandidate(
                mission_id=s["mission_id"],
                similarity_score=s["similarity_score"],
                error_type=s["error_type"],
                solution_type=s["solution_type"],
                solution_description=s["solution_snippet"],
                fitness_score=s["fitness_score"],
            ))
        
        # 4. Ordena por score composto (similarity * fitness)
        candidates.sort(
            key=lambda c: c.similarity_score * (0.5 + 0.5 * c.fitness_score),
            reverse=True,
        )
        candidates = candidates[:k]
        
        # 5. Adapta soluções se houver adapter
        if self.solution_adapter and candidates:
            for c in candidates:
                try:
                    c.adapted_solution = self.solution_adapter(
                        c.solution_description, error_description
                    )
                except Exception as e:
                    logger.debug(f"MemoryEngine: adapter falhou para {c.mission_id}: {e}")
        
        # 6. Armazena no cache
        self.cache.put(cache_key, candidates)
        
        if candidates:
            logger.info(
                f"MemoryEngine: {len(candidates)} soluções recuperadas "
                f"(top similarity={candidates[0].similarity_score:.3f})"
            )
        else:
            logger.info(f"MemoryEngine: nenhuma solução similar encontrada (min_sim={min_similarity})")
        
        return candidates
    
    def record_mission(
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
    ):
        """Registra uma missão na memória de longo prazo.
        
        Chamado após cada missão concluída (sucesso ou falha).
        """
        self.store.add_mission(
            mission_id=mission_id,
            error_description=error_description,
            solution_description=solution_description,
            error_type=error_type,
            solution_type=solution_type,
            kernel_arch=kernel_arch,
            success=success,
            fitness_score=fitness_score,
            extra_metadata=extra_metadata,
        )
        
        # Invalida cache relacionado
        cache_key = f"{error_type}:{error_description[:100]}"
        self.cache.put(cache_key, None)  # força re-busca
        
        # Persiste periodicamente
        if self.persistence_path and self.store.backend.count() % 10 == 0:
            self._save()
        
        logger.info(
            f"MemoryEngine: missão '{mission_id}' registrada "
            f"(success={success}, fitness={fitness_score:.3f})"
        )
    
    def get_solution_stats(self) -> Dict[str, Any]:
        """Estatísticas de soluções armazenadas."""
        return {
            **self.store.get_stats(),
            "cache": self.cache.stats(),
            "total_retrievals": self._total_retrievals,
            "total_hits": self._total_hits,
            "retrieval_hit_rate": f"{self._total_hits/max(self._total_retrievals,1):.1%}",
        }
    
    def suggest_solution(self, candidates: List[SolutionCandidate]) -> Optional[str]:
        """Sugere a melhor solução dos candidatos.
        
        Heurística:
        - 3+ candidatos similares com score > 0.7 → alta confiança
        - 2 candidatos com score > 0.5 → confiança média
        - 1 candidato com score > 0.3 → baixa confiança (melhor que nada)
        - 0 candidatos → sem sugestão
        """
        if not candidates:
            return None
        
        high_confidence = [c for c in candidates if c.similarity_score > 0.7]
        if len(high_confidence) >= 3:
            return f"[ALTA CONFIANÇA] {high_confidence[0].solution_description}"
        
        med_confidence = [c for c in candidates if c.similarity_score > 0.5]
        if len(med_confidence) >= 2:
            return f"[MÉDIA CONFIANÇA] {med_confidence[0].solution_description}"
        
        if candidates[0].similarity_score > 0.3:
            return f"[BAIXA CONFIANÇA] {candidates[0].solution_description}"
        
        return None
    
    def _save(self):
        """Persiste metadados em disco."""
        if not self.persistence_path:
            return
        try:
            data = {
                "total_retrievals": self._total_retrievals,
                "total_hits": self._total_hits,
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "backend_count": self.store.backend.count(),
            }
            Path(self.persistence_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.persistence_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"MemoryEngine: erro ao salvar: {e}")
    
    def _load(self):
        """Carrega metadados do disco."""
        try:
            with open(self.persistence_path) as f:
                data = json.load(f)
            self._total_retrievals = data.get("total_retrievals", 0)
            self._total_hits = data.get("total_hits", 0)
            logger.info(f"MemoryEngine: carregado do disco ({self._total_retrievals} retrievals)")
        except Exception as e:
            logger.warning(f"MemoryEngine: erro ao carregar: {e}")
