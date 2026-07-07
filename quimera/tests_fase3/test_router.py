"""
Testes do ModelRouter — Cobre timeout, retry, circuit breaker e fallback.
"""
import sys
import os
import asyncio
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


class TestCircuitBreaker:
    """Testes do Circuit Breaker pattern."""
    
    def test_initial_state(self):
        from quimera.core.model_router import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)
        assert not cb.is_open("test_provider")
    
    def test_opens_after_threshold(self):
        from quimera.core.model_router import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)
        
        for _ in range(3):
            cb.record_failure("test_provider")
        
        assert cb.is_open("test_provider")
    
    def test_does_not_open_before_threshold(self):
        from quimera.core.model_router import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)
        
        for _ in range(4):
            cb.record_failure("test_provider")
        
        assert not cb.is_open("test_provider")
    
    def test_success_resets_failures(self):
        from quimera.core.model_router import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)
        
        for _ in range(2):
            cb.record_failure("test_provider")
        
        cb.record_success("test_provider")
        assert not cb.is_open("test_provider")
    
    def test_recovery_timeout(self):
        import time
        from quimera.core.model_router import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        for _ in range(2):
            cb.record_failure("test_provider")
        
        assert cb.is_open("test_provider")
        
        time.sleep(0.15)
        assert not cb.is_open("test_provider")


class TestModelRouter:
    """Testes do ModelRouter com resiliência."""
    
    def test_router_initialization(self):
        from quimera.core.model_router import ModelRouter
        router = ModelRouter()
        
        assert router.timeout == 30.0
        assert router.max_retries == 3
        assert router.circuit_breaker is not None
    
    def test_router_custom_config(self):
        from quimera.core.model_router import ModelRouter
        router = ModelRouter(timeout=10.0, max_retries=5)
        
        assert router.timeout == 10.0
        assert router.max_retries == 5
    
    @pytest.mark.asyncio
    async def test_router_deterministic_fallback(self):
        """Sem providers configurados, deve retornar fallback determinístico."""
        from quimera.core.model_router import ModelRouter
        
        router = ModelRouter(timeout=1.0, max_retries=1)
        result = await router.route_request(
            [{"role": "user", "content": "test"}],
            task_type="test"
        )
        
        assert "[Deterministic]" in result
    
    @pytest.mark.asyncio
    async def test_router_handles_timeout(self):
        """Timeout não deve crashar o router."""
        from quimera.core.model_router import ModelRouter
        
        router = ModelRouter(timeout=0.001, max_retries=1)
        result = await router.route_request(
            [{"role": "user", "content": "test"}],
            task_type="test",
            timeout=0.001,
            retries=1,
        )
        
        assert result is not None
        assert isinstance(result, str)
    
    def test_get_best_model(self):
        from quimera.core.model_router import ModelRouter
        import asyncio
        
        router = ModelRouter()
        model = asyncio.run(router.get_best_model("test"))
        assert model is not None
        assert isinstance(model, str)
    
    def test_get_stats_initial(self):
        from quimera.core.model_router import ModelRouter
        
        router = ModelRouter()
        stats = router.get_stats()
        
        assert 'router' in stats
        assert 'timeout' in stats
        assert 'max_retries' in stats
    
    def test_reset_circuits(self):
        from quimera.core.model_router import ModelRouter
        
        router = ModelRouter()
        router.circuit_breaker.record_failure("test")
        router.circuit_breaker.record_failure("test")
        # Force open
        router.circuit_breaker._open_circuits.add("test")
        
        router.reset_circuits()
        assert len(router.circuit_breaker._open_circuits) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
