"""
Quimera Observability — Audit Trail, Resource Metrics, Health Dashboard.

Fase 4: Estende structured_logger com:
  - AuditTrail: registro imutável de ações críticas
  - ResourceMetrics: CPU, memória, tempo de execução
  - HealthCheck: verificação de saúde dos módulos
  - TraceExporter: exporta traces para análise
"""
import json
import logging
import os
import sys
import time
import uuid
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import psutil

logger = logging.getLogger("quimera.observability")


# ═══════════════════════════════════════════════════════════════════════════
# Audit Trail — Registro imutável de ações críticas
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class AuditEntry:
    """Uma entrada no audit trail."""
    id: str
    timestamp: str
    actor: str           # agente, módulo, ou "system"
    action: str          # "pipeline.start", "patch.applied", "agent.registered"
    resource: str        # path, mission_id, agent name
    outcome: str         # "success", "failure", "pending"
    details: Dict[str, Any] = field(default_factory=dict)
    trace_id: str = ""


class AuditTrail:
    """Registro imutável e append-only de ações críticas do sistema.
    
    Cada ação que modifica estado (patch aplicado, agente registrado,
    pipeline executado) é registrada com timestamp, ator, e trace_id.
    
    Uso:
        audit = AuditTrail()
        audit.record(
            actor="Pipeline",
            action="patch.applied",
            resource="mission-123",
            outcome="success",
            details={"patch_id": "patch_aarch64_abc123", "fitness": 0.85},
        )
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path) if storage_path else Path("logs/audit_trail.jsonl")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._buffer: List[AuditEntry] = []
        self._total_entries = 0
        self._load_existing()
    
    def _load_existing(self):
        if self.storage_path.exists():
            with open(self.storage_path) as f:
                self._total_entries = sum(1 for _ in f)
    
    def record(
        self,
        actor: str,
        action: str,
        resource: str = "",
        outcome: str = "success",
        details: Optional[Dict] = None,
        trace_id: str = "",
    ) -> str:
        """Registra uma ação no audit trail. Retorna o entry_id."""
        entry = AuditEntry(
            id=str(uuid.uuid4())[:12],
            timestamp=datetime.now(timezone.utc).isoformat(),
            actor=actor,
            action=action,
            resource=resource,
            outcome=outcome,
            details=details or {},
            trace_id=trace_id,
        )
        self._buffer.append(entry)
        self._total_entries += 1
        
        # Flush se buffer >= 100
        if len(self._buffer) >= 100:
            self.flush()
        
        return entry.id
    
    def flush(self):
        """Persiste o buffer no disco (append-only JSONL)."""
        if not self._buffer:
            return
        with open(self.storage_path, 'a') as f:
            for entry in self._buffer:
                f.write(json.dumps({
                    "id": entry.id,
                    "ts": entry.timestamp,
                    "actor": entry.actor,
                    "action": entry.action,
                    "resource": entry.resource,
                    "outcome": entry.outcome,
                    "details": entry.details,
                    "trace_id": entry.trace_id,
                }, default=str) + '\n')
        self._buffer.clear()
    
    def query(
        self,
        actor: Optional[str] = None,
        action: Optional[str] = None,
        outcome: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """Consulta o audit trail com filtros."""
        results = []
        if not self.storage_path.exists():
            return results
        
        with open(self.storage_path) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if actor and entry.get("actor") != actor:
                        continue
                    if action and entry.get("action") != action:
                        continue
                    if outcome and entry.get("outcome") != outcome:
                        continue
                    if since and entry.get("ts", "") < since:
                        continue
                    results.append(entry)
                    if len(results) >= limit:
                        break
                except json.JSONDecodeError:
                    continue
        
        # Include buffer
        for entry in self._buffer:
            entry_dict = {
                "id": entry.id, "ts": entry.timestamp, "actor": entry.actor,
                "action": entry.action, "resource": entry.resource,
                "outcome": entry.outcome, "details": entry.details,
                "trace_id": entry.trace_id,
            }
            if actor and entry_dict["actor"] != actor:
                continue
            if action and entry_dict["action"] != action:
                continue
            if outcome and entry_dict["outcome"] != outcome:
                continue
            results.append(entry_dict)
        
        return results[-limit:]
    
    def get_stats(self) -> Dict:
        """Estatísticas do audit trail."""
        outcomes = defaultdict(int)
        actions = defaultdict(int)
        
        if self.storage_path.exists():
            with open(self.storage_path) as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        outcomes[entry.get("outcome", "?")] += 1
                        actions[entry.get("action", "?")] += 1
                    except json.JSONDecodeError:
                        continue
        
        return {
            "total_entries": self._total_entries,
            "outcomes": dict(outcomes),
            "top_actions": dict(sorted(actions.items(), key=lambda x: -x[1])[:10]),
            "success_rate": f"{outcomes.get('success', 0) / max(self._total_entries, 1):.1%}",
        }


# ═══════════════════════════════════════════════════════════════════════════
# Resource Metrics — CPU, memória, tempo
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ResourceSnapshot:
    """Snapshot de recursos do sistema."""
    timestamp: str
    cpu_percent: float
    memory_rss_mb: float
    memory_vms_mb: float
    open_fds: int
    thread_count: int
    uptime_seconds: float


class ResourceMonitor:
    """Monitora uso de recursos do processo Quimera.
    
    Uso:
        monitor = ResourceMonitor()
        monitor.start()
        # ... executa pipeline ...
        snapshot = monitor.snapshot()
        print(f"CPU: {snapshot.cpu_percent}%, Memory: {snapshot.memory_rss_mb:.0f}MB")
        monitor.stop()
    """
    
    def __init__(self, sample_interval: float = 1.0):
        self.sample_interval = sample_interval
        self._start_time: Optional[float] = None
        self._snapshots: List[ResourceSnapshot] = []
        self._running = False
        self._process = psutil.Process(os.getpid())
    
    @property
    def uptime_seconds(self) -> float:
        if self._start_time is None:
            return 0.0
        return time.monotonic() - self._start_time
    
    def start(self):
        """Inicia o monitoramento."""
        self._start_time = time.monotonic()
        self._running = True
        logger.info("ResourceMonitor: started")
    
    def stop(self):
        """Para o monitoramento."""
        self._running = False
        self.flush()
        logger.info(f"ResourceMonitor: stopped ({len(self._snapshots)} snapshots)")
    
    def snapshot(self) -> ResourceSnapshot:
        """Captura um snapshot de recursos."""
        mem = self._process.memory_info()
        snap = ResourceSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            cpu_percent=self._process.cpu_percent(interval=0.1),
            memory_rss_mb=mem.rss / (1024 * 1024),
            memory_vms_mb=mem.vms / (1024 * 1024),
            open_fds=self._process.num_fds() if hasattr(self._process, 'num_fds') else -1,
            thread_count=self._process.num_threads(),
            uptime_seconds=self.uptime_seconds,
        )
        self._snapshots.append(snap)
        return snap
    
    def get_summary(self) -> Dict[str, Any]:
        """Resumo das métricas de recursos."""
        if not self._snapshots:
            return {"status": "no_data"}
        
        cpu_values = [s.cpu_percent for s in self._snapshots]
        mem_values = [s.memory_rss_mb for s in self._snapshots]
        
        return {
            "samples": len(self._snapshots),
            "uptime_seconds": self.uptime_seconds,
            "cpu": {
                "current": cpu_values[-1] if cpu_values else 0,
                "avg": sum(cpu_values) / len(cpu_values),
                "max": max(cpu_values),
                "min": min(cpu_values),
            },
            "memory_rss_mb": {
                "current": mem_values[-1] if mem_values else 0,
                "avg": sum(mem_values) / len(mem_values),
                "max": max(mem_values),
                "min": min(mem_values),
            },
            "threads": self._snapshots[-1].thread_count if self._snapshots else 0,
        }
    
    def flush(self):
        """Exporta snapshots para JSON."""
        export_path = Path("logs/resource_metrics.jsonl")
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with open(export_path, 'a') as f:
            for snap in self._snapshots:
                f.write(json.dumps({
                    "ts": snap.timestamp,
                    "cpu_pct": snap.cpu_percent,
                    "mem_rss_mb": round(snap.memory_rss_mb, 1),
                    "mem_vms_mb": round(snap.memory_vms_mb, 1),
                    "fds": snap.open_fds,
                    "threads": snap.thread_count,
                    "uptime_s": round(snap.uptime_seconds, 1),
                }) + '\n')
        self._snapshots.clear()
    
    @contextmanager
    def profile(self, label: str = ""):
        """Context manager para medir recursos de um bloco."""
        before = self.snapshot()
        t0 = time.monotonic()
        try:
            yield
        finally:
            elapsed = time.monotonic() - t0
            after = self.snapshot()
            logger.debug(
                f"Profile [{label}]: {elapsed*1000:.0f}ms, "
                f"CPU {after.cpu_percent - before.cpu_percent:+.1f}%, "
                f"Mem {after.memory_rss_mb - before.memory_rss_mb:+.1f}MB"
            )


# ═══════════════════════════════════════════════════════════════════════════
# Trace Exporter — Exporta traces para análise
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TraceSpan:
    """Um span de trace."""
    span_id: str
    parent_id: str
    name: str
    start_ts: str
    end_ts: str
    duration_ms: float
    status: str  # "ok", "error"
    error: str
    attributes: Dict[str, Any]


class TraceCollector:
    """Coleta spans de trace e exporta para análise.
    
    Uso:
        collector = TraceCollector()
        
        with collector.trace("pipeline.execute", mission_id="123") as span:
            with collector.trace("h4.evolve", parent=span) as child:
                # ... executa ...
                pass
    """
    
    def __init__(self):
        self._spans: List[TraceSpan] = []
        self._active_spans: Dict[str, TraceSpan] = {}
    
    @contextmanager
    def trace(self, name: str, parent: Optional["TraceSpan"] = None, **attrs):
        """Cria um span de trace."""
        span_id = str(uuid.uuid4())[:8]
        parent_id = parent.span_id if parent else ""
        t0 = time.monotonic()
        
        span = TraceSpan(
            span_id=span_id,
            parent_id=parent_id,
            name=name,
            start_ts=datetime.now(timezone.utc).isoformat(),
            end_ts="",
            duration_ms=0,
            status="ok",
            error="",
            attributes=attrs,
        )
        
        try:
            yield span
        except Exception as e:
            span.status = "error"
            span.error = str(e)
            raise
        finally:
            span.end_ts = datetime.now(timezone.utc).isoformat()
            span.duration_ms = (time.monotonic() - t0) * 1000
            self._spans.append(span)
    
    def get_trace_tree(self) -> List[Dict]:
        """Retorna a árvore de spans hierárquica."""
        spans_by_id = {s.span_id: s for s in self._spans}
        roots = [s for s in self._spans if not s.parent_id]
        
        def build_tree(span):
            children = [build_tree(s) for s in self._spans if s.parent_id == span.span_id]
            node = {
                "id": span.span_id,
                "name": span.name,
                "duration_ms": round(span.duration_ms, 1),
                "status": span.status,
                "error": span.error,
                "attrs": span.attributes,
            }
            if children:
                node["children"] = children
            return node
        
        return [build_tree(root) for root in roots]
    
    def get_summary(self) -> Dict:
        """Resumo dos spans."""
        if not self._spans:
            return {"total_spans": 0}
        
        durations = [s.duration_ms for s in self._spans]
        errors = [s for s in self._spans if s.status == "error"]
        
        return {
            "total_spans": len(self._spans),
            "total_duration_ms": round(sum(durations), 1),
            "avg_span_ms": round(sum(durations) / len(durations), 1),
            "max_span_ms": round(max(durations), 1),
            "error_spans": len(errors),
            "error_rate": f"{len(errors) / len(self._spans):.1%}",
        }
    
    def export_json(self, path: str = "logs/trace.json"):
        """Exporta todos os spans para JSON."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump({
                "trace_tree": self.get_trace_tree(),
                "summary": self.get_summary(),
                "exported_at": datetime.now(timezone.utc).isoformat(),
            }, f, indent=2, default=str)
    
    def flush(self):
        """Limpa os spans coletados."""
        self._spans.clear()
        self._active_spans.clear()


