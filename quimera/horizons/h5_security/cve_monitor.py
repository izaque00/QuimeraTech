"""
Quimera Mark X — CVE Monitor & Auto-Patch (Horizonte 5)

Monitora CVEs de kernel, gera patches automáticos e verifica supply chain.
  - Simulação de API NVD com CVEs de kernel realistas
  - Auto-patch com 6 templates por CWE
  - Supply chain: dependências vulneráveis, licenças, código de terceiros

De → Para:
  Antes: Vulnerabilidades detectadas manualmente
  Agora: CVE auto-patch + supply chain verification

Usage:
    monitor = CVEMonitor()
    relevant = monitor.scan_for_relevant_cves(target_file="fs/ext4/inode.c")
    for cve in relevant:
        patch = monitor.generate_patch(cve)
        print(f"CVE-{cve.cve_id}: auto-patch generated")
"""

import hashlib
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("quimera.h5.cve")


# ═══════════════════════════════════════════════════════════════════════════
# Data Structures
# ═══════════════════════════════════════════════════════════════════════════

class CVESeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class CVEEntry:
    cve_id: str
    description: str
    severity: CVESeverity
    cvss_score: float
    cwe_ids: List[str]
    affected_files: List[str]
    affected_versions: List[str]
    published_date: str
    patch_links: List[str]
    exploit_available: bool = False
    fixed_in: Optional[str] = None


@dataclass
class SupplyChainIssue:
    file_path: str
    issue_type: str  # dependency, license, third_party, version
    description: str
    severity: str
    recommendation: str


@dataclass
class SupplyChainReport:
    file_path: str
    vulnerable_deps: List[SupplyChainIssue]
    license_issues: List[SupplyChainIssue]
    third_party_detected: bool
    risk_score: float  # 0.0-1.0
    checked_at: str


# ═══════════════════════════════════════════════════════════════════════════
# Simulated CVE Database
# ═══════════════════════════════════════════════════════════════════════════

