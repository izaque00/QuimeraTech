"""Quimera Plugin SDK — Framework para Agentes de Reparo Multi-Linguagem.

Permite que terceiros escrevam agentes de reparo para novas linguagens
sem modificar o core do Quimera. Basta implementar a interface IRepairAgent.

Arquitetura do SDK:
    IRepairAgent (interface base)
        ├── detect(code) → List[Issue]
        ├── repair(code, issue) → Patch
        ├── verify(code, patch) → bool
        └── language → str

    PluginManager
        ├── register(agent)
        ├── discover(path)
        └── get_agent(language) → IRepairAgent

Suporte built-in via SDK:
    - Python: ast module, pylint, black, mypy
    - Rust: syn, cargo check, clippy, rustfmt
    - Go: go/ast, go vet, staticcheck, gofmt
    - Zig: zig ast-check, zig fmt
    - JavaScript/TypeScript: ESLint, Prettier

Uso:
    from quimera.plugins.plugin_sdk import (
        IRepairAgent, PluginManager, RepairIssue, Patch
    )
    
    class MyRustAgent(IRepairAgent):
        @property
        def language(self) -> str:
            return "rust"
        
        def detect(self, code: str) -> List[RepairIssue]:
            ...
        
        def repair(self, code: str, issue: RepairIssue) -> Patch:
            ...
    
    manager = PluginManager()
    manager.register(MyRustAgent())
"""

import logging
import importlib
import inspect
import pkgutil
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Type, Set
from pathlib import Path
from enum import Enum

from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)


# ============================================================================
# SDK Data Classes
# ============================================================================

class IssueSeverity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    HINT = "hint"


class IssueCategory(Enum):
    COMPILATION = "compilation"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    LOGIC = "logic"
    DEPENDENCY = "dependency"
    COMPATIBILITY = "compatibility"
    CUSTOM = "custom"


@dataclass
class RepairIssue:
    """Um problema detectado no código."""
    file_path: str
    line: int
    column: int = 0
    severity: IssueSeverity = IssueSeverity.ERROR
    category: IssueCategory = IssueCategory.COMPILATION
    code: str = ""              # Código do erro (ex: E0308)
    message: str = ""
    suggestion: str = ""
    context_lines: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file_path,
            "line": self.line,
            "column": self.column,
            "severity": self.severity.value,
            "category": self.category.value,
            "code": self.code,
            "message": self.message,
            "suggestion": self.suggestion,
        }


@dataclass
class Patch:
    """Um patch gerado para corrigir um RepairIssue."""
    file_path: str
    original_lines: str          # Código original
    patched_lines: str           # Código corrigido
    issue: RepairIssue
    confidence: float = 0.0      # 0-1
    description: str = ""
    unified_diff: str = ""       # Diff formato unificado
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return not self.original_lines and not self.patched_lines

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file_path,
            "confidence": self.confidence,
            "description": self.description,
            "diff_size": len(self.unified_diff),
        }


@dataclass
class RepairResult:
    """Resultado completo de uma operação de reparo."""
    language: str
    agent_name: str
    issues_found: int
    issues_fixed: int
    patches: List[Patch]
    verification_passed: bool
    errors: List[str] = field(default_factory=list)
    duration_ms: float = 0.0

    def summary(self) -> str:
        return (
            f"[{self.language}] {self.agent_name}: "
            f"{self.issues_fixed}/{self.issues_found} fixed, "
            f"verified={'yes' if self.verification_passed else 'no'}"
        )


# ============================================================================
# IRepairAgent — Interface Base
# ============================================================================

class IRepairAgent(ABC):
    """Interface base para agentes de reparo multi-linguagem.

    Para criar um agente para uma nova linguagem, implemente:
    - language (property)
    - detect(code, file_path) → List[RepairIssue]
    - repair(code, issue) → Patch
    - verify(original, patched) → bool

    Métodos opcionais:
    - supports_file_extension(ext) → bool
    - preprocess(code) → str
    - postprocess(code) → str
    - get_toolchain_info() → Dict
    """

    @property
    @abstractmethod
    def language(self) -> str:
        """Linguagem suportada (ex: 'rust', 'go', 'python', 'zig')."""
        ...

    @property
    def name(self) -> str:
        """Nome descritivo do agente."""
        return self.__class__.__name__

    @property
    def version(self) -> str:
        """Versão do agente."""
        return "1.0.0"

    @property
    def supported_extensions(self) -> List[str]:
        """Extensões de arquivo suportadas."""
        ext_map = {
            "python": [".py", ".pyi"],
            "rust": [".rs"],
            "go": [".go"],
            "zig": [".zig"],
            "c": [".c", ".h"],
            "cpp": [".cpp", ".cc", ".cxx", ".hpp"],
            "javascript": [".js", ".jsx"],
            "typescript": [".ts", ".tsx"],
        }
        return ext_map.get(self.language, [])

    @abstractmethod
    def detect(self, code: str, file_path: str = "") -> List[RepairIssue]:
        """Detecta problemas no código.

        Args:
            code: Código fonte completo.
            file_path: Caminho do arquivo (para mensagens de erro).

        Returns:
            Lista de RepairIssue encontrados.
        """
        ...

    @abstractmethod
    def repair(self, code: str, issue: RepairIssue) -> Patch:
        """Gera um patch para corrigir um problema.

        Args:
            code: Código fonte completo.
            issue: O problema a ser corrigido.

        Returns:
            Patch com a correção.
        """
        ...

    @abstractmethod
    def verify(self, original_code: str, patched_code: str) -> bool:
        """Verifica se o patch é válido (compila/linta sem erros).

        Args:
            original_code: Código antes do patch.
            patched_code: Código depois do patch.

        Returns:
            True se o patch é válido.
        """
        ...

    # Métodos opcionais

    def supports_file(self, file_path: str) -> bool:
        """Verifica se o agente suporta este arquivo."""
        ext = os.path.splitext(file_path)[1].lower()
        return ext in self.supported_extensions

    def preprocess(self, code: str) -> str:
        """Pré-processamento opcional do código."""
        return code

    def postprocess(self, code: str) -> str:
        """Pós-processamento opcional do código."""
        return code

    def get_toolchain_info(self) -> Dict[str, Any]:
        """Informações sobre toolchain necessária."""
        return {
            "language": self.language,
            "agent": self.name,
            "version": self.version,
            "extensions": self.supported_extensions,
        }

    def repair_all(
        self,
        code: str,
        file_path: str = "",
        max_fixes: int = 50,
    ) -> RepairResult:
        """Repara todos os problemas detectados em uma passagem.

        Args:
            code: Código fonte.
            file_path: Caminho do arquivo.
            max_fixes: Máximo de correções.

        Returns:
            RepairResult com todos os patches.
        """
        import time
        start = time.time()

        issues = self.detect(code, file_path)
        patches = []
        errors = []
        current_code = code

        for issue in issues[:max_fixes]:
            try:
                patch = self.repair(current_code, issue)
                if not patch.is_empty:
                    patches.append(patch)
                    current_code = patch.patched_lines
            except Exception as e:
                errors.append(f"Failed to repair {issue.code}: {e}")

        verified = self.verify(code, current_code) if patches else True

        return RepairResult(
            language=self.language,
            agent_name=self.name,
            issues_found=len(issues),
            issues_fixed=len(patches),
            patches=patches,
            verification_passed=verified,
            errors=errors,
            duration_ms=(time.time() - start) * 1000,
        )


