"""Quimera Red Team — Geração de Exploits para Testar Patches Ofensivamente.

Princípio: "quebrar antes de entregar" — antes de aprovar um patch,
o Red Team tenta ativamente encontrar vulnerabilidades nele gerando
exploits automatizados.

Estratégias de ataque:
- Buffer Overflow: gerar inputs que excedem bounds
- Use-After-Free: sequências de alloc/free/use
- Race Condition: acessos concorrentes a recursos compartilhados
- Integer Overflow: inputs que causam wrap-around
- Format String: padrões de formato maliciosos
- Null Dereference: caminhos que levam a NULL ptr access

Arquitetura:
    Patch → [Analyze surface] → [Generate exploits] → [Execute in sandbox]
                ↓                      ↓                      ↓
        Attack vectors         Exploit payloads        Crash/PoC reports

Uso:
    from quimera.integration_backends.red_team import RedTeam
    
    red_team = RedTeam()
    findings = red_team.attack(patch_code, original_code)
    
    for finding in findings:
        if finding.exploitable:
            print(f"❌ {finding.vulnerability}: {finding.poc}")
"""

import logging
import random
import re
import time
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Set, Iterator
from enum import Enum
from pathlib import Path

from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================

class AttackVector(Enum):
    """Vetores de ataque que o Red Team pode usar."""
    BUFFER_OVERFLOW = "buffer_overflow"
    USE_AFTER_FREE = "use_after_free"
    DOUBLE_FREE = "double_free"
    NULL_DEREF = "null_deref"
    INTEGER_OVERFLOW = "integer_overflow"
    RACE_CONDITION = "race_condition"
    FORMAT_STRING = "format_string"
    STACK_EXHAUSTION = "stack_exhaustion"
    HEAP_SPRAY = "heap_spray"
    TYPE_CONFUSION = "type_confusion"


class ExploitComplexity(Enum):
    TRIVIAL = "trivial"         # Exploit direto, sem bypass
    MODERATE = "moderate"       # Precisa de certas condicoes
    COMPLEX = "complex"         # Multi-estagio, bypass de mitigacoes
    THEORETICAL = "theoretical" # Viavel em teoria, PoC incompleto


class ExploitReliability(Enum):
    RELIABLE = "reliable"       # Funciona sempre
    SOMETIMES = "sometimes"     # Funciona ~50% das vezes
    FRAGILE = "fragile"         # Depende de layout de memoria especifico
    UNTESTED = "untested"       # Gerado mas nao testado


@dataclass
class AttackSurface:
    """Superficie de ataque identificada no codigo."""
    vector: AttackVector
    location: str               # "linha 42", "funcao copy_buffer"
    line_number: int
    function_name: str
    description: str
    risk_score: float           # 0-1
    preconditions: List[str] = field(default_factory=list)
    code_snippet: str = ""


@dataclass
class ExploitPayload:
    """Payload de exploit gerado."""
    id: str
    vector: AttackVector
    target_surface: AttackSurface
    complexity: ExploitComplexity
    reliability: ExploitReliability
    code: str                   # Codigo C do exploit
    expected_behavior: str      # O que deve acontecer (crash, corrupcao, etc.)
    mitigation_bypasses: List[str] = field(default_factory=list)
    requires_sandbox: bool = True


@dataclass
class RedTeamFinding:
    """Resultado de um ataque do Red Team."""
    exploitable: bool
    payload: ExploitPayload
    poc_result: Optional[str] = None    # Output da execucao do PoC
    crash_type: Optional[str] = None    # SIGSEGV, SIGABRT, etc.
    remediation_suggestion: str = ""
    severity: str = "UNKNOWN"           # CRITICAL, HIGH, MEDIUM, LOW

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exploitable": self.exploitable,
            "vector": self.payload.vector.value,
            "complexity": self.payload.complexity.value,
            "severity": self.severity,
            "remediation": self.remediation_suggestion,
            "crash_type": self.crash_type,
        }


# ============================================================================
# Payload Generators
# ============================================================================

