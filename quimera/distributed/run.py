"""
Quimera Mark X — Distributed Platform Entry Point (Horizonte 1)

Starts the full distributed platform:
  - API Gateway (FastAPI + uvicorn)
  - Distributed Orchestrator (worker pool + service discovery)
  - Tenant Manager (multi-tenant isolation)
  - Auto-Scaler (dynamic worker scaling)
  - Redis-backed mission queue

Usage:
    # Full platform
    python -m quimera.distributed.run --redis redis://localhost:6379
    
    # API only (multi-instance deployment)
    python -m quimera.distributed.run api --redis redis://redis:6379
    
    # Worker only
    python -m quimera.distributed.run worker --redis redis://redis:6379 --workers 4
    
    # Local mode (no Redis)
    python -m quimera.distributed.run local --workers 2
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("quimera.h1")


async def create_redis_client(redis_url: str):
    """Create Redis client with fallback."""
    if not redis_url:
        return None
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(redis_url)
        await client.ping()
        logger.info(f"Redis connected: {redis_url}")
        return client
    except Exception as e:
        logger.warning(f"Redis unavailable ({e}) — running in local mode")
        return None


async def run_api(redis_url: str, host: str = "0.0.0.0", port: int = 8000):
    """Start the API Gateway server."""
    import uvicorn

    redis = await create_redis_client(redis_url)

    # Import distributed modules
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from quimera.distributed.orchestrator import DistributedOrchestrator
    from quimera.distributed.tenant_manager import TenantManager
    from quimera.distributed.api_gateway import create_gateway

    # Initialize core services
    orchestrator = DistributedOrchestrator(redis)
    tenant_mgr = TenantManager(redis)
    await orchestrator.start()

    # Create seed tenant for development
    try:
        await tenant_mgr.create_tenant("Default Workspace", tier="pro")
    except Exception:
        pass

    # Build gateway
    app = create_gateway(orchestrator, tenant_mgr)
    logger.info(f"API Gateway starting on {host}:{port}")
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def run_worker(redis_url: str, capacity: int = 2):
    """Start a mission processing worker."""
    redis = await create_redis_client(redis_url)

    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from quimera.distributed.orchestrator import DistributedOrchestrator

    orchestrator = DistributedOrchestrator(redis)
    await orchestrator.start()

    # Define mission processing function
    async def process_mission(mission: dict):
        """Process a single mission through the full Quimera pipeline.
        
        Pipeline: detection → knowledge → hypothesis → candidate → build → validate
        """
        import time as _time
        mission_id = mission.get("mission_id", "unknown")
        language = mission.get("language", "c")
        code = mission.get("code", mission.get("error_context", ""))
        file_path = mission.get("kernel_path", mission.get("file_path", ""))
        logger.info(f"Worker processing mission {mission_id} ({language})")

        try:
            from quimera.pipeline import AutonomousPipeline
            t0 = _time.monotonic()
            pipeline = AutonomousPipeline()
            result = await pipeline.run(code, language=language)
            elapsed_ms = int((_time.monotonic() - t0) * 1000)

            patch_list = []
            if hasattr(result, 'evolved_patches') and result.evolved_patches:
                patch_list = result.evolved_patches
            best_patch = result.best_patch if hasattr(result, 'best_patch') and result.best_patch else (
                patch_list[0] if patch_list else ""
            )

            return {
                "mission_id": mission_id,
                "compilation_success": result.success if hasattr(result, 'success') else True,
                "patch": best_patch,
                "patches_generated": len(patch_list),
                "fitness_score": result.fitness_score if hasattr(result, 'fitness_score') else 0.0,
                "stages_completed": result.stages_completed if hasattr(result, 'stages_completed') else [],
                "time_ms": elapsed_ms,
                "worker": os.uname().nodename,
            }
        except Exception as e:
            logger.error(f"Pipeline failed for mission {mission_id}: {e}", exc_info=True)
            return {
                "mission_id": mission_id,
                "compilation_success": False,
                "patch": "",
                "error": str(e),
                "time_ms": 0,
                "worker": os.uname().nodename,
            }

    # Run worker loop
    worker_id = f"worker-{os.uname().nodename}-{os.getpid()}"
    await orchestrator.run_worker(worker_id, process_mission, capacity=capacity)


async def run_local(workers: int = 2):
    """Run everything locally without Redis — single process mode."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from quimera.distributed.orchestrator import DistributedOrchestrator
    from quimera.distributed.tenant_manager import TenantManager
    from quimera.distributed.scaler import AutoScaler

    # Initialize
    orchestrator = DistributedOrchestrator(None)
    tenant_mgr = TenantManager(None)
    scaler = AutoScaler(orchestrator, backend="local")

    await orchestrator.start()
    await tenant_mgr.create_tenant("Local Dev", tier="pro")

    logger.info(f"Quimera Mark X H1 — Local Mode ({workers} workers)")
    logger.info("Press Ctrl+C to stop")

    # Start worker simulation
    async def worker_process(mission):
        """Process mission through the full H1→H6 pipeline."""
        import time as _time
        t0 = _time.monotonic()
        try:
            from quimera.pipeline import AutonomousPipeline
            code = mission.get("code", mission.get("error_context", ""))
            kernel_path = mission.get("kernel_path", "")
            if not code and kernel_path:
                import os as _os
                if _os.path.exists(kernel_path):
                    with open(kernel_path) as f:
                        code = f.read()
            if not code:
                return {"ok": False, "error": "no source code in mission"}
            language = mission.get("language", "c")
            pipeline = AutonomousPipeline()
            result = await pipeline.run(
                code, language=language,
                error_description=mission.get("error_context", ""),
                tenant_id=mission.get("tenant_id", "default"),
            )
            elapsed_ms = int((_time.monotonic() - t0) * 1000)
            patch_list = []
            if hasattr(result, 'evolved_patches') and result.evolved_patches:
                patch_list = result.evolved_patches
            best_patch = result.best_patch if hasattr(result, 'best_patch') and result.best_patch else (
                patch_list[0] if patch_list else ""
            )
            return {
                "compilation_success": result.success if hasattr(result, 'success') else True,
                "patch": best_patch,
                "patches_generated": len(patch_list),
                "fitness_score": result.fitness_score if hasattr(result, 'fitness_score') else 0.0,
                "time_ms": elapsed_ms,
            }
        except Exception as e:
            logger.error(f"Local pipeline failed: {e}", exc_info=True)
            return {"compilation_success": False, "patch": "", "error": str(e), "time_ms": 0}

    # Run orchestrator with embedded workers
    tasks = []
    for i in range(workers):
        wid = f"worker-local-{i+1}"
        tasks.append(asyncio.create_task(
            orchestrator.run_worker(wid, worker_process, capacity=2)
        ))

    # Submit test missions
    for i in range(5):
        await orchestrator.submit_mission("tenant-1", {
            "kernel_path": f"/kernel/test_{i}.c",
            "language": "c",
            "error_context": f"Test mission {i}",
        })
        await asyncio.sleep(0.2)

    # Wait for workers
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass


