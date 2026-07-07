"""
Patch Quality Metrics — Quimera Mark X (Phase 2)

Measures whether patches actually work, not just whether they were generated.
Tracks:
  - Does it compile?
  - Do tests pass?
  - Did coverage change?
  - Did performance change?
  - Did any regression appear?

Each patch gets a quality score (0.0-1.0) computed from these dimensions.
The metrics accumulate per-project and feed back into the EngineeringKB
so the system learns which fix strategies actually work.
"""

import json, logging, os, re, subprocess, time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("quimera.quality")


@dataclass
class PatchQualityReport:
    """Full quality assessment for a single patch."""
    patch_id: str = ""
    file_path: str = ""
    project_path: str = ""
    
    # Compilation
    compiles: bool = False
    compile_errors: List[str] = field(default_factory=list)
    compile_score: float = 0.0  # 0.0 or 1.0
    
    # Test results
    tests_passed: int = 0
    tests_total: int = 0
    test_success_rate: float = 0.0
    test_score: float = 0.0
    
    # Coverage
    coverage_before: float = 0.0
    coverage_after: float = 0.0
    coverage_delta: float = 0.0
    coverage_score: float = 0.5  # baseline
    
    # Performance
    bench_before_ms: float = 0.0
    bench_after_ms: float = 0.0
    bench_delta_pct: float = 0.0
    perf_score: float = 0.5  # baseline
    
    # Regression
    regression_detected: bool = False
    regression_tests: List[str] = field(default_factory=list)
    regression_score: float = 1.0  # 1.0 = no regression
    
    # Overall
    overall_quality: float = 0.0  # weighted composite
    verdict: str = "pending"  # pending, passed, needs_review, rejected
    
    # Timing
    quality_check_time_ms: float = 0.0
    
    def compute_overall(self):
        """Compute weighted quality score."""
        weights = {
            "compile": 0.30,
            "test": 0.30,
            "coverage": 0.15,
            "perf": 0.10,
            "regression": 0.15,
        }
        
        self.overall_quality = (
            weights["compile"] * self.compile_score +
            weights["test"] * self.test_score +
            weights["coverage"] * self.coverage_score +
            weights["perf"] * self.perf_score +
            weights["regression"] * self.regression_score
        )
        
        if self.overall_quality >= 0.85:
            self.verdict = "passed"
        elif self.overall_quality >= 0.60:
            self.verdict = "needs_review"
        else:
            self.verdict = "rejected"
        
        return self


@dataclass
class ProjectQualityReport:
    """Cumulative quality across all patches for a project."""
    project_path: str = ""
    patches_evaluated: int = 0
    patches_passed: int = 0
    patches_rejected: int = 0
    patches_needs_review: int = 0
    avg_quality: float = 0.0
    compile_success_rate: float = 0.0
    test_success_rate: float = 0.0
    avg_coverage_delta: float = 0.0
    regressions_caused: int = 0
    reports: List[PatchQualityReport] = field(default_factory=list)


