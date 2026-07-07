"""Test Suite Executor — multi-build-system real test runner for Quimera.

Replaces the naive TestValidator. Detects the project's actual test framework
and runs it properly — not just 'make test'.

Supports: make test, ctest, cmake --build + test, pytest, cargo test, go test,
         meson test, bazel test, autotools (make check), catch2, gtest, boost.test

Each run produces a TestRunResult with granular pass/fail/skip counts,
per-test timing, stack traces, and exit codes — all consumed by the
DifferentialAnalyzer.
"""

import subprocess, time, json, re, shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum

from .base import ValidationPlugin, ValidatorResult, ValidatorLevel


# ═══════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════

class Framework(Enum):
    """Detected test framework."""
    MAKE_TEST = "make_test"
    MAKE_CHECK = "make_check"        # autotools convention
    CTEST = "ctest"
    CMAKE_TEST = "cmake_test"        # cmake --build + ctest
    PYTEST = "pytest"
    CARGO_TEST = "cargo_test"
    GO_TEST = "go_test"
    MESON_TEST = "meson_test"
    BAZEL_TEST = "bazel_test"
    CATCH2 = "catch2"                # binary with --list-tests
    GTEST = "gtest"                  # binary with --gtest_list_tests
    BOOST_TEST = "boost_test"        # binary with --list_content
    NIMBLE = "nimble_test"           # Nim
    ZIG_TEST = "zig_test"
    CUSTOM_SCRIPT = "custom_script"  # ./run_tests.sh, ./test.sh
    CUSTOM_BINARY = "custom_binary"  # ./test_binary
    UNKNOWN = "unknown"


@dataclass
class TestCaseResult:
    """Single test case outcome."""
    name: str
    passed: bool = False
    skipped: bool = False
    duration_ms: float = 0.0
    error_message: str = ""
    stack_trace: str = ""


@dataclass
class TestRunResult:
    """Complete test run output, ready for differential comparison."""
    framework: Framework = Framework.UNKNOWN
    command: str = ""

    # Counts
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    crashed: int = 0                      # segfault / timeout (not just assertion fail)

    # Timing
    total_duration_ms: float = 0.0
    slowest_test: str = ""
    slowest_duration_ms: float = 0.0

    # Raw
    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""

    # Detailed (if parser could extract)
    test_cases: List[TestCaseResult] = field(default_factory=list)
    crash_details: List[str] = field(default_factory=list)   # ASan, segfault, timeout

    # Binary artifacts for before/after comparison
    binary_path: Optional[str] = None
    binary_size_bytes: int = 0

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.passed / self.total

    @property
    def summary(self) -> str:
        return (
            f"{self.passed}/{self.total} passed"
            + (f", {self.failed} failed" if self.failed else "")
            + (f", {self.skipped} skipped" if self.skipped else "")
            + (f", {self.crashed} crashed" if self.crashed else "")
            + f"  [{self.total_duration_ms:.0f}ms]"
        )

    def to_dict(self) -> dict:
        return {
            "framework": self.framework.value,
            "command": self.command,
            "counts": {"total": self.total, "passed": self.passed,
                       "failed": self.failed, "skipped": self.skipped,
                       "crashed": self.crashed},
            "pass_rate": round(self.pass_rate, 4),
            "duration_ms": self.total_duration_ms,
            "exit_code": self.exit_code,
            "crash_details": self.crash_details,
        }


# ═══════════════════════════════════════════════════════════════
# Detector
# ═══════════════════════════════════════════════════════════════