SEED_CVES = [
    CVEEntry(
        cve_id="CVE-2024-0001",
        description="Heap-based buffer overflow in Linux kernel ext4 filesystem when processing specially crafted inode structures",
        severity=CVESeverity.CRITICAL,
        cvss_score=9.8,
        cwe_ids=["CWE-122"],
        affected_files=["fs/ext4/inode.c", "fs/ext4/ext4.h"],
        affected_versions=["6.1.0-6.6.0"],
        published_date="2024-01-15",
        patch_links=["https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=abc123"],
        exploit_available=True,
    ),
    CVEEntry(
        cve_id="CVE-2024-0002",
        description="Use-after-free in Linux kernel network stack due to incorrect reference counting in TCP socket handling",
        severity=CVESeverity.HIGH,
        cvss_score=7.8,
        cwe_ids=["CWE-416"],
        affected_files=["net/ipv4/tcp.c", "net/core/sock.c"],
        affected_versions=["5.15.0-6.6.0"],
        published_date="2024-02-01",
        patch_links=["https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=def456"],
        exploit_available=True,
    ),
    CVEEntry(
        cve_id="CVE-2024-0003",
        description="NULL pointer dereference in Linux kernel USB subsystem when handling malformed USB descriptors",
        severity=CVESeverity.HIGH,
        cvss_score=7.5,
        cwe_ids=["CWE-476"],
        affected_files=["drivers/usb/core/hub.c", "drivers/usb/core/usb.h"],
        affected_versions=["6.1.0-6.5.0"],
        published_date="2024-02-15",
        patch_links=["https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=ghi789"],
        exploit_available=False,
    ),
    CVEEntry(
        cve_id="CVE-2024-0004",
        description="Race condition in Linux kernel scheduler leading to privilege escalation on multi-core systems",
        severity=CVESeverity.CRITICAL,
        cvss_score=9.1,
        cwe_ids=["CWE-362"],
        affected_files=["kernel/sched/core.c", "kernel/sched/fair.c"],
        affected_versions=["6.2.0-6.6.0"],
        published_date="2024-03-01",
        patch_links=["https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=jkl012"],
        exploit_available=True,
    ),
    CVEEntry(
        cve_id="CVE-2024-0005",
        description="Integer overflow in Linux kernel memory management causing potential arbitrary code execution",
        severity=CVESeverity.HIGH,
        cvss_score=8.2,
        cwe_ids=["CWE-190"],
        affected_files=["mm/mmap.c", "mm/memory.c"],
        affected_versions=["6.0.0-6.6.0"],
        published_date="2024-03-15",
        patch_links=["https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=mno345"],
        exploit_available=False,
    ),
    CVEEntry(
        cve_id="CVE-2024-0006",
        description="Stack-based buffer overflow in Linux kernel BPF verifier when processing complex eBPF programs",
        severity=CVESeverity.MEDIUM,
        cvss_score=6.5,
        cwe_ids=["CWE-120"],
        affected_files=["kernel/bpf/verifier.c"],
        affected_versions=["6.4.0-6.6.0"],
        published_date="2024-04-01",
        patch_links=["https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=pqr678"],
        exploit_available=False,
    ),
    CVEEntry(
        cve_id="CVE-2024-0007",
        description="Format string vulnerability in Linux kernel debugging interface exposing kernel memory",
        severity=CVESeverity.MEDIUM,
        cvss_score=5.9,
        cwe_ids=["CWE-134"],
        affected_files=["kernel/debug/kdb/kdb_io.c"],
        affected_versions=["5.15.0-6.6.0"],
        published_date="2024-04-15",
        patch_links=["https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=stu901"],
        exploit_available=False,
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# Auto-Patch Templates by CWE
# ═══════════════════════════════════════════════════════════════════════════

PATCH_TEMPLATES = {
    "CWE-120": """/* CVE Auto-Patch: CWE-120 — Buffer Overflow */
/* Replace unbounded copy with bounded version + null termination */

// BEFORE:
//   strcpy(dst, src);
//   sprintf(buf, "%s", user_input);

// AFTER (auto-generated):
strncpy(dst, src, sizeof(dst) - 1);
dst[sizeof(dst) - 1] = '\\0';

snprintf(buf, sizeof(buf), "%s", user_input);
""",
    "CWE-122": """/* CVE Auto-Patch: CWE-122 — Heap Buffer Overflow */
/* Add bounds checking before heap operations */

// BEFORE:
//   memcpy(heap_buf, input, user_controlled_size);

// AFTER (auto-generated):
if (user_controlled_size > MAX_ALLOC_SIZE) return -EINVAL;
if (user_controlled_size > allocated_size) return -EOVERFLOW;
memcpy(heap_buf, input, min(user_controlled_size, allocated_size));
""",
    "CWE-416": """/* CVE Auto-Patch: CWE-416 — Use-After-Free */
/* Nullify pointer after free + add refcounting */

// AFTER (auto-generated):
if (ptr != NULL) {
    kfree(ptr);
    ptr = NULL;  // Prevent use-after-free
}

// Consider using kref for reference-counted objects:
// kref_init(&obj->refcount);
// kref_get(&obj->refcount);  // Before use
// kref_put(&obj->refcount, release_fn);  // Instead of kfree
""",
    "CWE-476": """/* CVE Auto-Patch: CWE-476 — NULL Pointer Dereference */
/* Add NULL checks before all dereferences */

// BEFORE:
//   ptr->field = value;

// AFTER (auto-generated):
if (!ptr) {
    pr_err("NULL pointer in %s:%d\\n", __func__, __LINE__);
    return -EINVAL;
}
ptr->field = value;

// Use ERR_PTR pattern where appropriate:
if (IS_ERR_OR_NULL(ptr))
    return PTR_ERR(ptr);
""",
    "CWE-362": """/* CVE Auto-Patch: CWE-362 — Race Condition */
/* Add proper locking around shared data access */

// BEFORE:
//   shared_counter++;

// AFTER (auto-generated):
static DEFINE_SPINLOCK(shared_lock);

spin_lock(&shared_lock);
shared_counter++;
spin_unlock(&shared_lock);

// For read-heavy access, consider RCU:
// rcu_read_lock();
// val = rcu_dereference(shared_ptr);
// rcu_read_unlock();
""",
    "CWE-190": """/* CVE Auto-Patch: CWE-190 — Integer Overflow */
/* Use checked arithmetic */

// BEFORE:
//   size_t total = count * size;
//   buf = kmalloc(total, GFP_KERNEL);

// AFTER (auto-generated):
size_t total;
if (check_mul_overflow(count, size, &total)) {
    pr_err("Integer overflow in allocation\\n");
    return -EOVERFLOW;
}
buf = kmalloc(total, GFP_KERNEL);
if (!buf) return -ENOMEM;
""",
}

PATCH_TEMPLATES["CWE-134"] = PATCH_TEMPLATES.get("CWE-120", "")  # Format string uses similar mitigation


# ═══════════════════════════════════════════════════════════════════════════
# CVE Monitor
# ═══════════════════════════════════════════════════════════════════════════

class CVEMonitor:
    """Monitors NVD for relevant CVEs and generates auto-patches."""

    def __init__(self, feed_url: Optional[str] = None):
        self.feed_url = feed_url
        self._cve_cache: Dict[str, CVEEntry] = {}
        self._total_patches_generated = 0

        # Load seed CVEs
        for cve in SEED_CVES:
            self._cve_cache[cve.cve_id] = cve

        logger.info(f"CVEMonitor: {len(self._cve_cache)} CVEs loaded")

    # ── Scan ───────────────────────────────────────────────────────────

    def scan_for_relevant_cves(
        self,
        target_file: str = "",
        min_severity: CVESeverity = CVESeverity.MEDIUM,
    ) -> List[CVEEntry]:
        """Find CVEs relevant to a target file."""
        relevant = []

        for cve in self._cve_cache.values():
            # Severity filter
            severity_order = {CVESeverity.LOW: 0, CVESeverity.MEDIUM: 1, CVESeverity.HIGH: 2, CVESeverity.CRITICAL: 3}
            if severity_order.get(cve.severity, 0) < severity_order.get(min_severity, 0):
                continue

            # File matching
            if target_file:
                if not any(target_file in f for f in cve.affected_files):
                    continue

            relevant.append(cve)

        relevant.sort(key=lambda c: c.cvss_score, reverse=True)
        logger.info(
            f"CVEMonitor: {len(relevant)} relevant CVEs for '{target_file}' "
            f"(min_severity={min_severity.value})"
        )
        return relevant

    def get_critical_cves(self) -> List[CVEEntry]:
        """Get all CRITICAL severity CVEs."""
        return self.scan_for_relevant_cves(min_severity=CVESeverity.CRITICAL)

    def get_exploitable_cves(self) -> List[CVEEntry]:
        """Get CVEs with known exploits."""
        return [c for c in self._cve_cache.values() if c.exploit_available]

    # ── Auto-Patch ─────────────────────────────────────────────────────

    def generate_patch(self, cve: CVEEntry) -> str:
        """Generate an auto-patch for a CVE based on its CWE."""
        for cwe in cve.cwe_ids:
            template = PATCH_TEMPLATES.get(cwe)
            if template:
                self._total_patches_generated += 1
                logger.info(f"CVEMonitor: auto-patch generated for {cve.cve_id} ({cwe})")
                return template

        # Generic patch
        generic = f"""/* CVE Auto-Patch: {cve.cve_id}
 * Severity: {cve.severity.value} (CVSS {cve.cvss_score})
 * Description: {cve.description}
 * Affected: {', '.join(cve.affected_files[:3])}
 *
 * Generic mitigation: Apply defense in depth.
 * Review affected code paths and apply appropriate bounds checking,
 * input validation, and error handling.
 */
"""
        self._total_patches_generated += 1
        return generic

    def generate_patches_for_all_relevant(
        self, target_file: str = ""
    ) -> Dict[str, str]:
        """Generate auto-patches for all relevant CVEs."""
        relevant = self.scan_for_relevant_cves(target_file)
        patches = {}
        for cve in relevant:
            patches[cve.cve_id] = self.generate_patch(cve)
        return patches

    # ── Stats ──────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_cves_tracked": len(self._cve_cache),
            "total_patches_generated": self._total_patches_generated,
            "critical_count": len(self.get_critical_cves()),
            "exploitable_count": len(self.get_exploitable_cves()),
            "by_severity": {
                s.value: len([c for c in self._cve_cache.values() if c.severity == s])
                for s in CVESeverity
            },
        }


# ═══════════════════════════════════════════════════════════════════════════
# Supply Chain Checker
# ═══════════════════════════════════════════════════════════════════════════

class SupplyChainChecker:
    """Verifies patch supply chain security."""

    # Known vulnerable kernel versions
    VULNERABLE_VERSIONS = {
        "linux": ["5.10.0-5.10.50", "5.15.0-5.15.30", "6.0.0-6.0.10"],
    }

    # License compatibility matrix
    LICENSE_COMPAT = {
        "GPL-2.0": {"GPL-2.0", "MIT", "BSD-2-Clause", "BSD-3-Clause", "LGPL-2.1"},
        "MIT": {"MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "ISC"},
        "Apache-2.0": {"Apache-2.0", "MIT", "BSD-2-Clause", "BSD-3-Clause"},
    }

    def __init__(self):
        self._total_checks = 0
        self._issues_found = 0

    def check(self, file_path: str, code: str = "", dependencies: List[str] = None) -> SupplyChainReport:
        """Check a patch for supply chain issues."""
        self._total_checks += 1
        vulnerable_deps = []
        license_issues = []
        third_party = False

        # Check for third-party code patterns
        third_party_patterns = [
            "Copyright (c)", "All rights reserved", "Proprietary",
            "vendor/", "third_party/", "external/",
        ]
        for pattern in third_party_patterns:
            if pattern.lower() in code.lower():
                third_party = True
                break

        # Check dependencies for known vulnerabilities
        if dependencies:
            for dep in dependencies:
                if "linux-" in dep:
                    for vuln_range in self.VULNERABLE_VERSIONS.get("linux", []):
                        vulnerable_deps.append(SupplyChainIssue(
                            file_path=file_path,
                            issue_type="dependency",
                            description=f"Dependency {dep} may be in vulnerable range {vuln_range}",
                            severity="HIGH",
                            recommendation=f"Update {dep} to latest stable version",
                        ))

        # Check license compatibility
        # Kernel code should be GPL-2.0 compatible
        incompatible_patterns = ["PROPRIETARY", "NO LICENSE", "UNLICENSED"]
        for pattern in incompatible_patterns:
            if pattern.lower() in code.lower():
                license_issues.append(SupplyChainIssue(
                    file_path=file_path,
                    issue_type="license",
                    description=f"Code contains {pattern} license pattern",
                    severity="CRITICAL",
                    recommendation="Ensure code is GPL-2.0 compatible for kernel inclusion",
                ))

        if third_party:
            license_issues.append(SupplyChainIssue(
                file_path=file_path,
                issue_type="third_party",
                description="Third-party code detected — verify license compatibility",
                severity="MEDIUM",
                recommendation="Review license terms and ensure GPL-2.0 compatibility",
            ))

        # Compute risk score
        risk = 0.0
        risk += len(vulnerable_deps) * 0.3
        risk += len(license_issues) * 0.25
        risk += (0.15 if third_party else 0.0)
        risk = min(1.0, risk)

        report = SupplyChainReport(
            file_path=file_path,
            vulnerable_deps=vulnerable_deps,
            license_issues=license_issues,
            third_party_detected=third_party,
            risk_score=round(risk, 2),
            checked_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

        if vulnerable_deps or license_issues:
            self._issues_found += 1

        logger.info(
            f"SupplyChain: {file_path} — risk={risk:.2f}, "
            f"deps={len(vulnerable_deps)}, licenses={len(license_issues)}, "
            f"third_party={third_party}"
        )

        return report

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_checks": self._total_checks,
            "issues_found": self._issues_found,
            "issue_rate": f"{self._issues_found / max(self._total_checks, 1):.1%}",
        }
