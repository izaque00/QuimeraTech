"""
Quimera Cognition — Agente Cognitivo de Engenharia de Software.

Pilares OMinivers:
  - ProjectContextV2     → modelo mental oficial (facts/beliefs/decisions + drift)
  - ProjectContext       → adapter de compatibilidade (delega para V2)
  - IntentInterpreter    → linguagem natural → plano de execução
  - ProjectIntelligence  → análise determinística
  - LocalAI              → IA conversacional
  - EngineeringKB        → memória técnica
  - ContextCoordinator   → monitora Context Drift

⚠️  project_context.py é APENAS adapter. Use project_context_v2 diretamente.
"""
# ═══ V2 primeiro (oficial, sem dependências circulares) ═══
from quimera.cognition.project_context_v2 import (
    ProjectContextV2, FactNode, BeliefNode, DecisionNode,
    ConfidenceLevel, ContextType,
)

# ═══ Adapter de compatibilidade ═══
from quimera.cognition.project_context import ProjectContext

# ═══ Demais módulos (com fallback para não quebrar o pacote) ═══
try:
    from quimera.cognition.intent_interpreter import (
        IntentInterpreter, IntentType, intent_interpreter,
    )
except ImportError:
    IntentInterpreter, IntentType, intent_interpreter = None, None, None

try:
    from quimera.cognition.project_intelligence import (
        ProjectIntelligence, project_intelligence,
    )
except ImportError:
    ProjectIntelligence, project_intelligence = None, None

try:
    from quimera.cognition.local_ai import (
        LocalAI, ConversationState, ConversationTurn, local_ai,
    )
except ImportError:
    LocalAI, ConversationState, ConversationTurn, local_ai = None, None, None, None

try:
    from quimera.cognition.engineering_kb import (
        EngineeringKnowledgeBase, VulnerabilityEntry, StrategyRecord, engineering_kb,
    )
except ImportError:
    EngineeringKnowledgeBase, VulnerabilityEntry, StrategyRecord, engineering_kb = None, None, None, None

try:
    from quimera.cognition.context_coordinator import (
        ContextCoordinator, context_coordinator,
    )
except ImportError:
    ContextCoordinator, context_coordinator = None, None
