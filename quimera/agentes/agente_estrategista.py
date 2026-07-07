# quimera/agentes/agente_estrategista.py

import sys
import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

# pycparser é necessário para a análise real da AST de código C.
from pycparser import c_parser, c_ast

# Importações de componentes do sistema Quimera
from quimera.quadro_negro import QuadroNegro
from quimera.agentes.agente_votoaste import C_AST_Parser # Reutiliza o parser C
from quimera.utils.controle import verificar_padroes_inseguros

logger = logging.getLogger(__name__)

# --- Estratégias de Reparo Definidas ---
ESTRATEGIA_REPARO_PADRAO = "REPARO_PADRAO"
ESTRATEGIA_REPARO_CONSERVADOR = "REPARO_CONSERVADOR"
ESTRATEGIA_REVISAO_SEGURANCA_URGENTE = "REVISAO_DE_SEGURANCA_URGENTE"


class ASTComplexityAnalyzer(c_ast.NodeVisitor):
    """
    Um NodeVisitor que percorre uma AST de código C para calcular métricas
    de complexidade, como a Complexidade Ciclomática de McCabe.
    """
    def __init__(self):
        self.complexity = 1  # A complexidade começa em 1 (para o caminho único de saída)
        self.decision_points = 0

    def visit_If(self, node):
        self.decision_points += 1
        self.generic_visit(node)

    def visit_For(self, node):
        self.decision_points += 1
        self.generic_visit(node)

    def visit_While(self, node):
        self.decision_points += 1
        self.generic_visit(node)

    def visit_Case(self, node): # para switch-case
        self.decision_points += 1
        self.generic_visit(node)

    def visit_BinaryOp(self, node):
        if node.op in ['&&', '||']:
            self.decision_points += 1
        self.generic_visit(node)

    def calculate_complexity(self, node: c_ast.FileAST) -> int:
        """Calcula a Complexidade Ciclomática."""
        self.visit(node)
        # Complexidade de McCabe = (Arestas - Nós + 2 * Componentes Conectados)
        # Uma aproximação comum é (Pontos de Decisão + 1)
        self.complexity = self.decision_points + 1
        return self.complexity


class AgenteEstrategista:
    """
    Agente de meta-nível responsável por analisar a complexidade e o risco
    de um arquivo de código para definir a estratégia de reparo mais adequada
    a ser seguida pelo OrquestradorIA.
    """

    COMPLEXITY_THRESHOLD_ALTA = 15
    COMMENT_DENSITY_THRESHOLD_BAIXA = 0.05 # Menos de 5% de linhas são comentários

    def __init__(self, quadro_negro: QuadroNegro):
        """
        Inicializa o AgenteEstrategista.
        """
        self.quadro_negro = quadro_negro
        self.c_parser = C_AST_Parser()
        self.complexity_analyzer = ASTComplexityAnalyzer()
        logger.info("AgenteEstrategista inicializado.")

    def _calcular_densidade_comentarios(self, codigo: str) -> float:
        """Calcula a proporção de linhas de comentário em relação ao total de linhas."""
        linhas = codigo.splitlines()
        if not linhas: return 0.0

        linhas_comentario = sum(1 for linha in linhas if linha.strip().startswith(('//', '/*', '*', '*/')))
        return linhas_comentario / len(linhas)

    async def observar_e_definir_estrategia(self, caminho_arquivo: str) -> Dict[str, Any]:
        """
        Analisa um arquivo de código-fonte e produz uma "Ficha de Estratégia"
        recomendando o melhor curso de ação para o reparo.

        Args:
            caminho_arquivo (str): O caminho do arquivo a ser analisado.

        Returns:
            Dict[str, Any]: A Ficha de Estratégia gerada.
        """
        logger.info(f"Análise estratégica iniciada para o arquivo: {caminho_arquivo}")

        try:
            codigo = Path(caminho_arquivo).read_text(encoding='utf-8', errors='ignore')
        except FileNotFoundError:
            return {"status": "falha_analise", "motivo": f"Arquivo não encontrado: {caminho_arquivo}"}

        # --- Coleta de Métricas ---
        # 1. Análise de Segurança
        analise_seguranca = verificar_padroes_inseguros(codigo)

        # 2. Análise de Complexidade AST
        ast_c = self.c_parser.parse(codigo, caminho_arquivo)
        complexidade_ciclo = 0
        if ast_c:
            complexidade_ciclo = self.complexity_analyzer.calculate_complexity(ast_c)
        else:
            logger.warning(f"Não foi possível gerar AST para '{caminho_arquivo}'. A análise de complexidade será 0.")

        # 3. Análise de Documentação (Densidade de Comentários)
        densidade_comentarios = self._calcular_densidade_comentarios(codigo)

        # --- Lógica de Decisão da Estratégia ---
        estrategia_recomendada = ESTRATEGIA_REPARO_PADRAO
        justificativa = "Código com complexidade e documentação dentro dos parâmetros normais. O fluxo de reparo padrão é recomendado."

        if not analise_seguranca['seguro']:
            estrategia_recomendada = ESTRATEGIA_REVISAO_SEGURANCA_URGENTE
            justificativa = (f"ALERTA MÁXIMO: Padrões de código inseguros detectados. "
                             f"Recomenda-se priorizar a correção de segurança. Detalhes: {analise_seguranca['detalhes']}")

        elif complexidade_ciclo > self.COMPLEXITY_THRESHOLD_ALTA:
            estrategia_recomendada = ESTRATEGIA_REPARO_CONSERVADOR
            justificativa = (f"Código com alta complexidade ciclomática ({complexidade_ciclo}). "
                             f"Recomenda-se uma abordagem de reparo conservadora, com mais rodadas de validação e LLMs robustos.")

        elif densidade_comentarios < self.COMMENT_DENSITY_THRESHOLD_BAIXA:
            estrategia_recomendada = ESTRATEGIA_REPARO_CONSERVADOR
            justificativa = (f"Código com baixa densidade de comentários ({densidade_comentarios:.2%}). "
                             f"O risco de introduzir regressões é maior. Recomenda-se uma abordagem conservadora.")

        # --- Geração da Ficha de Estratégia ---
        ficha_estrategia = {
            "caminho_arquivo": caminho_arquivo,
            "estrategia_recomendada": estrategia_recomendada,
            "justificativa": justificativa,
            "metricas_analisadas": {
                "complexidade_ciclomatica": complexidade_ciclo,
                "densidade_comentarios": round(densidade_comentarios, 4),
                "verificacao_seguranca": analise_seguranca
            }
        }

        # Publica a ficha no Quadro Negro para o Orquestrador
        self.quadro_negro.publicar_artefato(
            f"ficha_estrategia:{os.path.basename(caminho_arquivo)}",
            ficha_estrategia,
            autor=self.__class__.__name__
        )

        logger.info(f"Estratégia definida para '{caminho_arquivo}': {estrategia_recomendada}")
        return {"status": "sucesso_analise", "ficha_estrategia": ficha_estrategia}