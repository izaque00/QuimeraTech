# quimera/sandbox/backends/docker_backend.py
"""
Backend Docker para SandboxManager.

Executa código em container Docker isolado com resource limits.
"""

import asyncio
import logging
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Optional

from quimera.sandbox.backend_interface import ISandboxBackend
from quimera.sandbox.result import SandboxResult

logger = logging.getLogger(__name__)

# Dockerfile mínimo embutido para compilação C
MINIMAL_DOCKERFILE = """FROM alpine:3.19
RUN apk add --no-cache gcc musl-dev make python3 py3-pip
RUN adduser -D -u 1000 quimera
USER quimera
WORKDIR /workspace
"""


class DockerBackend(ISandboxBackend):
    """Backend Docker para execução isolada.
    
    Constrói uma imagem mínima com toolchain C e executa
    código em container temporário com limites de recurso.
    """
    
    def __init__(self, image_name: str = "quimera-sandbox:latest", build_on_init: bool = True):
        self.image_name = image_name
        self._available: Optional[bool] = None
        if build_on_init:
            # Não bloqueia init — faz build async quando necessário
            pass
    
    def name(self) -> str:
        return "docker"
    
    async def is_available(self) -> bool:
        """Verifica se Docker está disponível."""
        if self._available is not None:
            return self._available
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "info",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            self._available = proc.returncode == 0
        except FileNotFoundError:
            self._available = False
        logger.info(f"DockerBackend disponível: {self._available}")
        return self._available
    
    async def execute(
        self,
        code: str,
        language: str = "c",
        timeout: int = 30,
        memory_limit_mb: int = 512,
        network_enabled: bool = False,
    ) -> SandboxResult:
        """Executa código C em container Docker."""
        start = time.monotonic()
        
        with tempfile.TemporaryDirectory(prefix="quimera_sandbox_") as tmpdir:
            tmp = Path(tmpdir)
            
            # Escreve código fonte
            source_file = tmp / "code.c"
            source_file.write_text(code)
            
            # Escreve script de entrypoint
            entrypoint = tmp / "run.sh"
            entrypoint.write_text("""#!/bin/sh
set -e
gcc -Wall -Werror -o /workspace/a.out /workspace/code.c 2>&1
if [ $? -eq 0 ]; then
    timeout %d /workspace/a.out 2>&1
fi
""" % timeout)
            entrypoint.chmod(0o755)
            
            cmd = [
                "docker", "run", "--rm",
                "--memory", f"{memory_limit_mb}m",
                "--cpus", "1",
                "--network", "none" if not network_enabled else "bridge",
                "--read-only",
                "--tmpfs", "/tmp:exec",
                "-v", f"{tmpdir}:/workspace:ro",
                "-w", "/workspace",
                "--entrypoint", "/workspace/run.sh",
                self.image_name,
            ]
            
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(), timeout=timeout + 5
                    )
                except asyncio.TimeoutError:
                    proc.kill()
                    elapsed = (time.monotonic() - start) * 1000
                    return SandboxResult(
                        success=False, exit_code=-1,
                        killed_by_timeout=True,
                        execution_time_ms=elapsed,
                        sandbox_backend="docker",
                    )
                
                elapsed = (time.monotonic() - start) * 1000
                return SandboxResult(
                    success=proc.returncode == 0,
                    exit_code=proc.returncode,
                    stdout=stdout.decode(errors="replace") if stdout else "",
                    stderr=stderr.decode(errors="replace") if stderr else "",
                    execution_time_ms=elapsed,
                    killed_by_timeout=False,
                    sandbox_backend="docker",
                )
                
            except FileNotFoundError:
                return SandboxResult(
                    success=False, exit_code=-1,
                    error_message="Docker não encontrado no PATH",
                    sandbox_backend="docker",
                )
            except Exception as e:
                logger.error(f"Erro no DockerBackend: {e}", exc_info=True)
                return SandboxResult(
                    success=False, exit_code=-1,
                    error_message=str(e),
                    sandbox_backend="docker",
                )
    
    async def execute_file(
        self,
        file_path: str,
        timeout: int = 30,
        memory_limit_mb: int = 512,
    ) -> SandboxResult:
        """Executa um arquivo existente em container."""
        if not os.path.exists(file_path):
            return SandboxResult(
                success=False, exit_code=-1,
                error_message=f"Arquivo não encontrado: {file_path}",
                sandbox_backend="docker",
            )
        code = Path(file_path).read_text()
        return await self.execute(code, timeout=timeout, memory_limit_mb=memory_limit_mb)
    
    async def cleanup(self):
        """Remove imagem Docker construída."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "rmi", "-f", self.image_name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
        except Exception:
            pass
    
    async def build_image(self) -> bool:
        """Constrói imagem Docker para sandbox."""
        with tempfile.TemporaryDirectory(prefix="quimera_docker_") as tmpdir:
            dockerfile = Path(tmpdir) / "Dockerfile"
            dockerfile.write_text(MINIMAL_DOCKERFILE)
            
            try:
                proc = await asyncio.create_subprocess_exec(
                    "docker", "build", "-t", self.image_name, tmpdir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if proc.returncode == 0:
                    logger.info(f"Imagem Docker '{self.image_name}' construída")
                    return True
                else:
                    logger.error(f"Falha no build Docker: {stderr.decode(errors='replace')}")
                    return False
            except Exception as e:
                logger.error(f"Erro no build Docker: {e}")
                return False
