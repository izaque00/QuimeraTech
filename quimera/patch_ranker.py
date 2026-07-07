"""Patch Ranker — consenso multi-validator para escolher o melhor patch.

Now integrated with:
  - TestSuiteExecutor (multi-framework test suite runner)
  - DifferentialAnalyzer (before/after comparison with regression detection)
  - PatchMemory (context-aware evidence recording)
"""

import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from collections import defaultdict

from quimera.validators import (
    CompileValidator, BuildValidator, TestSuiteExecutor,
    BenchmarkValidator, ASanValidator, UBSanValidator, FuzzValidator,
    ValidationPlugin, ValidatorResult, ValidatorLevel,
    DifferentialAnalyzer, DifferentialReport,
    update_patch_memory_from_report,
)
from quimera.patch_memory import PatchCatalog, PatchMemory, PatchStatus


@dataclass
class RankedPatch:
    """A patch candidate with its validation scorecard."""
    candidate_id: str
    description: str
    patched_code: str
    diff: str = ""

    # Per-validator results
    scores: Dict[str, ValidatorResult] = field(default_factory=dict)

    # Consolidated
    total_score: int = 0
    max_possible: int = 0
    confidence: float = 0.0  # 0..100
    rank: int = 0

    # Differential report (before/after analysis)
    differential: Optional[DifferentialReport] = None

    # Patch Memory match
    similar_patch: Optional[PatchMemory] = None
    previous_attempts: int = 0
    previous_successes: int = 0

    @property
    def passed(self) -> bool:
        """Did all available validators pass?"""
        return all(r.passed for r in self.scores.values() if r.available)

    @property
    def failed_validators(self) -> list:
        return [k for k, v in self.scores.items() if not v.passed and v.available]

    @property
    def has_regression(self) -> bool:
        """Did differential analysis detect regressions?"""
        if self.differential:
            return not self.differential.safe_to_apply
        return False

    def summary(self) -> str:
        lines = [f"  #{self.rank} {self.candidate_id}: {self.description[:60]}"]
        lines.append(f"     Score: {self.total_score}/{self.max_possible} (confidence: {self.confidence:.0f}%)")
        for vname, vr in self.scores.items():
            s = "PASS" if vr.passed else ("FAIL" if vr.available else "SKIP")
            lines.append(f"     [{s:4s}] {vname:12s} +{vr.score:2d}")
        if self.failed_validators:
            lines.append(f"     Failed: {', '.join(self.failed_validators)}")
        if self.similar_patch and self.similar_patch.status == PatchStatus.PROVEN:
            lines.append(f"     Patch Memory: {self.similar_patch.status.value.upper()} "
                        f"({self.previous_successes}s/{self.previous_attempts}a)")
        if self.differential:
            if self.differential.regressions_detected:
                lines.append(f"     ⚠️  Regressions: {', '.join(self.differential.regressions_detected)}")
            if self.differential.improvements_detected:
                lines.append(f"     ✅ Improvements: {', '.join(self.differential.improvements_detected)}")
        return '\n'.join(lines)


