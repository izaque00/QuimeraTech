"""
Evidence-Driven Hypothesis Builder — filters knowledge before patching.

Sits BETWEEN KnowledgeBroker and ASTPatcher:
  KnowledgeBroker → raw results (docs, commits, CVEs, ...)
          ↓
  HypothesisBuilder → filter + rank + synthesize evidence
          ↓
  ASTPatcher → generates high-quality candidates

Not all knowledge is useful. The HypothesisBuilder:
  1. Filters out low-confidence results
  2. Deduplicates similar findings
  3. Ranks by evidence quality (code snippet > URL > description)
  4. Merges knowledge into structured hypotheses
  5. Consults SourceCatalog for optimal query order
"""
import json, time, re
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Hypothesis:
    """A structured hypothesis for the AST Patcher to work with."""
    id: str
    description: str
    approach: str  # 'null_after_free', 'bounds_check', 'early_return', etc.
    evidence: List[Dict] = field(default_factory=list)  # supporting KnowledgeResult data
    code_template: str = ""  # example fix code
    confidence: float = 0.0
    source_count: int = 0  # how many independent sources support this
    references: List[str] = field(default_factory=list)  # URLs


class HypothesisBuilder:
    """
    Filters raw knowledge into actionable hypotheses.

    Usage:
        builder = HypothesisBuilder()
        hypotheses = builder.build(knowledge_results, finding_cwe="CWE-416")
        for h in hypotheses:
            print(f"{h.approach}: conf={h.confidence:.2f} from {h.source_count} sources")
    """

    # How to extract approach from knowledge content
    APPROACH_PATTERNS = {
        # CWE-416 Use-After-Free
        "null_after_free": [
            r"=\s*NULL\s*;?\s*/\*.*after.*free",
            r"free\([^)]+\)\s*;\s*\w+\s*=\s*NULL",
            r"null\w*\s*(?:after|following|post)\s*free",
            r"SAFE_FREE",
            r"safe_free",
        ],
        "goto_cleanup": [
            r"goto\s+cleanup",
            r"goto\s+out",
            r"goto\s+err",
        ],
        "scope_guard": [
            r"__attribute__\s*\(\s*\(\s*cleanup",
            r"RAII",
            r"unique_ptr",
        ],
        # CWE-120 Buffer Overflow
        "strncpy": [
            r"strncpy\s*\(",
            r"strlcpy",
        ],
        "size_check": [
            r"sizeof\s*\(",
            r"if\s*\(.*(?:len|size|count).*>\s*.*sizeof",
        ],
        "snprintf": [
            r"snprintf\s*\(",
        ],
        # CWE-476 NULL Pointer Dereference
        "null_guard": [
            r"if\s*\(\s*\w+\s*(?:!=|==)\s*NULL\s*\)",
            r"if\s*\(\s*!\s*\w+\s*\)\s*return",
        ],
    }

    def __init__(self, project_root: str = ""):
        self.project_root = project_root

    def build(self, knowledge_results: List, finding_cwe: str = "",
              finding_desc: str = "") -> List[Hypothesis]:
        """
        Build hypotheses from knowledge results.

        Args:
            knowledge_results: List of KnowledgeResult from KnowledgeBroker
            finding_cwe: CWE ID (e.g. "CWE-416")
            finding_desc: Description of the finding

        Returns:
            Ranked list of Hypothesis objects
        """
        if not knowledge_results:
            return []

        # 1. Filter: keep only results with code snippets or high confidence
        filtered = [
            r for r in knowledge_results
            if (r.confidence >= 0.40 and r.code_snippet) or r.confidence >= 0.60
        ]
        if not filtered:
            filtered = knowledge_results[:5]  # fallback

        # 2. Deduplicate by summary similarity
        unique = self._deduplicate(filtered)

        # 3. Extract approaches from code/content
        approach_evidence = self._extract_approaches(unique, finding_cwe)

        # 4. Cross-reference: sources that agree → boost confidence
        cross_ref_boost = {}
        source_weights = {
            'patch_memory': 1.0, 'engineering_kb': 0.9,
            'github_commits': 0.85, 'github_issues': 0.70,
            'cve_database': 0.75, 'man_pages': 0.65,
            'stackoverflow': 0.55, 'project_docs': 0.50,
            'web_search': 0.45, 'llm': 0.35,
        }
        
        for approach, evidence_list in approach_evidence.items():
            sources = set(e.get('source', '') for e in evidence_list)
            # Cross-reference boost: more independent sources = more reliable
            cross_ref_boost[approach] = min(0.20, len(sources) * 0.05)
            # Source quality boost
            quality_sum = sum(source_weights.get(s, 0.5) for s in sources)
            cross_ref_boost[approach] += quality_sum / max(1, len(sources)) * 0.10

        # 5. Build hypotheses
        hypotheses = []
        seen = set()

        for approach, evidence_list in sorted(approach_evidence.items(),
                                               key=lambda x: -len(x[1])):
            if approach in seen:
                continue
            seen.add(approach)

            # Aggregate confidence
            source_types = set(e.get("source", "") for e in evidence_list)
            avg_conf = sum(e.get("confidence", 0.5) for e in evidence_list) / max(1, len(evidence_list))
            source_bonus = cross_ref_boost.get(approach, 0.10)
            # Quality-adjusted average confidence
            quality_conf = 0
            total_weight = 0
            for e in evidence_list:
                w = source_weights.get(e.get('source', ''), 0.5)
                quality_conf += e.get('confidence', 0.5) * w
                total_weight += w
            avg_conf = quality_conf / max(1, total_weight)

            # Find best code template
            code = ""
            for e in sorted(evidence_list,
                           key=lambda x: len(x.get("code", ""))):
                c = e.get("code", "")
                if len(c) > len(code) and len(c) < 2000:
                    code = c[:800]

            refs = list(set(
                e.get("url", "") for e in evidence_list
                if e.get("url", "")
            ))[:5]

            hypotheses.append(Hypothesis(
                id=f"HP-{approach}",
                description=f"Fix via {approach} (from {len(source_types)} sources: {', '.join(sorted(source_types))})",
                approach=approach,
                evidence=evidence_list[:5],
                code_template=code,
                confidence=min(0.95, avg_conf + source_bonus),
                source_count=len(source_types),
                references=refs,
            ))

        # Sort by confidence * source_count (more sources = more reliable)
        hypotheses.sort(key=lambda h: -(h.confidence * (1 + h.source_count * 0.1)))

        return hypotheses

    def _deduplicate(self, results: List) -> List:
        """Remove duplicate/near-duplicate results."""
        seen_summaries = set()
        unique = []
        for r in results:
            key = r.summary[:80].lower().strip()
            # Normalize
            key = re.sub(r'\s+', ' ', key)
            if key not in seen_summaries:
                seen_summaries.add(key)
                unique.append(r)
        return unique

    def _extract_approaches(self, results: List, cwe: str) -> Dict[str, List[Dict]]:
        """Extract fix approaches from knowledge results."""
        evidence = {}

        for r in results:
            content = (r.code_snippet + " " + r.summary).lower()
            matched = False

            for approach, patterns in self.APPROACH_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        evidence.setdefault(approach, []).append({
                            "source": r.source.value,
                            "confidence": r.confidence,
                            "code": r.code_snippet,
                            "url": r.url,
                            "summary": r.summary,
                        })
                        matched = True
                        break

            # If no specific approach matched, try generic
            if not matched:
                # Extract any C code snippet as generic evidence
                code_snip = r.code_snippet
                if code_snip and len(code_snip) > 10:
                    evidence.setdefault("generic_fix", []).append({
                        "source": r.source.value,
                        "confidence": r.confidence * 0.3,
                        "code": code_snip,
                        "url": r.url,
                        "summary": r.summary,
                    })

        return evidence

    def best_hypothesis(self, hypotheses: List[Hypothesis]) -> Optional[Hypothesis]:
        """Return the single best hypothesis."""
        return hypotheses[0] if hypotheses else None