async def run_full(redis_url: str, workers: int = 2):
    """Run the complete distributed platform."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from quimera.distributed.orchestrator import DistributedOrchestrator
    from quimera.distributed.tenant_manager import TenantManager
    from quimera.distributed.scaler import AutoScaler

    redis = await create_redis_client(redis_url)

    orchestrator = DistributedOrchestrator(redis)
    tenant_mgr = TenantManager(redis)
    scaler = AutoScaler(orchestrator, backend="local")

    await orchestrator.start()
    await tenant_mgr.create_tenant("Default", tier="pro")

    logger.info(f"Quimera Mark X — Distributed Platform v2.2.1")
    logger.info(f"  Redis: {'connected' if redis else 'local mode'}")
    logger.info(f"  Workers: {workers}")
    logger.info(f"  API: http://0.0.0.0:8000")

    # Start scaler
    scaler_task = asyncio.create_task(scaler.start())

    # Start API
    api_task = asyncio.create_task(run_api(redis_url))

    # Start workers
    worker_tasks = []
    for i in range(workers):
        worker_tasks.append(asyncio.create_task(run_worker(redis_url, capacity=2)))
        await asyncio.sleep(0.5)

    # Wait for shutdown
    try:
        await asyncio.gather(scaler_task, api_task, *worker_tasks)
    except asyncio.CancelledError:
        pass
    finally:
        await orchestrator.stop()
        await scaler.stop()


# ═══════════════════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Quimera Mark X — Distributed Platform")
    sub = parser.add_subparsers(dest="command")

    # api
    p_api = sub.add_parser("api", help="Start API Gateway")
    p_api.add_argument("--redis", default="redis://localhost:6379")
    p_api.add_argument("--host", default="0.0.0.0")
    p_api.add_argument("--port", type=int, default=8000)

    # worker
    p_worker = sub.add_parser("worker", help="Start Mission Worker")
    p_worker.add_argument("--redis", default="redis://localhost:6379")
    p_worker.add_argument("--workers", type=int, default=2)

    # local
    p_local = sub.add_parser("local", help="Run locally (no Redis)")
    p_local.add_argument("--workers", type=int, default=2)

    # all (default)
    p_all = sub.add_parser("all", help="Run full platform")
    p_all.add_argument("--redis", default="redis://localhost:6379")
    p_all.add_argument("--workers", type=int, default=2)

    args = parser.parse_args()

    if args.command == "api":
        asyncio.run(run_api(args.redis, args.host, args.port))
    elif args.command == "worker":
        asyncio.run(run_worker(args.redis, args.workers))
    elif args.command == "all":
        asyncio.run(run_full(args.redis, args.workers))
    elif args.command == "local":
        asyncio.run(run_local(args.workers))
    else:
        # Default: run full platform
        asyncio.run(run_full("redis://localhost:6379", 2))


if __name__ == "__main__":
    main()