# ═══════════════════════════════════════════════════════════════════════════
# Health Check — Verificação de saúde do sistema
# ═══════════════════════════════════════════════════════════════════════════

class HealthChecker:
    """Verifica a saúde de todos os módulos do Quimera.
    
    Uso:
        checker = HealthChecker()
        report = checker.check_all()
        print(report.status)  # "healthy", "degraded", "unhealthy"
    """
    
    CHECKS = {
        "database": lambda: HealthChecker._check_import("quimera.db.base"),
        "memory": lambda: HealthChecker._check_import("quimera.memory.memory_engine"),
        "router": lambda: HealthChecker._check_import("quimera.core.model_router"),
        "sandbox": lambda: HealthChecker._check_import("quimera.sandbox.manager"),
        "pipeline": lambda: HealthChecker._check_import("quimera.pipeline"),
        "agents": lambda: HealthChecker._check_import("quimera.mind.agent_registry"),
        "plugins": lambda: HealthChecker._check_import("quimera.plugins.plugin_manager"),
    }
    
    @staticmethod
    def _check_import(module_path: str) -> Tuple[bool, str]:
        try:
            __import__(module_path)
            return True, "ok"
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def _check_memory() -> Tuple[bool, str]:
        try:
            mem = psutil.virtual_memory()
            if mem.percent > 90:
                return False, f"Memory critical: {mem.percent:.1f}%"
            elif mem.percent > 75:
                return True, f"Memory high: {mem.percent:.1f}%"
            return True, f"Memory ok: {mem.percent:.1f}%"
        except Exception as e:
            return False, str(e)
    
    @classmethod
    def check_all(cls) -> Dict[str, Any]:
        """Executa todos os health checks."""
        results = {}
        
        for name, check_fn in cls.CHECKS.items():
            ok, detail = check_fn()
            results[name] = {"healthy": ok, "detail": detail}
        
        # System checks
        mem_ok, mem_detail = cls._check_memory()
        results["system_memory"] = {"healthy": mem_ok, "detail": mem_detail}
        
        healthy_count = sum(1 for v in results.values() if v["healthy"])
        total = len(results)
        
        if healthy_count == total:
            status = "healthy"
        elif healthy_count >= total - 2:
            status = "degraded"
        else:
            status = "unhealthy"
        
        return {
            "status": status,
            "healthy": healthy_count,
            "total": total,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "modules": results,
        }
    
    @classmethod
    def check_one(cls, module: str) -> Dict[str, Any]:
        """Verifica um módulo específico."""
        if module in cls.CHECKS:
            ok, detail = cls.CHECKS[module]()
            return {"module": module, "healthy": ok, "detail": detail}
        return {"module": module, "healthy": False, "detail": "unknown module"}


# ═══════════════════════════════════════════════════════════════════════════
# Global instances
# ═══════════════════════════════════════════════════════════════════════════

audit_trail = AuditTrail()
resource_monitor = ResourceMonitor()
trace_collector = TraceCollector()
health_checker = HealthChecker()
