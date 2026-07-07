"""
Quimera Planner — Antes de executar, planeja.
Divide problemas em subtarefas e seleciona os melhores agentes.
"""
import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("quimera.planner")

# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class SubTask:
    id: str
    description: str
    horizon: str           # H1-H6
    required_tools: List[str] = field(default_factory=list)
    agent: str = ""        # Assigned agent
    confidence: float = 0.5
    dependencies: List[str] = field(default_factory=list)  # IDs of subtasks this depends on

@dataclass
class Plan:
    id: str
    problem: str
    subtasks: List[SubTask] = field(default_factory=list)
    estimated_time_ms: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    confidence: float = 0.5

# ═══════════════════════════════════════════════════════════════════════════

class QuimeraPlanner:
    """Analyzes problems and creates execution plans.

    Uses both deterministic heuristics AND LLM reasoning (when available).
    Selects agents based on reputation scores.
    """

    def __init__(self, mind=None, reputation_engine=None):
        self.mind = mind
        self.reputation = reputation_engine

    async def plan(self, problem: str, context: Dict = None) -> Plan:
        """Create an execution plan for the given problem."""
        plan_id = f"plan-{int(asyncio.get_event_loop().time() * 1000)}"

        # 1. Classify problem → determine which horizons are needed
        horizon_needs = self._classify_problem(problem, context or {})

        # 2. Generate subtasks
        subtasks = self._generate_subtasks(plan_id, problem, horizon_needs)

        # 3. Assign agents based on reputation
        subtasks = await self._assign_agents(subtasks)

        # 4. Sort by dependencies (topological)
        subtasks = self._topological_sort(subtasks)

        # 5. Estimate total time
        total_ms = sum(
            self._estimate_subtask_time(st) for st in subtasks
        )

        # 6. Try LLM refinement (optional, non-blocking)
        try:
            if self.mind and hasattr(self.mind, '_llm_adviser') and self.mind._llm_adviser:
                refined = await self._llm_refine_plan(problem, subtasks)
                if refined:
                    subtasks = refined
        except Exception:
            pass

        return Plan(
            id=plan_id,
            problem=problem,
            subtasks=subtasks,
            estimated_time_ms=total_ms,
            confidence=self._calc_plan_confidence(subtasks),
        )

    # ── Problem Classification ──────────────────────────────────────────

    def _classify_problem(self, problem: str, context: Dict) -> Dict[str, int]:
        """Determine which horizons are needed and priority."""
        p = problem.lower()
        needs = {}

        # H1 (Distributed/Sandbox): always needed for execution
        needs["H1"] = 1

        # H2 (Memory): needed if we should check past solutions
        if any(kw in p for kw in ["similar", "before", "past", "crash", "segfault",
                                   "null pointer", "use after free", "double free"]):
            needs["H2"] = 2  # Higher priority

        # H3 (Formal Verification): needed for safety-critical code
        if any(kw in p for kw in ["verify", "prove", "assertion", "invariant",
                                   "overflow", "underflow", "buffer", "bounds"]):
            needs["H3"] = 2

        # H4 (Genetic Evolution): needed for code repair
        if any(kw in p for kw in ["fix", "repair", "patch", "correct", "bug",
                                   "error", "compile", "wrong", "broken"]):
            needs["H4"] = 3  # Highest priority for repairs

        # H5 (Security): needed for security issues
        if any(kw in p for kw in ["security", "exploit", "vulnerability", "cve",
                                   "attack", "injection", "bypass", "auth"]):
            needs["H5"] = 3

        # H6 (Multi-language): needed for cross-language work
        if any(kw in p for kw in ["convert", "translate", "port", "rust", "python",
                                   "go", "multi"]):
            needs["H6"] = 1

        # Default: H4 (repair) + H1 (sandbox)
        if not needs:
            needs["H4"] = 2
            needs["H1"] = 1

        return needs

    # ── Subtask Generation ──────────────────────────────────────────────

    def _generate_subtasks(self, plan_id: str, problem: str,
                           horizon_needs: Dict[str, int]) -> List[SubTask]:
        """Generate subtasks from classified horizons."""
        subtasks = []
        idx = 0

        # H2 first: retrieve past solutions
        if "H2" in horizon_needs:
            idx += 1
            subtasks.append(SubTask(
                id=f"{plan_id}-s{idx}",
                description=f"Retrieve similar past solutions from memory",
                horizon="H2",
                required_tools=["memory_retrieve_solutions"],
                confidence=0.9,
            ))

        # H3: verify before evolving
        if "H3" in horizon_needs:
            idx += 1
            subtasks.append(SubTask(
                id=f"{plan_id}-s{idx}",
                description=f"Formally verify safety properties",
                horizon="H3",
                required_tools=["z3_verify_patch"],
                dependencies=[f"{plan_id}-s{idx-1}"] if idx > 1 else [],
                confidence=0.7,
            ))

        # H4: evolve patches
        if "H4" in horizon_needs:
            idx += 1
            subtasks.append(SubTask(
                id=f"{plan_id}-s{idx}",
                description=f"Evolve code patches via genetic algorithm",
                horizon="H4",
                required_tools=["genetic_evolve"],
                confidence=0.75,
            ))

        # H5: attack to test security
        if "H5" in horizon_needs:
            idx += 1
            subtasks.append(SubTask(
                id=f"{plan_id}-s{idx}",
                description=f"Red team attack + fuzzing campaign",
                horizon="H5",
                required_tools=["red_team_attack", "cve_scan"],
                dependencies=[f"{plan_id}-s{idx-1}"] if idx > 1 else [],
                confidence=0.8,
            ))

        # H1: sandbox execution (final validation)
        idx += 1
        subtasks.append(SubTask(
            id=f"{plan_id}-s{idx}",
            description=f"Execute and validate in sandbox",
            horizon="H1",
            required_tools=["sandbox_execute"],
            dependencies=[f"{plan_id}-s{idx-1}"],
            confidence=0.85,
        ))

        return subtasks

    # ── Agent Assignment ────────────────────────────────────────────────

    async def _assign_agents(self, subtasks: List[SubTask]) -> List[SubTask]:
        """Assign best agent for each subtask based on reputation."""
        if not self.reputation:
            return subtasks

        best = self.reputation.get_best_agents(min_reputation=0.3)

        for st in subtasks:
            # Try to find specialized agent
            horizon_agents = {
                "H1": "sandbox",
                "H2": "memory",
                "H3": "verifier",
                "H4": "evolution",
                "H5": "red_team",
                "H6": "multilang",
            }
            preferred = horizon_agents.get(st.horizon, "generic")

            # Pick best available
            for agent in best:
                if preferred in agent.lower() or agent == preferred:
                    st.agent = agent
                    break

            if not st.agent and best:
                st.agent = best[0]

        return subtasks

    # ── Topological Sort ────────────────────────────────────────────────

    def _topological_sort(self, subtasks: List[SubTask]) -> List[SubTask]:
        """Sort subtasks respecting dependencies."""
        id_to_task = {s.id: s for s in subtasks}
        visited = set()
        order = []

        def visit(task_id):
            if task_id in visited:
                return
            visited.add(task_id)
            task = id_to_task.get(task_id)
            if task:
                for dep_id in task.dependencies:
                    if dep_id in id_to_task:
                        visit(dep_id)
                order.append(task)

        for st in subtasks:
            visit(st.id)

        return order

    # ── Estimation ─────────────────────────────────────────────────────

    def _estimate_subtask_time(self, st: SubTask) -> float:
        """Estimate execution time in milliseconds."""
        estimates = {
            "H1": 5000,    # Sandbox: 5s
            "H2": 500,     # Memory: 500ms
            "H3": 10000,   # Formal verification: 10s
            "H4": 30000,   # Genetic evolution: 30s
            "H5": 15000,   # Security testing: 15s
            "H6": 3000,    # Multi-language: 3s
        }
        return estimates.get(st.horizon, 5000)

    def _calc_plan_confidence(self, subtasks: List[SubTask]) -> float:
        """Overall plan confidence."""
        if not subtasks:
            return 0.5
        return sum(s.confidence for s in subtasks) / len(subtasks)

    # ── LLM Refinement (Optional) ──────────────────────────────────────

    async def _llm_refine_plan(self, problem: str,
                                subtasks: List[SubTask]) -> Optional[List[SubTask]]:
        """Ask LLM to refine the plan (non-blocking)."""
        try:
            prompt = (
                f"Problem: {problem}\n\n"
                f"Current plan:\n" +
                "\n".join(f"- [{st.horizon}] {st.description}" for st in subtasks) +
                "\n\nSuggest refinements. Return JSON: {\"subtasks\": [{\"horizon\": \"H4\", \"description\": \"...\"}]}"
            )
            result = await self.mind._consult_llm(prompt)
            if result and result.get("subtasks"):
                new_sts = []
                for i, s in enumerate(result["subtasks"]):
                    new_sts.append(SubTask(
                        id=f"llm-{i}",
                        description=s.get("description", ""),
                        horizon=s.get("horizon", "H4"),
                        confidence=0.6,
                    ))
                return new_sts
        except Exception:
            pass
        return None

    # ── Stats ───────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        return {
            "reputation": self.reputation.get_stats() if self.reputation else {},
            "horizon_coverage": ["H1", "H2", "H3", "H4", "H5", "H6"],
        }