def detect_test_framework(project_root: Path) -> Tuple[Framework, Optional[str]]:
    """
    Detect which test framework the project uses.
    Returns (framework, extra_info) — e.g. (CTEST, "build/") or (CUSTOM_BINARY, "./tests/test_runner")
    """
    r = project_root

    # Check for explicit test scripts first
    for script in ["run_tests.sh", "test.sh", "run_tests.py", "test_runner.sh"]:
        if (r / script).exists():
            return Framework.CUSTOM_SCRIPT, script

    # Build-system-level test targets
    mf = r / "Makefile"
    if mf.exists():
        mf_text = mf.read_text()
        if re.search(r'^test\s*:', mf_text, re.MULTILINE):
            return Framework.MAKE_TEST, None
        if re.search(r'^check\s*:', mf_text, re.MULTILINE):
            return Framework.MAKE_CHECK, None

    # CMake + CTest
    if (r / "CTestTestfile.cmake").exists() or (r / "CTestConfig.cmake").exists():
        return Framework.CTEST, None
    if (r / "CMakeLists.txt").exists():
        # Check if CTest is enabled
        cmake_text = (r / "CMakeLists.txt").read_text()
        if "enable_testing" in cmake_text or "add_test" in cmake_text:
            # Find build dir
            for build_dir in ["build", "cmake-build-debug", "cmake-build-release", "out"]:
                bd = r / build_dir
                if (bd / "CTestTestfile.cmake").exists():
                    return Framework.CTEST, str(bd)
            return Framework.CTEST, "build"

    # Rust / Cargo
    if (r / "Cargo.toml").exists():
        return Framework.CARGO_TEST, None

    # Go
    if (r / "go.mod").exists():
        return Framework.GO_TEST, None

    # Python
    if list(r.glob("test_*.py")) or list(r.glob("*_test.py")) or (r / "tests").is_dir():
        return Framework.PYTEST, None

    # Meson
    if (r / "meson.build").exists():
        return Framework.MESON_TEST, None

    # Bazel
    if (r / "BUILD").exists() or (r / "BUILD.bazel").exists():
        return Framework.BAZEL_TEST, None

    # Standalone test binaries (common in C/C++ projects)
    for pattern in ["**/test_*", "**/*_test", "**/*_tests", "**/tests/*", "build/**/test_*"]:
        for binary in r.glob(pattern):
            if binary.is_file() and not binary.suffix in [".c", ".cpp", ".h", ".o", ".a", ".so"]:
                if _is_executable(binary):
                    return Framework.CUSTOM_BINARY, str(binary)

    return Framework.UNKNOWN, None


def _is_executable(path: Path) -> bool:
    """Check if file is an ELF/Mach-O/PE binary or script with shebang."""
    try:
        with open(path, 'rb') as f:
            header = f.read(4)
        # ELF
        if header[:4] == b'\x7fELF':
            return True
        # Mach-O
        if header[:4] in (b'\xce\xfa\xed\xfe', b'\xcf\xfa\xed\xfe',
                          b'\xfe\xed\xfa\xce', b'\xfe\xed\xfa\xcf'):
            return True
        # Shebang
        if header[:2] == b'#!':
            return True
        # PE
        if header[:2] == b'MZ':
            return True
    except Exception:
        pass
    return os.access(str(path), os.X_OK) if hasattr(__import__('os'), 'access') else False


# ═══════════════════════════════════════════════════════════════
# Runners (one per framework)
# ═══════════════════════════════════════════════════════════════

def _run_cmd(cmd: str, cwd: Path, timeout: int = 300) -> Tuple[int, str, str, float]:
    """Run command and return (exit_code, stdout, stderr, duration_ms)."""
    t0 = time.time()
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=str(cwd)
        )
        dt = (time.time() - t0) * 1000
        return r.returncode, r.stdout, r.stderr, dt
    except subprocess.TimeoutExpired as e:
        dt = (time.time() - t0) * 1000
        return -1, e.stdout or "", e.stderr or f"TIMEOUT after {timeout}s", dt
    except Exception as e:
        dt = (time.time() - t0) * 1000
        return -99, "", str(e), dt


def run_make_test(project_root: Path, timeout: int = 300) -> TestRunResult:
    """Run 'make test' or 'make check'."""
    result = TestRunResult(framework=Framework.MAKE_TEST,
                           command="make test")
    exit_code, stdout, stderr, dt = _run_cmd("make test 2>&1", project_root, timeout)
    result.exit_code = exit_code
    result.stdout = stdout
    result.stderr = stderr
    result.total_duration_ms = dt

    # Try 'make check' if 'make test' not found
    if exit_code != 0 and "No rule to make target" in stderr:
        result.framework = Framework.MAKE_CHECK
        result.command = "make check"
        exit_code, stdout, stderr, dt = _run_cmd("make check 2>&1", project_root, timeout)
        result.exit_code = exit_code
        result.stdout = stdout
        result.stderr = stderr
        result.total_duration_ms = dt

    _parse_generic_output(result, stdout, stderr)
    return result


