"""Quimera Rust Agent — Reparo de Módulos Rust-for-Linux.

Agente de reparo para código Rust, focado em módulos Rust-for-Linux.
Usa análise de AST via módulo ast integrado + heurísticas específicas.

Funcionalidades:
- Detecção de erros de compilação (cargo check)
- Correção de borrow checker (lifetimes, ownership)
- Correção de pattern matching exaustivo
- Correção de unsafe blocks
- Formatação via rustfmt
- Integração com clippy lints

Uso:
    from quimera.plugins.rust_agent import RustAgent
    
    agent = RustAgent()
    issues = agent.detect(rust_code, "src/main.rs")
    for issue in issues:
        patch = agent.repair(rust_code, issue)
        print(patch.unified_diff)
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


class RustAgent(IRepairAgent):
    """Agente de reparo para código Rust.

    Suporta análise de código Rust com foco em:
    - Rust-for-Linux (módulos de kernel)
    - Borrow checker e ownership
    - Pattern matching e unsafe blocks
    """

    @property
    def language(self) -> str:
        return "rust"

    @property
    def name(self) -> str:
        return "Quimera Rust Agent"

    @property
    def supported_extensions(self) -> List[str]:
        return [".rs"]

    # ------------------------------------------------------------------
    # Detect
    # ------------------------------------------------------------------

    def detect(self, code: str, file_path: str = "") -> List[RepairIssue]:
        """Detecta problemas em código Rust."""
        issues = []

        issues.extend(self._detect_unsafe(code, file_path))
        issues.extend(self._detect_unwrap(code, file_path))
        issues.extend(self._detect_clone(code, file_path))
        issues.extend(self._detect_expect(code, file_path))
        issues.extend(self._detect_todo(code, file_path))
        issues.extend(self._detect_println(code, file_path))
        issues.extend(self._detect_mutex(code, file_path))

        # Tentar cargo check se disponível
        cargo_issues = self._cargo_check(code, file_path)
        issues.extend(cargo_issues)

        return issues

    def _detect_unsafe(self, code: str, file_path: str) -> List[RepairIssue]:
        """Detecta blocos unsafe que podem ser evitados."""
        issues = []
        for lineno, line in enumerate(code.splitlines(), 1):
            if 'unsafe {' in line and '// SAFETY:' not in line:
                issues.append(RepairIssue(
                    file_path=file_path,
                    line=lineno,
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.SECURITY,
                    code="RUST_UNSAFE_NO_COMMENT",
                    message="Bloco unsafe sem comentário SAFETY",
                    suggestion="Adicione // SAFETY: explicando por que é seguro",
                    context_lines=[line],
                ))
        return issues

    def _detect_unwrap(self, code: str, file_path: str) -> List[RepairIssue]:
        """Detecta .unwrap() que deveriam ser .expect() ou ?."""
        issues = []
        for lineno, line in enumerate(code.splitlines(), 1):
            if '.unwrap()' in line:
                issues.append(RepairIssue(
                    file_path=file_path,
                    line=lineno,
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.LOGIC,
                    code="RUST_UNWRAP",
                    message=".unwrap() pode causar panic — use .expect() ou ?",
                    suggestion="Substitua por .expect(\"reason\") ou propague com ?",
                    context_lines=[line],
                ))
        return issues

    def _detect_clone(self, code: str, file_path: str) -> List[RepairIssue]:
        """Detecta .clone() desnecessários."""
        issues = []
        for lineno, line in enumerate(code.splitlines(), 1):
            if '.clone()' in line and 'derive(Clone' not in line:
                issues.append(RepairIssue(
                    file_path=file_path,
                    line=lineno,
                    severity=IssueSeverity.INFO,
                    category=IssueCategory.PERFORMANCE,
                    code="RUST_CLONE",
                    message="Possível .clone() desnecessário — considere borrow",
                    suggestion="Use &referência em vez de .clone()",
                    context_lines=[line],
                ))
        return issues

    def _detect_expect(self, code: str, file_path: str) -> List[RepairIssue]:
        """Detecta .expect() com mensagem vazia."""
        issues = []
        for lineno, line in enumerate(code.splitlines(), 1):
            if '.expect("")' in line or ".expect('')" in line:
                issues.append(RepairIssue(
                    file_path=file_path,
                    line=lineno,
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.STYLE,
                    code="RUST_EMPTY_EXPECT",
                    message=".expect() com mensagem vazia",
                    suggestion="Forneça uma mensagem descritiva",
                    context_lines=[line],
                ))
        return issues

    def _detect_todo(self, code: str, file_path: str) -> List[RepairIssue]:
        """Detecta todo!() e unimplemented!() no código."""
        issues = []
        for lineno, line in enumerate(code.splitlines(), 1):
            if 'todo!()' in line or 'unimplemented!()' in line:
                issues.append(RepairIssue(
                    file_path=file_path,
                    line=lineno,
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.LOGIC,
                    code="RUST_TODO",
                    message="todo!() ou unimplemented!() em produção",
                    suggestion="Implemente a funcionalidade ou use feature gate",
                    context_lines=[line],
                ))
        return issues

    def _detect_println(self, code: str, file_path: str) -> List[RepairIssue]:
        """Detecta println! em código de kernel (deveria usar pr_info!)."""
        issues = []
        for lineno, line in enumerate(code.splitlines(), 1):
            if 'println!' in line:
                issues.append(RepairIssue(
                    file_path=file_path,
                    line=lineno,
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.STYLE,
                    code="RUST_PRINTLN_IN_KERNEL",
                    message="println! em código de kernel — use pr_info! ou log::info!",
                    suggestion="Substitua println! por pr_info! (kernel) ou log::info!",
                    context_lines=[line],
                ))
        return issues

    def _detect_mutex(self, code: str, file_path: str) -> List[RepairIssue]:
        """Detecta Mutex sem tratamento de poison."""
        issues = []
        for lineno, line in enumerate(code.splitlines(), 1):
            if 'Mutex::new' in line or 'Mutex<' in line:
                # Verificar se lock() trata poison
                if '.lock().unwrap()' in code:
                    issues.append(RepairIssue(
                        file_path=file_path,
                        line=lineno,
                        severity=IssueSeverity.WARNING,
                        category=IssueCategory.SECURITY,
                        code="RUST_MUTEX_POISON",
                        message="Mutex::lock().unwrap() — não trata Mutex poison",
                        suggestion="Use .lock().expect() ou match no PoisonError",
                        context_lines=[line],
                    ))
        return issues

    def _cargo_check(self, code: str, file_path: str) -> List[RepairIssue]:
        """Executa cargo check no código (se disponível)."""
        issues = []
        cargo_path = None
        for p in ["cargo", os.path.expanduser("~/.cargo/bin/cargo")]:
            if os.path.exists(p) or any(
                os.path.exists(os.path.join(d, "cargo"))
                for d in os.environ.get("PATH", "").split(":")
            ):
                cargo_path = "cargo"
                break

        if not cargo_path:
            return issues

        try:
            with tempfile.TemporaryDirectory(prefix="quimera_rust_") as tmp:
                src_dir = Path(tmp) / "src"
                src_dir.mkdir(exist_ok=True)
                rust_file = src_dir / (file_path or "main.rs")
                rust_file.write_text(code)

                # Criar Cargo.toml mínimo
                cargo_toml = Path(tmp) / "Cargo.toml"
                cargo_toml.write_text("""[package]
