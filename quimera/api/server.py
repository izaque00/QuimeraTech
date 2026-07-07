# quimera/api/server.py
"""
Servidor FastAPI do Quimera.

Expõe API REST + WebSocket para submissão de missões,
acompanhamento em tempo real, e gestão do sistema.

Uso:
    uvicorn quimera.api.server:app --host 0.0.0.0 --port 8000
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from quimera.api.schemas import (
    AgentInfo, AgentsResponse, HealthResponse,
    MetricsResponse, MissionCreate, MissionResponse,
    MissionStatus,
)
from quimera.api.mission_queue import MissionQueue

logger = logging.getLogger(__name__)

# Estado global do servidor
_start_time = time.time()
_mission_queue: Optional[MissionQueue] = None
_active_websockets: dict = {}


def create_app(redis_client=None, orquestrador=None) -> FastAPI:
    """Cria e configura a aplicação FastAPI."""
    global _mission_queue
    
    app = FastAPI(
        title="Quimera API",
        version="3.0.0",
        description="API REST do Sistema Quimera — Reparo autônomo de kernel Linux",
    )
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiter middleware
    @app.middleware("http")
    async def rate_limit_middleware(request, call_next):
        """Token-bucket rate limiting per client IP."""
        try:
            from quimera.utils.rate_limiter import rate_limiter as _rl
            from fastapi.responses import JSONResponse
            client_ip = request.client.host if request.client else "unknown"
            path = request.url.path
            if path == "/api/v1/missions" and request.method == "POST":
                if not _rl.is_allowed(f"mission:{client_ip}", rate=5.0, burst=10):
                    return JSONResponse(status_code=429, content={"detail": "Too many mission submissions"})
            else:
                if not _rl.is_allowed(client_ip, rate=50.0, burst=100):
                    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
        except ImportError:
            pass
        response = await call_next(request)
        return response
    
    _mission_queue = MissionQueue(redis_client)
    
    # ============== ENDPOINTS ==============
    
    @app.get("/api/v1/health", response_model=HealthResponse)
    async def health():
        """Health check do sistema."""
        manifest_version = "3.0.0"
        try:
            from quimera.orquestrador_aprimorado import OrquestradorAprimorado
            orch = OrquestradorAprimorado()
            manifest_version = orch.manifesto.get("versao", "3.0.0")
            agents_loaded = len(orch.componentes)
        except Exception:
            agents_loaded = 0
        
        queue_size = await _mission_queue.get_queue_size() if _mission_queue else 0
        active = await _mission_queue.list_active() if _mission_queue else []
        
        return HealthResponse(
            version=manifest_version,
            uptime_seconds=time.time() - _start_time,
            active_missions=len(active),
            total_missions=queue_size + len(active),
            sandbox_available=False,  # validado no startup real
            redis_connected=redis_client is not None,
            db_connected=True,
            agents_loaded=agents_loaded,
        )
    
    @app.get("/metrics")
    async def metrics():
        """Prometheus-compatible metrics endpoint."""
        from fastapi.responses import PlainTextResponse
        try:
            from quimera.logs.metrics import metrics as _m
            return PlainTextResponse(content=_m.get_metrics_text(), media_type="text/plain; version=0.0.4")
        except ImportError:
            return {"metrics": "prometheus_client not installed"}
    
    @app.post("/api/v1/missions", response_model=MissionResponse, status_code=201)
    async def create_mission(mission: MissionCreate):
        """Submete nova missão de reparo."""
        mission_id = await _mission_queue.enqueue(mission.model_dump())
        status = await _mission_queue.get_status(mission_id)
        return MissionResponse(
            mission_id=mission_id,
            status=MissionStatus.QUEUED,
            kernel_path=mission.kernel_path,
            target_arch=mission.target_arch,
            created_at=datetime.fromisoformat(status["created_at"]),
            updated_at=datetime.fromisoformat(status["updated_at"]),
        )
    
    @app.get("/api/v1/missions/{mission_id}", response_model=MissionResponse)
    async def get_mission(mission_id: str):
        """Obtém status de uma missão."""
        status = await _mission_queue.get_status(mission_id)
        if not status:
            raise HTTPException(status_code=404, detail="Missão não encontrada")
        return {
            "mission_id": mission_id,
            "status": status["status"],
            "kernel_path": status.get("kernel_path", ""),
            "target_arch": status.get("target_arch", ""),
            "created_at": status["created_at"],
            "updated_at": status["updated_at"],
            "progress_pct": status.get("progress_pct", 0),
            "current_step": status.get("current_step"),
            "compilation_success": status.get("compilation_success"),
            "error_message": status.get("error_message"),
            "patch_url": status.get("patch_url"),
            "metrics": status.get("metrics", {}),
        }
    
    @app.get("/api/v1/missions/{mission_id}/patch")
    async def download_patch(mission_id: str):
        """Download do patch gerado."""
        status = await _mission_queue.get_status(mission_id)
        if not status:
            raise HTTPException(status_code=404, detail="Missão não encontrada")
        if status["status"] != MissionStatus.COMPLETED.value:
            raise HTTPException(status_code=400, detail="Missão ainda não concluída")
        return {"mission_id": mission_id, "patch": status.get("patch", "")}
    
    @app.delete("/api/v1/missions/{mission_id}")
    async def cancel_mission(mission_id: str):
        """Cancela uma missão."""
        status = await _mission_queue.get_status(mission_id)
        if not status:
            raise HTTPException(status_code=404, detail="Missão não encontrada")
        await _mission_queue.update_status(mission_id, MissionStatus.CANCELLED)
        return {"mission_id": mission_id, "status": "cancelled"}
    
    @app.get("/api/v1/missions", response_model=List[MissionResponse])
    async def list_missions(limit: int = 20, status_filter: Optional[str] = None):
        """Lista missões recentes."""
        result = []
        if _mission_queue:
            all_missions = await _mission_queue.list_active()
            if status_filter:
                all_missions = [m for m in all_missions if m.get("status") == status_filter]
            for m in all_missions[:limit]:
                result.append({
                    "mission_id": m["mission_id"],
                    "status": m["status"],
                    "kernel_path": m.get("kernel_path", ""),
                    "target_arch": m.get("target_arch", ""),
                    "created_at": m["created_at"],
                    "updated_at": m["updated_at"],
                    "progress_pct": m.get("progress_pct", 0),
                    "current_step": m.get("current_step"),
                    "compilation_success": m.get("compilation_success"),
                    "error_message": m.get("error_message"),
                })
        return result
    
    @app.get("/api/v1/agents", response_model=AgentsResponse)
    async def list_agents():
        """Lista agentes ativos no sistema."""
        agents = [
            AgentInfo(name="AgenteBase", type="core", status="active", missions_completed=0),
            AgentInfo(name="AgenteRefinador", type="refinement", status="active", missions_completed=0),
            AgentInfo(name="AgenteQuantico", type="exploration", status="idle", missions_completed=0),
            AgentInfo(name="AgenteKAN", type="learning", status="idle", missions_completed=0),
            AgentInfo(name="SelfHealingLoop", type="recovery", status="active", missions_completed=0),
            AgentInfo(name="AgenteAutoCorrecao", type="recovery", status="active", missions_completed=0),
        ]
        return AgentsResponse(agents=agents, total=len(agents))
    
    @app.get("/api/v1/metrics", response_model=MetricsResponse)
    async def get_metrics():
        """Métricas do sistema."""
        return MetricsResponse(
            total_missions=0,
            success_rate=0.0,
            avg_compilation_time_ms=0.0,
            avg_repair_time_ms=0.0,
            top_providers={},
            self_healing_rate=0.0,
            sandbox_executions=0,
        )
    
    @app.websocket("/api/v1/missions/{mission_id}/ws")
    async def mission_websocket(websocket: WebSocket, mission_id: str):
        """WebSocket para acompanhamento em tempo real."""
        await websocket.accept()
        _active_websockets[mission_id] = websocket
        
        try:
            # Envia status atual
            status = await _mission_queue.get_status(mission_id)
            if status:
                await websocket.send_json(status)
            
            # Mantém conexão e envia atualizações
            while True:
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                    if data == "ping":
                        await websocket.send_text("pong")
                except asyncio.TimeoutError:
                    # Verifica se há atualização de status
                    new_status = await _mission_queue.get_status(mission_id)
                    if new_status and new_status.get("status") in (
                        MissionStatus.COMPLETED.value,
                        MissionStatus.FAILED.value,
                        MissionStatus.CANCELLED.value,
                    ):
                        await websocket.send_json(new_status)
                        break
        except WebSocketDisconnect:
            pass
        finally:
            _active_websockets.pop(mission_id, None)
    
    return app


# Instância padrão para uvicorn
app = create_app()