class ExploitGenerator:
    """Gera payloads de exploit para cada vetor de ataque."""

    _exploit_counter = 0

    @classmethod
    def _next_id(cls) -> str:
        cls._exploit_counter += 1
        return f"exploit_{cls._exploit_counter:04d}"

    @classmethod
    def buffer_overflow(cls, surface: AttackSurface) -> ExploitPayload:
        """Gera payload de buffer overflow."""
        buf_name = surface.code_snippet or "buf"
        code = f"""/* Quimera Red Team: Buffer Overflow PoC */
#include <string.h>
#include <stdio.h>

void test_overflow() {{
    char {buf_name}[16];
    /* Payload: escreve 256 bytes em buffer de 16 */
    memset({buf_name}, 'A', 256);
    {buf_name}[255] = '\\0';
    printf("Buffer: %s\\n", {buf_name});
}}
"""
        return ExploitPayload(
            id=cls._next_id(),
            vector=AttackVector.BUFFER_OVERFLOW,
            target_surface=surface,
            complexity=ExploitComplexity.TRIVIAL,
            reliability=ExploitReliability.RELIABLE,
            code=code,
            expected_behavior="Stack smashing / buffer overflow",
        )

    @classmethod
    def use_after_free(cls, surface: AttackSurface) -> ExploitPayload:
        """Gera payload de use-after-free."""
        code = """/* Quimera Red Team: Use-After-Free PoC */
#include <stdlib.h>
#include <stdio.h>

void test_uaf() {
    char *ptr = (char *)malloc(64);
    if (!ptr) return;
    strcpy(ptr, "sensitive_data");
    free(ptr);
    /* Use-After-Free: acessa memoria ja liberada */
    printf("UAF read: %s\\n", ptr);
    /* Corrompe heap metadata */
    strcpy(ptr, "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA");
}
"""
        return ExploitPayload(
            id=cls._next_id(),
            vector=AttackVector.USE_AFTER_FREE,
            target_surface=surface,
            complexity=ExploitComplexity.MODERATE,
            reliability=ExploitReliability.SOMETIMES,
            code=code,
            expected_behavior="Heap corruption / use-after-free read",
        )

    @classmethod
    def double_free(cls, surface: AttackSurface) -> ExploitPayload:
        """Gera payload de double-free."""
        code = """/* Quimera Red Team: Double-Free PoC */
#include <stdlib.h>

void test_double_free() {
    void *p = malloc(128);
    free(p);
    free(p);  /* Double free! */
}
"""
        return ExploitPayload(
            id=cls._next_id(),
            vector=AttackVector.DOUBLE_FREE,
            target_surface=surface,
            complexity=ExploitComplexity.TRIVIAL,
            reliability=ExploitReliability.RELIABLE,
            code=code,
            expected_behavior="Double free corruption / SIGABRT",
        )

    @classmethod
    def null_deref(cls, surface: AttackSurface) -> ExploitPayload:
        """Gera payload de null dereference."""
        code = """/* Quimera Red Team: NULL Dereference PoC */
#include <stdio.h>

struct data { int value; char *name; };

void test_null_deref() {
    struct data *d = NULL;
    /* NULL dereference */
    printf("Value: %d\\n", d->value);
}
"""
        return ExploitPayload(
            id=cls._next_id(),
            vector=AttackVector.NULL_DEREF,
            target_surface=surface,
            complexity=ExploitComplexity.TRIVIAL,
            reliability=ExploitReliability.RELIABLE,
            code=code,
            expected_behavior="Segmentation fault (SIGSEGV)",
        )

    @classmethod
    def integer_overflow(cls, surface: AttackSurface) -> ExploitPayload:
        """Gera payload de integer overflow."""
        code = """/* Quimera Red Team: Integer Overflow PoC */
#include <stdio.h>
#include <limits.h>
#include <stdlib.h>

void test_int_overflow() {
    int size = INT_MAX;
    /* Integer overflow: size + 1 = INT_MIN */
    char *buf = (char *)malloc(size + 1);
    if (!buf) {
        printf("Allocation failed (overflow prevented)\\n");
        return;
    }
    printf("Buffer allocated (should not happen)\\n");
    free(buf);
}
"""
        return ExploitPayload(
            id=cls._next_id(),
            vector=AttackVector.INTEGER_OVERFLOW,
            target_surface=surface,
            complexity=ExploitComplexity.TRIVIAL,
            reliability=ExploitReliability.RELIABLE,
            code=code,
            expected_behavior="Integer overflow in size calculation",
        )

    @classmethod
    def race_condition(cls, surface: AttackSurface) -> ExploitPayload:
        """Gera payload de race condition."""
        code = """/* Quimera Red Team: Race Condition PoC */
#include <pthread.h>
#include <stdio.h>

int shared_counter = 0;

void *increment(void *arg) {
    for (int i = 0; i < 100000; i++) {
        shared_counter++;  /* Race condition! Nao atomico */
    }
    return NULL;
}

void test_race() {
    pthread_t t1, t2;
    pthread_create(&t1, NULL, increment, NULL);
    pthread_create(&t2, NULL, increment, NULL);
    pthread_join(t1, NULL);
    pthread_join(t2, NULL);
    printf("Counter: %d (expected 200000)\\n", shared_counter);
}
"""
        return ExploitPayload(
            id=cls._next_id(),
            vector=AttackVector.RACE_CONDITION,
            target_surface=surface,
            complexity=ExploitComplexity.MODERATE,
            reliability=ExploitReliability.SOMETIMES,
            code=code,
            expected_behavior="Race condition: contador inconsistente",
        )

    @classmethod
    def format_string(cls, surface: AttackSurface) -> ExploitPayload:
        """Gera payload de format string."""
        code = """/* Quimera Red Team: Format String PoC */
#include <stdio.h>

void test_format_string() {
    char user_input[256] = "%x %x %x %x %x %s";
    /* Format string vulnerability: user_input como format */
    printf(user_input);
    printf("\\n");
}
"""
        return ExploitPayload(
            id=cls._next_id(),
            vector=AttackVector.FORMAT_STRING,
            target_surface=surface,
            complexity=ExploitComplexity.TRIVIAL,
            reliability=ExploitReliability.RELIABLE,
            code=code,
            expected_behavior="Memory leak via format string",
        )

    @classmethod
    def stack_exhaustion(cls, surface: AttackSurface) -> ExploitPayload:
        """Gera payload de exaustao de stack (recursao infinita)."""
        code = """/* Quimera Red Team: Stack Exhaustion PoC */
#include <stdio.h>

int deep_recursion(int n, char buf[4096]) {
    char local_buf[4096];
    if (n <= 0) return 0;
    return n + deep_recursion(n - 1, local_buf);
}

void test_stack_exhaustion() {
    printf("Starting deep recursion...\\n");
    int r = deep_recursion(10000, NULL);
    printf("Result: %d\\n", r);
}
"""
        return ExploitPayload(
            id=cls._next_id(),
            vector=AttackVector.STACK_EXHAUSTION,
            target_surface=surface,
            complexity=ExploitComplexity.TRIVIAL,
            reliability=ExploitReliability.RELIABLE,
            code=code,
            expected_behavior="Stack overflow / SIGSEGV",
        )

    # Mapa de vetor → gerador
    _GENERATORS = {
        AttackVector.BUFFER_OVERFLOW: buffer_overflow,
        AttackVector.USE_AFTER_FREE: use_after_free,
        AttackVector.DOUBLE_FREE: double_free,
        AttackVector.NULL_DEREF: null_deref,
        AttackVector.INTEGER_OVERFLOW: integer_overflow,
        AttackVector.RACE_CONDITION: race_condition,
        AttackVector.FORMAT_STRING: format_string,
        AttackVector.STACK_EXHAUSTION: stack_exhaustion,
    }

    @classmethod
    def generate(cls, surface: AttackSurface) -> ExploitPayload:
        """Gera payload para uma superficie de ataque."""
        gen = cls._GENERATORS.get(surface.vector)
        if gen:
            return gen.__func__(surface)
        # Fallback
        return ExploitPayload(
            id=cls._next_id(),
            vector=surface.vector,
            target_surface=surface,
            complexity=ExploitComplexity.MODERATE,
            reliability=ExploitReliability.UNTESTED,
            code=f"/* Exploit for {surface.vector.value} */\n/* Target: {surface.description} */",
            expected_behavior="Unknown",
        )


