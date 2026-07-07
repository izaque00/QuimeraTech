# quimera/agentes/refinador_v3/agente_refinador.py

import sys
import asyncio
import logging
import re
import json
from typing import Dict, Any, List, Optional, Tuple

from quimera.quadro_negro import QuadroNegro
try:
    from quimera.agentes.agente_critico import AgenteCritico
except ImportError:
    AgenteCritico = None  # AgenteCritico não disponível
try:
    from quimera.agentes.roteador_modelos import RoteadorModelos
except ImportError:
    RoteadorModelos = None  # RoteadorModelos não disponível
from quimera.agentes.refinador_v3.heuristicas_mutacao import HEURISTICAS
from quimera.agentes.refinador_v3.bandit_controller import BanditController
from quimera.agentes.refinador_v3.validador_ast import validar_patch_ast
from quimera.agentes.refinador_v3.votador_consenso import votar_consenso
from quimera.agentes.refinador_v3.memoria_iterativa import MemoriaIterativa
from quimera.agentes.refinador_v3.prompt_generator import gerar_prompt_refinamento
from quimera.agentes.refinador_v3.config_refinador import LIMIAR_ACEITE, MAX_ITERACOES
from quimera.utils.patch_utils_refactor import generate_patch_id
from quimera import config as quimera_config
from quimera.logs.parser import montar_log

from httpx import HTTPStatusError
from langchain_core.exceptions import LangChainException

logger = logging.getLogger(__name__)

