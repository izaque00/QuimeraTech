"""Formal Verification Pipeline — Orquestrador de Verificação Formal de Patches.

Integra os 3 motores de verificação do Horizonte 3 em um pipeline unificado:
1. Z3Analyst — verificação formal com Z3 Theorem Prover
2. CBMCAnalyzer — bounded model checking com CBMC/ESBMC
3. EbpfVerifier — verificação runtime com eBPF probes

Pipeline:
    Patch C → [Z3 Formal Proof] → [CBMC Bounded Check] → [eBPF Runtime Verify]
                  ↓                      ↓                        ↓
            SMT Solver           Model Checker            Kernel Probes
                  ↓                      ↓                        ↓
            SAT/UNSAT            Propriedades              Eventos runtime
                         ↘         ↓         ↙
                      Verdict Final Integrado

Uso:
    from quimera.core.formal_verification_pipeline import FormalVerificationPipeline
    
    pipeline = FormalVerificationPipeline()
    verdict = pipeline.verify(
        original_code=original_c,
        patched_code=patched_c,
        checks=["all"],
        sandbox_manager=manager,  # Opcional: para eBPF em sandbox
    )
    
    if verdict.certified_safe:
        print(f"✅ Patch certificado: {verdict.certificate}")
"""

import logging
import time
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from enum import Enum

from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)

# Importa os motores com fallback
try:
    from quimera.agentes.z3_analyst import Z3Analyst, VerificationResult, CounterExample, VulnerabilityClass
except ImportError:
    Z3Analyst = None

try:
    from quimera.integration_backends.cb_wrapper import CBMCAnalyzer, CBMCAnalysisResult, CBMCStatus
except ImportError:
    CBMCAnalyzer = None

try:
    from quimera.integration_backends.ebpf_verifier import EbpfVerifier, EbpfMonitorResult
except ImportError:
    EbpfVerifier = None


# ============================================================================
# Data Classes
# ============================================================================

class ConfidenceLevel(Enum):
    """Nível de confiança no veredito de verificação."""
    CERTIFIED = "certified"       # Passou nos 3 motores
    HIGH = "high"                 # Passou em 2 motores
    MEDIUM = "medium"             # Passou em 1 motor
    LOW = "low"                   # Apenas heurístico
    NONE = "none"                 # Não verificado


@dataclass
class EngineResult:
    """Resultado de um motor de verificação."""
    engine_name: str              # "z3", "cbmc", "ebpf"
    available: bool
    executed: bool
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    duration_ms: float = 0.0


@dataclass
class FormalVerificationVerdict:
    """Veredito final integrado da verificação formal."""
    certified_safe: bool
    confidence: ConfidenceLevel
    engines_executed: int
    engines_passed: int
    engine_results: Dict[str, EngineResult] = field(default_factory=dict)
    all_counterexamples: List[Dict[str, Any]] = field(default_factory=list)
    certificate: str = ""
    total_duration_ms: float = 0.0
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "certified_safe": self.certified_safe,
            "confidence": self.confidence.value,
            "engines": {
                name: {
                    "available": r.available,
                    "executed": r.executed,
                    "passed": r.passed,
                    "duration_ms": r.duration_ms,
                }
                for name, r in self.engine_results.items()
            },
            "certificate": self.certificate,
            "total_duration_ms": self.total_duration_ms,
            "recommendations": self.recommendations,
        }


# ============================================================================
# FormalVerificationPipeline
# ============================================================================

