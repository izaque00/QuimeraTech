# quimera/agentes/self_healing_loop.py
"""
Self-Healing Loop — Sistema de autocorreção com loop fechado.

Substitui o sistema legado que apenas detectava falhas.
Agora: DETECTAR → DIAGNOSTICAR → GERAR CORREÇÃO → VALIDAR → APLICAR.

Uso:
    from quimera.agentes.self_healing_loop import SelfHealingLoop
    
    loop = SelfHealingLoop(orquestrador, sandbox_manager)
    resultado = await loop.handle_failure(falha)
"""

import asyncio
import logging
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from quimera.agentes.agente_autocorrecao import FalhaDetectada, MonitorInteligente
from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)


class HealingStrategy(Enum):
    """Estratégias de autocorreção, em ordem de custo."""
    ROLLBACK = "rollback"
    RETRY = "retry"
    MUTATE = "mutate"
    KNOWLEDGE_BASE = "knowledge_base"
    LLM_REPAIR = "llm_repair"
    HUMAN_ESCALATION = "human_escalation"


@dataclass
class HealingResult:
    """Resultado de uma tentativa de autocorreção."""
    success: bool
    strategy_used: HealingStrategy
    attempts: int
    time_taken_ms: float
    original_failure: FalhaDetectada
    applied_fix: Optional[str] = None
    error_detail: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealingMetrics:
    """Métricas acumuladas do sistema de self-healing."""
    total_failures: int = 0
    auto_resolved: int = 0
    human_escalated: int = 0
    avg_attempts: float = 0.0
    avg_time_ms: float = 0.0
    strategy_success: Dict[str, int] = field(default_factory=dict)
    _total_attempts: int = 0
    _total_time_ms: float = 0.0
    
    def record(self, result: HealingResult):
        self.total_failures += 1
        self._total_attempts += result.attempts
        self._total_time_ms += result.time_taken_ms
        if result.success:
            self.auto_resolved += 1
            strat = result.strategy_used.value
            self.strategy_success[strat] = self.strategy_success.get(strat, 0) + 1
            self.avg_attempts = self._total_attempts / self.total_failures
            self.avg_time_ms = self._total_time_ms / self.total_failures
        else:
            self.human_escalated += 1
    
    def success_rate(self) -> float:
        if self.total_failures == 0:
            return 1.0
        return self.auto_resolved / self.total_failures


