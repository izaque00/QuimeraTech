"""
Quimera Mark X — DB Initializer & Migration Runner

Usage:
    python -m quimera.db.init_db          # create tables (dev)
    python -m quimera.db.init_db migrate  # run Alembic migrations
    python -m quimera.db.init_db seed     # seed test data
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("quimera.db.init")


async def run_migrations():
    """Run Alembic migrations programmatically."""
    from alembic.config import Config
    from alembic import command

    alembic_ini = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "..", "..", "alembic.ini"
    )
    alembic_ini = os.path.abspath(alembic_ini)

    if not os.path.exists(alembic_ini):
        logger.warning(f"alembic.ini not found at {alembic_ini}, using dev mode")
        from quimera.db import init_db
        await init_db()
        return

    alembic_cfg = Config(alembic_ini)
    command.upgrade(alembic_cfg, "head")
    logger.info("Migrations applied successfully.")


async def seed_test_data():
    """Insert test data for development."""
    from quimera.db.session import session_scope, create_repos

    async with session_scope() as session:
        repos = create_repos(session)

        # Seed a test mission
        mission = await repos["missions"].create(
            type="auto_repair",
            status="in_progress",
            target_file="/kernel/fs/ext4/inode.c",
            original_code="/* vulnerable buffer access */\nvoid process(char *buf) {\n    char local[64];\n    strcpy(local, buf);\n}",
            error_context="Buffer overflow in ext4_inode processing",
            language="c",
            priority=10,
            max_attempts=5,
        )
        logger.info(f"Seeded mission: {mission.id}")

        # Seed a patch
        patch = await repos["patches"].create(
            mission_id=mission.id,
            patch_code="void process(char *buf) {\n    char local[64];\n    strncpy(local, buf, sizeof(local)-1);\n    local[63] = '\\0';\n}",
            original_code=mission.original_code,
            status="pending_review",
            fitness_score=0.85,
            generation=3,
            created_by_agent="refinador_v4",
        )
        logger.info(f"Seeded patch: {patch.id}")

        # Seed a vulnerability
        vuln = await repos["vulnerabilities"].create(
            patch_id=patch.id,
            type="buffer_overflow",
            severity="HIGH",
            description="Stack-based buffer overflow via unbounded strcpy",
            location_file="inode.c",
            location_line=4,
            remediation="Replace strcpy with strncpy + null termination",
            detected_by="red_team",
        )
        logger.info(f"Seeded vulnerability: {vuln.id}")

        # Seed a fuzzing session
        fuzz = await repos["fuzzing_sessions"].create(
            target_file="/kernel/fs/ext4/inode.c",
            strategy="mutation",
            total_iterations=10000,
            unique_crashes=3,
            coverage_pct=72.5,
            executions_per_second=1500.0,
            completed_at=datetime.utcnow(),
            duration_ms=6500.0,
        )
        logger.info(f"Seeded fuzzing session: {fuzz.id}")

        # Seed a genetic population
        pop = await repos["genetic_populations"].create(
            mission_id=mission.id,
            generation=3,
            population_size=20,
            best_fitness=0.85,
            avg_fitness=0.62,
            median_fitness=0.65,
            diversity=0.35,
            pareto_front_size=4,
            elapsed_ms=1250.0,
        )
        logger.info(f"Seeded population: {pop.id}")

        # Seed genetic individual
        ind = await repos["genetic_individuals"].create(
            population_id=pop.id,
            patch_id=patch.id,
            patch_code=patch.patch_code,
            fitness_json={"compile": 1.0, "tests": 0.9, "security": 0.8, "performance": 0.7},
            generation_born=3,
            parent_ids=["parent_aa", "parent_bb"],
            pareto_rank=1,
            crowding_distance=0.25,
        )
        logger.info(f"Seeded individual: {ind.id}")

        # Seed coevolution session
        coev = await repos["coevolution_sessions"].create(
            mission_id=mission.id,
            generation=5,
            patch_best_fitness=0.88,
            test_best_effectiveness=0.92,
            arms_race_intensity=0.75,
            robust_patches_count=3,
            elapsed_ms=4500.0,
        )
        logger.info(f"Seeded coevolution session: {coev.id}")

        # Seed plugin
        plugin = await repos["plugin_registry"].create(
            name="Rust Kernel Agent",
            language="rust",
            version="1.0.0",
            class_name="RustAgent",
            module_path="quimera.plugins.rust_agent",
            capabilities=["detect", "repair", "verify"],
        )
        logger.info(f"Seeded plugin: {plugin.id}")

        # Seed multi-lang file
        mlf = await repos["multi_lang_files"].create(
            file_path="/rust/kernel/src/alloc.rs",
            language="rust",
            original_code="fn alloc(size: usize) -> *mut u8 { unsafe { libc::malloc(size) } }",
            patched_code="fn alloc(size: usize) -> *mut u8 {\n    if size == 0 { return std::ptr::null_mut(); }\n    unsafe { libc::malloc(size) }\n}",
            issues_found=2,
            issues_fixed=2,
            agent_used="rust_agent_v1",
            verified=True,
            repair_duration_ms=320.0,
        )
        logger.info(f"Seeded multi-lang file: {mlf.id}")

        # Seed IDE session
        ide = await repos["ide_sessions"].create(
            ide_type="vscode",
            ide_version="1.92.0",
            workspace_path="/home/dev/kernel",
            files_processed=15,
            total_repairs=8,
        )
        logger.info(f"Seeded IDE session: {ide.id}")

        # Seed supply chain check
        sc = await repos["supply_chain_checks"].create(
            file_path="/kernel/fs/ext4/inode.c",
            patch_id=patch.id,
            vulnerable_deps=[],
            license_issues=[],
            third_party_detected=False,
            risk_score=0.05,
        )
        logger.info(f"Seeded supply chain check: {sc.id}")

    logger.info("Seed data inserted successfully.")


async def main():
    if "migrate" in sys.argv:
        await run_migrations()
    elif "seed" in sys.argv:
        await seed_test_data()
    else:
        # Dev mode: create tables directly
        from quimera.db import init_db
        await init_db()
        logger.info("Dev mode: tables created (use 'migrate' for Alembic, 'seed' for test data)")


if __name__ == "__main__":
    asyncio.run(main())
