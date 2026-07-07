import shutil
from .base import ValidationPlugin, ValidatorLevel

class UBSanValidator(ValidationPlugin):
    name = "ubsan"; level = ValidatorLevel.UBSAN; score_weight = 10
    description = "UndefinedBehaviorSanitizer: int overflow, null deref, misalignment"
    
    def is_available(self, p): return shutil.which("gcc") is not None
    
    def run(self, p, bs="make", timeout=120):
        src = p / "main.c"
        if not src.exists():
            cfs = list(p.rglob("*.c"))
            if not cfs: return self._result(False, "No .c files", available=False)
            src = cfs[0]
        prog = p / "prog_ubsan"
        ok, out, err, dt = self._run_cmd(
            f"gcc -fsanitize=undefined -g -O1 -o {prog} {src} 2>&1",
            p, timeout)
        if not ok:
            return self._result(False, err, ["UBSan compile failed"], dt)
        ok2, out2, err2, dt2 = self._run_cmd("./prog_ubsan 2>&1", p, min(timeout, 30))
        combined = out2 + err2
        findings = []
        for line in combined.splitlines():
            if "runtime error:" in line:
                findings.append(f"UBSan: {line.strip()[:150]}")
        if findings: ok2 = False
        (p / "prog_ubsan").unlink(missing_ok=True)
        return self._result(ok2, combined, findings, dt + dt2)