# ============================================================================
# Plugin Manager
# ============================================================================

class PluginManager:
    """Gerencia registro e descoberta de plugins de reparo.

    Responsável por:
    - Registrar agentes built-in e de terceiros
    - Descobrir plugins em diretórios
    - Roteamento automático por extensão de arquivo

    Uso:
        manager = PluginManager()
        manager.discover("/path/to/plugins")
        agent = manager.get_agent_for_file("src/main.rs")
        result = agent.repair_all(code, "src/main.rs")
    """

    def __init__(self):
        self._agents: Dict[str, IRepairAgent] = {}       # language → agent
        self._extension_map: Dict[str, IRepairAgent] = {} # .ext → agent
        self._registry: Dict[str, Type[IRepairAgent]] = {}

    def register(self, agent: IRepairAgent):
        """Registra um agente de reparo."""
        self._agents[agent.language] = agent
        for ext in agent.supported_extensions:
            self._extension_map[ext] = agent
        montar_log(
            f"PluginManager: registrado agente '{agent.name}' "
            f"para {agent.language} ({', '.join(agent.supported_extensions)})",
            "INFO"
        )

    def register_class(self, agent_class: Type[IRepairAgent]):
        """Registra uma classe de agente (será instanciada sob demanda)."""
        self._registry[agent_class.__name__] = agent_class

    def unregister(self, language: str):
        """Remove um agente."""
        if language in self._agents:
            agent = self._agents.pop(language)
            for ext in agent.supported_extensions:
                if self._extension_map.get(ext) == agent:
                    del self._extension_map[ext]

    def discover(self, plugin_dir: str):
        """Descobre plugins em um diretório.

        Escaneia arquivos .py que contenham classes implementando IRepairAgent.

        Args:
            plugin_dir: Diretório contendo plugins.
        """
        plugin_path = Path(plugin_dir)
        if not plugin_path.exists():
            logger.warning(f"Plugin directory not found: {plugin_dir}")
            return 0

        sys.path.insert(0, str(plugin_path))
        count = 0

        for finder, name, ispkg in pkgutil.iter_modules([str(plugin_path)]):
            try:
                module = importlib.import_module(name)
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        inspect.isclass(attr)
                        and issubclass(attr, IRepairAgent)
                        and attr is not IRepairAgent
                    ):
                        try:
                            instance = attr()
                            self.register(instance)
                            count += 1
                        except Exception as e:
                            logger.warning(f"Failed to instantiate {attr_name}: {e}")
            except Exception as e:
                logger.warning(f"Failed to load plugin {name}: {e}")

        montar_log(f"PluginManager: {count} plugins descobertos em {plugin_dir}", "INFO")
        return count

    def get_agent(self, language: str) -> Optional[IRepairAgent]:
        """Obtém agente por linguagem."""
        return self._agents.get(language)

    def get_agent_for_file(self, file_path: str) -> Optional[IRepairAgent]:
        """Obtém agente apropriado para um arquivo."""
        ext = os.path.splitext(file_path)[1].lower()
        return self._extension_map.get(ext) or self._agents.get("c")  # fallback C

    def list_languages(self) -> List[str]:
        """Lista linguagens com agentes registrados."""
        return list(self._agents.keys())

    def list_agents(self) -> List[Dict[str, Any]]:
        """Lista todos os agentes registrados."""
        return [
            {
                "language": lang,
                "name": agent.name,
                "version": agent.version,
                "extensions": agent.supported_extensions,
            }
            for lang, agent in self._agents.items()
        ]

    def get_status(self) -> Dict[str, Any]:
        return {
            "total_agents": len(self._agents),
            "languages": self.list_languages(),
            "extensions": list(self._extension_map.keys()),
            "agents": self.list_agents(),
        }
