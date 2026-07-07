"""
Quimera MarkX — Evolution Control Layer (ECL) v2.0.0 — OMinivers

Sistema A: Gatekeeper seguro (sandbox + validação + humano + deploy + backup).
Sistema B: Gerador de hipóteses (fitness + catálogo + torneio).

Fluxo de dados correto:
  LEARNER → STRATEGY CATALOG → PLANNER (lê)
  PLANNER → EVOLUTION CORE (escreve proposta)
  PLANNER NUNCA modifica diretamente

Autoridade de propostas:
  ✅ SISTEMA_B (torneio)    → prioridade ALTA
  ✅ ENGINEERING_KB          → prioridade MÉDIA
  ✅ LOCAL_AI                → prioridade BAIXA
  ✅ HUMAN                   → prioridade MÁXIMA
  ❌ PLANNER / PIPELINE      → BLOQUEADOS (nunca geram propostas)

Princípios:
  1. Sistema B nunca toca produção — apenas gera hipóteses
  2. Sistema A é apenas um gate determinístico — sem inteligência própria
  3. NADA entra sem sandbox + validação + aprovação humana
  4. Backup 30 dias + rollback instantâneo
  5. Políticas versionadas: Policy v1, v2, v3 — nunca sobrescritas
  6. Constraints contextuais (segurança ≠ performance)
  7. Diversity por entropia, não threshold fixo
  8. Backstop multicritério: fitness + crashes + testes + cobertura
  9. Fitness Engine é DONO ÚNICO da função de fitness global
"""
from quimera.evolution.fitness_engine import (
    FitnessEngine, FitnessScore, FitnessWeights,
    TaskContext, CONTEXT_WEIGHTS, fitness_engine,
)
from quimera.evolution.evo_core import (
    EvolutionCore, EvolutionProposal, ProposalStatus, MutationType, evolution_core,
)
from quimera.evolution.backup_manager import (
    BackupManager, BackupRecord, backup_manager,
)
from quimera.evolution.validation_gate import (
    ValidationGate, ValidationResult, DiversityGuard,
    LongTermMetrics, CompositeConstraint,
    BASE_CONSTRAINTS, validation_gate,
)
from quimera.evolution.strategy_catalog import (
    StrategyCatalog, StrategyPolicy, PolicyStatus,
    TaskCategory, Explanation, strategy_catalog,
)
from quimera.evolution.proposal_authority import (
    ProposalAuthority, ProposalSource, ProposalPriority,
    ProposalOrigin, proposal_authority,
)
