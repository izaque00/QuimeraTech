"""Build Integration Layer — validates patches against real project build."""
import subprocess, time, re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List
from enum import Enum

class BuildSystem(Enum):
    MAKEFILE="make"; CMAKE="cmake"; AUTOTOOLS="autotools"; MESON="meson"; CARGO="cargo"; GO="go"; CUSTOM="custom"

class ValidationLevel(Enum):
    NONE=0; SYNTAX=1; COMPILE=2; BUILD=3; UNIT_TESTS=4; INTEGRATION=5; BENCHMARK=6; FUZZING=7; FULL=8

@dataclass
class ValidationResult:
    level: ValidationLevel = ValidationLevel.NONE
    build_passed: bool = False; tests_passed: bool = False
    tests_total: int = 0; tests_failed: int = 0
    benchmark_before: float = 0.0; benchmark_after: float = 0.0; benchmark_delta_pct: float = 0.0
    regression: bool = False; fuzzing_crashes: int = -1
    output_log: str = ""; errors: List[str] = field(default_factory=list); duration_seconds: float = 0.0
    
    @property
    def passed(self): return self.build_passed and not self.regression and self.tests_failed==0
    
    def summary(self):
        if self.level == ValidationLevel.NONE: return "Not validated"
        lines = [f"Level: {self.level.value}/8 ({self.level.name})"]
        lines.append(f"Build: {'PASS' if self.build_passed else 'FAIL'}")
        if self.regression: lines.append("REGRESSION")
        return '\n'.join(lines)

class BuildIntegrator:
    def __init__(self, root, bs=None):
        self.root = Path(root); self.build_system = bs or self._detect(); self.baseline = None
    
    def _detect(self):
        r = self.root
        if (r/"Cargo.toml").exists(): return BuildSystem.CARGO
        if (r/"go.mod").exists(): return BuildSystem.GO
        if (r/"CMakeLists.txt").exists(): return BuildSystem.CMAKE
        if (r/"Makefile").exists(): return BuildSystem.MAKEFILE
        return BuildSystem.CUSTOM
    
    def _run(self, cmd, timeout=120, cwd=None):
        cwd = cwd or self.root; t0 = time.time()
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=str(cwd))
            return (r.returncode==0, r.stdout[:5000], r.stderr[:5000], time.time()-t0)
        except Exception as e:
            logger.warning(f"build_integration timeout/error after {timeout}s: {e}")
            return (False, "", "TIMEOUT", timeout)
    
    def build_project(self, clean=False):
        vr = ValidationResult()
        ok,o,e,dt = self._run("make -j$(nproc) 2>&1")
        vr.build_passed = ok; vr.duration_seconds = dt; vr.output_log = (o+e)[:3000]
        vr.level = ValidationLevel.BUILD if ok else ValidationLevel.COMPILE
        if not ok: vr.errors.append(f"Build: {e[:200]}")
        return vr
    
    def run_tests(self, vr):
        if not vr.build_passed: return vr
        ok,o,e,dt = self._run("make test 2>&1", 300)
        vr.tests_passed = ok; vr.duration_seconds += dt
        vr.level = ValidationLevel.UNIT_TESTS if ok else vr.level
        return vr
    
    def run_benchmark(self, vr, bench_cmd=None):
        if not vr.build_passed: return vr
        ok,o,e,dt = self._run("time make 2>&1 || true", 120)
        vr.benchmark_after = dt
        if self.baseline:
            vr.benchmark_before = self.baseline
            vr.benchmark_delta_pct = ((vr.benchmark_after-self.baseline)/self.baseline)*100
            if vr.benchmark_delta_pct > 10: vr.regression = True
        vr.level = ValidationLevel.BENCHMARK
        return vr
    
    def establish_baseline(self):
        ok,o,e,dt = self._run("time make 2>&1 || true", 60)
        self.baseline = dt
    
    def full_validation(self, bench_cmd=None, bl=True):
        if bl: self.establish_baseline()
        vr = self.build_project()
        if vr.build_passed: vr = self.run_tests(vr)
        if vr.build_passed: vr = self.run_benchmark(vr, bench_cmd)
        return vr
