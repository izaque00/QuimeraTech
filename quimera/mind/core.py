"""
Quimera Mark X — Mind Core (Consciência Central)

The autonomous brain of Quimera. Not a classifier, not a chatbot wrapper —
a genuine operational consciousness that:

  1. Knows 100% of its own codebase (via RAG index + dependency graph)
  2. Self-diagnoses via log/exception/metric monitoring
  3. Proactively detects and repairs issues before they escalate
  4. Uses ALL internal engines (H1-H6) as tools via deep tool use
  5. Maintains persistent state across sessions (via H2 memory)
  6. Makes autonomous decisions based on confidence thresholds

Architecture:
    ┌──────────────────────────────────────────────────────┐
    │                   QuimeraMind                         │
    │  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
    │  │ SelfAwareness│  │ Codebase     │  │ Autonomy   │ │
    │  │ (diagnosis)  │  │ Knowledge    │  │ Engine     │ │
    │  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘ │
    │         │                 │                 │        │
    │  ┌──────▼─────────────────▼─────────────────▼──────┐ │
    │  │              Deep Tool Use                       │ │
    │  │  H1:Orchestrator  H2:Memory  H3:Z3  H4:Genetic  │ │
    │  │  H5:RedTeam       H6:Multi   Sandbox  DB        │ │
    │  └─────────────────────────────────────────────────┘ │
    │  ┌─────────────────────────────────────────────────┐ │
    │  │           Persistent State (H2 Memory)           │ │
    │  │  Context · History · Decisions · Learning       │ │
    │  └─────────────────────────────────────────────────┘ │
    └──────────────────────────────────────────────────────┘

Usage:
    mind = QuimeraMind()
    await mind.initialize()  # Index codebase + load state
    
    # Conversational
    response = await mind.process("Qual agente corrige buffer overflow?")
    
    # Autonomous (runs continuously)
    await mind.autopilot()
"""

import asyncio
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("quimera.mind")


# ═══════════════════════════════════════════════════════════════════════════
# Enums & State
# ═══════════════════════════════════════════════════════════════════════════

class MindState(str, Enum):
    INITIALIZING = "initializing"
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    REPAIRING = "repairing"
    LEARNING = "learning"
    ALERTING = "alerting"
    ERROR = "error"
    SHUTDOWN = "shutdown"


class ActionType(str, Enum):
    QUERY = "query"          # Just answering a question
    DIAGNOSE = "diagnose"   # Investigating an issue
    REPAIR = "repair"        # Fixing code
    OPTIMIZE = "optimize"   # Performance improvement
    SECURE = "secure"        # Security hardening
    LEARN = "learn"          # Updating knowledge
    ALERT = "alert"          # Notifying user
    DEPLOY = "deploy"        # Applying to production


class Confidence(str, Enum):
    HIGH = "high"       # 90%+ confident — auto-execute
    MEDIUM = "medium"   # 60-90% — suggest with reasoning
    LOW = "low"         # 30-60% — ask for confirmation
    UNCERTAIN = "uncertain"  # <30% — more investigation needed


@dataclass
class MindContext:
    """Persistent state across sessions."""
    session_id: str = ""
    state: MindState = MindState.IDLE
    last_action: Optional[str] = None
    last_action_time: str = ""
    total_actions: int = 0
    total_repairs: int = 0
    total_security_fixes: int = 0
    active_issues: List[Dict] = field(default_factory=list)
    recent_decisions: List[Dict] = field(default_factory=list)
    knowledge_version: str = ""
    uptime_start: str = ""


@dataclass
class Thought:
    """A single thought/decision by the Mind."""
    id: str
    type: ActionType
    reasoning: str
    confidence: Confidence
    plan: List[str]
    tool_calls: List[Dict]
    expected_outcome: str
    timestamp: str


# ═══════════════════════════════════════════════════════════════════════════
# Tool Registry — All H1-H6 engines exposed as callable tools
# ═══════════════════════════════════════════════════════════════════════════

