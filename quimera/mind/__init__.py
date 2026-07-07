"""
Quimera Mark X — Mind (Consciência Central Autônoma)

The autonomous brain of the Quimera platform.
Not a chatbot wrapper — a genuine operational consciousness.

Subsystems:
    core                — QuimeraMind: central decision loop (perceive → think → act → learn)
    codebase_knowledge  — Full codebase indexing (AST parsing, dependency graph, semantic search)
    self_awareness      — Continuous monitoring, auto-diagnosis, health checks
    autonomous_engine   — Autonomous action execution with confidence gating

Usage:
    from quimera.mind import QuimeraMind
    
    mind = QuimeraMind()
    await mind.initialize()
    
    # Conversational
    response = await mind.process("Corrige o buffer overflow em fs/ext4/inode.c")
    
    # Autonomous
    await mind.autopilot()
"""

from .core import (
    QuimeraMind, MindState, ActionType, Confidence, Thought, 
    MindContext, ToolRegistry,
)
from .codebase_knowledge import (
    CodebaseKnowledge, CodeSymbol, FileIndex, SearchResult, ASTParser,
)
from .self_awareness import (
    SelfAwareness, DetectedIssue, IssueSeverity, HealthSnapshot,
)
from .autonomous_engine import (
    AutonomousEngine, AutonomousAction, ActionResult, ActionPlanner,
)

from .full_knowledge import FullCodebaseKnowledge, UniversalFileIndex, FileClassifier
from .llm_adviser import LLMAdviser, LLMProvider, LLMConfig, LLMResponse
from .api_router import APIKeyRouter, RouterConfig, KeyState, ProviderStatus, ModelSpec

__version__ = "3.0.1"
