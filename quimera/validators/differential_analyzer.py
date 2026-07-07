"""Differential Analyzer — before/after comparison for Quimera patches.

This module compares project state before and after a patch is applied,
measuring: test results delta, benchmark delta, binary size delta,
memory usage delta, crash surface delta, and code change statistics.

The output is a DifferentialReport that feeds into:
  - PatchMemory (to record evidence per project/compiler/arch)
  - PatchRanker (to boost/deboost confidence based on regression detection)
  - Resolution States (to decide RESOLVED vs NEEDS_INVESTIGATION)

Philosophy: a patch that "compiles" is not enough. We need to prove it
didn't make things WORSE before we consider it PROVEN.
"""

import time, difflib, zlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum

from .test_executor import TestRunResult, execute_test_suite
from .base import ValidatorResult


# ═══════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════

class DeltaDirection(Enum):
    BETTER = "better"       # improvement (faster, smaller, fewer fails)
    NEUTRAL = "neutral"     # no significant change
    WORSE = "worse"         # regression (slower, bigger, more fails)
    UNKNOWN = "unknown"     # could not measure


@dataclass
class MetricDelta:
    """Single metric before/after comparison."""
    name: str
    unit: str = ""
    before: float = 0.0
    after: float = 0.0
    delta_absolute: float = 0.0
    delta_pct: float = 0.0
    direction: DeltaDirection = DeltaDirection.NEUTRAL
    threshold_pct: float = 10.0  # above this % → WORSE or BETTER

    @property
    def significant(self) -> bool:
        return abs(self.delta_pct) >= self.threshold_pct

    @property
    def is_regression(self) -> bool:
        return self.direction == DeltaDirection.WORSE and self.significant

    def summary(self) -> str:
        arrow = {"better": "↓", "neutral": "→", "worse": "↑", "unknown": "?"}[self.direction.value]
        return (f"  {self.name:24s}: {self.before:.2f}{self.unit} → "
                f"{self.after:.2f}{self.unit}  "
                f"({arrow} {self.delta_pct:+.1f}%)")


@dataclass
class TestDelta:
    """Before/after comparison of test results."""
    framework: str = ""
    tests_before: int = 0
    tests_after: int = 0
    passed_before: int = 0
    passed_after: int = 0
    failed_before: int = 0
    failed_after: int = 0
    crashed_before: int = 0
    crashed_after: int = 0
    new_failures: List[str] = field(default_factory=list)    # tests that PASSED before, FAIL now
    new_passes: List[str] = field(default_factory=list)      # tests that FAILED before, PASS now
    duration_before_ms: float = 0.0
    duration_after_ms: float = 0.0

    @property
    def regression(self) -> bool:
        """Did any test that passed before now fail?"""
        return len(self.new_failures) > 0 or self.crashed_after > self.crashed_before

    @property
    def improvement(self) -> bool:
        """Did any test that failed before now pass?"""
        return len(self.new_passes) > 0


@dataclass
class CodeDelta:
    """Code change statistics."""
    files_changed: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    lines_modified: int = 0
    functions_touched: int = 0
    diff_unified: str = ""

    @property
    def total_changes(self) -> int:
        return self.lines_added + self.lines_removed


@dataclass
class ArtifactDelta:
    """Before/after comparison of build artifacts."""
    binary_path: str = ""
    size_before_bytes: int = 0
    size_after_bytes: int = 0
    # Checksums for identity check
    md5_before: str = ""
    md5_after: str = ""
    sections_before: Dict[str, int] = field(default_factory=dict)  # .text, .data, .bss
    sections_after: Dict[str, int] = field(default_factory=dict)


