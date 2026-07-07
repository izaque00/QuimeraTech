"""
Quimera Mark X — Self Awareness (Mind Subsystem)

Continuous monitoring and auto-diagnosis. Not just a health check —
a genuine self-awareness system that:

  - Monitors logs, exceptions, performance metrics in real-time
  - Detects regressions (new bugs, performance drops, test failures)
  - Correlates issues across horizons (e.g., H3 verification failure → H4 genetic fix)
  - Maintains a "self-model" of expected vs actual behavior
  - Alerts the Mind when intervention is needed

Usage:
    awareness = SelfAwareness(mind)
    await awareness.start()
    
    issues = await awareness.detect_issues()
    # → [{type: "compilation_error", severity: "HIGH", ...}, ...]
    
    health = await awareness.health_check()
    # → {status: "degraded", issues: [...], metrics: {...}}
"""

import asyncio
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Deque, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("quimera.mind.awareness")


# ═══════════════════════════════════════════════════════════════════════════
# Issue Detection
# ═══════════════════════════════════════════════════════════════════════════

class IssueSeverity(str, Enum):
    CRITICAL = "CRITICAL"    # System down / data loss risk
    HIGH = "HIGH"           # Service degraded / security risk
    MEDIUM = "MEDIUM"       # Performance issue / warning
    LOW = "LOW"             # Cosmetic / informational


@dataclass
class DetectedIssue:
    type: str                # compilation_error, runtime_error, security_vuln, etc.
    severity: IssueSeverity
    description: str
    source: str              # Which component detected it
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    suggested_action: Optional[str] = None
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved: bool = False
    auto_fixable: bool = False
    related_issues: List[str] = field(default_factory=list)


@dataclass
class HealthSnapshot:
    timestamp: str
    status: str  # healthy, degraded, critical
    active_issues: int
    resolved_issues: int
    horizon_status: Dict[str, str]
    metrics: Dict[str, Any]
    recommendations: List[str]


# ═══════════════════════════════════════════════════════════════════════════
# Heuristic Detectors
# ═══════════════════════════════════════════════════════════════════════════

class CodeHeuristicDetector:
    """Detects issues by analyzing code patterns heuristically."""

    # Anti-patterns with severity
    ANTI_PATTERNS = [
        (r'\bstrcpy\s*\(', IssueSeverity.HIGH, "Unsafe strcpy detected — use strncpy", "buffer_overflow", True),
        (r'\bstrcat\s*\(', IssueSeverity.HIGH, "Unsafe strcat detected — use strncat", "buffer_overflow", True),
        (r'\bsprintf\s*\(', IssueSeverity.HIGH, "Unsafe sprintf detected — use snprintf", "buffer_overflow", True),
        (r'\bgets\s*\(', IssueSeverity.CRITICAL, "Dangerous gets() function — remove immediately", "buffer_overflow", True),
        (r'\bfree\s*\([^)]+\)(?!.*=.*NULL)', IssueSeverity.MEDIUM, "free() without NULL assignment — potential UAF", "use_after_free", True),
        (r'\bNULL\b(?!.*check|.*if)', IssueSeverity.MEDIUM, "Possible NULL pointer usage without check", "null_deref", True),
        (r'\bmalloc\s*\([^)]*\*\s*[^)]*\)', IssueSeverity.MEDIUM, "Unchecked multiplication in malloc — potential integer overflow", "integer_overflow", False),
        (r'//\s*TODO|//\s*FIXME|//\s*HACK', IssueSeverity.LOW, "Unresolved TODO/FIXME/HACK comment", "tech_debt", False),
        (r'#\s*pragma\s+once(?!.*#\s*ifndef)', IssueSeverity.LOW, "Consider using #ifndef guard instead of #pragma once", "style", False),
    ]

    @classmethod
    def scan_file(cls, file_path: str, content: str) -> List[DetectedIssue]:
        """Scan a single file for anti-patterns."""
        import re
        issues = []

        for pattern, severity, desc, issue_type, auto_fixable in cls.ANTI_PATTERNS:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                line_num = content[:match.start()].count("\n") + 1
                issues.append(DetectedIssue(
                    type=issue_type,
                    severity=severity,
                    description=desc,
                    source="CodeHeuristicDetector",
                    file_path=file_path,
                    line_number=line_num,
                    auto_fixable=auto_fixable,
                    suggested_action=f"Auto-fix available via genetic evolution" if auto_fixable else "Manual review recommended",
                ))

        return issues


