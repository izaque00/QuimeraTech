"""Security Orchestrator — Orquestrador de Seguranca Ofensiva e Defensiva.

Integra os 3 motores do Horizonte 5 em um pipeline unificado:
1. RedTeam — Gera exploits para testar patches ofensivamente
2. FuzzingEngine — Fuzzing com feedback de cobertura
3. CVEMonitor — Monitora CVEs e gera patches automaticos

Pipeline de seguranca completa:
    Patch → [Red Team Attack] → [Fuzzing] → [CVE Monitor]
                ↓                    ↓              ↓
          Exploits gerados     Crashes encontrados   CVEs relevantes
                ↓                    ↓              ↓
          [Security Verdict] ← ← ← ← ← ← ← ← ← ← ←
                ↓
        APPROVED / NEEDS_FIX / REJECTED

Uso:
    from quimera.core.security_orchestrator import SecurityOrchestrator
    
    sec = SecurityOrchestrator()
    verdict = sec.evaluate_security(patch_code, original_code)
    
    if verdict.approved:
        print(f"✅ Patch seguro: {verdict.summary()}")
    else:
        print(f"❌ {len(verdict.findings)} vulnerabilidades encontradas")
"""

import logging
import time
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)

try:
    from quimera.integration_backends.red_team import RedTeam, RedTeamFinding
    RED_TEAM_AVAILABLE = True
except ImportError:
    RED_TEAM_AVAILABLE = False

try:
    from quimera.integration_backends.fuzzing_engine import FuzzingEngine, FuzzResult
    FUZZING_AVAILABLE = True
except ImportError:
    FUZZING_AVAILABLE = False

try:
    from quimera.seguranca.cve_monitor import CVEMonitor, CVEInfo, SupplyChainCheck
    CVE_MONITOR_AVAILABLE = True
except ImportError:
    CVE_MONITOR_AVAILABLE = False


# ============================================================================
# Data Classes
# ============================================================================

class SecurityVerdict(Enum):
    APPROVED = "approved"
    APPROVED_WITH_WARNINGS = "approved_with_warnings"
    NEEDS_FIX = "needs_fix"
    REJECTED = "rejected"


@dataclass
class SecurityEvaluation:
    """Resultado da avaliacao de seguranca completa."""
    verdict: SecurityVerdict
    security_score: float  # 0-1, higher = better
    red_team_findings: List[Dict[str, Any]] = field(default_factory=list)
    fuzzing_results: Optional[Dict[str, Any]] = None
    cve_findings: Optional[Dict[str, Any]] = None
    supply_chain_issues: List[Dict[str, Any]] = field(default_factory=list)
    total_critical: int = 0
    total_high: int = 0
    total_medium: int = 0
    recommendations: List[str] = field(default_factory=list)
    evaluation_time_ms: float = 0.0

    @property
    def approved(self) -> bool:
        return self.verdict in (
            SecurityVerdict.APPROVED,
            SecurityVerdict.APPROVED_WITH_WARNINGS,
        )

    def summary(self) -> str:
        return (
            f"Security: {self.verdict.value} (score={self.security_score:.2f}) — "
            f"{self.total_critical} critical, {self.total_high} high, "
            f"{self.total_medium} medium"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "security_score": self.security_score,
            "findings": {
                "critical": self.total_critical,
                "high": self.total_high,
                "medium": self.total_medium,
            },
            "red_team": len(self.red_team_findings),
            "fuzzing_crashes": (
                len(self.fuzzing_results.get("crashes", []))
                if self.fuzzing_results else 0
            ),
            "supply_chain_issues": len(self.supply_chain_issues),
            "recommendations": self.recommendations[:5],
        }


# ============================================================================
# SecurityOrchestrator
# ============================================================================

