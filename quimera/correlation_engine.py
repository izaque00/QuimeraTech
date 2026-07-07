"""
Correlation Engine v2 — Quimera Mark X

Groups findings → identifies root cause candidates → builds evidence per candidate.

Pipeline:
  Detection → Correlation → RCA → Evidence Builder → Patch Candidates

This module does NOT claim findings are "bugs" or that fixes are "resolved".
Everything is a candidate until validated in sandbox.
"""

import re
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Evidence:
    """Evidence gathered for a Root Cause candidate."""
    total_occurrences: int = 0
    contexts_affected: int = 0
    safe_occurrences: int = 0
    risky_occurrences: int = 0
    uncertain: int = 0
    context_dependent: int = 0
    has_test_coverage: bool = False
    affects_public_api: bool = False
    compiler_can_reach: bool = True
    estimated_risk: str = "unknown"
    
    def risk_score(self) -> float:
        if self.total_occurrences == 0:
            return 0.0
        return self.risky_occurrences / self.total_occurrences


@dataclass
class RootCause:
    """A root cause HYPOTHESIS — not a confirmed bug."""
    id: str
    pattern: str
    description: str
    findings_count: int
    evidence: Evidence = field(default_factory=Evidence)
    candidate_fix: str = ""
    confidence: float = 0.0
    type: str = "systematic"
    
    def summary(self) -> str:
        return (f"{self.id}: {self.pattern} — {self.findings_count} findings, "
                f"{self.evidence.risky_occurrences} risky, "
                f"{self.evidence.safe_occurrences} safe, "
                f"risk={self.evidence.estimated_risk}")


class EvidenceBuilder:
    """For each Root Cause candidate, gather contextual evidence."""
    
    def analyze_free_without_null(self, findings: list, source_dir: Path) -> Evidence:
        ev = Evidence()
        ev.total_occurrences = len(findings)
        seen_contexts = set()
        
        for f in findings:
            fp = source_dir / f.get("f", "")
            if not fp.exists():
                continue
            
            seen_contexts.add((f.get("f"), f.get("func")))
            
            try:
                code = fp.read_text(errors='ignore')
                lines = code.splitlines()
            except Exception:
                ev.uncertain += 1
                continue
            
            ln = f.get("l", 0)
            var = f.get("var", "")
            if not var or ln == 0:
                ev.uncertain += 1
                continue
            
            nearby_start = max(0, ln - 1)
            nearby_end = min(len(lines), ln + 4)
            nearby = '\n'.join(lines[nearby_start:nearby_end])
            
            has_null_assign = f'{var} = NULL' in nearby or f'{var}=NULL' in nearby
            
            scope_end = min(len(lines), ln + 30)
            scope_text = '\n'.join(lines[ln:scope_end])
            goes_out_of_scope = bool(re.search(r'^\s*\}\s*$', scope_text, re.MULTILINE))
            
            used_after = False
            for i in range(ln, min(len(lines), ln + 20)):
                if var in lines[i] and 'free' not in lines[i].lower():
                    used_after = True
                    break
            
            if has_null_assign or goes_out_of_scope:
                ev.safe_occurrences += 1
            elif used_after:
                ev.risky_occurrences += 1
            else:
                ev.uncertain += 1
            
            if any(kw in f.get("func", "").lower() for kw in
                   ['ssl_', 'evp_', 'x509_', 'bio_', 'rsa_', 'ec_']):
                ev.affects_public_api = True
        
        ev.contexts_affected = len(seen_contexts)
        risk_ratio = ev.risk_score()
        if risk_ratio > 0.3:
            ev.estimated_risk = "high"
        elif risk_ratio > 0.1:
            ev.estimated_risk = "medium"
        elif ev.uncertain / max(ev.total_occurrences, 1) > 0.5:
            ev.estimated_risk = "uncertain"
        else:
            ev.estimated_risk = "low"
        
        return ev
    
    def analyze_memcpy_pattern(self, findings: list, source_dir: Path) -> Evidence:
        ev = Evidence()
        ev.total_occurrences = len(findings)
        seen = set()
        risky = 0
        safe = 0
        
        for f in findings:
            fp = source_dir / f.get("f", "")
            seen.add((f.get("f"), f.get("func")))
            code_line = f.get("code", "")
            
            m = re.search(r'memcpy\s*\([^,]+,\s*[^,]+,\s*(\w+)', code_line)
            if m:
                size_arg = m.group(1)
                if size_arg.isupper() or size_arg.startswith("sizeof") or size_arg.isdigit():
                    safe += 1
                else:
                    risky += 1
            else:
                ev.uncertain += 1
        
        ev.contexts_affected = len(seen)
        ev.safe_occurrences = safe
        ev.risky_occurrences = risky
        ev.estimated_risk = "medium" if risky > 0 else "low"
        return ev