class ToolRegistry:
    """Registry of all internal engines callable by the Mind.

    Each tool has:
      - name: Unique identifier
      - description: What it does, when to use it
      - horizon: Which horizon it belongs to
      - fn: Async callable
      - required_context: What context it needs
    """

    def __init__(self):
        self._tools: Dict[str, Dict] = {}
        self._register_all()

    def _register_all(self):
        """Register all H1-H6 tools."""
        # H1: Distributed Platform
        self.register(
            name="orchestrator_submit_mission",
            description="Submit a repair mission for a tenant. Use when user asks to fix code.",
            horizon="H1",
            fn_name="quimera.distributed.orchestrator:DistributedOrchestrator.submit_mission",
            required_context=["tenant_id", "code", "error_description"],
        )
        self.register(
            name="orchestrator_get_worker_status",
            description="Get cluster health and worker status. Use for system diagnostics.",
            horizon="H1",
            fn_name="quimera.distributed.orchestrator:DistributedOrchestrator.get_cluster_stats",
            required_context=[],
        )
        self.register(
            name="scaler_evaluate",
            description="Evaluate if scaling is needed. Use when load changes.",
            horizon="H1",
            fn_name="quimera.distributed.scaler:AutoScaler.evaluate",
            required_context=[],
        )

        # H2: Memory
        self.register(
            name="memory_retrieve_solutions",
            description="Search past successful repairs for similar errors. Use FIRST before attempting any fix.",
            horizon="H2",
            fn_name="quimera.memory.memory_engine:MemoryEngine.retrieve_solutions",
            required_context=["error_description", "error_type"],
        )
        self.register(
            name="memory_record_outcome",
            description="Record repair result for future learning. Use after every repair attempt.",
            horizon="H2",
            fn_name="quimera.memory.integration:MemoryPipeline.record_outcome",
            required_context=["mission_id", "context", "solution", "success"],
        )
        self.register(
            name="federated_knowledge",
            description="Query privacy-preserved knowledge from other tenants. Use when local memory insufficient.",
            horizon="H2",
            fn_name="quimera.memory.federated:FederatedMemory.fetch_global_knowledge",
            required_context=["query", "domain"],
        )

        # H3: Formal Verification
        self.register(
            name="z3_verify_patch",
            description="Formally prove a patch is correct using Z3 theorem prover. Use for safety-critical code.",
            horizon="H3",
            fn_name="quimera.integration_backends.z3_analyst:Z3Analyst.verify_patch",
            required_context=["patch_code", "original_code"],
        )
        self.register(
            name="cbmc_bounded_check",
            description="Bounded model checking via CBMC. Use for C code with loops/buffers.",
            horizon="H3",
            fn_name="quimera.integration_backends.cb_wrapper:CBMCWrapper.run_bounded_check",
            required_context=["c_code", "unwind_bound"],
        )

        # H4: Genetic Evolution
        self.register(
            name="genetic_evolve",
            description="Evolve a population of patches using NSGA-II. Use when deterministic repair fails.",
            horizon="H4",
            fn_name="quimera.horizons.h4_evolution.genetic_patch_engine:GeneticPatchEngine.evolve",
            required_context=["original_code", "error_context"],
        )
        self.register(
            name="coevolution_attack",
            description="Coevolve patches and tests adversarially. Use for critical patches needing robustness.",
            horizon="H4",
            fn_name="quimera.horizons.h4_evolution.coevolution_engine:CoevolutionEngine.coevolve",
            required_context=["original_code", "error_context"],
        )

        # H5: Security
        self.register(
            name="red_team_attack",
            description="Generate exploits to test a patch before release. Use on every patch before deployment.",
            horizon="H5",
            fn_name="quimera.horizons.h5_security.red_team:RedTeam.attack",
            required_context=["patched_code"],
        )
        self.register(
            name="fuzzing_campaign",
            description="Run mutation fuzzing against code. Use for robustness testing.",
            horizon="H5",
            fn_name="quimera.horizons.h5_security.fuzzing_engine:FuzzingEngine.fuzz",
            required_context=["code"],
        )
        self.register(
            name="cve_scan",
            description="Check if code is affected by known CVEs. Use for security audits.",
            horizon="H5",
            fn_name="quimera.seguranca.cve_monitor:CVEMonitor.scan_for_relevant_cves",
            required_context=["target_file"],
        )
        self.register(
            name="supply_chain_check",
            description="Verify dependencies and licenses. Use for third-party code integration.",
            horizon="H5",
            fn_name="quimera.seguranca.cve_monitor:SupplyChainChecker.check",
            required_context=["file_path", "code"],
        )

        # H6: Multi-Language
        self.register(
            name="multi_lang_repair",
            description="Repair code in any supported language (C, Rust, Go, Python).",
            horizon="H6",
            fn_name="quimera.plugins.multi_lang_orchestrator:MultiLangOrchestrator.repair",
            required_context=["code", "language", "error_description"],
        )

        # Core tools
        self.register(
            name="sandbox_execute",
            description="Execute code safely in sandbox. Use for testing patches.",
            horizon="core",
            fn_name="quimera.sandbox.manager:SandboxManager.run_safely",
            required_context=["code", "language"],
        )
        self.register(
            name="knowledge_base_query",
            description="Query the knowledge base for documentation/patterns. Use for understanding error types.",
            horizon="core",
            fn_name="quimera.core.knowledge_base:KnowledgeBase.query",
            required_context=["query"],
        )
        self.register(
            name="codebase_search",
            description="Search the entire codebase for patterns, functions, or imports.",
            horizon="mind",
            fn_name="quimera.mind.codebase_knowledge:CodebaseKnowledge.search",
            required_context=["query"],
        )

    def register(self, name: str, description: str, horizon: str, fn_name: str, required_context: List[str]):
        self._tools[name] = {
            "name": name,
            "description": description,
            "horizon": horizon,
            "fn_name": fn_name,
            "required_context": required_context,
        }

    def get_tool(self, name: str) -> Optional[Dict]:
        return self._tools.get(name)

    def find_tools(self, intent: str, required_horizon: Optional[str] = None) -> List[Dict]:
        """Find relevant tools for a given intent."""
        matches = []
        intent_lower = intent.lower()
        for tool in self._tools.values():
            if required_horizon and tool["horizon"] != required_horizon:
                continue
            if any(word in intent_lower for word in tool["description"].lower().split()):
                matches.append(tool)
        if not matches:
            matches = list(self._tools.values())
        return matches

    def list_all(self) -> List[Dict]:
        return list(self._tools.values())

    def tool_count(self) -> int:
        return len(self._tools)