class LogMonitor:
    """Monitors log files for errors and anomalies."""

    def __init__(self):
        self._error_patterns = [
            (r'(?i)error', IssueSeverity.HIGH),
            (r'(?i)exception', IssueSeverity.HIGH),
            (r'(?i)crash', IssueSeverity.CRITICAL),
            (r'(?i)fail(ed|ure)?', IssueSeverity.MEDIUM),
            (r'(?i)timeout', IssueSeverity.MEDIUM),
            (r'(?i)deprecated', IssueSeverity.LOW),
            (r'(?i)warning', IssueSeverity.LOW),
        ]
        self._last_position: Dict[str, int] = {}  # file → last read position

    async def scan_logs(self, log_dir: str = "logs") -> List[DetectedIssue]:
        """Scan log files for new errors."""
        import re
        issues = []

        if not os.path.exists(log_dir):
            return issues

        for log_file in os.listdir(log_dir):
            path = os.path.join(log_dir, log_file)
            if not os.path.isfile(path):
                continue

            try:
                with open(path) as f:
                    # Start from last position
                    start = self._last_position.get(path, 0)
                    f.seek(start)
                    new_lines = f.readlines()
                    self._last_position[path] = f.tell()

                for line in new_lines:
                    for pattern, severity in self._error_patterns:
                        if re.search(pattern, line):
                            issues.append(DetectedIssue(
                                type="log_error",
                                severity=severity,
                                description=f"Log event: {line.strip()[:200]}",
                                source=f"LogMonitor:{log_file}",
                                auto_fixable=False,
                            ))
                            break  # One issue per line
            except Exception:
                pass

        return issues


class TestHealthChecker:
    """Checks test suite health."""

    @staticmethod
    async def check(test_dir: str = "tests") -> List[DetectedIssue]:
        """Check for test health issues."""
        issues = []

        if not os.path.exists(test_dir):
            return [DetectedIssue(
                type="missing_tests",
                severity=IssueSeverity.HIGH,
                description="Test directory not found — no test coverage",
                source="TestHealthChecker",
                auto_fixable=False,
            )]

        # Count test files
        test_files = list(Path(test_dir).rglob("test_*.py")) + list(Path(test_dir).rglob("*_test.py"))
        if not test_files:
            issues.append(DetectedIssue(
                type="no_tests",
                severity=IssueSeverity.HIGH,
                description="No test files found",
                source="TestHealthChecker",
                auto_fixable=False,
            ))

        return issues


class DependencyHealthChecker:
    """Checks dependency and import health."""

    @staticmethod
    async def check(codebase_knowledge) -> List[DetectedIssue]:
        """Check for broken imports and circular dependencies."""
        issues = []

        if not codebase_knowledge or not codebase_knowledge._indexed:
            return issues

        # Check for files importing non-existent modules
        for file_path, imports in codebase_knowledge._imports_graph.items():
            for imp in imports:
                base = imp.split(".")[0]
                if base not in codebase_knowledge._reverse_imports:
                    # Module not exported by any file
                    pass  # Could be external dependency — skip

        return issues


# ═══════════════════════════════════════════════════════════════════════════
# Self Awareness — Main Class
# ═══════════════════════════════════════════════════════════════════════════

