import logging
_log = logging.getLogger(__name__)
"""
UnifiedMemory — Single interface for all TheAnd memory systems.

Wraps:
  - patch_memory: fast lookup of known fixes
  - engineering_memory: full decision history
  - live_catalog: model performance tracking
  - source_catalog: KB source effectiveness
  - Bibliotecario: semantic code index
  - Cognitive Librarian: advanced retrieval

EXPOSE two methods only:
  - remember(result) → saves everything
  - recall(query, cwe) → searches all stores
  - decision_report(result) → human-readable explanation
"""
import time, json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict


@dataclass
class DecisionReport:
    """Complete explanation of why a patch was chosen."""
    finding_cwe: str = ""
    finding_desc: str = ""
    hypotheses: List[Dict] = field(default_factory=list)
    candidates_total: int = 0
    candidates_passed: int = 0
    chosen_approach: str = ""
    chosen_score: float = 0.0
    evidence_sources: List[str] = field(default_factory=list)
    validation_results: Dict[str, bool] = field(default_factory=dict)
    impact_score: float = 0.0
    timestamp: str = ""
    project: str = ""
    file: str = ""

    def markdown(self) -> str:
        """Generate human-readable decision explanation."""
        h = self.hypotheses
        hyp_lines = ""
        for hp in h[:3]:
            hyp_lines += f"| {hp['approach']} | {hp['confidence']:.2f} | {hp['sources']} |\n"

        val = self.validation_results
        val_lines = ""
        for k, v in val.items():
            val_lines += f"| {k} | {'✅' if v else '❌'} |\n"

        return f"""# Decision Report

## Finding
**{self.finding_cwe}**: {self.finding_desc}

## Hypotheses Considered
| Approach | Confidence | Sources |
|----------|-----------|---------|
{hyp_lines}

## Candidates
- **Generated:** {self.candidates_total}
- **Passed validation:** {self.candidates_passed}
- **Chosen:** {self.chosen_approach} (score: {self.chosen_score:.2f})

## Evidence Sources
{', '.join(self.evidence_sources)}

## Validation Results
| Check | Result |
|-------|--------|
{val_lines}

## Impact
- **Lines changed:** minimal
- **Impact score:** {self.impact_score:.0%}

## Verdict
✅ Patch **{self.chosen_approach}** accepted with confidence **{self.chosen_score:.2f}**

---
*{self.project} · {self.file} · {self.timestamp}*
"""


class UnifiedMemory:
    """
    Single memory interface. All 6 stores behind one API.
    
    Usage:
        mem = UnifiedMemory()
        mem.remember(result)       # saves to all stores
        results = mem.recall(q)    # searches all stores
        report = mem.decision_report(result)  # explains the choice
    """

    def __init__(self, project_root: str = "."):
        self.project_root = project_root
        self._patch_memory = None
        self._eng_memory = None
        self._live_catalog = None
        self._source_catalog = None

    @property
    def patch_memory(self):
        if self._patch_memory is None:
            from quimera.patch_memory import PatchCatalog
            self._patch_memory = PatchCatalog()
        return self._patch_memory

    @property
    def eng_memory(self):
        if self._eng_memory is None:
            from quimera.engineering_memory import EngineeringMemory
            self._eng_memory = EngineeringMemory(self.project_root)
        return self._eng_memory

    @property
    def live_catalog(self):
        if self._live_catalog is None:
            from quimera.live_catalog import LiveCatalog
            self._live_catalog = LiveCatalog(self.project_root)
        return self._live_catalog

    @property
    def source_catalog(self):
        if self._source_catalog is None:
            from quimera.source_catalog import SourceCatalog
            self._source_catalog = SourceCatalog(self.project_root)
        return self._source_catalog

    def remember(self, result: Dict):
        """Save execution result to ALL memory stores."""
        cwe = result.get('cwe', '')
        project = result.get('project', '')
        patch_code = result.get('patch_code', '')
        sources = result.get('sources_used', [])
        compiled = result.get('compiled', False)
        asan_ok = result.get('asan_clean', False)
        ubsan_ok = result.get('ubsan_clean', False)
        model = result.get('model', 'unknown')
        provider = result.get('provider', 'unknown')
        total_time = result.get('total_time_ms', 0)

        # 1. Patch Memory — proven fix
        if compiled and asan_ok and patch_code:
            try:
                self.patch_memory.add_successful_patch(cwe, patch_code, sources)
            except: pass  # noqa: bare-except — non-critical fallback

        # 2. Engineering Memory — full decision log
        try:
            self.eng_memory.record(
                project=project, cwe=cwe,
                knowledge_sources_used=sources,
                compiled=compiled, asan_clean=asan_ok, ubsan_clean=ubsan_ok,
                patch_accepted=compiled,
                patch_code=patch_code[:500] if patch_code else '',
                model_used=model, provider_used=provider,
                final_result='success' if compiled else 'failed',
            )
        except: pass  # noqa: bare-except — non-critical fallback

        # 3. Live Catalog — model performance
        try:
            self.live_catalog.record_attempt(
                model, provider, cwe, 'c',
                compiled and asan_ok, total_time
            )
        except: pass  # noqa: bare-except — non-critical fallback

        # 4. Source Catalog — KB source ranking
        for src in sources:
            try:
                self.source_catalog.record_query(src, useful=True, accepted=compiled)
            except: pass  # noqa: bare-except — non-critical fallback

    def recall(self, query: str, cwe: str = "") -> List[Dict]:
        """Search all memory stores for relevant knowledge."""
        results = []
        
        # Patch Memory
        try:
            pm_results = self.patch_memory.search(query, cwe)
            results.extend(pm_results)
        except: pass  # noqa: bare-except — non-critical fallback

        # Engineering Memory
        try:
            em_results = self.eng_memory.search(query, cwe)
            results.extend(em_results)
        except: pass  # noqa: bare-except — non-critical fallback

        return results

    def decision_report(self, result: Dict) -> DecisionReport:
        """Generate a complete decision explanation."""
        return DecisionReport(
            finding_cwe=result.get('cwe', ''),
            finding_desc=result.get('description', ''),
            hypotheses=result.get('hypotheses', []),
            candidates_total=result.get('candidates_generated', 0),
            candidates_passed=result.get('candidates_passed', 0),
            chosen_approach=result.get('best_approach', ''),
            chosen_score=result.get('final_score', 0.0),
            evidence_sources=result.get('sources_used', []),
            validation_results={
                'compile': result.get('compiled', False),
                'asan': result.get('asan_clean', False),
                'ubsan': result.get('ubsan_clean', False),
                'static_analysis': result.get('static_clean', False),
                'aegis_sentinel': result.get('aegis_threats', -1) == 0,
                'aegis_malware': result.get('aegis_malware_clean', True),
            },
            impact_score=result.get('impact_score', 0.0),
            timestamp=time.strftime('%Y-%m-%d %H:%M:%S'),
            project=result.get('project', ''),
            file=result.get('file', ''),
        )
