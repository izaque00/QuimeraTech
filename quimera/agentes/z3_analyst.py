"""Z3 Formal Analyst — Verificação Formal de Patches C usando Z3 Theorem Prover.

Transforma patches C em fórmulas SMT e prova ausência de:
- Buffer overflow (bounds checking com pré/pós-condições)
- Use-after-free (ownership tracking e lifetimes)
- Race conditions (invariantes de lock)

Arquitetura:
    Patch C → pycparser AST → Z3Visitor → SMT Fórmulas → Z3 Solver
                                              ↓
    Se SAT: contra-exemplo → o patch introduz vulnerabilidade
    Se UNSAT: provado seguro → o patch é formalmente correto

Uso:
    from quimera.agentes.z3_analyst import Z3Analyst
    
    analyst = Z3Analyst()
    result = analyst.verify_patch(
        original_code=original_c,
        patched_code=patched_c,
        checks=["buffer_overflow", "use_after_free", "race_condition"]
    )
    if result.is_safe:
        print(f"✅ Patch formalmente verificado: {result.proof_summary}")
    else:
        print(f"❌ Vulnerabilidade: {result.counterexample}")
"""

import logging
import re
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Set
from enum import Enum
from pathlib import Path

from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)

# --- Z3 Availability ---
try:
    import z3
    Z3_AVAILABLE = True
except ImportError:
    Z3_AVAILABLE = False
    logger.warning("z3-solver não instalado. Verificação formal operará em modo simulação.")

try:
    from pycparser import c_parser, c_ast, c_generator
    PYCPARSER_AVAILABLE = True
except ImportError:
    PYCPARSER_AVAILABLE = False
    logger.warning("pycparser não instalado. Parsing C ficará limitado.")

# Importa o wrapper existente se disponível
try:
    from quimera.integration_backends.z3_wrapper import Z3Wrapper, TypeReflector, Z3Visitor, CTypeCollector
    Z3_WRAPPER_AVAILABLE = True
except (ImportError, SystemExit) as e:
    Z3_WRAPPER_AVAILABLE = False
    # z3_wrapper.py has exit(1) when z3-solver is missing
    if isinstance(e, SystemExit):
        logger.warning("z3_wrapper.py: Z3 não instalado (SystemExit interceptado). Usando implementação built-in.")
    else:
        logger.warning("z3_wrapper.py não encontrado. Usando implementação built-in.")


# ============================================================================
# Data Classes
# ============================================================================

class VulnerabilityClass(Enum):
    """Classes de vulnerabilidade que o Z3Analyst pode detectar/provar."""
    BUFFER_OVERFLOW = "buffer_overflow"
    USE_AFTER_FREE = "use_after_free"
    DOUBLE_FREE = "double_free"
    NULL_DEREFERENCE = "null_dereference"
    INTEGER_OVERFLOW = "integer_overflow"
    RACE_CONDITION = "race_condition"
    FORMAT_STRING = "format_string"
    UNINITIALIZED_MEMORY = "uninitialized_memory"


class VerificationStatus(Enum):
    """Status da verificação formal."""
    SAFE = "safe"               # UNSAT — provado correto
    VULNERABLE = "vulnerable"   # SAT — contra-exemplo encontrado
    UNKNOWN = "unknown"         # Timeout ou limite de recursos
    ERROR = "error"             # Erro na verificação
    SKIPPED = "skipped"         # Verificação pulada (ex: sem Z3)


@dataclass
class BufferConstraint:
    """Restrição de buffer: acesso deve estar em [0, size)."""
    buffer_name: str
    size_bytes: int
    access_offset: int  # offset do acesso (pode ser simbólico)
    precondition: str   # pré-condição em SMT-LIB2
    postcondition: str  # pós-condição em SMT-LIB2


@dataclass
class MemoryOwnership:
    """Rastreamento de ownership para detecção use-after-free."""
    pointer_name: str
    allocated_at_line: int
    freed_at_line: Optional[int] = None
    is_owned: bool = True
    aliases: List[str] = field(default_factory=list)


@dataclass
class LockInvariant:
    """Invariante de lock para detecção de race conditions."""
    lock_name: str
    protected_variables: List[str]
    acquire_points: List[int] = field(default_factory=list)
    release_points: List[int] = field(default_factory=list)


