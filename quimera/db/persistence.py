"""
Quimera Mark X — Persistence Adapter v2.2.1

Bridges all 6 horizons with the database.
Provides async persistence adapters for:
  H1: Core (missions, patches, agents)
  H3: Formal Verification
  H4: Genetic Evolution + Coevolution
  H5: Security (Red Team, Fuzzing, CVE, Supply Chain)
  H6: Multi-Language (Plugins, Files, IDE)

Usage:
    adapter = PersistenceAdapter()
    await adapter.initialize()
    
    # Save a mission
    mission = await adapter.missions.create_mission(dto)
    
    # Save verification verdict
    await adapter.verification.save_verdict(verdict)
    
    # Save genetic population  
    await adapter.evolution.save_population(...)
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from .session import session_scope, create_repos

logger = logging.getLogger("quimera.persistence")


# ═══════════════════════════════════════════════════════════════════════
# DTOs
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class MissionDTO:
    id: str = ""
    type: str = "auto_repair"
    status: str = "pending"
    target_file: str = ""
    original_code: Optional[str] = None
    patched_code: Optional[str] = None
    error_context: Optional[str] = None
    language: str = "c"
    priority: int = 0
    max_attempts: int = 3
    metadata_json: Optional[Dict] = None


@dataclass
class PatchDTO:
    id: str = ""
    mission_id: str = ""
    patch_code: str = ""
    original_code: Optional[str] = None
    diff_unified: Optional[str] = None
    fitness_score: Optional[float] = None
    generation: Optional[int] = None
    status: str = "pending"
    created_by_agent: Optional[str] = None
    metadata_json: Optional[Dict] = None


@dataclass
class VerificationVerdictDTO:
    mission_id: str = ""
    patch_id: str = ""
    confidence: str = "MEDIUM"  # CERTIFIED, HIGH, MEDIUM, LOW, NONE
    z3_result: Optional[Dict] = None
    cbmc_result: Optional[Dict] = None
    ebpf_result: Optional[Dict] = None
    overall_score: float = 0.0
    issues: List[Dict] = field(default_factory=list)


@dataclass
class SecurityVerdictDTO:
    mission_id: str = ""
    patch_id: str = ""
    verdict: str = "NEEDS_FIX"  # APPROVED, APPROVED_WITH_WARNINGS, NEEDS_FIX, REJECTED
    red_team_findings: List[Dict] = field(default_factory=list)
    fuzzing_crashes: List[Dict] = field(default_factory=list)
    cve_matches: List[Dict] = field(default_factory=list)
    supply_chain_issues: List[Dict] = field(default_factory=list)
    security_score: float = 0.0


# ═══════════════════════════════════════════════════════════════════════
# Adapters
# ═══════════════════════════════════════════════════════════════════════

class MissionPersistence:
    """H1: Core persistence."""

    async def create_mission(self, dto: MissionDTO) -> MissionDTO:
        async with session_scope() as session:
            repos = create_repos(session)
            m = await repos["missions"].create(
                type=dto.type, status=dto.status,
                target_file=dto.target_file, original_code=dto.original_code,
                error_context=dto.error_context, language=dto.language,
                priority=dto.priority, max_attempts=dto.max_attempts,
                metadata_json=dto.metadata_json,
            )
            dto.id = m.id
            return dto

    async def get_mission(self, mission_id: str) -> Optional[Dict]:
        async with session_scope() as session:
            repos = create_repos(session)
            m = await repos["missions"].get(mission_id)
            if not m:
                return None
            return {
                "id": m.id, "type": m.type, "status": m.status,
                "target_file": m.target_file, "language": m.language,
                "priority": m.priority, "attempt_count": m.attempt_count,
                "original_code": m.original_code, "patched_code": m.patched_code,
                "metadata_json": m.metadata_json,
                "created_at": str(m.created_at) if m.created_at else None,
                "completed_at": str(m.completed_at) if m.completed_at else None,
            }

    async def update_status(self, mission_id: str, status: str, **kwargs):
        async with session_scope() as session:
            repos = create_repos(session)
            await repos["missions"].update(mission_id, status=status, **kwargs)

    async def save_patch(self, dto: PatchDTO) -> PatchDTO:
        async with session_scope() as session:
            repos = create_repos(session)
            p = await repos["patches"].create(
                mission_id=dto.mission_id, patch_code=dto.patch_code,
                original_code=dto.original_code, diff_unified=dto.diff_unified,
                fitness_score=dto.fitness_score, generation=dto.generation,
                status=dto.status, created_by_agent=dto.created_by_agent,
                metadata_json=dto.metadata_json,
            )
            dto.id = p.id
            return dto

    async def get_pending_missions(self, limit: int = 10) -> List[Dict]:
        async with session_scope() as session:
            repos = create_repos(session)
            missions = await repos["missions"].get_active(limit)
            return [{"id": m.id, "type": m.type, "target_file": m.target_file,
                     "language": m.language, "priority": m.priority} for m in missions]

    async def get_best_patches(self, mission_id: str, limit: int = 10) -> List[Dict]:
        async with session_scope() as session:
            repos = create_repos(session)
            patches = await repos["patches"].list(limit=limit, mission_id=mission_id)
            return [{"id": p.id, "patch_code": p.patch_code,
                     "fitness_score": p.fitness_score, "generation": p.generation,
                     "status": p.status, "created_by_agent": p.created_by_agent}
                    for p in patches]


class VerificationPersistence:
    """H3: Formal verification results persisted as mission metadata + vulns."""

    async def save_verdict(self, verdict: VerificationVerdictDTO):
        async with session_scope() as session:
            repos = create_repos(session)

            # Update mission metadata
            await repos["missions"].update(
                verdict.mission_id,
                metadata_json={
                    "verification": {
                        "confidence": verdict.confidence,
                        "z3": verdict.z3_result,
                        "cbmc": verdict.cbmc_result,
                        "ebpf": verdict.ebpf_result,
                        "overall_score": verdict.overall_score,
                    }
                },
            )

            # Save issues as vulnerabilities
            for issue in verdict.issues:
                await repos["vulnerabilities"].create(
                    patch_id=verdict.patch_id,
                    type=issue.get("type", "unknown"),
                    severity=issue.get("severity", "MEDIUM"),
                    description=issue.get("description", ""),
                    location_file=issue.get("file"),
                    location_line=issue.get("line"),
                    detected_by="formal_verification",
                    status="open" if verdict.confidence in ("LOW", "NONE") else "resolved",
                )

            logger.info(f"Verification saved: {verdict.mission_id} conf={verdict.confidence}")


class EvolutionPersistence:
    """H4: Genetic evolution + coevolution persistence."""

    async def save_population(
        self, mission_id: str, generation: int,
        population_size: int, individuals: List[Dict],
        best_fitness: float, avg_fitness: float,
        median_fitness: float = 0.0, diversity: float = 0.0,
        pareto_front_size: int = 0, elapsed_ms: float = 0.0,
    ) -> str:
        async with session_scope() as session:
            repos = create_repos(session)
            pop = await repos["genetic_populations"].create(
                mission_id=mission_id, generation=generation,
                population_size=population_size, best_fitness=best_fitness,
                avg_fitness=avg_fitness, median_fitness=median_fitness,
                diversity=diversity, pareto_front_size=pareto_front_size,
                elapsed_ms=elapsed_ms, individuals_json={"individuals": individuals},
            )

            for ind in individuals[:10]:
                await repos["genetic_individuals"].create(
                    population_id=pop.id, patch_code=ind.get("patch_code"),
                    fitness_json=ind.get("fitness_json"),
                    generation_born=ind.get("generation_born", generation),
                    parent_ids=ind.get("parent_ids"),
                    pareto_rank=ind.get("pareto_rank"),
                    crowding_distance=ind.get("crowding_distance"),
                )
            return pop.id

    async def save_coevolution(
        self, mission_id: str, generation: int,
        patch_best_fitness: float, test_best_effectiveness: float,
        arms_race_intensity: float, robust_patches_count: int,
        elapsed_ms: float, tests: List[Dict],
    ):
        async with session_scope() as session:
            repos = create_repos(session)
            await repos["coevolution_sessions"].create(
                mission_id=mission_id, generation=generation,
                patch_best_fitness=patch_best_fitness,
                test_best_effectiveness=test_best_effectiveness,
                arms_race_intensity=arms_race_intensity,
                robust_patches_count=robust_patches_count,
                elapsed_ms=elapsed_ms, tests_json={"tests": tests},
            )

    async def get_evolution_history(self, mission_id: str) -> List[Dict]:
        async with session_scope() as session:
            from sqlalchemy import select as sa_select
            repos = create_repos(session)
            pops = await repos["genetic_populations"].list(limit=500, mission_id=mission_id)
            return [
                {"generation": p.generation, "population_size": p.population_size,
                 "best_fitness": p.best_fitness, "avg_fitness": p.avg_fitness,
                 "diversity": p.diversity, "pareto_front_size": p.pareto_front_size}
                for p in pops
            ]


class SecurityPersistence:
    """H5: Red Team + Fuzzing + CVE + Supply Chain persistence."""

    async def save_security_verdict(self, verdict: SecurityVerdictDTO):
        async with session_scope() as session:
            repos = create_repos(session)

            # Red team → vulnerabilities
            for f in verdict.red_team_findings:
                await repos["vulnerabilities"].create(
                    patch_id=verdict.patch_id,
                    type=f.get("vuln_type", "unknown"),
                    severity=f.get("severity", "HIGH"),
                    description=f.get("description", ""),
                    exploit_code=f.get("payload"),
                    detected_by="red_team",
                    status="open" if f.get("exploitable") else "mitigated",
                )

            # Fuzzing crashes
            if verdict.fuzzing_crashes:
                await repos["fuzzing_sessions"].create(
                    target_file=verdict.fuzzing_crashes[0].get("target_file", ""),
                    total_iterations=verdict.fuzzing_crashes[0].get("iterations", 0),
                    unique_crashes=len(verdict.fuzzing_crashes),
                    crash_data={"crashes": verdict.fuzzing_crashes},
                    completed_at=datetime.utcnow(),
                )

            # CVE cache
            for cve in verdict.cve_matches:
                await repos["cve_cache"].upsert(
                    cve_id=cve.get("cve_id", ""),
                    description=cve.get("description"),
                    severity=cve.get("severity"),
                    cvss_score=cve.get("cvss_score"),
                    cwe_ids=cve.get("cwe_ids"),
                )

            # Supply chain
            if verdict.supply_chain_issues:
                await repos["supply_chain_checks"].create(
                    file_path=verdict.supply_chain_issues[0].get("file_path", ""),
                    patch_id=verdict.patch_id,
                    vulnerable_deps=[i for i in verdict.supply_chain_issues if i.get("type") == "dependency"],
                    license_issues=[i for i in verdict.supply_chain_issues if i.get("type") == "license"],
                    risk_score=1.0 - verdict.security_score,
                )

            # Update patch status
            status_map = {"APPROVED": "approved", "APPROVED_WITH_WARNINGS": "approved",
                         "NEEDS_FIX": "needs_revision", "REJECTED": "rejected"}
            await repos["patches"].update(
                verdict.patch_id,
                status=status_map.get(verdict.verdict, "pending"),
                metadata_json={"security_verdict": verdict.verdict, "score": verdict.security_score},
            )

            logger.info(f"Security verdict: {verdict.patch_id} {verdict.verdict}")


class MultiLangPersistence:
    """H6: Plugin registry + multi-language files + IDE sessions."""

    async def register_plugin(
        self, name: str, language: str, version: str,
        class_name: str, module_path: str,
        capabilities: Optional[List[str]] = None,
    ) -> str:
        async with session_scope() as session:
            repos = create_repos(session)
            p = await repos["plugin_registry"].create(
                name=name, language=language, version=version,
                class_name=class_name, module_path=module_path,
                capabilities=capabilities or [],
            )
            return p.id

    async def save_file_repair(
        self, file_path: str, language: str,
        original_code: str, patched_code: str,
        issues_found: int, issues_fixed: int,
        agent_used: str, verified: bool = False,
        repair_duration_ms: float = 0.0,
        issues: Optional[List[Dict]] = None,
    ):
        async with session_scope() as session:
            repos = create_repos(session)
            await repos["multi_lang_files"].create(
                file_path=file_path, language=language,
                original_code=original_code, patched_code=patched_code,
                issues_found=issues_found, issues_fixed=issues_fixed,
                agent_used=agent_used, verified=verified,
                repair_duration_ms=repair_duration_ms,
                issues_json=issues or [],
            )

    async def start_ide_session(self, ide_type: str, workspace_path: str) -> str:
        async with session_scope() as session:
            repos = create_repos(session)
            s = await repos["ide_sessions"].create(
                ide_type=ide_type, workspace_path=workspace_path,
            )
            return s.id

    async def end_ide_session(self, session_id: str, files_processed: int, total_repairs: int):
        async with session_scope() as session:
            repos = create_repos(session)
            await repos["ide_sessions"].update(
                session_id, files_processed=files_processed,
                total_repairs=total_repairs, session_end=datetime.utcnow(),
            )

    async def get_active_plugins(self, language: Optional[str] = None) -> List[Dict]:
        async with session_scope() as session:
            repos = create_repos(session)
            if language:
                plugins = await repos["plugin_registry"].get_active_for_language(language)
            else:
                plugins = await repos["plugin_registry"].list(limit=100)
            return [{"name": p.name, "language": p.language, "version": p.version,
                     "class_name": p.class_name, "capabilities": p.capabilities}
                    for p in plugins]


# ═══════════════════════════════════════════════════════════════════════
# Master Adapter
# ═══════════════════════════════════════════════════════════════════════

class PersistenceAdapter:
    """Top-level persistence adapter connecting all 6 horizons to the database."""

    def __init__(self):
        self.missions = MissionPersistence()
        self.verification = VerificationPersistence()
        self.security = SecurityPersistence()
        self.evolution = EvolutionPersistence()
        self.multilang = MultiLangPersistence()

    async def initialize(self):
        from .session import check_db_health, init_db_async
        if not await check_db_health():
            logger.info("Initializing database...")
            await init_db_async()
        logger.info("PersistenceAdapter ready.")

    async def health_check(self) -> Dict[str, bool]:
        from .session import check_db_health
        ok = await check_db_health()
        return {"database": ok}