def run_ctest(project_root: Path, build_dir: Optional[str] = None, timeout: int = 300) -> TestRunResult:
    """Run ctest."""
    cwd = project_root / build_dir if build_dir else project_root
    result = TestRunResult(framework=Framework.CTEST,
                           command=f"ctest --test-dir {build_dir or '.'}")
    exit_code, stdout, stderr, dt = _run_cmd("ctest 2>&1", cwd, timeout)
    result.exit_code = exit_code
    result.stdout = stdout
    result.stderr = stderr
    result.total_duration_ms = dt

    _parse_ctest_output(result, stdout)
    return result


def run_cargo_test(project_root: Path, timeout: int = 600) -> TestRunResult:
    """Run cargo test."""
    result = TestRunResult(framework=Framework.CARGO_TEST,
                           command="cargo test")
    exit_code, stdout, stderr, dt = _run_cmd("cargo test 2>&1", project_root, timeout)
    result.exit_code = exit_code
    result.stdout = stdout
    result.stderr = stderr
    result.total_duration_ms = dt

    _parse_cargo_test_output(result, stdout)
    return result


def run_go_test(project_root: Path, timeout: int = 300) -> TestRunResult:
    """Run go test ./..."""
    result = TestRunResult(framework=Framework.GO_TEST,
                           command="go test ./...")
    exit_code, stdout, stderr, dt = _run_cmd("go test -v ./... 2>&1", project_root, timeout)
    result.exit_code = exit_code
    result.stdout = stdout
    result.stderr = stderr
    result.total_duration_ms = dt

    _parse_go_test_output(result, stdout)
    return result


def run_pytest(project_root: Path, timeout: int = 300) -> TestRunResult:
    """Run pytest."""
    result = TestRunResult(framework=Framework.PYTEST,
                           command="python -m pytest")
    exit_code, stdout, stderr, dt = _run_cmd(
        "python -m pytest -v 2>&1 || python3 -m pytest -v 2>&1",
        project_root, timeout
    )
    result.exit_code = exit_code
    result.stdout = stdout
    result.stderr = stderr
    result.total_duration_ms = dt

    _parse_pytest_output(result, stdout)
    return result


def run_custom_binary(project_root: Path, binary_path: str, timeout: int = 300) -> TestRunResult:
    """Run a standalone test binary (catch2, gtest, custom)."""
    full_path = project_root / binary_path
    result = TestRunResult(framework=Framework.CUSTOM_BINARY,
                           command=str(full_path))
    result.binary_path = str(full_path)
    if full_path.exists():
        result.binary_size_bytes = full_path.stat().st_size

    exit_code, stdout, stderr, dt = _run_cmd(str(full_path), project_root, timeout)
    result.exit_code = exit_code
    result.stdout = stdout
    result.stderr = stderr
    result.total_duration_ms = dt

    _parse_generic_output(result, stdout, stderr)
    return result


def run_custom_script(project_root: Path, script: str, timeout: int = 300) -> TestRunResult:
    """Run a custom test script."""
    result = TestRunResult(framework=Framework.CUSTOM_SCRIPT,
                           command=f"./{script}")
    exit_code, stdout, stderr, dt = _run_cmd(f"./{script}", project_root, timeout)
    result.exit_code = exit_code
    result.stdout = stdout
    result.stderr = stderr
    result.total_duration_ms = dt

    _parse_generic_output(result, stdout, stderr)
    return result


# ═══════════════════════════════════════════════════════════════
# Output Parsers
# ═══════════════════════════════════════════════════════════════

