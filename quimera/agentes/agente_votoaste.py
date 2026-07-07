# quimera/agentes/agente_votoaste.py

import logging
import asyncio
import subprocess
import tempfile
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

# pycparser é necessário para a análise real da AST de código C.
# Adicionar 'pycparser' ao requirements.txt
from pycparser import c_parser, c_ast, parse_file

# Importações de componentes do sistema Quimera
from quimera.quadro_negro import QuadroNegro
from quimera.utils.linter import check_code_lint # Usado para o voto de "estilo"
from quimera.utils.controle import verificar_padroes_inseguros
from quimera.core.vector_manager import VectorManager
from quimera.utils.refactor_utils import rollback_best_version

logger = logging.getLogger(__name__)

class C_AST_Parser:
    """Encapsula a lógica para parsear código C usando pycparser, lidando com o pré-processamento."""
    def __init__(self):
        self.parser = c_parser.CParser()

    def _preprocess_code(self, code: str, c_file_path: str) -> Optional[str]:
        """Usa o pré-processador do GCC para expandir includes e macros."""
        try:
            # Escreve o código em um arquivo temporário para o pré-processador
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.c', dir=os.path.dirname(c_file_path)) as tmp_file:
                tmp_file.write(code)
                tmp_file_path = tmp_file.name

            # Invoca gcc -E. Assume que estamos em um ambiente com toolchain de compilação.
            # -I. para incluir o diretório atual na busca por headers.
            cmd = ['gcc', '-E', '-I.', tmp_file_path]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
            return result.stdout
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.error(f"Falha no pré-processamento do código C: {e}")
            return None
        finally:
            if 'tmp_file_path' in locals() and os.path.exists(tmp_file_path):
                os.remove(tmp_file_path)

    def parse(self, code: str, file_path: str) -> Optional[c_ast.FileAST]:
        """Tenta parsear o código C, pré-processando-o primeiro."""
        processed_code = self._preprocess_code(code, file_path)
        if not processed_code:
            return None
        try:
            ast = self.parser.parse(processed_code, filename=file_path)
            return ast
        except c_parser.ParseError as e:
            logger.warning(f"Erro de parsing na AST C para '{file_path}': {e}")
            return None


class KanVisitor(c_ast.NodeVisitor):
    """NodeVisitor para percorrer a AST C e realizar análises simbólicas."""
    def __init__(self):
        self.resultados = {'recursao_infinita': False, 'atribuicao_nula_ponteiro': False}
        self.current_function = None

    def visit_FuncDef(self, node):
        self.current_function = node.decl.name
        self.generic_visit(node)
        self.current_function = None

    def visit_FuncCall(self, node):
        if isinstance(node.name, c_ast.ID) and node.name.name == self.current_function:
            self.resultados['recursao_infinita'] = True
            logger.warning(f"Detecção de recursão direta na função '{self.current_function}'!")
        self.generic_visit(node)

    def visit_Assignment(self, node):
        # Verifica se estamos atribuindo a um ponteiro desreferenciado (ex: *p = 0)
        if isinstance(node.lvalue, c_ast.UnaryOp) and node.lvalue.op == '*':
            # Verifica se o valor atribuído é uma constante zero
            if isinstance(node.rvalue, c_ast.Constant) and node.rvalue.value == '0':
                self.resultados['atribuicao_nula_ponteiro'] = True
                logger.info("Detecção de atribuição de constante nula a um ponteiro.")
        self.generic_visit(node)


class AgenteKanValidador:
    """Realiza validação simbólica em uma AST de código C."""
    def __init__(self):
        self.c_parser = C_AST_Parser()

    async def rotular_codigo_simbolico(self, code: str, file_path: str) -> Dict[str, Any]:
        ast = self.c_parser.parse(code, file_path)
        if not ast:
            return {"status": "falha_parsing_c", "score": 0.1}

        visitor = KanVisitor()
        visitor.visit(ast)

        score = 1.0
        if visitor.resultados['recursao_infinita']: score -= 0.8
        if visitor.resultados['atribuicao_nula_ponteiro']: score -= 0.1 # Pode ser legítimo

        return {"status": "sucesso", "score": max(0.0, score), "detalhes": visitor.resultados}