class PatchRanker:
    """
    Orquestrador de validação multi-validator com differential analysis.

    Para cada patch candidate:
      1. Captura baseline (testes, código, binário)
      2. Aplica o patch
      3. Executa cada validator disponível
      4. Roda differential analyzer (antes/depois)
      5. Acumula score ponderado
      6. Consulta Patch Memory por similaridade
      7. Registra evidências no Patch Memory
      8. Ranqueia todos os candidatos por evidência acumulada

    O melhor patch = maior score de validação + sem regressões.
    """

    def __init__(self, project_root: Path, patch_catalog: PatchCatalog = None,
                 baseline: float = None, enable_differential: bool = True):
        self.root = Path(project_root)
        self.catalog = patch_catalog or PatchCatalog()
        self.baseline = baseline
        self.enable_differential = enable_differential

        self.validators: List[ValidationPlugin] = [
            CompileValidator(),
            BuildValidator(),
            TestSuiteExecutor(),       # ← NEW: multi-framework test executor
            BenchmarkValidator(baseline=baseline),
            ASanValidator(),
            UBSanValidator(),
            FuzzValidator(),
        ]

    def rank(self, candidates: list, original_file: Path) -> List[RankedPatch]:
        """
        Validate all candidates against all validators + differential analysis.
        Returns candidates ranked by total validation score.
        """
        ranked = []

        for i, candidate in enumerate(candidates):
            rp = RankedPatch(
                candidate_id=f"patch-{i+1}",
                description=candidate.description if hasattr(candidate, 'description')
                              else str(candidate)[:60],
                patched_code=candidate.patched_code if hasattr(candidate, 'patched_code')
                              else str(candidate),
                diff=candidate.diff if hasattr(candidate, 'diff') else "",
            )

            # ── Differential Analysis (before/after) ──
            if self.enable_differential:
                analyzer = DifferentialAnalyzer(self.root)
                analyzer.capture_baseline()

            # Backup original
            original_content = original_file.read_text() if original_file.exists() else ""

            # Apply patch
            original_file.write_text(rp.patched_code)

            # ── Run each validator ──
            total = 0
            max_score = 0

            for validator in self.validators:
                if validator.is_available(self.root):
                    result = validator.run(self.root)
                    rp.scores[validator.name] = result
                    total += result.score
                    max_score += validator.score_weight
                else:
                    rp.scores[validator.name] = ValidatorResult(
                        name=validator.name, level=validator.level,
                        passed=True, available=False, score=0,
                        output=f"{validator.name}: not available"
                    )

            # ── Differential comparison ──
            if self.enable_differential:
                try:
                    rp.differential = analyzer.compare(
                        patch_id=rp.candidate_id,
                        project=self.root.name,
                    )
                    # Penalize regressions
                    if rp.differential.regressions_detected:
                        total = max(0, total - 15 * len(rp.differential.regressions_detected))
                    # Bonus for improvements
                    if rp.differential.improvements_detected:
                        total += 5 * len(rp.differential.improvements_detected)
                except Exception as e:
                    pass

            # Restore original
            if original_file.exists():
                original_file.write_text(original_content)

            rp.total_score = total
            rp.max_possible = max_score
            rp.confidence = min(100, (total / max(max_score, 1)) * 100)

            # Check Patch Memory for similar patches
            self._check_memory(rp)

            # ── Update Patch Memory with evidence ──
            if rp.differential and self.enable_differential:
                try:
                    update_patch_memory_from_report(rp.differential, self.catalog)
                except Exception:
                    pass

            ranked.append(rp)

        # Sort by score descending, penalize regressions
        ranked.sort(key=lambda r: (-r.total_score, -r.confidence, r.has_regression))
        for i, rp in enumerate(ranked):
            rp.rank = i + 1

        return ranked

    def _check_memory(self, rp: RankedPatch):
        """Check if a similar patch exists in Patch Memory."""
        for pat in self.catalog.all_patches:
            if pat.pattern_regex and pat.pattern_regex in rp.patched_code:
                rp.similar_patch = pat
                rp.previous_attempts = pat.total_attempts
                rp.previous_successes = pat.total_successes
                if pat.status in (PatchStatus.PROVEN, PatchStatus.RELIABLE):
                    rp.confidence = min(100, rp.confidence + 5)
                break

    def best(self, candidates: list, original_file: Path) -> Optional[RankedPatch]:
        """Return the single best-ranked patch."""
        ranked = self.rank(candidates, original_file)
        return ranked[0] if ranked else None

    def report(self, ranked: List[RankedPatch]) -> str:
        """Generate a human-readable ranking report."""
        lines = [
            "=" * 60,
            "PATCH RANKING REPORT (Consensus Validation + Differential Analysis)",
            "=" * 60,
            "",
            f"  Candidates tested: {len(ranked)}",
            f"  Validators: {', '.join(v.name for v in self.validators)}",
            f"  Differential analysis: {'ON' if self.enable_differential else 'OFF'}",
            "",
        ]

        for rp in ranked:
            lines.append(rp.summary())
            lines.append("")

        if ranked:
            best = ranked[0]
            lines.append(f"  RECOMMENDED: #{best.rank} {best.candidate_id}")
            lines.append(f"  Confidence: {best.confidence:.0f}%")

            if best.has_regression:
                lines.append(f"  ⚠️  REGRESSION DETECTED in best patch — review required")
            if best.failed_validators:
                lines.append(f"  ⚠️  Failed validators: {', '.join(best.failed_validators)}")
                lines.append(f"  Consider manual review before applying.")
            else:
                lines.append(f"  ✅ All validators passed. Ready to apply.")

        lines.append("")
        lines.append("  " + "=" * 56)
        return '\n'.join(lines)


# ─── DEMO ───
if __name__ == "__main__":
    import sys, shutil

    PROJ = Path(tempfile.mkdtemp(prefix="quimera_pr_"))
    if PROJ.exists():
        shutil.rmtree(PROJ)
    PROJ.mkdir(parents=True)

    (PROJ / "main.c").write_text("""#include <stdio.h>
#include <stdlib.h>
int main() {
    int *p = malloc(100);
    p[0] = 42;
    printf("p[0] = %d\\n", p[0]);
    free(p);
    printf("done\\n");
    return 0;
}
""")

    (PROJ / "Makefile").write_text("""CC=gcc
CFLAGS=-Wall -Werror -O2
TARGET=prog
all: $(TARGET)
$(TARGET): main.c
\t$(CC) $(CFLAGS) -o $(TARGET) main.c
test: $(TARGET)
\t./$(TARGET) && echo PASS
clean:
\trm -f $(TARGET)
""")

    class FakeCandidate:
        def __init__(self, desc, code, diff=""):
            self.description = desc
            self.patched_code = code
            self.diff = diff

    original = (PROJ / "main.c").read_text()

    candidates = [
        FakeCandidate("Add NULL check only",
            original.replace('p[0] = 42;', 'if (!p) return 1;\n    p[0] = 42;')),
        FakeCandidate("Add NULL check + NULL after free",
            original.replace('p[0] = 42;', 'if (!p) return 1;\n    p[0] = 42;')
                   .replace('free(p);', 'free(p);\n    p = NULL;')),
        FakeCandidate("Bad: remove NULL check",
            original.replace('int *p = malloc(100);\n    p[0] = 42;',
                           'int *p = malloc(100);\n    p[0] = 42;')),
    ]

    ranker = PatchRanker(PROJ, enable_differential=True)
    ranked = ranker.rank(candidates, PROJ / "main.c")

    print(ranker.report(ranked))

    shutil.rmtree(PROJ, ignore_errors=True)
