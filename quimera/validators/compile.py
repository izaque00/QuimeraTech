import shutil
from .base import ValidationPlugin, ValidatorLevel

class CompileValidator(ValidationPlugin):
    name = "compile"; level = ValidatorLevel.COMPILE; score_weight = 10
    description = "gcc -Wall -Werror compilation"
    
    def is_available(self, p): return shutil.which("gcc") is not None
    
    def run(self, p, bs="make", timeout=120):
        src = p / "main.c"
        if not src.exists():
            cfs = list(p.rglob("*.c"))
            if not cfs: return self._result(False, "No .c files", available=False)
            src = cfs[0]
        ok, out, err, dt = self._run_cmd(
            f"gcc -Wall -Werror -c -o {p}/test.o {src}", p, timeout)
        return self._result(ok, err, [err[:200]] if not ok else [], dt)
