# quimera/sandbox/backend_interface.py
"""
Interface abstrata para backends de sandbox.
"""

from abc import ABC, abstractmethod
from typing import Optional
from quimera.sandbox.result import SandboxResult


class ISandboxBackend(ABC):
    """Interface para backends de sandbox.
    
    Implementações:
        DockerBackend, FirejailBackend, E2BBackend
    """
    
    @abstractmethod
    def name(self) -> str:
        """Nome do backend para logging e seleção."""
        ...
    
    @abstractmethod
    async def execute(
        self,
        code: str,
        language: str = "c",
        timeout: int = 30,
        memory_limit_mb: int = 512,
        network_enabled: bool = False,
    ) -> SandboxResult:
        """Executa código em sandbox isolado.
        
        Args:
            code: Código fonte a executar.
            language: Linguagem ('c', 'python', 'bash').
            timeout: Timeout em segundos.
            memory_limit_mb: Limite de memória em MB.
            network_enabled: Se permite acesso à rede.
            
        Returns:
            SandboxResult com output e status da execução.
        """
        ...
    
    @abstractmethod
    async def execute_file(
        self,
        file_path: str,
        timeout: int = 30,
        memory_limit_mb: int = 512,
    ) -> SandboxResult:
        """Executa um arquivo em sandbox.
        
        Args:
            file_path: Caminho do arquivo a executar.
            timeout: Timeout em segundos.
            memory_limit_mb: Limite de memória em MB.
        """
        ...
    
    @abstractmethod
    async def cleanup(self):
        """Limpa recursos do backend após execução."""
        ...
    
    @abstractmethod
    async def is_available(self) -> bool:
        """Verifica se o backend está disponível no sistema."""
        ...