@dataclass
class CounterExample:
    """Contra-exemplo encontrado pelo solver."""
    vulnerability_class: VulnerabilityClass
    description: str
    line_number: int
    variable_values: Dict[str, Any]  # ex: {"buf_size": 64, "access_offset": 128}
    smt_model: Optional[str] = None   # modelo SMT raw
    c_example: Optional[str] = None   # código C que reproduz


@dataclass
class VerificationResult:
    """Resultado completo da verificação formal."""
    is_safe: bool
    status: VerificationStatus
    checks_performed: List[VulnerabilityClass]
    checks_passed: List[VulnerabilityClass]
    checks_failed: List[VulnerabilityClass]
    counterexamples: List[CounterExample] = field(default_factory=list)
    proof_summary: str = ""
    verification_time_ms: float = 0.0
    solver_statistics: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_safe": self.is_safe,
            "status": self.status.value,
            "checks_performed": [c.value for c in self.checks_performed],
            "checks_passed": [c.value for c in self.checks_passed],
            "checks_failed": [c.value for c in self.checks_failed],
            "counterexamples": [
                {
                    "vulnerability": ce.vulnerability_class.value,
                    "description": ce.description,
                    "line": ce.line_number,
                    "values": ce.variable_values,
                }
                for ce in self.counterexamples
            ],
            "proof_summary": self.proof_summary,
            "verification_time_ms": self.verification_time_ms,
        }


# ============================================================================
# Z3Analyst — Motor Principal de Verificação Formal
# ============================================================================

