# quimera/sandbox/result.py
"""
Estrutura de resultado de execução em sandbox.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SandboxResult:
    """Resultado de uma execução em sandbox.
    
    Attributes:
        success: Se a execução terminou sem erro.
        exit_code: Código de saída do processo.
        stdout: Saída padrão.
        stderr: Saída de erro.
        execution_time_ms: Tempo de execução em milissegundos.
        killed_by_timeout: Se foi morto por timeout.
        killed_by_oom: Se foi morto por falta de memória.
        sandbox_backend: Nome do backend usado.
        error_message: Mensagem de erro do sandbox (se falha de infra).
    """
    success: bool
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    execution_time_ms: float = 0.0
    killed_by_timeout: bool = False
    killed_by_oom: bool = False
    sandbox_backend: str = "unknown"
    error_message: Optional[str] = None
    
    @property
    def is_clean(self) -> bool:
        """Execução limpa: sucesso, sem timeout, sem OOM."""
        return self.success and not self.killed_by_timeout and not self.killed_by_oom
    
    @property
    def combined_output(self) -> str:
        """Combina stdout + stderr para log."""
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(self.stderr)
        return "\n".join(parts)
    
    def to_log_dict(self) -> dict:
        """Representação segura para logging (sem dados sensíveis)."""
        return {
            "success": self.success,
            "exit_code": self.exit_code,
            "execution_time_ms": self.execution_time_ms,
            "killed_by_timeout": self.killed_by_timeout,
            "killed_by_oom": self.killed_by_oom,
            "sandbox_backend": self.sandbox_backend,
        }
