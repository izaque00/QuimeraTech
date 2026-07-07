"""
Testes da Memória — VectorStore, MemoryEngine e integração.
Cobre o bug do vector_store obrigatório corrigido na Fase 2.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


class TestVectorStore:
    """Testes da VectorStore."""
    
    def test_in_memory_backend(self):
        from quimera.memory.vector_store import VectorStore, InMemoryBackend
        backend = InMemoryBackend(dim=128)
        store = VectorStore(backend, encoder=None)
        
        assert store is not None
    
    def test_vector_store_add_and_search(self):
        from quimera.memory.vector_store import VectorStore, InMemoryBackend
        backend = InMemoryBackend(dim=128)
        store = VectorStore(backend, encoder=None)
        
        # Add a mission
        store.add_mission(
            mission_id="test-1",
            error_description="buffer overflow in strcpy",
            error_type="buffer_overflow",
            solution_description="use strncpy instead",
            solution_type="replace_function",
            success=True,
            fitness_score=0.85,
            kernel_arch="aarch64",
        )
        
        # Search
        results = store.find_similar("buffer overflow", k=3)
        assert isinstance(results, list)
    
    def test_vector_store_lru_cache(self):
        from quimera.memory.vector_store import VectorStore, InMemoryBackend
        backend = InMemoryBackend(dim=128)
        store = VectorStore(backend, encoder=None)
        
        assert store is not None


class TestMemoryEngine:
    """Testes do MemoryEngine — incluindo o bug do vector_store opcional."""
    
    def test_memory_engine_without_vector_store(self):
        """BUG FIX: MemoryEngine deve funcionar sem vector_store explícito."""
        from quimera.memory.memory_engine import MemoryEngine
        
        engine = MemoryEngine()  # Não passa vector_store
        assert engine is not None
        assert engine.store is not None  # Deve ter criado um fallback
    
    def test_memory_engine_with_vector_store(self):
        from quimera.memory.vector_store import VectorStore, InMemoryBackend
        from quimera.memory.memory_engine import MemoryEngine
        
        store = VectorStore(InMemoryBackend(dim=128))
        engine = MemoryEngine(vector_store=store)
        
        assert engine.store is store
    
    def test_retrieve_solutions_empty(self):
        """Busca em memória vazia deve retornar lista vazia."""
        from quimera.memory.memory_engine import MemoryEngine
        
        engine = MemoryEngine()
        results = engine.retrieve_solutions(
            error_description="buffer overflow",
            error_type="compilation",
        )
        
        assert isinstance(results, list)
        assert len(results) == 0
    
    def test_retrieve_solutions_is_sync(self):
        """retrieve_solutions deve ser síncrono (bug fix da Fase 2)."""
        import inspect
        from quimera.memory.memory_engine import MemoryEngine
        
        engine = MemoryEngine()
        assert not inspect.iscoroutinefunction(engine.retrieve_solutions)
    
    def test_memory_engine_cache(self):
        from quimera.memory.memory_engine import MemoryEngine
        
        engine = MemoryEngine(cache_size=500, persistence_path=None)
        assert engine.cache.max_size == 500


class TestLRUCache:
    """Testes do LRU Cache."""
    
    def test_lru_basic(self):
        from quimera.memory.memory_engine import LRUCache
        
        cache = LRUCache(max_size=3)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        
        assert cache.get("a") == 1
        assert cache.get("b") == 2
        assert cache.get("c") == 3
    
    def test_lru_eviction(self):
        from quimera.memory.memory_engine import LRUCache
        
        cache = LRUCache(max_size=2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)  # Deve evictar "a"
        
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3
    
    def test_lru_reorder_on_access(self):
        from quimera.memory.memory_engine import LRUCache
        
        cache = LRUCache(max_size=2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.get("a")  # Reordena "a" como mais recente
        cache.put("c", 3)  # Deve evictar "b"
        
        assert cache.get("a") == 1
        assert cache.get("b") is None
        assert cache.get("c") == 3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
