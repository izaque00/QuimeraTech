# quimera/api/schemas.py
"""
Modelos Pydantic para validação de requests/responses da API.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MissionStatus(str, Enum):
    """Status de uma missão."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPILING = "compiling"
    TESTING = "testing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MissionCreate(BaseModel):
    """Request para criar missão."""
    kernel_path: str = Field(..., description="Caminho do kernel source")
    target_arch: str = Field(default="aarch64", description="Arquitetura alvo")
    optimization: str = Field(default="default", description="Nível de otimização")
    max_iterations: int = Field(default=10, ge=1, le=100)
    llm_provider: Optional[str] = Field(default=None, description="Provedor LLM preferido")
    priority: int = Field(default=0, ge=0, le=10, description="Prioridade (0=baixa, 10=urgente)")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MissionResponse(BaseModel):
    """Response com dados da missão."""
    mission_id: str
    status: MissionStatus
    kernel_path: str
    target_arch: str
    created_at: datetime
    updated_at: datetime
    progress_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    current_step: Optional[str] = None
    compilation_success: Optional[bool] = None
    error_message: Optional[str] = None
    patch_url: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    """Health check."""
    status: str = "healthy"
    version: str
    uptime_seconds: float
    active_missions: int
    total_missions: int
    sandbox_available: bool
    redis_connected: bool
    db_connected: bool
    agents_loaded: int


class AgentInfo(BaseModel):
    """Informações de um agente."""
    name: str
    type: str
    status: str
    current_mission: Optional[str] = None
    missions_completed: int = 0


class AgentsResponse(BaseModel):
    """Lista de agentes."""
    agents: List[AgentInfo]
    total: int


class MetricsResponse(BaseModel):
    """Métricas do sistema."""
    total_missions: int
    success_rate: float
    avg_compilation_time_ms: float
    avg_repair_time_ms: float
    top_providers: Dict[str, float]
    self_healing_rate: float
    sandbox_executions: int
