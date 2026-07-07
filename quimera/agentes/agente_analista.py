# quimera/agentes/agente_analista.py

import sys
import logging
import os
import re
import json
from typing import Dict, Any, Optional, Tuple

from quimera.quadro_negro import QuadroNegro, QuadroNegroError
try:
    from quimera.agentes.roteador_modelos import RoteadorModelos
except ImportError:
    RoteadorModelos = None  # RoteadorModelos não disponível
from quimera.db.base import get_db
from quimera.db import service as db_service, schemas as db_schemas
from quimera import config
from quimera.logs.parser import montar_log

# Importações condicionais para ferramentas de análise avançada
try:
    from quimera.agentes.sub_agentes.z3_analyst import Z3Analyst
    Z3_AVAILABLE = True
except ImportError:
    Z3_AVAILABLE = False

try:
    from quimera.agentes.sub_agentes.llm_debugger import LLMDebugger
    LLM_DEBUGGER_AVAILABLE = True
except ImportError:
    LLM_DEBUGGER_AVAILABLE = False

logger = logging.getLogger(__name__)

class EngenheiroDebug:
    """
    Agente especialista em análise de causa raiz (RCA) para erros de compilação.
    Utiliza LLMs e ferramentas de análise simbólica para diagnosticar problemas.
    Na versão aprimorada, ele é capaz de utilizar contexto de um bibliotecário.
    """
    def __init__(self, quadro_negro: QuadroNegro):
        self.quadro_negro = quadro_negro
        self.roteador = RoteadorModelos() if RoteadorModelos is not None else None
        self.z3_analyst = Z3Analyst() if Z3_AVAILABLE else None

        if LLM_DEBUGGER_AVAILABLE:
            debug_expert_model_info = self.roteador.selecionar_agentes_para_tarefa("code_debugger_expert", 1)
            if debug_expert_model_info:
                self.llm_expert_instance = debug_expert_model_info[0]["cliente_llm"]
                self.llm_debugger = LLMDebugger()
            else:
                self.llm_expert_instance = None
                self.llm_debugger = None
        else:
            self.llm_expert_instance = None
            self.llm_debugger = None

        montar_log("EngenheiroDebug (analista) inicializado.", "INFO")

    def _criar_prompt_analise(self, log_erro: str, contexto_rag: str, z3_feedback: Optional[dict], debugger_feedback: Optional[dict]) -> str:
        """
        Cria um prompt detalhado e estruturado para a análise de causa raiz,
        agora incluindo o contexto RAG do Bibliotecário.
        """

        prompt_parts = [
            "Você é um engenheiro de software sênior da NASA, especialista em depuração do kernel Linux. Sua missão é realizar uma análise de causa raiz (RCA) precisa de um erro de compilação.",
            "\n### LOG DE ERRO DE COMPILAÇÃO:\n```\n" + log_erro + "\n```",
        ]

        if contexto_rag:
            prompt_parts.append("\n### CONTEXTO DO CÓDIGO-FONTE (fornecido pelo Bibliotecário Cognitivo):\n" + contexto_rag)

        if z3_feedback:
            prompt_parts.append("\n### FEEDBACK DA ANÁLISE SIMBÓLICA (Z3):\n```json\n" + json.dumps(z3_feedback, indent=2) + "\n```")

        if debugger_feedback:
            prompt_parts.append("\n### FEEDBACK DO DEBUGGER ASSISTIDO POR LLM:\n```json\n" + json.dumps(debugger_feedback, indent=2) + "\n```")

        prompt_parts.append("""
### SUA TAREFA:
Analise TODAS as informações fornecidas (log de erro, contexto do código, e feedbacks de ferramentas) e retorne um único objeto JSON com a seguinte estrutura:
{
  "status": "ok" | "falha",
  "causa_raiz": "Uma descrição técnica, detalhada e concisa da causa mais provável do erro.",
  "arquivo_afetado": "O caminho relativo do arquivo onde o erro ocorre (ex: 'kernel/fork.c').",
  "linha_suspeita": "O número da linha onde a correção provavelmente é necessária.",
  "sugestao_correcao": "Uma sugestão de alto nível sobre como o problema pode ser corrigido.",
  "justificativa": "A justificativa técnica para sua análise, explicando como as evidências (incluindo o contexto do bibliotecário, se houver) levaram à sua conclusão.",
  "confianca": "Um score de 0.0 a 1.0 indicando sua confiança na análise."
}

Seja preciso e técnico. Foque na identificação do problema real. A sua análise será a base para a geração de um patch corretivo.
""")
        return "\n".join(prompt_parts)

    async def _extract_code_snippet_from_log(self, log_erro: str) -> Optional[Tuple[str, str, int]]:
        """Extrai o caminho do arquivo, seu conteúdo e o número da linha do log de erro."""
        match = re.search(r'([\w\d\/\._-]+\.(c|h)):(\d+):', log_erro)
        if not match:
            montar_log("EngenheiroDebug: Não foi possível extrair caminho/linha do log de erro.", "WARNING")
            return None

        relative_path, _, line_number_str = match.groups()
        line_number = int(line_number_str)

        kernel_root = os.getenv("KERNEL_ROOT")
        if not kernel_root:
            montar_log("EngenheiroDebug: KERNEL_ROOT não definido, não é possível ler o arquivo.", "ERROR")
            return None

        full_path = os.path.join(kernel_root, relative_path)
        if not os.path.exists(full_path):
            montar_log(f"EngenheiroDebug: Arquivo não encontrado em {full_path}", "ERROR")
            return None

        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                return relative_path, f.read(), line_number
        except Exception as e:
            montar_log(f"EngenheiroDebug: Erro ao ler o arquivo de código '{full_path}': {e}", "ERROR")
            return None

    async def analisar(self, log_erro: str, historico_relevante: str = "", contexto_rag: str = "") -> Dict[str, Any]:
        """
        Executa a análise de causa raiz, agora aceitando um contexto RAG do Bibliotecário.
        """
        montar_log("EngenheiroDebug: Iniciando análise da causa raiz com contexto aprimorado...", "INFO")

        agentes_selecionados = self.roteador.selecionar_agentes_para_tarefa("analise_causa_raiz", 1)
        if not agentes_selecionados:
            return {"status": "falha", "causa_raiz": "Nenhum agente de análise operacional encontrado."}

        agente_escolhido = agentes_selecionados[0]
        llm_cliente = agente_escolhido["cliente_llm"]
        nome_modelo = agente_escolhido["nome"]

        # Garantir que agente_escolhido existe no escopo do except
        analise: Dict[str, Any] = {"status": "falha", "causa_raiz": ""}

        z3_analysis_feedback, debugger_analysis_feedback = None, None
        code_info = await self._extract_code_snippet_from_log(log_erro)

        if code_info:
            relative_path, code_content, line_number = code_info

            if self.z3_analyst:
                montar_log("EngenheiroDebug: Tentando análise simbólica com Z3.", "INFO")
                safety_assertion = "true"
                ptr_match = re.search(r'dereferencing NULL pointer \'(.*?)\'', log_erro)
                if ptr_match: safety_assertion = f"{ptr_match.group(1)} != NULL"
                try:
                    z3_analysis_feedback = self.z3_analyst.check_c_assertion(code_content, safety_assertion)
                except Exception as e:
                    montar_log(f"Erro na análise com Z3: {e}", "WARNING")
                    z3_analysis_feedback = {"status": "error_z3", "message": str(e)}

            if self.llm_debugger:
                montar_log("EngenheiroDebug: Tentando depuração assistida por LLM.", "INFO")
                debug_query = f"Analise o erro no log e o código. Por que o erro ocorre na linha {line_number}?"
                try:
                    debugger_analysis_feedback = await self.llm_debugger.debug_code_step_by_step(self.llm_expert_instance, code_content, log_erro, debug_query)
                except Exception as e:
                    montar_log(f"Erro no debugger LLM: {e}", "WARNING")
                    debugger_analysis_feedback = {"status": "error_debugger", "message": str(e)}

        prompt = self._criar_prompt_analise(log_erro, contexto_rag, z3_analysis_feedback, debugger_analysis_feedback)

        try:
            resposta_llm_obj = await llm_cliente.ainvoke(prompt)
            resposta_bruta = resposta_llm_obj.content
            # Regex mais robusto para extrair JSON
            json_match = re.search(r"\{.*\}", resposta_bruta, re.DOTALL)
            if json_match:
                analise = json.loads(json_match.group(0))
            else:
                raise json.JSONDecodeError("Nenhum objeto JSON encontrado na resposta.", resposta_bruta, 0)

        except Exception as e:
            montar_log(f"EngenheiroDebug: Falha na análise ou parsing. Modelo: '{nome_modelo}'. Erro: {e}", "ERROR")
            analise = {"status": "falha", "causa_raiz": str(e), "log_bruto_llm": locals().get("resposta_bruta", "N/A")}
            if agente_escolhido.get("provedor"):
                self.roteador.reportar_falha_provedor(agente_escolhido["provedor"])

        self.quadro_negro.publicar_artefato(config.ANALISE_CAUSA_RAIZ_KEY, analise, self.__class__.__name__)
        try:
            with get_db() as session:
                db_service.registrar_analise(session, db_schemas.EntradaAnalise(modelo=nome_modelo, log_bruto=log_erro, resultado=analise))
        except Exception as e:
            montar_log(f"EngenheiroDebug: Erro ao registrar análise no DB: {e}", "ERROR")

        return analise