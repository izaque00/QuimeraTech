"""
Utilitários de resiliência para o sistema Quimera.

Contém implementações de Circuit Breaker, retry com backoff,
e outras ferramentas de resiliência distribuída.
"""

import time
import threading
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from quimera.logs.parser import montar_log


class CircuitBreaker:
    """
    Implementação thread-safe do padrão Circuit Breaker.

    Estados:
        - CLOSED (fechado): operação normal, falhas são contadas.
        - OPEN (aberto): após threshold de falhas, rejeita chamadas rapidamente.
        - HALF_OPEN (semi-aberto): após cooldown, permite uma chamada de teste.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        cooldown_seconds: float = 300.0,
        half_open_max_calls: int = 1,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.half_open_max_calls = half_open_max_calls

        self._status: str = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self._consecutive_failures: int = 0
        self._cooldown_until: float = 0.0
        self._half_open_calls: int = 0
        self._lock = threading.RLock()

    @property
    def is_operational(self) -> bool:
        """Verifica se o circuito permite chamadas."""
        with self._lock:
            if self._status == "CLOSED":
                return True
            if self._status == "OPEN":
                if time.time() >= self._cooldown_until:
                    self._status = "HALF_OPEN"
                    self._half_open_calls = 0
                    montar_log(
                        f"CircuitBreaker '{self.name}': OPEN -> HALF_OPEN",
                        "INFO",
                    )
                    return True
                return False
            if self._status == "HALF_OPEN":
                return self._half_open_calls < self.half_open_max_calls
            return False

    def record_success(self):
        """Registra uma chamada bem-sucedida."""
        with self._lock:
            self._consecutive_failures = 0
            if self._status == "HALF_OPEN":
                self._status = "CLOSED"
                self._half_open_calls = 0
                montar_log(
                    f"CircuitBreaker '{self.name}': HALF_OPEN -> CLOSED",
                    "INFO",
                )

    def record_failure(self) -> bool:
        """
        Registra uma falha. Retorna True se o circuito acabou de abrir.
        """
        with self._lock:
            self._consecutive_failures += 1

            if self._status == "HALF_OPEN":
                self._status = "OPEN"
                self._cooldown_until = time.time() + self.cooldown_seconds
                montar_log(
                    f"CircuitBreaker '{self.name}': HALF_OPEN -> OPEN "
                    f"(cooldown={self.cooldown_seconds}s)",
                    "WARNING",
                )
                return True

            if self._consecutive_failures >= self.failure_threshold:
                self._status = "OPEN"
                self._cooldown_until = time.time() + self.cooldown_seconds
                montar_log(
                    f"CircuitBreaker '{self.name}': CLOSED -> OPEN "
                    f"(falhas={self._consecutive_failures}, cooldown={self.cooldown_seconds}s)",
                    "CRITICAL",
                )
                return True

            return False

    def __call__(self, func: Callable) -> Callable:
        """Decorator para aplicar o circuit breaker em uma função."""
        def wrapper(*args, **kwargs):
            if not self.is_operational:
                raise RuntimeError(
                    f"CircuitBreaker '{self.name}' está OPEN. "
                    f"Cooldown até {datetime.fromtimestamp(self._cooldown_until)}"
                )
            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            except Exception:
                self.record_failure()
                raise
        return wrapper


class CircuitBreakerRegistry:
    """Registro global de CircuitBreakers por nome."""

    _instance: Optional["CircuitBreakerRegistry"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._breakers: Dict[str, CircuitBreaker] = {}
        return cls._instance

    def get_or_create(
        self,
        name: str,
        failure_threshold: int = 3,
        cooldown_seconds: float = 300.0,
    ) -> CircuitBreaker:
        """Obtém ou cria um CircuitBreaker pelo nome."""
        if name not in self._breakers:
            with self._lock:
                if name not in self._breakers:
                    self._breakers[name] = CircuitBreaker(
                        name=name,
                        failure_threshold=failure_threshold,
                        cooldown_seconds=cooldown_seconds,
                    )
        return self._breakers[name]

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Obtém um CircuitBreaker existente ou None."""
        return self._breakers.get(name)

    def reset(self, name: str):
        """Reseta um CircuitBreaker específico."""
        breaker = self._breakers.get(name)
        if breaker:
            with breaker._lock:
                breaker._status = "CLOSED"
                breaker._consecutive_failures = 0
                breaker._cooldown_until = 0.0
                breaker._half_open_calls = 0

    def reset_all(self):
        """Reseta todos os CircuitBreakers."""
        for name in self._breakers:
            self.reset(name)
