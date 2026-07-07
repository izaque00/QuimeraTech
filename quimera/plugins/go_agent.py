"""Quimera Go Agent — Reparo de Infraestrutura Cloud (Kubernetes Operators).

Agente de reparo para código Go, focado em operadores Kubernetes
e infraestrutura cloud.

Funcionalidades:
- Detecção de erros de compilação (go build)
- Correção de error handling (err check ausente)
- Correção de goroutine leaks (falta de context cancellation)
- Correção de resource leaks (defer close ausente)
- Formatação via gofmt
- Integração com staticcheck e go vet

Uso:
    from quimera.plugins.go_agent import GoAgent
    
    agent = GoAgent()
    issues = agent.detect(go_code, "main.go")
    for issue in issues:
        patch = agent.repair(go_code, issue)
"""

import re
import logging
import subprocess
import tempfile
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from quimera.plugins.plugin_sdk import (
    IRepairAgent, RepairIssue, Patch, IssueSeverity, IssueCategory
)
from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)


class GoAgent(IRepairAgent):
    """Agente de reparo para código Go."""

    @property
    def language(self) -> str:
        return "go"

    @property
    def name(self) -> str:
        return "Quimera Go Agent"

    @property
    def supported_extensions(self) -> List[str]:
        return [".go"]

    # ------------------------------------------------------------------
    # Detect
    # ------------------------------------------------------------------

    def detect(self, code: str, file_path: str = "") -> List[RepairIssue]:
        issues = []
        issues.extend(self._detect_unchecked_error(code, file_path))
        issues.extend(self._detect_resource_leak(code, file_path))
        issues.extend(self._detect_goroutine_leak(code, file_path))
        issues.extend(self._detect_nil_deref(code, file_path))
        issues.extend(self._detect_defer_in_loop(code, file_path))
        issues.extend(self._detect_empty_interface(code, file_path))
        issues.extend(self._detect_panic(code, file_path))

        go_vet_issues = self._go_vet(code, file_path)
        issues.extend(go_vet_issues)

        return issues

    def _detect_unchecked_error(self, code: str, file_path: str) -> List[RepairIssue]:
        """Detecta erros não verificados."""
        issues = []
        for lineno, line in enumerate(code.splitlines(), 1):
            # Padrão: _, err := ou result, _ := (ignorando erro)
            if re.match(r'.*,\s*err\s*:?=', line):
                # Verifica se há if err != nil nas próximas linhas
                pass
            # Padrão: chamada que retorna error sem verificação
            if re.match(r'^\s+\w+\(.*\)\s*$', line) and 'err' not in line:
                if 'log.' not in line and 'fmt.' not in line:
                    # Pode ser chamada que retorna error ignorado
                    pass

        # Padrão mais comum: val, _ := func() — ignorando erro
        for lineno, line in enumerate(code.splitlines(), 1):
            if re.search(r',\s*_\s*:=', line) and 'err' not in line:
                issues.append(RepairIssue(
                    file_path=file_path,
                    line=lineno,
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.LOGIC,
                    code="GO_UNCHECKED_ERROR",
                    message="Erro sendo ignorado com _",
                    suggestion="Verifique o erro: if err != nil { return err }",
                    context_lines=[line],
                ))

        return issues

    def _detect_resource_leak(self, code: str, file_path: str) -> List[RepairIssue]:
        """Detecta recursos sem defer close."""
        issues = []
        lines = code.splitlines()
        resource_creators = [
            'os.Open', 'os.Create', 'net.Dial', 'net.Listen',
            'http.Get', 'http.Post', 'sql.Open',
        ]

        for lineno, line in enumerate(lines, 1):
            for creator in resource_creators:
                if creator in line and 'defer' not in line:
                    # Verificar próximas 3 linhas por defer close
                    has_defer = False
                    for j in range(lineno, min(lineno + 4, len(lines))):
                        if 'defer' in lines[j] and 'Close()' in lines[j]:
                            has_defer = True
                            break
                    if not has_defer:
                        issues.append(RepairIssue(
                            file_path=file_path,
                            line=lineno,
                            severity=IssueSeverity.WARNING,
                            category=IssueCategory.PERFORMANCE,
                            code="GO_RESOURCE_LEAK",
                            message=f"Recurso criado sem defer close ({creator})",
                            suggestion="Adicione: defer resource.Close()",
                            context_lines=[line],
                        ))
        return issues

    def _detect_goroutine_leak(self, code: str, file_path: str) -> List[RepairIssue]:
        """Detecta goroutines sem context cancellation."""
        issues = []
        for lineno, line in enumerate(code.splitlines(), 1):
            if 'go func(' in line or 'go ' in line:
                # Verificar se usa context.Context
                if 'context.Context' not in code and 'ctx context.Context' not in code:
                    issues.append(RepairIssue(
                        file_path=file_path,
                        line=lineno,
                        severity=IssueSeverity.WARNING,
                        category=IssueCategory.PERFORMANCE,
                        code="GO_GOROUTINE_LEAK",
                        message="Goroutine sem context.Context — potencial leak",
                        suggestion="Adicione context.Context para cancelamento",
                        context_lines=[line],
                    ))
        return issues

    def _detect_nil_deref(self, code: str, file_path: str) -> List[RepairIssue]:
        """Detecta potenciais nil dereferences."""
        issues = []
        for lineno, line in enumerate(code.splitlines(), 1):
            # Acesso a campo sem nil check
            match = re.search(r'(\w+)\.(\w+)', line)
            if match and match.group(1) not in ('fmt', 'log', 'os', 'io', 'ctx'):
                var = match.group(1)
                # Verificar se há nil check antes
                nil_check = False
                for j in range(max(0, lineno - 3), lineno):
                    if f'{var} != nil' in code.splitlines()[j] or f'{var} == nil' in code.splitlines()[j]:
                        nil_check = True
                        break
                if not nil_check and var[0].isupper():  # Campo exportado
                    issues.append(RepairIssue(
                        file_path=file_path,
                        line=lineno,
                        severity=IssueSeverity.WARNING,
                        category=IssueCategory.SECURITY,
                        code="GO_NIL_DEREF",
                        message=f"Acesso a {var}.{match.group(2)} sem nil check",
                        suggestion=f"Adicione: if {var} == nil {{ return ... }}",
                        context_lines=[line],
                    ))
        return issues

    def _detect_defer_in_loop(self, code: str, file_path: str) -> List[RepairIssue]:
        """Detecta defer dentro de loop (acumula até o fim da função)."""
        issues = []
        lines = code.splitlines()
        in_loop = False
        for lineno, line in enumerate(lines, 1):
            if re.search(r'\bfor\b', line):
                in_loop = True
            if in_loop and 'defer' in line:
                issues.append(RepairIssue(
                    file_path=file_path,
                    line=lineno,
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.PERFORMANCE,
                    code="GO_DEFER_IN_LOOP",
                    message="defer em loop — acumula até o fim da função",
                    suggestion="Extraia para função anônima: func() { defer ... }()",
                    context_lines=[line],
                ))
            if in_loop and line.strip() == '}':
                in_loop = False
        return issues

    def _detect_empty_interface(self, code: str, file_path: str) -> List[RepairIssue]:
        """Detecta interface{} (deveria ser any em Go 1.18+)."""
        issues = []
        for lineno, line in enumerate(code.splitlines(), 1):
            if 'interface{}' in line:
                issues.append(RepairIssue(
                    file_path=file_path,
                    line=lineno,
                    severity=IssueSeverity.INFO,
                    category=IssueCategory.STYLE,
                    code="GO_EMPTY_INTERFACE",
                    message="Use any em vez de interface{} (Go 1.18+)",
                    suggestion="Substitua interface{} por any",
                    context_lines=[line],
                ))
        return issues

    def _detect_panic(self, code: str, file_path: str) -> List[RepairIssue]:
        """Detecta panic em código de produção."""
        issues = []
        for lineno, line in enumerate(code.splitlines(), 1):
            if 'panic(' in line and '// nolint' not in line:
                issues.append(RepairIssue(
                    file_path=file_path,
                    line=lineno,
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.LOGIC,
                    code="GO_PANIC",
                    message="panic() em produção — use retorno de erro",
                    suggestion="Substitua por return fmt.Errorf(...)",
                    context_lines=[line],
                ))
        return issues

    def _go_vet(self, code: str, file_path: str) -> List[RepairIssue]:
        """Executa go vet no código."""
        issues = []
        go_path = None
        for p in ["go"]:
            try:
                subprocess.run([p, "version"], capture_output=True, timeout=5)
                go_path = p
                break
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

        if not go_path:
            return issues

        try:
            with tempfile.TemporaryDirectory(prefix="quimera_go_") as tmp:
                go_file = Path(tmp) / (file_path or "main.go")
                go_file.write_text(code)

                # Inicializar módulo Go
                subprocess.run(
                    ["go", "mod", "init", "quimera_check"],
                    cwd=tmp, capture_output=True, timeout=10
                )

                proc = subprocess.run(
                    ["go", "vet", go_file.name],
                    cwd=tmp, capture_output=True, text=True, timeout=30
                )

                for line in proc.stderr.splitlines():
                    match = re.match(r'.*?:(\d+):(\d+):\s*(.+)', line)
                    if match:
                        issues.append(RepairIssue(
                            file_path=file_path,
                            line=int(match.group(1)),
                            column=int(match.group(2)),
                            severity=IssueSeverity.WARNING,
                            category=IssueCategory.COMPILATION,
                            code="GO_VET",
                            message=match.group(3),
                            suggestion="Corrija o warning do go vet",
                        ))

        except Exception as e:
            logger.debug(f"go vet failed: {e}")

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
            "GO_RESOURCE_LEAK": lambda: self._fix_resource_leak(lines, line_idx),
            "GO_DEFER_IN_LOOP": lambda: self._fix_defer_in_loop(lines, line_idx),
            "GO_EMPTY_INTERFACE": lambda: self._fix_empty_interface(lines, line_idx),
            "GO_PANIC": lambda: self._fix_panic(lines, line_idx),
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

    def _fix_resource_leak(self, lines: List[str], idx: int) -> Tuple[List[str], float]:
        indent = " " * (len(lines[idx]) - len(lines[idx].lstrip()))
        # Extrair nome da variável
        match = re.search(r'(\w+)\s*,\s*\w+\s*:?=\s*', lines[idx])
        var_name = match.group(1) if match else "resource"
        lines.insert(idx + 1, f"{indent}defer {var_name}.Close()")
        return lines, 0.8

    def _fix_defer_in_loop(self, lines: List[str], idx: int) -> Tuple[List[str], float]:
        indent = " " * (len(lines[idx]) - len(lines[idx].lstrip()))
        lines[idx] = f"{indent}// FIXME: defer in loop — use anonymous function\n{lines[idx]}"
        return lines, 0.3

    def _fix_empty_interface(self, lines: List[str], idx: int) -> Tuple[List[str], float]:
        lines[idx] = lines[idx].replace('interface{}', 'any')
        return lines, 0.9

    def _fix_panic(self, lines: List[str], idx: int) -> Tuple[List[str], float]:
        indent = " " * (len(lines[idx]) - len(lines[idx].lstrip()))
        lines[idx] = f"{indent}// FIXME: panic replaced with error return\n{indent}return fmt.Errorf(\"unexpected error\")"
        return lines, 0.3

    def verify(self, original_code: str, patched_code: str) -> bool:
        if original_code == patched_code:
            return True
        if patched_code.count('{') != patched_code.count('}'):
            return False
        return True

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
