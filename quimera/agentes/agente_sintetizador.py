# quimera/agentes/agente_sintetizador.py

import sys
import logging
import ast
import json
import re
from sys import version_info
from typing import Dict, Optional, Any, List, Tuple

# Importações de componentes do sistema Quimera
from quimera.quadro_negro import QuadroNegro
try:
    from quimera.agentes.roteador_modelos import RoteadorModelos
except ImportError:
    RoteadorModelos = None  # RoteadorModelos não disponível
from quimera import config

# Importa exceções específicas para tratamento de erro de API
from httpx import HTTPStatusError
from cohere.errors import TooManyRequestsError
from langchain_core.exceptions import LangChainException


logger = logging.getLogger(__name__)

class AstMergeEngine:
    """
    Motor de fusão e síntese que utiliza um LLM de alta capacidade para consolidar
    múltiplas propostas de patch em uma única solução otimizada.
    """
    def __init__(self, quadro_negro: QuadroNegro):
        """
        Inicializa o motor de síntese.

        Args:
            quadro_negro (QuadroNegro): A instância do Quadro Negro para comunicação.
        """
        self.quadro_negro = quadro_negro
        self.roteador = RoteadorModelos() if RoteadorModelos is not None else None
        self.python_version_int = int(f"{version_info.major}{version_info.minor}")
        logger.info("AstMergeEngine (Sintetizador) inicializado com sucesso.")

    def _criar_prompt_sintese(self, patches_brutos: List[str], analise_causa_raiz: str, log_erro: str, conteudo_arquivo: str = "") -> str:
        """Cria o prompt detalhado para a tarefa de síntese."""
        contexto_patches = "\n\n".join([f"--- PROPOSTA DE PATCH {i+1} ---\n```diff\n{patch}\n```" for i, patch in enumerate(patches_brutos)])

        contexto_codigo = ""
        if conteudo_arquivo:
            arquivo_afetado_nome = json.loads(analise_causa_raiz).get("arquivo_afetado", "desconhecido")
            contexto_codigo = (
                f"### CONTEÚDO COMPLETO DO ARQUIVO A SER CORRIGIDO: {arquivo_afetado_nome} ###\n"
                f"```c\n{conteudo_arquivo}\n```\n"
                "#####################################################################\n\n"
            )

        return f"""
Você é um Engenheiro de Integração de Código Sênior do kernel Linux, um especialista em revisar e consolidar contribuições de múltiplos desenvolvedores.

**Sua Tarefa:**
Analisar várias propostas de patch geradas por diferentes IAs para resolver o mesmo erro de compilação. Seu objetivo é **sintetizar essas propostas em um único patch final que seja superior a todos os individuais.**

{contexto_codigo}

**Contexto do Problema Original:**
*   **Análise da Causa Raiz:** {analise_causa_raiz}
*   **Log de Erro:** {log_erro}

**Propostas de Patch para Sintetizar:**
{contexto_patches}

**Instruções para a Síntese (REGRAS CRÍTICAS):**
1.  **Combine as Melhores Ideias:** Identifique os pontos fortes de cada proposta e combine-os.
2.  **Resolva Conflitos:** Se as propostas forem conflitantes, use seu julgamento de especialista para escolher a abordagem mais robusta e segura.
3.  **Refine o Código:** Melhore a clareza, a eficiência e o estilo do código final.
4.  **Formato de Saída Rígido:** Sua resposta deve ser **APENAS e SOMENTE** o patch unificado final, encapsulado em um bloco de código Markdown.
5.  **PRECISÃO DO CONTEXTO (MAIS IMPORTANTE):** As linhas de contexto no patch (as que não começam com `+` ou `-`) devem corresponder **exatamente** ao conteúdo do arquivo fornecido acima. **NÃO INVENTE OU MODIFIQUE AS LINHAS DE CONTEXTO.**
6.  **NENHUM TEXTO ADICIONAL:** Nenhuma explicação, saudação ou comentário **fora do bloco ` ```diff...``` `** é permitido.
"""

    def _extrair_patch_da_resposta(self, resposta_bruta: str) -> str:
        """Extrai o conteúdo do patch de uma resposta de LLM."""
        match = re.search(r"```diff\n(.*?)```", resposta_bruta, re.DOTALL)
        if match:
            extracted_patch = match.group(1).strip()
            return extracted_patch if extracted_patch.endswith('\n') else extracted_patch + '\n'

        lines = resposta_bruta.splitlines()
        start_index = -1
        for i, line in enumerate(lines):
            if line.strip().startswith('--- a/'):
                start_index = i
                break
        if start_index != -1:
            fallback_patch = "\n".join(lines[start_index:]).strip()
            return fallback_patch if fallback_patch.endswith('\n') else fallback_patch + '\n'
        return ""

    async def sintetizar_patches(self, patches_brutos: List[str], conteudo_arquivo_original: str = "") -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Executa o ciclo completo de síntese de patches, de forma resiliente.
        Retorna o patch sintetizado e metadados do LLM utilizado.
        """
        llm_metadata = {"model_name": "N/A", "provider": "N/A", "token_usage": {"total_tokens": 0}}

        if not patches_brutos:
            logger.warning("Nenhuma solução bruta fornecida para síntese.")
            return None, llm_metadata

        agentes_disponiveis = self.roteador.selecionar_agentes_para_tarefa(
            habilidade_requerida="sintese_de_codigo",
            quantidade=1
        )
        if not agentes_disponiveis:
            msg_erro = "Nenhum agente de síntese operacional encontrado."
            logger.error(msg_erro)
            return None, llm_metadata

        agente_selecionado = agentes_disponiveis[0]
        llm_sintetizador = agente_selecionado["cliente_llm"]
        nome_modelo = agente_selecionado["nome"]
        provedor = agente_selecionado["provedor"]

        llm_metadata["model_name"] = nome_modelo
        llm_metadata["provider"] = provedor

        logger.info(f"Iniciando síntese de {len(patches_brutos)} propostas com o modelo '{nome_modelo}'.")

        analise_causa_raiz = self.quadro_negro.obter_conteudo_artefato(config.ANALISE_CAUSA_RAIZ_KEY) or {}
        log_erro = self.quadro_negro.obter_conteudo_artefato(config.LOG_COMPILACAO_ERRO_KEY) or "Log de erro não disponível."

        prompt = self._criar_prompt_sintese(patches_brutos, json.dumps(analise_causa_raiz), log_erro, conteudo_arquivo_original)

        try:
            resposta_llm_obj = await llm_sintetizador.ainvoke(prompt)
            solucao_sintetizada_raw = resposta_llm_obj.content.strip()

            if hasattr(resposta_llm_obj, 'response_metadata') and 'token_usage' in resposta_llm_obj.response_metadata:
                llm_metadata["token_usage"] = resposta_llm_obj.response_metadata["token_usage"]

            solucao_sintetizada = self._extrair_patch_da_resposta(solucao_sintetizada_raw)

            if not solucao_sintetizada or not solucao_sintetizada.startswith("--- a/"):
                logger.warning(f"O modelo sintetizador '{nome_modelo}' não gerou um patch válido. Resposta: {solucao_sintetizada_raw[:500]}...")
                return None, llm_metadata

            if not solucao_sintetizada.endswith('\n'):
                solucao_sintetizada += '\n'

            self.quadro_negro.publicar_artefato(
                config.SOLUCAO_SINTETIZADA_KEY,
                solucao_sintetizada,
                autor=self.__class__.__name__
            )
            logger.info("Solução sintetizada e publicada no Quadro Negro com sucesso.")
            return solucao_sintetizada, llm_metadata

        except (TooManyRequestsError, HTTPStatusError, LangChainException) as e:
            logger.error(f"[Sintetizador] Erro de API ao usar '{nome_modelo}' do provedor '{provedor}': {e}", exc_info=True)
            self.roteador.reportar_falha_provedor(provedor)
            return None, llm_metadata
        except Exception as e:
            logger.error(f"[Sintetizador] Falha crítica na síntese de patches via LLM '{nome_modelo}': {e}", exc_info=True)
            return None, llm_metadata