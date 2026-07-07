"""
Quimera Evolução — Camada de Decisão.

Passos 1-6, integrados sobre a arquitetura existente:
  1. AgentRegistry (enriquecido com metadados)
  2. Dispatcher (seleção de agentes candidatos)
  3. AgentReputation (ranking por histórico)
  4. StrategySelector (escolha de estratégia)
  5. ExecutionPlanner (orquestração do plano)
  6. ContinuousLearner (aprendizado contínuo)
"""
from quimera.evolucao.dispatcher import Dispatcher, dispatcher
from quimera.evolucao.agent_reputation import AgentReputation, agent_reputation
from quimera.evolucao.strategy_selector import StrategySelector, strategy_selector
from quimera.evolucao.execution_planner import ExecutionPlanner, execution_planner
from quimera.evolucao.continuous_learning import ContinuousLearner, continuous_learner
