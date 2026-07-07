# quimera/sandbox/backends/firejail_backend.py
"""
Backend Firejail para SandboxManager.

Firejail oferece isolamento via namespaces Linux com
overhead próximo de zero (ideal para Linux).
"""

import asyncio
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Optional

from quimera.sandbox.backend_interface import ISandboxBackend
from quimera.sandbox.result import SandboxResult

logger = logging.getLogger(__name__)


class FirejailBackend(ISandboxBackend):
    """Backend Firejail para execução isolada em Linux.
    
    Usa Linux namespaces (via Firejail) para isolar
    processo, filesystem, rede e recursos.
    """
    
    def __init__(self, profile: str = "default"):
        self.profile = profile
        self._available: Optional[bool] = None
    
    def name(self) -> str:
        return "firejail"
    
    async def is_available(self) -> bool:
        """Verifica se Firejail está disponível."""
        if self._available is not None:
            return self._available
        if os.name != "posix":
            self._available = False
            return False
        try:
            proc = await asyncio.create_subprocess_exec(
                "firejail", "--version",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            self._available = proc.returncode == 0
        except FileNotFoundError:
            self._available = False
        logger.info(f"FirejailBackend disponível: {self._available}")
        return self._available
    
    async def execute(
        self,
        code: str,
        language: str = "c",
        timeout: int = 30,
        memory_limit_mb: int = 512,
        network_enabled: bool = False,
    ) -> SandboxResult:
        """Executa código C via Firejail."""
        start = time.monotonic()
        
        with tempfile.TemporaryDirectory(prefix="quimera_firejail_") as tmpdir:
            tmp = Path(tmpdir)
            
            # Escreve código
            source = tmp / "code.c"
            source.write_text(code)
            
            # Compila primeiro (fora do jail para simplicidade)
            binary = tmp / "a.out"
            
            compile_proc = await asyncio.create_subprocess_exec(
                "gcc", "-Wall", "-Werror", "-o", str(binary), str(source),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            compile_stdout, compile_stderr = await compile_proc.communicate()
            
            if compile_proc.returncode != 0:
                elapsed = (time.monotonic() - start) * 1000
                return SandboxResult(
                    success=False,
                    exit_code=compile_proc.returncode,
                    stderr=compile_stderr.decode(errors="replace") if compile_stderr else "Erro de compilação",
                    execution_time_ms=elapsed,
                    sandbox_backend="firejail",
                )
            
            # Executa no Firejail
            firejail_cmd = [
                "firejail",
                f"--profile={self.profile}" if self.profile != "default" else "--noprofile",
                "--private=" + tmpdir,
                "--private-dev",
                "--private-tmp",
                "--seccomp",
                "--caps.drop=all",
                "--nonewprivs",
                f"--rlimit-as={memory_limit_mb * 1024 * 1024}",
            ]
            if not network_enabled:
                firejail_cmd.append("--net=none")
            
            firejail_cmd.append(str(binary))
            
            try:
                proc = await asyncio.create_subprocess_exec(
                    *firejail_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(), timeout=timeout
                    )
                except asyncio.TimeoutError:
                    proc.kill()
                    elapsed = (time.monotonic() - start) * 1000
                    return SandboxResult(
                        success=False, exit_code=-1,
                        killed_by_timeout=True,
                        execution_time_ms=elapsed,
                        sandbox_backend="firejail",
                    )
                
                elapsed = (time.monotonic() - start) * 1000
                return SandboxResult(
                    success=proc.returncode == 0,
                    exit_code=proc.returncode,
                    stdout=stdout.decode(errors="replace") if stdout else "",
                    stderr=stderr.decode(errors="replace") if stderr else "",
                    execution_time_ms=elapsed,
                    killed_by_timeout=False,
                    sandbox_backend="firejail",
                )
                
            except FileNotFoundError:
                return SandboxResult(
                    success=False, exit_code=-1,
                    error_message="Firejail não encontrado",
                    sandbox_backend="firejail",
                )
            except Exception as e:
                logger.error(f"Erro no FirejailBackend: {e}", exc_info=True)
                return SandboxResult(
                    success=False, exit_code=-1,
                    error_message=str(e),
                    sandbox_backend="firejail",
                )
    
    async def execute_file(
        self,
        file_path: str,
        timeout: int = 30,
        memory_limit_mb: int = 512,
    ) -> SandboxResult:
        """Executa arquivo em Firejail."""
        if not os.path.exists(file_path):
            return SandboxResult(
                success=False, exit_code=-1,
                error_message=f"Arquivo não encontrado: {file_path}",
                sandbox_backend="firejail",
            )
        code = Path(file_path).read_text()
        return await self.execute(code, timeout=timeout, memory_limit_mb=memory_limit_mb)
    
    async def cleanup(self):
        """Firejail não requer cleanup (stateless)."""
        pass
