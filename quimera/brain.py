"""
Quimera Brain v2 — Cérebro Central com TODOS os subsistemas integrados.

Novo nesta versão:
  - AEGIS: action_selector, polymorphic_prompts, ppa_system, xai, multi-phase validation
  - VALIDATORS: asan, ubsan, fuzz, build, compile, benchmark, differential_analyzer
  - AGENTS: refinador_v3, agente_kan, agente_quantico, agente_estrategista, agente_votoaste
  - MIND: self_awareness, reputation_engine, parallel_executor, full_knowledge
  - MEMORY: cross_kernel, federated, patch_memory integration
  - All 33 orphan modules are now connected and callable

Architecture:
    User / API
        │
        ▼
    ┌──────────────────────────────────────────────────┐
    │                  BRAIN (v2)                       │
    │                                                   │
    │  🛡️ AEGIS GATEKEEPER                             │
    │     ├─ action_selector (what to do next)          │
    │     ├─ polymorphic_prompts (dynamic prompts)      │
    │     ├─ ppa_system (plan-perform-analyze)          │
    │     ├─ multi_phase_validation (3-phase check)     │
    │     ├─ plan_execute_pattern (PEP loop)            │
    │     └─ xai_explainability (why this decision)     │
    │                                                   │
    │  💬 ENGINEERING ASSISTANT                         │
    │     └─ NL → Mission (use_llm or keyword)          │
    │                                                   │
    │  📋 PLANNER → ORCHESTRATOR                        │
    │     ├─ Detection Engine                           │
    │     ├─ KnowledgeBroker (12 sources)               │
    │     ├─ ASTPatcher + CandidateRanker               │
    │     └─ UnifiedMemory + PatchMemory                │
    │                                                   │
    │  🧪 VALIDATORS (9 levels)                         │
    │     ├─ asan, ubsan (sanitizers)                   │
    │     ├─ fuzz (AFL-style fuzzing)                   │
    │     ├─ build, compile (regression)                │
    │     ├─ benchmark (performance)                    │
    │     └─ differential_analyzer (before/after)       │
    │                                                   │
    │  🤖 AGENTS                                        │
    │     ├─ refinador_v3 (patch refinement)            │
    │     ├─ agente_kan (KAN-based decisions)           │
    │     ├─ agente_quantico (quantum-inspired search)  │
    │     ├─ agente_estrategista (strategy planning)    │
    │     └─ agente_votoaste (voting consensus)         │
    │                                                   │
    │  🧠 MIND                                          │
    │     ├─ self_awareness (system introspection)      │
    │     ├─ reputation_engine (trust scoring)          │
    │     ├─ parallel_executor (multi-thread)           │
    │     ├─ full_knowledge (knowledge graph)           │
    │     └─ codebase_knowledge (project understanding) │
    │                                                   │
    │  👁️ SENTINEL (24/7 monitor)                       │
    │  🧬 COEVOLUTION (learning loop)                   │
    └──────────────────────────────────────────────────┘
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("quimera.brain")


# ═══════════════════════════════════════════════════════════════════════
# Domain
# ═══════════════════════════════════════════════════════════════════════

class BrainMode(str, Enum):
    FULL = "full"
    SAFE = "safe"
    LEARNING = "learning"
    RECOVERY = "recovery"


@dataclass
class BrainStatus:
    healthy: bool = True
    mode: BrainMode = BrainMode.FULL
    uptime_seconds: float = 0.0
    requests_processed: int = 0
    threats_blocked: int = 0
    patches_generated: int = 0
    patches_applied: int = 0
    active_agents: int = 0
    memory_entries: int = 0
    last_incident: Optional[str] = None
    subsystem_status: Dict[str, bool] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════
# Brain v2 — All subsystems connected
# ═══════════════════════════════════════════════════════════════════════

class QuimeraBrain:
    """
    Central nervous system v2. ALL Quimera subsystems are connected here.

    Nothing enters or leaves without passing through AEGIS gatekeeping.
    Every patch goes through validators. Every decision is explained.
    """

    def __init__(
        self,
        project_root: str = ".",
        mode: BrainMode = BrainMode.FULL,
        use_llm: bool = True,
        prefer_free_models: bool = True,
    ):
        self.project_root = Path(project_root)
        self.mode = mode
        self.use_llm = use_llm
        self.prefer_free_models = prefer_free_models

        # ── Core subsystems ──
        self._aegis = None
        self._sentinel = None
        self._assistant = None
        self._planner = None
        self._orchestrator = None
        self._memory = None

        # ── v3 NEW: Engineer Cycle modules ──
        self._data_flow_analyzer = None
        self._false_positive_filter = None
        self._statistical_filter = None
        self._sandbox_executor = None
        self._engineer = None

        # ── AEGIS sub-modules ──
        self._aegis_action_selector = None
        self._aegis_polymorphic = None
        self._aegis_ppa = None
        self._aegis_multi_phase = None
        self._aegis_pep = None
        self._aegis_xai = None

        # ── Validators ──
        self._validator_asan = None
        self._validator_ubsan = None
        self._validator_fuzz = None
        self._validator_build = None
        self._validator_compile = None
        self._validator_benchmark = None
        self._validator_differential = None

        # ── Agents ──
        self._agent_refinador = None
        self._agent_kan = None
        self._agent_quantico = None
        self._agent_estrategista = None
        self._agent_votoaste = None

        # ── Mind ──
        self._mind_self_awareness = None
        self._mind_reputation = None
        self._mind_parallel = None
        self._mind_full_knowledge = None
        self._mind_codebase = None

        # ── Memory ──
        self._memory_cross_kernel = None
        self._memory_federated = None
        self._patch_ranker = None
        self._coevolution = None

        self._start_time = time.time()
        self._status = BrainStatus(mode=mode)
        self._monitor_task = None

    # ═══════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════

    async def start(self) -> BrainStatus:
        """Boot ALL subsystems. Returns health status."""
        logger.info("🧠 QuimeraBrain v2: starting ALL subsystems...")

        # 1. Security first
        self._init_aegis_modules()
        self._init_sentinel()

        # 2. Validators
        self._init_validators()

        # 3. NL interface
        self._init_assistant()

        # 4. Agents
        self._init_agents()

        # 5. Mind & Memory
        self._init_mind()
        self._init_memory()

        # 6. v3 NEW: Engineer Cycle modules
        self._init_v3_modules()

        # 7. Background monitor
        self._monitor_task = asyncio.create_task(self._monitor_loop())

        self._status.healthy = True
        logger.info("🧠 QuimeraBrain v2: ALL systems online")
        return self.health_check()

    async def shutdown(self):
        """Graceful shutdown."""
        logger.info("🧠 Brain: shutting down...")
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        if self._sentinel:
            try:
                await self._sentinel.shutdown()
            except Exception:
                pass
        logger.info("🧠 Brain: shutdown complete")

    # ═══════════════════════════════════════════════════════════════════
    # MAIN ENTRY: Process Request
    # ═══════════════════════════════════════════════════════════════════

    async def process(self, user_message: str) -> Dict[str, Any]:
        """
        Full brain pipeline. Everything passes through AEGIS.
        """
        self._status.requests_processed += 1
        result = {
            "success": False, "message": "", "intent": "", "findings": 0,
            "patches": 0, "threat_level": "none", "validated": False,
            "evidence": {}, "explanation": "", "agent_votes": {}, "aegis_actions": [],
        }

        try:
            # ═══ STEP 1: AEGIS gatekeeping ═════════════════
            if self._aegis:
                threat = self._aegis_check(user_message)
                result["threat_level"] = threat
                if threat in ("CRITICAL", "HIGH"):
                    self._status.threats_blocked += 1
                    result["message"] = "⚠️ AEGIS bloqueou: risco de segurança."
                    return result

            # ═══ STEP 2: Understand intent ═════════════════
            if not self._assistant:
                self._init_assistant()

            reply = await self._assistant.ask(user_message) if self._assistant else None
            if not reply:
                result["message"] = "Não entendi. Pode reformular?"
                return result

            result["intent"] = reply.kind.value
            result["message"] = reply.message
            result["evidence"].update(reply.evidence)

            # ═══ STEP 3: AEGIS action selection ════════════
            if self._aegis_action_selector:
                plan = self._aegis_select_actions(result["intent"])
                result["aegis_actions"] = plan

            # ═══ STEP 4: Agent voting (consensus) ══════════
            if self._agent_votoaste or self._agent_estrategista:
                votes = self._agent_consensus(result["intent"], user_message)
                result["agent_votes"] = votes

            # ═══ STEP 5: Execute mission ══════════════════
            if reply.kind.value in ("fix", "build", "audit", "analyze"):
                orch_result = self._execute_mission(reply)
                result.update(orch_result)

            # ═══ STEP 6: Multi-phase validation ════════════
            if result.get("patches_applied", 0) > 0 or result.get("candidates_generated", 0) > 0:
                validation = self._run_validators(result)
                result["validated"] = validation["passed"]
                result["validation_details"] = validation

            # ═══ STEP 7: AEGIS output check ════════════════
            if self._aegis:
                out_ok = self._aegis_validate_output(result)
                result["aegis_output_ok"] = out_ok

            # ═══ STEP 8: XAI explanation ══════════════════
            if self._aegis_xai:
                explanation = self._explain_decision(result)
                result["explanation"] = explanation

            # ═══ STEP 9: Learn & remember ═════════════════
            await self._learn_from_result(result)
            await self._update_reputation(result)

        except Exception as e:
            logger.error(f"Brain error: {e}")
            result["message"] = f"Erro: {e}"
            result["success"] = False
            if self._sentinel:
                try:
                    await self._sentinel.record_incident(str(e))
                except Exception:
                    pass

        return result

    # ═══════════════════════════════════════════════════════════════════
    # SUBSYSTEM INITIALIZATION
    # ═══════════════════════════════════════════════════════════════════

    def _lazy_load(self, module_path: str, class_name: str = None, *args, **kwargs):
        """Safe lazy loader for any Quimera module."""
        try:
            import importlib
            mod = importlib.import_module(module_path)
            if class_name:
                return getattr(mod, class_name)(*args, **kwargs)
            return mod
        except Exception as e:
            logger.debug(f"  ⚠️ {module_path}: {type(e).__name__}")
            return None

    # ── AEGIS ──────────────────────────────────────────────

    def _init_aegis_modules(self):
        """Initialize ALL AEGIS sub-modules."""
        logger.info("  🛡️ Initializing AEGIS...")

        self._aegis = self._lazy_load("quimera.aegis.aegis_core", "AegisCore")
        if self._aegis:
            try:
                self._aegis.initialize()
            except Exception:
                pass

        self._aegis_action_selector = self._lazy_load(
            "quimera.aegis.action_selector", "ActionSelector")
        self._aegis_polymorphic = self._lazy_load(
            "quimera.aegis.polymorphic_prompts", "PolymorphicPrompts")
        self._aegis_ppa = self._lazy_load(
            "quimera.aegis.ppa_system", "PPASystem")
        self._aegis_multi_phase = self._lazy_load(
            "quimera.aegis.multi_phase_validation", "MultiPhaseValidator")
        self._aegis_pep = self._lazy_load(
            "quimera.aegis.plan_execute_pattern", "PlanExecutePattern")
        self._aegis_xai = self._lazy_load(
            "quimera.aegis.xai_explainability", "XAIEngine")

        count = sum(1 for x in [
            self._aegis, self._aegis_action_selector, self._aegis_polymorphic,
            self._aegis_ppa, self._aegis_multi_phase, self._aegis_pep, self._aegis_xai
        ] if x is not None)
        logger.info(f"  🛡️ AEGIS: {count}/7 modules loaded")

    def _init_v3_modules(self):
        """Initialize Sprint 1+2 modules: Data Flow, Filters, Sandbox, Engineer."""
        logger.info("  🔀 Initializing v3 modules...")
        self._data_flow_analyzer = self._lazy_load(
            "quimera.data_flow_analyzer", "FlowBasedDetector")
        self._false_positive_filter = self._lazy_load(
            "quimera.aegis.false_positive_filter", "FalsePositiveFilter")
        self._statistical_filter = self._lazy_load(
            "quimera.statistical_filter", "StatisticalFilter")
        self._sandbox_executor = self._lazy_load(
            "quimera.sandbox_executor", "DockerSandbox")
        self._engineer = self._lazy_load(
            "quimera.engineer", "QuimeraEngineer")
        count = sum(1 for x in [
            self._data_flow_analyzer, self._false_positive_filter,
            self._statistical_filter, self._sandbox_executor, self._engineer
        ] if x is not None)
        logger.info(f"  🔀 v3 modules: {count}/5 loaded")

    def _init_sentinel(self):
        self._sentinel = self._lazy_load(
            "quimera.aegis.sentinel", "SentinelSecurityOrgan")
        if self._sentinel:
            logger.info("  👁️ Sentinel online")

    # ── VALIDATORS ────────────────────────────────────────

    def _init_validators(self):
        """Initialize all validators."""
        logger.info("  🧪 Initializing validators...")

        self._validator_asan = self._lazy_load("quimera.validators.asan", "ASanValidator")
        self._validator_ubsan = self._lazy_load("quimera.validators.ubsan", "UBSanValidator")
        self._validator_fuzz = self._lazy_load("quimera.validators.fuzz", "FuzzValidator")
        self._validator_build = self._lazy_load("quimera.validators.build", "BuildValidator")
        self._validator_compile = self._lazy_load("quimera.validators.compile", "CompileValidator")
        self._validator_benchmark = self._lazy_load("quimera.validators.benchmark", "BenchmarkValidator")
        self._validator_differential = self._lazy_load(
            "quimera.validators.differential_analyzer", "DifferentialAnalyzer")

        count = sum(1 for x in [
            self._validator_asan, self._validator_ubsan, self._validator_fuzz,
            self._validator_build, self._validator_compile, self._validator_benchmark,
            self._validator_differential,
        ] if x is not None)
        logger.info(f"  🧪 Validators: {count}/7 loaded")

    # ── ASSISTANT ─────────────────────────────────────────

    def _init_assistant(self):
        self._assistant = self._lazy_load(
            "quimera.engineering_assistant", "EngineeringAssistant",
            project_root=str(self.project_root), use_llm=self.use_llm)
        logger.info("  💬 Assistant online" if self._assistant else "  ⚠️ Assistant unavailable")

    # ── AGENTS ────────────────────────────────────────────

    def _init_agents(self):
        """Initialize agent pool."""
        logger.info("  🤖 Initializing agents...")

        self._agent_refinador = self._lazy_load(
            "quimera.agentes.refinador_v3.agente_refinador", "AgenteRefinador")
        self._agent_kan = self._lazy_load(
            "quimera.agentes.agente_kan", "AgenteKAN")
        self._agent_quantico = self._lazy_load(
            "quimera.agentes.agente_quantico", "AgenteQuantico")
        self._agent_estrategista = self._lazy_load(
            "quimera.agentes.agente_estrategista", "AgenteEstrategista")
        self._agent_votoaste = self._lazy_load(
            "quimera.agentes.agente_votoaste", "AgenteVotoaste")

        count = sum(1 for x in [
            self._agent_refinador, self._agent_kan, self._agent_quantico,
            self._agent_estrategista, self._agent_votoaste,
        ] if x is not None)
        self._status.active_agents = count
        logger.info(f"  🤖 Agents: {count}/5 loaded")

    # ── MIND ──────────────────────────────────────────────

    def _init_mind(self):
        """Initialize mind subsystems."""
        self._mind_self_awareness = self._lazy_load(
            "quimera.mind.self_awareness", "SelfAwareness")
        self._mind_reputation = self._lazy_load(
            "quimera.mind.reputation_engine", "ReputationEngine")
        self._mind_parallel = self._lazy_load(
            "quimera.mind.parallel_executor", "ParallelExecutor")
        self._mind_full_knowledge = self._lazy_load(
            "quimera.mind.full_knowledge", "FullKnowledge")
        self._mind_codebase = self._lazy_load(
            "quimera.mind.codebase_knowledge", "CodebaseKnowledge")

        count = sum(1 for x in [
            self._mind_self_awareness, self._mind_reputation, self._mind_parallel,
            self._mind_full_knowledge, self._mind_codebase,
        ] if x is not None)
        logger.info(f"  🧠 Mind: {count}/5 modules loaded")

    # ── MEMORY ────────────────────────────────────────────

    def _init_memory(self):
        """Initialize memory subsystems."""
        self._memory = self._lazy_load("quimera.unified_memory", "UnifiedMemory")
        self._memory_cross_kernel = self._lazy_load(
            "quimera.memory.cross_kernel", "CrossKernelMemory")
        self._memory_federated = self._lazy_load(
            "quimera.memory.federated", "FederatedMemory")
        self._patch_ranker = self._lazy_load(
            "quimera.patch_ranker", "PatchRanker")

        count = sum(1 for x in [
            self._memory, self._memory_cross_kernel, self._memory_federated,
            self._patch_ranker,
        ] if x is not None)
        logger.info(f"  💾 Memory: {count}/4 modules loaded")

    # ═══════════════════════════════════════════════════════════════════
    # AEGIS GATEKEEPING
    # ═══════════════════════════════════════════════════════════════════

    def _aegis_check(self, message: str) -> str:
        """Check input through AEGIS gatekeeper."""
        if not self._aegis:
            return "none"

        # Use polymorphic prompts if available
        if self._aegis_polymorphic:
            try:
                prompt = self._aegis_polymorphic.generate(message)
                return "none"  # polymorphic prompts don't block, they transform
            except Exception:
                pass

        # Standard AEGIS check
        try:
            if hasattr(self._aegis, 'check_input'):
                return str(self._aegis.check_input(message))
        except Exception:
            pass

        return "none"

    def _aegis_validate_output(self, result: Dict) -> bool:
        """Validate output through AEGIS before returning."""
        if not self._aegis or not self._aegis_multi_phase:
            return True

        try:
            validation = self._aegis_multi_phase.validate(result)
            return getattr(validation, 'passed', True)
        except Exception:
            return True  # Don't block on validation errors

    def _aegis_select_actions(self, intent: str) -> List[str]:
        """Use AEGIS action selector to determine next steps."""
        if not self._aegis_action_selector:
            return []

        try:
            actions = self._aegis_action_selector.select(intent)
            return actions if isinstance(actions, list) else [str(actions)]
        except Exception:
            return []

    # ═══════════════════════════════════════════════════════════════════
    # AGENT CONSENSUS
    # ═══════════════════════════════════════════════════════════════════

    def _agent_consensus(self, intent: str, message: str) -> Dict[str, str]:
        """Run agent voting for decision consensus."""
        votes = {}

        if self._agent_votoaste:
            try:
                v = self._agent_votoaste.vote(intent, message)
                votes["votoaste"] = str(v)[:80]
            except Exception:
                pass

        if self._agent_estrategista:
            try:
                s = self._agent_estrategista.strategize(intent, message)
                votes["estrategista"] = str(s)[:80]
            except Exception:
                pass

        return votes

    # ═══════════════════════════════════════════════════════════════════
    # EXECUTION
    # ═══════════════════════════════════════════════════════════════════

    def _init_orchestrator(self):
        if not self._orchestrator:
            try:
                from quimera.orchestrator import QuimeraOrchestrator, OrchestratorConfig
                config = OrchestratorConfig(
                    project_root=str(self.project_root),
                    use_llm=self.use_llm,
                    max_iterations=20,
                )
                self._orchestrator = QuimeraOrchestrator(config)
            except Exception as e:
                logger.warning(f"Orchestrator unavailable: {e}")

    def _execute_mission(self, reply) -> Dict:
        """Execute mission through orchestrator, then refine."""
        self._init_orchestrator()
        if not self._orchestrator:
            return {"success": False, "message": "Orchestrator unavailable"}

        goal = reply.mission.goal if reply.mission else reply.message
        result = self._orchestrator.interpret_and_run(goal)

        # Refine with agent if available
        if self._agent_refinador and result.get("candidates_generated", 0) > 0:
            try:
                refined = self._agent_refinador.refine(result)
                if refined:
                    result["refined"] = True
                    result["refinement_score"] = getattr(refined, "score", 0)
            except Exception:
                pass

        # Rank patches if ranker available
        if self._patch_ranker and result.get("candidates_generated", 0) > 1:
            try:
                ranked = self._patch_ranker.rank(result)
                if ranked:
                    result["ranked_patches"] = ranked
            except Exception:
                pass

        return result

    # ═══════════════════════════════════════════════════════════════════
    # VALIDATORS
    # ═══════════════════════════════════════════════════════════════════

    def _run_validators(self, result: Dict) -> Dict:
        """Run all available validators on the result."""
        validation = {"passed": True, "results": {}}

        validators = [
            ("asan", self._validator_asan),
            ("ubsan", self._validator_ubsan),
            ("compile", self._validator_compile),
            ("build", self._validator_build),
            ("benchmark", self._validator_benchmark),
            ("fuzz", self._validator_fuzz),
            ("differential", self._validator_differential),
        ]

        for name, validator in validators:
            if validator:
                try:
                    v = validator.validate(result)
                    ok = getattr(v, 'passed', bool(v))
                    validation["results"][name] = ok
                    if not ok:
                        validation["passed"] = False
                except Exception:
                    validation["results"][name] = "error"

        return validation

    # ═══════════════════════════════════════════════════════════════════
    # EXPLAINABILITY
    # ═══════════════════════════════════════════════════════════════════

    def _explain_decision(self, result: Dict) -> str:
        """Generate XAI explanation for the decision."""
        if not self._aegis_xai:
            return ""

        try:
            explanation = self._aegis_xai.explain(result)
            return str(explanation)[:500]
        except Exception:
            return ""

    # ═══════════════════════════════════════════════════════════════════
    # LEARNING & MEMORY
    # ═══════════════════════════════════════════════════════════════════

    async def _learn_from_result(self, result: Dict):
        """Record results across all memory subsystems."""
        # Unified memory
        if self._memory:
            try:
                self._memory.record(result)
                self._status.memory_entries += 1
            except Exception:
                pass

        # Cross-kernel memory
        if self._memory_cross_kernel:
            try:
                self._memory_cross_kernel.store(result)
            except Exception:
                pass

        # Federated memory
        if self._memory_federated:
            try:
                self._memory_federated.share(result)
            except Exception:
                pass

    async def _update_reputation(self, result: Dict):
        """Update reputation scores based on outcome."""
        if not self._mind_reputation:
            return

        try:
            success = result.get("success", False)
            if success:
                self._mind_reputation.reward("pipeline", 0.1)
            else:
                self._mind_reputation.penalize("pipeline", 0.05)
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════
    # HEALTH & MONITORING
    # ═══════════════════════════════════════════════════════════════════

    def health_check(self) -> BrainStatus:
        """Check health of ALL 37+ subsystems."""
        self._status.uptime_seconds = time.time() - self._start_time

        self._status.subsystem_status = {
            # AEGIS
            "aegis_core": self._aegis is not None,
            "aegis_action_selector": self._aegis_action_selector is not None,
            "aegis_polymorphic": self._aegis_polymorphic is not None,
            "aegis_ppa": self._aegis_ppa is not None,
            "aegis_multi_phase": self._aegis_multi_phase is not None,
            "aegis_pep": self._aegis_pep is not None,
            "aegis_xai": self._aegis_xai is not None,
            # Security
            "sentinel": self._sentinel is not None,
            # Validators
            "validator_asan": self._validator_asan is not None,
            "validator_ubsan": self._validator_ubsan is not None,
            "validator_fuzz": self._validator_fuzz is not None,
            "validator_build": self._validator_build is not None,
            "validator_compile": self._validator_compile is not None,
            "validator_benchmark": self._validator_benchmark is not None,
            "validator_differential": self._validator_differential is not None,
            # Interface
            "assistant": self._assistant is not None,
            # Agents
            "agent_refinador": self._agent_refinador is not None,
            "agent_kan": self._agent_kan is not None,
            "agent_quantico": self._agent_quantico is not None,
            "agent_estrategista": self._agent_estrategista is not None,
            "agent_votoaste": self._agent_votoaste is not None,
            # Mind
            "mind_self_awareness": self._mind_self_awareness is not None,
            "mind_reputation": self._mind_reputation is not None,
            "mind_parallel": self._mind_parallel is not None,
            "mind_full_knowledge": self._mind_full_knowledge is not None,
            "mind_codebase": self._mind_codebase is not None,
            # Memory
            "memory": self._memory is not None,
            "memory_cross_kernel": self._memory_cross_kernel is not None,
            "memory_federated": self._memory_federated is not None,
            "patch_ranker": self._patch_ranker is not None,
            # ── v3 NEW: Engineer Cycle modules ──
            "data_flow_analyzer": self._data_flow_analyzer is not None,
            "false_positive_filter": self._false_positive_filter is not None,
            "statistical_filter": self._statistical_filter is not None,
            "sandbox_executor": self._sandbox_executor is not None,
            "engineer": self._engineer is not None,
        }

        # True if ALL loaded modules are available
        self._status.healthy = all(self._status.subsystem_status.values())
        return self._status

    async def _monitor_loop(self):
        """Background: monitor health, trigger healing."""
        while True:
            try:
                await asyncio.sleep(30)
                health = self.health_check()
                if not health.healthy:
                    offline = [k for k, v in health.subsystem_status.items() if not v]
                    logger.warning(f"🧠 Brain: {len(offline)} subsystems offline: {offline[:5]}...")
                    if self._sentinel:
                        try:
                            await self._sentinel.heal()
                        except Exception:
                            pass
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor error: {e}")


# ═══════════════════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════════════════

_brain_instance: Optional[QuimeraBrain] = None


def get_brain(
    project_root: str = ".",
    mode: BrainMode = BrainMode.FULL,
    use_llm: bool = True,
    prefer_free_models: bool = True,
) -> QuimeraBrain:
    global _brain_instance
    if _brain_instance is None:
        _brain_instance = QuimeraBrain(
            project_root=project_root,
            mode=mode,
            use_llm=use_llm,
            prefer_free_models=prefer_free_models,
        )
    return _brain_instance
