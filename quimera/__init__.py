"""
TheAnd — Quimera Mark X: Plataforma de Engenharia de Software Autônoma.

Organism fully integrated: 30+ modules, 13-phase pipeline,
Defensive Shield (AEGIS), Genetic Evolution, Formal Verification,
Cognitive Librarian, Multi-Agent System, Sandbox Engine.

Entry points:
  - QuimeraOrchestrator: 13-phase autonomous pipeline
  - NaturalConfig: Natural language interface (PT/EN/ES)
  - LLMConfig: Auto-detect and configure LLM providers

ALL imports are lazy — nothing is loaded at package level.
Import individual classes as needed or use the convenience accessors.
"""

import logging
logger = logging.getLogger("quimera")


# ── LAZY IMPORT HELPERS ───────────────────────────────────────────────

class _LazyImporter:
    """Lazy-loads a module attribute on first access."""

    def __init__(self, module_path: str, attr_name: str, friendly_name: str = ""):
        self._module_path = module_path
        self._attr_name = attr_name
        self._friendly_name = friendly_name or attr_name
        self._obj = None

    def __call__(self):
        if self._obj is None:
            try:
                import importlib
                mod = importlib.import_module(self._module_path)
                self._obj = getattr(mod, self._attr_name)
            except ImportError as e:
                logger.warning(
                    f"Dependency missing for {self._friendly_name}: {e}. "
                    f"Install required packages to enable this feature."
                )
                raise
            except AttributeError:
                logger.warning(
                    f"Attribute {self._attr_name} not found in {self._module_path}. "
                    f"Module may be incomplete."
                )
                raise
        return self._obj


# ── CORE (always available, minimal deps) ─────────────────────────────

def _get_OrchestratorConfig():
    from quimera.orchestrator import OrchestratorConfig
    return OrchestratorConfig


def _get_QuimeraOrchestrator():
    from quimera.orchestrator import QuimeraOrchestrator
    return QuimeraOrchestrator


def _get_Planner():
    from quimera.planner import Planner
    return Planner


def _get_DetectionEngine():
    from quimera.detection_engine import DetectionEngine
    return DetectionEngine


def _get_PatchCatalog():
    from quimera.patch_memory import PatchCatalog
    return PatchCatalog


# ── KNOWLEDGE ─────────────────────────────────────────────────────────

def _get_KnowledgeBroker():
    from quimera.knowledge_broker import KnowledgeBroker, KnowledgeResult
    return KnowledgeBroker


def _get_HypothesisBuilder():
    from quimera.hypothesis_builder import HypothesisBuilder, Hypothesis
    return HypothesisBuilder


def _get_SourceCatalog():
    from quimera.source_catalog import SourceCatalog
    return SourceCatalog


def _get_LiveCatalog():
    from quimera.live_catalog import LiveCatalog, ModelStats
    return LiveCatalog


# ── CANDIDATE GENERATION ──────────────────────────────────────────────

def _get_CandidateGenerator():
    from quimera.candidate_generator import CandidateGenerator, LLMInterface
    return CandidateGenerator


def _get_ASTPatcher():
    from quimera.ast_patcher import ASTPatcher, ASTPatchCandidate
    return ASTPatcher


def _get_CandidateRanker():
    from quimera.candidate_ranker import CandidateRanker, RankedCandidate
    return CandidateRanker


# ── MEMORY ────────────────────────────────────────────────────────────

def _get_EngineeringMemory():
    from quimera.engineering_memory import EngineeringMemory, EngineeringRecord
    return EngineeringMemory


def _get_UnifiedMemory():
    from quimera.unified_memory import UnifiedMemory, DecisionReport
    return UnifiedMemory


# ── CONFIG ────────────────────────────────────────────────────────────

def _get_NaturalConfig():
    from quimera.natural_config import NaturalConfig, NLResponse
    return NaturalConfig


def _get_LLMConfig():
    from quimera.llm_config import LLMConfig
    return LLMConfig


# ── OPTIONAL: HEAVY MODULES (may fail if deps missing) ────────────────

def _get_GeneticPatchEngine():
    from quimera.horizons.h4_evolution.genetic_patch_engine import GeneticPatchEngine
    return GeneticPatchEngine


def _get_Z3Wrapper():
    from quimera.integration_backends.z3_wrapper import Z3Wrapper
    return Z3Wrapper


def _get_SandboxManager():
    from quimera.sandbox.manager import SandboxManager
    return SandboxManager


def _get_AegisCore():
    from quimera.aegis.aegis_core import AegisCore
    return AegisCore


def _get_ValidationPipeline():
    from quimera.aegis.validation_pipeline import ValidationPipeline
    return ValidationPipeline


def _get_Sentinel():
    from quimera.aegis.sentinel import SentinelSecurityOrgan
    return SentinelSecurityOrgan


