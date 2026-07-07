# quimera/agentes/agente_analista_mult.py

import logging
import asyncio
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

# Importações de componentes do sistema Quimera (os agentes que ele irá orquestrar)
from quimera.quadro_negro import QuadroNegro
try:
    from quimera.agentes.agente_analista import EngenheiroDebug
except ImportError:
    EngenheiroDebug = None  # EngenheiroDebug não disponível
from quimera.agentes.agente_estrategista import AgenteEstrategista, ESTRATEGIA_REPARO_CONSERVADOR, ESTRATEGIA_REVISAO_SEGURANCA_URGENTE
from quimera.agentes.agente_votoaste import AgenteRevisorAssemble
from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)

class AgenteAnalistaMult:
    """
    Agente de Correção e Análise Simultânea Multivariante.

    Este agente não executa uma análise por si só, mas orquestra um comitê
    de agentes analistas especializados para operarem em paralelo. Ele sintetiza
    os resultados de múltiplas perspectivas (causa raiz, estratégia, qualidade)
    em um único diagnóstico enriquecido, ponderado e abrangente.
    """
    def __init__(self, quadro_negro: QuadroNegro):
        """
        Inicializa o AgenteAnalistaMult e o comitê de agentes analistas.
        """
        self.quadro_negro = quadro_negro
        self.llm_expert_instance = None # Será injetado pelo Orquestrador se necessário

        # O comitê de análise é composto por instâncias de outros agentes especializados.
        self.comite_de_analise = {
            # Injeta a instância do LLM Expert para o EngenheiroDebug usar em suas sub-ferramentas
            "analista_causa_raiz": EngenheiroDebug(quadro_negro, self.llm_expert_instance) if EngenheiroDebug is not None else None,
            "analista_estrategico": AgenteEstrategista(quadro_negro),
            "analista_qualidade_inicial": AgenteRevisorAssemble(quadro_negro), # Votoaste
        }
        montar_log(f"AgenteAnalistaMult inicializado com um comitê de {len(self.comite_de_analise)} agentes.", "INFO")

    def set_llm_expert_instance(self, llm_instance: Any):
        """Permite a injeção de uma instância de LLM para ser usada pelos sub-agentes."""
        self.llm_expert_instance = llm_instance
        # Atualiza a instância no EngenheiroDebug, se ele já foi criado
        if "analista_causa_raiz" in self.comite_de_analise:
            self.comite_de_analise["analista_causa_raiz"].llm_expert_instance = llm_instance

    def _sintetizar_resultados(self, resultados_brutos: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Sintetiza os resultados de todas as análises paralelas em um único
        dicionário de "Análise Consolidada", com lógica de decisão para a estratégia final.

        Args:
            resultados_brutos (List[Dict[str, Any]]): A lista de dicionários retornados
                                                       pelos agentes do comitê.

        Returns:
            Optional[Dict[str, Any]]: A análise consolidada e enriquecida, ou None se
                                      nenhum resultado válido foi obtido.
        """
        if not resultados_brutos:
            montar_log("Síntese falhou: Nenhum resultado válido recebido do comitê de análise.", "WARNING")
            return None

        analise_consolidada = {
            "fonte": self.__class__.__name__,
            "perspectivas_individuais": {},
            "resumo_executivo": "",
            "estrategia_final_recomendada": "REPARO_PADRAO", # Padrão
            "score_confianca_diagnostico": 0.5 # Começa com confiança média
        }

        # Extrai e organiza os dados de cada resultado
        for res in resultados_brutos:
            if not res or not isinstance(res, dict): continue

            if "causa_raiz" in res:
                analise_consolidada["perspectivas_individuais"]["causa_raiz"] = res
            elif "ficha_estrategia" in res:
                analise_consolidada["perspectivas_individuais"]["estrategia"] = res["ficha_estrategia"]
            elif "resultado" in res and "score_qualidade_final" in res.get("resultado", {}):
                analise_consolidada["perspectivas_individuais"]["qualidade_inicial"] = res["resultado"]

        # Constrói o resumo e define a estratégia final
        estrategia = analise_consolidada["perspectivas_individuais"].get("estrategia", {})
        causa_raiz = analise_consolidada["perspectivas_individuais"].get("causa_raiz", {})
        qualidade_inicial = analise_consolidada["perspectivas_individuais"].get("qualidade_inicial", {})

        # Lógica de Ponderação para Confiança e Estratégia
        confianca = 0.5
        justificativa_confianca = "Confiança base."

        if causa_raiz.get("status") == "ok":
            confianca += 0.2
            justificativa_confianca += " | Causa raiz identificada."

        if estrategia:
            confianca += 0.1
            justificativa_confianca += " | Análise estratégica concluída."
            # Lógica de promoção de risco: Segurança tem a maior prioridade.
            if estrategia.get("estrategia_recomendada") == ESTRATEGIA_REVISAO_SEGURANCA_URGENTE:
                analise_consolidada["estrategia_final_recomendada"] = ESTRATEGIA_REVISAO_SEGURANCA_URGENTE
                confianca = 1.0 # Confiança máxima na necessidade de agir.
                justificativa_confianca = "PROMOÇÃO DE RISCO: Risco de segurança detectado, ação urgente necessária."
            elif estrategia.get("estrategia_recomendada") == ESTRATEGIA_REPARO_CONSERVADOR:
                analise_consolidada["estrategia_final_recomendada"] = ESTRATEGIA_REPARO_CONSERVADOR

        analise_consolidada["score_confianca_diagnostico"] = round(min(confianca, 1.0), 2)

        resumo = (
            f"Análise Multivariante Concluída:\n"
            f"- Causa Raiz Identificada: {causa_raiz.get('causa_raiz', 'Não determinada.')}\n"
            f"- Arquivo Afetado: {causa_raiz.get('arquivo_afetado', 'N/A')}\n"
            f"- Complexidade Ciclomática: {estrategia.get('metricas_analisadas', {}).get('complexidade_ciclomatica', 'N/A')}\n"
            f"- Score de Saúde Inicial do Código (Votoaste): {qualidade_inicial.get('score_qualidade_final', 'N/A'):.2f}\n"
            f"- Nível de Confiança do Diagnóstico: {analise_consolidada['score_confianca_diagnostico']:.2f}\n"
            f"- Estratégia Final Recomendada: **{analise_consolidada['estrategia_final_recomendada']}**"
        )
        analise_consolidada["resumo_executivo"] = resumo

        return analise_consolidada

    async def analisar_em_paralelo(self, caminho_arquivo_relativo: str, log_erro: str) -> Dict[str, Any]:
        """
        Orquestra a execução paralela do comitê de analistas e sintetiza seus resultados.

        Args:
            caminho_arquivo_relativo (str): O caminho relativo do arquivo a ser analisado.
            log_erro (str): O log de erro da compilação associado ao problema.

        Returns:
            Dict[str, Any]: A análise consolidada e multivariada.
        """
        kernel_root = os.getenv("KERNEL_ROOT")
        if not kernel_root:
            return {"status": "falha_critica", "motivo": "Variável de ambiente KERNEL_ROOT não definida."}

        caminho_arquivo_completo = os.path.join(kernel_root, caminho_arquivo_relativo)

        montar_log(f"Iniciando análise multivariante para o arquivo: {caminho_arquivo_completo}...", "INFO")

        try:
            codigo_fonte = Path(caminho_arquivo_completo).read_text(encoding='utf-8', errors='ignore')
        except FileNotFoundError:
            return {"status": "falha_critica", "motivo": f"Arquivo não encontrado: {caminho_arquivo_completo}"}

        # Prepara as tarefas para execução concorrente com os argumentos corretos.
        tasks = [
            # CORREÇÃO APLICADA AQUI: Usa `analisar` com `log_erro`.
            self.comite_de_analise["analista_causa_raiz"].analisar(log_erro),
            # CORREÇÃO APLICADA AQUI: Passa o caminho completo.
            self.comite_de_analise["analista_estrategico"].observar_e_definir_estrategia(caminho_arquivo_completo),
            # CORREÇÃO APLICADA AQUI: Passa o caminho completo.
            self.comite_de_analise["analista_qualidade_inicial"].avaliar_proposta_de_codigo(codigo_fonte, caminho_arquivo_completo)
        ]

        # Executa todas as análises em paralelo e trata exceções individualmente.
        resultados_brutos = await asyncio.gather(*tasks, return_exceptions=True)

        # Filtra e loga exceções que possam ter ocorrido
        resultados_validos = []
        for i, res in enumerate(resultados_brutos):
            if isinstance(res, Exception):
                nome_agente = list(self.comite_de_analise.keys())[i]
                montar_log(f"O agente '{nome_agente}' falhou durante a análise paralela: {res}", "ERROR", exc_info=res)
            else:
                resultados_validos.append(res)

        if not resultados_validos:
            montar_log("Todos os agentes analistas falharam. Não é possível produzir uma análise consolidada.", "ERROR")
            return {"status": "falha_total_analise", "motivo": "Nenhum agente do comitê retornou um resultado válido."}

        # Sintetiza os resultados válidos em uma única análise
        analise_final_consolidada = self._sintetizar_resultados(resultados_validos)

        if not analise_final_consolidada:
            return {"status": "falha_sintese", "motivo": "Não foi possível consolidar os resultados das análises."}

        # Publica o resultado final no Quadro Negro
        self.quadro_negro.publicar_artefato(
            f"analise_multivariante:{caminho_arquivo_relativo}",
            analise_final_consolidada,
            autor=self.__class__.__name__
        )

        montar_log(f"Análise multivariante para '{caminho_arquivo_relativo}' concluída com sucesso.", "INFO")
        return {"status": "sucesso_analise_multivariante", "resultado": analise_final_consolidada}