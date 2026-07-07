"""
Quimera Mark X — Auto-Scaler (Horizonte 1)

Dynamically scales worker pool based on queue depth, latency,
and resource utilization.

Strategies:
  - QUEUE_DEPTH: Scale based on pending missions
  - LATENCY: Scale based on mission processing time
  - SCHEDULE: Time-based scaling (business hours)
  - HYBRID: Weighted combination (default)

Integration points:
  - Docker: docker-compose up -d --scale worker=N
  - Kubernetes: HPA (HorizontalPodAutoscaler) manifest generation
  - Local: Spawn subprocess workers

Usage:
    scaler = AutoScaler(orchestrator, strategy="hybrid")
    await scaler.start()
"""

import asyncio
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("quimera.scaler")


class ScalingAction(str, Enum):
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    NONE = "none"


class ScalingStrategy(str, Enum):
    QUEUE_DEPTH = "queue_depth"
    LATENCY = "latency"
    SCHEDULE = "schedule"
    HYBRID = "hybrid"


@dataclass
class ScalingDecision:
    action: ScalingAction
    current_workers: int
    target_workers: int
    reason: str
    metrics: Dict[str, Any]


# ═══════════════════════════════════════════════════════════════════════════
# Scaling Rules
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_RULES = {
    "min_workers": 1,
    "max_workers": 20,
    "queue_per_worker": 5,           # Target queue depth per worker
    "scale_up_threshold": 0.7,       # 70% capacity utilization triggers scale up
    "scale_down_threshold": 0.3,     # 30% triggers scale down
    "cooldown_seconds": 60,          # Minimum time between scaling actions
    "max_latency_ms": 30000,         # Max acceptable mission processing time
    "business_hours_start": 8,       # 8 AM
    "business_hours_end": 20,        # 8 PM
    "business_hours_workers": 4,
    "off_hours_workers": 1,
}


# ═══════════════════════════════════════════════════════════════════════════
# Auto-Scaler
# ═══════════════════════════════════════════════════════════════════════════