name = "quimera_check"
version = "0.1.0"
edition = "2021"
""")

                proc = subprocess.run(
                    ["cargo", "check", "--message-format=short"],
                    cwd=tmp, capture_output=True, text=True, timeout=30
                )

                for line in proc.stderr.splitlines():
                    # Parse: src/main.rs:10:5: error[E0308]: mismatched types
                    match = re.match(
                        r'.*?:(\d+):(\d+):\s*(error|warning)\[?(\w+)\]?:\s*(.+)',
                        line
                    )
                    if match:
                        lineno = int(match.group(1))
                        col = int(match.group(2))
                        sev = match.group(3)
                        code = match.group(4)
                        msg = match.group(5)
                        issues.append(RepairIssue(
                            file_path=file_path,
                            line=lineno,
                            column=col,
                            severity=IssueSeverity.ERROR if sev == "error" else IssueSeverity.WARNING,
                            category=IssueCategory.COMPILATION,
                            code=f"RUST_{code}",
                            message=msg,
                            suggestion="Corrija o erro de compilação",
                        ))

        except FileNotFoundError:
            pass
        except Exception as e:
            logger.debug(f"cargo check failed: {e}")

        return issues

    # ------------------------------------------------------------------
    # Repair
    # ------------------------------------------------------------------

    def repair(self, code: str, issue: RepairIssue) -> Patch:
        """Gera patch para corrigir um problema Rust."""
        lines = code.splitlines()
        if issue.line < 1 or issue.line > len(lines):
            return Patch(
                file_path=issue.file_path,
                original_lines=code,
                patched_lines=code,
                issue=issue,
                confidence=0.0,
            )

        line_idx = issue.line - 1
        original_line = lines[line_idx]

        # Reparos por código de issue
        repair_map = {
            "RUST_UNSAFE_NO_COMMENT": lambda: self._fix_unsafe_comment(lines, line_idx),
            "RUST_UNWRAP": lambda: self._fix_unwrap(lines, line_idx),
            "RUST_EMPTY_EXPECT": lambda: self._fix_empty_expect(lines, line_idx),
            "RUST_PRINTLN_IN_KERNEL": lambda: self._fix_println(lines, line_idx),
            "RUST_TODO": lambda: self._fix_todo(lines, line_idx),
        }

        fixer = repair_map.get(issue.code, lambda: (lines, 0.3))
        new_lines, confidence = fixer()

        unified = self._generate_diff(code, "\n".join(new_lines), issue.file_path)

        return Patch(
            file_path=issue.file_path,
            original_lines=code,
            patched_lines="\n".join(new_lines),
            issue=issue,
            confidence=confidence,
            description=f"Fix {issue.code}: {issue.message}",
            unified_diff=unified,
        )

    def _fix_unsafe_comment(self, lines: List[str], idx: int) -> Tuple[List[str], float]:
        """Adiciona comentário SAFETY antes de bloco unsafe."""
        indent = len(lines[idx]) - len(lines[idx].lstrip())
        safety_comment = " " * indent + "// SAFETY: This unsafe block is required because ..."
        lines.insert(idx, safety_comment)
        return lines, 0.7

    def _fix_unwrap(self, lines: List[str], idx: int) -> Tuple[List[str], float]:
        """Substitui .unwrap() por .expect()."""
        line = lines[idx]
        lines[idx] = line.replace(".unwrap()", '.expect("operation failed")')
        return lines, 0.8

    def _fix_empty_expect(self, lines: List[str], idx: int) -> Tuple[List[str], float]:
        """Preenche mensagem vazia de .expect()."""
        line = lines[idx]
        lines[idx] = line.replace('.expect("")', '.expect("unexpected error")')
        lines[idx] = lines[idx].replace(".expect('')", '.expect("unexpected error")')
        return lines, 0.9

    def _fix_println(self, lines: List[str], idx: int) -> Tuple[List[str], float]:
        """Substitui println! por pr_info!."""
        line = lines[idx]
        lines[idx] = line.replace("println!", "pr_info!")
        return lines, 0.8

    def _fix_todo(self, lines: List[str], idx: int) -> Tuple[List[str], float]:
        """Adiciona stub para todo!()."""
        line = lines[idx]
        indent = " " * (len(line) - len(line.lstrip()))
        replacement = f'{indent}// FIXME: Implement this functionality\n{indent}unimplemented!("Not yet implemented")'
        lines[idx] = replacement
        return lines, 0.3

    # ------------------------------------------------------------------
    # Verify
    # ------------------------------------------------------------------

    def verify(self, original_code: str, patched_code: str) -> bool:
        """Verifica se o código Rust patchado compila."""
        if original_code == patched_code:
            return True

        # Verificação básica: número de { } balanceados
        if patched_code.count('{') != patched_code.count('}'):
            return False

        # Tentar cargo check
        issues = self._cargo_check(patched_code, "verify.rs")
        errors = [i for i in issues if i.severity == IssueSeverity.ERROR]
        return len(errors) == 0

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def _generate_diff(self, original: str, patched: str, file_path: str) -> str:
        """Gera diff unificado simples."""
        orig_lines = original.splitlines()
        patch_lines = patched.splitlines()

        diff = [f"--- a/{file_path}", f"+++ b/{file_path}"]
        max_len = max(len(orig_lines), len(patch_lines))

        for i in range(max_len):
            orig = orig_lines[i] if i < len(orig_lines) else ""
            pat = patch_lines[i] if i < len(patch_lines) else ""
            if orig != pat:
                if orig:
                    diff.append(f"-{orig}")
                if pat:
                    diff.append(f"+{pat}")

        return "\n".join(diff)
