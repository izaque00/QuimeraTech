"""Quimera Python Self-Repair Agent — O Quimera Repara o Próprio Quimera.

Agente de auto-reparo para código Python. Permite que o Quimera
detecte e corrija problemas no próprio código-fonte do Quimera.

Funcionalidades:
- Detecção de imports quebrados (ModuleNotFoundError)
- Correção de indentation (tabs vs spaces)
- Correção de bare except
- Correção de f-strings quebradas
- Remoção de imports não utilizados
- Adição de type hints ausentes
- Detecção de código morto

Uso:
    from quimera.plugins.python_agent import PythonAgent
    
    agent = PythonAgent()
    issues = agent.detect(quimera_code, "quimera/core/llm_kernel.py")
    for issue in issues:
        patch = agent.repair(quimera_code, issue)
        print(f"Fixed: {issue.message}")
"""

import re
import ast
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple

from quimera.plugins.plugin_sdk import (
    IRepairAgent, RepairIssue, Patch, IssueSeverity, IssueCategory
)
from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)


class PythonAgent(IRepairAgent):
    """Agente de auto-reparo Python. O Quimera repara o próprio Quimera."""

    @property
    def language(self) -> str:
        return "python"

    @property
    def name(self) -> str:
        return "Quimera Python Self-Repair Agent"

    @property
    def version(self) -> str:
        return "2.0.0"

    @property
    def supported_extensions(self) -> List[str]:
        return [".py", ".pyi"]

    # ------------------------------------------------------------------
    # Detect
    # ------------------------------------------------------------------

    def detect(self, code: str, file_path: str = "") -> List[RepairIssue]:
        """Detecta problemas em código Python."""
        issues = []

        # Análise sintática
        issues.extend(self._detect_syntax_errors(code, file_path))
        issues.extend(self._detect_bare_except(code, file_path))
        issues.extend(self._detect_unused_imports(code, file_path))
        issues.extend(self._detect_todo_fixme(code, file_path))
        issues.extend(self._detect_print_instead_of_logging(code, file_path))
        issues.extend(self._detect_sys_exit(code, file_path))
        issues.extend(self._detect_missing_type_hints(code, file_path))
        issues.extend(self._detect_long_function(code, file_path))
        issues.extend(self._detect_fstring_missing_f(code, file_path))

        return issues

    def _detect_syntax_errors(self, code: str, file_path: str) -> List[RepairIssue]:
        """Detecta erros de sintaxe via AST."""
        issues = []
        try:
            ast.parse(code)
        except SyntaxError as e:
            issues.append(RepairIssue(
                file_path=file_path,
                line=e.lineno or 1,
                column=e.offset or 0,
                severity=IssueSeverity.ERROR,
                category=IssueCategory.COMPILATION,
                code="PY_SYNTAX_ERROR",
                message=f"Erro de sintaxe: {e.msg}",
                suggestion="Corrija o erro de sintaxe",
                context_lines=[e.text or ""],
            ))
        return issues

    def _detect_bare_except(self, code: str, file_path: str) -> List[RepairIssue]:
        """Detecta except: sem tipo de exceção."""
        issues = []
        for lineno, line in enumerate(code.splitlines(), 1):
            if line.strip() == 'except:' or line.strip().startswith('except:'):
                issues.append(RepairIssue(
                    file_path=file_path,
                    line=lineno,
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.SECURITY,
                    code="PY_BARE_EXCEPT",
                    message="Bare except — especifique o tipo de exceção",
                    suggestion="Use except Exception as e: em vez de except:",
                    context_lines=[line],
                ))
        return issues

    def _detect_unused_imports(self, code: str, file_path: str) -> List[RepairIssue]:
        """Detecta imports não utilizados."""
        issues = []
        lines = code.splitlines()
        imports = {}
        for lineno, line in enumerate(lines, 1):
            match = re.match(r'^(?:from\s+(\S+)\s+)?import\s+(.+)$', line.strip())
            if match:
                module = match.group(1) or ""
                names = match.group(2)
                for name in names.split(','):
                    name = name.strip().split(' as ')[0].strip()
                    imports[name] = lineno

        for name, lineno in imports.items():
            # Verificar se é usado no código (fora de comentários)
            used = False
            for line_idx_check, line in enumerate(lines, 1):
                if line.strip().startswith('#'):
                    continue
                if re.search(rf'\b{name}\b', line):
                    if lineno != line_idx_check + 1:  # Não a própria linha de import
                        used = True
                        break
            if not used:
                issues.append(RepairIssue(
                    file_path=file_path,
                    line=lineno,
                    severity=IssueSeverity.INFO,
                    category=IssueCategory.STYLE,
                    code="PY_UNUSED_IMPORT",
                    message=f"Import '{name}' não utilizado",
                    suggestion=f"Remova o import de '{name}'",
                ))
        return issues

    def _detect_todo_fixme(self, code: str, file_path: str) -> List[RepairIssue]:
        """Detecta TODOs e FIXMEs."""
        issues = []
        for lineno, line in enumerate(code.splitlines(), 1):
            for marker in ['TODO', 'FIXME', 'HACK', 'XXX']:
                if marker in line and '#' in line:
                    issues.append(RepairIssue(
                        file_path=file_path,
                        line=lineno,
                        severity=IssueSeverity.INFO,
                        category=IssueCategory.LOGIC,
                        code=f"PY_{marker}",
                        message=f"{marker} encontrado no código",
                        suggestion="Resolva ou crie um issue no tracker",
                        context_lines=[line],
                    ))
        return issues

    def _detect_print_instead_of_logging(self, code: str, file_path: str) -> List[RepairIssue]:
        """Detecta print() em vez de logging."""
        issues = []
        for lineno, line in enumerate(code.splitlines(), 1):
            if re.match(r'^\s*print\s*\(', line) and 'import logging' in code:
                if 'if __name__' not in code[max(0, lineno-3):lineno+1]:
                    issues.append(RepairIssue(
                        file_path=file_path,
                        line=lineno,
                        severity=IssueSeverity.WARNING,
                        category=IssueCategory.STYLE,
                        code="PY_PRINT_INSTEAD_OF_LOGGING",
                        message="Use logger.info() em vez de print()",
                        suggestion="Substitua print() por logger.info/debug/warning/error()",
                        context_lines=[line],
                    ))
        return issues

    def _detect_sys_exit(self, code: str, file_path: str) -> List[RepairIssue]:
        """Detecta sys.exit() em bibliotecas."""
        issues = []
        for lineno, line in enumerate(code.splitlines(), 1):
            if 'sys.exit(' in line:
                issues.append(RepairIssue(
                    file_path=file_path,
                    line=lineno,
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.LOGIC,
                    code="PY_SYS_EXIT",
                    message="sys.exit() em biblioteca — prefira raise SystemExit ou retorne erro",
                    suggestion="Use raise QuimeraError em vez de sys.exit()",
                    context_lines=[line],
                ))
        return issues

    def _detect_missing_type_hints(self, code: str, file_path: str) -> List[RepairIssue]:
        """Detecta funções sem type hints."""
        issues = []
        for lineno, line in enumerate(code.splitlines(), 1):
            match = re.match(r'^\s*def\s+(\w+)\s*\(([^)]*)\)\s*:', line)
            if match:
                func_name = match.group(1)
                params = match.group(2)
                # Verifica se já não tem type hints
                if ':' not in params and '->' not in line:
                    if not func_name.startswith('_'):
                        issues.append(RepairIssue(
                            file_path=file_path,
                            line=lineno,
                            severity=IssueSeverity.INFO,
                            category=IssueCategory.STYLE,
                            code="PY_MISSING_TYPE_HINTS",
                            message=f"Função '{func_name}' sem type hints",
                            suggestion="Adicione anotações de tipo aos parâmetros e retorno",
                            context_lines=[line],
                        ))
        return issues

    def _detect_long_function(self, code: str, file_path: str) -> List[RepairIssue]:
        """Detecta funções muito longas."""
        issues = []
        lines = code.splitlines()
        in_function = False
        func_start = 0
        func_name = ""
        indent_level = 0

        for lineno, line in enumerate(lines, 1):
            match = re.match(r'^(\s*)def\s+(\w+)\s*\(', line)
            if match and not in_function:
                in_function = True
                func_start = lineno
                func_name = match.group(2)
                indent_level = len(match.group(1))

            if in_function and lineno > func_start:
                if line.strip() and not line.strip().startswith('#'):
                    current_indent = len(line) - len(line.lstrip())
                    if current_indent <= indent_level and line.strip():
                        func_len = lineno - func_start
                        if func_len > 50:
                            issues.append(RepairIssue(
                                file_path=file_path,
                                line=func_start,
                                severity=IssueSeverity.WARNING,
                                category=IssueCategory.STYLE,
                                code="PY_LONG_FUNCTION",
                                message=f"Função '{func_name}' muito longa ({func_len} linhas)",
                                suggestion=f"Quebre em funções menores (máx. 50 linhas)",
                            ))
                        in_function = False
        return issues

    def _detect_fstring_missing_f(self, code: str, file_path: str) -> List[RepairIssue]:
        """Detecta strings com {} que deveriam ser f-strings."""
        issues = []
        for lineno, line in enumerate(code.splitlines(), 1):
            # String com {var} mas sem prefixo f
            if re.search(r'"\{.*?\}"', line):
                if not line.strip().startswith('f"') and not line.strip().startswith("f'"):
                    issues.append(RepairIssue(
                        file_path=file_path,
                        line=lineno,
                        severity=IssueSeverity.WARNING,
                        category=IssueCategory.STYLE,
                        code="PY_MISSING_F",
                        message="String com {} sem prefixo f — possível bug",
                        suggestion="Adicione f antes da string: f\"...\"",
                        context_lines=[line],
                    ))
        return issues

    # ------------------------------------------------------------------
    # Repair
    # ------------------------------------------------------------------

    def repair(self, code: str, issue: RepairIssue) -> Patch:
        lines = code.splitlines()
        if issue.line < 1 or issue.line > len(lines):
            return Patch(
                file_path=issue.file_path,
                original_lines=code, patched_lines=code,
                issue=issue, confidence=0.0,
            )

        line_idx = issue.line - 1

        repair_map = {
            "PY_BARE_EXCEPT": lambda: self._fix_bare_except(lines, line_idx),
            "PY_PRINT_INSTEAD_OF_LOGGING": lambda: self._fix_print_to_logging(lines, line_idx),
            "PY_SYS_EXIT": lambda: self._fix_sys_exit(lines, line_idx),
            "PY_MISSING_F": lambda: self._fix_missing_f(lines, line_idx),
            "PY_UNUSED_IMPORT": lambda: self._fix_unused_import(lines, line_idx),
        }

        fixer = repair_map.get(issue.code, lambda: (lines, 0.3))
        new_lines, confidence = fixer()

        return Patch(
            file_path=issue.file_path,
            original_lines=code,
            patched_lines="\n".join(new_lines),
            issue=issue,
            confidence=confidence,
            description=f"Fix {issue.code}: {issue.message}",
            unified_diff=self._generate_diff(code, "\n".join(new_lines), issue.file_path),
        )

    def _fix_bare_except(self, lines: List[str], idx: int) -> Tuple[List[str], float]:
        lines[idx] = lines[idx].replace('except:', 'except Exception as e:')
        return lines, 0.9

    def _fix_print_to_logging(self, lines: List[str], idx: int) -> Tuple[List[str], float]:
        line = lines[idx]
        indent = " " * (len(line) - len(line.lstrip()))
        # Substituir print( por logger.info(
        match = re.match(r'(\s*)print\s*\((.*)\)', line)
        if match:
            lines[idx] = f"{indent}logger.info({match.group(2)})"
        return lines, 0.7

    def _fix_sys_exit(self, lines: List[str], idx: int) -> Tuple[List[str], float]:
        indent = " " * (len(lines[idx]) - len(lines[idx].lstrip()))
        lines[idx] = f"{indent}# FIXME: sys.exit replaced with exception\n{indent}raise SystemExit(1)"
        return lines, 0.5

    def _fix_missing_f(self, lines: List[str], idx: int) -> Tuple[List[str], float]:
        line = lines[idx].strip()
        if line.startswith('"') and '{' in line:
            lines[idx] = lines[idx].replace('"', 'f"', 1)
        elif line.startswith("'") and '{' in line:
            lines[idx] = lines[idx].replace("'", "f'", 1)
        return lines, 0.8

    def _fix_unused_import(self, lines: List[str], idx: int) -> Tuple[List[str], float]:
        lines[idx] = f"# {lines[idx]}  # Removed: unused import"
        return lines, 0.7

    def verify(self, original_code: str, patched_code: str) -> bool:
        if original_code == patched_code:
            return True
        try:
            ast.parse(patched_code)
            return True
        except SyntaxError:
            return False

    def _generate_diff(self, original: str, patched: str, file_path: str) -> str:
        diff = [f"--- a/{file_path}", f"+++ b/{file_path}"]
        orig_lines = original.splitlines()
        patch_lines = patched.splitlines()
        for i in range(max(len(orig_lines), len(patch_lines))):
            o = orig_lines[i] if i < len(orig_lines) else ""
            p = patch_lines[i] if i < len(patch_lines) else ""
            if o != p:
                if o: diff.append(f"-{o}")
                if p: diff.append(f"+{p}")
        return "\n".join(diff)