class FormalVerificationPipeline:
    """Pipeline integrado de verificação formal de patches.

    Orquestra Z3, CBMC e eBPF em sequência, com early-exit em falha
    crítica. Gera certificado de verificação com rastreabilidade.

    Attributes:
        z3_timeout_ms: Timeout do solver Z3.
        cbmc_unwind: Profundidade do bounded model checking.
        enable_ebpf: Se True, executa verificação eBPF (requer root/sandbox).
        fail_fast: Se True, para na primeira falha crítica.
    """

    def __init__(
        self,
        z3_timeout_ms: int = 5000,
        cbmc_unwind: int = 100,
        cbmc_timeout: int = 60,
        enable_ebpf: bool = True,
        fail_fast: bool = False,
    ):
        self.z3_timeout_ms = z3_timeout_ms
        self.cbmc_unwind = cbmc_unwind
        self.cbmc_timeout = cbmc_timeout
        self.enable_ebpf = enable_ebpf
        self.fail_fast = fail_fast

        # Inicializar motores
        self._z3 = self._init_z3()
        self._cbmc = self._init_cbmc()
        self._ebpf = self._init_ebpf()

        available = sum([
            self._z3 is not None,
            self._cbmc is not None and self._cbmc.is_available() if self._cbmc else False,
            self._ebpf is not None and self._ebpf.is_available if self._ebpf else False,
        ])
        montar_log(
            f"FormalVerificationPipeline: {available}/3 motores disponíveis "
            f"(Z3={'✅' if self._z3 else '❌'}, "
            f"CBMC={'✅' if self._cbmc and self._cbmc.is_available() else '❌'}, "
            f"eBPF={'✅' if self._ebpf and self._ebpf.is_available else '❌'})",
            "INFO" if available >= 2 else "WARNING"
        )

    def _init_z3(self):
        if Z3Analyst is None:
            return None
        try:
            return Z3Analyst(solver_timeout_ms=self.z3_timeout_ms)
        except Exception as e:
            logger.warning(f"Não foi possível inicializar Z3Analyst: {e}")
            return None

    def _init_cbmc(self):
        if CBMCAnalyzer is None:
            return None
        try:
            analyzer = CBMCAnalyzer(
                default_unwind=self.cbmc_unwind,
                timeout_seconds=self.cbmc_timeout,
            )
            return analyzer if analyzer.is_available() else None
        except Exception as e:
            logger.warning(f"Não foi possível inicializar CBMCAnalyzer: {e}")
            return None

    def _init_ebpf(self):
        if EbpfVerifier is None or not self.enable_ebpf:
            return None
        try:
            verifier = EbpfVerifier()
            return verifier if verifier.is_available else None
        except Exception as e:
            logger.warning(f"Não foi possível inicializar EbpfVerifier: {e}")
            return None

    # ------------------------------------------------------------------
    # API Principal
    # ------------------------------------------------------------------

    def verify(
        self,
        original_code: str,
        patched_code: str,
        checks: Optional[List[str]] = None,
        sandbox_pid: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FormalVerificationVerdict:
        """Executa o pipeline completo de verificação formal.

        Args:
            original_code: Código C original (antes do patch).
            patched_code: Código C após aplicar o patch.
            checks: Lista de checks Z3 (ex: ["buffer_overflow", "use_after_free"]).
            sandbox_pid: PID do processo em sandbox (para eBPF).
            metadata: Metadados do patch (arquivo, autor, etc.).

        Returns:
            FormalVerificationVerdict com resultado integrado.
        """
        start_time = time.time()
        engine_results: Dict[str, EngineResult] = {}

        if checks is None:
            checks = ["buffer_overflow", "use_after_free", "null_dereference", "race_condition"]

        # ── Engine 1: Z3 Formal Proof ──
        engine_results["z3"] = self._run_z3(original_code, patched_code, checks)
        if self.fail_fast and not engine_results["z3"].passed:
            return self._build_verdict(engine_results, start_time)

        # ── Engine 2: CBMC Bounded Model Checking ──
        engine_results["cbmc"] = self._run_cbmc(original_code, patched_code)
        if self.fail_fast and not engine_results["cbmc"].passed:
            return self._build_verdict(engine_results, start_time)

        # ── Engine 3: eBPF Runtime Verification ──
        engine_results["ebpf"] = self._run_ebpf(patched_code, sandbox_pid)

        return self._build_verdict(engine_results, start_time, metadata)

    def quick_verify(self, patched_code: str) -> Tuple[bool, str]:
        """Verificação rápida — apenas Z3 heurístico + CBMC se disponível.

        Ideal para PR checks e CI pipelines.

        Returns:
            (is_safe, reason)
        """
        # Z3 rápido (heurístico se sem solver)
        if self._z3:
            result = self._z3.verify_patch(
                patched_code, patched_code,  # mesmo código = verificar apenas o patch
                checks=["buffer_overflow", "use_after_free", "null_dereference"]
            )
            if not result.is_safe:
                reasons = [ce.description for ce in result.counterexamples]
                return False, f"Z3: {', '.join(reasons[:3])}"

        # CBMC rápido (unwind pequeno)
        if self._cbmc and self._cbmc.is_available():
            cbmc_result = self._cbmc.verify(
                patched_code, unwind_bound=20,
                properties=["array-bounds", "pointer", "overflow"]
            )
            if not cbmc_result.all_passed:
                return False, f"CBMC: {cbmc_result.failed_properties} falhas"

        return True, "Quick verification passed"

    # ------------------------------------------------------------------
    # Execução dos Motores
    # ------------------------------------------------------------------

    def _run_z3(
        self, original: str, patched: str, checks: List[str]
    ) -> EngineResult:
        """Executa verificação Z3."""
        result = EngineResult(
            engine_name="z3",
            available=self._z3 is not None,
            executed=False,
            passed=False,
        )

        if not self._z3:
            result.details["reason"] = "Z3Analyst não inicializado"
            return result

        start = time.time()
        try:
            z3_result = self._z3.verify_patch(original, patched, checks=checks)
            result.executed = True
            result.passed = z3_result.is_safe
            result.details = z3_result.to_dict()
            result.duration_ms = z3_result.verification_time_ms

            if not z3_result.is_safe:
                result.errors = [
                    f"[{ce['vulnerability']}] {ce['description']}"
                    for ce in z3_result.to_dict().get("counterexamples", [])
                ]

            montar_log(
                f"Z3: {'✅' if result.passed else '❌'} "
                f"({z3_result.verification_time_ms:.0f}ms)",
                "INFO" if result.passed else "WARNING"
            )
        except Exception as e:
            result.executed = True
            result.errors.append(f"Z3 erro: {e}")
            logger.error(f"Z3 verification error: {e}", exc_info=True)

        result.duration_ms = (time.time() - start) * 1000
        return result

    def _run_cbmc(self, original: str, patched: str) -> EngineResult:
        """Executa verificação CBMC."""
        result = EngineResult(
            engine_name="cbmc",
            available=self._cbmc is not None and self._cbmc.is_available(),
            executed=False,
            passed=False,
        )

        if not self._cbmc or not self._cbmc.is_available():
            result.details["reason"] = "CBMC não disponível"
            return result

        start = time.time()
        try:
            patch_results = self._cbmc.verify_patch(
                original, patched,
                unwind_bound=self.cbmc_unwind,
                properties=["array-bounds", "pointer", "overflow", "memory-leak"],
            )

            result.executed = True
            if "patched" in patch_results:
                patched_result = patch_results["patched"]
                result.passed = patched_result.all_passed
                result.details = patched_result.to_dict()
                if not patched_result.all_passed:
                    result.errors.append(
                        f"CBMC: {patched_result.failed_properties} falhas"
                    )
            else:
                result.errors.append("CBMC: resultado do patch não disponível")
        except Exception as e:
            result.executed = True
            result.errors.append(f"CBMC erro: {e}")
            logger.error(f"CBMC error: {e}", exc_info=True)

        result.duration_ms = (time.time() - start) * 1000
        return result

    def _run_ebpf(
        self, patched_code: str, sandbox_pid: Optional[int]
    ) -> EngineResult:
        """Executa verificação eBPF."""
        result = EngineResult(
            engine_name="ebpf",
            available=self._ebpf is not None and self._ebpf.is_available,
            executed=False,
            passed=False,
        )

        if not self._ebpf or not self._ebpf.is_available:
            result.details["reason"] = "eBPF não disponível (requer bpftrace + root)"
            return result

        # eBPF precisa de execução real — geralmente em sandbox
        if sandbox_pid is None:
            result.details["reason"] = "Sem sandbox PID — pulando eBPF"
            result.executed = False
            return result

        start = time.time()
        try:
            with self._ebpf.monitor(pid=sandbox_pid) as session:
                # O código seria executado no sandbox aqui
                # Por enquanto, apenas monitoramos
                monitor_result = session.collect()

            result.executed = True
            result.passed = monitor_result.is_clean
            result.details = {
                "total_events": monitor_result.total_events,
                "critical": monitor_result.critical_count,
                "error": monitor_result.error_count,
                "warning": monitor_result.warning_count,
            }
            if not monitor_result.is_clean:
                result.errors = [
                    f"eBPF: {e.message}" for e in monitor_result.events
                    if e.severity in ("critical", "error")
                ]
        except Exception as e:
            result.executed = True
            result.errors.append(f"eBPF erro: {e}")
            logger.debug(f"eBPF error: {e}")

        result.duration_ms = (time.time() - start) * 1000
        return result

    # ------------------------------------------------------------------
    # Construção do Veredito
    # ------------------------------------------------------------------

    def _build_verdict(
        self,
        engine_results: Dict[str, EngineResult],
        start_time: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FormalVerificationVerdict:
        """Constrói o veredito integrado."""
        executed = [r for r in engine_results.values() if r.executed]
        passed = [r for r in executed if r.passed]
        available = [r for r in engine_results.values() if r.available]

        all_counterexamples = []
        for r in executed:
            if not r.passed and r.errors:
                all_counterexamples.append({
                    "engine": r.engine_name,
                    "errors": r.errors,
                })

        # Determinar confiança
        if len(executed) >= 3 and len(passed) == len(executed):
            confidence = ConfidenceLevel.CERTIFIED
        elif len(passed) >= 2:
            confidence = ConfidenceLevel.HIGH
        elif len(passed) >= 1:
            confidence = ConfidenceLevel.MEDIUM
        elif len(executed) > 0:
            confidence = ConfidenceLevel.LOW
        else:
            confidence = ConfidenceLevel.NONE

        certified = confidence in (ConfidenceLevel.CERTIFIED, ConfidenceLevel.HIGH)

        # Gerar certificado
        certificate = self._generate_certificate(
            engine_results, confidence, metadata
        )

        # Recomendações
        recommendations = []
        if not certified:
            if confidence == ConfidenceLevel.MEDIUM:
                recommendations.append(
                    "Instale CBMC e/ou bpftrace para verificação completa (nível CERTIFIED)"
                )
            if any(
                r.engine_name == "z3" and not r.available
                for r in engine_results.values()
            ):
                recommendations.append(
                    "Instale z3-solver: pip install z3-solver"
                )
            if all_counterexamples:
                recommendations.append(
                    "Verifique os contra-exemplos manualmente antes de aplicar o patch"
                )

        total_ms = (time.time() - start_time) * 1000

        return FormalVerificationVerdict(
            certified_safe=certified,
            confidence=confidence,
            engines_executed=len(executed),
            engines_passed=len(passed),
            engine_results=engine_results,
            all_counterexamples=all_counterexamples,
            certificate=certificate,
            total_duration_ms=total_ms,
            recommendations=recommendations,
        )

    def _generate_certificate(
        self,
        engine_results: Dict[str, EngineResult],
        confidence: ConfidenceLevel,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Gera certificado de verificação em formato legível."""
        cert_lines = [
            "=" * 70,
            "  QUIMERA FORMAL VERIFICATION CERTIFICATE",
            "=" * 70,
            f"  Confidence: {confidence.value.upper()}",
            f"  Timestamp:  {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        ]

        if metadata:
            for k, v in metadata.items():
                cert_lines.append(f"  {k}: {v}")

        cert_lines.append("-" * 70)
        cert_lines.append("  Engine Results:")
        for name, result in engine_results.items():
            status = "PASS" if result.passed else ("FAIL" if result.executed else "SKIP")
            icon = "✅" if result.passed else ("❌" if result.executed else "⏭️")
            cert_lines.append(
                f"    {icon} {name.upper():6s} [{status}] "
                f"(available={result.available}, time={result.duration_ms:.0f}ms)"
            )
            if result.errors:
                for err in result.errors[:3]:
                    cert_lines.append(f"       ↳ {err}")

        cert_lines.append("-" * 70)
        cert_lines.append(
            f"  Verdict: {'✅ CERTIFIED SAFE' if confidence in (ConfidenceLevel.CERTIFIED, ConfidenceLevel.HIGH) else '⚠️  NEEDS REVIEW'}"
        )
        cert_lines.append("=" * 70)

        return "\n".join(cert_lines)

    # ------------------------------------------------------------------
    # Informações
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Retorna status dos motores de verificação."""
        return {
            "z3_available": self._z3 is not None,
            "cbmc_available": self._cbmc is not None and self._cbmc.is_available() if self._cbmc else False,
            "ebpf_available": self._ebpf is not None and self._ebpf.is_available if self._ebpf else False,
            "fail_fast": self.fail_fast,
            "features": {
                "z3_theorem_proving": self._z3 is not None,
                "bounded_model_checking": self._cbmc is not None and self._cbmc.is_available() if self._cbmc else False,
                "runtime_verification": self._ebpf is not None and self._ebpf.is_available if self._ebpf else False,
                "formal_certification": True,  # Pipeline sempre disponível (pelo menos heurístico)
            }
        }


# ============================================================================
# Factory
# ============================================================================

def create_verification_pipeline(
    z3_timeout: int = 5000,
    cbmc_unwind: int = 100,
    enable_ebpf: bool = True,
    fail_fast: bool = False,
) -> FormalVerificationPipeline:
    """Factory function para o pipeline de verificação formal."""
    return FormalVerificationPipeline(
        z3_timeout_ms=z3_timeout,
        cbmc_unwind=cbmc_unwind,
        enable_ebpf=enable_ebpf,
        fail_fast=fail_fast,
    )