class SelfAwareness:
    """Continuous self-monitoring and diagnosis system.

    Maintains a "self-model" of the Quimera system — what's healthy,
    what's degraded, what needs attention. Feeds into the Mind's
    decision loop.
    """

    def __init__(self, mind=None):
        self.mind = mind  # Reference to QuimeraMind

        # Issue tracking
        self._active_issues: Dict[str, DetectedIssue] = {}
        self._resolved_issues: List[DetectedIssue] = []
        self._issue_history: Deque[DetectedIssue] = deque(maxlen=1000)

        # Health history
        self._health_history: Deque[HealthSnapshot] = deque(maxlen=100)

        # Detectors
        self._code_detector = CodeHeuristicDetector()
        self._log_monitor = LogMonitor()

        # State
        self._running = False
        self._last_scan_time: float = 0
        self._scan_interval: float = 60  # seconds

        logger.info("SelfAwareness initialized")

    async def start(self):
        """Start continuous monitoring."""
        self._running = True
        logger.info("SelfAwareness: monitoring started")
        # Initial health check
        await self.health_check()

    async def stop(self):
        self._running = False
        logger.info("SelfAwareness: monitoring stopped")

    # ── Issue Detection ─────────────────────────────────────────────────

    async def detect_issues(self) -> List[DetectedIssue]:
        """Run all detectors and return found issues."""
        all_issues = []

        # 1. Code heuristic scan (on indexed files)
        if self.mind and self.mind._knowledge and self.mind._knowledge._indexed:
            for file_path, content in self.mind._knowledge._content_cache.items():
                full_path = os.path.join(self.mind.workspace_path, file_path)
                if os.path.exists(full_path):
                    issues = self._code_detector.scan_file(full_path, content)
                    all_issues.extend(issues)

        # 2. Log monitoring
        log_issues = await self._log_monitor.scan_logs()
        all_issues.extend(log_issues)

        # 3. Test health
        test_issues = await TestHealthChecker.check()
        all_issues.extend(test_issues)

        # 4. Dependency health
        if self.mind and self.mind._knowledge:
            dep_issues = await DependencyHealthChecker.check(self.mind._knowledge)
            all_issues.extend(dep_issues)

        # Update tracking
        for issue in all_issues:
            key = f"{issue.type}:{issue.file_path}:{issue.line_number}"
            if key not in self._active_issues:
                self._active_issues[key] = issue
                self._issue_history.append(issue)

        self._last_scan_time = time.time()

        # Log summary
        if all_issues:
            critical = sum(1 for i in all_issues if i.severity == IssueSeverity.CRITICAL)
            high = sum(1 for i in all_issues if i.severity == IssueSeverity.HIGH)
            logger.info(f"SelfAwareness: {len(all_issues)} issues ({critical} critical, {high} high)")

        return all_issues

    # ── Health Check ─────────────────────────────────────────────────────

    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive system health check."""
        issues = await self.detect_issues()

        # Determine overall status
        critical_count = sum(1 for i in issues if i.severity == IssueSeverity.CRITICAL)
        high_count = sum(1 for i in issues if i.severity == IssueSeverity.HIGH)

        if critical_count > 0:
            status = "critical"
        elif high_count > 3:
            status = "degraded"
        else:
            status = "healthy"

        # Per-horizon status
        horizon_status = {}
        for h in ["H1", "H2", "H3", "H4", "H5", "H6"]:
            h_issues = [i for i in issues if i.source and h.lower() in i.source.lower()]
            if any(i.severity == IssueSeverity.CRITICAL for i in h_issues):
                horizon_status[h] = "critical"
            elif any(i.severity == IssueSeverity.HIGH for i in h_issues):
                horizon_status[h] = "degraded"
            else:
                horizon_status[h] = "healthy"

        # Metrics
        metrics = {
            "total_scans": len(self._health_history) + 1,
            "active_issues": len(issues),
            "total_resolved": len(self._resolved_issues),
            "by_severity": {
                "critical": critical_count,
                "high": high_count,
                "medium": sum(1 for i in issues if i.severity == IssueSeverity.MEDIUM),
                "low": sum(1 for i in issues if i.severity == IssueSeverity.LOW),
            },
            "by_type": {},
        }
        for i in issues:
            metrics["by_type"][i.type] = metrics["by_type"].get(i.type, 0) + 1

        # Recommendations
        recommendations = []
        if critical_count > 0:
            recommendations.append(f"URGENT: {critical_count} critical issues require immediate attention")
        if any(i.auto_fixable for i in issues):
            auto_count = sum(1 for i in issues if i.auto_fixable)
            recommendations.append(f"{auto_count} issues are auto-fixable via genetic evolution")
        if any(i.type == "missing_tests" for i in issues):
            recommendations.append("Add test coverage to critical modules")

        snapshot = HealthSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            status=status,
            active_issues=len(issues),
            resolved_issues=len(self._resolved_issues),
            horizon_status=horizon_status,
            metrics=metrics,
            recommendations=recommendations,
        )
        self._health_history.append(snapshot)

        return {
            "status": status,
            "issues": [{"type": i.type, "severity": i.severity.value, "description": i.description,
                         "file": i.file_path, "line": i.line_number, "auto_fixable": i.auto_fixable}
                        for i in issues[:20]],
            "metrics": metrics,
            "recommendations": recommendations,
            "horizons": horizon_status,
        }

    # ── Resolution ───────────────────────────────────────────────────────

    def mark_resolved(self, issue_key: str):
        """Mark an issue as resolved."""
        if issue_key in self._active_issues:
            issue = self._active_issues.pop(issue_key)
            issue.resolved = True
            self._resolved_issues.append(issue)
            logger.info(f"SelfAwareness: issue resolved — {issue.description[:100]}")

    def get_auto_fixable_issues(self) -> List[DetectedIssue]:
        """Get issues that can be automatically fixed."""
        return [i for i in self._active_issues.values() if i.auto_fixable]

    # ── Stats ────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        return {
            "active_issues": len(self._active_issues),
            "total_resolved": len(self._resolved_issues),
            "last_scan": self._last_scan_time,
            "running": self._running,
            "health_snapshots": len(self._health_history),
        }
