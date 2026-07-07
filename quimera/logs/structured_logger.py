"""
Quimera Structured Logger — JSON logging with tracing, metrics, timing.
Replaces plain print() logging. Every execution is traceable.
"""
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from contextlib import contextmanager

# ═══════════════════════════════════════════════════════════════════════════
# Structured Logger
# ═══════════════════════════════════════════════════════════════════════════

class StructuredLogger:
    """JSON-structured logger with trace spans, metrics, and timing."""

    def __init__(self, name: str = "quimera", level: int = logging.DEBUG):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.handlers = [handler]

    def _emit(self, level: str, msg: str, **extra):
        """Emit a structured log entry."""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "msg": msg,
            **extra,
        }
        self.logger.info(json.dumps(entry, default=str))

    def info(self, msg, **kw): self._emit("INFO", msg, **kw)
    def warn(self, msg, **kw): self._emit("WARN", msg, **kw)
    def error(self, msg, **kw): self._emit("ERROR", msg, **kw)
    def debug(self, msg, **kw): self._emit("DEBUG", msg, **kw)

    # ── Trace Spans ────────────────────────────────────────────────────

    @contextmanager
    def span(self, name: str, **attrs):
        """Create a trace span. Records duration automatically."""
        span_id = str(uuid.uuid4())[:8]
        t0 = time.monotonic()
        self._emit("TRACE", f"span.start", span_id=span_id, span=name, **attrs)
        try:
            yield span_id
        except Exception as e:
            elapsed = (time.monotonic() - t0) * 1000
            self._emit("TRACE", f"span.error", span_id=span_id, span=name,
                       duration_ms=round(elapsed, 1), error=str(e), **attrs)
            raise
        else:
            elapsed = (time.monotonic() - t0) * 1000
            self._emit("TRACE", f"span.end", span_id=span_id, span=name,
                       duration_ms=round(elapsed, 1), **attrs)

    # ── Pipeline Tracing ───────────────────────────────────────────────

    def trace_pipeline_step(self, mission_id: str, step: str, horizon: str,
                             agent: str = "", model: str = "",
                             duration_ms: float = 0, tokens: int = 0,
                             success: bool = True, error: str = ""):
        """Log one step of the pipeline."""
        self._emit("PIPELINE", f"step.{step}",
                   mission_id=mission_id, step=step, horizon=horizon,
                   agent=agent, model=model,
                   duration_ms=round(duration_ms, 1), tokens=tokens,
                   success=success, error=error)

    def trace_mission(self, mission_id: str, action: str, **details):
        """Log a mission-level event."""
        self._emit("MISSION", action, mission_id=mission_id, **details)


# ═══════════════════════════════════════════════════════════════════════════
# Metrics Collector
# ═══════════════════════════════════════════════════════════════════════════

class MetricsCollector:
    """Collects runtime metrics: latency, tokens, model usage, success rates."""

    def __init__(self):
        self._metrics: List[Dict] = []

    def record(self, metric_type: str, **data):
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": metric_type,
            **data,
        }
        self._metrics.append(entry)

    def record_llm_call(self, provider: str, model: str, duration_ms: float,
                         tokens_in: int = 0, tokens_out: int = 0,
                         success: bool = True, error: str = ""):
        self.record("llm_call", provider=provider, model=model,
                    duration_ms=round(duration_ms, 1),
                    tokens_in=tokens_in, tokens_out=tokens_out,
                    success=success, error=error)

    def record_agent_action(self, agent: str, action: str, duration_ms: float,
                            success: bool = True):
        self.record("agent_action", agent=agent, action=action,
                    duration_ms=round(duration_ms, 1), success=success)

    def record_tool_execution(self, tool: str, horizon: str, duration_ms: float,
                              success: bool = True, error: str = ""):
        self.record("tool_exec", tool=tool, horizon=horizon,
                    duration_ms=round(duration_ms, 1), success=success, error=error)

    def get_summary(self) -> Dict[str, Any]:
        if not self._metrics:
            return {"total_events": 0}

        llm_calls = [m for m in self._metrics if m["type"] == "llm_call"]
        agent_actions = [m for m in self._metrics if m["type"] == "agent_action"]
        tool_execs = [m for m in self._metrics if m["type"] == "tool_exec"]

        return {
            "total_events": len(self._metrics),
            "llm_calls": len(llm_calls),
            "llm_success_rate": f"{sum(1 for m in llm_calls if m.get('success')) / max(len(llm_calls), 1):.1%}",
            "llm_avg_latency_ms": round(sum(m.get("duration_ms", 0) for m in llm_calls) / max(len(llm_calls), 1), 1),
            "total_tokens": sum(m.get("tokens_in", 0) + m.get("tokens_out", 0) for m in llm_calls),
            "agent_actions": len(agent_actions),
            "agent_success_rate": f"{sum(1 for m in agent_actions if m.get('success')) / max(len(agent_actions), 1):.1%}",
            "tool_executions": len(tool_execs),
            "tool_success_rate": f"{sum(1 for m in tool_execs if m.get('success')) / max(len(tool_execs), 1):.1%}",
        }

    def get_provider_usage(self) -> Dict[str, int]:
        """Count calls per LLM provider."""
        from collections import Counter
        return dict(Counter(
            m.get("provider", "?") for m in self._metrics if m["type"] == "llm_call"
        ))

    def flush(self):
        self._metrics.clear()


# Global instances
log = StructuredLogger("quimera")
metrics = MetricsCollector()
