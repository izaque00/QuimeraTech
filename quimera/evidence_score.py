"""
Evidence Score System — Quimera Mark X

A fix is NOT trusted after one sandbox pass.
It must accumulate evidence across multiple dimensions:
  - Multiple projects
  - Multiple compilers
  - Test suite passes
  - No regression
  - Benchmark stability
  - Fuzzing

Confidence is DERIVED from evidence, not hardcoded.
"""

import time
from typing import Set


class EvidenceScore:
    """
    Tracks evidence for a learned fix pattern.
    
    Tiers: UNVERIFIED → TENTATIVE → PROMISING → RELIABLE → PROVEN
    """
    
    WEIGHTS = {
        "compiles":         0.10,
        "tests_pass":       0.20,
        "no_regression":    0.15,
        "benchmark_stable": 0.10,
        "multi_project":    0.20,
        "multi_compiler":   0.10,
        "fuzzing_pass":     0.10,
        "manual_review":    0.05,
    }
    
    def __init__(self):
        self.evidence = {k: False for k in self.WEIGHTS}
        self.projects_validated: Set[str] = set()
        self.compilers_validated: Set[str] = set()
        self.attempts = 0
        self.failures = 0
    
    def record(self, evidence_type: str, detail: str = ""):
        if evidence_type in self.evidence:
            self.evidence[evidence_type] = True
        if evidence_type == "multi_project" and detail:
            self.projects_validated.add(detail)
        if evidence_type == "multi_compiler" and detail:
            self.compilers_validated.add(detail)
    
    def record_attempt(self, success: bool):
        self.attempts += 1
        if not success:
            self.failures += 1
    
    @property
    def score(self) -> float:
        total = sum(
            self.WEIGHTS[k] for k, v in self.evidence.items() if v
        )
        if len(self.projects_validated) >= 3:
            total += 0.05
        if len(self.compilers_validated) >= 2:
            total += 0.05
        if self.failures > 0:
            total *= 0.7 ** self.failures
        return min(1.0, total)
    
    @property
    def tier(self) -> str:
        s = self.score
        if s >= 0.80: return "PROVEN"
        if s >= 0.60: return "RELIABLE"
        if s >= 0.40: return "PROMISING"
        if s >= 0.20: return "TENTATIVE"
        return "UNVERIFIED"
    
    def summary(self) -> str:
        lines = [f"EvidenceScore: {self.score:.2f} ({self.tier})"]
        for k, v in self.evidence.items():
            lines.append(f"  {'[x]' if v else '[ ]'} {k}")
        lines.append(f"  Projects: {', '.join(sorted(self.projects_validated)) or 'none'}")
        lines.append(f"  Compilers: {', '.join(sorted(self.compilers_validated)) or 'none'}")
        lines.append(f"  Attempts: {self.attempts}, Failures: {self.failures}")
        return '\n'.join(lines)


class LearnedPattern:
    """
    A fix pattern that Quimera discovered and validated through evidence.
    
    Confidence = 0.25 (base) + 0.70 * evidence_score
    This means:
      - No evidence:       0.25 (UNVERIFIED — needs sandbox)
      - Full evidence:     0.95 (PROVEN — safe to apply)
    """
    
    def __init__(self, name: str, pattern: str, fix: str, explanation: str):
        self.name = name
        self.pattern = pattern
        self.fix = fix
        self.explanation = explanation
        self.evidence = EvidenceScore()
        self.first_seen = time.time()
        self.last_validated = None
    
    @property
    def confidence(self) -> float:
        return 0.25 + self.evidence.score * 0.70
    
    def validate(self, success: bool, context: str = ""):
        self.evidence.record_attempt(success)
        self.last_validated = time.time()
    
    def summary(self) -> str:
        return (f"{self.name}: conf={self.confidence:.2f} "
                f"[{self.evidence.tier}] "
                f"({self.evidence.attempts} attempts, "
                f"{len(self.evidence.projects_validated)} projects)")
