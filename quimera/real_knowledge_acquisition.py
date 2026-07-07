"""
Real Knowledge Acquisition Layer — Quimera Mark X

Replaces the placeholder knowledge_acquisition.py with:
  1. Internal catalog of 12 known error patterns with regex matching
  2. Real error classification (compile, link, runtime, security, unknown)
  3. Evidence-based learning (patterns only trusted after multi-project validation)
  4. LLM consultation placeholder (always marked as low confidence)

Architecture:
  Error → Classify → Catalog lookup → Match?
    ├── Yes (conf > 0.80) → Hypothesis + fix → Sandbox validation
    └── No → LLM hypothesis (conf 0.25) → Sandbox → If passes → learn()
"""

import re
from quimera.knowledge_acquisition import (
    KnowledgeAcquisitionLayer, ErrorContext, Hypothesis, ResearchReport
)
from quimera.evidence_score import LearnedPattern


KNOWN_ERROR_PATTERNS = {
    "implicit_function_declaration": {
        "pattern": r"implicit\s+declaration\s+of\s+function\s+['\"]?(\w+)",
        "fix": "Add #include <appropriate_header.h> or declare function prototype before use",
        "confidence": 0.95,
        "explanation": "Function called before it was declared or defined.",
    },
    "undefined_reference": {
        "pattern": r"undefined\s+reference\s+to\s+[`'\"](\w+)",
        "fix": "Link with -l{library} or add the missing .o file to the build",
        "confidence": 0.92,
        "explanation": "Symbol is declared but not linked. Missing -l flag or object file.",
    },
    "incompatible_pointer_type": {
        "pattern": r"incompatible\s+pointer\s+type",
        "fix": "Cast pointer explicitly: (target_type*)ptr, or fix the type mismatch at declaration",
        "confidence": 0.88,
        "explanation": "Pointer type mismatch in assignment or function argument.",
    },
    "null_pointer_dereference": {
        "pattern": r"(NULL\s+pointer|Segmentation\s+fault|null\s+deref|null\s+pointer\s+dereference)",
        "fix": "Add NULL guard: if (!ptr) { return -1; }",
        "confidence": 0.90,
        "explanation": "Pointer dereferenced without NULL validation.",
    },
    "double_free": {
        "pattern": r"double\s+free|free\s*\(\s*(\w+)\s*\).*free\s*\(\s*\1",
        "fix": "After free(ptr), set ptr = NULL. Before free, check if (ptr).",
        "confidence": 0.89,
        "explanation": "Same memory freed twice. Missing NULL assignment after free.",
    },
    "use_after_free": {
        "pattern": r"use.after.free|UaF|dangling\s+pointer|heap-use-after-free",
        "fix": "Set ptr = NULL after free(). Add lifetime documentation.",
        "confidence": 0.87,
        "explanation": "Memory accessed after being freed. Pointer not nullified.",
    },
    "buffer_overflow_strcpy": {
        "pattern": r"buffer\s+(over|too).*strcpy|strcpy\s+overflow|__strcpy_chk",
        "fix": "Replace strcpy(dst, src) with strncpy(dst, src, sizeof(dst)-1);",
        "confidence": 0.93,
        "explanation": "strcpy without destination size check.",
    },
    "format_string_vulnerability": {
        "pattern": r"format\s+(string|not\s+a\s+string\s+literal)",
        "fix": "Use printf(\"%s\", user_input) instead of printf(user_input)",
        "confidence": 0.91,
        "explanation": "User-controlled format string allows arbitrary memory read/write.",
    },
    "integer_overflow": {
        "pattern": r"integer\s+overflow|signed\s+integer\s+overflow",
        "fix": "Check bounds: if (a > INT_MAX / b) return ERR;",
        "confidence": 0.86,
        "explanation": "Arithmetic operation overflows, leading to undersized allocation.",
    },
    "missing_break_switch": {
        "pattern": r"switch.*?(?:missing|no)\s+break|fallthrough",
        "fix": "Add 'break;' or '/* fallthrough */' comment after each case",
        "confidence": 0.94,
        "explanation": "Missing break in switch statement causes unintended fallthrough.",
    },
    "uninitialized_variable": {
        "pattern": r"(?:uninitialized|used\s+uninitialized|may\s+be\s+used\s+uninitialized)",
        "fix": "Initialize variable: type var = {0}; or type var = INIT_VALUE;",
        "confidence": 0.92,
        "explanation": "Variable used before being assigned a value.",
    },
    "memory_leak": {
        "pattern": r"(?:memory\s+leak|leaked|leaking\s+\d+\s+bytes|definitely\s+lost)",
        "fix": "Ensure free() in all code paths. Use goto cleanup pattern.",
        "confidence": 0.85,
        "explanation": "Allocated memory not freed on all execution paths.",
    },
}


