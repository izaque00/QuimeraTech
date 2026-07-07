"""
Quimera Metrics — Prometheus-compatible observability layer.

Uses prometheus_client if installed; falls back to JSON counters.
Exposes /metrics endpoint for Prometheus scraping.
"""
import logging
import time
import threading
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

_HAS_PROMETHEUS = False
try:
    from prometheus_client import Counter, Gauge, Histogram, generate_latest, REGISTRY
    _HAS_PROMETHEUS = True
except ImportError:
    pass


class QuimeraMetrics:
    """Central metrics registry for the Quimera pipeline."""

    def __init__(self):
        self._lock = threading.Lock()
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, list] = {}
        self._start_time = time.time()

        if _HAS_PROMETHEUS:
            self._init_prometheus()

    def _init_prometheus(self):
        self._prom_counters = {}
        self._prom_gauges = {}
        self._prom_histograms = {}

        # Core metrics
        self._prom_counters["missions_total"] = Counter(
            "quimera_missions_total", "Total missions submitted", ["status"]
        )
        self._prom_counters["patches_generated"] = Counter(
            "quimera_patches_generated", "Total patches generated", ["language"]
        )
        self._prom_counters["llm_calls"] = Counter(
            "quimera_llm_calls_total", "Total LLM API calls", ["provider", "status"]
        )
        self._prom_gauges["pipeline_active"] = Gauge(
            "quimera_pipeline_active", "Currently running pipelines"
        )
        self._prom_gauges["api_uptime_seconds"] = Gauge(
            "quimera_api_uptime_seconds", "API uptime in seconds"
        )
        self._prom_histograms["pipeline_duration"] = Histogram(
            "quimera_pipeline_duration_seconds",
            "Pipeline execution duration",
            buckets=[0.1, 0.5, 1, 5, 10, 30, 60, 120, 300],
        )
        self._prom_histograms["llm_latency"] = Histogram(
            "quimera_llm_latency_seconds",
            "LLM API call latency",
            buckets=[0.05, 0.1, 0.5, 1, 2, 5, 10, 30],
        )

    # ── Counter ──
    def inc_counter(self, name: str, labels: Optional[Dict[str, str]] = None):
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + 1
        if _HAS_PROMETHEUS and name in self._prom_counters:
            c = self._prom_counters[name]
            if labels and hasattr(c, 'labels'):
                c.labels(**labels).inc()
            else:
                c.inc()

    # ── Gauge ──
    def set_gauge(self, name: str, value: float):
        with self._lock:
            self._gauges[name] = value
        if _HAS_PROMETHEUS and name in self._prom_gauges:
            self._prom_gauges[name].set(value)

    def inc_gauge(self, name: str, delta: float = 1.0):
        with self._lock:
            self._gauges[name] = self._gauges.get(name, 0.0) + delta
        if _HAS_PROMETHEUS and name in self._prom_gauges:
            self._prom_gauges[name].inc(delta)

    def dec_gauge(self, name: str, delta: float = 1.0):
        with self._lock:
            self._gauges[name] = self._gauges.get(name, 0.0) - delta
        if _HAS_PROMETHEUS and name in self._prom_gauges:
            self._prom_gauges[name].dec(delta)

    # ── Histogram ──
    def observe(self, name: str, value: float):
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = []
            self._histograms[name].append(value)
            if len(self._histograms[name]) > 1000:
                self._histograms[name] = self._histograms[name][-1000:]
        if _HAS_PROMETHEUS and name in self._prom_histograms:
            self._prom_histograms[name].observe(value)

    # ── Export ──
    def get_metrics_text(self) -> str:
        """Return Prometheus text format (or JSON fallback)."""
        if _HAS_PROMETHEUS:
            self._prom_gauges["api_uptime_seconds"].set(time.time() - self._start_time)
            return generate_latest(REGISTRY).decode("utf-8")

        # JSON fallback
        import json
        uptime = time.time() - self._start_time
        return json.dumps({
            "uptime_seconds": uptime,
            "counters": self._counters,
            "gauges": self._gauges,
            "histogram_sizes": {k: len(v) for k, v in self._histograms.items()},
        }, indent=2)

    def get_health(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "uptime_seconds": time.time() - self._start_time,
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
        }


# Global singleton
metrics = QuimeraMetrics()
