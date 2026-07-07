"""
Context Coordinator & Drift Monitor — MetaX v4.1.0

Este módulo atua como o sistema imunológico do Quimera MarkX. 
Ele garante o equilíbrio:
  - Macro-Decisão: Baseada no ProjectContextV2 (estratégia, restrições, hipóteses globais).
  - Micro-Adaptação: Baseada em dados telemetrados crus locais (compilador, testes físicos).

Se o ProjectContextV2 começar a sofrer de Overfitting ou "Falsa Coerência" (drift_score > 50),
o Coordinator intervém, purga as hipóteses subjetivas da IA, dá um "hard-reset" no Modelo Mental
e força o Pipeline a confiar exclusivamente nas leituras físicas locais (facts).

Autor: Quimera MarkX — MetaX
"""
import logging
from typing import Any, Dict, Tuple
from quimera.cognition.project_context_v2 import ProjectContextV2, ConfidenceLevel, ContextType

logger = logging.getLogger("quimera.cognition.coordinator")


class ContextCoordinator:
    def __init__(self, drift_threshold: int = 50):
        self.drift_threshold = drift_threshold

    def coordinate_execution(self, context: ProjectContextV2, local_telemetry: Dict[str, Any]) -> Tuple[ProjectContextV2, str]:
        """Coordena a execução equilibrando o macro (contexto) e o micro (telemetria local)."""
        logger.info(f"Coordenando execução. Monitorando desvio de contexto...")

        # 1. Injetar telemetria local crua como fatos verificados (Facts)
        for k, v in local_telemetry.items():
            context.add_fact(k, v, source="local_telemetry")

        # 2. Avaliar Drift (Viés e Overfitting)
        drift = context.check_drift()
        score = drift["drift_score"]
        
        logger.info(f"Context Drift Score: {score}/100")

        # 3. Tomar ação corretiva se o contexto estiver "envenenado" (Falsa Coerência)
        if score > self.drift_threshold:
            logger.warning(f"⚠️ DETECTADO CONTEXT DRIFT CRÍTICO ({score}/100)! Purgando hipóteses subjetivas...")
            
            # Purgar crenças não verificadas
            purged_keys = []
            for k in list(context.beliefs.keys()):
                if context.beliefs[k].confidence != ConfidenceLevel.VERIFIED:
                    purged_keys.append(k)
                    del context.beliefs[k]
                    
            context.record_decision(
                action="hard_reset_beliefs",
                rationale=f"Context Drift Score atingiu {score}. Purgado chaves: {purged_keys}. Forçado micro-determinismo.",
                success=True
            )
            
            # Modo de Execução Emergencial: Confiar apenas nas leituras do compilador local
            execution_mode = "pure_micro_telemetry"
        else:
            # Modo Normal: Equilíbrio macro-micro
            execution_mode = "balanced_cognitive"

        return context, execution_mode


# Global Coordinator
context_coordinator = ContextCoordinator()
