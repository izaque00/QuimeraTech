"""Lint Extractors — Funções puras e reutilizáveis para detecção de problemas em código.

Extraídas do agente_fiscal_codigo.py como funções independentes para:
- Eliminar duplicação de I/O (lê arquivo uma vez, passa conteúdo)
- Permitir composição e testes unitários
- Separar detecção de relatório

Uso:
    from quimera.utils.lint_extractors import (
        detectar_problemas_sintaxe,
        detectar_problemas_indentacao,
        detectar_problemas_estilo,
        detectar_problemas_imports,
        detectar_todos_problemas,
    )
"""

import ast
import re
import logging
from typing import List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ProblemaDetectado:
    """Um problema de código detectado."""
    arquivo: str
    linha: int
    coluna: int = 0
    tipo: str = "unknown"
    severidade: str = "warning"
    descricao: str = ""
    codigo_problema: str = ""
    sugestao_correcao: str = ""
    regra_violada: str = ""


def _sugerir_correcao_sintaxe(error: SyntaxError) -> str:
    """Sugere correção com base no tipo de SyntaxError."""
    sugestoes = {
        "invalid syntax": "Verifique a sintaxe da linha — possível erro de digitação ou caractere inválido.",
        "unexpected EOF": "String ou bloco não foi fechado corretamente.",
        "EOL while scanning": "String literal não foi fechada com aspa.",
        "invalid character": "Caractere não-ASCII ou inválido encontrado.",
    }
    msg = str(error.msg).lower()
    for key, sug in sugestoes.items():
        if key in msg:
            return sug
    return f"Erro de sintaxe: {error.msg}"


def detectar_problemas_sintaxe(
    conteudo: str, arquivo: str = "<string>"
) -> List[ProblemaDetectado]:
    """Detecta problemas de sintaxe Python usando AST.

    Args:
        conteudo: Conteúdo do arquivo como string.
        arquivo: Nome do arquivo para relatório.

    Returns:
        Lista de ProblemaDetectado (vazia se sem erros).
    """
    problemas: List[ProblemaDetectado] = []
    try:
        ast.parse(conteudo)
    except SyntaxError as e:
        problemas.append(
            ProblemaDetectado(
                arquivo=arquivo,
                linha=e.lineno or 0,
                coluna=e.offset or 0,
                tipo="syntax",
                severidade="critical",
                descricao=f"Erro de sintaxe: {e.msg}",
                codigo_problema=(e.text or "").strip(),
                sugestao_correcao=_sugerir_correcao_sintaxe(e),
                regra_violada="SyntaxError",
            )
        )
        logger.debug(f"Sintaxe: erro em {arquivo}:{e.lineno} — {e.msg}")
    return problemas


def detectar_problemas_indentacao(
    conteudo: str, arquivo: str = "<string>"
) -> List[ProblemaDetectado]:
    """Detecta problemas de indentação (tabs vs espaços, indentação inconsistente).

    Args:
        conteudo: Conteúdo do arquivo como string.
        arquivo: Nome do arquivo para relatório.

    Returns:
        Lista de ProblemaDetectado.
    """
    problemas: List[ProblemaDetectado] = []
    linhas = conteudo.splitlines()

    tem_tabs = any("\t" in line for line in linhas)
    tem_espacos = any(line.startswith(" ") for line in linhas)

    if tem_tabs and tem_espacos:
        problemas.append(
            ProblemaDetectado(
                arquivo=arquivo,
                linha=1,
                tipo="style",
                severidade="warning",
                descricao="Arquivo mistura tabs e espaços para indentação.",
                sugestao_correcao="Converta todos os tabs para 4 espaços.",
                regra_violada="mixed-indentation",
            )
        )

    for i, line in enumerate(linhas, start=1):
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        if indent > 0 and indent % 4 != 0:
            problemas.append(
                ProblemaDetectado(
                    arquivo=arquivo,
                    linha=i,
                    coluna=indent,
                    tipo="style",
                    severidade="info",
                    descricao=f"Indentação de {indent} espaços não é múltipla de 4.",
                    sugestao_correcao=f"Ajuste para {((indent // 4) + 1) * 4} espaços.",
                    regra_violada="indentation-multiple-of-4",
                )
            )
    return problemas


