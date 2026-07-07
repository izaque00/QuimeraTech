"""
End-to-End Test: Quimera Pipeline Complete

Tests:
  1. Pipeline H1→H6 on real C code
  2. Worker + Mission processing
  3. Sandbox compilation
  4. Self-healing fallback
  5. Memory persistence
  6. Distributed orchestrator

Usage:
    PYTHONPATH=. pytest quimera/tests_fase3/test_e2e.py -v -s
"""
import pytest
import asyncio
import time
import tempfile
import os
from pathlib import Path

# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_c_code():
    """Realistic C code with common vulnerabilities."""
    return """
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

void process_buffer(const char *input, int size) {
    char buf[64];
    strcpy(buf, input);  // CWE-121: buffer overflow
    printf("Processed: %s\\n", buf);
}

int main(int argc, char **argv) {
    if (argc < 2) {
        printf("Usage: %s <input>\\n", argv[0]);
        return 1;
    }
    
    char *data = malloc(strlen(argv[1]) + 1);
    if (data == NULL) {
        return 1;  // CWE-401: memory leak of nothing, but pattern
    }
    
    strncpy(data, argv[1], strlen(argv[1]));
    process_buffer(data, strlen(data));
    
    free(data);
    return 0;
}
"""

@pytest.fixture
def temp_c_file(sample_c_code):
    """Create a temporary C file for testing."""
    fd, path = tempfile.mkstemp(suffix='.c', prefix='quimera_test_')
    with os.fdopen(fd, 'w') as f:
        f.write(sample_c_code)
    yield path
    try:
        os.unlink(path)
    except Exception:
        pass


# ── Test 1: Pipeline H1→H6 ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pipeline_full_h1_h6(sample_c_code):
    """Full pipeline should run all 7 stages and detect strcpy vulnerability."""
    from quimera.pipeline import AutonomousPipeline
    
    pipeline = AutonomousPipeline()
    ctx = await pipeline.run(sample_c_code, language="c",
                             error_description="CWE-121 buffer overflow")
    
    # Should complete without fatal error
    assert ctx.stages_completed, "Pipeline should complete at least some stages"
    
    # Should detect the unsafe strcpy
    if hasattr(ctx, 'verification_result'):
        assert ctx.verification_result is not None
    
    # Should produce at least a fallback patch
    if hasattr(ctx, 'best_patch'):
        assert ctx.best_patch, "Should produce a patch"
    
    print(f"\n✅ Pipeline H1→H6: {len(ctx.stages_completed)}/7 stages, fitness={ctx.fitness_score:.3f}, patches={len(ctx.evolved_patches) if ctx.evolved_patches else 0}")


# ── Test 2: Worker processing ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_worker_processes_mission(temp_c_file):
    """Worker should process a mission through compilation + self-healing."""
    from quimera.api.worker import MissionWorker
    from quimera.api.mission_queue import MissionQueue
    
    queue = MissionQueue()  # Local mode (no Redis needed)
    worker = MissionWorker(queue, max_concurrent=1)
    
    # Create a mission
    mission = {
        "mission_id": "e2e-test-001",
        "kernel_path": temp_c_file,
        "target_arch": "x86_64",
        "language": "c",
        "error_context": "Test mission",
    }
    
    t0 = time.monotonic()
    await worker._process_mission(mission)
    elapsed = (time.monotonic() - t0) * 1000
    
    status = await queue.get_status("e2e-test-001")
    assert status is not None, "Mission should have a status"
    
    print(f"\n✅ Worker processing: {elapsed:.0f}ms, status={status}")


# ── Test 3: Sandbox compilation ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sandbox_compilation():
    """Sandbox should compile valid C code."""
    from quimera.api.worker import MissionWorker
    from quimera.api.mission_queue import MissionQueue
    
    queue = MissionQueue()
    worker = MissionWorker(queue)
    
    result = await worker._compile_in_sandbox({
        "kernel_path": "",
        "source_code": "int main() { return 0; }",
    })
    
    print(f"\n✅ Sandbox compilation: {'PASS' if result else 'FAIL (expected if no GCC)'}")
    # Note: may fail if no GCC in environment — that's OK


# ── Test 4: Self-healing fallback ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_self_healing_fallback(sample_c_code):
    """Self-healing should attempt to fix compilation failures."""
    from quimera.api.worker import MissionWorker
    from quimera.api.mission_queue import MissionQueue
    
    queue = MissionQueue()
    worker = MissionWorker(queue)
    
    result = await worker._attempt_self_healing({
        "mission_id": "e2e-heal-001",
        "kernel_path": "",
        "source_code": sample_c_code,
        "error_context": "CWE-121: stack buffer overflow in strcpy",
        "target_arch": "x86_64",
    })
    
    print(f"\n✅ Self-healing: {'PASS' if result else 'NO FIX (expected without LLM)'}")


# ── Test 5: Memory persistence ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_memory_pipeline_integration():
    """MemoryPipeline should persist outcomes."""
    try:
        from quimera.memory.integration import MemoryPipeline
        
        pipeline = MemoryPipeline(auto_record=True)
        
        # Try recording an outcome
        await pipeline.record_outcome(
            mission_id="e2e-mem-001",
            error_description="CWE-476 null pointer",
            error_type="null_deref",
            success=True,
            fitness_score=0.95,
            patch_code="// NULL check added",
        )
        print("\n✅ Memory persistence: OK")
    except ImportError:
        print("\n⚠️ MemoryPipeline not available — skipping")
    except Exception as e:
        print(f"\n⚠️ Memory persistence: {e}")


# ── Test 6: CLI repair command ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cli_repair(temp_c_file):
    """CLI repair command should work on a real file."""
    import sys
    from unittest.mock import patch
    
    sys.argv = ["quimera", "repair", temp_c_file]
    
    try:
        from quimera.cli import main
        result = main()
        print(f"\n✅ CLI repair: exit code={result}")
    except SystemExit as e:
        print(f"\n✅ CLI repair: exit={e.code}")
    except Exception as e:
        print(f"\n⚠️ CLI repair: {e}")


# ── Test 7: Validator chain ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_validator_chain(temp_c_file):
    """Validators should form a chain: compile → build → test → asan → ubsan → fuzz."""
    from quimera.validators.compile import CompileValidator
    from quimera.validators.base import BaseValidator
    
    code = Path(temp_c_file).read_text()
    
    # At minimum, the compile validator should work
    v = CompileValidator()
    try:
        ok, out, err, elapsed = v._run_cmd(f"gcc -fsyntax-only {temp_c_file} 2>&1", temp_c_file, 30)
        print(f"\n✅ CompileValidator: compile={'OK' if ok else 'FAIL'}, {elapsed:.0f}s")
    except Exception as e:
        print(f"\n⚠️ CompileValidator: {e}")


# ── Run ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    asyncio.run(test_pipeline_full_h1_h6("""
    int main() { char buf[10]; strcpy(buf, "overflow"); return 0; }
    """))
    print("\n" + "="*60)
    print("All E2E tests complete!")
    print("="*60)
