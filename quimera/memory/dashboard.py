"""
Quimera Mark X — Memory Dashboard (Horizonte 2)

Real-time metrics and visualization for the long-term memory system.
Provides:
    - Memory hit rate over time
    - Top solution domains
    - Cache efficiency stats
    - Federated contributions
    - Privacy budget tracking
    - Per-tenant memory usage

Usage:
    dashboard = MemoryDashboard(memory_pipeline)
    stats = await dashboard.get_full_report()
"""

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Deque, Dict, List, Optional

import logging
logger = logging.getLogger("quimera.memory.dashboard")


@dataclass
class TimeSeriesPoint:
    timestamp: str
    value: float
    label: str = ""


class MemoryDashboard:
    """Real-time dashboard for memory system metrics."""

    def __init__(
        self,
        memory_pipeline=None,     # MemoryPipeline
        max_history: int = 1000,  # Max time-series points
    ):
        self.pipeline = memory_pipeline
        self.max_history = max_history

        # Time-series data
        self._hit_rate_history: Deque[TimeSeriesPoint] = deque(maxlen=max_history)
        self._retrieval_latency: Deque[TimeSeriesPoint] = deque(maxlen=max_history)
        self._cache_size_history: Deque[TimeSeriesPoint] = deque(maxlen=max_history)
        self._total_contributions: Deque[TimeSeriesPoint] = deque(maxlen=max_history)

        # Aggregations
        self._domain_counts: Dict[str, int] = defaultdict(int)
        self._tenant_usage: Dict[str, Dict[str, Any]] = {}
        self._start_time = time.time()

        logger.info(f"MemoryDashboard: initialized (max_history={max_history})")

    # ── Recording ───────────────────────────────────────────────────────

    async def record_retrieval(
        self,
        candidates_found: int,
        memory_hit: bool,
        latency_ms: float,
        domain: str = "general",
        tenant_id: Optional[str] = None,
    ):
        """Record a memory retrieval event."""
        now = datetime.now(timezone.utc).isoformat()

        # Hit rate (boolean → 1/0)
        self._hit_rate_history.append(TimeSeriesPoint(
            timestamp=now, value=1.0 if memory_hit else 0.0,
            label="hit" if memory_hit else "miss",
        ))

        # Latency
        self._retrieval_latency.append(TimeSeriesPoint(
            timestamp=now, value=latency_ms,
        ))

        # Domain stats
        self._domain_counts[domain] += 1

        # Tenant usage
        if tenant_id:
            if tenant_id not in self._tenant_usage:
                self._tenant_usage[tenant_id] = {
                    "total_retrievals": 0,
                    "total_hits": 0,
                    "domains": defaultdict(int),
                }
            self._tenant_usage[tenant_id]["total_retrievals"] += 1
            if memory_hit:
                self._tenant_usage[tenant_id]["total_hits"] += 1
            self._tenant_usage[tenant_id]["domains"][domain] += 1

    async def record_cache_stats(self, cache_size: int, hit_rate: float):
        """Record cache snapshot."""
        self._cache_size_history.append(TimeSeriesPoint(
            timestamp=datetime.now(timezone.utc).isoformat(),
            value=cache_size,
            label=f"hit_rate={hit_rate:.1%}",
        ))

    async def record_federated_contribution(self, domain: str):
        """Record a federated knowledge contribution."""
        self._total_contributions.append(TimeSeriesPoint(
            timestamp=datetime.now(timezone.utc).isoformat(),
            value=1.0,
            label=domain,
        ))

    # ── Reports ─────────────────────────────────────────────────────────

    async def get_full_report(self) -> Dict[str, Any]:
        """Get comprehensive memory dashboard report."""
        # Pipeline stats
        pipeline_stats = {}
        if self.pipeline:
            try:
                pipeline_stats = await self.pipeline.get_memory_stats()
            except Exception as e:
                pipeline_stats = {"error": str(e)}

        # Current hit rate (last 100 retrievals)
        recent_hits = list(self._hit_rate_history)[-100:]
        current_hit_rate = (
            sum(p.value for p in recent_hits) / len(recent_hits)
            if recent_hits else 0.0
        )

        # Domain distribution
        total_domain = sum(self._domain_counts.values())
        domain_distribution = {
            d: {
                "count": c,
                "pct": f"{c / max(total_domain, 1):.1%}",
            }
            for d, c in sorted(
                self._domain_counts.items(), key=lambda x: x[1], reverse=True
            )[:10]
        }

        # Avg latency
        recent_latency = [p.value for p in self._retrieval_latency][-100:]
        avg_latency_ms = sum(recent_latency) / len(recent_latency) if recent_latency else 0

        # Tenant summary
        tenant_summary = []
        for tid, usage in self._tenant_usage.items():
            tenant_summary.append({
                "tenant_id": tid,
                "total_retrievals": usage["total_retrievals"],
                "total_hits": usage["total_hits"],
                "hit_rate": (
                    f"{usage['total_hits'] / max(usage['total_retrievals'], 1):.1%}"
                ),
                "top_domains": dict(
                    sorted(usage["domains"].items(), key=lambda x: x[1], reverse=True)[:5]
                ),
            })

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": time.time() - self._start_time,
            "pipeline": pipeline_stats,
            "current_hit_rate": round(current_hit_rate, 4),
            "avg_retrieval_latency_ms": round(avg_latency_ms, 1),
            "total_retrievals": len(self._hit_rate_history),
            "total_federated_contributions": len(self._total_contributions),
            "domain_distribution": domain_distribution,
            "tenants": tenant_summary,
            "time_series": {
                "hit_rate": [
                    {"t": p.timestamp, "v": p.value, "l": p.label}
                    for p in list(self._hit_rate_history)[-50:]
                ],
                "latency_ms": [
                    {"t": p.timestamp, "v": p.value}
                    for p in list(self._retrieval_latency)[-50:]
                ],
                "cache_size": [
                    {"t": p.timestamp, "v": p.value}
                    for p in list(self._cache_size_history)[-50:]
                ],
            },
        }

    async def get_quick_stats(self) -> Dict[str, Any]:
        """Get quick summary stats."""
        recent = list(self._hit_rate_history)[-100:]
        hit_rate = sum(p.value for p in recent) / max(len(recent), 1)

        return {
            "hit_rate": f"{hit_rate:.1%}",
            "total_retrievals": len(self._hit_rate_history),
            "top_domain": max(self._domain_counts, key=self._domain_counts.get) if self._domain_counts else "none",
            "federated_contributions": len(self._total_contributions),
            "uptime_hours": round((time.time() - self._start_time) / 3600, 1),
        }

    async def get_tenant_report(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed report for a specific tenant."""
        usage = self._tenant_usage.get(tenant_id)
        if not usage:
            return None
        return {
            "tenant_id": tenant_id,
            "total_retrievals": usage["total_retrievals"],
            "total_hits": usage["total_hits"],
            "hit_rate": f"{usage['total_hits'] / max(usage['total_retrievals'], 1):.1%}",
            "domains": dict(usage["domains"]),
        }

    # ── Health Check ────────────────────────────────────────────────────

    async def health_check(self) -> Dict[str, Any]:
        """Check memory system health."""
        issues = []
        stats = {}

        if self.pipeline:
            try:
                stats = await self.pipeline.get_memory_stats()
            except Exception as e:
                issues.append(f"pipeline_error: {e}")

        # Check hit rate
        recent = list(self._hit_rate_history)[-100:]
        hit_rate = sum(p.value for p in recent) / max(len(recent), 1) if recent else 0
        if len(recent) > 20 and hit_rate < 0.1:
            issues.append("low_hit_rate")

        # Check memory engine
        if self.pipeline and self.pipeline.memory:
            mem_stats = self.pipeline.memory.get_solution_stats()
            total = mem_stats.get("total_entries", 0)
            if total == 0:
                issues.append("empty_memory_store")

        return {
            "status": "healthy" if not issues else "degraded",
            "issues": issues,
            "current_hit_rate": f"{hit_rate:.1%}",
            "uptime_seconds": time.time() - self._start_time,
            "stats": stats,
        }

    async def run_realtime_monitor(self, interval: float = 10.0):
        """Run a continuous monitoring loop (prints stats periodically)."""
        while True:
            quick = await self.get_quick_stats()
            logger.info(
                f"MemoryMonitor: hit_rate={quick['hit_rate']} "
                f"retrievals={quick['total_retrievals']} "
                f"top_domain={quick['top_domain']} "
                f"fed_contrib={quick['federated_contributions']}"
            )
            await asyncio.sleep(interval)
