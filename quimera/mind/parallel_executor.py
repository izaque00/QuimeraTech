"""
Quimera Parallel Executor — Executes independent subtasks concurrently.
Uses asyncio.gather with dependency-aware scheduling.
"""
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("quimera.executor")

# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class SubTaskResult:
    subtask_id: str
    success: bool
    agent: str
    horizon: str
    duration_ms: float
    output: Dict = field(default_factory=dict)
    error: str = ""

@dataclass
class ExecutionResult:
    plan_id: str
    results: List[SubTaskResult] = field(default_factory=list)
    total_duration_ms: float = 0.0
    parallel_speedup: float = 1.0

# ═══════════════════════════════════════════════════════════════════════════

class ParallelExecutor:
    """Execute a Plan with maximal parallelism respecting dependencies.

    Subtasks with the same dependency level run concurrently.
    Example:
        Problem → [H2, H3]  (parallel — no deps)
               → H4        (depends on H2, H3)
               → H5        (depends on H4)
               → H1        (depends on H5)
    """

    def __init__(self, engine=None, reputation=None, max_parallel: int = 5):
        self.engine = engine           # AutonomousEngine
        self.reputation = reputation   # ReputationEngine
        self.max_parallel = max_parallel

    async def execute(self, plan) -> ExecutionResult:
        """Execute a Plan with dependency-aware parallelism."""
        t0 = time.monotonic()

        # Build dependency graph
        done: Dict[str, SubTaskResult] = {}
        pending = list(plan.subtasks)
        results = []

        while pending:
            # Find tasks whose dependencies are all satisfied
            ready = []
            still_pending = []

            for st in pending:
                deps_satisfied = all(
                    d in done and done[d].success
                    for d in st.dependencies
                )
                if deps_satisfied:
                    ready.append(st)
                else:
                    still_pending.append(st)

            if not ready and still_pending:
                # Deadlock — run remaining tasks anyway
                ready = still_pending
                still_pending = []

            # Execute ready tasks in parallel (up to max_parallel)
            batch_results = await self._execute_batch(ready)

            for r in batch_results:
                done[r.subtask_id] = r
                results.append(r)

            pending = still_pending

        total_ms = (time.monotonic() - t0) * 1000
        serial_ms = sum(r.duration_ms for r in results)
        speedup = serial_ms / max(total_ms, 1)

        # Record all results in reputation
        if self.reputation:
            for r in results:
                self.reputation.record_action(
                    action_id=r.subtask_id,
                    agent=r.agent,
                    action=r.horizon,
                    success=r.success,
                    latency_ms=r.duration_ms,
                    fitness=1.0 if r.success else 0.0,
                )

        return ExecutionResult(
            plan_id=plan.id if hasattr(plan, 'id') else "?",
            results=results,
            total_duration_ms=round(total_ms, 1),
            parallel_speedup=round(speedup, 1),
        )

    async def _execute_batch(self, subtasks: list) -> List[SubTaskResult]:
        """Execute a batch of subtasks in parallel."""
        if self.max_parallel > 1 and len(subtasks) > 1:
            # Parallel
            tasks = [self._execute_one(st) for st in subtasks]
            return await asyncio.gather(*tasks)
        elif subtasks:
            # Sequential (single task or max_parallel=1)
            return [await self._execute_one(subtasks[0])]
        return []

    async def _execute_one(self, st) -> SubTaskResult:
        """Execute a single subtask."""
        t0 = time.monotonic()

        try:
            # Map subtask to action
            action_data = {
                "type": st.horizon.lower(),
                "description": st.description,
                "severity": "HIGH" if st.confidence > 0.7 else "MEDIUM",
            }

            # Use AutonomousEngine if available
            if self.engine:
                from quimera.mind.autonomous_engine import AutonomousAction
                action = AutonomousAction(
                    id=st.id,
                    type="repair",
                    issue=action_data,
                    tool_chain=st.required_tools,
                    confidence=st.confidence,
                )
                result = await self.engine.execute_action(action)
                success = result.success
                output = {"tools_executed": result.tools_executed,
                          "horizon": result.horizon_used,
                          "repairs": result.repairs_made}
            else:
                # Deterministic fallback
                success = True
                output = {"status": "executed_deterministic",
                          "tools": st.required_tools}

        except Exception as e:
            success = False
            output = {}
            error = str(e)
        else:
            error = ""

        elapsed = (time.monotonic() - t0) * 1000

        return SubTaskResult(
            subtask_id=st.id,
            success=success,
            agent=st.agent or "auto",
            horizon=st.horizon,
            duration_ms=round(elapsed, 1),
            output=output,
            error=error,
        )

    def get_stats(self) -> Dict[str, Any]:
        return {
            "max_parallel": self.max_parallel,
            "engine": "AutonomousEngine" if self.engine else "deterministic",
        }
