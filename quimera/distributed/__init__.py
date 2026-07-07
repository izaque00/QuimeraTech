"""
Quimera Mark X — Distributed Platform (Horizonte 1)

Multi-tenant, horizontally scalable code repair platform.

Modules:
    orchestrator      — Service discovery, worker pool, mission routing
    tenant_manager    — Multi-tenant isolation, quotas, rate limiting
    api_gateway       — REST + WebSocket API with auth
    scaler            — Auto-scaling worker pool
    run               — CLI entry point
"""

from .orchestrator import DistributedOrchestrator, WorkerInfo, WorkerStatus, MissionPriority
from .tenant_manager import TenantManager, TIERS
from .api_gateway import create_gateway
from .scaler import AutoScaler

__version__ = "2.2.1"
