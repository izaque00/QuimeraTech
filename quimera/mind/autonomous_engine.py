"""Quimera Mind - Autonomous Engine v3.1 — REAL H1-H6 execution."""
import asyncio, json, logging, os, time, traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("quimera.mind.engine")

class ConfidenceLevel(float, Enum): CRITICAL = 0.95; HIGH = 0.80; MEDIUM = 0.50; LOW = 0.25

@dataclass
class AutonomousAction:
    id: str; type: str; issue: Dict; tool_chain: List[str]; max_attempts: int = 3
    validation_check: Optional[str] = None; confidence: float = 0.5
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

@dataclass
class ActionResult:
    action_id: str; success: bool; tools_executed: List[str] = field(default_factory=list)
    tools_failed: List[str] = field(default_factory=list); repairs_made: int = 0
    horizon_used: str = ""; duration_ms: float = 0.0
    patches: List[Dict] = field(default_factory=list); error: Optional[str] = None

class ActionPlanner:
    TOOL_MAP = {
        "compilation_error": ["codebase_search", "genetic_evolve", "sandbox_execute"],
        "memory_error": ["z3_verify_patch", "genetic_evolve", "cbmc_verify"],
        "security_vuln": ["red_team_attack", "cve_scan", "genetic_evolve", "sandbox_execute"],
        "cve_alert": ["cve_scan", "red_team_attack", "genetic_evolve"],
        "test_failure": ["coevolution_attack", "genetic_evolve", "sandbox_execute"],
        "unknown": ["codebase_search", "knowledge_base_query", "genetic_evolve"],
    }
    SEVERITY = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    @classmethod
    def plan(cls, issue):
        t = issue.get("type", "unknown"); s = issue.get("severity", "MEDIUM")
        c = {"CRITICAL": 0.95, "HIGH": 0.80, "MEDIUM": 0.50}.get(s, 0.25)
        return AutonomousAction(
            id=f"act-{int(time.time()*1000)}",
            type="repair" if t != "cve_alert" else "secure",
            issue=issue,
            tool_chain=cls.TOOL_MAP.get(t, cls.TOOL_MAP["unknown"]),
            max_attempts=3 if s in ("CRITICAL", "HIGH") else 2,
            confidence=c,
        )

