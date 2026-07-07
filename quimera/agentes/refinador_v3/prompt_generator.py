# quimera/agentes/refinador_v3/prompt_generator.py

import json
from typing import Any, Dict

def gerar_prompt_refinamento(
    patch: str,
    sugestao: str,
    ponto_fraco: str,
    causa: Any
) -> str:
    """
    Gera um prompt de alta fidelidade e estruturado para o LLM, instruindo-o a
    refinar um patch com base em um feedback de engenharia específico e detalhado.

    Esta versão é robusta contra erros de sintaxe de f-string.
    """

    # Serializa a causa raiz de forma segura
    try:
        if isinstance(causa, dict):
            causa_txt = json.dumps(causa, indent=2, ensure_ascii=False, sort_keys=True)
        elif isinstance(causa, str):
            causa_txt = causa
        else:
            causa_txt = "Informação de causa raiz não disponível."
    except Exception:
        causa_txt = "Erro ao serializar a análise da causa raiz."

    # Construção em partes para evitar unterminated string literal
    partes_do_prompt = [
        "<|SYSTEM|>",
        "Você é um engenheiro de software de elite, especialista em otimização de patches para o kernel Linux.",
        "Sua tarefa é pegar um patch existente que tem falhas e refiná-lo para a perfeição técnica.",
        "A sua precisão é fundamental.",
        "",
        "<|DOSSIÊ DE REFINAMENTO|>",
        "",
        "**1. CONTEXTO DO PROBLEMA ORIGINAL (NÃO ESQUEÇA O OBJETIVO):**",
        "```json",
        causa_txt,
        "```",
        "",
        "**2. PATCH ATUAL (A SER REFINADO):**",
        "Este patch foi proposto, mas falhou na validação ou na compilação.",
        "```diff",
        patch,
        "```",
        "",
        "**3. FEEDBACK DA ANÁLISE CRÍTICA ANTERIOR:**",
        "Esta é a razão pela qual o patch precisa de refinamento.",
        f"*   **Ponto Fraco Identificado:** {ponto_fraco}",
        f"*   **Sugestão de Melhoria / Log de Erro:** {sugestao}",
        "",
        "<|MISSÃO|>",
        "",
        "**SUA TAREFA DE REFINAMENTO (REGRAS ESTRITAS):**",
        "1.  **Analise o Feedback:** Entenda por que o patch atual foi considerado imperfeito.",
        "    Se o feedback for um log de compilação, resolva o erro de compilação.",
        "    Se for uma sugestão de lógica, aplique-a.",
        "2.  **Aplique a Correção:** Modifique o patch para incorporar a sugestão de melhoria ou corrigir o erro de compilação.",
        "3.  **Aumente a Precisão:** Remova qualquer código ou contexto desnecessário.",
        "    O patch deve ser o menor e mais preciso possível para resolver o problema, seguindo as melhores práticas do kernel.",
        "4.  **Formato de Saída ABSOLUTO:** Sua resposta deve conter **APENAS e SOMENTE** o bloco de código do patch refinado,",
        "    no formato 'unified diff', encapsulado em ```diff ... ```.",
        "5.  **Contexto Perfeito (CRÍTICO):** Garanta que as linhas de contexto (as que não começam com `+` ou `-`) sejam",
        "    **EXATAMENTE IGUAIS** ao código original do arquivo. Não invente ou modifique as linhas de contexto.",
        "6.  **NENHUM TEXTO ADICIONAL:** Não inclua explicações, justificativas, saudações ou qualquer caractere fora do bloco de código do diff.",
        "",
        "<|SAÍDA ESPERADA|>",
        "```diff",
        "--- a/caminho/do/arquivo.c",
        "+++ b/caminho/do/arquivo.c",
        "@@ -linha,n +linha,n @@",
        " código de contexto...",
        "- linha antiga problemática",
        "+ linha nova, corrigida e otimizada",
        "```"
    ]

    return "\n".join(partes_do_prompt)