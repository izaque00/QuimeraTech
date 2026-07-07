# quimera/sandbox/__init__.py
"""
Sistema de Sandbox do Quimera Mark II.

Isola a execução de código gerado/modificado pelos agentes
em ambientes controlados, impedindo danos ao sistema host.

Backends disponíveis:
    DockerBackend   — container Docker (multi-plataforma)
    FirejailBackend — Firejail (Linux, zero overhead)
    E2BBackend      — E2B Cloud (remoto, máximo isolamento)

Uso:
    from quimera.sandbox import SandboxManager, DockerBackend
    
    manager = SandboxManager(DockerBackend())
    result = await manager.run_safely(code, language="c", timeout=30)
"""

from quimera.sandbox.manager import SandboxManager
from quimera.sandbox.result import SandboxResult
from quimera.sandbox.backend_interface import ISandboxBackend
from quimera.sandbox.backends.docker_backend import DockerBackend
from quimera.sandbox.backends.firejail_backend import FirejailBackend

__all__ = [
    "SandboxManager",
    "SandboxResult",
    "ISandboxBackend",
    "DockerBackend",
    "FirejailBackend",
]
