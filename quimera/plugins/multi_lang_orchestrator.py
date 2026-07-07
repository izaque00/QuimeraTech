"""Quimera Multi-Language Orchestrator — Plataforma Universal de Reparo.

Orquestrador que integra todos os agentes de linguagem e o Plugin SDK
em uma plataforma unificada. Roteia automaticamente arquivos para o
agente correto baseado na extensão.

Também contém a especificação do Quimera IDE Plugin para VSCode/JetBrains.

Pipeline Multi-Linguagem:
    Arquivo → [PluginManager] → Agente correto → detect → repair → verify
       .rs       RustAgent
       .go       GoAgent
       .py       PythonAgent (self-repair!)
       .c/.h     Agente C (core existente)
       .zig      ZigAgent (futuro)

Uso:
    from quimera.plugins.multi_lang_orchestrator import MultiLangOrchestrator
    
    orchestrator = MultiLangOrchestrator()
    orchestrator.register_all_builtin_agents()
    
    result = orchestrator.repair_file("src/main.rs", rust_code)
    print(f"Fixed: {result.issues_fixed}/{result.issues_found}")
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field

from quimera.plugins.plugin_sdk import (
    PluginManager, IRepairAgent, RepairIssue, Patch, RepairResult
)
from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)


@dataclass
class IDEPluginSpec:
    """Especificação do Quimera IDE Plugin.

    Define a interface e capacidades do plugin para VSCode e JetBrains.
    """
    name: str = "Quimera"
    display_name: str = "Quimera AI Code Repair"
    description: str = (
        "AI-powered code repair across multiple languages. "
        "Detect, repair, and verify bugs with formal verification."
    )
    version: str = "1.0.0"
    publisher: str = "quimera"
    icon: str = "quimera-logo.png"

    # Comandos
    commands: List[Dict[str, str]] = field(default_factory=lambda: [
        {"id": "quimera.repairFile", "title": "Quimera: Repair File"},
        {"id": "quimera.repairSelection", "title": "Quimera: Repair Selection"},
        {"id": "quimera.repairWorkspace", "title": "Quimera: Repair Workspace"},
        {"id": "quimera.verifyFile", "title": "Quimera: Verify File (Formal)"},
        {"id": "quimera.explainIssue", "title": "Quimera: Explain Issue"},
        {"id": "quimera.showDashboard", "title": "Quimera: Show Dashboard"},
    ])

    # Keybindings
    keybindings: List[Dict[str, str]] = field(default_factory=lambda: [
        {"key": "ctrl+shift+r", "command": "quimera.repairFile"},
        {"key": "ctrl+shift+v", "command": "quimera.verifyFile"},
        {"key": "ctrl+shift+e", "command": "quimera.explainIssue"},
    ])

    # Problemas suportados (VS Code Problem Matcher)
    problem_matchers: List[Dict[str, Any]] = field(default_factory=lambda: [
        {
            "name": "quimera-issues",
            "owner": "quimera",
            "pattern": [
                {
                    "regexp": r"^(.+):(\d+):(\d+):\s+(error|warning|info):\s+(.+)$",
                    "file": 1, "line": 2, "column": 3,
                    "severity": 4, "message": 5,
                }
            ]
        }
    ])

    # Linguagens suportadas
    languages: List[Dict[str, Any]] = field(default_factory=lambda: [
        {"id": "c", "extensions": [".c", ".h"], "agent": "Quimera Core C Agent"},
        {"id": "rust", "extensions": [".rs"], "agent": "Quimera Rust Agent"},
        {"id": "go", "extensions": [".go"], "agent": "Quimera Go Agent"},
        {"id": "python", "extensions": [".py"], "agent": "Quimera Python Self-Repair Agent"},
        {"id": "zig", "extensions": [".zig"], "agent": "Quimera Zig Agent (future)"},
    ])

    def to_vscode_package_json(self) -> Dict[str, Any]:
        """Gera package.json para VSCode extension."""
        return {
            "name": self.name.lower(),
            "displayName": self.display_name,
            "description": self.description,
            "version": self.version,
            "publisher": self.publisher,
            "icon": self.icon,
            "engines": {"vscode": "^1.85.0"},
            "categories": ["Linters", "Formatters", "Machine Learning"],
            "activationEvents": [
                "onLanguage:c", "onLanguage:rust", "onLanguage:go",
                "onLanguage:python", "onLanguage:zig",
            ],
            "contributes": {
                "commands": [
                    {"command": c["id"], "title": c["title"]}
                    for c in self.commands
                ],
                "keybindings": [
                    {"command": kb["command"], "key": kb["key"]}
                    for kb in self.keybindings
                ],
                "problemMatchers": self.problem_matchers,
                "configuration": {
                    "title": "Quimera",
                    "properties": {
                        "quimera.apiUrl": {
                            "type": "string",
                            "default": "http://localhost:8000",
                            "description": "URL da API Quimera"
                        },
                        "quimera.autoRepair": {
                            "type": "boolean",
                            "default": True,
                            "description": "Reparar automaticamente ao salvar"
                        },
                        "quimera.formalVerification": {
                            "type": "boolean",
                            "default": True,
                            "description": "Habilitar verificação formal"
                        }
                    }
                }
            }
        }


# ============================================================================
# MultiLangOrchestrator
# ============================================================================

class MultiLangOrchestrator:
    """Orquestrador multi-linguagem.

    Integra todos os agentes via PluginManager e fornece API unificada
    para reparo de código em qualquer linguagem suportada.
    """

    def __init__(self):
        self._manager = PluginManager()
        self._ide_spec = IDEPluginSpec()
        self._stats = {
            "total_files_processed": 0,
            "total_issues_found": 0,
            "total_issues_fixed": 0,
            "languages_used": set(),
        }

    def register_all_builtin_agents(self):
        """Registra todos os agentes built-in."""
        try:
            from quimera.plugins.rust_agent import RustAgent
            self._manager.register(RustAgent())
        except ImportError:
            logger.warning("RustAgent não disponível")

        try:
            from quimera.plugins.go_agent import GoAgent
            self._manager.register(GoAgent())
        except ImportError:
            logger.warning("GoAgent não disponível")

        try:
            from quimera.plugins.python_agent import PythonAgent
            self._manager.register(PythonAgent())
        except ImportError:
            logger.warning("PythonAgent não disponível")

        status = self._manager.get_status()
        montar_log(
            f"MultiLangOrchestrator: {status['total_agents']} agentes registrados "
            f"({', '.join(status['languages'])})",
            "INFO"
        )

    def register_agent(self, agent: IRepairAgent):
        """Registra um agente customizado."""
        self._manager.register(agent)

    def repair_file(
        self, file_path: str, code: str, max_fixes: int = 50
    ) -> Optional[RepairResult]:
        """Repara um arquivo usando o agente apropriado.

        Args:
            file_path: Caminho do arquivo.
            code: Código fonte.
            max_fixes: Máximo de correções.

        Returns:
            RepairResult ou None se nenhum agente suportar o arquivo.
        """
        agent = self._manager.get_agent_for_file(file_path)
        if not agent:
            ext = os.path.splitext(file_path)[1]
            montar_log(
                f"MultiLangOrchestrator: nenhum agente para .{ext} "
                f"({file_path})",
                "WARNING"
            )
            return None

        result = agent.repair_all(code, file_path, max_fixes)
        self._stats["total_files_processed"] += 1
        self._stats["total_issues_found"] += result.issues_found
        self._stats["total_issues_fixed"] += result.issues_fixed
        self._stats["languages_used"].add(agent.language)

        montar_log(
            f"MultiLangOrchestrator: {file_path} — {result.summary()}",
            "INFO"
        )
        return result

    def repair_directory(
        self, directory: str, recursive: bool = True
    ) -> Dict[str, RepairResult]:
        """Repara todos os arquivos em um diretório.

        Args:
            directory: Diretório com código fonte.
            recursive: Se True, processa subdiretórios.

        Returns:
            Dict mapeando file_path → RepairResult.
        """
        results = {}
        dir_path = Path(directory)

        pattern = "**/*" if recursive else "*"
        for file_path in dir_path.glob(pattern):
            if file_path.is_file():
                try:
                    code = file_path.read_text(errors="ignore")
                    result = self.repair_file(str(file_path), code)
                    if result:
                        results[str(file_path)] = result
                except Exception as e:
                    logger.warning(f"Failed to process {file_path}: {e}")

        total_fixed = sum(r.issues_fixed for r in results.values())
        montar_log(
            f"MultiLangOrchestrator: {len(results)} arquivos processados, "
            f"{total_fixed} issues corrigidos",
            "INFO"
        )
        return results

    def get_agent_for_file(self, file_path: str) -> Optional[IRepairAgent]:
        """Retorna o agente apropriado para um arquivo."""
        return self._manager.get_agent_for_file(file_path)

    def list_supported_languages(self) -> List[str]:
        """Lista linguagens suportadas."""
        return self._manager.list_languages()

    def get_ide_plugin_spec(self) -> Dict[str, Any]:
        """Retorna especificação do IDE plugin."""
        return self._ide_spec.to_vscode_package_json()

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "languages_used": list(self._stats["languages_used"]),
            "agents_registered": len(self._manager.list_agents()),
            "supported_languages": self._manager.list_languages(),
        }
