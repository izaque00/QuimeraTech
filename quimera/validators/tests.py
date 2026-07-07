from .base import ValidationPlugin, ValidatorLevel

class TestValidator(ValidationPlugin):
    name = "tests"; level = ValidatorLevel.TESTS; score_weight = 25
    description = "Project test suite"
    
    def is_available(self, p):
        mf = p / "Makefile"
        return mf.exists() and "test" in mf.read_text().lower()
    
    def run(self, p, bs="make", timeout=300):
        ok, out, err, dt = self._run_cmd("make test 2>&1", p, timeout)
        if not ok:
            ok2, out2, err2, dt2 = self._run_cmd("make check 2>&1", p, timeout)
            if ok2: ok, out, err, dt = True, out2, err2, dt2
        return self._result(ok, out + err, [err[:200]] if not ok else [], dt)