class SecurityOrchestrator:
    """Orquestrador de seguranca ofensiva/defensiva.

    Pipeline completo:
    1. Red Team ataca o patch
    2. Fuzzing busca crashes
    3. CVE Monitor verifica vulnerabilities conhecidas
    4. Supply chain check
    5. Veredito integrado

    Attributes:
        enable_red_team: Ativar Red Team.
        enable_fuzzing: Ativar Fuzzing.
        enable_cve_monitor: Ativar CVE Monitor.
        aggressiveness: 0-1, agressividade do Red Team.
        fuzz_iterations: Iteracoes de fuzzing.
        fuzz_timeout: Timeout do fuzzing em segundos.
        fail_on_critical: Se True, rejeita patch com findings criticos.
    """

    def __init__(
        self,
        enable_red_team: bool = True,
        enable_fuzzing: bool = True,
        enable_cve_monitor: bool = True,
        aggressiveness: float = 0.8,
        fuzz_iterations: int = 5000,
        fuzz_timeout: int = 20,
        fail_on_critical: bool = True,
    ):
        self.enable_red_team = enable_red_team
        self.enable_fuzzing = enable_fuzzing
        self.enable_cve_monitor = enable_cve_monitor
        self.fail_on_critical = fail_on_critical

        # Inicializar motores
        self._red_team = self._init_red_team(aggressiveness)
        self._fuzzer = self._init_fuzzer(fuzz_iterations, fuzz_timeout)
        self._cve_monitor = self._init_cve_monitor()

        available = sum([
            self._red_team is not None,
            self._fuzzer is not None,
            self._cve_monitor is not None,
        ])
        montar_log(
            f"SecurityOrchestrator: {available}/3 motores disponiveis "
            f"(RedTeam={'OK' if self._red_team else 'NO'}, "
            f"Fuzzing={'OK' if self._fuzzer else 'NO'}, "
            f"CVEMonitor={'OK' if self._cve_monitor else 'NO'})",
            "INFO" if available >= 2 else "WARNING"
        )

    def _init_red_team(self, aggressiveness: float):
        if not RED_TEAM_AVAILABLE:
            return None
        try:
            return RedTeam(aggressiveness=aggressiveness)
        except Exception as e:
            logger.warning(f"RedTeam init failed: {e}")
            return None

    def _init_fuzzer(self, iterations: int, timeout: int):
        if not FUZZING_AVAILABLE:
            return None
        try:
            return FuzzingEngine(
                max_iterations=iterations,
                timeout_seconds=timeout,
            )
        except Exception as e:
            logger.warning(f"FuzzingEngine init failed: {e}")
            return None

    def _init_cve_monitor(self):
        if not CVE_MONITOR_AVAILABLE:
            return None
        try:
            return CVEMonitor(auto_patch_enabled=True)
        except Exception as e:
            logger.warning(f"CVEMonitor init failed: {e}")
            return None

    # ------------------------------------------------------------------
    # API Principal
    # ------------------------------------------------------------------

    def evaluate_security(
        self,
        patch_code: str,
        original_code: str = "",
        affected_files: Optional[List[str]] = None,
        kernel_version: Optional[str] = None,
    ) -> SecurityEvaluation:
        """Avalia seguranca completa de um patch.

        Args:
            patch_code: Codigo do patch.
            original_code: Codigo original (para diff).
            affected_files: Arquivos afetados pelo patch.
            kernel_version: Versao do kernel para CVE check.

        Returns:
            SecurityEvaluation com veredito e findings.
        """
        start = time.time()
        evaluation = SecurityEvaluation(
            verdict=SecurityVerdict.APPROVED,
            security_score=1.0,
        )

        # ── 1. Red Team Attack ──
        if self._red_team and self.enable_red_team:
            montar_log("SecurityOrchestrator: Red Team atacando...", "INFO")
            try:
                rt_findings = self._red_team.attack(patch_code, original_code)
                evaluation.red_team_findings = [
                    f.to_dict() for f in rt_findings if f.exploitable
                ]
                for f in rt_findings:
                    if f.exploitable:
                        if f.severity == "CRITICAL":
                            evaluation.total_critical += 1
                        elif f.severity == "HIGH":
                            evaluation.total_high += 1
                        elif f.severity == "MEDIUM":
                            evaluation.total_medium += 1
            except Exception as e:
                logger.error(f"Red Team error: {e}")

        # ── 2. Fuzzing ──
        if self._fuzzer and self.enable_fuzzing:
            montar_log("SecurityOrchestrator: Fuzzing...", "INFO")
            try:
                fuzz_result = self._fuzzer.fuzz(
                    target_code=patch_code,
                    input_seeds=[
                        b"", b"A" * 100, b"\x00" * 10,
                        b"%s%s%s%s", b"../../../etc/passwd",
                    ],
                )
                evaluation.fuzzing_results = {
                    "unique_crashes": len(fuzz_result.unique_crashes),
                    "total_crashes": fuzz_result.total_crashes,
                    "coverage_pct": fuzz_result.coverage_pct,
                    "iterations": fuzz_result.total_iterations,
                    "crashes": [
                        c.to_dict() for c in fuzz_result.unique_crashes
                    ],
                }
                for crash in fuzz_result.unique_crashes:
                    if crash.severity == "CRITICAL":
                        evaluation.total_critical += 1
                    elif crash.severity == "HIGH":
                        evaluation.total_high += 1
            except Exception as e:
                logger.error(f"Fuzzing error: {e}")

        # ── 3. CVE Monitor ──
        if self._cve_monitor and self.enable_cve_monitor:
            montar_log("SecurityOrchestrator: Verificando CVEs...", "INFO")
            try:
                cves = self._cve_monitor.check_for_product(
                    product="linux_kernel",
                    version=kernel_version or "6.x",
                    days_back=90,
                    min_severity="HIGH",
                )
                evaluation.cve_findings = {
                    "total_cves": len(cves),
                    "cves": [c.to_dict() for c in cves[:10]],
                }
            except Exception as e:
                logger.error(f"CVE Monitor error: {e}")

        # ── 4. Supply Chain ──
        if self._cve_monitor:
            montar_log("SecurityOrchestrator: Verificando supply chain...", "INFO")
            try:
                sc_checks = self._cve_monitor.check_supply_chain(
                    patch_code, affected_files
                )
                evaluation.supply_chain_issues = [
                    {"file": c.file_path, "risk_score": c.risk_score,
                     "vulnerable_deps": c.vulnerable_deps,
                     "license_issues": c.license_issues}
                    for c in sc_checks if c.has_vulnerable_deps or c.license_issues
                ]
            except Exception as e:
                logger.error(f"Supply chain check error: {e}")

        # ── 5. Veredito ──
        evaluation = self._compute_verdict(evaluation)
        evaluation.evaluation_time_ms = (time.time() - start) * 1000

        montar_log(
            f"SecurityOrchestrator: {evaluation.summary()} "
            f"({evaluation.evaluation_time_ms:.0f}ms)",
            "INFO" if evaluation.approved else "WARNING"
        )

        return evaluation

    def quick_security_check(self, patch_code: str) -> Tuple[bool, str]:
        """Verificacao rapida de seguranca para CI/CD."""
        if self._red_team:
            is_safe, reason = self._red_team.quick_attack(patch_code)
            if not is_safe:
                return False, f"Red Team: {reason}"

        # Fuzz rapido
        if self._fuzzer:
            is_safe, reason = self._fuzzer.quick_fuzz(patch_code, b"")
            if not is_safe:
                return False, f"Fuzzing: {reason}"

        return True, "Quick security check passed"

    # ------------------------------------------------------------------
    # Veredito
    # ------------------------------------------------------------------

    def _compute_verdict(self, evaluation: SecurityEvaluation) -> SecurityEvaluation:
        """Calcula veredito baseado nos findings."""
        # Calcular score de seguranca
        penalty = 0.0
        penalty += evaluation.total_critical * 0.30
        penalty += evaluation.total_high * 0.15
        penalty += evaluation.total_medium * 0.05
        penalty += len(evaluation.supply_chain_issues) * 0.10

        evaluation.security_score = max(0.0, 1.0 - penalty)

        # Determinar veredito
        if evaluation.total_critical > 0 and self.fail_on_critical:
            evaluation.verdict = SecurityVerdict.REJECTED
            evaluation.recommendations.append(
                f"{evaluation.total_critical} vulnerabilidades CRITICAS encontradas. "
                "Corrigir antes de aplicar."
            )
        elif evaluation.total_critical > 0:
            evaluation.verdict = SecurityVerdict.NEEDS_FIX
            evaluation.recommendations.append(
                f"{evaluation.total_critical} vulnerabilidades CRITICAS. Revisao manual necessaria."
            )
        elif evaluation.total_high > 0:
            evaluation.verdict = SecurityVerdict.NEEDS_FIX
            evaluation.recommendations.append(
                f"{evaluation.total_high} vulnerabilidades HIGH. Recomendado corrigir."
            )
        elif evaluation.total_medium > 2:
            evaluation.verdict = SecurityVerdict.APPROVED_WITH_WARNINGS
            evaluation.recommendations.append(
                f"{evaluation.total_medium} vulnerabilidades MEDIUM. "
                "Revisar antes do proximo release."
            )
        elif evaluation.total_medium > 0:
            evaluation.verdict = SecurityVerdict.APPROVED_WITH_WARNINGS
        else:
            evaluation.verdict = SecurityVerdict.APPROVED

        if evaluation.security_score < 0.5:
            evaluation.recommendations.append(
                f"Score de seguranca muito baixo ({evaluation.security_score:.2f}). "
                "Refatorar patch com foco em seguranca."
            )

        return evaluation

    def get_status(self) -> Dict[str, Any]:
        return {
            "red_team_available": self._red_team is not None,
            "fuzzing_available": self._fuzzer is not None,
            "cve_monitor_available": self._cve_monitor is not None,
            "fail_on_critical": self.fail_on_critical,
            "features": {
                "offensive_testing": self._red_team is not None,
                "fuzzing": self._fuzzer is not None,
                "cve_monitoring": self._cve_monitor is not None,
                "auto_patch": (
                    self._cve_monitor.auto_patch_enabled
                    if self._cve_monitor else False
                ),
                "supply_chain_security": self._cve_monitor is not None,
            }
        }