class AutonomousEngine:
    def __init__(self, mind=None):
        self.mind = mind; self._action_history = []; self._total_actions = 0
        self._total_successes = 0; self._min_confidence = 0.5; self._decision_log = []

    async def handle_issues(self, issues):
        if not issues: return {"handled": 0, "actions": [], "summary": "No issues"}
        if isinstance(issues[0], dict): raw = issues
        else: raw = [{"type": i.type, "severity": i.severity.value if hasattr(i, 'severity') else "MEDIUM", "description": i.description, "file_path": getattr(i, 'file_path', '?'), "line_number": getattr(i, 'line_number', 0)} for i in issues]
        raw.sort(key=lambda i: ActionPlanner.SEVERITY.get(i.get("severity", "MEDIUM"), 99))
        actions = [ActionPlanner.plan(i) for i in raw]
        executable = [a for a in actions if a.confidence >= self._min_confidence]
        results = []
        for action in executable[:5]:
            result = await self._execute_with_retry(action)
            results.append(result); self._action_history.append(action); self._total_actions += 1
            if result.success: self._total_successes += 1
        return {"handled": len(results), "successes": sum(1 for r in results if r.success), "actions": [{"id": r.action_id, "success": r.success, "tools": r.tools_executed, "horizon": r.horizon_used} for r in results]}

    async def execute_action(self, action): return await self._execute_with_retry(action)

    async def _execute_with_retry(self, action):
        t0 = time.monotonic(); tools_executed = []; tools_failed = []; patches = []; last_error = None
        for attempt in range(action.max_attempts):
            for tool_name in action.tool_chain:
                try:
                    result = await self._execute_tool_real(tool_name, action)
                    if result.get("ok"): tools_executed.append(tool_name)
                    else: tools_failed.append(tool_name)
                except Exception as e:
                    tools_failed.append(tool_name); last_error = str(e)
            if tools_failed and attempt < action.max_attempts - 1:
                await asyncio.sleep(2 ** (attempt + 1)); tools_failed = []
            if tools_executed and not tools_failed: break
        elapsed = (time.monotonic() - t0) * 1000
        success = len(tools_failed) == 0 and len(tools_executed) > 0
        return ActionResult(
            action_id=action.id, success=success, tools_executed=tools_executed,
            tools_failed=tools_failed, repairs_made=len(patches),
            horizon_used=self._horizon(tools_executed), duration_ms=round(elapsed, 1),
            error=last_error,
        )

    async def _execute_tool_real(self, tool_name, action):
        m = {
            "genetic_evolve": self._h4_genetic_evolve,
            "red_team_attack": self._h5_red_team,
            "cve_scan": self._h5_fuzz,
            "z3_verify_patch": self._h3_z3_verify,
            "cbmc_verify": self._h3_cbmc,
            "memory_retrieve_solutions": self._h2_memory,
            "sandbox_execute": self._h1_sandbox,
            "codebase_search": self._kb_search,
            "knowledge_base_query": self._kb_search,
            "coevolution_attack": self._h4_coevolution,
        }
        return await (m.get(tool_name, self._unknown)(action))

    # ── H4 Genetic Evolution ───────────────────────────────────────────
    async def _h4_genetic_evolve(self, action):
        try:
            from quimera.horizons.h4_evolution.genetic_patch_engine import GeneticPatchEngine
            fp = action.issue.get("file_path", "")
            if not fp or not os.path.exists(fp): return {"ok": False, "error": "No file"}
            engine = GeneticPatchEngine(population_size=100, generations=50, mutation_rate=0.1, crossover_rate=0.8)
            patches = await asyncio.to_thread(engine.evolve_patches, file_path=fp, error_description=action.issue.get("description", ""))
            return {"ok": bool(patches), "horizon": "H4", "repairs_made": 1 if patches else 0, "patches": patches or []}
        except ImportError: return {"ok": False, "horizon": "H4", "error": "GeneticPatchEngine unavailable"}
        except Exception as e: return {"ok": False, "horizon": "H4", "error": str(e)}

    async def _h4_coevolution(self, action):
        try:
            from quimera.agentes.coevolution_engine import CoevolutionEngine
            engine = CoevolutionEngine()
            results = await asyncio.to_thread(engine.run, action.issue)
            return {"ok": True, "horizon": "H4", "results": results}
        except ImportError: return {"ok": False, "horizon": "H4", "error": "Coevolution unavailable"}
        except Exception as e: return {"ok": False, "horizon": "H4", "error": str(e)}

    # ── H5 Security ────────────────────────────────────────────────────
    async def _h5_red_team(self, action):
        try:
            from quimera.horizons.h5_security.red_team import RedTeam
            fp = action.issue.get("file_path", "")
            if not fp: return {"ok": False, "error": "No file"}
            with open(fp) as f: source = f.read()
            team = RedTeam(); attacks = await asyncio.to_thread(team.attack, source)
            passed = sum(1 for a in attacks if a.get("vulnerable")) if attacks else 0
            return {"ok": True, "horizon": "H5", "attacks_passed": passed, "attacks_total": len(attacks) if attacks else 0, "vulnerable": passed > 0}
        except ImportError: return {"ok": False, "horizon": "H5", "error": "RedTeam unavailable"}
        except Exception as e: return {"ok": False, "horizon": "H5", "error": str(e)}

    async def _h5_fuzz(self, action):
        try:
            from quimera.horizons.h5_security.fuzzing_engine import FuzzingEngine
            engine = FuzzingEngine()
            fp = action.issue.get("file_path", "")
            with open(fp) as f: source = f.read()
            results = await asyncio.to_thread(engine.fuzz, source)
            return {"ok": True, "horizon": "H5", "fuzzed": len(results) if results else 0}
        except ImportError: return {"ok": False, "horizon": "H5", "error": "Fuzzing unavailable"}
        except Exception as e: return {"ok": False, "horizon": "H5", "error": str(e)}

    # ── H3 Formal Verification ─────────────────────────────────────────
    async def _h3_z3_verify(self, action):
        try:
            from quimera.integration_backends.z3_wrapper import Z3Wrapper
            fp = action.issue.get("file_path", "")
            if not fp: return {"ok": False, "error": "No file"}
            with open(fp) as f: source = f.read()
            wrapper = Z3Wrapper()
            result = wrapper.check_c_assertion(source, action.issue.get("description", "safety check"))
            return {"ok": result.get("verified", False), "horizon": "H3", "verified": result.get("verified", False)}
        except ImportError: return {"ok": False, "horizon": "H3", "error": "Z3 unavailable"}
        except Exception as e: return {"ok": False, "horizon": "H3", "error": str(e)}

    async def _h3_cbmc(self, action):
        try:
            fp = action.issue.get("file_path", "")
            proc = await asyncio.create_subprocess_exec("cbmc", fp, "--unwind", "10", "--trace", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            return {"ok": b"VERIFICATION SUCCESSFUL" in stdout, "horizon": "H3"}
        except Exception as e:
            import logging as _log
            _log.getLogger(__name__).warning(f"CBMC verification failed: {e}")
            return {"ok": False, "horizon": "H3", "error": f"CBMC: {e}"}

    # ── H2 Memory ─────────────────────────────────────────────────────
    async def _h2_memory(self, action):
        try:
            from quimera.memory.integration import MemoryPipeline
            pipeline = MemoryPipeline()
            results = await pipeline.retrieve_solutions(error_type=action.issue.get("type", ""), error_description=action.issue.get("description", ""))
            return {"ok": True, "horizon": "H2", "count": results.total_found, "solutions": results.solutions}
        except ImportError: return {"ok": False, "horizon": "H2", "error": "Memory unavailable"}
        except Exception as e: return {"ok": False, "horizon": "H2", "error": str(e)}

    # ── H1 Sandbox ────────────────────────────────────────────────────
    async def _h1_sandbox(self, action):
        try:
            from quimera.sandbox.manager import SandboxManager
            mgr = SandboxManager()
            result = await mgr.run(action.issue.get("file_path", ""), timeout=30)
            return {"ok": result.get("exit_code") == 0, "horizon": "H1", "exit_code": result.get("exit_code")}
        except ImportError: return {"ok": False, "horizon": "H1", "error": "Sandbox unavailable"}
        except Exception as e: return {"ok": False, "horizon": "H1", "error": str(e)}

    # ── Knowledge ─────────────────────────────────────────────────────
    async def _kb_search(self, action):
        if self.mind and hasattr(self.mind, '_knowledge') and self.mind._knowledge:
            results = await self.mind._knowledge.search(action.issue.get("description", ""))
            return {"ok": True, "results": results or []}
        return {"ok": False, "error": "Knowledge not initialized"}

    async def _unknown(self, action): return {"ok": False, "error": "Unknown tool"}

    def _horizon(self, tools):
        m = {"genetic_evolve": "H4", "red_team_attack": "H5", "cve_scan": "H5", "z3_verify_patch": "H3", "cbmc_verify": "H3", "memory_retrieve_solutions": "H2", "sandbox_execute": "H1"}
        for t in tools:
            if t in m: return m[t]
        return "?"

    def get_stats(self):
        return {"total_actions": self._total_actions, "total_successes": self._total_successes, "success_rate": f"{self._total_successes / max(self._total_actions, 1):.1%}"}