def _parse_generic_output(result: TestRunResult, stdout: str, stderr: str):
    """Extract pass/fail/crash counts from unstructured output."""
    combined = stdout + "\n" + stderr

    # Count PASS/FAIL patterns
    result.passed = len(re.findall(r'\bPASS\b', combined))
    result.failed = len(re.findall(r'\bFAIL\b', combined))

    # Detect crashes
    crash_patterns = [
        r'segmentation fault', r'SIGSEGV', r'SIGABRT', r'SIGILL', r'SIGFPE',
        r'AddressSanitizer', r'UndefinedBehaviorSanitizer', r'heap-buffer-overflow',
        r'stack-buffer-overflow', r'heap-use-after-free', r'double-free',
        r'memory leak', r'LeakSanitizer', r'ASAN:', r'UBSAN:',
        r'core dumped', r'Aborted', r'Bus error',
        r'Assertion.*failed', r'panic:', r'FATAL:',
    ]
    for pattern in crash_patterns:
        matches = re.findall(pattern, combined, re.IGNORECASE)
        if matches:
            result.crashed += len(matches)
            for m in matches[:5]:
                # Get surrounding context
                idx = combined.lower().find(m.lower())
                if idx >= 0:
                    ctx = combined[max(0, idx - 40):idx + len(m) + 80].strip()
                    result.crash_details.append(ctx[:200])

    # Fallback: count lines with "ok" / "not ok" (TAP format)
    if result.passed == 0 and result.failed == 0:
        ok_lines = re.findall(r'^ok\s', combined, re.MULTILINE)
        nok_lines = re.findall(r'^not ok\s', combined, re.MULTILINE)
        result.passed = len(ok_lines)
        result.failed = len(nok_lines)

    # Count test names from common patterns
    test_names = re.findall(r'(?:test|Test|TEST)\s*[\(\:]?\s*(\w+)', combined)
    if test_names and result.passed == 0 and result.failed == 0:
        # Individual test lines: "[PASS] test_name" or "test_name ... ok"
        pass_lines = re.findall(r'(?:\[PASS\]|\.\.\.\s*ok\b|PASSED\s*:)\s*(\S+)', combined)
        fail_lines = re.findall(r'(?:\[FAIL\]|\.\.\.\s*FAILED\b|FAILED\s*:)\s*(\S+)', combined)
        result.passed = len(pass_lines)
        result.failed = len(fail_lines)
        # Duration extraction
        times = re.findall(r'(\d+\.?\d*)\s*(?:ms|s)\b', combined)
        if times:
            result.slowest_duration_ms = max(float(t) for t in times)

    result.total = result.passed + result.failed + result.skipped
    result.exit_code = result.exit_code if result.total > 0 else (0 if result.crashed == 0 else -1)

    # Detect segfault/crash from exit code
    if result.exit_code in (-11, 139):  # SIGSEGV
        result.crashed = max(result.crashed, 1)
        result.crash_details.append("SIGSEGV (exit code 139)")
    elif result.exit_code in (-6, 134):  # SIGABRT
        result.crashed = max(result.crashed, 1)
        result.crash_details.append("SIGABRT (exit code 134)")


def _parse_ctest_output(result: TestRunResult, stdout: str):
    """Parse ctest output format."""
    # "100% tests passed, 0 tests failed out of 15"
    m = re.search(r'(\d+)%\s+tests passed.*?(\d+)\s+tests? failed.*?out of\s+(\d+)', stdout)
    if m:
        result.total = int(m.group(3))
        result.failed = int(m.group(2))
        result.passed = result.total - result.failed

    # Individual test lines: "1/15 Test #1: test_name ........   Passed    0.05 sec"
    for line in stdout.split('\n'):
        tm = re.match(r'\s*\d+/\d+\s+Test\s+#\d+:\s+(\S+).*?(Passed|Failed|Not Run)\s+([\d.]+)\s+sec', line)
        if tm:
            name, status, dur = tm.group(1), tm.group(2), float(tm.group(3))
            tc = TestCaseResult(
                name=name,
                passed=(status == "Passed"),
                skipped=(status == "Not Run"),
                duration_ms=dur * 1000,
            )
            result.test_cases.append(tc)
            if dur * 1000 > result.slowest_duration_ms:
                result.slowest_duration_ms = dur * 1000
                result.slowest_test = name


def _parse_cargo_test_output(result: TestRunResult, stdout: str):
    """Parse 'cargo test' output."""
    # "test result: ok. 12 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out"
    m = re.search(
        r'test result:\s*(\w+)\.\s*(\d+)\s+passed;\s*(\d+)\s+failed;\s*(\d+)\s+ignored',
        stdout
    )
    if m:
        result.passed = int(m.group(2))
        result.failed = int(m.group(3))
        result.skipped = int(m.group(4))
        result.total = result.passed + result.failed + result.skipped

    # Individual tests: "test module::test_name ... ok" / "... FAILED"
    for line in stdout.split('\n'):
        tm = re.match(r'test\s+(\S+)\s+\.\.\.\s+(\w+)', line)
        if tm:
            name, status = tm.group(1), tm.group(2)
            tc = TestCaseResult(
                name=name,
                passed=(status == "ok"),
                duration_ms=0.0,
            )
            result.test_cases.append(tc)

    # Duration
    dur_m = re.search(r'finished in\s+([\d.]+)s', stdout)
    if dur_m:
        result.total_duration_ms = float(dur_m.group(1)) * 1000


