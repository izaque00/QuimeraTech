"""Model Router — delegates to LLM Adviser's MultiProviderRouter (11 providers).
Includes resilience patterns: timeout, retry with backoff, circuit breaker, fallback chain.
"""
import asyncio
import logging
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("quimera.model_router")


class CircuitBreaker:
    """Circuit breaker pattern — prevents cascading failures."""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failures: Dict[str, int] = defaultdict(int)
        self._last_failure: Dict[str, float] = {}
        self._open_circuits: set = set()
    
    def record_failure(self, provider: str) -> None:
        self._failures[provider] += 1
        self._last_failure[provider] = time.time()
        if self._failures[provider] >= self.failure_threshold:
            self._open_circuits.add(provider)
            logger.warning(f"Circuit BREAKER OPEN for {provider} ({self._failures[provider]} failures)")
    
    def record_success(self, provider: str) -> None:
        self._failures[provider] = 0
        self._open_circuits.discard(provider)
    
    def is_open(self, provider: str) -> bool:
        if provider not in self._open_circuits:
            return False
        # Check recovery timeout
        last = self._last_failure.get(provider, 0)
        if time.time() - last > self.recovery_timeout:
            self._open_circuits.discard(provider)
            self._failures[provider] = 0
            logger.info(f"Circuit RESET for {provider} (recovery timeout)")
            return False
        return True


class ModelRouter:
    """Router with full resilience: timeout, retry, circuit breaker, fallback."""
    
    DEFAULT_TIMEOUT = 30.0  # seconds
    MAX_RETRIES = 3
    RETRY_DELAY_BASE = 1.0  # exponential backoff base
    
    def __init__(self, timeout: float = DEFAULT_TIMEOUT, max_retries: int = MAX_RETRIES):
        self._adviser = None
        self._init_done = False
        self.timeout = timeout
        self.max_retries = max_retries
        self.circuit_breaker = CircuitBreaker()
        self._stats: Dict[str, int] = defaultdict(int)
    
    async def _ensure_init(self):
        if self._init_done:
            return
        try:
            from quimera.mind.llm_adviser import MultiProviderRouter
            self._adviser = MultiProviderRouter()
            self._init_done = True
            logger.info("ModelRouter: MultiProviderRouter initialized")
        except ImportError:
            self._init_done = True
            logger.warning("ModelRouter: MultiProviderRouter not available — using deterministic fallback")
    
    async def route_request(
        self, messages, task_type: str = "general", 
        timeout: Optional[float] = None,
        retries: Optional[int] = None,
    ) -> str:
        """Route request with timeout, retry, and fallback."""
        await self._ensure_init()
        timeout = timeout or self.timeout
        retries = retries or self.max_retries
        
        if self._adviser:
            for attempt in range(retries):
                try:
                    result = await asyncio.wait_for(
                        self._adviser.route(messages, task_type),
                        timeout=timeout,
                    )
                    content = result.get("content", "")
                    provider = result.get("model", "unknown")
                    
                    if content and "Todos provedores esgotados" not in content:
                        self.circuit_breaker.record_success(provider)
                        self._stats["success"] += 1
                        return content
                    else:
                        self.circuit_breaker.record_failure(provider)
                        
                except asyncio.TimeoutError:
                    logger.warning(f"ModelRouter: timeout on attempt {attempt + 1}/{retries}")
                    self._stats["timeout"] += 1
                except Exception as e:
                    logger.warning(f"ModelRouter: error on attempt {attempt + 1}/{retries}: {e}")
                    self._stats["error"] += 1
                
                if attempt < retries - 1:
                    delay = self.RETRY_DELAY_BASE * (2 ** attempt)
                    await asyncio.sleep(delay)
        
        # Deterministic fallback
        self._stats["fallback"] += 1
        return f"[Deterministic] Processed {task_type}"
    
    async def get_best_model(self, task_type: str = "") -> str:
        """Get best available model, skipping circuits that are open."""
        await self._ensure_init()
        if self._adviser:
            provider_order = self._adviser.get_provider_order()
            for provider in provider_order:
                if not self.circuit_breaker.is_open(provider):
                    return provider
        return "ollama"
    
    def get_stats(self) -> Dict:
        """Get router statistics including resilience metrics."""
        if self._adviser:
            base_stats = self._adviser.get_stats()
        else:
            base_stats = {}
        base_stats.update({
            "router": dict(self._stats),
            "circuit_breaker_open": list(self.circuit_breaker._open_circuits),
            "timeout": self.timeout,
            "max_retries": self.max_retries,
        })
        return base_stats
    
    def reset_circuits(self) -> None:
        """Force reset all circuit breakers."""
        self.circuit_breaker._open_circuits.clear()
        self.circuit_breaker._failures.clear()
        self.circuit_breaker._last_failure.clear()
        logger.info("ModelRouter: all circuit breakers reset")

# Singleton
model_router = ModelRouter()
