"""Base classes for validator plugins."""
import time, subprocess
from pathlib import Path
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum

class ValidatorLevel(Enum):
    SYNTAX = 1; COMPILE = 2; BUILD = 3; TESTS = 4; BENCHMARK = 5
    ASAN = 6; UBSAN = 7; TSAN = 8; MSAN = 9; FUZZING = 10

@dataclass
class ValidatorResult:
    name: str; level: ValidatorLevel; passed: bool
    available: bool = True; score: int = 0
    output: str = ""; findings: list = field(default_factory=list); duration: float = 0.0
    def summary(self):
        s = "PASS" if self.passed else ("FAIL" if self.available else "SKIP")
        return f"[{s:4s}] {self.name:12s} +{self.score:2d} {self.level.name}"

class ValidationPlugin(ABC):
    name = "base"; level = ValidatorLevel.SYNTAX; score_weight = 5; description = ""
    @abstractmethod
    def is_available(self, project: Path) -> bool: ...
    @abstractmethod
    def run(self, project: Path, build_system: str = "make", timeout: int = 120) -> ValidatorResult: ...
    def _run_cmd(self, cmd, cwd, timeout=120):
        t0 = time.time()
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=str(cwd))
            return (r.returncode==0, r.stdout[:8000], r.stderr[:8000], time.time()-t0)
        except Exception as e:
            import logging as _log; _log.getLogger(__name__).warning(f"validator timeout/error after {timeout}s: {e}")
            return (False, "", "TIMEOUT", timeout)
    def _result(self, passed, output="", findings=None, duration=0.0, available=True):
        return ValidatorResult(name=self.name, level=self.level, passed=passed, available=available,
            score=self.score_weight if passed and available else 0, output=output[:3000],
            findings=findings or [], duration=duration)