def _parse_go_test_output(result: TestRunResult, stdout: str):
    """Parse 'go test -v' output."""
    # "--- PASS: TestName (0.05s)" / "--- FAIL: TestName (0.05s)" / "--- SKIP: TestName"
    for line in stdout.split('\n'):
        tm = re.match(r'---\s+(PASS|FAIL|SKIP):\s+(\S+)\s*(?:\(([\d.]+)s\))?', line)
        if tm:
            status, name, dur = tm.group(1), tm.group(2), float(tm.group(3) or 0)
            tc = TestCaseResult(
                name=name,
                passed=(status == "PASS"),
                skipped=(status == "SKIP"),
                duration_ms=dur * 1000,
            )
            result.test_cases.append(tc)
            if dur * 1000 > result.slowest_duration_ms:
                result.slowest_duration_ms = dur * 1000
                result.slowest_test = name

    result.passed = sum(1 for t in result.test_cases if t.passed)
    result.failed = sum(1 for t in result.test_cases if not t.passed and not t.skipped)
    result.skipped = sum(1 for t in result.test_cases if t.skipped)
    result.total = len(result.test_cases)

    # Also "ok   package_name  0.123s" / "FAIL package_name"
    if result.total == 0:
        pkg_lines = re.findall(r'^(ok|FAIL)\s+\S+\s+([\d.]+)s', stdout, re.MULTILINE)
        for status, dur_str in pkg_lines:
            if status == 'ok':
                result.passed += 1
            else:
                result.failed += 1
            result.total = result.passed + result.failed


def _parse_pytest_output(result: TestRunResult, stdout: str):
    """Parse pytest output."""
    # "3 passed, 1 failed, 2 skipped in 0.45s"
    m = re.search(r'(\d+)\s+passed.*?(\d+)\s+failed.*?(\d+)\s+skipped', stdout)
    if not m:
        m = re.search(r'(\d+)\s+passed.*?(\d+)\s+failed', stdout)
    if m:
        result.passed = int(m.group(1))
        result.failed = int(m.group(2)) if m.lastindex >= 2 else 0
        if m.lastindex >= 3:
            result.skipped = int(m.group(3))
    else:
        # Summary line: "== 3 passed, 1 failed in 0.45s =="
        m = re.search(r'==\s*(\d+)\s+passed.*?(\d+)\s+failed', stdout)

    if not m:
        result.passed = len(re.findall(r'PASSED', stdout))
        result.failed = len(re.findall(r'FAILED', stdout))

    if m:
        result.passed = int(m.group(1))
        result.failed = int(m.group(2))

    result.total = result.passed + result.failed + result.skipped

    # Duration
    dur_m = re.search(r'in\s+([\d.]+)s', stdout)
    if dur_m:
        result.total_duration_ms = float(dur_m.group(1)) * 1000


# ═══════════════════════════════════════════════════════════════
# Main Executor
# ═══════════════════════════════════════════════════════════════

def execute_test_suite(project_root: Path, timeout: int = 600) -> TestRunResult:
    """
    Auto-detect test framework and run the test suite.
    Returns a structured TestRunResult ready for differential analysis.
    """
    framework, extra = detect_test_framework(project_root)

    runners = {
        Framework.MAKE_TEST: lambda: run_make_test(project_root, timeout),
        Framework.MAKE_CHECK: lambda: run_make_test(project_root, timeout),
        Framework.CTEST: lambda: run_ctest(project_root, extra, timeout),
        Framework.CMAKE_TEST: lambda: run_ctest(project_root, extra, timeout),
        Framework.CARGO_TEST: lambda: run_cargo_test(project_root, timeout),
        Framework.GO_TEST: lambda: run_go_test(project_root, timeout),
        Framework.PYTEST: lambda: run_pytest(project_root, timeout),
        Framework.MESON_TEST: lambda: _run_fallback(project_root, "meson test", Framework.MESON_TEST, timeout),
        Framework.BAZEL_TEST: lambda: _run_fallback(project_root, "bazel test //...", Framework.BAZEL_TEST, timeout),
        Framework.CUSTOM_BINARY: lambda: run_custom_binary(project_root, extra or "", timeout),
        Framework.CUSTOM_SCRIPT: lambda: run_custom_script(project_root, extra or "", timeout),
    }

    runner = runners.get(framework)
    if runner:
        return runner()

    # Unknown — fallback to generic make test / make check
    result = run_make_test(project_root, timeout)
    if result.total == 0 and result.crashed == 0:
        result.framework = Framework.UNKNOWN
    return result


