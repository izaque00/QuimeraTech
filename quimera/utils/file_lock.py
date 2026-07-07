# quimera/utils/file_lock.py
"""
File lock usando fcntl (Unix) ou msvcrt (Windows).

Substitui os os.remove() inseguros no .git/index.lock
que causavam race conditions entre múltiplos AgentesQuimera.

Uso:
    from quimera.utils.file_lock import FileLock
    
    with FileLock("/path/to/.git/index.lock", timeout=5):
        # operação segura com subprocess git
"""

import os
import time
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Detecta backend de lock
if os.name == 'posix':
    import fcntl

    def _acquire(fd, timeout: float):
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    return False
                time.sleep(0.1)

    def _release(fd):
        fcntl.flock(fd, fcntl.LOCK_UN)

elif os.name == 'nt':
    import msvcrt

    def _acquire(fd, timeout: float):
        deadline = time.monotonic() + timeout
        while True:
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                return True
            except OSError:
                if time.monotonic() >= deadline:
                    return False
                time.sleep(0.1)

    def _release(fd):
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
else:
    def _acquire(fd, timeout: float):
        return True
    def _release(fd):
        pass


@contextmanager
def FileLock(path: str, timeout: float = 10.0):
    """Adquire lock exclusivo em um arquivo.

    Args:
        path: Caminho do arquivo de lock.
        timeout: Tempo máximo de espera em segundos.

    Yields:
        True se o lock foi adquirido.

    Raises:
        TimeoutError: Se não conseguir adquirir o lock no timeout.
    """
    dirname = os.path.dirname(path)
    if dirname and not os.path.exists(dirname):
        os.makedirs(dirname, exist_ok=True)

    fd = os.open(path, os.O_CREAT | os.O_RDWR)
    try:
        acquired = _acquire(fd, timeout)
        if not acquired:
            os.close(fd)
            raise TimeoutError(f"Não foi possível adquirir lock em '{path}' após {timeout}s")
        logger.debug(f"Lock adquirido: {path}")
        yield True
    finally:
        _release(fd)
        os.close(fd)
        try:
            os.remove(path)
        except OSError:
            pass
        logger.debug(f"Lock liberado: {path}")