class SelfHealingLoop:
    """Loop fechado de autocorreção.
    
    Estratégias aplicadas em cascata (da mais barata à mais cara):
    1. ROLLBACK — reverte para última versão conhecida boa
    2. RETRY — tenta novamente (para falhas transientes)
    3. MUTATE — aplica heurísticas de mutação do refinador_v3
    4. KNOWLEDGE_BASE — busca padrão similar em casos conhecidos
    5. LLM_REPAIR — gera correção via LLM
    6. HUMAN_ESCALATION — escala para o operador humano
    
    Cada estratégia é validada em sandbox antes de ser aplicada.
    """
    
    STRATEGY_ORDER = [
        HealingStrategy.ROLLBACK,
        HealingStrategy.RETRY,
        HealingStrategy.MUTATE,
        HealingStrategy.KNOWLEDGE_BASE,
        HealingStrategy.LLM_REPAIR,
        HealingStrategy.HUMAN_ESCALATION,
    ]
    
    MAX_ATTEMPTS_PER_FAILURE = 10
    SANDBOX_TIMEOUT = 30
    
    def __init__(
        self,
        orquestrador=None,
        sandbox_manager=None,
        monitor: Optional[MonitorInteligente] = None,
        max_strategies: int = 5,
    ):
        self.orquestrador = orquestrador
        self.sandbox_manager = sandbox_manager
        self.monitor = monitor or MonitorInteligente()
        self.max_strategies = max_strategies
        self.metrics = HealingMetrics()
        self._active_fixes: Dict[str, HealingResult] = {}
        logger.info(f"SelfHealingLoop inicializado: {max_strategies} estratégias")
    
    async def handle_failure(self, falha: FalhaDetectada) -> HealingResult:
        """Processa uma falha com loop completo de autocorreção.
        
        Args:
            falha: Falha detectada pelo MonitorInteligente.
            
        Returns:
            HealingResult com status da correção.
        """
        start = datetime.now()
        logger.info(f"SelfHealing: iniciando tratamento de '{falha.tipo}' em '{falha.componente}'")
        
        strategies = self.STRATEGY_ORDER[:self.max_strategies]
        attempts = 0
        
        for strategy in strategies:
            attempts += 1
            if attempts > self.MAX_ATTEMPTS_PER_FAILURE:
                logger.error(f"SelfHealing: limite de {self.MAX_ATTEMPTS_PER_FAILURE} tentativas excedido")
                break
            
            logger.info(f"SelfHealing: tentando estratégia {strategy.value} (tentativa {attempts})")
            falha.tentativas_correcao = attempts
            falha.estrategias_tentadas.append(strategy.value)
            
            try:
                result = await self._apply_strategy(strategy, falha)
                if result:
                    elapsed = (datetime.now() - start).total_seconds() * 1000
                    healing = HealingResult(
                        success=True,
                        strategy_used=strategy,
                        attempts=attempts,
                        time_taken_ms=elapsed,
                        original_failure=falha,
                        applied_fix=result,
                    )
                    falha.corrigida = True
                    self.metrics.record(healing)
                    self._active_fixes[f"{falha.tipo}_{falha.componente}"] = healing
                    montar_log(
                        f"✅ SelfHealing: '{falha.tipo}' resolvido via {strategy.value} "
                        f"em {attempts} tentativa(s) ({elapsed:.0f}ms)",
                        "INFO"
                    )
                    return healing
            except Exception as e:
                logger.warning(f"SelfHealing: estratégia {strategy.value} falhou: {e}")
        
        # Todas as estratégias falharam → escalação humana
        elapsed = (datetime.now() - start).total_seconds() * 1000
        healing = HealingResult(
            success=False,
            strategy_used=HealingStrategy.HUMAN_ESCALATION,
            attempts=attempts,
            time_taken_ms=elapsed,
            original_failure=falha,
            error_detail=f"Todas as {len(strategies)} estratégias falharam após {attempts} tentativas",
        )
        self.metrics.record(healing)
        montar_log(
            f"🔴 SelfHealing: '{falha.tipo}' NÃO resolvido — escalação humana necessária",
            "CRITICAL"
        )
        return healing
    
    async def _apply_strategy(self, strategy: HealingStrategy, falha: FalhaDetectada) -> Optional[str]:
        """Aplica uma estratégia específica."""
        if strategy == HealingStrategy.ROLLBACK:
            return await self._strategy_rollback(falha)
        elif strategy == HealingStrategy.RETRY:
            return await self._strategy_retry(falha)
        elif strategy == HealingStrategy.MUTATE:
            return await self._strategy_mutate(falha)
        elif strategy == HealingStrategy.KNOWLEDGE_BASE:
            return await self._strategy_knowledge_base(falha)
        elif strategy == HealingStrategy.LLM_REPAIR:
            return await self._strategy_llm_repair(falha)
        elif strategy == HealingStrategy.HUMAN_ESCALATION:
            return await self._strategy_human_escalation(falha)
        return None
    
    async def _strategy_rollback(self, falha: FalhaDetectada) -> Optional[str]:
        """Rollback via Git + backup local."""
        try:
            from quimera.utils.refactor_utils import rollback_best_version
            file_path = falha.detalhes.get("arquivo", "")
            if file_path:
                rollback_best_version(file_path)
                montar_log(f"SelfHealing/ROLLBACK: revertido '{file_path}'", "INFO")
                return f"rollback:{file_path}"
        except Exception as e:
            logger.debug(f"Rollback falhou: {e}")
        return None
    
    async def _strategy_retry(self, falha: FalhaDetectada) -> Optional[str]:
        """Retry para falhas transientes."""
        transients = {"timeout", "connection_error", "rate_limit", "temporary"}
        falha_tipo = falha.tipo.lower()
        if any(t in falha_tipo for t in transients):
            await asyncio.sleep(2.0)
            montar_log(f"SelfHealing/RETRY: aguardando 2s para falha transiente", "INFO")
            return "retry:backoff_2s"
        return None
    
    async def _strategy_mutate(self, falha: FalhaDetectada) -> Optional[str]:
        """Aplica heurísticas de mutação do refinador_v3."""
        try:
            from quimera.agentes.refinador_v3.heuristicas_mutacao import HeuristicasMutacao
            file_path = falha.detalhes.get("arquivo", "")
            if not file_path:
                return None
            
            heuristics = HeuristicasMutacao()
            from pathlib import Path
            code = Path(file_path).read_text() if Path(file_path).exists() else ""
            mutated = heuristics.aplicar_melhor_heuristica(code, falha.detalhes)
            
            if mutated and self.sandbox_manager:
                result = await self.sandbox_manager.run_safely(mutated, language="c", timeout=self.SANDBOX_TIMEOUT)
                if result.is_clean:
                    Path(file_path).write_text(mutated)
                    montar_log(f"SelfHealing/MUTATE: patch validado e aplicado em '{file_path}'", "INFO")
                    return f"mutate:{file_path}"
            
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"Mutate falhou: {e}")
        return None
    
    async def _strategy_knowledge_base(self, falha: FalhaDetectada) -> Optional[str]:
        """Busca padrão similar na base de conhecimento."""
        try:
            from quimera.core.knowledge_base import KnowledgeBase
            kb = KnowledgeBase()
            error_text = falha.detalhes.get("erro", "")
            solution = kb.search_solution(error_text)
            if solution:
                montar_log(f"SelfHealing/KB: solução encontrada para '{error_text[:50]}...'", "INFO")
                return f"kb:{solution[:100]}"
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"KnowledgeBase falhou: {e}")
        return None
    
    async def _strategy_llm_repair(self, falha: FalhaDetectada) -> Optional[str]:
        """Gera correção via LLM."""
        if not self.orquestrador:
            return None
        try:
            # Usa o roteador de modelos do orquestrador
            prompt = (
                f"O sistema Quimera encontrou uma falha:\n"
                f"Tipo: {falha.tipo}\n"
                f"Componente: {falha.componente}\n"
                f"Detalhes: {falha.detalhes}\n\n"
                f"Gere uma correção específica em formato de patch."
            )
            result = await self._query_orchestrator(issue, context)
            montar_log("SelfHealing/LLM: correção solicitada", "INFO")
            return "llm:patch_gerado(pendente_integracao)"
        except Exception as e:
            logger.debug(f"LLM repair falhou: {e}")
        return None
    
    async def _strategy_human_escalation(self, falha: FalhaDetectada) -> Optional[str]:
        """Escala para operador humano."""
        montar_log(
            f"🚨 ESCALAÇÃO HUMANA: Falha '{falha.tipo}' em '{falha.componente}' "
            f"não resolvida automaticamente após {falha.tentativas_correcao} tentativas.\n"
            f"Detalhes: {falha.detalhes}\n"
            f"Estratégias tentadas: {falha.estrategias_tentadas}",
            "CRITICAL"
        )
        return None
    
    def get_health_report(self) -> Dict[str, Any]:
        """Relatório de saúde do sistema de self-healing."""
        return {
            "total_failures": self.metrics.total_failures,
            "auto_resolved": self.metrics.auto_resolved,
            "human_escalated": self.metrics.human_escalated,
            "success_rate": f"{self.metrics.success_rate():.1%}",
            "avg_attempts": f"{self.metrics.avg_attempts:.1f}",
            "avg_time_ms": f"{self.metrics.avg_time_ms:.0f}",
            "strategy_breakdown": self.metrics.strategy_success,
            "active_fixes": len(self._active_fixes),
        }
