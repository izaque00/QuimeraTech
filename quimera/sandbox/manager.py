# quimera/sandbox/manager.py
"""
SandboxManager — orquestrador de execução segura.

Coordena validação pré-execução, execução no backend,
sanitização de output e logging.
"""

import asyncio
import logging
from typing import Optional

from quimera.sandbox.backend_interface import ISandboxBackend
from quimera.sandbox.result import SandboxResult
from quimera.utils.controle import verificar_padroes_inseguros

logger = logging.getLogger(__name__)

# Padrões que bloqueiam execução mesmo em sandbox
BLOCKED_PATTERNS = [
    "os.system(", "subprocess.", "eval(", "exec(",
    "__import__", "open(", "socket.", "requests.",
    "urllib.", "ftp", "telnet",
]


class SandboxManager:
    """Gerencia execução segura de código em sandbox.
    
    Fluxo:
        1. Validação pré-execução (padrões inseguros)
        2. Seleção/fallback de backend
        3. Execução com timeout e resource limits
        4. Sanitização de output (remoção de paths sensíveis)
        5. Logging estruturado
    
    Uso:
        manager = SandboxManager(DockerBackend())
        result = await manager.run_safely(code, language="c")
        if result.is_clean:
            print("Patch seguro!")
    """
    
    def __init__(self, backend: ISandboxBackend, fallback_backend: Optional[ISandboxBackend] = None):
        self.backend = backend
        self.fallback_backend = fallback_backend
        self._execution_count = 0
        logger.info(f"SandboxManager inicializado: backend={backend.name()}")
    
    async def run_safely(
        self,
        code: str,
        language: str = "c",
        timeout: int = 30,
        memory_limit_mb: int = 512,
        network_enabled: bool = False,
        pre_validate: bool = True,
    ) -> SandboxResult:
        """Executa código com todas as camadas de segurança.
        
        Args:
            code: Código fonte.
            language: Linguagem (c, python, bash).
            timeout: Timeout em segundos.
            memory_limit_mb: Limite de memória.
            network_enabled: Permite rede.
            pre_validate: Habilita validação pré-execução.
            
        Returns:
            SandboxResult.
        """
        self._execution_count += 1
        
        # 1. Validação pré-execução
        if pre_validate:
            is_safe, blocked = self._validate_code(code)
            if not is_safe:
                logger.warning(f"Código bloqueado na validação: {blocked}")
                return SandboxResult(
                    success=False,
                    exit_code=-1,
                    error_message=f"Padrão inseguro detectado: {blocked}",
                    sandbox_backend=self.backend.name(),
                )
        
        # 2. Verificar disponibilidade do backend
        backend = self.backend
        if not await backend.is_available():
            if self.fallback_backend and await self.fallback_backend.is_available():
                logger.warning(f"Backend {backend.name()} indisponível, fallback para {self.fallback_backend.name()}")
                backend = self.fallback_backend
            else:
                return SandboxResult(
                    success=False,
                    exit_code=-1,
                    error_message=f"Backend '{backend.name()}' indisponível",
                    sandbox_backend=backend.name(),
                )
        
        # 3. Execução
        try:
            result = await asyncio.wait_for(
                backend.execute(
                    code=code,
                    language=language,
                    timeout=timeout,
                    memory_limit_mb=memory_limit_mb,
                    network_enabled=network_enabled,
                ),
                timeout=timeout + 10,  # margem extra para overhead
            )
        except asyncio.TimeoutError:
            logger.error(f"Sandbox timeout após {timeout+10}s")
            result = SandboxResult(
                success=False,
                exit_code=-1,
                killed_by_timeout=True,
                error_message=f"Timeout do sandbox após {timeout+10}s",
                sandbox_backend=backend.name(),
            )
        except Exception as e:
            logger.error(f"Erro no sandbox: {e}", exc_info=True)
            result = SandboxResult(
                success=False,
                exit_code=-1,
                error_message=str(e),
                sandbox_backend=backend.name(),
            )
        
        # 4. Sanitização de output
        result.stdout = self._sanitize_output(result.stdout)
        result.stderr = self._sanitize_output(result.stderr)
        
        # 5. Logging
        log_data = result.to_log_dict()
        if result.is_clean:
            logger.info(f"Execução #{self._execution_count}: OK ({result.execution_time_ms:.0f}ms)")
        else:
            logger.warning(f"Execução #{self._execution_count}: FAIL — {log_data}")
        
        return result
    
    def _validate_code(self, code: str) -> tuple:
        """Valida código antes da execução."""
        is_safe, patterns = verificar_padroes_inseguros(code)
        if not is_safe:
            return False, ", ".join(patterns)
        
        # Verificação adicional de padrões bloqueados
        for pattern in BLOCKED_PATTERNS:
            if pattern in code:
                return False, pattern
        return True, ""
    
    def _sanitize_output(self, output: str) -> str:
        """Remove informações sensíveis do output."""
        import re
        # Remove paths absolutos
        output = re.sub(r'/home/\w+', '/home/***', output)
        output = re.sub(r'/tmp/\w+', '/tmp/***', output)
        return output
    
    async def cleanup(self):
        """Limpa recursos de todos os backends."""
        await self.backend.cleanup()
        if self.fallback_backend:
            await self.fallback_backend.cleanup()
        logger.info("SandboxManager: recursos liberados.")