@dataclass
class DifferentialReport:
    """Complete before/after analysis for one patch application."""

    # Identity
    patch_id: str = ""
    project: str = ""
    compiler: str = ""
    arch: str = ""

    # Core deltas
    test_delta: Optional[TestDelta] = None
    benchmark_delta: Optional[MetricDelta] = None    # execution time
    binary_size_delta: Optional[MetricDelta] = None   # artifact size
    memory_delta: Optional[MetricDelta] = None        # peak RSS (if measurable)
    code_delta: Optional[CodeDelta] = None

    # Additional metrics
    metrics: List[MetricDelta] = field(default_factory=list)
    artifact_delta: Optional[ArtifactDelta] = None

    # Verdict
    regressions_detected: List[str] = field(default_factory=list)
    improvements_detected: List[str] = field(default_factory=list)
    safe_to_apply: bool = False
    confidence_delta: float = 0.0  # how much this affects PatchRanker confidence
    analysis_duration_ms: float = 0.0

    def summary(self) -> str:
        lines = ["=" * 60, f"DIFFERENTIAL REPORT — {self.patch_id}"]
        lines.append(f"  Project: {self.project} | Compiler: {self.compiler} | Arch: {self.arch}")

        if self.code_delta:
            cd = self.code_delta
            lines.append(f"  Code: +{cd.lines_added}/-{cd.lines_removed} lines, "
                        f"{cd.files_changed} files, {cd.functions_touched} functions")

        if self.test_delta:
            td = self.test_delta
            lines.append(f"  Tests: {td.passed_before}→{td.passed_after} passed, "
                        f"{td.failed_before}→{td.failed_after} failed")
            if td.new_failures:
                lines.append(f"    ⚠️  NEW FAILURES: {td.new_failures}")
            if td.new_passes:
                lines.append(f"    ✅ NEW PASSES: {td.new_passes}")

        for m in self.metrics:
            lines.append(m.summary())

        if self.binary_size_delta:
            lines.append(self.binary_size_delta.summary())
        if self.benchmark_delta:
            lines.append(self.benchmark_delta.summary())

        lines.append("")
        if self.regressions_detected:
            lines.append("  ❌ REGRESSIONS DETECTED:")
            for r in self.regressions_detected:
                lines.append(f"     - {r}")
        if self.improvements_detected:
            lines.append("  ✅ IMPROVEMENTS:")
            for imp in self.improvements_detected:
                lines.append(f"     - {imp}")

        lines.append(f"  Safe to apply: {'YES ✅' if self.safe_to_apply else 'NO ❌'}")
        lines.append(f"  Confidence delta: {self.confidence_delta:+.2f}")
        return '\n'.join(lines)

    def to_evidence_dict(self) -> dict:
        """Convert to a dict suitable for PatchMemory evidence records."""
        evidence = {
            "patch_id": self.patch_id,
            "project": self.project,
            "compiler": self.compiler,
            "arch": self.arch,
            "safe_to_apply": self.safe_to_apply,
            "confidence_delta": self.confidence_delta,
        }
        if self.test_delta:
            evidence["tests"] = {
                "passed_before": self.test_delta.passed_before,
                "passed_after": self.test_delta.passed_after,
                "failed_before": self.test_delta.failed_before,
                "failed_after": self.test_delta.failed_after,
                "crashed_before": self.test_delta.crashed_before,
                "crashed_after": self.test_delta.crashed_after,
                "regression": self.test_delta.regression,
                "improvement": self.test_delta.improvement,
                "new_failures": self.test_delta.new_failures,
                "new_passes": self.test_delta.new_passes,
            }
        if self.binary_size_delta:
            evidence["binary_size"] = {
                "before_bytes": self.binary_size_delta.before,
                "after_bytes": self.binary_size_delta.after,
                "delta_pct": self.binary_size_delta.delta_pct,
            }
        if self.benchmark_delta:
            evidence["benchmark"] = {
                "before_ms": self.benchmark_delta.before,
                "after_ms": self.benchmark_delta.after,
                "delta_pct": self.benchmark_delta.delta_pct,
            }
        return evidence


# ═══════════════════════════════════════════════════════════════
# Analyzer
# ═══════════════════════════════════════════════════════════════