# ═══════════════════════════════════════════════════════════════════════════
# Quimera Mind — The Central Consciousness
# ═══════════════════════════════════════════════════════════════════════════

class QuimeraMind:
    """The autonomous brain of the Quimera platform.

    Not a simple intent classifier — a genuine operational consciousness
    that knows its entire codebase, self-diagnoses, and acts autonomously.

    Lifecycle:
      1. initialize() — Index codebase, load memory state
      2. perceive() — Monitor logs, metrics, exceptions
      3. think() — Analyze situation, create plan
      4. act() — Execute plan via tool use
      5. learn() — Record outcome for future
    """

    def __init__(
        self,
        workspace_path: Optional[str] = None,
        autopilot_enabled: bool = True,
        auto_repair_threshold: Confidence = Confidence.HIGH,
        alert_on_repair: bool = True,
        llm_provider: Optional[str] = None,  # "ollama", "openai", "anthropic", "groq"
        llm_model: Optional[str] = None,     # "qwen3", "gpt-4o", "claude-sonnet-4-20250514"
        llm_temperature: float = 0.3,
    ):
        self.workspace_path = workspace_path or os.getcwd()
        self.autopilot_enabled = autopilot_enabled
        self.auto_repair_threshold = auto_repair_threshold
        self.alert_on_repair = alert_on_repair
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.llm_temperature = llm_temperature

        # Core components (initialized in initialize())
        self.tools: ToolRegistry = ToolRegistry()
        self.state: MindState = MindState.INITIALIZING
        self.context: MindContext = MindContext(
            session_id=f"mind-{int(time.time())}",
            uptime_start=datetime.now(timezone.utc).isoformat(),
        )

        # Lazy-loaded engines
        self._knowledge: Optional[Any] = None      # CodebaseKnowledge
        self._awareness: Optional[Any] = None      # SelfAwareness
        self._autonomy: Optional[Any] = None       # AutonomousEngine
        self._memory: Optional[Any] = None         # MemoryPipeline
        self._llm: Optional[Any] = None            # LLMAdviser (opcional)
        
        # P3 Intelligence engines
        self._reputation: Optional[Any] = None     # ReputationEngine
        self._planner: Optional[Any] = None        # QuimeraPlanner
        self._executor: Optional[Any] = None       # ParallelExecutor

        # State tracking
        self._action_history: List[Thought] = []
        self._pending_issues: List[Dict] = []

        logger.info(f"QuimeraMind initialized (autopilot={autopilot_enabled})")
        logger.info(f"  Tools available: {self.tools.tool_count()} across H1-H6 + core")

    # ═══════════════════════════════════════════════════════════════════
    # Lifecycle
    # ═══════════════════════════════════════════════════════════════════

    async def initialize(self) -> "QuimeraMind":
        """Full initialization: index codebase, load state, start monitoring."""
        logger.info("QuimeraMind: initializing...")
        self.state = MindState.INITIALIZING

        # 1. Index codebase knowledge
        from .codebase_knowledge import CodebaseKnowledge
        self._knowledge = CodebaseKnowledge(self.workspace_path)
        await self._knowledge.index()
        self.context.knowledge_version = self._knowledge.version
        logger.info(f"  Codebase indexed: {self._knowledge.file_count} files, {self._knowledge.symbol_count} symbols")

        # 1b. Initialize Reputation Engine (P3)
        from .reputation_engine import ReputationEngine
        self._reputation = ReputationEngine()
        logger.info(f"  Reputation engine: online — {self._reputation.get_stats()['total_actions']} past actions")

        # Initialize AgentRegistry
        from .agent_registry import AgentRegistry
        self._agent_registry = AgentRegistry
        logger.info(f"  AgentRegistry: {AgentRegistry.count()} agents mapped to H1-H6")

        # 1c. Initialize Planner (P3)
        from .planner import QuimeraPlanner
        self._planner = QuimeraPlanner(mind=self, reputation_engine=self._reputation)
        logger.info("  Planner: ready")

        # 1d. Initialize Parallel Executor (P3)
        from .parallel_executor import ParallelExecutor
        self._executor = ParallelExecutor(engine=None, reputation=self._reputation, max_parallel=5)
        # Will be wired to AutonomousEngine after step 3
        logger.info("  Executor: ready (max_parallel=5)")

        # 2. Initialize self-awareness
        from .self_awareness import SelfAwareness
        self._awareness = SelfAwareness(self)
        await self._awareness.start()
        logger.info("  Self-awareness: online")

        # 3. Initialize autonomous engine
        from .autonomous_engine import AutonomousEngine
        self._autonomy = AutonomousEngine(self)
        logger.info("  Autonomous engine: ready")
        
        # Wire executor to AutonomousEngine (P3)
        self._executor.engine = self._autonomy

        # 3b. Initialize Full Knowledge (all file types)
        from .full_knowledge import FullCodebaseKnowledge
        self._full_knowledge = FullCodebaseKnowledge(self.workspace_path)
        await self._full_knowledge.index()
        logger.info(f"  Full knowledge: {self._full_knowledge.file_count} files indexed")

        # 3b2. Initialize Bibliotecario
        try:
            from quimera.bibliotecario.cognitive_librarian_ultra_advanced import CognitiveLibrarian
            self._librarian = CognitiveLibrarian()
            await self._librarian.initialize()
            logger.info("  Bibliotecario: online")
        except Exception:
            self._librarian = None

        # 3c. Initialize LLM Adviser (optional, user-controlled)
        if self.llm_provider:
            try:
                from .llm_adviser import LLMAdviser
                self._llm = LLMAdviser(
                    provider=self.llm_provider,
                    model=self.llm_model,
                    temperature=self.llm_temperature,
                )
                available = await self._llm.health_check()
                if available:
                    logger.info(f"  LLM Adviser: connected ({self.llm_provider}/{self.llm_model or 'default'})")
                else:
                    logger.warning(f"  LLM Adviser: unavailable — deterministic only")
                    self._llm = None
            except Exception as e:
                logger.warning(f"  LLM Adviser: failed to load ({e}) — deterministic only")
                self._llm = None
        else:
            logger.info("  LLM Adviser: disabled (deterministic mode)")

        # 4. Load persistent memory
        try:
            from quimera.memory.integration import MemoryPipeline
            self._memory = MemoryPipeline(auto_record=True)
            logger.info("  Memory pipeline: connected")
        except Exception as e:
            logger.warning(f"  Memory pipeline: unavailable ({e})")

        # 5. Health check
        health = await self._awareness.health_check()
        self.context.active_issues = health.get("issues", [])

        self.state = MindState.IDLE
        logger.info(f"QuimeraMind: initialized — {self.tools.tool_count()} tools, state={self.state.value}")
        return self

    # ═══════════════════════════════════════════════════════════════════
    # Main Loop: Perceive → Think → Act → Learn
    # ═══════════════════════════════════════════════════════════════════

    async def process(self, user_input: Optional[str] = None) -> Dict[str, Any]:
        """Main entry point. Handles both conversational and autonomous modes.

        If user_input is None, runs autonomous perception→action cycle.
        """
        # 1. PERCEIVE: Gather state
        perception = await self._perceive(user_input)

        # 2. Auto-diagnose (always runs)
        if self.autopilot_enabled and self._awareness:
            issues = await self._awareness.detect_issues()
            if issues:
                self._pending_issues = issues
                if not user_input:
                    # Autonomous mode: handle issues proactively
                    return await self._handle_autonomous(issues)

        # 3. THINK: Analyze and plan
        thought = await self._think(user_input, perception)

        # 4. ACT: Execute the plan
        result = await self._act(thought)

        # 5. LEARN: Record for future
        await self._learn(thought, result)

        return result

    async def _perceive(self, user_input: Optional[str]) -> Dict[str, Any]:
        """Gather all relevant state."""
        perception = {
            "user_input": user_input,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mind_state": self.state.value,
            "pending_issues": len(self._pending_issues),
            "action_count": self.context.total_actions,
        }

        # Codebase awareness
        if self._knowledge:
            perception["codebase"] = {
                "files": self._knowledge.file_count,
                "symbols": self._knowledge.symbol_count,
            }

        # System health
        if self._awareness:
            perception["health"] = await self._awareness.health_check()

        return perception

    async def _think(
        self, user_input: Optional[str], perception: Dict
    ) -> Thought:
        """Analyze the situation and create a plan of action.

        Flow:
        1. Deterministic analysis (always runs)
        2. If confidence < MEDIUM and LLM is available → consult IA
        3. IA suggestion is VALIDATED (never trusted blindly)
        4. Returns the best plan available
        """
        self.state = MindState.THINKING

        if user_input:
            thought = await self._think_conversational(user_input, perception)
        else:
            thought = await self._think_autonomous(perception)

        # ═══ LLM ADVISER: Consult IA when deterministic confidence is LOW ═══
        if self._llm and self._should_consult_llm(thought):
            try:
                llm_enhanced = await self._consult_llm(thought, user_input, perception)
                if llm_enhanced:
                    logger.info(
                        f"  LLM Adviser: enhanced plan — "
                        f"confidence {thought.confidence.value} → {llm_enhanced.confidence.value}, "
                        f"tools {len(thought.tool_calls)} → {len(llm_enhanced.tool_calls)}"
                    )
                    thought = llm_enhanced
            except Exception as e:
                logger.warning(f"  LLM Adviser: consultation failed ({e}) — using deterministic plan")

        return thought

    def _should_consult_llm(self, thought: Thought) -> bool:
        """Decide if LLM consultation is warranted.
        
        Rules:
        - LOW/UNCERTAIN confidence → always consult
        - MEDIUM with complex problem (>1 tool needed) → consult
        - HIGH confidence → skip (deterministic is enough)
        """
        if not self._llm:
            return False
        if thought.confidence in (Confidence.LOW, Confidence.UNCERTAIN):
            return True
        if thought.confidence == Confidence.MEDIUM and len(thought.tool_calls) > 1:
            return True
        return False

    async def _consult_llm(
        self, deterministic_thought: Thought, user_input: Optional[str], perception: Dict
    ) -> Optional[Thought]:
        """Consult LLM for a better plan. The LLM is an ADVISER — Mind decides."""
        if not self._llm:
            return None

        # Build context for LLM
        context = {
            "user_input": user_input or "Autonomous repair",
            "deterministic_plan": {
                "intent": deterministic_thought.type.value,
                "confidence": deterministic_thought.confidence.value,
                "tools": [tc["tool"] for tc in deterministic_thought.tool_calls],
                "reasoning": deterministic_thought.reasoning,
            },
            "codebase": perception.get("codebase", {}),
            "pending_issues": [
                {"type": i.get("type"), "severity": i.get("severity")}
                for i in self._pending_issues[:3]
            ],
            "available_tools": self.tools.list_tools(),
        }

        try:
            advice = await self._llm.advise(context)
        except Exception:
            return None

        if not advice or not advice.get("tools"):
            return None

        # Validate: every tool suggested MUST exist in ToolRegistry
        validated_tools = []
        for tool_name in advice.get("tools", [])[:4]:
            tool = self.tools.get_tool(tool_name)
            if tool:
                validated_tools.append({
                    "tool": tool_name,
                    "horizon": tool["horizon"],
                    "reason": f"LLM suggested: {advice.get('reasoning', 'no reasoning provided')[:80]}",
                })

        if not validated_tools:
            logger.warning("  LLM Adviser: suggested tools not found in registry — ignoring")
            return None

        # Build enhanced thought (confidence boosted if LLM was confident)
        llm_confidence_str = advice.get("confidence", "medium")
        confidence_map = {
            "high": Confidence.HIGH, "medium": Confidence.MEDIUM,
            "low": Confidence.LOW, "uncertain": Confidence.UNCERTAIN,
        }
        new_confidence = confidence_map.get(llm_confidence_str.lower(), Confidence.MEDIUM)

        # Never let LLM override to HIGH if deterministic was UNCERTAIN
        if deterministic_thought.confidence == Confidence.UNCERTAIN and new_confidence == Confidence.HIGH:
            new_confidence = Confidence.MEDIUM

        new_thought_id = f"llm-{int(time.time() * 1000)}"
        return Thought(
            id=new_thought_id,
            type=deterministic_thought.type,
            reasoning=f"[LLM-Enhanced] {advice.get('reasoning', 'IA suggested approach')[:300]}",
            confidence=new_confidence,
            plan=[tc["tool"] for tc in validated_tools],
            tool_calls=validated_tools,
            expected_outcome=advice.get("expected_outcome", deterministic_thought.expected_outcome),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    async def _think_conversational(self, user_input: str, perception: Dict) -> Thought:
        """Analyze user intent and create action plan."""
        thought_id = f"thought-{int(time.time() * 1000)}"

        # 1. Understand intent via keyword + context analysis
        intent = self._classify_intent(user_input)
        confidence = self._assess_confidence(user_input, perception)

        # 2. Find relevant tools
        tools = self.tools.find_tools(user_input)

        # 3. Build plan
        plan = self._build_plan(intent, tools, user_input)

        # 4. Determine tool calls
        tool_calls = []
        for tool_name in plan[:3]:  # Max 3 tool calls per thought
            tool = self.tools.get_tool(tool_name)
            if tool:
                tool_calls.append({
                    "tool": tool_name,
                    "horizon": tool["horizon"],
                    "reason": tool["description"][:100],
                })

        return Thought(
            id=thought_id,
            type=self._intent_to_action(intent),
            reasoning=f"User asked about: '{user_input[:200]}'. Intent: {intent}. Selected {len(tool_calls)} tools.",
            confidence=confidence,
            plan=plan,
            tool_calls=tool_calls,
            expected_outcome=self._predict_outcome(intent, tools),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    async def _think_autonomous(self, perception: Dict) -> Thought:
        """Autonomous thinking: detect issues and plan repair."""
        thought_id = f"auto-{int(time.time() * 1000)}"

        issues = self._pending_issues
        if not issues:
            return Thought(
                id=thought_id,
                type=ActionType.QUERY,
                reasoning="No issues detected. System healthy.",
                confidence=Confidence.HIGH,
                plan=[],
                tool_calls=[],
                expected_outcome="Continue monitoring",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        # Prioritize issues by severity
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        issues.sort(key=lambda i: severity_order.get(i.get("severity", "LOW"), 99))

        top_issue = issues[0]
        issue_type = top_issue.get("type", "unknown")

        # Select tools based on issue type
        tool_map = {
            "compilation_error": ["memory_retrieve_solutions", "genetic_evolve", "sandbox_execute"],
            "runtime_error": ["memory_retrieve_solutions", "z3_verify_patch", "sandbox_execute"],
            "security_vuln": ["red_team_attack", "cve_scan", "genetic_evolve"],
            "performance_regression": ["sandbox_execute", "knowledge_base_query"],
            "cve_alert": ["cve_scan", "red_team_attack", "genetic_evolve"],
            "test_failure": ["coevolution_attack", "genetic_evolve"],
        }
        tool_names = tool_map.get(issue_type, ["memory_retrieve_solutions", "codebase_search"])

        tool_calls = [
            {"tool": name, "horizon": self.tools.get_tool(name)["horizon"] if self.tools.get_tool(name) else "?", "reason": f"Auto-selected for {issue_type}"}
            for name in tool_names[:4]
        ]

        confidence = Confidence.HIGH if top_issue.get("severity") in ("CRITICAL", "HIGH") else Confidence.MEDIUM

        return Thought(
            id=thought_id,
            type=ActionType.REPAIR if issue_type != "cve_alert" else ActionType.SECURE,
            reasoning=f"Autonomously detected: {top_issue.get('description', 'unknown issue')}. "
                     f"Severity: {top_issue.get('severity', '?')}. "
                     f"Selected {len(tool_calls)} tools for {issue_type}.",
            confidence=confidence,
            plan=tool_names,
            tool_calls=tool_calls,
            expected_outcome=f"Autonomous repair of {issue_type} via {', '.join(tool_names[:3])}",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # ═══════════════════════════════════════════════════════════════════
    # Action Execution
    # ═══════════════════════════════════════════════════════════════════

    async def _act(self, thought: Thought) -> Dict[str, Any]:
        """Execute the plan via tool use."""
        self.state = MindState.ACTING
        self.context.total_actions += 1

        results = {
            "thought_id": thought.id,
            "action_type": thought.type.value,
            "confidence": thought.confidence.value,
            "tool_results": [],
            "success": False,
            "output": "",
        }

        for tc in thought.tool_calls:
            tool_result = await self._execute_tool(tc["tool"], thought)
            results["tool_results"].append(tool_result)

        # Determine overall success
        success_count = sum(1 for tr in results["tool_results"] if tr.get("ok", False))
        total_count = len(results["tool_results"])
        results["success"] = success_count == total_count if total_count > 0 else True

        # Generate output
        results["output"] = self._format_results(results, thought)

        self._action_history.append(thought)
        self.state = MindState.IDLE

        return results

    async def _execute_tool(self, tool_name: str, thought: Thought) -> Dict[str, Any]:
        """Execute a single tool with intelligent error handling."""
        tool = self.tools.get_tool(tool_name)
        if not tool:
            return {"tool": tool_name, "ok": False, "error": "Tool not found"}

        try:
            # Dynamic import and call
            fn_name = tool["fn_name"]
            module_path, class_method = fn_name.split(":", 1)
            class_name, method_name = class_method.split(".", 1)

            # Import module
            import importlib
            try:
                module = importlib.import_module(module_path)
            except ImportError:
                # Try alternate paths
                try:
                    module = importlib.import_module(module_path.replace("quimera.agentes.", "quimera.agentes.refinador_v3."))
                except ImportError:
                    return {"tool": tool_name, "ok": False, "error": f"Cannot import {module_path}"}

            cls = getattr(module, class_name, None)
            if not cls:
                return {"tool": tool_name, "ok": False, "error": f"Class {class_name} not found"}

            # Instantiate and call
            instance = cls() if not hasattr(cls, '_instance') else cls()
            method = getattr(instance, method_name, None)
            if not method:
                return {"tool": tool_name, "ok": False, "error": f"Method {method_name} not found"}

            result = method() if not asyncio.iscoroutinefunction(method) else await method()

            return {
                "tool": tool_name,
                "ok": True,
                "horizon": tool["horizon"],
                "result_type": type(result).__name__,
                "result_summary": str(result)[:500],
            }

        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name} — {e}", exc_info=True)
            return {"tool": tool_name, "ok": False, "error": str(e)[:200]}

    # ═══════════════════════════════════════════════════════════════════
    # Learning
    # ═══════════════════════════════════════════════════════════════════

    async def _learn(self, thought: Thought, result: Dict):
        """Record outcome in memory for future learning."""
        self.state = MindState.LEARNING

        if self._memory:
            try:
                await self._memory.record_outcome(
                    mission_id=thought.id,
                    ctx={"error_description": thought.reasoning},
                    solution_description=str(result.get("output", ""))[:500],
                    solution_type=thought.type.value,
                    success=result.get("success", False),
                    fitness_score=1.0 if result.get("success") else 0.3,
                )
            except Exception as e:
                logger.debug(f"Learning record failed: {e}")

        self.state = MindState.IDLE

    # ═══════════════════════════════════════════════════════════════════
    # Autonomous Mode
    # ═══════════════════════════════════════════════════════════════════

    async def _handle_autonomous(self, issues: List[Dict]) -> Dict[str, Any]:
        """Handle issues autonomously without user input."""
        logger.info(f"QuimeraMind: autonomous mode — {len(issues)} issues detected")
        self.state = MindState.REPAIRING

        result = await self.process(None)  # Recursive call without user_input

        if self.alert_on_repair and result.get("tool_results"):
            logger.info(f"QuimeraMind: autonomous action completed — {len(result['tool_results'])} tools used")

        return result

    async def autopilot(self):
        """Run continuous autonomous monitoring and repair loop."""
        logger.info("QuimeraMind: autopilot engaged")
        while self.autopilot_enabled:
            try:
                await self.process(None)  # Autonomous perception→action
                await asyncio.sleep(30)  # Check every 30 seconds
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Autopilot error: {e}", exc_info=True)
                await asyncio.sleep(60)

    # ═══════════════════════════════════════════════════════════════════
    # P3: Plan & Execute (Intelligence Layer)
    # ═══════════════════════════════════════════════════════════════════

    async def plan_and_execute(self, problem: str) -> Dict[str, Any]:
        """Plan a solution and execute subtasks in parallel.

        Full P3 intelligence pipeline:
          1. Classify problem → determine horizons
          2. Generate subtasks with dependencies
          3. Assign agents based on reputation
          4. Execute subtasks in parallel (max 5 concurrent)
          5. Record all outcomes in reputation
          6. Learn from results
        """
        if not self._planner:
            return {"success": False, "error": "Planner not initialized"}

        logger.info(f"QuimeraMind: planning for: {problem[:80]}")

        # 1. Create plan
        plan = await self._planner.plan(problem)

        logger.info(
            f"  Plan: {len(plan.subtasks)} subtasks, "
            f"est. {plan.estimated_time_ms / 1000:.1f}s, "
            f"confidence {plan.confidence:.1%}"
        )

        # 2. Execute with parallelism
        result = await self._executor.execute(plan)

        logger.info(
            f"  Executed: {sum(1 for r in result.results if r.success)}/{len(result.results)} succeeded "
            f"in {result.total_duration_ms:.0f}ms "
            f"(speedup {result.parallel_speedup:.1f}x)"
        )

        # 3. Record outcomes in memory
        if self._memory:
            for r in result.results:
                await self._memory.record_outcome(
                    mission_id=r.subtask_id,
                    error_type=f"plan_{plan.id}",
                    error_description=r.error or "planned action",
                    solution_description=str(r.output),
                    success=r.success,
                    fitness_score=1.0 if r.success else 0.0,
                )

        # 4. Get reputation summary
        rep_stats = self._reputation.get_stats() if self._reputation else {}

        return {
            "success": all(r.success for r in result.results),
            "plan_id": plan.id,
            "subtasks_executed": len(result.results),
            "subtasks_succeeded": sum(1 for r in result.results if r.success),
            "total_duration_ms": result.total_duration_ms,
            "parallel_speedup": result.parallel_speedup,
            "confidence": plan.confidence,
            "reputation": rep_stats,
            "results": [
                {
                    "id": r.subtask_id,
                    "agent": r.agent,
                    "horizon": r.horizon,
                    "success": r.success,
                    "duration_ms": r.duration_ms,
                    "error": r.error,
                }
                for r in result.results
            ],
        }

    async def get_intelligence_stats(self) -> Dict[str, Any]:
        """Get P3 intelligence layer stats."""
        return {
            "planner": self._planner.get_stats() if self._planner else {},
            "reputation": self._reputation.get_stats() if self._reputation else {},
            "executor": self._executor.get_stats() if self._executor else {},
            "overall_success_rate": self._reputation.get_success_rate() if self._reputation else 0.0,
            "best_agents": self._reputation.get_best_agents() if self._reputation else [],
            "best_models": self._reputation.get_best_models() if self._reputation else [],
        }

    # ═══════════════════════════════════════════════════════════════════
    # Intent Classification (NOT a chatbot wrapper — operational classifier)
    # ═══════════════════════════════════════════════════════════════════

    def _classify_intent(self, text: str) -> str:
        """Classify operational intent from natural language."""
        text_lower = text.lower()

        patterns = {
            "repair": ["corrige", "corrigir", "arrumar", "consertar", "fix", "repair", "bug", "erro", "falha", "broken", "fixes"],
            "explain": ["explica", "explicar", "como funciona", "o que é", "explain", "how does", "what is", "describe"],
            "analyze": ["analisa", "analisar", "avalia", "avaliar", "review", "check", "verifica", "scan", "audit"],
            "optimize": ["otimiza", "melhora", "acelera", "performance", "faster", "speed"],
            "secure": ["seguro", "segurança", "vulnerabilidade", "exploit", "cve", "security", "vuln"],
            "deploy": ["deploy", "aplica", "produção", "production", "release"],
            "status": ["status", "saúde", "health", "como está", "métricas", "metrics"],
            "learn": ["aprende", "lembra", "memoriza", "registra", "record"],
        }

        scores = {intent: sum(1 for w in words if any(p in w for p in text_lower.split()))
                  for intent, words in patterns.items()}

        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "query"

    def _assess_confidence(self, text: str, perception: Dict) -> Confidence:
        """Assess how confident the Mind is about handling this request."""
        # High confidence: user is asking about something well within our capabilities
        high_confidence = ["corrige", "fix", "repair", "status", "health", "qual agente", "o que é"]
        if any(w in text.lower() for w in high_confidence):
            return Confidence.HIGH

        # Medium: complex operations
        med_confidence = ["otimiza", "deploy", "produção", "analisa tudo"]
        if any(w in text.lower() for w in med_confidence):
            return Confidence.MEDIUM

        # Default: medium (we know our codebase well)
        return Confidence.MEDIUM

    def _intent_to_action(self, intent: str) -> ActionType:
        mapping = {
            "repair": ActionType.REPAIR,
            "explain": ActionType.QUERY,
            "analyze": ActionType.DIAGNOSE,
            "optimize": ActionType.OPTIMIZE,
            "secure": ActionType.SECURE,
            "deploy": ActionType.DEPLOY,
            "status": ActionType.DIAGNOSE,
            "learn": ActionType.LEARN,
        }
        return mapping.get(intent, ActionType.QUERY)

    def _build_plan(self, intent: str, tools: List[Dict], user_input: str) -> List[str]:
        """Build an ordered plan of tool calls."""
        # Strategic sequence based on intent
        strategy = {
            "repair": ["memory_retrieve_solutions", "codebase_search", "genetic_evolve", "sandbox_execute", "memory_record_outcome"],
            "explain": ["codebase_search", "knowledge_base_query"],
            "analyze": ["codebase_search", "cve_scan", "supply_chain_check"],
            "optimize": ["sandbox_execute", "codebase_search", "genetic_evolve"],
            "secure": ["cve_scan", "red_team_attack", "fuzzing_campaign", "genetic_evolve"],
            "deploy": ["red_team_attack", "z3_verify_patch", "cve_scan"],
            "status": ["orchestrator_get_worker_status"],
        }

        plan = strategy.get(intent, ["codebase_search", "knowledge_base_query"])

        # Insert available tools
        available_names = {t["name"] for t in tools}
        plan = [t for t in plan if t in available_names]

        return plan[:4]  # Max 4 steps

    def _predict_outcome(self, intent: str, tools: List[Dict]) -> str:
        tool_names = [t["name"] for t in tools[:3]]
        predictions = {
            "repair": f"Will search memory, evolve patch, and test in sandbox using {', '.join(tool_names)}",
            "explain": f"Will search codebase and knowledge base for answer",
            "analyze": f"Will scan codebase, CVEs, and supply chain",
            "secure": f"Will attack, fuzz, and verify patch security",
        }
        return predictions.get(intent, f"Will use {len(tools)} tools: {', '.join(tool_names)}")

    def _format_results(self, results: Dict, thought: Thought) -> str:
        """Format tool execution results into human-readable output."""
        lines = []
        lines.append(f"🧠 **QuimeraMind** — {thought.type.value.upper()}")
        lines.append(f"   Confidence: {thought.confidence.value}")

        for tr in results.get("tool_results", []):
            status = "✅" if tr.get("ok") else "❌"
            horizon = tr.get("horizon", "?")
            lines.append(f"   {status} [{horizon}] {tr['tool']}: {tr.get('result_summary', tr.get('error', ''))[:100]}")

        lines.append(f"\n   💭 {thought.reasoning[:200]}")

        return "\n".join(lines)

    # ═══════════════════════════════════════════════════════════════════
    # Public API
    #