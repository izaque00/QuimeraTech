import re
import random
import logging
from typing import Any, Tuple, Optional, Callable, List

from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)

def mutacao_simplificacao_contexto(patch: str, **kwargs) -> Tuple[str, None]:
    montar_log("Aplicando heurística: mutacao_simplificacao_contexto.", "DEBUG")
    if not patch: return patch, None
    linhas_patch = patch.splitlines()
    novo_patch_linhas = []
    for linha in linhas_patch:
        if linha.startswith('--- a/') or linha.startswith('+++ b/'):
            novo_patch_linhas.append(linha)
        elif linha.startswith('@@'):
            break
    hunk_header_re = re.compile(r'^(@@\s*[-+]\d+(,\d+)?\s*[-+]\d+(,\d+)?\s*@@.*)')
    in_hunk = False
    for linha in linhas_patch:
        if hunk_header_re.match(linha):
            novo_patch_linhas.append(linha)
            in_hunk = True
        elif in_hunk and (linha.startswith('+') or linha.startswith('-')):
            novo_patch_linhas.append(linha)
    return "\n".join(novo_patch_linhas) + "\n", None

def mutacao_limpeza_semantica(patch: str, **kwargs) -> Tuple[str, None]:
    montar_log("Aplicando heurística: mutacao_limpeza_semantica.", "DEBUG")
    if not patch: return patch, None
    linhas_finais = []
    blank_or_comment_re = re.compile(r'^[+\-]\s*($|//.*|/\*.*\*/\s*$)')
    for linha in patch.splitlines():
        if not blank_or_comment_re.match(linha):
            linhas_finais.append(linha)
    return "\n".join(linhas_finais) + "\n", None

def mutacao_troca_operador_logico(patch: str, **kwargs) -> Tuple[str, None]:
    montar_log("Aplicando heurística: mutacao_troca_operador_logico.", "DEBUG")
    if not patch: return patch, None
    trocas_possiveis = [("==", "!="), ("!=", "=="), ("&&", "||"), ("||", "&&"), (">", "<="), ("<", ">="), (">=", "<"), ("<=", ">")]
    random.shuffle(trocas_possiveis)
    linhas_patch = patch.splitlines()
    mutado = False
    for i, linha in enumerate(linhas_patch):
        if linha.startswith('+') and not linha.startswith('+++'):
            for op_original, op_novo in trocas_possiveis:
                if op_original in linha:
                    linhas_patch[i] = linha.replace(op_original, op_novo, 1)
                    montar_log(f"Operador '{op_original}' trocado por '{op_novo}' na linha {i+1}.", "DEBUG")
                    mutado = True
                    break
            if mutado:
                break
    if mutado:
        return "\n".join(linhas_patch) + "\n", None
    return patch, None

async def mutacao_reformulacao_llm(patch: str, llm_client: Any, **kwargs) -> Tuple[str, None]:
    montar_log("Aplicando heurística: mutacao_reformulacao_llm (reescrita completa).", "INFO")
    if not patch or not llm_client: return patch, None
    prompt = f"""
Você é um Engenheiro de Kernel Linux Sênior e especialista em refatoração de código.
Analise o seguinte patch e o reescreva para ser mais eficiente, seguro e perfeitamente alinhado ao estilo de código do kernel.
Mantenha o objetivo funcional do patch original, mas melhore sua implementação.
Se o patch original já for excelente, retorne-o sem modificações.
Sua resposta deve conter APENAS o bloco de código do novo patch, no formato diff.

Patch Original para Refinar:
```diff
{patch}


Sua Versão Refinada (apenas o patch):

Generated diff
"""
    try:
        resposta_obj = await llm_client.ainvoke(prompt)
        resposta_bruta = resposta_obj.content
        match = re.search(r"```diff\n(.*?)```", resposta_bruta, re.DOTALL)
        if match:
            patch_refinado = match.group(1).strip()
            return patch_refinado + "\n", None
        montar_log("LLM não formatou a resposta da reformulação corretamente. Retornando patch original.", "WARNING")
        return patch, None
    except Exception as e:
        montar_log(f"Erro na heurística de reformulação LLM: {e}", "ERROR", exc_info=True)
        return patch, None

HEURISTICAS: List[Callable] = [
    mutacao_simplificacao_contexto,
    mutacao_limpeza_semantica,
    mutacao_troca_operador_logico,
    mutacao_reformulacao_llm,
]