if __name__ == "__main__":
    # Test with simulated knowledge results
    from quimera.knowledge_broker import KnowledgeResult, KnowledgeSource

    results = [
        KnowledgeResult(KnowledgeSource.PATCH_MEMORY, 0.92,
                       "free(p); p = NULL; // CWE-416 fix",
                       code_snippet="free(ptr);\n    ptr = NULL; /* prevent UAF */"),
        KnowledgeResult(KnowledgeSource.STACKOVERFLOW, 0.65,
                       "Always set pointer to NULL after free()",
                       "https://stackoverflow.com/q/12345",
                       code_snippet="free(p);\np = NULL;"),
        KnowledgeResult(KnowledgeSource.GITHUB_COMMITS, 0.72,
                       "Commit abc123: Fix UAF in session cleanup",
                       "https://github.com/linux/commit/abc123",
                       code_snippet="free(session);\nsession = NULL;\ngoto cleanup;"),
        KnowledgeResult(KnowledgeSource.CVE_DATABASE, 0.58,
                       "CVE-2023-12345: Use-after-free in libfoo",
                       code_snippet="/* Patch: nullify after free */"),
        KnowledgeResult(KnowledgeSource.MAN_PAGES, 0.50,
                       "BUGS: free() does not set pointer to NULL",
                       code_snippet=""),
    ]

    builder = HypothesisBuilder()
    hypotheses = builder.build(results, "CWE-416", "free() without NULL")

    print("Hypothesis Builder — Evidence-Driven Filtering")
    print("=" * 60)
    print(f"Input: {len(results)} knowledge results")
    print(f"Output: {len(hypotheses)} hypotheses\n")

    for h in hypotheses:
        print(f"[{h.approach:<20s}] conf={h.confidence:.2f} "
              f"sources={h.source_count}")
        print(f"  {h.description[:100]}")
        if h.code_template:
            lines = h.code_template.strip().split('\n')
            print(f"  Code: {' | '.join(l.strip()[:50] for l in lines[:3])}")
        if h.references:
            print(f"  Refs: {len(h.references)} URLs")
        print()