# ============================================================================
# RedTeam — Motor Principal
# ============================================================================

class RedTeam:
    """Equipe ofensiva automatizada que testa patches gerando exploits.

    Principio: "Se voce nao consegue quebrar seu proprio codigo,
    outra pessoa vai."

    Attributes:
        aggressiveness: 0-1, quantos vetores de ataque tentar.
        max_exploits_per_vector: Limite de exploits por vetor.
        sandbox_executor: Funcao opcional para executar exploits em sandbox.
    """

    # Padroes de vulnerabilidade para analise de superficie de ataque
    _ATTACK_PATTERNS = [
        (
            AttackVector.BUFFER_OVERFLOW,
            [
                (r'\bstrcpy\s*\(', 0.9, "strcpy sem bounds check"),
                (r'\bgets\s*\(', 1.0, "gets() inerentemente inseguro"),
                (r'\bsprintf\s*\(', 0.8, "sprintf sem bounds check"),
                (r'\bstrcat\s*\(', 0.7, "strcat sem bounds check"),
                (r'\bmemcpy\s*\([^,]+,[^,]+,\s*(\w+)', 0.6, "memcpy sem validacao de size"),
                (r'\bscanf\s*\([^)]*%s', 0.8, "scanf %s sem bounds"),
            ]
        ),
        (
            AttackVector.USE_AFTER_FREE,
            [
                (r'\bfree\s*\((\w+)\)', 0.4, "free() — potencial UAF se reutilizado"),
            ]
        ),
        (
            AttackVector.NULL_DEREF,
            [
                (r'(\w+)->(\w+)', 0.3, "acesso a ponteiro sem verificacao NULL"),
                (r'\*(\w+)\s*=', 0.2, "dereferencia sem NULL check"),
            ]
        ),
        (
            AttackVector.INTEGER_OVERFLOW,
            [
                (r'\bint\s+\w+\s*=\s*\w+\s*\+\s*\w+', 0.3, "soma de inteiros sem check"),
                (r'\bmalloc\s*\(\s*\w+\s*\*\s*\w+\s*\)', 0.6, "malloc com multiplicacao"),
            ]
        ),
        (
            AttackVector.FORMAT_STRING,
            [
                (r'\bprintf\s*\(\s*\w+\s*\)', 0.6, "printf com string de usuario"),
                (r'\bfprintf\s*\([^,]+,\s*\w+\s*\)', 0.5, "fprintf com format string variavel"),
            ]
        ),
        (
            AttackVector.RACE_CONDITION,
            [
                (r'\bpthread_create\s*\(', 0.4, "criacao de thread — potencial race"),
                (r'\bstatic\s+\w+\s+\w+\s*=', 0.3, "variavel estatica compartilhada"),
                (r'\bglobal\s+\w+', 0.4, "variavel global sem protecao"),
            ]
        ),
    ]

    def __init__(
        self,
        aggressiveness: float = 0.8,
        max_exploits_per_vector: int = 2,
        sandbox_executor: Optional[callable] = None,
    ):
        self.aggressiveness = aggressiveness
        self.max_exploits_per_vector = max_exploits_per_vector
        self.sandbox_executor = sandbox_executor

        self._findings_history: List[RedTeamFinding] = []
        self._total_attacks = 0
        self._successful_attacks = 0

    # ------------------------------------------------------------------
    # API Principal
    # ------------------------------------------------------------------

    def attack(
        self,
        patch_code: str,
        original_code: str = "",
        vectors: Optional[List[str]] = None,
    ) -> List[RedTeamFinding]:
        """Executa ataque completo contra um patch.

        Args:
            patch_code: Codigo do patch a ser atacado.
            original_code: Codigo original para diff.
            vectors: Vetores de ataque especificos. None = todos.

        Returns:
            Lista de RedTeamFindings com exploits e resultados.
        """
        montar_log(
            f"RedTeam: iniciando ataque contra patch "
            f"({len(patch_code.splitlines())} linhas, aggressiveness={self.aggressiveness})",
            "INFO"
        )

        start = time.time()
        findings: List[RedTeamFinding] = []

        # 1. Analisar superficie de ataque
        surfaces = self._analyze_attack_surface(patch_code, vectors)

        montar_log(
            f"RedTeam: {len(surfaces)} superficies de ataque identificadas",
            "INFO"
        )

        # 2. Gerar exploits
        for surface in surfaces:
            # Sempre processar superficies de alto risco (>0.5),
            # usar aggressiveness como filtro apenas para baixo risco
            if surface.risk_score < 0.5 and random.random() > self.aggressiveness:
                continue

            # Gerar 1-2 exploits por superficie
            n_exploits = min(
                self.max_exploits_per_vector,
                random.randint(1, 2)
            )
            for _ in range(n_exploits):
                self._total_attacks += 1
                payload = ExploitGenerator.generate(surface)

                # 3. Executar em sandbox se disponivel
                finding = self._execute_exploit(payload)

                if finding.exploitable:
                    self._successful_attacks += 1
                    montar_log(
                        f"RedTeam: ❌ {finding.severity} {finding.payload.vector.value}: "
                        f"{finding.crash_type or 'exploitavel'}",
                        "WARNING"
                    )

                findings.append(finding)

        elapsed = (time.time() - start) * 1000
        montar_log(
            f"RedTeam: ataque concluido em {elapsed:.0f}ms — "
            f"{self._successful_attacks}/{self._total_attacks} exploits bem-sucedidos, "
            f"{len(findings)} findings",
            "INFO" if self._successful_attacks == 0 else "WARNING"
        )

        self._findings_history.extend(findings)
        return findings

    def quick_attack(self, patch_code: str) -> Tuple[bool, str]:
        """Ataque rapido (apenas vetores triviais). Ideal para CI/CD."""
        findings = self.attack(
            patch_code,
            vectors=["buffer_overflow", "null_deref", "format_string", "double_free"]
        )
        exploitable = [f for f in findings if f.exploitable]
        if exploitable:
            return False, (
                f"{len(exploitable)} vulnerabilidades: "
                + "; ".join(f.payload.vector.value for f in exploitable[:3])
            )
        return True, "Quick attack passed"

    # ------------------------------------------------------------------
    # Analise de Superficie
    # ------------------------------------------------------------------

    def _analyze_attack_surface(
        self,
        code: str,
        filter_vectors: Optional[List[str]] = None,
    ) -> List[AttackSurface]:
        """Analisa o codigo em busca de superficies de ataque."""
        surfaces: List[AttackSurface] = []
        lines = code.splitlines()

        allowed_vectors = None
        if filter_vectors:
            allowed_vectors = set(filter_vectors)

        for vector, patterns in self._ATTACK_PATTERNS:
            if allowed_vectors and vector.value not in allowed_vectors:
                continue

            for pattern, base_risk, desc in patterns:
                for lineno, line in enumerate(lines, start=1):
                    match = re.search(pattern, line)
                    if not match:
                        continue

                    # Contexto: funcao em que esta
                    func_name = self._find_enclosing_function(lines, lineno)

                    # Ajustar risco baseado em contexto
                    risk = base_risk
                    if 'if' in line and 'NULL' in line:
                        risk *= 0.5  # Tem NULL check visivel
                    if 'static' in line or 'const' in line:
                        risk *= 0.7

                    surfaces.append(AttackSurface(
                        vector=vector,
                        location=f"linha {lineno}",
                        line_number=lineno,
                        function_name=func_name,
                        description=desc,
                        risk_score=min(1.0, risk),
                        preconditions=[],
                        code_snippet=line.strip()[:200],
                    ))

        # Ordenar por risco
        surfaces.sort(key=lambda s: s.risk_score, reverse=True)
        return surfaces

    def _find_enclosing_function(self, lines: List[str], lineno: int) -> str:
        """Encontra a funcao que contem uma linha."""
        for i in range(lineno - 1, -1, -1):
            match = re.search(
                r'^\s*(?:static\s+)?(?:inline\s+)?'
                r'(?:void|int|char|long|short|float|double|unsigned|struct\s+\w+)'
                r'\s+(\w+)\s*\([^)]*\)',
                lines[i]
            )
            if match:
                return match.group(1)
        return "<unknown>"

    # ------------------------------------------------------------------
    # Execucao de Exploits
    # ------------------------------------------------------------------

    def _execute_exploit(self, payload: ExploitPayload) -> RedTeamFinding:
        """Executa um exploit e retorna o finding."""
        finding = RedTeamFinding(
            exploitable=False,
            payload=payload,
            remediation_suggestion=self._suggest_remediation(payload.vector),
        )

        if self.sandbox_executor:
            try:
                result = self.sandbox_executor(payload.code)
                if result.get("crashed"):
                    finding.exploitable = True
                    finding.crash_type = result.get("signal", "UNKNOWN")
                    finding.poc_result = result.get("output", "")
                    finding.severity = self._assess_severity(
                        payload.vector, result
                    )
                else:
                    finding.poc_result = "No crash detected"
            except Exception as e:
                logger.warning(f"Sandbox execution failed: {e}")
        else:
            # Sem sandbox: avaliacao heuristica
            finding.exploitable = (
                payload.complexity in (
                    ExploitComplexity.TRIVIAL,
                    ExploitComplexity.MODERATE,
                )
                and payload.reliability != ExploitReliability.UNTESTED
            )
            if finding.exploitable:
                finding.severity = self._assess_severity_heuristic(payload)
                finding.crash_type = "HEURISTIC"
            finding.poc_result = "Heuristic assessment (no sandbox)"

        return finding

    # ------------------------------------------------------------------
    # Avaliacao
    # ------------------------------------------------------------------

    def _assess_severity(
        self,
        vector: AttackVector,
        result: Dict[str, Any],
    ) -> str:
        """Avalia severidade baseada no resultado da execucao."""
        signal = result.get("signal", "")
        if signal in ("SIGSEGV", "SIGABRT", "SIGBUS"):
            if vector in (AttackVector.BUFFER_OVERFLOW, AttackVector.USE_AFTER_FREE):
                return "CRITICAL"
            return "HIGH"
        if signal in ("SIGILL",):
            return "HIGH"
        return "MEDIUM"

    def _assess_severity_heuristic(self, payload: ExploitPayload) -> str:
        """Avalia severidade heuristicamente."""
        critical_vectors = {
            AttackVector.BUFFER_OVERFLOW,
            AttackVector.USE_AFTER_FREE,
            AttackVector.DOUBLE_FREE,
        }
        high_vectors = {
            AttackVector.NULL_DEREF,
            AttackVector.INTEGER_OVERFLOW,
            AttackVector.FORMAT_STRING,
        }
        if payload.vector in critical_vectors:
            return "CRITICAL"
        if payload.vector in high_vectors:
            return "HIGH"
        return "MEDIUM"

    def _suggest_remediation(self, vector: AttackVector) -> str:
        """Sugere remediacao para um vetor de ataque."""
        suggestions = {
            AttackVector.BUFFER_OVERFLOW:
                "Use strncpy/snprintf com bounds checking. Adicione __CPROVER_assert de bounds.",
            AttackVector.USE_AFTER_FREE:
                "Defina ponteiro como NULL apos free(). Use static analysis para tracking de lifetime.",
            AttackVector.DOUBLE_FREE:
                "Defina ponteiro como NULL apos free(). Adicione asserts de nao-NULL antes de free.",
            AttackVector.NULL_DEREF:
                "Adicione verificacao if (ptr == NULL) antes de dereferenciar.",
            AttackVector.INTEGER_OVERFLOW:
                "Use __builtin_add_overflow() ou checks explicitos antes de operacoes.",
            AttackVector.RACE_CONDITION:
                "Proteja acessos com mutex/spinlock. Use atomic_t para contadores.",
            AttackVector.FORMAT_STRING:
                "Use printf(\"%s\", var) em vez de printf(var).",
        }
        return suggestions.get(
            vector,
            "Revise o codigo para mitigar este vetor de ataque."
        )

    # ------------------------------------------------------------------
    # Estatisticas
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatisticas do Red Team."""
        return {
            "total_attacks": self._total_attacks,
            "successful_attacks": self._successful_attacks,
            "success_rate": (
                self._successful_attacks / max(self._total_attacks, 1)
            ),
            "aggressiveness": self.aggressiveness,
            "history_size": len(self._findings_history),
        }

    def get_last_findings(self, n: int = 10) -> List[Dict[str, Any]]:
        """Retorna os ultimos N findings."""
        return [f.to_dict() for f in self._findings_history[-n:]]