class RealKnowledgeAcquisition(KnowledgeAcquisitionLayer):
    """
    Knowledge Acquisition with REAL internal catalog + evidence-based learning.
    
    Inherits the full multi-source research pipeline from KnowledgeAcquisitionLayer
    and adds:
      - 12 built-in error patterns with regex matching
      - Evidence-based learning (via LearnedPattern)
      - LLM consultation fallback (always low confidence)
    """
    
    def __init__(self, search_web: bool = False, llm_enabled: bool = False):
        super().__init__(search_web=search_web)
        self.llm_enabled = llm_enabled
        self._catalog = dict(KNOWN_ERROR_PATTERNS)
        self._learned_patterns = {}  # Evidence-based learned patterns
    
    def research(self, ctx: ErrorContext) -> ResearchReport:
        report = super().research(ctx)
        
        # Check internal catalog first (higher confidence than parent's AI synthesis)
        for name, entry in {**self._catalog, **self._get_learned_catalog()}.items():
            m = re.search(entry["pattern"], ctx.error_message, re.IGNORECASE)
            if m:
                fix = entry["fix"]
                for i, g in enumerate(m.groups()):
                    fix = fix.replace(f"{{{i}}}", g or "?")
                
                hyp = Hypothesis(
                    id=f"catalog-{name}",
                    description=f"Known pattern: {name} — {entry['explanation']}",
                    proposed_fix=fix,
                    confidence=entry["confidence"],
                )
                report.hypotheses.insert(0, hyp)
        
        if (not report.has_high_confidence) and self.llm_enabled:
            llm_hyp = self._consult_llm(ctx)
            if llm_hyp:
                report.hypotheses.append(llm_hyp)
        
        report.hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        return report
    
    def _get_learned_catalog(self) -> dict:
        """Convert LearnedPattern objects to catalog entries."""
        return {
            name: {
                "pattern": lp.pattern,
                "fix": lp.fix,
                "confidence": lp.confidence,
                "explanation": lp.explanation,
            }
            for name, lp in self._learned_patterns.items()
        }
    
    def _consult_llm(self, ctx: ErrorContext) -> Hypothesis:
        """LLM consultation — always low confidence, always needs validation."""
        return Hypothesis(
            id="llm-synthesis",
            description=f"LLM analysis of: {ctx.error_message[:100]}",
            proposed_fix="[LLM-generated fix — requires sandbox validation]",
            confidence=0.25,
            requires_validation=True,
        )
    
    def learn(self, name: str, pattern: str, fix: str, explanation: str):
        """
        Add a newly discovered pattern.
        It starts UNVERIFIED (conf=0.25) and must accumulate evidence.
        """
        lp = LearnedPattern(name, pattern, fix, explanation)
        self._learned_patterns[name] = lp
        return lp
    
    def get_learned(self, name: str) -> LearnedPattern:
        return self._learned_patterns.get(name)
    
    @property
    def catalog_size(self) -> int:
        return len(self._catalog) + len(self._learned_patterns)
    
    @property
    def proven_patterns(self) -> list:
        return [lp for lp in self._learned_patterns.values()
                if lp.evidence.tier == "PROVEN"]
