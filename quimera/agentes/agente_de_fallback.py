# quimera/agentes/agente_de_fallback.py

import logging
import asyncio
from typing import Dict, Any, List

# Importações de componentes do sistema Quimera
from quimera.quadro_negro import QuadroNegro
from quimera.agentes.agente_gestao_rollback import AgenteDeConserto
from quimera import config

logger = logging.getLogger(__name__)

class AgenteDeFallback:
    """
    Agente que atua como um mecanismo de segurança proativo. Ele monitora o
    sistema em busca de sinais de perigo, como "drifts" de código críticos,
    e aciona o AgenteDeConserto para reverter o sistema a um estado seguro
    antes que uma falha catastrófica ocorra.
    """

    def __init__(self, quadro_negro: QuadroNegro):
        """
        Inicializa o AgenteDeFallback.

        Args:
            quadro_negro (QuadroNegro): A instância do Quadro Negro para monitoramento.
        """
        self.quadro_negro = quadro_negro
        # O AgenteDeFallback delega a ação de conserto para o especialista.
        self.agente_de_conserto = AgenteDeConserto(self.quadro_negro)
        logger.info("AgenteDeFallback inicializado e pronto para monitorar.")

    async def monitorar_drift_critico(self) -> List[Dict[str, Any]]:
        """
        Verifica o Quadro Negro em busca de artefatos de drift e, se o risco for
        muito alto, aciona um rollback preventivo para os arquivos afetados.

        Esta função foi projetada para ser executada periodicamente.

        Returns:
            List[Dict[str, Any]]: Uma lista de dicionários, cada um representando uma
                                  ação de rollback que foi acionada.
        """
        logger.debug("Monitorando o Quadro Negro em busca de drifts críticos...")

        # Busca por todos os artefatos de drift publicados.
        # Um agente como o EvolutorDeCodigo publicaria esses artefatos.
        artefatos_de_drift = self.quadro_negro.listar_todos_artefatos(prefixo="drift_detectado:")

        acoes_executadas = []

        if not artefatos_de_drift:
            logger.debug("Nenhum drift detectado no Quadro Negro.")
            return acoes_executadas

        for artefato in artefatos_de_drift:
            dados = artefato.get('dados', {})
            caminho_arquivo = dados.get('caminho_arquivo')
            drift_score = dados.get('drift_score')

            if not caminho_arquivo or drift_score is None:
                continue

            # Compara o drift detectado com o limiar de segurança crítico.
            if drift_score > config.FALLBACK_DRIFT_CRITICO:
                motivo = (f"Drift crítico detectado ({drift_score:.4f}), "
                          f"excedendo o limiar de segurança ({config.FALLBACK_DRIFT_CRITICO}).")

                logger.critical(f"ALERTA DE SEGURANÇA: {motivo} para o arquivo '{caminho_arquivo}'. Acionando rollback preventivo.")

                # Deleta a ação de conserto para o AgenteDeConserto.
                sucesso_rollback = await self.agente_de_conserto.executar_rollback_arquivo(
                    caminho_arquivo=caminho_arquivo,
                    motivo=motivo
                )

                acao = {
                    "arquivo": caminho_arquivo,
                    "drift_detectado": drift_score,
                    "rollback_acionado": True,
                    "sucesso_rollback": sucesso_rollback
                }
                acoes_executadas.append(acao)

                # Após tratar o drift, o artefato pode ser removido ou marcado como tratado
                # para evitar que seja processado novamente no próximo ciclo de monitoramento.
                self.quadro_negro.redis.delete(artefato['chave_completa'])

        if acoes_executadas:
            logger.info(f"{len(acoes_executadas)} ações de fallback foram acionadas devido a drifts críticos.")

        return acoes_executadas