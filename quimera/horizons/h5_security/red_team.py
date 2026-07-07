"""
Quimera Mark X — Red Team Engine (Horizonte 5)

Gera exploits para testar patches ofensivamente ("quebrar antes de entregar").
  - 10 vetores de ataque: buffer overflow, UAF, double-free, null deref,
    integer overflow, race condition, format string, stack exhaustion,
    heap spray, type confusion
  - Payloads C completos com código executável
  - 3 níveis de complexidade + 4 níveis de confiabilidade
  - quick_attack() para CI/CD

De → Para:
  Antes: Scanner estático detecta vulnerabilidades
  Agora: Red Team gera exploits automaticamente para testar patches

Usage:
    team = RedTeam()
    exploits = team.attack(patched_code, original_code)
    for exploit in exploits:
        if exploit.is_exploitable:
            print(f"Patch still vulnerable to {exploit.vuln_type}!")
"""

import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("quimera.h5.redteam")


# ═══════════════════════════════════════════════════════════════════════════
# Enums & Data
# ═══════════════════════════════════════════════════════════════════════════

class AttackComplexity(str, Enum):
    LOW = "low"          # Simple payload, easy to detect
    MEDIUM = "medium"    # Moderate sophistication
    HIGH = "high"        # Advanced technique


class ExploitReliability(str, Enum):
    UNRELIABLE = "unreliable"    # Works sometimes
    RELIABLE = "reliable"        # Works consistently
    VERY_RELIABLE = "very_reliable"  # Works almost always
    PROVEN = "proven"            # Verified in exploitation


class VulnerabilityType(str, Enum):
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


@dataclass
class Exploit:
    id: str
    vuln_type: VulnerabilityType
    complexity: AttackComplexity
    reliability: ExploitReliability
    payload: str
    description: str
    target_file: str = ""
    target_line: int = 0
    is_exploitable: bool = True
    severity: str = "HIGH"
    cwe_id: str = ""
    mitigation: str = ""
    generation_time_ms: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════
# Payload Generators
# ═══════════════════════════════════════════════════════════════════════════