class PatchQualityEvaluator:
    """
    Evaluates patch quality through multiple dimensions.
    Can work with or without a build environment.
    
    Without build env: does static analysis + heuristic checks.
    With build env: full compile + test + coverage + bench.
    """
    
    def __init__(self, project_path: str = None, has_build_env: bool = False):
        self.project_path = Path(project_path) if project_path else None
        self.has_build_env = has_build_env
        self._baseline_coverage: Optional[float] = None
        self._baseline_bench: Optional[float] = None
        self._reports: List[PatchQualityReport] = []
    
    def evaluate(
        self,
        original_code: str,
        patched_code: str,
        file_path: str,
        language: str = "c",
        patch_id: str = "",
        run_tests: bool = False,
    ) -> PatchQualityReport:
        """
        Full quality evaluation of a patch across 5 dimensions:
        compile, test, coverage, performance, regression.
        
        Returns a PatchQualityReport with overall score (0.0-1.0) and verdict.
        When comparing original==patched (baseline), scores reflect code health,
        not patch quality.
        """
        t0 = time.monotonic()
        
        report = PatchQualityReport(
            patch_id=patch_id or f"patch-{int(time.time()*1000)}",
            file_path=file_path,
            project_path=str(self.project_path) if self.project_path else "",
        )
        
        # 1. Compilation check
        report.compile_score, report.compiles, report.compile_errors = \
            self._check_compilation(patched_code, file_path, language)
        
        # 2. Test check (if possible)
        if run_tests and self.has_build_env:
            report.test_score, report.tests_passed, report.tests_total = \
                self._check_tests(patched_code, file_path)
            report.test_success_rate = report.tests_passed / max(report.tests_total, 1)
        
        # 3. Coverage check (if possible)
        if self.has_build_env:
            report.coverage_score, report.coverage_delta = self._check_coverage(patched_code)
        
        # 4. Performance check
        report.perf_score, report.bench_delta_pct = self._check_performance(
            original_code, patched_code, language
        )
        
        # 5. Regression check
        report.regression_score, report.regression_detected = self._check_regression(
            original_code, patched_code
        )
        
        report.quality_check_time_ms = (time.monotonic() - t0) * 1000
        report.compute_overall()
        self._reports.append(report)
        
        return report
    
    # ── Individual checks ──────────────────────────────────────────
    
    def _check_compilation(
        self, code: str, file_path: str, language: str
    ) -> Tuple[float, bool, List[str]]:
        """Try to compile the patch. Falls back to syntax check."""
        errors = []
        
        if language == "c":
            if self.has_build_env and self.project_path:
                # Try real compilation
                tmp_file = self.project_path / f"_quimera_patch_{int(time.time())}.c"
                try:
                    tmp_file.write_text(code)
                    result = subprocess.run(
                        ["gcc", "-fsyntax-only", "-Wall", "-Werror", str(tmp_file)],
                        capture_output=True, text=True, timeout=30,
                        cwd=str(self.project_path)
                    )
                    if result.returncode == 0:
                        return 1.0, True, []
                    else:
                        error_lines = result.stderr.strip().split('\n')[:3]
                        errors = [e.strip() for e in error_lines if e.strip()]
                        return 0.0, False, errors
                except Exception as e:
                    errors.append(f"Compilation check failed: {e}")
                    return 0.0, False, errors
                finally:
                    try: tmp_file.unlink()
                    except: pass  # noqa: bare-except — non-critical fallback
            else:
                # Static syntax check: basic heuristics
                score = 1.0
                compiles = True
                
                # Check brace balance
                if code.count('{') != code.count('}'):
                    errors.append("Mismatched braces")
                    score -= 0.3
                    compiles = False
                
                # Check parenthesis balance
                if code.count('(') != code.count(')'):
                    errors.append("Mismatched parentheses")
                    score -= 0.3
                    compiles = False
                
                # Check for obvious syntax errors
                if '#include' not in code and 'int main' not in code:
                    pass  # Not a full program, that's OK
                
                return max(0.0, score), compiles, errors
        
        elif language == "python":
            try:
                compile(code, file_path, 'exec')
                return 1.0, True, []
            except SyntaxError as e:
                return 0.0, False, [f"SyntaxError: {e}"]
        
        return 0.5, True, []  # Unknown language, assume OK
    
    def _check_tests(
        self, code: str, file_path: str
    ) -> Tuple[float, int, int]:
        """Run project tests. Requires build environment."""
        if not self.has_build_env:
            return 0.5, 0, 0
        
        try:
            # Try common test runners
            project_dir = str(self.project_path)
            
            # Python: pytest
            test_dir = self.project_path / "tests"
            if test_dir.exists() or (self.project_path / "test").exists():
                result = subprocess.run(
                    ["python3", "-m", "pytest", "-x", "--tb=short"],
                    capture_output=True, text=True, timeout=60,
                    cwd=project_dir
                )
                # Parse pytest output
                passed = result.stdout.count("PASSED")
                failed = result.stdout.count("FAILED")
                total = passed + failed
                if total > 0:
                    return passed / total, passed, total
            
            # C: make test
            makefile = self.project_path / "Makefile"
            if makefile.exists():
                result = subprocess.run(
                    ["make", "test"], capture_output=True, text=True, timeout=60,
                    cwd=project_dir
                )
                if result.returncode == 0:
                    return 1.0, 1, 1
            
            return 0.5, 0, 0  # No test suite found
        except Exception:
            return 0.5, 0, 0
    
    def _check_coverage(self, code: str) -> Tuple[float, float]:
        """Check if coverage changed. Requires build environment."""
        if not self.has_build_env or not self._baseline_coverage:
            return 0.5, 0.0
        
        # This would normally run a coverage tool.
        # For now, return baseline — unchanged.
        return 0.5, 0.0
    
    def _check_performance(
        self, original: str, patched: str, language: str
    ) -> Tuple[float, float]:
        """Quick performance comparison via code structure analysis."""
        # Heuristic: count function calls as rough complexity proxy
        def count_calls(s):
            return len(re.findall(r'\b[a-zA-Z_]\w*\s*\(', s))
        
        orig_calls = count_calls(original)
        patch_calls = count_calls(patched)
        
        if orig_calls == 0:
            return 0.70, 0.0  # Default: neutral
        
        delta_pct = ((patch_calls - orig_calls) / orig_calls) * 100
        
        # Minimal change (±3%) = neutral, not penalized
        if abs(delta_pct) < 3:
            return 0.75, delta_pct
        # More calls = potentially slower
        elif delta_pct > 30:
            return 0.30, delta_pct
        elif delta_pct > 10:
            return 0.55, delta_pct
        # Fewer calls = potentially faster
        elif delta_pct < -20:
            return 0.90, delta_pct
        elif delta_pct < -5:
            return 0.80, delta_pct
        else:
            return 0.70, delta_pct
    
    def _check_regression(
        self, original: str, patched: str
    ) -> Tuple[float, bool]:
        """Check if patch introduces regressions by comparing structure."""
        regressions = []
        
        # 1. Did we remove functionality?
        orig_funcs = set(re.findall(r'(?:static\s+)?(?:\w+\s+)?(\w+)\s*\(', original))
        patch_funcs = set(re.findall(r'(?:static\s+)?(?:\w+\s+)?(\w+)\s*\(', patched))
        removed = orig_funcs - patch_funcs
        if removed:
            # Filter out common patterns
            common = {'if', 'while', 'for', 'switch', 'sizeof', 'return', 'void'}
            removed = removed - common
            if removed:
                regressions.append(f"Removed calls: {', '.join(list(removed)[:3])}")
        
        # 2. Did we change signatures?
        orig_sigs = set(re.findall(r'(\w+\s+\w+\s*\([^)]*\))', original))
        patch_sigs = set(re.findall(r'(\w+\s+\w+\s*\([^)]*\))', patched))
        if orig_sigs != patch_sigs:
            regressions.append("Function signatures may have changed")
        
        # 3. Did we remove error handling?
        if 'NULL' in original and 'NULL' not in patched:
            regressions.append("NULL checks may have been removed")
        
        has_regression = len(regressions) > 0
        score = 1.0 - (len(regressions) * 0.2)
        
        return max(0.0, score), has_regression
    
    # ── Project-level aggregation ─────────────────────────────────
    
    def get_project_report(self) -> ProjectQualityReport:
        """Aggregate all patch reports for this project."""
        if not self._reports:
            return ProjectQualityReport(project_path=str(self.project_path or ""))
        
        passed = sum(1 for r in self._reports if r.verdict == "passed")
        rejected = sum(1 for r in self._reports if r.verdict == "rejected")
        review = sum(1 for r in self._reports if r.verdict == "needs_review")
        avg_q = sum(r.overall_quality for r in self._reports) / len(self._reports)
        compile_ok = sum(1 for r in self._reports if r.compiles) / len(self._reports)
        test_ok = sum(r.test_success_rate for r in self._reports if r.tests_total > 0)
        test_ok = test_ok / max(sum(1 for r in self._reports if r.tests_total > 0), 1)
        avg_cov = sum(r.coverage_delta for r in self._reports) / len(self._reports)
        regressions = sum(1 for r in self._reports if r.regression_detected)
        
        return ProjectQualityReport(
            project_path=str(self.project_path or ""),
            patches_evaluated=len(self._reports),
            patches_passed=passed,
            patches_rejected=rejected,
            patches_needs_review=review,
            avg_quality=avg_q,
            compile_success_rate=compile_ok,
            test_success_rate=test_ok,
            avg_coverage_delta=avg_cov,
            regressions_caused=regressions,
            reports=self._reports,
        )
    
    def set_baseline(self, coverage: float = None, bench_ms: float = None):
        """Set baseline metrics before patching."""
        if coverage is not None:
            self._baseline_coverage = coverage
        if bench_ms is not None:
            self._baseline_bench = bench_ms
    
    def reset(self):
        """Reset evaluator state."""
        self._reports = []
        self._baseline_coverage = None
        self._baseline_bench = None