class AutoScaler:
    """Dynamic worker pool scaler.

    Monitors cluster metrics and adjusts worker count automatically.
    Supports Docker, Kubernetes, and local process scaling backends.
    """

    def __init__(
        self,
        orchestrator,        # DistributedOrchestrator
        strategy: str = "hybrid",
        rules: Optional[Dict] = None,
        backend: str = "local",  # local, docker, kubernetes
        check_interval: int = 15,
    ):
        self.orchestrator = orchestrator
        self.strategy = ScalingStrategy(strategy)
        self.rules = {**DEFAULT_RULES, **(rules or {})}
        self.backend = backend
        self.check_interval = check_interval

        self._running = False
        self._last_action_time = 0.0
        self._local_workers: List[subprocess.Popen] = []
        self._metrics_history: List[Dict] = []  # Rolling window for trend analysis

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def start(self):
        self._running = True
        logger.info(f"AutoScaler started (strategy={self.strategy.value}, backend={self.backend})")
        while self._running:
            try:
                decision = await self.evaluate()
                if decision.action != ScalingAction.NONE:
                    await self.execute(decision)
            except Exception as e:
                logger.error(f"Scaler evaluation error: {e}", exc_info=True)
            await asyncio.sleep(self.check_interval)

    async def stop(self):
        self._running = False
        for proc in self._local_workers:
            proc.terminate()
        logger.info("AutoScaler stopped")

    # ── Evaluation ─────────────────────────────────────────────────────

    async def evaluate(self) -> ScalingDecision:
        """Evaluate current cluster state and produce scaling decision."""
        # Get current state
        stats = await self.orchestrator.get_cluster_stats()
        queue_size = await self.orchestrator.get_global_queue_size()
        current_workers = stats["active_workers"]
        capacity = stats["total_capacity"]
        load = stats["current_load"]

        # Cooldown check
        if time.time() - self._last_action_time < self.rules["cooldown_seconds"]:
            return ScalingDecision(
                action=ScalingAction.NONE,
                current_workers=current_workers,
                target_workers=current_workers,
                reason="Cooldown active",
                metrics={"queue_size": queue_size, "load": load, "capacity": capacity},
            )

        # Compute target based on strategy
        if self.strategy == ScalingStrategy.QUEUE_DEPTH:
            target = await self._evaluate_queue_depth(queue_size, current_workers)
        elif self.strategy == ScalingStrategy.LATENCY:
            target = await self._evaluate_latency(current_workers)
        elif self.strategy == ScalingStrategy.SCHEDULE:
            target = self._evaluate_schedule()
        else:  # HYBRID
            q_target = await self._evaluate_queue_depth(queue_size, current_workers)
            l_target = await self._evaluate_latency(current_workers)
            s_target = self._evaluate_schedule()
            # Weighted: queue 50%, latency 30%, schedule 20%
            target = int(q_target * 0.5 + l_target * 0.3 + s_target * 0.2)
            target = max(1, target)

        # Clamp to bounds
        target = max(self.rules["min_workers"], min(self.rules["max_workers"], target))

        # Determine action
        if target > current_workers:
            action = ScalingAction.SCALE_UP
            reason = f"Scaling up: queue={queue_size}, load={load}/{capacity}"
        elif target < current_workers:
            action = ScalingAction.SCALE_DOWN
            reason = f"Scaling down: queue={queue_size}, load={load}/{capacity}"
        else:
            action = ScalingAction.NONE
            reason = "Stable"

        return ScalingDecision(
            action=action,
            current_workers=current_workers,
            target_workers=target,
            reason=reason,
            metrics={"queue_size": queue_size, "load": load, "capacity": capacity, "strategy": self.strategy.value},
        )

    async def _evaluate_queue_depth(self, queue_size: int, current_workers: int) -> int:
        """Target workers based on queue depth."""
        per_worker = self.rules["queue_per_worker"]
        target = max(1, int(queue_size / per_worker) + 1)
        return target

    async def _evaluate_latency(self, current_workers: int) -> int:
        """Target workers based on recent processing latency."""
        if len(self._metrics_history) < 3:
            return current_workers
        recent = self._metrics_history[-5:]
        avg_latency = sum(m.get("avg_latency_ms", 0) for m in recent) / len(recent)

        if avg_latency > self.rules["max_latency_ms"]:
            return current_workers + 2
        elif avg_latency < self.rules["max_latency_ms"] * 0.3:
            return max(1, current_workers - 1)
        return current_workers

    def _evaluate_schedule(self) -> int:
        """Target workers based on time of day."""
        import datetime
        hour = datetime.datetime.now().hour
        if self.rules["business_hours_start"] <= hour < self.rules["business_hours_end"]:
            return self.rules["business_hours_workers"]
        return self.rules["off_hours_workers"]

    async def record_metrics(self, metrics: Dict[str, Any]):
        """Record processing metrics for trend analysis."""
        self._metrics_history.append(metrics)
        if len(self._metrics_history) > 100:
            self._metrics_history = self._metrics_history[-50:]

    # ── Execution ──────────────────────────────────────────────────────

    async def execute(self, decision: ScalingDecision):
        """Execute a scaling decision."""
        logger.info(
            f"Scaling: {decision.action.value} "
            f"{decision.current_workers} → {decision.target_workers} "
            f"({decision.reason})"
        )

        self._last_action_time = time.time()

        if self.backend == "docker":
            await self._scale_docker(decision)
        elif self.backend == "kubernetes":
            await self._generate_k8s_manifest(decision)
        else:
            await self._scale_local(decision)

    async def _scale_docker(self, decision: ScalingDecision):
        """Scale Docker Compose worker replicas."""
        try:
            cmd = [
                "docker-compose", "up", "-d",
                "--scale", f"worker={decision.target_workers}",
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                logger.info(f"Docker scaled to {decision.target_workers} workers")
            else:
                logger.error(f"Docker scale failed: {stderr.decode()}")
        except FileNotFoundError:
            logger.warning("docker-compose not found — scaling skipped")

    async def _scale_local(self, decision: ScalingDecision):
        """Scale by spawning/killing local worker processes."""
        # Scale up
        while len(self._local_workers) < decision.target_workers:
            try:
                proc = subprocess.Popen(
                    ["python", "-m", "quimera.api.worker"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._local_workers.append(proc)
                logger.info(f"Spawned worker #{len(self._local_workers)}")
            except Exception as e:
                logger.error(f"Failed to spawn worker: {e}")
                break

        # Scale down
        while len(self._local_workers) > decision.target_workers:
            proc = self._local_workers.pop()
            proc.terminate()
            logger.info(f"Terminated worker (#{len(self._local_workers) + 1} remaining)")

    async def _generate_k8s_manifest(self, decision: ScalingDecision):
        """Generate Kubernetes HPA manifest."""
        manifest = {
            "apiVersion": "autoscaling/v2",
            "kind": "HorizontalPodAutoscaler",
            "metadata": {"name": "quimera-worker-hpa"},
            "spec": {
                "scaleTargetRef": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "name": "quimera-worker",
                },
                "minReplicas": self.rules["min_workers"],
                "maxReplicas": self.rules["max_workers"],
                "metrics": [
                    {
                        "type": "Resource",
                        "resource": {
                            "name": "cpu",
                            "target": {"type": "Utilization", "averageUtilization": 70},
                        },
                    },
                    {
                        "type": "External",
                        "external": {
                            "metric": {"name": "quimera_queue_depth"},
                            "target": {"type": "AverageValue", "averageValue": str(self.rules["queue_per_worker"])},
                        },
                    },
                ],
            },
        }
        logger.info(f"K8s HPA: target replicas = {decision.target_workers}")
        return manifest