class NeuralVoteMachine:
    """Agrega múltiplas análises de código para gerar um score de qualidade."""
    def __init__(self):
        self.vector_manager = VectorManager()
        self.kan_validator = AgenteKanValidador()
        logger.info("NeuralVoteMachine inicializada com componentes de análise reais.")

    async def get_votes(self, codigo_proposto: str, codigo_original: str, caminho_arquivo: str) -> Dict[str, Any]:
        votos = {}
        # É preciso salvar o código proposto em um arquivo temporário para o linter
        with tempfile.NamedTemporaryFile(mode='w', delete=True, suffix='.c') as tmp_proposto:
            tmp_proposto.write(codigo_proposto)
            tmp_proposto.flush()

            # 1. Voto de Estilo (Lint) - Simulado com pylint, ideal seria um linter C
            lint_result = check_code_lint(tmp_proposto.name, codigo_proposto) # Reutilizando a função
            votos['lint_score'] = lint_result.get('lint_score', 0.0) / 10.0

        # 2. Voto de Segurança
        security_result = verificar_padroes_inseguros(codigo_proposto)
        votos['security_score'] = 1.0 if security_result.get('seguro') else 0.05

        # 3. Voto de Análise Simbólica (Kan com AST C)
        kan_result = await self.kan_validator.rotular_codigo_simbolico(codigo_proposto, caminho_arquivo)
        votos['symbolic_score'] = kan_result.get('score', 0.0)

        # 4. Voto de Drift Vetorial
        vetor_original = self.vector_manager.as_full_vector(codigo_original)
        vetor_proposto = self.vector_manager.as_full_vector(codigo_proposto)
        drift = self.vector_manager.get_drift(vetor_original, vetor_proposto)
        votos['drift_score'] = 1.0 - drift

        return votos

    def consolidar_votos(self, votos: Dict[str, Any]) -> float:
        pesos = {'lint_score': 0.15, 'security_score': 0.45, 'symbolic_score': 0.25, 'drift_score': 0.15}
        score_final = sum(votos.get(chave, 0.0) * peso for chave, peso in pesos.items())
        return round(score_final, 4)


class AgenteRevisorAssemble:
    """Orquestra o NeuralVoteMachine para produzir uma avaliação de qualidade final."""
    MIN_QUALITY_SCORE = 0.65

    def __init__(self, quadro_negro: QuadroNegro):
        self.quadro_negro = quadro_negro
        self.voting_engine = NeuralVoteMachine()
        logger.info("AgenteRevisorAssemble (Votoaste) inicializado.")

    async def avaliar_proposta_de_codigo(self, codigo_proposto: str, caminho_arquivo: str) -> Dict[str, Any]:
        logger.info(f"Iniciando ciclo de análise e voto para: {caminho_arquivo}...")
        try:
            codigo_original = Path(caminho_arquivo).read_text(encoding='utf-8')
        except FileNotFoundError: return {"status": "falha_critica", "motivo": f"Arquivo original não encontrado: {caminho_arquivo}"}

        votos = await self.voting_engine.get_votes(codigo_proposto, codigo_original, caminho_arquivo)
        score_final = self.voting_engine.consolidar_votos(votos)

        resultado_completo = {"caminho_arquivo": caminho_arquivo, "score_qualidade_final": score_final, "votos_detalhados": votos}

        self.quadro_negro.publicar_artefato(f"avaliacao_votoaste:{os.path.basename(caminho_arquivo)}", resultado_completo, autor=self.__class__.__name__)

        if score_final >= self.MIN_QUALITY_SCORE:
            logger.info(f"Proposta para '{caminho_arquivo}' APROVADA com score final de {score_final:.2f}.")
            return {"status": "aprovado", "resultado": resultado_completo}
        else:
            logger.warning(f"Proposta para '{caminho_arquivo}' REJEITADA com score final de {score_final:.2f}.")
            return {"status": "rejeitado", "motivo": "Baixo score de qualidade na votação.", "resultado": resultado_completo}