class AgenteRefinadorV3:
    """
    Agente refinador de produção v3. Orquestra um ciclo iterativo de mutação e
    avaliação para aprimorar um patch, usando um MAB para otimizar a
    seleção de estratégias de mutação.
    """

    def __init__(self, quadro_negro: QuadroNegro, critico: AgenteCritico):
        self.quadro_negro = quadro_negro
        self.critico = critico
        self.roteador = RoteadorModelos()  if RoteadorModelos is not None else None
        self.memoria = MemoriaIterativa()
        self.bandit = BanditController(HEURISTICAS)
        montar_log("AgenteRefinadorV3 inicializado com sucesso.", "INFO")

    def _extrair_patch(self, resposta: str) -> Optional[str]:
        """Extrai o conteúdo de um patch de um bloco de código Markdown."""
        match = re.search(r"```diff\s*(.*?)```", resposta, re.DOTALL)
        if match:
            patch_content = match.group(1).strip()
            if patch_content.startswith("--- a/"):
                return patch_content
        return None

    async def refinar_patch(self, patch_inicial: str, arquivo_afetado: str, feedback_erro_compilacao: Optional[str] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Executa o ciclo de refinamento iterativo.
        Retorna um dicionário de resultados do refinamento e metadados do LLM.
        """
        llm_metadata = {"model_name": "N/A", "provider": "N/A", "token_usage": {"total_tokens": 0}}
        historico_iteracoes = []
        patch_atual = patch_inicial

        avaliacao_atual_iter = await self.critico.inspecionar_e_validar_patch(patch_atual, arquivo_afetado)
        score_atual = avaliacao_atual_iter.get("score_final", 0.0)
        historico_iteracoes.append({"iteracao": 0, "patch": patch_atual, "score_final": score_atual, "avaliacao": avaliacao_atual_iter})

        for i in range(MAX_ITERACOES):
            montar_log(f"[Refinador V3] Iteração {i+1}: Score atual {score_atual:.2f}", "INFO")
            if score_atual >= LIMIAR_ACEITE and not feedback_erro_compilacao:
                montar_log(f"[Refinador V3] Limiar de aceite ({LIMIAR_ACEITE}) atingido. Concluindo.", "INFO")
                break

            agentes_disponiveis = self.roteador.selecionar_agentes_para_tarefa("refinamento_de_patch", 1)
            if not agentes_disponiveis:
                agentes_disponiveis = self.roteador.selecionar_agentes_para_tarefa("critica_logica_patch", 1)
            if not agentes_disponiveis:
                return {"patch_final": patch_atual, "score_final": score_atual, "motivo": "Nenhum agente para refinamento."}, llm_metadata

            agente_selecionado = agentes_disponiveis[0]
            llm_para_usar = agente_selecionado["cliente_llm"]
            llm_metadata.update({"model_name": agente_selecionado["nome"], "provider": agente_selecionado["provedor"]})

            heuristica_funcao = self.bandit.escolher()

            # --- INÍCIO DA CORREÇÃO ---
            if asyncio.iscoroutinefunction(heuristica_funcao):
                # Se a heurística for async, passe o cliente LLM
                patch_mutado, _ = await heuristica_funcao(patch_atual, llm_client=llm_para_usar)
            else:
                # Se for síncrona, chame-a sem argumentos extras
                patch_mutado, _ = heuristica_funcao(patch_atual)
            # --- FIM DA CORREÇÃO ---

            feedback_critico = avaliacao_atual_iter.get("detalhes", {}).get("avaliacao_logica_llm", {})
            sugestao = feedback_erro_compilacao or feedback_critico.get("sugestao_de_melhoria", "Melhorar a robustez.")
            ponto_fraco = "Falha de compilação" if feedback_erro_compilacao else feedback_critico.get("ponto_fraco_principal", "O patch pode não ser a solução ideal.")
            causa_raiz_analise = self.quadro_negro.obter_conteudo_artefato(quimera_config.ANALISE_CAUSA_RAIZ_KEY)

            prompt_final = gerar_prompt_refinamento(patch_mutado, sugestao, ponto_fraco, causa_raiz_analise)

            patch_refinado_llm = None
            try:
                resposta_llm_obj = await llm_para_usar.ainvoke(prompt_final)
                patch_refinado_llm = self._extrair_patch(resposta_llm_obj.content)
                if hasattr(resposta_llm_obj, 'response_metadata') and 'token_usage' in resposta_llm_obj.response_metadata:
                    llm_metadata["token_usage"] = resposta_llm_obj.response_metadata["token_usage"]
            except (HTTPStatusError, LangChainException) as e:
                montar_log(f"[Refinador V3] Erro de API com '{agente_selecionado['nome']}': {e}", "ERROR", exc_info=True)
                self.roteador.reportar_falha_provedor(agente_selecionado["provedor"])
                continue

            if not patch_refinado_llm:
                self.bandit.registrar_resultado(heuristica_funcao, 0.0)
                continue

            if not validar_patch_ast(patch_refinado_llm, arquivo_afetado):
                self.bandit.registrar_resultado(heuristica_funcao, 0.0)
                continue

            nova_avaliacao = await self.critico.inspecionar_e_validar_patch(patch_refinado_llm, arquivo_afetado)
            novo_score = nova_avaliacao.get("score_final", 0.0)
            self.bandit.registrar_resultado(heuristica_funcao, novo_score)

            melhor_da_rodada = votar_consenso([
                {"patch": patch_atual, "score_final": score_atual, "avaliacao": avaliacao_atual_iter},
                {"patch": patch_refinado_llm, "score_final": novo_score, "avaliacao": nova_avaliacao}
            ])

            patch_atual, score_atual, avaliacao_atual_iter = melhor_da_rodada["patch"], melhor_da_rodada["score_final"], melhor_da_rodada["avaliacao"]

            historico_iteracoes.append({"iteracao": i + 1, "patch": patch_atual, "score_final": score_atual, "avaliacao": avaliacao_atual_iter})
            feedback_erro_compilacao = None

        melhor_patch_global = votar_consenso(historico_iteracoes)
        patch_final_ciclo = melhor_patch_global.get("patch", patch_atual)
        score_final_ciclo = melhor_patch_global.get("score_final", score_atual)

        patch_id = generate_patch_id(patch_final_ciclo)
        self.memoria.salvar(patch_id, historico_iteracoes)
        self.quadro_negro.publicar_artefato(f"patch_refinado_v3:{patch_id}", {"patch": patch_final_ciclo, "score": score_final_ciclo}, autor=self.__class__.__name__)

        return {"patch_final": patch_final_ciclo, "score_final": score_final_ciclo}, llm_metadata