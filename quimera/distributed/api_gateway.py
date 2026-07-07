"""
Quimera Mark X — API Gateway (Horizonte 1)

Multi-tenant API Gateway with authentication, rate limiting,
and mission routing through the distributed orchestrator.

Expands the existing FastAPI server with:
  - Per-tenant endpoints: /api/v1/tenants/{tid}/...
  - API key authentication
  - Rate limit headers
  - Tenant-aware mission submission
  - WebSocket for real-time cluster status

Usage:
    uvicorn quimera.api.api_gateway:app --host 0.0.0.0 --port 8000
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger("quimera.gateway")

_start_time = time.time()

# These will be injected at startup
_orchestrator = None
_tenant_manager = None


# ═══════════════════════════════════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════════════════════════════════

class TenantCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    tier: str = Field(default="free")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TenantResponse(BaseModel):
    tenant_id: str
    name: str
    tier: str
    status: str
    created_at: str
    features: List[str] = []
    usage: Dict[str, Any] = {}


class MissionSubmit(BaseModel):
    kernel_path: str = Field(..., description="Path to kernel source or code")
    language: str = Field(default="c")
    target_arch: str = Field(default="aarch64")
    original_code: Optional[str] = None
    error_context: Optional[str] = None
    priority: int = Field(default=5, ge=0, le=10)
    max_attempts: int = Field(default=3, ge=1, le=20)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MissionResponse(BaseModel):
    mission_id: str
    tenant_id: str
    status: str
    language: str
    created_at: str
    updated_at: str
    progress_pct: float = 0.0


class ClusterStats(BaseModel):
    total_workers: int
    active_workers: int
    idle_workers: int
    total_capacity: int
    current_load: int
    total_tenants: int
    active_missions: int
    queue_size: int
    uptime_seconds: float
    redis_connected: bool


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "2.2.1"
    uptime_seconds: float
    redis_connected: bool
    db_connected: bool
    workers_registered: int


# ═══════════════════════════════════════════════════════════════════════════
# Auth Middleware
# ═══════════════════════════════════════════════════════════════════════════

async def authenticate_tenant(
    request: Request,
    x_api_key: Optional[str] = Header(None),
    x_tenant_id: Optional[str] = Header(None),
) -> str:
    """Extract and validate tenant identity.
    
    Supports:
      - API Key header: X-API-Key
      - Tenant ID header: X-Tenant-ID (for dev/testing)
    """
    if x_tenant_id:
        tenant = await _tenant_manager.get_tenant(x_tenant_id)
        if tenant and tenant.get("status") == "active":
            return x_tenant_id

    if x_api_key:
        # Simple API key → tenant_id mapping (production uses JWT/OAuth)
        tenant_id = x_api_key.replace("qk_", "").split("_")[0] if x_api_key.startswith("qk_") else x_api_key
        tenant = await _tenant_manager.get_tenant(tenant_id)
        if tenant and tenant.get("status") == "active":
            return tenant_id

    raise HTTPException(status_code=401, detail="Invalid or missing credentials")


async def check_tenant_access(
    request: Request,
    tenant_id: str = Depends(authenticate_tenant),
) -> str:
    """Check tenant has access and is within rate limits."""
    # Rate limit check
    ok, msg = await _tenant_manager.check_rate_limit(tenant_id)
    if not ok:
        raise HTTPException(status_code=429, detail=msg)
    return tenant_id


# ═══════════════════════════════════════════════════════════════════════════
# Gateway Application
# ═══════════════════════════════════════════════════════════════════════════

def create_gateway(orchestrator, tenant_manager) -> FastAPI:
    """Create the API Gateway application."""
    global _orchestrator, _tenant_manager
    _orchestrator = orchestrator
    _tenant_manager = tenant_manager

    app = FastAPI(
        title="Quimera Mark X — API Gateway",
        version="2.2.1",
        description="Multi-tenant distributed code repair platform",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Global Endpoints ───────────────────────────────────────────

    @app.get("/api/v1/health", response_model=HealthResponse)
    async def health():
        workers = await _orchestrator.list_workers()
        return HealthResponse(
            uptime_seconds=time.time() - _start_time,
            redis_connected=_orchestrator._use_redis,
            db_connected=True,
            workers_registered=len(workers),
        )

    @app.get("/api/v1/cluster", response_model=ClusterStats)
    async def cluster_stats():
        worker_stats = await _orchestrator.get_cluster_stats()
        tenant_stats = await _tenant_manager.get_cluster_tenant_stats()
        return ClusterStats(
            total_workers=worker_stats["total_workers"],
            active_workers=worker_stats["active_workers"],
            idle_workers=worker_stats["idle_workers"],
            total_capacity=worker_stats["total_capacity"],
            current_load=worker_stats["current_load"],
            total_tenants=tenant_stats["total_tenants"],
            active_missions=tenant_stats["total_active_missions"],
            queue_size=await _orchestrator.get_global_queue_size(),
            uptime_seconds=time.time() - _start_time,
            redis_connected=_orchestrator._use_redis,
        )

    @app.get("/api/v1/workers")
    async def list_workers():
        workers = await _orchestrator.list_workers()
        return {"workers": [w.to_dict() for w in workers], "total": len(workers)}

    # ── Tenant Management ───────────────────────────────────────────

    @app.post("/api/v1/tenants", response_model=TenantResponse, status_code=201)
    async def create_tenant(body: TenantCreate):
        tid = await _tenant_manager.create_tenant(
            name=body.name, tier=body.tier, metadata=body.metadata
        )
        tenant = await _tenant_manager.get_tenant(tid)
        usage = await _tenant_manager.get_tenant_usage(tid)
        return TenantResponse(
            tenant_id=tid,
            name=tenant["name"],
            tier=tenant["tier"],
            status=tenant["status"],
            created_at=tenant["created_at"],
            features=tenant.get("features", []),
            usage=usage,
        )

    @app.get("/api/v1/tenants")
    async def list_tenants():
        tenants = await _tenant_manager.list_tenants()
        return {"tenants": tenants, "total": len(tenants)}

    # ── Per-Tenant Mission Endpoints ────────────────────────────────

    @app.post(
        "/api/v1/tenants/{tenant_id}/missions",
        response_model=MissionResponse,
        status_code=201,
    )
    async def submit_mission(
        tenant_id: str,
        body: MissionSubmit,
        _: str = Depends(check_tenant_access),
    ):
        """Submit a mission for a specific tenant."""
        # Full validation
        ok, msg = await _tenant_manager.can_submit_mission(tenant_id, body.language)
        if not ok:
            raise HTTPException(status_code=429 if "limit" in msg.lower() or "rate" in msg.lower() else 403, detail=msg)

        # Get tenant for priority boost
        tenant = await _tenant_manager.get_tenant(tenant_id)
        priority_boost = tenant.get("priority_boost", 0) if tenant else 0

        mission_data = body.model_dump()
        mission_data["tenant_id"] = tenant_id

        from quimera.distributed.orchestrator import MissionPriority
        priority = MissionPriority(min(10, body.priority + priority_boost))

        mission_id = await _orchestrator.submit_mission(tenant_id, mission_data, priority=priority)
        await _tenant_manager.mission_started(tenant_id)

        return MissionResponse(
            mission_id=mission_id,
            tenant_id=tenant_id,
            status="queued",
            language=body.language,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

    @app.get("/api/v1/tenants/{tenant_id}/missions/{mission_id}")
    async def get_mission(tenant_id: str, mission_id: str):
        """Get mission status."""
        # Status stored in orchestrator
        if _orchestrator._use_redis:
            import json
            key = f"quimera:h1:mission:{mission_id}"
            raw = await _orchestrator.redis.get(key)
            if raw:
                data = json.loads(raw)
                if data.get("tenant_id") == tenant_id:
                    return data
        raise HTTPException(status_code=404, detail="Mission not found")

    @app.get("/api/v1/tenants/{tenant_id}/missions")
    async def list_tenant_missions(tenant_id: str, limit: int = 20):
        """List recent missions for a tenant from the orchestrator queue."""
        try:
            missions = await _orchestrator.list_missions(tenant_id, limit=limit)
            return {"missions": missions, "total": len(missions)}
        except AttributeError:
            # Orchestrator doesn't support mission listing yet — query DB
            try:
                from quimera.db.service import get_missions_by_tenant
                records = await get_missions_by_tenant(tenant_id, limit=limit)
                return {"missions": records, "total": len(records)}
            except Exception:
                return {"missions": [], "total": 0, "note": "Mission persistence layer not available"}

    @app.get("/api/v1/tenants/{tenant_id}/usage")
    async def tenant_usage(tenant_id: str):
        return await _tenant_manager.get_tenant_usage(tenant_id)

    @app.post("/api/v1/tenants/{tenant_id}/upgrade")
    async def upgrade_tenant(tenant_id: str, tier: str = "pro"):
        if tier not in ("pro", "enterprise"):
            raise HTTPException(status_code=400, detail="Invalid tier")
        await _tenant_manager.update_tier(tenant_id, tier)
        tenant = await _tenant_manager.get_tenant(tenant_id)
        return {"tenant_id": tenant_id, "tier": tenant["tier"], "status": "upgraded"}

    # ── WebSocket: Cluster Events ───────────────────────────────────

    @app.websocket("/api/v1/ws/cluster")
    async def cluster_websocket(websocket: WebSocket):
        await websocket.accept()
        try:
            while True:
                stats = await _orchestrator.get_cluster_stats()
                tenant_stats = await _tenant_manager.get_cluster_tenant_stats()
                await websocket.send_json({
                    "type": "cluster_stats",
                    "workers": stats,
                    "tenants": tenant_stats,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                await asyncio.sleep(5)
        except WebSocketDisconnect:
            pass

    # ── Error Handlers ──────────────────────────────────────────────

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail, "status_code": exc.status_code},
        )

    return app


# Default instance
app = create_gateway(None, None)