class CorrelationEngine:
    """Groups findings → root cause candidates → evidence per candidate."""
    
    def __init__(self, source_dir: Path):
        self.source_dir = source_dir
        self.builder = EvidenceBuilder()
    
    def run(self, all_findings: list) -> list:
        groups = defaultdict(list)
        for f in all_findings:
            groups[(f.get("f"), f.get("func"), f.get("var"), f.get("cwe"))].append(f)
        
        by_cwe = defaultdict(list)
        for f in all_findings:
            by_cwe[f.get("cwe")].append(f)
        
        root_causes = []
        
        if "CWE-416" in by_cwe:
            findings = by_cwe["CWE-416"]
            ev = self.builder.analyze_free_without_null(findings, self.source_dir)
            root_causes.append(RootCause(
                id="RCA-002",
                pattern="free() without ptr = NULL assignment",
                description="Memory deallocation not followed by pointer nullification.",
                findings_count=len(findings),
                evidence=ev,
                candidate_fix="Candidate: SAFE_FREE macro — free(p); p = NULL;",
                confidence=0.65 if ev.risky_occurrences > 0 else 0.30,
                type="systematic",
            ))
        
        if "CWE-120" in by_cwe:
            findings = by_cwe["CWE-120"]
            ev = self.builder.analyze_memcpy_pattern(findings, self.source_dir)
            root_causes.append(RootCause(
                id="RCA-003",
                pattern="memcpy with potentially unchecked size",
                description="memcpy called with size not verified against destination capacity.",
                findings_count=len(findings),
                evidence=ev,
                candidate_fix="Candidate: Add bounds check before memcpy",
                confidence=0.70 if ev.risky_occurrences > 0 else 0.25,
                type="pattern",
            ))
        
        if "CWE-134" in by_cwe:
            findings = by_cwe["CWE-134"]
            root_causes.append(RootCause(
                id="RCA-005",
                pattern="printf with variable format string",
                description="Format string passed as variable instead of literal.",
                findings_count=len(findings),
                evidence=Evidence(
                    total_occurrences=len(findings),
                    contexts_affected=len(set((f.get("f"), f.get("func")) for f in findings)),
                    estimated_risk="medium",
                ),
                candidate_fix="Candidate: Replace printf(var) with printf(\"%s\", var)",
                confidence=0.80,
                type="pattern",
            ))
        
        if "CWE-476" in by_cwe:
            findings = by_cwe["CWE-476"]
            root_causes.append(RootCause(
                id="RCA-001",
                pattern="Missing NULL check after allocation",
                description="malloc/calloc return value used without NULL validation.",
                findings_count=len(findings),
                evidence=Evidence(
                    total_occurrences=len(findings),
                    contexts_affected=len(set((f.get("f"), f.get("func")) for f in findings)),
                    estimated_risk="medium",
                ),
                candidate_fix="Candidate: Add if (!ptr) return ERR; after allocation",
                confidence=0.85,
                type="systematic",
            ))
        
        return root_causes