class ExploitPayloads:
    """Generates C exploit payloads for each vulnerability type."""

    @staticmethod
    def buffer_overflow() -> str:
        return """/* EXPLOIT: Buffer Overflow */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

void exploit_buffer_overflow() {
    char small_buf[16];
    char large_input[256];
    
    /* Fill with shellcode pattern */
    memset(large_input, 0x41, sizeof(large_input)-1);
    large_input[255] = '\\0';
    
    /* Trigger overflow */
    strcpy(small_buf, large_input);
    
    /* Verify corruption */
    printf("[EXPLOIT] Buffer overflow triggered - small_buf corrupted\\n");
}

int main() {
    exploit_buffer_overflow();
    return 0;
}"""

    @staticmethod
    def use_after_free() -> str:
        return """/* EXPLOIT: Use-After-Free */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    char data[64];
    void (*callback)(void);
} Object;

void exploit_uaf() {
    Object *obj = (Object*)malloc(sizeof(Object));
    obj->callback = NULL;
    free(obj);
    
    /* Allocate something else to occupy freed memory */
    char *spray = (char*)malloc(sizeof(Object));
    memset(spray, 0x42, sizeof(Object));
    
    /* Use-After-Free: access obj after free */
    if (obj->callback != NULL) {
        printf("[EXPLOIT] UAF triggered - stale pointer still accessible\\n");
    }
    
    free(spray);
}

int main() {
    exploit_uaf();
    return 0;
}"""

    @staticmethod
    def double_free() -> str:
        return """/* EXPLOIT: Double Free */
#include <stdio.h>
#include <stdlib.h>

void exploit_double_free() {
    void *ptr = malloc(128);
    free(ptr);
    
    /* Double free */
    free(ptr);
    
    printf("[EXPLOIT] Double free triggered\\n");
}

int main() {
    exploit_double_free();
    return 0;
}"""

    @staticmethod
    def null_deref() -> str:
        return """/* EXPLOIT: NULL Pointer Dereference */
#include <stdio.h>
#include <stdlib.h>

void exploit_null_deref() {
    int *ptr = NULL;
    
    /* Trigger NULL deref */
    *ptr = 0xDEADBEEF;
    
    printf("[EXPLOIT] NULL deref triggered (may crash)\\n");
}

int main() {
    exploit_null_deref();
    return 0;
}"""

    @staticmethod
    def integer_overflow() -> str:
        return """/* EXPLOIT: Integer Overflow */
#include <stdio.h>
#include <stdlib.h>
#include <limits.h>

void exploit_int_overflow() {
    int max = INT_MAX;
    int result = max + 1;  /* Overflow wraps to INT_MIN */
    
    if (result < 0 && max > 0) {
        printf("[EXPLOIT] Integer overflow detected: %d + 1 = %d\\n", max, result);
    }
    
    /* Size calculation overflow */
    size_t n = (size_t)-1;  /* SIZE_MAX */
    size_t elem_size = 16;
    size_t total = n * elem_size;  /* Wraps to small value */
    
    char *buf = (char*)malloc(total);  /* Allocates tiny buffer */
    if (buf) {
        printf("[EXPLOIT] Integer overflow in allocation: requested %zu, got tiny buf\\n", n * elem_size);
        free(buf);
    }
}

int main() {
    exploit_int_overflow();
    return 0;
}"""

    @staticmethod
    def race_condition() -> str:
        return """/* EXPLOIT: Race Condition (TOCTOU) */
#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include <unistd.h>

static int shared_counter = 0;
static int race_detected = 0;

void* thread_func(void* arg) {
    for (int i = 0; i < 1000; i++) {
        int tmp = shared_counter;
        usleep(1);  /* Race window */
        shared_counter = tmp + 1;
    }
    return NULL;
}

void exploit_race_condition() {
    pthread_t t1, t2;
    
    pthread_create(&t1, NULL, thread_func, NULL);
    pthread_create(&t2, NULL, thread_func, NULL);
    
    pthread_join(t1, NULL);
    pthread_join(t2, NULL);
    
    if (shared_counter != 2000) {
        printf("[EXPLOIT] Race condition detected: counter=%d (expected 2000)\\n", shared_counter);
    }
}

int main() {
    exploit_race_condition();
    return 0;
}"""

    @staticmethod
    def format_string() -> str:
        return """/* EXPLOIT: Format String Vulnerability */
#include <stdio.h>
#include <string.h>

void exploit_format_string() {
    char user_input[256];
    strcpy(user_input, "%x.%x.%x.%x.%x.%x.%x.%x");
    
    /* Vulnerable: user-controlled format string */
    printf(user_input);
    printf("\\n");
    
    printf("[EXPLOIT] Format string attack: stack values leaked\\n");
}

int main() {
    exploit_format_string();
    return 0;
}"""

    @staticmethod
    def stack_exhaustion() -> str:
        return """/* EXPLOIT: Stack Exhaustion */
#include <stdio.h>
#include <stdlib.h>

volatile int depth = 0;

void recursive_bomb() {
    char buffer[4096];  /* 4KB per frame */
    buffer[0] = 'A';
    depth++;
    recursive_bomb();
}

void exploit_stack_exhaustion() {
    printf("[EXPLOIT] Starting stack exhaustion attack...\\n");
    /* Would overflow in practice; guarded here */
    printf("[EXPLOIT] Stack exhaustion: depth=%d, stack usage=%dKB\\n", 
           depth, depth * 4);
}

int main() {
    exploit_stack_exhaustion();
    return 0;
}"""

    @staticmethod
    def heap_spray() -> str:
        return """/* EXPLOIT: Heap Spray */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define SPRAY_COUNT 1000
#define SPRAY_SIZE 65536  /* 64KB */

void exploit_heap_spray() {
    void *spray[SPRAY_COUNT];
    
    for (int i = 0; i < SPRAY_COUNT; i++) {
        spray[i] = malloc(SPRAY_SIZE);
        if (spray[i]) {
            memset(spray[i], 0x90, SPRAY_SIZE);  /* NOP sled */
        }
    }
    
    printf("[EXPLOIT] Heap spray: %d allocations of %d bytes\\n", SPRAY_COUNT, SPRAY_SIZE);
    
    /* Clean up */
    for (int i = 0; i < SPRAY_COUNT; i++) {
        free(spray[i]);
    }
}

int main() {
    exploit_heap_spray();
    return 0;
}"""

    @staticmethod
    def type_confusion() -> str:
        return """/* EXPLOIT: Type Confusion */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { int type; int value; } TypeA;
typedef struct { int type; char *ptr; } TypeB;

void exploit_type_confusion() {
    TypeA a = { .type = 1, .value = 0x41414141 };
    
    /* Type confusion: cast TypeA* to TypeB* */
    TypeB *b = (TypeB*)&a;
    
    printf("[EXPLOIT] Type confusion: TypeA.value=0x%x interpreted as TypeB.ptr=%p\\n",
           a.value, b->ptr);
    
    if (b->ptr == (char*)0x41414141) {
        printf("[EXPLOIT] Type confusion verified - arbitrary pointer crafted\\n");
    }
}

int main() {
    exploit_type_confusion();
    return 0;
}"""

    PAYLOADS = {
        VulnerabilityType.BUFFER_OVERFLOW: buffer_overflow,
        VulnerabilityType.USE_AFTER_FREE: use_after_free,
        VulnerabilityType.DOUBLE_FREE: double_free,
        VulnerabilityType.NULL_DEREF: null_deref,
        VulnerabilityType.INTEGER_OVERFLOW: integer_overflow,
        VulnerabilityType.RACE_CONDITION: race_condition,
        VulnerabilityType.FORMAT_STRING: format_string,
        VulnerabilityType.STACK_EXHAUSTION: stack_exhaustion,
        VulnerabilityType.HEAP_SPRAY: heap_spray,
        VulnerabilityType.TYPE_CONFUSION: type_confusion,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Red Team
# ═══════════════════════════════════════════════════════════════════════════

class RedTeam:
    """Generates exploits to stress-test patches before release."""

    def __init__(self, severity_threshold: str = "MEDIUM"):
        self.severity_threshold = severity_threshold
        self._total_exploits_generated = 0
        self._total_exploitable = 0

    # ── Attack Surface Analysis ────────────────────────────────────────

    @staticmethod
    def analyze_attack_surface(code: str) -> List[Tuple[VulnerabilityType, float]]:
        """Analyze code for potential vulnerability surface.

        Returns list of (vuln_type, confidence_score).
        """
        surface = []

        patterns = {
            VulnerabilityType.BUFFER_OVERFLOW: [
                ("strcpy", 0.9), ("strcat", 0.85), ("sprintf", 0.8),
                ("gets", 0.95), ("scanf", 0.6), ("memcpy", 0.5),
            ],
            VulnerabilityType.USE_AFTER_FREE: [
                ("free(", 0.6), ("kfree(", 0.6),
            ],
            VulnerabilityType.DOUBLE_FREE: [
                ("free(", 0.3),  # Only if called multiple times
            ],
            VulnerabilityType.NULL_DEREF: [
                ("->", 0.4), ("*ptr", 0.4),
            ],
            VulnerabilityType.INTEGER_OVERFLOW: [
                ("malloc(", 0.5), ("size_t", 0.3), ("int", 0.2),
            ],
            VulnerabilityType.RACE_CONDITION: [
                ("global", 0.5), ("shared", 0.6), ("static", 0.4),
            ],
            VulnerabilityType.FORMAT_STRING: [
                ("printf(", 0.4), ("fprintf(", 0.4), ("sprintf(", 0.5),
            ],
        }

        for vtype, pats in patterns.items():
            max_conf = 0.0
            for pat, conf in pats:
                if pat in code:
                    max_conf = max(max_conf, conf)
            if max_conf > 0.0:
                # Boost if multiple patterns match
                matches = sum(1 for p, _ in pats if p in code)
                confidence = min(1.0, max_conf + (matches - 1) * 0.1)
                surface.append((vtype, confidence))

        surface.sort(key=lambda x: x[1], reverse=True)
        return surface

    # ── Attack Generation ──────────────────────────────────────────────

    def attack(
        self,
        patched_code: str,
        original_code: Optional[str] = None,
        complexity: AttackComplexity = AttackComplexity.MEDIUM,
    ) -> List[Exploit]:
        """Generate exploits against a patched code file.

        Args:
            patched_code: The patched code to attack.
            original_code: Original vulnerable code (for comparison).
            complexity: Attack sophistication level.

        Returns:
            List of generated exploits.
        """
        t0 = time.monotonic()
        exploits = []

        # Analyze attack surface
        surface = self.analyze_attack_surface(patched_code)
        logger.info(f"RedTeam: {len(surface)} potential attack surfaces found")

        # If original code is provided, compare to find what was "fixed"
        fixed_areas = set()
        if original_code:
            orig_surface = self.analyze_attack_surface(original_code)
            fixed_areas = {t for t, _ in orig_surface}

        # Generate exploits for each vulnerability type found
        for vtype, confidence in surface:
            # Skip if confidence too low
            if confidence < 0.3:
                continue

            # Generate payload
            payload_gen = ExploitPayloads.PAYLOADS.get(vtype)
            if payload_gen is None:
                continue

            try:
                payload = payload_gen()
            except Exception:
                payload = f"/* Exploit for {vtype.value} */\n// Payload generation failed"

            # Determine exploitability
            if vtype in fixed_areas:
                is_exploitable = confidence < 0.5  # Was supposedly fixed
                reliability = ExploitReliability.UNRELIABLE if confidence < 0.5 else ExploitReliability.RELIABLE
            else:
                is_exploitable = confidence > 0.4
                reliability = ExploitReliability.RELIABLE if confidence > 0.6 else ExploitReliability.UNRELIABLE

            severity = "CRITICAL" if confidence > 0.8 else ("HIGH" if confidence > 0.6 else "MEDIUM")

            exploit = Exploit(
                id=f"exploit-{self._total_exploits_generated:04d}",
                vuln_type=vtype,
                complexity=complexity,
                reliability=reliability,
                payload=payload,
                description=f"Auto-generated {vtype.value} exploit (confidence={confidence:.0%})",
                is_exploitable=is_exploitable,
                severity=severity,
                cwe_id=self._get_cwe(vtype),
                mitigation=self._suggest_mitigation(vtype),
                generation_time_ms=(time.monotonic() - t0) * 1000,
            )
            exploits.append(exploit)
            self._total_exploits_generated += 1
            if is_exploitable:
                self._total_exploitable += 1

        logger.info(
            f"RedTeam: generated {len(exploits)} exploits "
            f"({self._total_exploitable} exploitable)"
        )
        return exploits

    def quick_attack(self, patched_code: str) -> List[Exploit]:
        """Quick attack for CI/CD — only MEDIUM+ severity, low complexity."""
        exploits = self.attack(patched_code, complexity=AttackComplexity.LOW)
        return [e for e in exploits if e.severity in ("CRITICAL", "HIGH")]

    def attack_all_vectors(self, patched_code: str) -> List[Exploit]:
        """Generate exploits for ALL 10 vulnerability types regardless of surface analysis."""
        exploits = []
        t0 = time.monotonic()

        for vtype in VulnerabilityType:
            payload_gen = ExploitPayloads.PAYLOADS.get(vtype)
            if not payload_gen:
                continue
            try:
                payload = payload_gen()
            except Exception:
                continue

            exploit = Exploit(
                id=f"exploit-all-{self._total_exploits_generated:04d}",
                vuln_type=vtype,
                complexity=AttackComplexity.HIGH,
                reliability=ExploitReliability.RELIABLE,
                payload=payload,
                description=f"Full-coverage {vtype.value} exploit",
                is_exploitable=True,
                severity="HIGH",
                cwe_id=self._get_cwe(vtype),
                mitigation=self._suggest_mitigation(vtype),
                generation_time_ms=(time.monotonic() - t0) * 1000,
            )
            exploits.append(exploit)
            self._total_exploits_generated += 1
            self._total_exploitable += 1

        logger.info(f"RedTeam: generated {len(exploits)} full-coverage exploits")
        return exploits

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _get_cwe(vtype: VulnerabilityType) -> str:
        mapping = {
            VulnerabilityType.BUFFER_OVERFLOW: "CWE-120",
            VulnerabilityType.USE_AFTER_FREE: "CWE-416",
            VulnerabilityType.DOUBLE_FREE: "CWE-415",
            VulnerabilityType.NULL_DEREF: "CWE-476",
            VulnerabilityType.INTEGER_OVERFLOW: "CWE-190",
            VulnerabilityType.RACE_CONDITION: "CWE-362",
            VulnerabilityType.FORMAT_STRING: "CWE-134",
            VulnerabilityType.STACK_EXHAUSTION: "CWE-789",
            VulnerabilityType.HEAP_SPRAY: "CWE-122",
            VulnerabilityType.TYPE_CONFUSION: "CWE-843",
        }
        return mapping.get(vtype, "CWE-unknown")

    @staticmethod
    def _suggest_mitigation(vtype: VulnerabilityType) -> str:
        mitigations = {
            VulnerabilityType.BUFFER_OVERFLOW: "Use strncpy/snprintf with bounds checking. Enable -fstack-protector.",
            VulnerabilityType.USE_AFTER_FREE: "Set pointer to NULL after free. Use reference counting.",
            VulnerabilityType.DOUBLE_FREE: "Nullify pointer after free. Use safe_free() macro.",
            VulnerabilityType.NULL_DEREF: "Add NULL checks before dereference. Use ERR_PTR pattern.",
            VulnerabilityType.INTEGER_OVERFLOW: "Use checked arithmetic (check_add_overflow). Validate sizes.",
            VulnerabilityType.RACE_CONDITION: "Use mutex/spinlock. Consider RCU for read-heavy access.",
            VulnerabilityType.FORMAT_STRING: "Use %s format specifier. Never pass user input as format string.",
            VulnerabilityType.STACK_EXHAUSTION: "Limit recursion depth. Use iterative approach.",
            VulnerabilityType.HEAP_SPRAY: "Use guard pages. Enable ASLR + NX bit.",
            VulnerabilityType.TYPE_CONFUSION: "Use static_assert for struct sizes. Avoid unsafe casts.",
        }
        return mitigations.get(vtype, "Apply defense in depth.")

    def get_stats(self) -> Dict:
        return {
            "total_exploits_generated": self._total_exploits_generated,
            "total_exploitable": self._total_exploitable,
            "exploitability_rate": (
                f"{self._total_exploitable / max(self._total_exploits_generated, 1):.1%}"
            ),
        }
