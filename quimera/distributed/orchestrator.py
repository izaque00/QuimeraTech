"""
Quimera Mark X — Distributed Orchestrator (Horizonte 1)

Service discovery, worker pool management, and multi-tenant routing.

Architecture:
    ┌──────────────────────────────────────────────────┐
    │                 API Gateway                       │
    │  /api/v1/tenants/{tid}/missions/...              │
    └──────────────┬───────────────────────────────────┘
                   │
    ┌──────────────▼───────────────────────────────────┐
    │           Distributed Orchestrator                │
    │  ┌─────────┐  ┌──────────┐  ┌────────────────┐  │
    │  │ Tenant  │  │ Worker   │  │ Auto-Scaler    │  │
    │  │ Manager │  │ Pool     │  │                 │  │
    │  └─────────┘  └──────────┘  └────────────────┘  │
    └──────────────┬───────────────────────────────────┘
                   │
    ┌──────────────▼───────────────────────────────────┐
    │              Redis Cluster                        │
    │  ┌─────────┐  ┌──────────┐  ┌────────────────┐  │
    │  │ Queue   │  │ Pub/Sub  │  │ Service        │  │
    │  │ (lists) │  │ (chan)   │  │ Registry (HSET)│  │
    │  └─────────┘  └──────────┘  └────────────────┘  │
    └──────────────────────────────────────────────────┘

Usage:
    orchestrator = DistributedOrchestrator(redis_client)
    await orchestrator.start()
    
    # Submit a mission for a tenant
    mission_id = await orchestrator.submit_mission(tenant_id, mission_data)
    
    # Register a worker
    worker_id = await orchestrator.register_worker(worker_info)
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("quimera.distributed")


# ═══════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════

REDIS_PREFIX = "quimera:h1:"

# Keys
WORKER_REGISTRY = REDIS_PREFIX + "workers"           # HSET worker_id → info
WORKER_HEARTBEATS = REDIS_PREFIX + "worker:{}:hb"     # String TTL
TENANT_QUEUE_PREFIX = REDIS_PREFIX + "tenant:{}:queue"  # List
TENANT_ACTIVE = REDIS_PREFIX + "tenant:{}:active"    # Set
TENANT_QUOTA = REDIS_PREFIX + "tenant:{}:quota"      # Hash
SERVICE_REGISTRY = REDIS_PREFIX + "services"          # HSET
GLOBAL_QUEUE = REDIS_PREFIX + "global_queue"          # List
METRICS_PREFIX = REDIS_PREFIX + "metrics:"            # Prefix for time-series

# Timeouts (seconds)
WORKER_HEARTBEAT_TTL = 30
WORKER_CLEANUP_INTERVAL = 15
QUEUE_POLL_INTERVAL = 0.5
SCALER_CHECK_INTERVAL = 10


# ═══════════════════════════════════════════════════════════════════════════
# Data Structures
# ═══════════════════════════════════════════════════════════════════════════

class WorkerStatus(str, Enum):
    IDLE = "idle"
    BUSY = "busy"
    DRAINING = "draining"
    OFFLINE = "offline"


class MissionPriority(int, Enum):
    LOW = 0
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10


@dataclass
class WorkerInfo:
    worker_id: str = ""
    hostname: str = ""
    pid: int = 0
    status: WorkerStatus = WorkerStatus.IDLE
    capacity: int = 2                    # Max concurrent missions
    current_load: int = 0               # Active missions
    total_processed: int = 0
    total_success: int = 0
    supported_languages: List[str] = field(default_factory=lambda: ["c"])
    sandbox_available: bool = True
    version: str = "2.2.1"
    registered_at: str = ""
    last_heartbeat: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "worker_id": self.worker_id,
            "hostname": self.hostname,
            "pid": self.pid,
            "status": self.status.value,
            "capacity": self.capacity,
            "current_load": self.current_load,
            "total_processed": self.total_processed,
            "total_success": self.total_success,
            "supported_languages": self.supported_languages,
            "sandbox_available": self.sandbox_available,
            "version": self.version,
            "registered_at": self.registered_at,
            "last_heartbeat": self.last_heartbeat,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "WorkerInfo":
        return cls(
            worker_id=data.get("worker_id", ""),
            hostname=data.get("hostname", ""),
            pid=data.get("pid", 0),
            status=WorkerStatus(data.get("status", "idle")),
            capacity=data.get("capacity", 2),
            current_load=data.get("current_load", 0),
            total_processed=data.get("total_processed", 0),
            total_success=data.get("total_success", 0),
            supported_languages=data.get("supported_languages", ["c"]),
            sandbox_available=data.get("sandbox_available", True),
            version=data.get("version", "2.2.1"),
            registered_at=data.get("registered_at", ""),
            last_heartbeat=data.get("last_heartbeat", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TenantInfo:
    tenant_id: str = ""
    name: str = ""
    tier: str = "free"                  # free, pro, enterprise
    max_concurrent_missions: int = 2
    max_daily_missions: int = 50
    daily_missions_used: int = 0
    rate_limit_rpm: int = 60            # Requests per minute
    allowed_languages: List[str] = field(default_factory=lambda: ["c"])
    features: List[str] = field(default_factory=list)
    created_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════
# Distributed Orchestrator
# ═══════════════════════════════════════════════════════════════════════════

class DistributedOrchestrator:
    """Core orchestrator for the distributed Quimera platform.

    Responsibilities:
      - Worker registry & heartbeat monitoring
      - Multi-tenant mission routing
      - Global + per-tenant queue management
      - Auto-scaling signals
      - Metrics aggregation
    """

    def __init__(self, redis_client=None):
        self.redis = redis_client
        self._use_redis = redis_client is not None
        self._local_workers: Dict[str, WorkerInfo] = {}
        self._local_tenants: Dict[str, TenantInfo] = {}
        self._local_queue: List[Tuple[str, Dict]] = []  # (tenant_id, mission_data)
        self._running = False
        self._start_time = time.time()

        if self._use_redis:
            logger.info("DistributedOrchestrator: Redis mode — full cluster")
        else:
            logger.info("DistributedOrchestrator: Local mode — single instance")

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def start(self):
        self._running = True
        if self._use_redis:
            asyncio.create_task(self._cleanup_loop())
            asyncio.create_task(self._metrics_loop())
        logger.info("DistributedOrchestrator started")
        return self

    async def stop(self):
        self._running = False
        # Drain workers
        for wid in list(self._local_workers.keys()):
            await self._mark_worker_offline(wid)
        logger.info("DistributedOrchestrator stopped")

    # ── Worker Registry ────────────────────────────────────────────────

    async def register_worker(self, info: WorkerInfo) -> str:
        """Register a worker in the cluster."""
        if not info.worker_id:
            info.worker_id = f"worker-{uuid.uuid4().hex[:8]}"

        now = datetime.now(timezone.utc).isoformat()
        info.registered_at = info.registered_at or now
        info.last_heartbeat = now

        if self._use_redis:
            await self.redis.hset(WORKER_REGISTRY, info.worker_id, json.dumps(info.to_dict()))
            await self.redis.setex(WORKER_HEARTBEATS.format(info.worker_id), WORKER_HEARTBEAT_TTL, now)
        else:
            self._local_workers[info.worker_id] = info

        logger.info(f"Worker registered: {info.worker_id} ({info.hostname})")
        return info.worker_id

    async def heartbeat(self, worker_id: str, current_load: int = 0):
        """Update worker heartbeat and load."""
        now = datetime.now(timezone.utc).isoformat()

        if self._use_redis:
            await self.redis.setex(WORKER_HEARTBEATS.format(worker_id), WORKER_HEARTBEAT_TTL, now)
            raw = await self.redis.hget(WORKER_REGISTRY, worker_id)
            if raw:
                info = WorkerInfo.from_dict(json.loads(raw))
                info.last_heartbeat = now
                info.current_load = current_load
                info.status = WorkerStatus.BUSY if current_load >= info.capacity else WorkerStatus.IDLE
                await self.redis.hset(WORKER_REGISTRY, worker_id, json.dumps(info.to_dict()))
        else:
            if worker_id in self._local_workers:
                self._local_workers[worker_id].last_heartbeat = now
                self._local_workers[worker_id].current_load = current_load

    async def get_available_worker(self, language: str = "c") -> Optional[WorkerInfo]:
        """Find the best available worker for a mission."""
        if self._use_redis:
            raw_workers = await self.redis.hgetall(WORKER_REGISTRY)
            workers = [
                WorkerInfo.from_dict(json.loads(v))
                for v in (raw_workers.values() if raw_workers else [])
            ]
        else:
            workers = list(self._local_workers.values())

        # Filter: idle + supports language + sandbox available
        available = [
            w for w in workers
            if w.status == WorkerStatus.IDLE
            and language in w.supported_languages
            and w.sandbox_available
            and w.current_load < w.capacity
        ]

        if not available:
            return None

        # Select: least loaded first
        available.sort(key=lambda w: w.current_load)
        return available[0]

    async def list_workers(self) -> List[WorkerInfo]:
        if self._use_redis:
            raw = await self.redis.hgetall(WORKER_REGISTRY)
            return [WorkerInfo.from_dict(json.loads(v)) for v in (raw.values() if raw else [])]
        return list(self._local_workers.values())

    async def get_cluster_stats(self) -> Dict[str, Any]:
        workers = await self.list_workers()
        active = [w for w in workers if w.status != WorkerStatus.OFFLINE]
        return {
            "total_workers": len(workers),
            "active_workers": len(active),
            "idle_workers": len([w for w in active if w.status == WorkerStatus.IDLE]),
            "total_capacity": sum(w.capacity for w in active),
            "current_load": sum(w.current_load for w in active),
            "total_processed": sum(w.total_processed for w in active),
            "total_success": sum(w.total_success for w in active),
            "uptime_seconds": time.time() - self._start_time,
        }

    # ── Mission Submission ──────────────────────────────────────────────

    async def submit_mission(
        self, tenant_id: str, mission_data: Dict[str, Any],
        priority: MissionPriority = MissionPriority.NORMAL,
    ) -> str:
        """Submit a mission for a tenant. Routes to best worker or queues.

        Returns mission_id.
        """
        mission_id = f"qm-{uuid.uuid4().hex[:12]}"

        payload = {
            "mission_id": mission_id,
            "tenant_id": tenant_id,
            "priority": priority.value,
            "status": "queued",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **mission_data,
        }

        language = mission_data.get("language", "c")

        # Try direct dispatch to an available worker
        worker = await self.get_available_worker(language)

        if worker and priority == MissionPriority.CRITICAL:
            # Direct dispatch for critical missions
            if self._use_redis:
                worker_queue = REDIS_PREFIX + f"worker:{worker.worker_id}:queue"
                await self.redis.lpush(worker_queue, json.dumps(payload))
            else:
                self._local_queue.append((tenant_id, payload))
            logger.info(f"Mission {mission_id} dispatched directly to {worker.worker_id}")
        else:
            # Queue for tenant
            if self._use_redis:
                queue_key = TENANT_QUEUE_PREFIX.format(tenant_id)
                await self.redis.rpush(queue_key, json.dumps(payload))
                await self.redis.rpush(GLOBAL_QUEUE, json.dumps(payload))
            else:
                self._local_queue.append((tenant_id, payload))
            logger.info(f"Mission {mission_id} queued for tenant {tenant_id}")

        return mission_id

    async def get_next_mission(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """Get the next mission for a worker to process.

        Priority order: worker-specific queue → global queue
        """
        if self._use_redis:
            # Try worker-specific queue first
            worker_queue = REDIS_PREFIX + f"worker:{worker_id}:queue"
            raw = await self.redis.rpop(worker_queue)
            if not raw:
                raw = await self.redis.rpop(GLOBAL_QUEUE)
            return json.loads(raw) if raw else None
        else:
            if self._local_queue:
                _, mission = self._local_queue.pop(0)
                return mission
            return None

    async def update_mission_status(self, mission_id: str, status: str, **kwargs):
        """Update mission status with distributed notification."""
        update = {
            "mission_id": mission_id,
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **kwargs,
        }
        if self._use_redis:
            key = REDIS_PREFIX + f"mission:{mission_id}"
            await self.redis.set(key, json.dumps(update))
            await self.redis.publish(REDIS_PREFIX + "events", json.dumps(update))
        logger.debug(f"Mission {mission_id}: {status}")

    # ── Tenant Management ──────────────────────────────────────────────

    async def register_tenant(self, info: TenantInfo) -> str:
        if not info.tenant_id:
            info.tenant_id = f"tenant-{uuid.uuid4().hex[:8]}"
        info.created_at = datetime.now(timezone.utc).isoformat()

        if self._use_redis:
            key = REDIS_PREFIX + f"tenant:{info.tenant_id}"
            await self.redis.hset(key, mapping=info.__dict__)
        else:
            self._local_tenants[info.tenant_id] = info

        logger.info(f"Tenant registered: {info.tenant_id} ({info.name})")
        return info.tenant_id

    async def get_tenant(self, tenant_id: str) -> Optional[TenantInfo]:
        if self._use_redis:
            key = REDIS_PREFIX + f"tenant:{tenant_id}"
            raw = await self.redis.hgetall(key)
            return TenantInfo(**raw) if raw else None
        return self._local_tenants.get(tenant_id)

    async def get_tenant_queue_size(self, tenant_id: str) -> int:
        if self._use_redis:
            return await self.redis.llen(TENANT_QUEUE_PREFIX.format(tenant_id)) or 0
        return sum(1 for tid, _ in self._local_queue if tid == tenant_id)

    async def get_global_queue_size(self) -> int:
        if self._use_redis:
            return await self.redis.llen(GLOBAL_QUEUE) or 0
        return len(self._local_queue)

    # ── Internal ───────────────────────────────────────────────────────

    async def _cleanup_loop(self):
        """Periodically remove dead workers."""
        while self._running:
            try:
                if self._use_redis:
                    raw = await self.redis.hgetall(WORKER_REGISTRY)
                    for wid, data in (raw or {}).items():
                        hb = await self.redis.get(WORKER_HEARTBEATS.format(wid))
                        if not hb:
                            logger.warning(f"Worker {wid} heartbeat lost — marking offline")
                            await self._mark_worker_offline(wid)
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
            await asyncio.sleep(WORKER_CLEANUP_INTERVAL)

    async def _mark_worker_offline(self, worker_id: str):
        if self._use_redis:
            raw = await self.redis.hget(WORKER_REGISTRY, worker_id)
            if raw:
                info = WorkerInfo.from_dict(json.loads(raw))
                info.status = WorkerStatus.OFFLINE
                await self.redis.hset(WORKER_REGISTRY, worker_id, json.dumps(info.to_dict()))

    async def _metrics_loop(self):
        """Aggregate and publish cluster metrics."""
        while self._running:
            try:
                stats = await self.get_cluster_stats()
                if self._use_redis:
                    await self.redis.setex(
                        REDIS_PREFIX + "metrics:latest",
                        60,
                        json.dumps(stats),
                    )
            except Exception as e:
                logger.error(f"Metrics error: {e}")
            await asyncio.sleep(SCALER_CHECK_INTERVAL)

    async def run_worker(
        self, worker_id: str, process_fn, capacity: int = 2, poll_interval: float = 1.0
    ):
        """Run a worker loop on this process.

        Args:
            worker_id: Worker identifier
            process_fn: Async function(mission_data) → result
            capacity: Max concurrent missions
            poll_interval: Seconds between queue polls
        """
        # Register
        import os
        info = WorkerInfo(
            worker_id=worker_id,
            hostname=os.uname().nodename,
            pid=os.getpid(),
            capacity=capacity,
        )
        await self.register_worker(info)

        active_tasks: Dict[str, asyncio.Task] = {}

        while self._running:
            # Clean completed tasks
            active_tasks = {mid: t for mid, t in active_tasks.items() if not t.done()}

            # Heartbeat
            await self.heartbeat(worker_id, current_load=len(active_tasks))

            # Pick up work if capacity available
            if len(active_tasks) < capacity:
                mission = await self.get_next_mission(worker_id)
                if mission:
                    mid = mission["mission_id"]
                    task = asyncio.create_task(self._execute_mission(mid, mission, process_fn))
                    active_tasks[mid] = task
                    logger.info(f"Worker {worker_id}: executing {mid} ({len(active_tasks)}/{capacity})")

            await asyncio.sleep(poll_interval)

    async def _execute_mission(self, mission_id: str, mission: Dict, process_fn):
        try:
            await self.update_mission_status(mission_id, "running")
            result = await process_fn(mission)
            await self.update_mission_status(mission_id, "completed", **result)
            return result
        except Exception as e:
            logger.error(f"Mission {mission_id} failed: {e}", exc_info=True)
            await self.update_mission_status(mission_id, "failed", error=str(e))
            return {"error": str(e)}