def _get_CognitiveLibrarian():
    try:
        from quimera.bibliotecario.biblioteca_alexandria import BibliotecaAlexandria
        return BibliotecaAlexandria
    except ImportError:
        logger.warning("BibliotecaAlexandria not available")
        return None


def _get_AgenteMestra():
    from quimera.agentes.agente_mestra import AgenteMestra
    return AgenteMestra


def _get_AgenteConfigurador():
    from quimera.agentes.agente_configurador import AgenteConfiguradorDeKernel
    return AgenteConfiguradorDeKernel



def _get_EvolutorDeCodigo():
    try:
        from quimera.agentes.agente_evolutivo_de_codigo import EvolutorDeCodigo
        return EvolutorDeCodigo
    except ImportError:
        logger.warning("EvolutorDeCodigo not available")
        return None

def _get_RefinadorV4():
    try:
        from quimera.agentes.refinador_v3.agente_refinador import AgenteRefinador
        return AgenteRefinador
    except ImportError:
        logger.warning("AgenteRefinador not available")
        return None


# ── PUBLIC API ────────────────────────────────────────────────────────

__all__ = [
    # Core v4 NEW
    "QuimeraEngineer", "IterativeEngineer",
    "DetectionEngine", "FlowBasedDetector",
    "SemanticHunter", "OfflineSemanticHunter",
    "LLMConfig", "PatchMemory",
    "ASanValidator", "KernelSandbox",
    "PythonParser", "RustParser",
    # Legacy
    "QuimeraOrchestrator", "OrchestratorConfig",
    "Planner",
    "KnowledgeBroker", "KnowledgeResult",
    "HypothesisBuilder", "Hypothesis",
    "ASTPatcher", "ASTPatchCandidate",
    "CandidateGenerator", "LLMInterface",
    "CandidateRanker", "RankedCandidate",
    "SourceCatalog",
    "LiveCatalog", "ModelStats",
    "EngineeringMemory", "EngineeringRecord",
    "PatchCatalog",
    "NaturalConfig", "NLResponse",
    "GeneticPatchEngine",
    "AegisCore", "ValidationPipeline", "SentinelSecurityOrgan",
    "Z3Wrapper",
    "CognitiveLibrarianUltraAdvanced",
    "SandboxManager",
    "AgenteMestra", "AgenteConfiguradorDeKernel",
    "AgenteRefinadorV4",
    "UnifiedMemory", "DecisionReport",
]

# Convenience: module-level accessors that lazy-load
def __getattr__(name: str):
    _map = {
        "QuimeraOrchestrator": _get_QuimeraOrchestrator,
        "OrchestratorConfig": _get_OrchestratorConfig,
        "Planner": _get_Planner,
        "DetectionEngine": _get_DetectionEngine,
        "KnowledgeBroker": _get_KnowledgeBroker,
        "KnowledgeResult": _get_KnowledgeBroker,  # same module
        "HypothesisBuilder": _get_HypothesisBuilder,
        "Hypothesis": _get_HypothesisBuilder,
        "ASTPatcher": _get_ASTPatcher,
        "ASTPatchCandidate": _get_ASTPatcher,
        "CandidateGenerator": _get_CandidateGenerator,
        "LLMInterface": _get_CandidateGenerator,
        "CandidateRanker": _get_CandidateRanker,
        "RankedCandidate": _get_CandidateRanker,
        "SourceCatalog": _get_SourceCatalog,
        "LiveCatalog": _get_LiveCatalog,
        "ModelStats": _get_LiveCatalog,
        "EngineeringMemory": _get_EngineeringMemory,
        "EngineeringRecord": _get_EngineeringMemory,
        "PatchCatalog": _get_PatchCatalog,
        "NaturalConfig": _get_NaturalConfig,
        "NLResponse": _get_NaturalConfig,
        "LLMConfig": _get_LLMConfig,
        "GeneticPatchEngine": _get_GeneticPatchEngine,
        "AegisCore": _get_AegisCore,
        "ValidationPipeline": _get_ValidationPipeline,
        "SentinelSecurityOrgan": _get_Sentinel,
        "Z3Wrapper": _get_Z3Wrapper,
        "CognitiveLibrarianUltraAdvanced": _get_CognitiveLibrarian,
        "SandboxManager": _get_SandboxManager,
        "AgenteMestra": _get_AgenteMestra,
        "AgenteConfiguradorDeKernel": _get_AgenteConfigurador,
        "EvolutorDeCodigo": _get_EvolutorDeCodigo,
        "AgenteRefinadorV4": _get_RefinadorV4,
        "UnifiedMemory": _get_UnifiedMemory,
        "DecisionReport": _get_UnifiedMemory,
    }
    if name in _map:
        return _map[name]()
    raise AttributeError(f"module 'quimera' has no attribute '{name}'")