class DifferentialAnalyzer:
    """
    Compare project state before and after a patch.

    Usage:
        analyzer = DifferentialAnalyzer(project_root)
        analyzer.capture_baseline()       # before patch
        apply_patch(code)
        report = analyzer.compare()       # after patch → full differential
    """

    def __init__(self, project_root: Path):
        self.root = Path(project_root)
        self.patch_id = ""

        # Baseline (captured before patch)
        self._baseline_tests: Optional[TestRunResult] = None
        self._baseline_binary_size: int = 0
        self._baseline_binary_md5: str = ""
        self._baseline_mtime: float = 0.0
        self._baseline_file_contents: Dict[str, str] = {}  # path → content

    def capture_baseline(self, files_to_track: List[str] = None):
        """
        Capture "before" state. Call this BEFORE applying the patch.

        Args:
            files_to_track: list of source file paths (relative to root) to snapshot.
                            If None, auto-detects .c/.h/.cpp/.hpp/.rs/.go/.py files.
        """
        # Snapshot source files
        if files_to_track is None:
            files_to_track = []
            for ext in ['.c', '.h', '.cpp', '.hpp', '.cc', '.hh', '.rs', '.go', '.py']:
                for f in self.root.rglob(f'*{ext}'):
                    rel = str(f.relative_to(self.root))
                    if '/test' not in rel.lower() and 'test_' not in rel.lower():
                        files_to_track.append(rel)
                    if len(files_to_track) > 100:
                        break
                if len(files_to_track) > 100:
                    break

        self._baseline_file_contents = {}
        for rel_path in files_to_track[:200]:
            fpath = self.root / rel_path
            if fpath.exists() and fpath.is_file():
                try:
                    self._baseline_file_contents[rel_path] = fpath.read_text()
                except Exception:
                    pass

        # Snapshot test results
        self._baseline_tests = execute_test_suite(self.root)

        # Snapshot binary metrics
        self._snapshot_binary_metrics()

    def _snapshot_binary_metrics(self):
        """Capture binary size and checksum for BASELINE (before patch).
        
        Called only by capture_baseline(). Never by compare().
        """
        for pattern in ['build/*', '*.out', 'a.out', 'target/release/*', 'target/debug/*',
                        'build/bin/*', 'build/src/*', 'bin/*']:
            for binary in sorted(self.root.glob(pattern)):
                if binary.is_file() and binary.suffix in ('', '.out', '.elf'):
                    try:
                        self._baseline_binary_size = binary.stat().st_size
                        with open(binary, 'rb') as f:
                            self._baseline_binary_md5 = _md5(f.read())
                        self._baseline_mtime = binary.stat().st_mtime
                        return  # found baseline binary — done
                    except Exception:
                        pass

    def _read_current_binary_metrics(self) -> dict:
        """Read current binary metrics WITHOUT overwriting baseline.
        
        Called by compare() to get the "after" state.
        """
        for pattern in ['build/*', '*.out', 'a.out', 'target/release/*', 'target/debug/*',
                        'build/bin/*', 'build/src/*', 'bin/*']:
            for binary in sorted(self.root.glob(pattern)):
                if binary.is_file() and binary.suffix in ('', '.out', '.elf'):
                    try:
                        return {
                            'size': binary.stat().st_size,
                            'md5': _md5(binary.read_bytes()),
                        }
                    except Exception:
                        pass
        return {'size': 0, 'md5': ''}

    def compare(self, patch_id: str = "", project: str = "",
                compiler: str = "", arch: str = "",
                test_timeout: int = 300) -> DifferentialReport:
        """
        Compare current state ("after") against captured baseline ("before").

        Returns a DifferentialReport with all deltas computed.
        """
        t0 = time.time()
        report = DifferentialReport(
            patch_id=patch_id,
            project=project or self.root.name,
            compiler=compiler,
            arch=arch,
        )

        # ── Test delta ──────────────────────────────────────
        after_tests = execute_test_suite(self.root, test_timeout)
        if self._baseline_tests:
            report.test_delta = self._compute_test_delta(
                self._baseline_tests, after_tests
            )

        # ── Code delta ──────────────────────────────────────
        report.code_delta = self._compute_code_delta()

        # ── Binary size delta ─────────────────────────────
        current_binary = self._read_current_binary_metrics()
        if self._baseline_binary_size > 0:
            try:
                current_size = current_binary.get('size', 0)
                current_md5 = current_binary.get('md5', '')

                if current_size > 0:
                    delta_bytes = current_size - self._baseline_binary_size
                    delta_pct = (delta_bytes / self._baseline_binary_size) * 100
                    direction = DeltaDirection.NEUTRAL
                    if delta_pct > 5:
                        direction = DeltaDirection.WORSE
                    elif delta_pct < -5:
                        direction = DeltaDirection.BETTER

                    report.binary_size_delta = MetricDelta(
                        name="Binary size",
                        unit=" bytes",
                        before=self._baseline_binary_size,
                        after=current_size,
                        delta_absolute=delta_bytes,
                        delta_pct=delta_pct,
                        direction=direction,
                        threshold_pct=10.0,
                    )
            except Exception:
                pass

        # ── Benchmark delta (from test execution time as proxy) ──
        if self._baseline_tests and self._baseline_tests.total_duration_ms > 0:
            before_dur = self._baseline_tests.total_duration_ms
            after_dur = after_tests.total_duration_ms
            if after_dur > 0:
                delta_pct = ((after_dur - before_dur) / before_dur) * 100
                direction = DeltaDirection.NEUTRAL
                if delta_pct > 10:
                    direction = DeltaDirection.WORSE
                elif delta_pct < -10:
                    direction = DeltaDirection.BETTER

                report.metrics.append(MetricDelta(
                    name="Test suite duration",
                    unit="ms",
                    before=before_dur,
                    after=after_dur,
                    delta_absolute=after_dur - before_dur,
                    delta_pct=delta_pct,
                    direction=direction,
                ))

        # ── Compile regressions list ─────────────────────
        report.regressions_detected = []
        report.improvements_detected = []

        if report.test_delta and report.test_delta.regression:
            report.regressions_detected.append(
                f"Test regression: {len(report.test_delta.new_failures)} new failures, "
                f"{report.test_delta.crashed_after - report.test_delta.crashed_before} new crashes"
            )
        if report.test_delta and report.test_delta.improvement:
            report.improvements_detected.append(
                f"Test improvement: {len(report.test_delta.new_passes)} new passes"
            )

        if report.binary_size_delta and report.binary_size_delta.is_regression:
            report.regressions_detected.append(
                f"Binary size increased by {report.binary_size_delta.delta_pct:+.1f}%"
            )
        if report.binary_size_delta and report.binary_size_delta.direction == DeltaDirection.BETTER:
            report.improvements_detected.append(
                f"Binary size decreased by {abs(report.binary_size_delta.delta_pct):.1f}%"
            )

        for m in report.metrics:
            if m.is_regression:
                report.regressions_detected.append(f"{m.name}: {m.delta_pct:+.1f}%")
            elif m.direction == DeltaDirection.BETTER and m.significant:
                report.improvements_detected.append(f"{m.name}: {m.delta_pct:+.1f}%")

        # ── Verdict ─────────────────────────────────────
        report.safe_to_apply = (
            len(report.regressions_detected) == 0
            and (report.test_delta is None or not report.test_delta.regression)
        )

        # ── Confidence delta ────────────────────────────
        # Start neutral; regressions subtract, improvements add
        report.confidence_delta = 0.0
        for _ in report.regressions_detected:
            report.confidence_delta -= 0.25
        for _ in report.improvements_detected:
            report.confidence_delta += 0.10
        if report.safe_to_apply:
            report.confidence_delta = max(report.confidence_delta, 0.0)

        report.analysis_duration_ms = (time.time() - t0) * 1000
        return report

    def _compute_test_delta(self, before: TestRunResult,
                            after: TestRunResult) -> TestDelta:
        """Compare two TestRunResults to identify regressions and improvements."""
        delta = TestDelta(
            framework=after.framework.value,
            tests_before=before.total,
            tests_after=after.total,
            passed_before=before.passed,
            passed_after=after.passed,
            failed_before=before.failed,
            failed_after=after.failed,
            crashed_before=before.crashed,
            crashed_after=after.crashed,
            duration_before_ms=before.total_duration_ms,
            duration_after_ms=after.total_duration_ms,
        )

        # If we have per-test granularity, compare individual tests
        if before.test_cases and after.test_cases:
            before_map = {t.name: t for t in before.test_cases}
            after_map = {t.name: t for t in after.test_cases}

            for name, tc in after_map.items():
                if name in before_map:
                    before_tc = before_map[name]
                    # Test that passed before but fails now → regression
                    if before_tc.passed and not tc.passed:
                        delta.new_failures.append(name)
                    # Test that failed before but passes now → improvement
                    if not before_tc.passed and tc.passed:
                        delta.new_passes.append(name)

        # If no individual tests, use aggregate counts
        if delta.failed_after > delta.failed_before:
            delta.new_failures.append(
                f"{delta.failed_after - delta.failed_before} additional failures"
            )
        if delta.passed_after > delta.passed_before:
            delta.new_passes.append(
                f"{delta.passed_after - delta.passed_before} additional passes"
            )

        return delta

    def _compute_code_delta(self) -> CodeDelta:
        """Compute code change statistics by comparing current files to baseline."""
        cd = CodeDelta()
        total_added = 0
        total_removed = 0

        for rel_path, old_content in self._baseline_file_contents.items():
            fpath = self.root / rel_path
            if not fpath.exists():
                # File was deleted
                cd.files_changed += 1
                cd.lines_removed += len(old_content.split('\n'))
                continue

            try:
                new_content = fpath.read_text()
            except Exception:
                continue

            if old_content == new_content:
                continue

            cd.files_changed += 1
            diff = list(difflib.unified_diff(
                old_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f'a/{rel_path}',
                tofile=f'b/{rel_path}',
                lineterm='',
            ))

            for line in diff:
                if line.startswith('+') and not line.startswith('+++'):
                    cd.lines_added += 1
                elif line.startswith('-') and not line.startswith('---'):
                    cd.lines_removed += 1

            if cd.diff_unified:
                cd.diff_unified += '\n'
            cd.diff_unified += '\n'.join(diff[:100])  # cap at 100 lines

        # Count functions touched (crude: look for function definitions near + lines)
        func_pattern = r'^\+.*?\b(\w+)\s*\([^)]*\)\s*\{'
        import re
        funcs = set(re.findall(func_pattern, cd.diff_unified, re.MULTILINE))
        cd.functions_touched = len(funcs)

        return cd


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _md5(data: bytes) -> str:
    """Compute MD5 hash."""
    import hashlib
    return hashlib.md5(data).hexdigest()


