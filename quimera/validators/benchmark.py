import re
from .base import ValidationPlugin, ValidatorLevel

class BenchmarkValidator(ValidationPlugin):
    name = "benchmark"; level = ValidatorLevel.BENCHMARK; score_weight = 10
    description = "Before/after performance comparison (>10% slower = FAIL)"
    
    def __init__(self, baseline=None):
        self.baseline = baseline
    
    def is_available(self, p): return True
    
    def run(self, p, bs="make", timeout=60):
        ok, out, err, dt = self._run_cmd("time make 2>&1 || true", p, timeout)
        m = re.search(r'([\d.]+)\s*(?:s|sec)', out + err)
        current = float(m.group(1)) if m else dt
        if self.baseline and self.baseline > 0:
            delta = ((current - self.baseline) / self.baseline) * 100
            if delta > 10:
                return self._result(False, out + err, [f"REGRESSION: +{delta:.1f}%"], dt)
        return self._result(True, out + err, [], dt)
