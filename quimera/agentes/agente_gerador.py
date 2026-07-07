# quimera/agentes/agente_gerador.py

import sys
import logging
import re
import json
import os
from datetime import datetime
from typing import List, Any, Optional

from quimera.quadro_negro import QuadroNegro
from quimera.core.knowledge_base import KnowledgeBase
from quimera.db.base import get_db
from quimera.db.models import HistoricoRefatoracao
from quimera import config
from quimera.logs.parser import montar_log
from quimera.utils.general import get_code
import hashlib

logger = logging.getLogger(__name__)

def _get_code_snippet(full_code: str, line_number: int, context_lines: int = 40) -> str:
    if not full_code:
        return ""
    lines = full_code.splitlines()
    start = max(0, line_number - context_lines - 1)
    end = min(len(lines), line_number + context_lines)
    return "\n".join(lines[start:end])

class AgenteGerador:
    def __init__(self, llm_clientes: List[Any], nome_modelo: str):
        if not llm_clientes or not llm_clientes[0]:
            raise ValueError(f"AgenteGerador para '{nome_modelo}' requer um cliente LLM válido.")
        self.llm_cliente = llm_clientes[0]
        self.nome_modelo = nome_modelo
        self.quadro_negro = QuadroNegro()
        self.knowledge_base = KnowledgeBase()
        montar_log(f"AgenteGerador (Modelo: {self.nome_modelo}) inicializado.", "INFO")

    def _criar_prompt_missao(self, analise_causa_raiz: dict, log_erro_compilacao: str, code_snippet: str = "", caso_similar: Optional[dict] = None) -> str:
        contexto_memoria = ""
        if caso_similar and caso_similar.get('diff'):
            contexto_memoria = (
                "### CONTEXTO DE UM CASO SIMILAR RESOLVIDO:\n"
                "Use esta solução anterior como forte referência para o problema atual.\n"
                f"Patch da solução anterior:\n```diff\n{caso_similar.get('diff')}\n```\n\n"
            )

        contexto_codigo = ""
        if code_snippet:
            arquivo_afetado = analise_causa_raiz.get("arquivo_afetado", "desconhecido")
            linha_suspeita = analise_causa_raiz.get("linha_suspeita", "N/A")
            contexto_codigo = (
                f"### SNIPPET RELEVANTE DO ARQUIVO '{arquivo_afetado}' (em torno da linha {linha_suspeita}) ###\n"
                f"```c\n{code_snippet}\n```\n"
            )

        prompt_base = f"""
Você é um especialista de classe mundial em engenharia de kernel Linux. Sua tarefa é gerar um patch funcional para corrigir o erro de compilação descrito abaixo.

{contexto_memoria}
### LOG DE ERRO DE COMPILAÇÃO:
{log_erro_compilacao}

### ANÁLISE DA CAUSA RAIZ FORNECIDA:
{json.dumps(analise_causa_raiz, indent=2)}

{contexto_codigo}
### INSTRUÇÕES CRÍTICAS:
1. Baseie-se na análise da causa raiz e no contexto fornecido.
2. Gere um patch completo e funcional no formato "unified diff".
3. Siga rigorosamente o estilo de codificação do kernel Linux (indentação com tabs, limite de 80 colunas, etc.).
4. O patch deve ser autocontido e não exigir outras modificações.
5. Responda APENAS com o código do patch. NÃO inclua explicações, comentários ou qualquer texto adicional.

```diff
"""
        return prompt_base.strip()

    def _extrair_patch_da_resposta(self, resposta_bruta: Any) -> Optional[str]:
        if not isinstance(resposta_bruta, str):
            montar_log("Resposta do LLM não é uma string.", "WARNING", extra={"tipo": str(type(resposta_bruta))})
            return None

        match = re.search(r"```(?:diff)?\s*\n(.*?)\n```", resposta_bruta, re.DOTALL)
        if match:
            return match.group(1).strip()

        if '--- a/' in resposta_bruta and '+++ b/' in resposta_bruta:
            start_index = resposta_bruta.find('--- a/')
            return resposta_bruta[start_index:].strip()

        montar_log("Não foi possível extrair um patch válido da resposta do LLM.", "WARNING", extra={"resposta_bruta": resposta_bruta})
        return None

    async def gerar_patch(self, analise_causa_raiz: dict, log_erro_compilacao: str) -> Optional[str]:
        montar_log(f"AgenteGerador ({self.nome_modelo}): Iniciando geração de patch (ciclo de fallback).", "INFO")

        arquivo_afetado = analise_causa_raiz.get("arquivo_afetado")
        if not arquivo_afetado:
            montar_log("Análise da causa raiz não contém 'arquivo_afetado'. Geração de patch abortada.", "ERROR")
            return None

        kernel_root = os.getenv("KERNEL_ROOT")
        full_code = get_code(kernel_root, arquivo_afetado)
        if not full_code:
            montar_log(f"Não foi possível obter o código para {arquivo_afetado}. Geração de patch abortada.", "ERROR")
            return None

        linha_suspeita = analise_causa_raiz.get("linha_suspeita", 1)
        code_snippet = _get_code_snippet(full_code, linha_suspeita)

        caso_similar = self.knowledge_base.buscar_solucao_similar(log_erro_compilacao)
        if caso_similar:
            montar_log("Caso similar encontrado na base de conhecimento. Usando como contexto.", "INFO")

        prompt = self._criar_prompt_missao(analise_causa_raiz, log_erro_compilacao, code_snippet, caso_similar)

        try:
            resposta_llm_obj = await self.llm_cliente.ainvoke(prompt)
            resposta_str = getattr(resposta_llm_obj, 'content', resposta_llm_obj)
            patch_proposto = self._extrair_patch_da_resposta(resposta_str)

            if patch_proposto:
                montar_log(f"AgenteGerador ({self.nome_modelo}): Patch gerado com sucesso.", "SUCCESS")
                patch_id = hashlib.sha256(patch_proposto.encode('utf-8')).hexdigest()[:12]
                self.quadro_negro.publicar_artefato(
                    f"{config.PATCH_GERADO_KEY}_{patch_id}",
                    {
                        "patch_content": patch_proposto,
                        "gerador": self.nome_modelo,
                        "timestamp": datetime.now().isoformat()
                    },
                    self.__class__.__name__
                )

                # Armazena o histórico no banco de dados
                async for session in get_db():
                    novo_registro = HistoricoRefatoracao(
                        arquivo=arquivo_afetado,
                        patch=patch_proposto,
                        modelo=self.nome_modelo,
                        data=datetime.utcnow()
                    )
                    session.add(novo_registro)
                    await session.commit()

                return patch_proposto
            else:
                montar_log(f"AgenteGerador ({self.nome_modelo}): A resposta do LLM não continha um patch válido.", "WARNING")
                return None
        except Exception as e:
            montar_log(f"AgenteGerador ({self.nome_modelo}): Exceção durante a chamada da API do LLM: {e}", "ERROR", exc_info=True)
            return None