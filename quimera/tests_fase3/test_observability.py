"""
Testes de Observabilidade — AuditTrail, ResourceMonitor, TraceCollector, HealthChecker.
"""
import sys
import os
import json
import time
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


class TestAuditTrail:
    """Testes do AuditTrail."""
    
    def setup_method(self):
        import tempfile
        self.tmpfile = tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False)
        self.tmpfile.close()
    
    def teardown_method(self):
        import os
        os.unlink(self.tmpfile.name)
    
    def test_record_entry(self):
        from quimera.logs.observability import AuditTrail
        
        audit = AuditTrail(storage_path=self.tmpfile.name)
        entry_id = audit.record(
            actor="test",
            action="test.action",
            resource="test-resource",
            outcome="success",
            details={"key": "value"},
        )
        
        assert entry_id is not None
        assert len(entry_id) == 12
        assert audit._total_entries == 1
    
    def test_flush_and_query(self):
        from quimera.logs.observability import AuditTrail
        
        audit = AuditTrail(storage_path=self.tmpfile.name)
        audit.record(actor="agent1", action="pipeline.start", outcome="success")
        audit.record(actor="agent2", action="patch.applied", outcome="failure")
        audit.record(actor="agent1", action="pipeline.end", outcome="success")
        audit.flush()
        
        # Query by actor
        results = audit.query(actor="agent1")
        assert len(results) == 2
        
        # Query by action
        results = audit.query(action="patch.applied")
        assert len(results) == 1
        assert results[0]["outcome"] == "failure"
        
        # Query by outcome
        results = audit.query(outcome="failure")
        assert len(results) == 1
    
    def test_get_stats(self):
        from quimera.logs.observability import AuditTrail
        
        audit = AuditTrail(storage_path=self.tmpfile.name)
        audit.record(actor="test", action="action1", outcome="success")
        audit.record(actor="test", action="action2", outcome="success")
        audit.record(actor="test", action="action3", outcome="failure")
        audit.flush()
        
        stats = audit.get_stats()
        assert stats["total_entries"] == 3
        assert stats["outcomes"]["success"] == 2
        assert stats["outcomes"]["failure"] == 1
        assert len(stats["top_actions"]) == 3
    
    def test_flush_clears_buffer(self):
        from quimera.logs.observability import AuditTrail
        
        audit = AuditTrail(storage_path=self.tmpfile.name)
        audit.record(actor="test", action="test", outcome="success")
        assert len(audit._buffer) == 1
        audit.flush()
        assert len(audit._buffer) == 0


class TestResourceMonitor:
    """Testes do ResourceMonitor."""
    
    def test_snapshot(self):
        from quimera.logs.observability import ResourceMonitor
        
        monitor = ResourceMonitor()
        monitor.start()
        snap = monitor.snapshot()
        monitor.stop()
        
        assert snap is not None
        assert snap.cpu_percent >= 0
        assert snap.memory_rss_mb > 0
        assert snap.uptime_seconds >= 0
    
    def test_summary_with_no_data(self):
        from quimera.logs.observability import ResourceMonitor
        
        monitor = ResourceMonitor()
        summary = monitor.get_summary()
        assert summary["status"] == "no_data"
    
    def test_summary_with_data(self):
        from quimera.logs.observability import ResourceMonitor
        
        monitor = ResourceMonitor()
        monitor.start()
        monitor.snapshot()
        monitor.snapshot()
        summary = monitor.get_summary()
        monitor.stop()
        
        assert summary["samples"] == 2
        assert "cpu" in summary
        assert "memory_rss_mb" in summary
    
    def test_profile_context_manager(self):
        from quimera.logs.observability import ResourceMonitor
        
        monitor = ResourceMonitor()
        monitor.start()
        
        with monitor.profile("test_block"):
            time.sleep(0.01)
        
        summary = monitor.get_summary()
        monitor.stop()
        
        assert summary["samples"] == 2  # before + after
    
    def test_uptime(self):
        from quimera.logs.observability import ResourceMonitor
        
        monitor = ResourceMonitor()
        assert monitor.uptime_seconds == 0.0
        monitor.start()
        time.sleep(0.01)
        assert monitor.uptime_seconds > 0
        monitor.stop()


class TestTraceCollector:
    """Testes do TraceCollector."""
    
    def test_trace_span(self):
        from quimera.logs.observability import TraceCollector
        
        collector = TraceCollector()
        
        with collector.trace("test.operation", key="value") as span:
            assert span.name == "test.operation"
            assert span.attributes["key"] == "value"
            assert span.status == "ok"
        
        assert len(collector._spans) == 1
        assert collector._spans[0].duration_ms >= 0
    
    def test_trace_error(self):
        from quimera.logs.observability import TraceCollector
        
        collector = TraceCollector()
        
        try:
            with collector.trace("test.error"):
                raise ValueError("test error")
        except ValueError:
            pass
        
        assert len(collector._spans) == 1
        assert collector._spans[0].status == "error"
        assert "test error" in collector._spans[0].error
    
    def test_trace_tree(self):
        from quimera.logs.observability import TraceCollector
        
        collector = TraceCollector()
        
        with collector.trace("root") as root:
            with collector.trace("child1", parent=root):
                pass
            with collector.trace("child2", parent=root):
                pass
        
        tree = collector.get_trace_tree()
        assert len(tree) == 1
        assert tree[0]["name"] == "root"
        assert len(tree[0]["children"]) == 2
    
    def test_trace_summary(self):
        from quimera.logs.observability import TraceCollector
        
        collector = TraceCollector()
        
        with collector.trace("op1"):
            pass
        with collector.trace("op2"):
            pass
        
        summary = collector.get_summary()
        assert summary["total_spans"] == 2
        assert summary["error_spans"] == 0
    
    def test_empty_trace_summary(self):
        from quimera.logs.observability import TraceCollector
        
        collector = TraceCollector()
        summary = collector.get_summary()
        assert summary["total_spans"] == 0
    
    def test_flush(self):
        from quimera.logs.observability import TraceCollector
        
        collector = TraceCollector()
        with collector.trace("test"):
            pass
        
        assert len(collector._spans) == 1
        collector.flush()
        assert len(collector._spans) == 0


class TestHealthChecker:
    """Testes do HealthChecker."""
    
    def test_check_all(self):
        from quimera.logs.observability import health_checker
        
        report = health_checker.check_all()
        
        assert "status" in report
        assert report["status"] in ("healthy", "degraded", "unhealthy")
        assert "modules" in report
        assert "database" in report["modules"]
        assert "memory" in report["modules"]
        assert "router" in report["modules"]
    
    def test_check_one_valid(self):
        from quimera.logs.observability import health_checker
        
        result = health_checker.check_one("database")
        assert result["module"] == "database"
        assert result["healthy"] is True
    
    def test_check_one_invalid(self):
        from quimera.logs.observability import health_checker
        
        result = health_checker.check_one("nonexistent_module")
        assert result["healthy"] is False
    
    def test_all_modules_healthy(self):
        """Depois das correções, todos os módulos devem estar healthy."""
        from quimera.logs.observability import health_checker
        
        report = health_checker.check_all()
        
        unhealthy = [m for m, r in report["modules"].items() if not r["healthy"]]
        assert len(unhealthy) == 0, f"Módulos unhealthy: {unhealthy}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