# ═══════════════════════════════════════════════════════════════
# Integration with PatchMemory
# ═══════════════════════════════════════════════════════════════

def update_patch_memory_from_report(report: DifferentialReport, catalog):
    """
    Update PatchMemory with evidence from a differential report.
    
    Decides whether to record_success or record_failure based on the
    report's safe_to_apply verdict and regression analysis.
    """
    for pat in catalog.all_patches:
        if pat.id == report.patch_id:
            if report.safe_to_apply:
                pat.record_success(
                    project=report.project,
                    compiler=report.compiler,
                    arch=report.arch,
                )
            else:
                reasons = "; ".join(report.regressions_detected) if report.regressions_detected else "regression detected"
                pat.record_failure(
                    project=report.project,
                    compiler=report.compiler,
                    arch=report.arch,
                    reason=reasons,
                )
            return True
    return False


# ═══════════════════════════════════════════════════════════════
# Demo
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import shutil, subprocess

    tmp = Path("/tmp/quimera_diff_demo")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    # Create a test project with a known bug
    with open(str(tmp / "main.c"), "w") as f:
        f.write("""#include <stdio.h>
#include <stdlib.h>

int compute(int n) {
    int *buf = malloc(n * sizeof(int));
    int sum = 0;
    for (int i = 0; i < n; i++) {
        buf[i] = i;
        sum += buf[i];
    }
    free(buf);
    // BUG: no buf = NULL after free
    return sum;
}

int main() {
    printf("result: %d\\n", compute(10));
    return 0;
}
""")

    with open(str(tmp / "test.c"), "w") as f:
        f.write("""#include <stdio.h>
#include <assert.h>
int compute(int n);
int main() {
    assert(compute(10) == 45);
    assert(compute(1) == 0);
    assert(compute(0) == 0);
    printf("All tests passed\\n");
    return 0;
}
""")

    with open(str(tmp / "Makefile"), "w") as f:
        f.write("""CC=gcc
CFLAGS=-Wall -Werror
test: test_bin
\t./test_bin
test_bin: main.c test.c
\t$(CC) $(CFLAGS) -o test_bin main.c test.c
clean:
\trm -f test_bin
""")

    # Build baseline
    print("Building...")
    subprocess.run("make test_bin 2>&1", shell=True, cwd=str(tmp))

    analyzer = DifferentialAnalyzer(tmp)
    analyzer.capture_baseline()

    # Apply patch: add buf = NULL after free
    with open(str(tmp / "main.c"), "r") as f:
        code = f.read()
    patched = code.replace("free(buf);\n    // BUG", "free(buf);\n    buf = NULL;\n    // BUG")
    with open(str(tmp / "main.c"), "w") as f:
        f.write(patched)

    subprocess.run("make test_bin 2>&1", shell=True, cwd=str(tmp))

    report = analyzer.compare(patch_id="DEMO-001", project="quimera-demo",
                              compiler="gcc", arch="x86_64")

    print(report.summary())
    print(f"\nEvidence dict: {report.to_evidence_dict()}")

    shutil.rmtree(tmp, ignore_errors=True)
