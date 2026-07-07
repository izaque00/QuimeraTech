# quimera/utils/retry.py
"""
Decorator de retry com exponential backoff e jitter.

Substitui os try/except sem retry que existiam em chamadas
de subprocess e rede (kernel, rollback, LLM).

Uso:
    from quimera.utils.retry import retry

    @retry(max_attempts=3, base_delay=1.0, backoff=2.0)
    def fazer_chamada_externa():
        ...
"""

import asyncio
import functools
import logging
import random
import time
from typing import Callable, Type, Tuple

logger = logging.getLogger(__name__)

# Exceções que justificam retry (transientes)
RETRYABLE_EXCEPTIONS = (
    TimeoutError,
    ConnectionError,
    OSError,
)


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    backoff: float = 2.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    retryable: Tuple[Type[Exception], ...] = RETRYABLE_EXCEPTIONS,
):
    """Decorator que aplica retry com exponential backoff.

    Args:
        max_attempts: Número máximo de tentativas (inclui a primeira).
        base_delay: Delay inicial em segundos.
        backoff: Fator de multiplicação a cada tentativa.
        max_delay: Delay máximo entre tentativas.
        jitter: Se True, adiciona ±25% de variação aleatória ao delay.
        retryable: Tupla de exceções que justificam retry.

    Returns:
        Decorator.
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except retryable as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.error(
                            f"Retry esgotado para {func.__name__}: "
                            f"{max_attempts} tentativas, último erro: {e}"
                        )
                        raise
                    delay = min(base_delay * (backoff ** (attempt - 1)), max_delay)
                    if jitter:
                        delay *= random.uniform(0.75, 1.25)
                    logger.warning(
                        f"Retry {attempt}/{max_attempts} para {func.__name__}: "
                        f"{type(e).__name__}: {e}. Aguardando {delay:.1f}s..."
                    )
                    time.sleep(delay)
            raise last_exception  # type: ignore
        return wrapper
    return decorator


def async_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    backoff: float = 2.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    retryable: Tuple[Type[Exception], ...] = RETRYABLE_EXCEPTIONS,
):
    """Versão async do decorator de retry."""

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.error(
                            f"Async retry esgotado para {func.__name__}: "
                            f"{max_attempts} tentativas, último erro: {e}"
                        )
                        raise
                    delay = min(base_delay * (backoff ** (attempt - 1)), max_delay)
                    if jitter:
                        delay *= random.uniform(0.75, 1.25)
                    logger.warning(
                        f"Async retry {attempt}/{max_attempts} para "
                        f"{func.__name__}: {type(e).__name__}: {e}. "
                        f"Aguardando {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
            raise last_exception  # type: ignore
        return wrapper
    return decorator
