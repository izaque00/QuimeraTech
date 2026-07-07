# quimera/integration_backends/llm_debugger.py

import logging
import asyncio
from typing import Dict, Any, Optional, List, Tuple

from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)


def sanitize_input(text: str, max_length: int = 10000) -> str:
    """Sanitize input for LLM prompts to prevent prompt injection."""
    if not isinstance(text, str):
        text = str(text)
    text = text[:max_length]
    # Escape potential prompt injection markers
    text = text.replace("```", "`\u200B``")
    return text


class LLMDebugger:
    def __init__(self):
        montar_log("LLMDebugger inicializado.", log_level="INFO")

    async def debug_code_step_by_step(self, llm_client: Any, code_snippet: str, error_context: str, debug_query: str) -> Dict[str, Any]:
        montar_log(f"LLMDebugger: Iniciando depuração passo a passo.", log_level="INFO")

        if not llm_client:
            montar_log("LLMDebugger: Cliente LLM não disponível. Não é possível depurar.", log_level="ERROR")
            return {"analysis": "LLM indisponível para depuração.", "confidence_score": 0.0}

        # Sanitizar todos os inputs antes de interpolar no prompt
        safe_code = sanitize_input(code_snippet)
        safe_error = sanitize_input(error_context)
        safe_query = sanitize_input(debug_query)

        prompt = f"""
Você é um depurador de kernel Linux especialista, capaz de simular a execução de código C e diagnosticar problemas como se estivesse usando um depurador simbólico.
Sua tarefa é analisar o trecho de código C do kernel, o contexto do erro e responder à pergunta de depuração de forma técnica e concisa.

---
**TRECHO DE CÓDIGO (C Kernel):**
```c
{safe_code}

CONTEXTO DO ERRO / PROBLEMA:
{safe_error}

PERGUNTA DE DEPURAÇÃO:
{safe_query}

SUA ANÁLISE:
Atue como um depurador. Explique o fluxo de execução relevante, identifique o ponto problemático e responda à pergunta de depuração. Se possível, sugira qual seria o valor de variáveis críticas, o estado de registradores ou o fluxo de controle alternativo naquele ponto.
"""

        try:
            response_obj = await llm_client.query(prompt, max_tokens=1024, temperature=0.1)
            analysis_text = response_obj.get("content", "N/A").strip()

            confidence = 0.5
            if "stack trace" in analysis_text.lower() or "memory address" in analysis_text.lower() or "register" in analysis_text.lower():
                confidence = 0.9
            elif "function call" in analysis_text.lower() or "variable value" in analysis_text.lower():
                confidence = 0.7

            montar_log(f"LLMDebugger: Análise de depuração recebida. Confiança: {confidence:.2f}", log_level="INFO")
            return {"analysis": analysis_text, "confidence_score": confidence}

        except Exception as e:
            montar_log(f"LLMDebugger: Erro durante a depuração assistida por LLM: {e}", log_level="ERROR")
            return {"analysis": f"Erro na depuração LLM: {e}", "confidence_score": 0.0}