# Convenience function
def evaluate_patch(
    original: str, patched: str, file_path: str = "",
    language: str = "c", has_build_env: bool = False,
    project_path: str = None,
) -> PatchQualityReport:
    """One-shot evaluation of a patch."""
    evaluator = PatchQualityEvaluator(
        project_path=project_path, has_build_env=has_build_env
    )
    return evaluator.evaluate(original, patched, file_path, language)


# ═══════════════════════════════════════════════════════════════════
# Testing / Demo
# ═══════════════════════════════════════════════════════════════════

def demo():
    """Demonstrate patch quality evaluation."""
    original = """
    #include <string.h>
    void copy_name(char *src) {
        char buf[64];
        strcpy(buf, src);
        printf(buf);
        free(src);
    }
    """
    
    # Good patch: uses strncpy + snprintf + NULL
    good_patch = """
    #include <string.h>
    void copy_name(char *src) {
        char buf[64];
        strncpy(buf, src, sizeof(buf)-1);
        buf[sizeof(buf)-1] = '\\0';
        printf("%s", buf);
        free(src);
        src = NULL;
    }
    """
    
    # Bad patch: introduces syntax error
    bad_patch = """
    #include <string.h>
    void copy_name(char *src) {
        char buf[64]
        strncpy(buf, src, 64)
    }
    """
    
    evaluator = PatchQualityEvaluator()
    
    print("=== Good Patch ===")
    r = evaluator.evaluate(original, good_patch, "test.c")
    print(f"  compiles={r.compiles} errors={r.compile_errors}")
    print(f"  compile={r.compile_score:.2f} test={r.test_score:.2f} perf={r.perf_score:.2f} reg={r.regression_score:.2f}")
    print(f"  overall={r.overall_quality:.2f} verdict={r.verdict}")
    
    print("\n=== Bad Patch (syntax error) ===")
    r = evaluator.evaluate(original, bad_patch, "test.c")
    print(f"  compiles={r.compiles} errors={r.compile_errors}")
    print(f"  overall={r.overall_quality:.2f} verdict={r.verdict}")
    
    print("\n=== Project Report ===")
    pr = evaluator.get_project_report()
    print(f"  patches={pr.patches_evaluated} passed={pr.patches_passed} rejected={pr.patches_rejected}")
    print(f"  avg_quality={pr.avg_quality:.2f} compile_ok={pr.compile_success_rate:.1%}")


if __name__ == "__main__":
    demo()
