# quimera/sandbox/backends/__init__.py
"""
Backends de sandbox do Quimera.
"""

from quimera.sandbox.backends.docker_backend import DockerBackend
from quimera.sandbox.backends.firejail_backend import FirejailBackend

__all__ = ["DockerBackend", "FirejailBackend"]