def _run_fallback(project_root: Path, cmd: str, framework: Framework,
                  timeout: int) -> TestRunResult:
    """Generic fallback runner for systems without custom parser."""
    result = TestRunResult(framework=framework, command=cmd)
    exit_code, stdout, stderr, dt = _run_cmd(cmd, project_root, timeout)
    result.exit_code = exit_code
    result.stdout = stdout
    result.stderr = stderr
    result.total_duration_ms = dt
    _parse_generic_output(result, stdout, stderr)
    return result


# ═══════════════════════════════════════════════════════════════
# Validator Plugin (replaces / wraps the old TestValidator)
# ═══════════════════════════════════════════════════════════════

class TestSuiteExecutor(ValidationPlugin):
    """Validator that runs the project's real test suite via auto-detection."""

    name = "test_suite"
    level = ValidatorLevel.TESTS
    score_weight = 25
    description = "Multi-framework test suite executor"

    def __init__(self, timeout: int = 600):
        self.timeout = timeout
        self._last_run: Optional[TestRunResult] = None

    def is_available(self, project: Path) -> bool:
        framework, _ = detect_test_framework(project)
        return framework != Framework.UNKNOWN

    def run(self, project: Path, build_system: str = "make",
            timeout: int = 0) -> ValidatorResult:
        """
        Execute the test suite. Returns ValidatorResult for scoring.
        The TestRunResult is stored in self._last_run for differential analysis.
        """
        t = timeout or self.timeout
        self._last_run = execute_test_suite(project, t)

        passed = self._last_run.total > 0 and self._last_run.failed == 0 and self._last_run.crashed == 0
        findings = []

        if self._last_run.failed > 0:
            findings.append(f"{self._last_run.failed} tests FAILED")
        if self._last_run.crashed > 0:
            findings.append(f"{self._last_run.crashed} crashes detected")
        if self._last_run.crash_details:
            findings.extend(self._last_run.crash_details[:3])

        return self._result(
            passed=passed,
            output=self._last_run.summary,
            findings=findings,
            duration=self._last_run.total_duration_ms,
        )

    @property
    def last_result(self) -> Optional[TestRunResult]:
        """Get the structured result from the last run."""
        return self._last_run


# ─── compatibility: old TestValidator interface ───
# This allows existing code that imports TestValidator to keep working,
# but it now uses the new executor internally.
TestValidator = TestSuiteExecutor


# ═══════════════════════════════════════════════════════════════
# Demo / self-test
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    # Create a test project
    tmp = Path("/tmp/quimera_test_demo")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    (tmp / "main.c").write_text("""#include <stdio.h>
int add(int a, int b) { return a + b; }
int sub(int a, int b) { return a - b; }
int mul(int a, int b) { return a * b; }
""")

    (tmp / "test_main.c").write_text("""#include <stdio.h>
#include <assert.h>
int add(int a, int b);
int sub(int a, int b);
int mul(int a, int b);
int main() {
    assert(add(2,3) == 5);
    assert(sub(5,3) == 2);
    assert(mul(4,3) == 12);
    printf("All tests passed\\n");
    return 0;
}
""")

    (tmp / "Makefile").write_text("""CC=gcc
CFLAGS=-Wall -Werror
test: test_binary
\t./test_binary && echo PASS || echo FAIL
test_binary: main.c test_main.c
\t$(CC) $(CFLAGS) -o test_binary main.c test_main.c
clean:
\trm -f test_binary
""")

    print("=" * 60)
    print("Test Suite Executor — Demo")
    print("=" * 60)

    framework, extra = detect_test_framework(tmp)
    print(f"  Detected: {framework.value}" + (f" ({extra})" if extra else ""))

    result = execute_test_suite(tmp)
    print(f"  Result: {result.summary}")
    print(f"  Framework: {result.framework.value}")
    print(f"  Command: {result.command}")
    print(f"  Exit: {result.exit_code}")
    if result.crash_details:
        print(f"  Crashes: {result.crash_details}")

    shutil.rmtree(tmp, ignore_errors=True)