def detectar_problemas_estilo(
    conteudo: str, arquivo: str = "<string>", max_linha: int = 100
) -> List[ProblemaDetectado]:
    """Detecta problemas de estilo: linhas longas, trailing whitespace, prints.

    Args:
        conteudo: Conteúdo do arquivo como string.
        arquivo: Nome do arquivo para relatório.
        max_linha: Comprimento máximo de linha aceitável.

    Returns:
        Lista de ProblemaDetectado.
    """
    problemas: List[ProblemaDetectado] = []
    linhas = conteudo.splitlines()

    for i, line in enumerate(linhas, start=1):
        if len(line) > max_linha:
            problemas.append(
                ProblemaDetectado(
                    arquivo=arquivo,
                    linha=i,
                    coluna=max_linha,
                    tipo="style",
                    severidade="warning",
                    descricao=f"Linha muito longa ({len(line)} > {max_linha} caracteres).",
                    sugestao_correcao="Quebre a linha em múltiplas linhas.",
                    regra_violada="line-too-long",
                )
            )

        if line.rstrip() != line:
            problemas.append(
                ProblemaDetectado(
                    arquivo=arquivo,
                    linha=i,
                    tipo="style",
                    severidade="info",
                    descricao="Trailing whitespace encontrado.",
                    sugestao_correcao="Remova espaços em branco no final da linha.",
                    regra_violada="trailing-whitespace",
                )
            )

    return problemas


def detectar_problemas_imports(
    conteudo: str, arquivo: str = "<string>"
) -> List[ProblemaDetectado]:
    """Detecta problemas com imports: wildcard, relativos, não utilizados.

    Args:
        conteudo: Conteúdo do arquivo como string.
        arquivo: Nome do arquivo para relatório.

    Returns:
        Lista de ProblemaDetectado.
    """
    problemas: List[ProblemaDetectado] = []
    linhas = conteudo.splitlines()

    for i, line in enumerate(linhas, start=1):
        if re.match(r"^\s*from\s+\S+\s+import\s+\*", line):
            problemas.append(
                ProblemaDetectado(
                    arquivo=arquivo,
                    linha=i,
                    tipo="style",
                    severidade="warning",
                    descricao="Wildcard import (*) — polui o namespace.",
                    sugestao_correcao="Importe apenas os nomes necessários explicitamente.",
                    regra_violada="wildcard-import",
                )
            )

        if "import" in line and "sys.path" in line:
            problemas.append(
                ProblemaDetectado(
                    arquivo=arquivo,
                    linha=i,
                    tipo="design",
                    severidade="warning",
                    descricao="Manipulação de sys.path — frágil e imprevisível.",
                    sugestao_correcao="Use instalação via pip -e . ou PYTHONPATH.",
                    regra_violada="sys-path-manipulation",
                )
            )

    return problemas


def detectar_todos_problemas(
    conteudo: str, arquivo: str = "<string>", max_linha: int = 100
) -> List[ProblemaDetectado]:
    """Executa todos os detectores em uma única passagem.

    Lê o conteúdo uma vez e aplica todos os detectores, evitando
    o problema de 4x I/O desnecessário do código original.

    Args:
        conteudo: Conteúdo do arquivo como string.
        arquivo: Nome do arquivo para relatório.
        max_linha: Comprimento máximo de linha aceitável.

    Returns:
        Lista combinada de ProblemaDetectado de todos os detectores.
    """
    problemas: List[ProblemaDetectado] = []
    problemas.extend(detectar_problemas_sintaxe(conteudo, arquivo))
    problemas.extend(detectar_problemas_indentacao(conteudo, arquivo))
    problemas.extend(detectar_problemas_estilo(conteudo, arquivo, max_linha))
    problemas.extend(detectar_problemas_imports(conteudo, arquivo))
    return problemas
