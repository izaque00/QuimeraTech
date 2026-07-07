"""
ProjectContext v1 — ADAPTER de compatibilidade.

⚠️  ESTE MÓDULO É UM ADAPTER — NÃO CONTÉM LÓGICA DE NEGÓCIO.
    Toda lógica real está em project_context_v2.py (implementação oficial).

    Este arquivo existe APENAS para manter compatibilidade com código
    legado que importa de project_context.py. Ele delega todas as
    chamadas para ProjectContextV2.

    REGRA: Nenhum código novo deve importar deste módulo.
           Use diretamente: from quimera.cognition.project_context_v2 import ProjectContextV2

Autor: Quimera MarkX — OMinivers
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from pathlib import Path

from quimera.cognition.project_context_v2 import (
    ProjectContextV2,
    FactNode,
    BeliefNode,
    DecisionNode,
    ConfidenceLevel,
    ContextType,
)

logger = logging.getLogger("quimera.cognition.project_context")


# ═══════════════════════════════════════════════════════════════
# ADAPTER — Delegação para ProjectContextV2 (implementação oficial)
# ═══════════════════════════════════════════════════════════════


# ── Re-export stubs from project_context_v2 ──
# These types are defined here for backward compatibility.

@dataclass
class DependencyInfo:
    """Information about a project dependency."""
    name: str
    version: str = ""
    is_dev: bool = False


@dataclass
class ComponentInfo:
    """Information about a project component."""
    name: str = ""
    type: str = "module"
    path: str = ""
    dependencies: List[str] = field(default_factory=list)
    complexity: float = 0.0


@dataclass
class Risk:
    """A detected risk in the project."""
    id: str = ""
    area: str = ""
    severity: "RiskLevel" = None
    description: str = ""
    recommendation: str = ""
    cwe_id: str = ""


def create_empty_context(project_path: str = ".") -> "ProjectContext":
    """Create an empty project context for analysis."""
    return ProjectContext(project_path=project_path)



class RiskLevel(str, Enum):
    """Risk severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ArchitecturePattern(str, Enum):
    """Common architecture patterns."""
    MONOLITH = "monolith"
    MICROSERVICES = "microservices"
    LAYERED = "layered"
    EVENT_DRIVEN = "event_driven"
    PLUGIN = "plugin"
    UNKNOWN = "unknown"

class ProjectHealth(str, Enum):
    """Health rating for a project."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class ProjectContext:
    """Flexible project context — stores all analysis results as attributes."""
    
    def __init__(self, project_path: str = ".", **kwargs):
        self.project_path = project_path
        self.project_name = Path(project_path).name
        self.primary_language = "unknown"
        self.frameworks: List[str] = []
        self.build_system = ""
        self.package_manager = ""
        self.purpose = ""
        self.domain = ""
        self.source_dirs: List[str] = []
        self.test_dirs: List[str] = []
        self.config_files: List[str] = []
        self.entry_point = ""
        self.file_count = 0
        self.total_lines = 0
        self.architecture = ArchitecturePattern.UNKNOWN
        self.dependencies: List[DependencyInfo] = []
        self.components: List[ComponentInfo] = []
        self.data_flows: List[List[str]] = []
        self.has_tests = False
        self.has_linting = False
        self.has_type_checking = False
        self.has_ci = False
        self.has_docker = False
        self.has_docs = False
        self.risks: List[Risk] = []
        self.health_score = 50.0
        self.health = ProjectHealth.UNKNOWN
        self.tags: List[str] = []
        self.conversation_context: List[Dict] = []
        self.user_intent = ""
        self.user_message = ""
        self.user_priority = "medium"
        self.current_error = ""
        self.error_type = ""
        self.expected_behavior = ""
        self.build_command = ""
        self.test_command = ""
        # Apply any extra kwargs
        for k, v in kwargs.items():
            setattr(self, k, v)
    
    def summary(self) -> str:
        fw = ', '.join(self.frameworks) if self.frameworks else 'none'
        return (
            f'Project: {self.project_name}\n'
            f'Language: {self.primary_language}\n'
            f'Files: {self.file_count} ({self.total_lines} lines)\n'
            f'Frameworks: {fw}\n'
            f'Architecture: {self.architecture.value}\n'
            f'Health: {self.health_score:.0f}/100 ({self.health.value})\n'
            f'Components: {len(self.components)}\n'
            f'Risks: {len(self.risks)}\n'
            f'Has tests: {self.has_tests}\n'
            f'Has CI: {self.has_ci}'
        )
    
    def __repr__(self):
        return f"ProjectContext({self.project_name}, {self.primary_language}, {self.file_count} files)"

