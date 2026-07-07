# quimera/api/run.py
"""
Entrypoint para iniciar o servidor Quimera.

Modos:
    api       — Apenas API REST (FastAPI + uvicorn)
    worker    — Apenas Mission Worker (processa fila)
    all       — API + Worker + Dashboard (completo)

Uso:
    python -m quimera.api.run api --port 8000
    python -m quimera.api.run worker
    python -m quimera.api.run all --port 8000 --redis redis://localhost:6379
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Adiciona raiz ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def parse_args():
    parser = argparse.ArgumentParser(description="Quimera API Server")
    parser.add_argument("mode", choices=["api", "worker", "all"], default="all", nargs="?")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--redis", default=None, help="Redis URL (redis://host:port)")
    parser.add_argument("--workers", type=int, default=2, help="Max concurrent workers")
    parser.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error"])
    return parser.parse_args()


async def main():
    args = parse_args()
    
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("quimera.api")
    
    # Redis
    redis_client = None
    if args.redis:
        try:
            import redis.asyncio as aioredis
            redis_client = aioredis.from_url(args.redis)
            await redis_client.ping()
            logger.info(f"Redis conectado: {args.redis}")
        except Exception as e:
            logger.warning(f"Redis indisponível ({e}) — usando modo local")
    
    if args.mode in ("api", "all"):
        # API + Dashboard
        from quimera.api.server import create_app, app as default_app
        from quimera.api.dashboard import DASHBOARD_HTML
        
        app = create_app(redis_client=redis_client)
        
        @app.get("/dashboard")
        async def dashboard():
            from fastapi.responses import HTMLResponse
            return HTMLResponse(content=DASHBOARD_HTML)
        
        import uvicorn
        
        if args.mode == "all":
            # Inicia worker em background
            from quimera.api.worker import MissionWorker
            from quimera.api.mission_queue import MissionQueue
            
            queue = MissionQueue(redis_client)
            worker = MissionWorker(queue, max_concurrent=args.workers)
            asyncio.create_task(worker.start())
            logger.info(f"Worker iniciado ({args.workers} workers)")
        
        config = uvicorn.Config(app, host=args.host, port=args.port, log_level=args.log_level)
        server = uvicorn.Server(config)
        logger.info(f"🚀 Quimera API: http://{args.host}:{args.port}")
        logger.info(f"📊 Dashboard: http://{args.host}:{args.port}/dashboard")
        logger.info(f"❤️  Health:   http://{args.host}:{args.port}/api/v1/health")
        await server.serve()
    
    elif args.mode == "worker":
        from quimera.api.worker import run_worker
        await run_worker(args.redis)


if __name__ == "__main__":
    asyncio.run(main())
