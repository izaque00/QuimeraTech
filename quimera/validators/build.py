from .base import ValidationPlugin, ValidatorLevel

class BuildValidator(ValidationPlugin):
    name = "build"; level = ValidatorLevel.BUILD; score_weight = 20
    description = "Full project build (make/cmake/cargo)"
    
    def is_available(self, p):
        return (p / "Makefile").exists() or (p / "CMakeLists.txt").exists() or (p / "Cargo.toml").exists()
    
    def run(self, p, bs="make", timeout=120):
        ok, out, err, dt = self._run_cmd("make -j$(nproc) 2>&1", p, timeout)
        return self._result(ok, out + err, [err[:200]] if not ok else [], dt)
