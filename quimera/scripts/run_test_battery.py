#!/usr/bin/env python3
"""
Quimera Test Battery Runner — Automated pipeline validation.

Runs the full pipeline on all 6 test battery levels and generates a report.
Usage: python -m quimera.scripts.run_test_battery [--verbose]
"""
import sys
import time
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_battery")

TEST_BATTERY = Path(__file__).resolve().parent.parent.parent / "test_battery"
LEVELS = [
    ("level1_trivial.c", "CWE-476 NULL pointer dereference", 0.8),
    ("level2_easy.c", "Buffer overflow in strcpy", 0.7),
    ("level3_medium.c", "Use-after-free pattern", 0.6),
    ("level4_hard.c", "Integer overflow + race condition", 0.5),
    ("level5_extreme.c", "Complex concurrency bug", 0.3),
    ("level6_impossible.c", "Architecture-level flaw", 0.1),
]


def run_level(filepath: str, description: str, expected_min_score: float) -> dict:
    """Run pipeline on a single test battery file."""
    import asyncio
    from quimera.pipeline import AutonomousPipeline

    path = TEST_BATTERY / filepath
    if not path.exists():
        return {"file": filepath, "status": "SKIPPED", "reason": "file not found"}

    code = path.read_text(errors="ignore")
    logger.info(f"🔧 Testing {filepath} — {description}")

    t0 = time.monotonic()
    try:
        pipeline = AutonomousPipeline()
        result = asyncio.run(pipeline.run(code, language="c"))
        elapsed = time.monotonic() - t0

        success = getattr(result, "success", False)
        fitness = getattr(result, "fitness_score", 0.0)
        patches = len(getattr(result, "evolved_patches", []) or [])
        stages = getattr(result, "stages_completed", [])

        return {
            "file": filepath,
            "description": description,
            "status": "PASS" if fitness >= expected_min_score else "PARTIAL",
            "success": success,
            "fitness": round(fitness, 4),
            "patches": patches,
            "stages_completed": stages,
            "time_ms": int(elapsed * 1000),
            "expected_min_score": expected_min_score,
        }
    except Exception as e:
        return {
            "file": filepath,
            "status": "ERROR",
            "error": str(e),
            "time_ms": int((time.monotonic() - t0) * 1000),
        }


def main():
    verbose = "--verbose" in sys.argv
    results = []

    for filepath, desc, min_score in LEVELS:
        result = run_level(filepath, desc, min_score)
        results.append(result)

        icon = {"PASS": "✅", "PARTIAL": "🟡", "ERROR": "❌", "SKIPPED": "⚪"}.get(result["status"], "?")
        if verbose:
            print(f"  {icon} {result['file']}: {result['status']} fitness={result.get('fitness', 'N/A')}")
        else:
            print(f"  {icon} {result['file']}: {result['status']}")

    # Summary
    passed = sum(1 for r in results if r["status"] == "PASS")
    total = len([r for r in results if r["status"] != "SKIPPED"])
    print(f"\n📊 Results: {passed}/{total} passed")

    # Save report
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "results": results,
        "summary": {"passed": passed, "total": total, "skipped": len(results) - total},
    }
    report_path = Path(__file__).parent.parent.parent / "logs" / "test_battery_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f"📄 Report saved to {report_path}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