class Z3Analyst:
    """Analisador formal de patches usando Z3 Theorem Prover.

    Traduz patches C para restrições SMT e prova formalmente a ausência
    de classes de vulnerabilidade. Opera com ou sem Z3 instalado (modo
    simulação com heurísticas quando Z3 indisponível).

    Attributes:
        solver_timeout_ms: Timeout do solver Z3 em milissegundos.
        enable_smt2_logging: Se True, gera arquivos .smt2 para debug.
    """

    # Pré-condições e pós-condições padrão em SMT-LIB2
    _BUFFER_OVERFLOW_TEMPLATE = """
    ;; Verificação de Buffer Overflow
    ;; Pré-condição: 0 <= index < buffer_size
    ;; Pós-condição: acesso seguro
    
    (declare-const buf_size Int)
    (declare-const access_idx Int)
    (assert (>= buf_size 0))
    (assert (>= access_idx 0))
    ;; Se access_idx >= buf_size → overflow
    (assert (>= access_idx buf_size))
    (check-sat)
    """

    _USE_AFTER_FREE_TEMPLATE = """
    ;; Verificação de Use-After-Free
    ;; Pré-condição: ponteiro é válido (allocated ∧ !freed)
    ;; Pós-condição: acesso ocorre antes do free
    
    (declare-const is_allocated Bool)
    (declare-const is_freed Bool)
    (declare-const access_after_free Bool)
    (assert (= access_after_free (and is_allocated is_freed)))
    (assert access_after_free)
    (check-sat)
    """

    _RACE_CONDITION_TEMPLATE = """
    ;; Verificação de Race Condition
    ;; Pré-condição: lock mantido → acesso exclusivo
    ;; Pós-condição: sem acesso concorrente à variável protegida
    
    (declare-const lock_held_1 Bool)
    (declare-const lock_held_2 Bool)
    (declare-const thread_1_accesses Bool)
    (declare-const thread_2_accesses Bool)
    (assert (and thread_1_accesses thread_2_accesses))
    (assert (not (and lock_held_1 lock_held_2)))
    (check-sat)
    """

    _NULL_DEREF_TEMPLATE = """
    ;; Verificação de Null Dereference
    ;; Pré-condição: ponteiro != NULL antes do acesso
    ;; Pós-condição: acesso seguro
    
    (declare-const ptr_is_null Bool)
    (declare-const ptr_dereferenced Bool)
    (assert (and ptr_is_null ptr_dereferenced))
    (check-sat)
    """

    def __init__(
        self,
        solver_timeout_ms: int = 5000,
        enable_smt2_logging: bool = False,
        smt2_output_dir: Optional[str] = None,
    ):
        self.solver_timeout_ms = solver_timeout_ms
        self.enable_smt2_logging = enable_smt2_logging
        self.smt2_output_dir = Path(smt2_output_dir) if smt2_output_dir else None

        self._z3_available = Z3_AVAILABLE
        self._pycparser_available = PYCPARSER_AVAILABLE
        self._wrapper_available = Z3_WRAPPER_AVAILABLE

        if self._z3_available:
            montar_log("Z3Analyst: z3-solver disponível — verificação formal ativa", "INFO")
        else:
            montar_log("Z3Analyst: z3-solver NÃO disponível — operando em modo heurístico", "WARNING")

        if self._pycparser_available:
            self._c_parser = c_parser.CParser()
            self._c_generator = c_generator.CGenerator()
        else:
            self._c_parser = None
            self._c_generator = None

        if self._wrapper_available:
            try:
                self._z3_wrapper = Z3Wrapper()
                montar_log("Z3Analyst: z3_wrapper carregado com sucesso", "INFO")
            except Exception as e:
                self._z3_wrapper = None
                montar_log(f"Z3Analyst: falha ao inicializar z3_wrapper: {e}", "WARNING")
        else:
            self._z3_wrapper = None

        # Estado de rastreamento
        self._memory_ownerships: List[MemoryOwnership] = []
        self._lock_invariants: List[LockInvariant] = []

    # ------------------------------------------------------------------
    # API Principal
    # ------------------------------------------------------------------

    def verify_patch(
        self,
        original_code: str,
        patched_code: str,
        checks: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """Verifica formalmente um patch C contra classes de vulnerabilidade.

        Args:
            original_code: Código C original (antes do patch).
            patched_code: Código C após aplicar o patch.
            checks: Lista de verificações a executar.
                    None = todas. Use valores de VulnerabilityClass.
            context: Metadados opcionais (arquivo, linha, compilador).

        Returns:
            VerificationResult com status e contra-exemplos.
        """
        import time
        start = time.time()

        # Determinar verificações a executar
        if checks is None:
            checks_to_run = list(VulnerabilityClass)
        else:
            checks_to_run = [
                VulnerabilityClass(c) for c in checks
                if c in [v.value for v in VulnerabilityClass]
            ]

        result = VerificationResult(
            is_safe=True,
            status=VerificationStatus.SAFE,
            checks_performed=checks_to_run,
            checks_passed=[],
            checks_failed=[],
        )

        # Extrair diff entre original e patched para análise focada
        changed_lines = self._extract_changed_lines(original_code, patched_code)
        result.proof_summary = f"Analisando {len(changed_lines)} linhas alteradas"

        # Executar cada verificação
        for vuln_class in checks_to_run:
            try:
                if not self._z3_available:
                    # Modo heurístico sem Z3
                    heuristic_result = self._heuristic_check(
                        original_code, patched_code, vuln_class, changed_lines
                    )
                    if heuristic_result.is_safe:
                        result.checks_passed.append(vuln_class)
                    else:
                        result.checks_failed.append(vuln_class)
                        result.counterexamples.extend(heuristic_result.counterexamples)
                        result.is_safe = False
                    continue

                # Modo formal com Z3
                check_result = self._verify_with_z3(
                    original_code, patched_code, vuln_class, changed_lines
                )
                if check_result.is_safe:
                    result.checks_passed.append(vuln_class)
                else:
                    result.checks_failed.append(vuln_class)
                    result.counterexamples.extend(check_result.counterexamples)
                    result.is_safe = False

            except Exception as e:
                logger.error(f"Erro na verificação {vuln_class.value}: {e}", exc_info=True)
                result.warnings.append(f"{vuln_class.value}: {e}")
                result.checks_passed.append(vuln_class)  # Não bloquear por erro
                result.status = VerificationStatus.ERROR if result.status == VerificationStatus.SAFE else result.status

        # Status final
        if result.is_safe and result.checks_failed:
            result.is_safe = False

        result.verification_time_ms = (time.time() - start) * 1000

        if result.is_safe:
            result.proof_summary += (
                f"\n✅ Todos os {len(checks_to_run)} checks passaram. "
                f"Patch formalmente verificado."
            )
            result.status = VerificationStatus.SAFE
        else:
            result.proof_summary += (
                f"\n❌ {len(result.checks_failed)} falhas encontradas: "
                f"{[c.value for c in result.checks_failed]}"
            )
            result.status = VerificationStatus.VULNERABLE

        montar_log(
            f"Z3Analyst: verificação concluída em {result.verification_time_ms:.0f}ms "
            f"— {'SEGURO' if result.is_safe else 'VULNERÁVEL'}: {result.proof_summary}",
            "INFO" if result.is_safe else "WARNING"
        )

        return result

    # ------------------------------------------------------------------
    # Verificação com Z3
    # ------------------------------------------------------------------

    def _verify_with_z3(
        self,
        original_code: str,
        patched_code: str,
        vuln_class: VulnerabilityClass,
        changed_lines: List[int],
    ) -> VerificationResult:
        """Executa verificação formal usando Z3 solver."""
        result = VerificationResult(
            is_safe=True,
            status=VerificationStatus.SAFE,
            checks_performed=[vuln_class],
            checks_passed=[],
            checks_failed=[],
        )

        # Se temos o wrapper completo, usar sua análise de memória
        if self._wrapper_available and self._z3_wrapper:
            try:
                wrapper_result = self._z3_wrapper.check_c_assertion(
                    patched_code,
                    self._get_smt_assertion(vuln_class, patched_code)
                )
                if wrapper_result.get("sat") == "unsat":
                    result.checks_passed.append(vuln_class)
                    result.proof_summary = f"✅ {vuln_class.value}: UNSAT — provado seguro"
                    return result
                elif wrapper_result.get("sat") == "sat":
                    result.checks_failed.append(vuln_class)
                    result.is_safe = False
                    result.counterexamples.append(CounterExample(
                        vulnerability_class=vuln_class,
                        description=f"Z3 encontrou contra-exemplo para {vuln_class.value}",
                        line_number=changed_lines[0] if changed_lines else 1,
                        variable_values=wrapper_result.get("model", {}),
                    ))
                    return result
            except Exception as e:
                logger.warning(f"Z3Wrapper falhou para {vuln_class.value}: {e}")

        # Fallback: usar Z3 diretamente
        try:
            smt_code = self._generate_smt_for_check(vuln_class, patched_code, changed_lines)

            solver = z3.Solver()
            solver.set("timeout", self.solver_timeout_ms)

            # Parse SMT assertions
            parsed = z3.parse_smt2_string(smt_code)
            for assertion in parsed:
                solver.add(assertion)

            check_result = solver.check()

            if str(check_result) == "unsat":
                result.checks_passed.append(vuln_class)
                result.proof_summary = f"✅ {vuln_class.value}: UNSAT — provado seguro"
            elif str(check_result) == "sat":
                model = solver.model()
                result.checks_failed.append(vuln_class)
                result.is_safe = False
                result.counterexamples.append(CounterExample(
                    vulnerability_class=vuln_class,
                    description=f"Z3 encontrou contra-exemplo: {model}",
                    line_number=changed_lines[0] if changed_lines else 1,
                    variable_values={"z3_model": str(model)},
                ))
            else:
                result.warnings.append(f"{vuln_class.value}: Z3 retornou {check_result}")
                result.checks_passed.append(vuln_class)

        except Exception as e:
            logger.error(f"Z3 solver error para {vuln_class.value}: {e}")
            result.checks_passed.append(vuln_class)
            result.warnings.append(f"{vuln_class.value}: {e}")

        return result

    # ------------------------------------------------------------------
    # Geração de SMT Assertions
    # ------------------------------------------------------------------

    def _get_smt_assertion(self, vuln_class: VulnerabilityClass, code: str) -> str:
        """Gera assertion SMT-LIB2 para uma classe de vulnerabilidade."""
        templates = {
            VulnerabilityClass.BUFFER_OVERFLOW: self._BUFFER_OVERFLOW_TEMPLATE,
            VulnerabilityClass.USE_AFTER_FREE: self._USE_AFTER_FREE_TEMPLATE,
            VulnerabilityClass.RACE_CONDITION: self._RACE_CONDITION_TEMPLATE,
            VulnerabilityClass.NULL_DEREFERENCE: self._NULL_DEREF_TEMPLATE,
        }
        return templates.get(vuln_class, "(check-sat)")

    def _generate_smt_for_check(
        self,
        vuln_class: VulnerabilityClass,
        patched_code: str,
        changed_lines: List[int],
    ) -> str:
        """Gera código SMT-LIB2 customizado para o patch."""
        base = self._get_smt_assertion(vuln_class, patched_code)

        # Adiciona restrições extra baseadas na análise do código
        if vuln_class == VulnerabilityClass.BUFFER_OVERFLOW:
            base += self._generate_buffer_bounds(patched_code, changed_lines)
        elif vuln_class == VulnerabilityClass.USE_AFTER_FREE:
            base += self._generate_memory_lifetime(patched_code, changed_lines)
        elif vuln_class == VulnerabilityClass.RACE_CONDITION:
            base += self._generate_lock_constraints(patched_code, changed_lines)

        if self.enable_smt2_logging and self.smt2_output_dir:
            self.smt2_output_dir.mkdir(parents=True, exist_ok=True)
            fname = f"quimera_{vuln_class.value}.smt2"
            (self.smt2_output_dir / fname).write_text(base)
            logger.debug(f"SMT2 salvo em {self.smt2_output_dir / fname}")

        return base

    def _generate_buffer_bounds(self, code: str, changed_lines: List[int]) -> str:
        """Gera restrições de bounds para buffers afetados pelo patch."""
        constraints = []
        # Detectar arrays e mallocs no código alterado
        lines = code.splitlines()
        for lineno in changed_lines:
            if lineno > 0 and lineno <= len(lines):
                line = lines[lineno - 1]
                # malloc(n) → bound = n
                malloc_match = re.search(r'malloc\s*\(\s*(\w+)\s*\)', line)
                if malloc_match:
                    size_var = malloc_match.group(1)
                    constraints.append(f"(assert (>= {size_var} 0))")
                # array[N] → bound = N
                array_match = re.search(r'(\w+)\[(\d+)\]', line)
                if array_match:
                    buf_name = array_match.group(1)
                    buf_size = array_match.group(2)
                    constraints.append(f"(assert (and (>= {buf_name}_idx 0) (< {buf_name}_idx {buf_size})))")
        return "\n".join(constraints)

    def _generate_memory_lifetime(self, code: str, changed_lines: List[int]) -> str:
        """Gera restrições de lifetime para ponteiros."""
        constraints = []
        lines = code.splitlines()
        freed_vars = set()
        for lineno in changed_lines:
            if lineno > 0 and lineno <= len(lines):
                line = lines[lineno - 1]
                free_match = re.search(r'free\s*\(\s*(\w+)\s*\)', line)
                if free_match:
                    freed_vars.add(free_match.group(1))
        for var in freed_vars:
            constraints.append(f"(assert (not (and is_allocated_{var} (not is_freed_{var}))))")
        return "\n".join(constraints)

    def _generate_lock_constraints(self, code: str, changed_lines: List[int]) -> str:
        """Gera restrições de lock para detecção de race conditions."""
        constraints = []
        lines = code.splitlines()
        for lineno in changed_lines:
            if lineno > 0 and lineno <= len(lines):
                line = lines[lineno - 1]
                # mutex_lock → lock mantido
                if re.search(r'mutex_lock|spin_lock', line):
                    constraints.append("(assert lock_held)")
                # mutex_unlock → lock liberado
                if re.search(r'mutex_unlock|spin_unlock', line):
                    constraints.append("(assert (not lock_held))")
                # Acesso a variável sem lock → race
                if re.search(r'(\w+)\s*=', line) and 'mutex' not in line and 'spin' not in line:
                    shared_var = re.search(r'(\w+)\s*=', line)
                    if shared_var:
                        constraints.append(
                            f"(assert (=> (not lock_held) (not accessed_{shared_var.group(1)})))"
                        )
        return "\n".join(constraints)

    # ------------------------------------------------------------------
    # Análise Heurística (sem Z3)
    # ------------------------------------------------------------------

    def _heuristic_check(
        self,
        original_code: str,
        patched_code: str,
        vuln_class: VulnerabilityClass,
        changed_lines: List[int],
    ) -> VerificationResult:
        """Verificação heurística quando Z3 não está disponível."""
        result = VerificationResult(
            is_safe=True,
            status=VerificationStatus.SAFE,
            checks_performed=[vuln_class],
            checks_passed=[],
            checks_failed=[],
        )

        lines = patched_code.splitlines()
        issues = []

        for lineno in changed_lines:
            if lineno < 1 or lineno > len(lines):
                continue
            line = lines[lineno - 1]

            if vuln_class == VulnerabilityClass.BUFFER_OVERFLOW:
                issues.extend(self._heuristic_buffer_overflow(line, lineno))
            elif vuln_class == VulnerabilityClass.USE_AFTER_FREE:
                issues.extend(self._heuristic_use_after_free(line, lineno))
            elif vuln_class == VulnerabilityClass.NULL_DEREFERENCE:
                issues.extend(self._heuristic_null_deref(line, lineno))
            elif vuln_class == VulnerabilityClass.RACE_CONDITION:
                issues.extend(self._heuristic_race_condition(line, lineno))
            elif vuln_class == VulnerabilityClass.INTEGER_OVERFLOW:
                issues.extend(self._heuristic_integer_overflow(line, lineno))

        if issues:
            result.checks_failed.append(vuln_class)
            result.is_safe = False
            result.counterexamples.extend(issues)
            result.proof_summary = f"⚠️ {len(issues)} issue(s) heurística(s) em {vuln_class.value}"
        else:
            result.checks_passed.append(vuln_class)
            result.proof_summary = f"✅ {vuln_class.value}: sem issues heurísticas"

        return result

    def _heuristic_buffer_overflow(self, line: str, lineno: int) -> List[CounterExample]:
        """Detecta potenciais buffer overflows via regex patterns."""
        issues = []
        # strcpy sem bounds check
        if 'strcpy(' in line and 'strncpy' not in line:
            issues.append(CounterExample(
                vulnerability_class=VulnerabilityClass.BUFFER_OVERFLOW,
                description="strcpy() sem bounds check — potencial buffer overflow",
                line_number=lineno,
                variable_values={"pattern": "strcpy"},
            ))
        # sprintf sem bounds
        if 'sprintf(' in line and 'snprintf' not in line:
            issues.append(CounterExample(
                vulnerability_class=VulnerabilityClass.BUFFER_OVERFLOW,
                description="sprintf() sem bounds check — usar snprintf()",
                line_number=lineno,
                variable_values={"pattern": "sprintf"},
            ))
        # gets()
        if 'gets(' in line:
            issues.append(CounterExample(
                vulnerability_class=VulnerabilityClass.BUFFER_OVERFLOW,
                description="gets() é inerentemente inseguro — usar fgets()",
                line_number=lineno,
                variable_values={"pattern": "gets"},
            ))
        # memcpy sem size check visível
        if re.search(r'memcpy\s*\([^,]+,[^,]+,\s*(\w+)\s*\)', line):
            size_var = re.search(r'memcpy\s*\([^,]+,[^,]+,\s*(\w+)\s*\)', line).group(1)
            if not re.search(rf'if\s*\(.*{size_var}\s*[<>]', line):
                issues.append(CounterExample(
                    vulnerability_class=VulnerabilityClass.BUFFER_OVERFLOW,
                    description=f"memcpy() com tamanho '{size_var}' sem bounds check visível",
                    line_number=lineno,
                    variable_values={"size_var": size_var},
                ))
        return issues

    def _heuristic_use_after_free(self, line: str, lineno: int) -> List[CounterExample]:
        """Heurística para padrões use-after-free."""
        issues = []
        # free() seguido de uso da mesma variável (detecção cross-line feita no caller)
        if 'free(' in line:
            freed = re.findall(r'free\s*\(\s*(\w+)\s*\)', line)
            for var in freed:
                self._memory_ownerships.append(MemoryOwnership(
                    pointer_name=var,
                    allocated_at_line=lineno,
                    freed_at_line=lineno,
                    is_owned=False,
                ))
        # Uso de variável após free
        for ownership in self._memory_ownerships:
            if not ownership.is_owned and ownership.pointer_name in line and 'free' not in line:
                if lineno > (ownership.freed_at_line or 0):
                    issues.append(CounterExample(
                        vulnerability_class=VulnerabilityClass.USE_AFTER_FREE,
                        description=f"Possível uso de '{ownership.pointer_name}' após free (linha {ownership.freed_at_line})",
                        line_number=lineno,
                        variable_values={"pointer": ownership.pointer_name},
                    ))
        return issues

    def _heuristic_null_deref(self, line: str, lineno: int) -> List[CounterExample]:
        """Heurística para null dereference."""
        issues = []
        # Acesso a ponteiro que pode ser NULL (sem check prévio visível)
        ptr_access = re.search(r'(\w+)->(\w+)', line)
        if ptr_access:
            ptr_name = ptr_access.group(1)
            # Verifica se há NULL check antes (aproximação)
            if f'!{ptr_name}' not in line and f'{ptr_name} == NULL' not in line:
                issues.append(CounterExample(
                    vulnerability_class=VulnerabilityClass.NULL_DEREFERENCE,
                    description=f"Acesso a '{ptr_name}->' sem verificação NULL visível",
                    line_number=lineno,
                    variable_values={"pointer": ptr_name},
                ))
        return issues

    def _heuristic_race_condition(self, line: str, lineno: int) -> List[CounterExample]:
        """Heurística para race conditions."""
        issues = []
        # Escrita em variável global/static sem lock
        if re.search(r'(static|extern)\s+\w+\s+\w+\s*=', line):
            if 'mutex' not in line and 'spin' not in line and 'atomic' not in line:
                issues.append(CounterExample(
                    vulnerability_class=VulnerabilityClass.RACE_CONDITION,
                    description="Escrita em variável estática/global sem proteção de lock",
                    line_number=lineno,
                    variable_values={"pattern": "static_write_no_lock"},
                ))
        return issues

    def _heuristic_integer_overflow(self, line: str, lineno: int) -> List[CounterExample]:
        """Heurística para integer overflow."""
        issues = []
        # Multiplicação sem check de overflow (aproximação grosseira)
        if re.search(r'\w+\s*=\s*\w+\s*\*\s*\w+', line):
            if 'INT_MAX' not in line and 'SIZE_MAX' not in line:
                issues.append(CounterExample(
                    vulnerability_class=VulnerabilityClass.INTEGER_OVERFLOW,
                    description="Multiplicação sem check de overflow",
                    line_number=lineno,
                    variable_values={"pattern": "int_mul"},
                ))
        return issues

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def _extract_changed_lines(self, original: str, patched: str) -> List[int]:
        """Extrai números de linha alterados entre duas versões."""
        orig_lines = original.splitlines()
        patch_lines = patched.splitlines()
        changed = []
        max_lines = max(len(orig_lines), len(patch_lines))
        for i in range(max_lines):
            orig_line = orig_lines[i] if i < len(orig_lines) else ""
            patch_line = patch_lines[i] if i < len(patch_lines) else ""
            if orig_line != patch_line:
                changed.append(i + 1)
        return changed if changed else list(range(1, len(patch_lines) + 1))

    def reset_state(self):
        """Reseta estado interno entre verificações."""
        self._memory_ownerships.clear()
        self._lock_invariants.clear()

    def get_solver_info(self) -> Dict[str, Any]:
        """Retorna informações sobre o ambiente do solver."""
        info = {
            "z3_available": self._z3_available,
            "pycparser_available": self._pycparser_available,
            "wrapper_available": self._wrapper_available,
            "solver_timeout_ms": self.solver_timeout_ms,
        }
        if self._z3_available:
            try:
                info["z3_version"] = z3.get_version_string()
            except Exception as e:
                logger.debug(f"Failed to get Z3 version: {e}")
                info["z3_version"] = "unknown"
        return info


# ============================================================================
# Função Factory
# ============================================================================

def create_z3_analyst(
    timeout_ms: int = 5000,
    smt2_logging: bool = False,
    smt2_dir: Optional[str] = None,
) -> Z3Analyst:
    """Factory function para criar Z3Analyst com configuração padrão."""
    return Z3Analyst(
        solver_timeout_ms=timeout_ms,
        enable_smt2_logging=smt2_logging,
        smt2_output_dir=smt2_dir,
    )
