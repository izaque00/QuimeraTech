# quimera/agentes/refinador_v3/votador_consenso.py

import logging
from typing import List, Dict, Any

from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)

# Se a diferença entre os scores for menor que este valor, critérios de desempate são usados.
# Isso evita que pequenas flutuações no score de um LLM causem uma decisão.
LIMIAR_DESEMPATE = 0.05

def votar_consenso(avaliacoes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Seleciona a melhor avaliação de uma lista usando uma lógica de votação ponderada.

    Primeiro, seleciona o candidato com o maior 'score_final'. Se os scores forem
    muito próximos (dentro do LIMIAR_DESEMPATE), aplica critérios secundários para
    desempatar:
    1. Menor número de erros de estilo (linter).
    2. Menor tamanho de patch (preferência por simplicidade).

    Args:
        avaliacoes (List[Dict[str, Any]]): Uma lista de dicionários, cada um
            representando uma avaliação completa de um patch, incluindo 'score_final',
            'patch' e a estrutura de 'avaliacao' do AgenteCritico.

    Returns:
        Dict[str, Any]: O dicionário de avaliação completo que foi considerado o melhor.
                        Retorna um dicionário vazio se a lista de entrada for vazia.
    """
    if not avaliacoes:
        montar_log("Votador de consenso recebeu uma lista de avaliações vazia.", "WARNING")
        return {}

    # Filtra avaliações inválidas ou sem score
    avaliacoes_validas = [a for a in avaliacoes if isinstance(a, dict) and "score_final" in a]
    if not avaliacoes_validas:
        montar_log("Nenhuma avaliação válida com 'score_final' encontrada para votação.", "ERROR")
        return avaliacoes[0] if avaliacoes else {}

    # Ordena os candidatos do melhor para o pior score
    avaliacoes_ordenadas = sorted(avaliacoes_validas, key=lambda a: a.get("score_final", 0.0), reverse=True)

    melhor_candidato = avaliacoes_ordenadas[0]

    # Se houver apenas um candidato ou a diferença para o segundo for grande, não há desempate.
    if len(avaliacoes_ordenadas) == 1:
        montar_log(f"Votação: Apenas um candidato. Vencedor por padrão com score {melhor_candidato.get('score_final', 0.0):.2f}.", "INFO")
        return melhor_candidato

    segundo_melhor_candidato = avaliacoes_ordenadas[1]
    diferenca_score = melhor_candidato.get("score_final", 0.0) - segundo_melhor_candidato.get("score_final", 0.0)

    if diferenca_score > LIMIAR_DESEMPATE:
        montar_log(f"Votação: Vencedor claro por score ({melhor_candidato.get('score_final', 0.0):.2f}).", "INFO")
        return melhor_candidato

    # --- Lógica de Desempate ---
    montar_log(f"Scores próximos (diferença: {diferenca_score:.3f}). Acionando critérios de desempate...", "DEBUG")

    # Critério 1: Menor número de erros de linter
    try:
        erros_melhor = len(melhor_candidato.get("avaliacao", {}).get("detalhes", {}).get("analise_estilo", {}).get("errors", []))
        erros_segundo = len(segundo_melhor_candidato.get("avaliacao", {}).get("detalhes", {}).get("analise_estilo", {}).get("errors", []))

        if erros_melhor < erros_segundo:
            montar_log(f"Votação: Desempate por erros de linter. Vencedor tem {erros_melhor} erros vs {erros_segundo}.", "INFO")
            return melhor_candidato
        if erros_segundo < erros_melhor:
            montar_log(f"Votação: Desempate por erros de linter. Vencedor tem {erros_segundo} erros vs {erros_melhor}.", "INFO")
            return segundo_melhor_candidato
    except Exception as e:
        montar_log(f"Erro ao acessar dados de linter para desempate: {e}. Pulando critério.", "WARNING")

    # Critério 2: Menor tamanho do patch (simplicidade)
    try:
        tamanho_melhor = len(melhor_candidato.get("patch", ""))
        tamanho_segundo = len(segundo_melhor_candidato.get("patch", ""))

        if tamanho_melhor < tamanho_segundo:
            montar_log(f"Votação: Desempate por tamanho do patch. Vencedor é mais conciso ({tamanho_melhor} vs {tamanho_segundo} caracteres).", "INFO")
            return melhor_candidato
        if tamanho_segundo < tamanho_melhor:
            montar_log(f"Votação: Desempate por tamanho do patch. Vencedor é mais conciso ({tamanho_segundo} vs {tamanho_melhor} caracteres).", "INFO")
            return segundo_melhor_candidato
    except Exception as e:
         montar_log(f"Erro ao acessar dados de patch para desempate: {e}. Pulando critério.", "WARNING")

    # Se todos os critérios de desempate falharem, mantenha o original com maior score.
    montar_log("Votação: Critérios de desempate não foram conclusivos. Mantendo o candidato com maior score inicial.", "INFO")
    return melhor_candidato