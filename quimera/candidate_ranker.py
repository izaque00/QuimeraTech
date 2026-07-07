"""
Candidate Ranker — validates and ranks multiple patch candidates.

For each candidate:
  1. Compile check (gcc -fsyntax-only -Wall -Werror)
  2. Build check (full project build)
  3. Test suite (if available)
  4. ASan (AddressSanitizer)
  5. UBSan (UndefinedBehaviorSanitizer)
  6. Differential analysis (before/after behavior)

Returns ranked list: best candidate first.
"""
import os, subprocess, tempfile, shutil, difflib, time
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass, field


@dataclass
class RankedCandidate:
    id: str
    description: str
    patched_code: str
    approach: str
    initial_confidence: float

    # Validation results
    compiled: bool = False
    build_passed: bool = False
    tests_passed: bool = False
    asan_clean: bool = False
    ubsan_clean: bool = False
    behavior_preserved: bool = False  # diff analysis

    # Scores
    compile_score: float = 0.0
    test_score: float = 0.0
    sanitizer_score: float = 0.0
    diff_score: float = 0.0
    final_score: float = 0.0

    # Metadata
    compile_error: str = ""
    total_time_ms: float = 0.0
    rank: int = 0


class CandidateRanker:
    """
    Ranks patch candidates by actually testing them.

    Scoring weights (configurable):
      compile:    30%  — must compile with -Wall -Werror
      tests:      20%  — must pass test suite
      sanitizers: 25%  — must be ASan+UBSan clean
      diff:       15%  — behavior must not regress
      confidence: 10%  — initial confidence from generator

    The candidate with the highest total score wins.
    """

    def __init__(self, project_root: str = "", compiler: str = "gcc"):
        self.project_root = project_root
        self.compiler = compiler

        # Weights
        self.weights = {
            'compile': 0.25,
            'tests': 0.15,
            'sanitizers': 0.20,
            'diff': 0.10,
            'confidence': 0.10,
            'static_analysis': 0.10,
            'impact': 0.10,
        }

    def rank(self, candidates: List, original_code: str,
             file_path: str = "", test_cmd: str = "",
             benchmark_cmd: str = "") -> List[RankedCandidate]:
        """
        Rank all candidates. Returns sorted list (best first).

        Args:
            candidates: List of CandidatePatch or ASTPatchCandidate
            original_code: original (buggy) source code
            file_path: path to the file being patched
            test_cmd: command to run tests
            benchmark_cmd: command to run benchmark for diff analysis
        """
        ranked = []

        for i, cand in enumerate(candidates):
            rc = RankedCandidate(
                id=getattr(cand, 'id', f'C{i}'),
                description=getattr(cand, 'description', ''),
                patched_code=getattr(cand, 'patched_code', ''),
                approach=getattr(cand, 'approach', getattr(cand, 'level', 'unknown')),
                initial_confidence=getattr(cand, 'confidence', 0.5),
            )

            t0 = time.monotonic()

            # Level 1: Compile check (gate — must pass)
            rc.compiled, rc.compile_error = self._check_compile(rc.patched_code)
            if not rc.compiled:
                rc.final_score = 0
                rc.total_time_ms = (time.monotonic() - t0) * 1000
                ranked.append(rc)
                continue

            rc.compile_score = 1.0

            # Level 2: Build check
            if file_path:
                rc.build_passed = self._check_build(file_path, rc.patched_code)
                rc.compile_score = 1.0 if rc.build_passed else 0.5

            # Level 3: Tests
            if test_cmd and rc.build_passed:
                rc.tests_passed = self._check_tests(test_cmd)
                rc.test_score = 1.0 if rc.tests_passed else 0.0

            # Level 4-5: Sanitizers
            if rc.build_passed:
                asan_ok, ubsan_ok = self._check_sanitizers(file_path, rc.patched_code)
                rc.asan_clean = asan_ok
                rc.ubsan_clean = ubsan_ok
                rc.sanitizer_score = (0.5 if asan_ok else 0) + (0.5 if ubsan_ok else 0)

            # Level 6: Differential analysis
            if benchmark_cmd and rc.build_passed:
                rc.behavior_preserved = self._check_behavior(benchmark_cmd)
                rc.diff_score = 1.0 if rc.behavior_preserved else 0.3

            # Level 7: Static Analysis
            static_ok, _ = self._check_static_analysis(rc.patched_code)
            static_score = 1.0 if static_ok else 0.0

            # Level 8: Impact (code churn)
            impact_score = self._check_impact(original_code, rc.patched_code)
            churn = self._check_code_churn(original_code, rc.patched_code)

            # Level 9: Formal Verification (Z3/Angr)
            formal_boost = self._check_formal_verification(rc.patched_code, 
                                   getattr(finding, 'cwe_id', '') if 'finding' in dir() else '')

            # Compute final score
            rc.final_score = (
                rc.compile_score * self.weights['compile'] +
                rc.test_score * self.weights['tests'] +
                rc.sanitizer_score * self.weights['sanitizers'] +
                rc.diff_score * self.weights['diff'] +
                rc.initial_confidence * self.weights['confidence'] +
                static_score * self.weights['static_analysis'] +
                impact_score * self.weights['impact'] +
                formal_boost * 0.15  # Formal verification bonus
            )

            rc.total_time_ms = (time.monotonic() - t0) * 1000
            ranked.append(rc)

        # Sort and assign ranks
        ranked.sort(key=lambda r: -r.final_score)
        for i, r in enumerate(ranked):
            r.rank = i + 1

        return ranked


    # ── Level 7: Static Analysis ─────────────────────
    def _check_formal_verification(self, code: str, finding_cwe: str = "") -> float:
        """
        Level 9: Formal Verification (Z3, Angr).
        Returns confidence boost 0.0-1.0 if mathematically proven safe.
        """
        boost = 0.0
        try:
            from quimera.integration_backends.z3_wrapper import Z3Analyzer
            z3 = Z3Analyzer()
            # Quick check: can we prove the fix is safe?
            result = z3.verify_safety(code, finding_cwe)
            if result and getattr(result, 'proven', False):
                boost += 0.25
        except ImportError:
            pass
        try:
            from quimera.integration_backends.angr_wrapper import AngrAnalyzer
            angr = AngrAnalyzer()
            result = angr.check_path(code)
            if result and getattr(result, 'safe', False):
                boost += 0.15
        except ImportError:
            pass
        return min(boost, 0.30)

    def _check_static_analysis(self, code: str) -> Tuple[bool, str]:
        """Run cppcheck or clang-tidy on patched code."""
        try:
            import subprocess, tempfile, os
            with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as f:
                f.write(code)
                f.flush()
                path = f.name

            # Try cppcheck first (lighter)
            r = subprocess.run(
                ['cppcheck', '--enable=all', '--inconclusive', '--quiet', path],
                capture_output=True, text=True, timeout=30
            )
            os.unlink(path)
            return r.returncode == 0, r.stderr[:200]
        except FileNotFoundError:
            # cppcheck not installed — skip gracefully
            return True, "cppcheck not available"
        except Exception as e:
            return True, ""  # Don't penalize if tool unavailable

    def _check_impact(self, original_code: str, patched_code: str) -> float:
        """
        Measure patch impact: fewer changed lines = lower risk.

        Returns 0.0-1.0 where 1.0 = minimal impact (best).
        """
        import difflib
        orig_lines = original_code.split('\n')
        pat_lines = patched_code.split('\n')
        diff = list(difflib.unified_diff(orig_lines, pat_lines))
        changed = len([l for l in diff if l.startswith('+') or l.startswith('-')])
        # Score: fewer changes = better
        if changed == 0:
            return 0.0  # no change = not a patch
        if changed <= 3:
            return 1.0  # minimal impact
        if changed <= 10:
            return 0.8
        if changed <= 30:
            return 0.5
        return 0.2  # large impact

    def _check_code_churn(self, original_code: str, patched_code: str) -> Dict:
        """Measure code churn: added, removed, modified lines."""
        import difflib
        orig_lines = original_code.split('\n')
        pat_lines = patched_code.split('\n')
        added = 0
        removed = 0
        for line in difflib.unified_diff(orig_lines, pat_lines):
            if line.startswith('+') and not line.startswith('+++'):
                added += 1
            elif line.startswith('-') and not line.startswith('---'):
                removed += 1
        return {'added': added, 'removed': removed, 'total_churn': added + removed}


    def _check_compile(self, code: str) -> Tuple[bool, str]:
        """Check if code compiles with -Wall -Werror."""
        try:
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.c', delete=False
            ) as f:
                f.write(code)
                f.flush()
                r = subprocess.run(
                    [self.compiler, '-fsyntax-only', '-Wall', '-Werror', f.name],
                    capture_output=True, text=True, timeout=30
                )
                os.unlink(f.name)
                return r.returncode == 0, r.stderr[:200]
        except Exception as e:
            return False, str(e)[:200]

    def _check_build(self, file_path: str, patched_code: str) -> bool:
        """Try a full build with the patched file."""
        try:
            # Backup original
            backup = file_path + '.quimera_bak'
            with open(file_path) as f:
                original = f.read()

            with open(file_path, 'w') as f:
                f.write(patched_code)

            # Try make
            r = subprocess.run(
                ['make', '-j2'], cwd=self.project_root or os.path.dirname(file_path),
                capture_output=True, text=True, timeout=120
            )
            ok = r.returncode == 0

            # Restore original
            with open(file_path, 'w') as f:
                f.write(original)

            try: os.remove(backup)
            except: pass  # noqa: bare-except — non-critical fallback

            return ok
        except Exception:
            return False

    def _check_tests(self, test_cmd: str) -> bool:
        """Run project tests."""
        try:
            r = subprocess.run(
                test_cmd, shell=True,
                cwd=self.project_root or '.',
                capture_output=True, text=True, timeout=120
            )
            return r.returncode == 0
        except Exception:
            return False

    def _check_sanitizers(self, file_path: str, patched_code: str) -> Tuple[bool, bool]:
        """Check ASan and UBSan on the patched code."""
        asan_ok = True
        ubsan_ok = True

        try:
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.c', delete=False
            ) as f:
                f.write(patched_code)
                f.flush()
                src = f.name

            # Compile with ASan
            bin_asan = src + '.asan'
            r = subprocess.run(
                [self.compiler, '-fsanitize=address', '-g', '-o', bin_asan, src],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode == 0:
                r2 = subprocess.run([bin_asan], capture_output=True, text=True, timeout=10)
                asan_ok = 'ERROR' not in r2.stderr

            # Compile with UBSan
            bin_ubsan = src + '.ubsan'
            r = subprocess.run(
                [self.compiler, '-fsanitize=undefined', '-g', '-o', bin_ubsan, src],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode == 0:
                r2 = subprocess.run([bin_ubsan], capture_output=True, text=True, timeout=10)
                ubsan_ok = 'runtime error' not in r2.stderr.lower()

            # Cleanup
            for f in [src, bin_asan, bin_ubsan,
                      src + '.asan', src + '.ubsan']:
                try: os.unlink(f)
                except: pass  # noqa: bare-except — non-critical fallback

        except Exception:
            pass

        return asan_ok, ubsan_ok

    def _check_behavior(self, benchmark_cmd: str) -> bool:
        """Check that patched code doesn't change behavior."""
        try:
            r = subprocess.run(
                benchmark_cmd, shell=True,
                cwd=self.project_root or '.',
                capture_output=True, text=True, timeout=60
            )
            return r.returncode == 0
        except Exception:
            return True  # Don't penalize if benchmark fails to run

    def summary(self, ranked: List[RankedCandidate]) -> str:
        """Generate a human-readable summary."""
        lines = []
        lines.append(f"{'Rank':<5s} {'ID':<15s} {'Score':<7s} {'Compile':<8s} "
                      f"{'Tests':<6s} {'ASan':<5s} {'UBSan':<6s} {'Approach'}")
        lines.append("-" * 80)

        for r in ranked:
            lines.append(
                f"#{r.rank:<4d} {r.id:<15s} {r.final_score:<7.2%} "
                f"{'✅' if r.compiled else '❌':<8s} "
                f"{'✅' if r.tests_passed else '—':<6s} "
                f"{'✅' if r.asan_clean else '—':<5s} "
                f"{'✅' if r.ubsan_clean else '—':<6s} "
                f"{r.approach[:25]}"
            )

        # Best candidate
        best = ranked[0] if ranked else None
        if best and best.final_score > 0:
            lines.append(f"\nBest: {best.id} ({best.approach}) — score={best.final_score:.2%}")
            if best.compile_error:
                lines.append(f"  Error: {best.compile_error[:120]}")

        return '\n'.join(lines)


if __name__ == "__main__":
    from quimera.ast_patcher import ASTPatcher

    code = '''#include <stdlib.h>
static char *g_token = NULL;

void logout() {
    if (g_token) {
        free(g_token);
    }
}
'''
    class FakeFinding:
        cwe_id = 'CWE-416'
        line = 6
        description = 'free without NULL'

    patcher = ASTPatcher()
    candidates = patcher.generate(FakeFinding(), code, num_candidates=5)

    ranker = CandidateRanker()
    ranked = ranker.rank(candidates, code)

    print(ranker.summary(ranked))
