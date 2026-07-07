import shutil
from .base import ValidationPlugin, ValidatorLevel

class ASanValidator(ValidationPlugin):
    name = "asan"; level = ValidatorLevel.ASAN; score_weight = 15
    description = "AddressSanitizer: detects use-after-free, buffer overflow, leaks"
    
    def is_available(self, p): return shutil.which("gcc") is not None
    
    def run(self, p, bs="make", timeout=120):
        src = p / "main.c"
        if not src.exists():
            cfs = list(p.rglob("*.c"))
            if not cfs: return self._result(False, "No .c files", available=False)
            src = cfs[0]
        prog = p / "prog_asan"
        ok, out, err, dt = self._run_cmd(
            f"gcc -fsanitize=address -g -O1 -fno-omit-frame-pointer -o {prog} {src} 2>&1",
            p, timeout)
        if not ok:
            return self._result(False, err, ["ASan compile failed"], dt)
        ok2, out2, err2, dt2 = self._run_cmd("./prog_asan 2>&1", p, min(timeout, 30))
        combined = out2 + err2
        findings = []
        asan_errs = ["ERROR: AddressSanitizer", "heap-use-after-free",
                     "heap-buffer-overflow", "stack-buffer-overflow", "double-free"]
        for ae in asan_errs:
            if ae in combined:
                findings.append(f"ASan: {combined.split(chr(10))[0][:150]}")
                break
        if findings: ok2 = False
        (p / "prog_asan").unlink(missing_ok=True)
        return self._result(ok2, combined, findings, dt + dt2)
