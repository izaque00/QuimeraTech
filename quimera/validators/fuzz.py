from .base import ValidationPlugin, ValidatorLevel

class FuzzValidator(ValidationPlugin):
    name = "fuzzing"; level = ValidatorLevel.FUZZING; score_weight = 10
    description = "AFL++ / libFuzzer crash detection"
    
    def is_available(self, p):
        return False  # Requires project-specific setup
    
    def run(self, p, bs="make", timeout=120):
        return self._result(True, "Fuzzing not configured for this project",
                          [], 0, available=False)
