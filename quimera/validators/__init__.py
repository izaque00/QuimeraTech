"""Validator plugins for Quimera — v2 with TestSuiteExecutor + DifferentialAnalyzer."""

from .base import ValidationPlugin, ValidatorResult, ValidatorLevel
from .compile import CompileValidator
from .build import BuildValidator
from .benchmark import BenchmarkValidator
from .asan import ASanValidator
from .ubsan import UBSanValidator
from .fuzz import FuzzValidator

# Test Suite Executor (multi-framework — replaces old simple TestValidator)
from .test_executor import (
    TestSuiteExecutor, TestRunResult, TestCaseResult,
    Framework, detect_test_framework, execute_test_suite,
)

# Backward-compat alias: old code importing TestValidator still works
TestValidator = TestSuiteExecutor

# Differential Analyzer (before/after comparison with regression detection)
from .differential_analyzer import (
    DifferentialAnalyzer, DifferentialReport,
    TestDelta, MetricDelta, CodeDelta,
    ArtifactDelta, DeltaDirection,
    update_patch_memory_from_report,
)

__all__ = [
    # Base
    "ValidationPlugin", "ValidatorResult", "ValidatorLevel",
    # Original validators (TestValidator now aliases TestSuiteExecutor)
    "CompileValidator", "BuildValidator", "TestValidator",
    "BenchmarkValidator", "ASanValidator", "UBSanValidator", "FuzzValidator",
    # Test Suite Executor (new — multi-framework)
    "TestSuiteExecutor", "TestRunResult", "TestCaseResult", "Framework",
    "detect_test_framework", "execute_test_suite",
    # Differential Analyzer (new — before/after comparison)
    "DifferentialAnalyzer", "DifferentialReport", "TestDelta",
    "MetricDelta", "CodeDelta", "ArtifactDelta", "DeltaDirection",
    "update_patch_memory_from_report",
]
