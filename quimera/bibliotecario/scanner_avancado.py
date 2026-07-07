"""
Scanner Avançado de Última Geração - Bibliotecário Cognitivo
Sistema de escaneamento e catalogação automática de código-fonte
Tecnologia comparável aos projetos do Google - Nível NASA/Empresarial
"""


# Verificações de dependências adicionadas automaticamente
def verificar_dependencia(nome_modulo, funcionalidade="essa funcionalidade"):
    """Verifica se uma dependência está disponível"""
    try:
        __import__(nome_modulo)
        return True
    except ImportError:
        print(f"⚠️  {nome_modulo} não instalado - {funcionalidade} não disponível")
        return False

import logging
_logger = logging.getLogger(__name__)


def _unavailable_feature(feature_name: str, *args, **kwargs):
    """Loga warning quando funcionalidade não está disponível por falta de dependências."""
    _logger.warning(f"Funcionalidade '{feature_name}' indisponível — dependência não instalada")
    return None

import asyncio
import logging
import os
import json
import hashlib
import time
import subprocess
import tempfile
import shutil
import mimetypes
try:
    import magic
except ImportError:
    magic = None  # Opcional
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from collections import defaultdict, deque
import multiprocessing as mp

# Análise avançada de código
try:
    import tree_sitter
    from tree_sitter import Language, Parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

try:
    import pygments
    from pygments.lexers import get_lexer_for_filename, guess_lexer
    from pygments.token import Token
    PYGMENTS_AVAILABLE = True
except ImportError:
    PYGMENTS_AVAILABLE = False

try:
    import ast
    import astunparse
    AST_AVAILABLE = True
except ImportError:
    AST_AVAILABLE = False

# Machine Learning e NLP
try:
    from transformers import AutoTokenizer, AutoModel, pipeline
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

# Análise de imagens e documentos
try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)


@dataclass
class ArquivoEscaneado:
    """Representa um arquivo completamente escaneado e analisado"""
    caminho: str
    nome: str
    extensao: str
    tamanho: int
    hash_md5: str
    hash_sha256: str
    tipo_mime: str
    linguagem: str
    encoding: str
    linhas_codigo: int
    linhas_comentario: int
    linhas_branco: int
    complexidade_ciclomatica: int
    qualidade_codigo: float
    vulnerabilidades: List[Dict[str, Any]]
    dependencias: List[str]
    imports: List[str]
    funcoes: List[Dict[str, Any]]
    classes: List[Dict[str, Any]]
    variaveis: List[Dict[str, Any]]
    constantes: List[Dict[str, Any]]
    comentarios_extraidos: List[str]
    documentacao: str
    licenca: Optional[str]
    autor: Optional[str]
    data_criacao: Optional[datetime]
    data_modificacao: datetime
    tags_automaticas: List[str]
    categoria: str
    subcategoria: str
    framework_detectado: Optional[str]
    padroes_design: List[str]
    metricas_avancadas: Dict[str, Any]
    embeddings: Optional[List[float]]
    relacionamentos: List[Dict[str, Any]]
    metadados_extras: Dict[str, Any]


@dataclass
class RepositorioEscaneado:
    """Representa um repositório completamente escaneado"""
    url: str
    nome: str
    descricao: str
    linguagem_principal: str
    linguagens_detectadas: Dict[str, int]
    total_arquivos: int
    total_linhas_codigo: int
    estrutura_diretorios: Dict[str, Any]
    dependencias_projeto: List[str]
    frameworks_utilizados: List[str]
    padroes_arquiteturais: List[str]
    qualidade_geral: float
    complexidade_geral: float
    cobertura_documentacao: float
    vulnerabilidades_criticas: int
    licenca_projeto: Optional[str]
    contribuidores: List[str]
    commits_analisados: int
    data_ultimo_commit: Optional[datetime]
    atividade_projeto: str  # 'ativo', 'moderado', 'inativo'
    maturidade_projeto: str  # 'experimental', 'beta', 'estavel', 'maduro'
    tags_projeto: List[str]
    categoria_projeto: str
    readme_analisado: Dict[str, Any]
    changelog_analisado: Dict[str, Any]
    issues_analisadas: Dict[str, Any]
    metricas_git: Dict[str, Any]
    arquivos_escaneados: List[ArquivoEscaneado]
    relatorio_completo: Dict[str, Any]


class AnalisadorLinguagem:
    """Analisador avançado de linguagens de programação"""

    def __init__(self):
        self.parsers = {}
        self.tokenizers = {}
        self.modelos_ml = {}

        # Inicializar componentes se disponíveis
        if TRANSFORMERS_AVAILABLE:
            self._inicializar_modelos_ml()

        if SPACY_AVAILABLE:
            self._inicializar_spacy()

        if TREE_SITTER_AVAILABLE:
            self._inicializar_tree_sitter()

    def _inicializar_modelos_ml(self):
        """Inicializa modelos de Machine Learning para análise de código"""
        try:
            # Modelo para análise de código
            self.modelos_ml['code_analyzer'] = pipeline(
                "text-classification",
                model="microsoft/codebert-base",
                return_all_scores=True
            )

            # Modelo para detecção de vulnerabilidades
            self.modelos_ml['vulnerability_detector'] = pipeline(
                "text-classification",
                model="huggingface/CodeBERTa-small-v1",
                return_all_scores=True
            )

            montar_log("Modelos ML para análise de código inicializados", "INFO")

        except Exception as e:
            montar_log(f"Erro ao inicializar modelos ML: {e}", "WARNING")

    def _inicializar_spacy(self):
        """Inicializa SpaCy para processamento de linguagem natural"""
        try:
            import spacy
            self.nlp = spacy.load("en_core_web_sm")
            montar_log("SpaCy inicializado para análise de documentação", "INFO")
        except Exception as e:
            montar_log(f"Erro ao inicializar SpaCy: {e}", "WARNING")
            self.nlp = None

    def _inicializar_tree_sitter(self):
        """Inicializa Tree-sitter para parsing avançado"""
        try:
            # Configurar parsers para diferentes linguagens
            linguagens = ['c', 'cpp', 'python', 'javascript', 'java', 'go', 'rust']

            for lang in linguagens:
                try:
                    # Em produção, seria configurado adequadamente
                    language = Language(f'build/my-languages.so', lang)
                    parser = Parser()
                    parser.set_language(language)
                    self.parsers[lang] = parser
                except Exception:
                    continue

            montar_log(f"Tree-sitter inicializado para {len(self.parsers)} linguagens", "INFO")

        except Exception as e:
            montar_log(f"Erro ao inicializar Tree-sitter: {e}", "WARNING")

    def detectar_linguagem(self, arquivo: str, conteudo: str) -> str:
        """Detecta a linguagem de programação com alta precisão"""
        # Método 1: Extensão do arquivo
        extensao = Path(arquivo).suffix.lower()

        mapeamento_extensoes = {
            '.c': 'c', '.h': 'c',
            '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.hpp': 'cpp',
            '.py': 'python', '.pyx': 'python',
            '.js': 'javascript', '.jsx': 'javascript', '.ts': 'typescript',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.php': 'php',
            '.rb': 'ruby',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.sh': 'bash', '.bash': 'bash',
            '.sql': 'sql',
            '.html': 'html', '.htm': 'html',
            '.css': 'css',
            '.xml': 'xml',
            '.json': 'json',
            '.yaml': 'yaml', '.yml': 'yaml',
            '.toml': 'toml',
            '.ini': 'ini',
            '.cfg': 'config',
            '.conf': 'config'
        }

        linguagem_extensao = mapeamento_extensoes.get(extensao, 'unknown')

        # Método 2: Análise do conteúdo usando Pygments
        if PYGMENTS_AVAILABLE and linguagem_extensao == 'unknown':
            try:
                lexer = guess_lexer(conteudo[:1000])  # Analisar primeiros 1000 chars
                linguagem_extensao = lexer.name.lower()
            except Exception:
                pass

        # Método 3: Análise de padrões específicos
        if linguagem_extensao == 'unknown':
            linguagem_extensao = self._detectar_por_padroes(conteudo)

        # Método 4: Machine Learning (se disponível)
        if TRANSFORMERS_AVAILABLE and linguagem_extensao == 'unknown':
            linguagem_extensao = self._detectar_com_ml(conteudo)

        return linguagem_extensao

    def _detectar_por_padroes(self, conteudo: str) -> str:
        """Detecta linguagem por padrões específicos"""
        linhas = conteudo.split('\n')[:50]  # Analisar primeiras 50 linhas

        # Padrões específicos
        if any('#include' in linha for linha in linhas):
            return 'c'

        if any('import ' in linha or 'from ' in linha for linha in linhas):
            return 'python'

        if any('function ' in linha or 'var ' in linha or 'let ' in linha for linha in linhas):
            return 'javascript'

        if any('public class' in linha or 'import java' in linha for linha in linhas):
            return 'java'

        if any('package main' in linha or 'func ' in linha for linha in linhas):
            return 'go'

        if any('fn ' in linha or 'use std::' in linha for linha in linhas):
            return 'rust'

        return 'text'

    def _detectar_com_ml(self, conteudo: str) -> str:
        """Detecta linguagem usando Machine Learning"""
        try:
            if 'code_analyzer' in self.modelos_ml:
                # Usar primeiros 512 caracteres para análise
                texto_analise = conteudo[:512]
                resultado = self.modelos_ml['code_analyzer'](texto_analise)

                # Processar resultado e mapear para linguagem
                if resultado and len(resultado) > 0:
                    melhor_score = max(resultado[0], key=lambda x: x['score'])
                    return melhor_score['label'].lower()

        except Exception as e:
            montar_log(f"Erro na detecção ML de linguagem: {e}", "WARNING")

        return 'unknown'

    def analisar_complexidade(self, conteudo: str, linguagem: str) -> int:
        """Calcula complexidade ciclomática avançada"""
        if linguagem in self.parsers:
            return self._analisar_complexidade_tree_sitter(conteudo, linguagem)
        else:
            return self._analisar_complexidade_regex(conteudo, linguagem)

    def _analisar_complexidade_tree_sitter(self, conteudo: str, linguagem: str) -> int:
        """Análise de complexidade usando Tree-sitter"""
        try:
            parser = self.parsers[linguagem]
            tree = parser.parse(bytes(conteudo, "utf8"))

            complexidade = 1  # Complexidade base

            def visitar_no(node):
                nonlocal complexidade

                # Nós que aumentam complexidade
                nos_complexidade = {
                    'if_statement', 'while_statement', 'for_statement',
                    'switch_statement', 'case_statement', 'catch_clause',
                    'conditional_expression', 'logical_and', 'logical_or'
                }

                if node.type in nos_complexidade:
                    complexidade += 1

                for child in node.children:
                    visitar_no(child)

            visitar_no(tree.root_node)
            return complexidade

        except Exception as e:
            montar_log(f"Erro na análise Tree-sitter: {e}", "WARNING")
            return self._analisar_complexidade_regex(conteudo, linguagem)

    def _analisar_complexidade_regex(self, conteudo: str, linguagem: str) -> int:
        """Análise de complexidade usando regex (fallback)"""
        import re

        # Padrões por linguagem
        padroes = {
            'c': [r'\bif\b', r'\belse\b', r'\bwhile\b', r'\bfor\b', r'\bswitch\b', r'\bcase\b'],
            'cpp': [r'\bif\b', r'\belse\b', r'\bwhile\b', r'\bfor\b', r'\bswitch\b', r'\bcase\b', r'\btry\b', r'\bcatch\b'],
            'python': [r'\bif\b', r'\belif\b', r'\belse\b', r'\bwhile\b', r'\bfor\b', r'\btry\b', r'\bexcept\b'],
            'javascript': [r'\bif\b', r'\belse\b', r'\bwhile\b', r'\bfor\b', r'\bswitch\b', r'\bcase\b', r'\btry\b', r'\bcatch\b'],
            'java': [r'\bif\b', r'\belse\b', r'\bwhile\b', r'\bfor\b', r'\bswitch\b', r'\bcase\b', r'\btry\b', r'\bcatch\b']
        }

        padroes_lang = padroes.get(linguagem, padroes['c'])

        complexidade = 1
        for padrao in padroes_lang:
            matches = re.findall(padrao, conteudo, re.IGNORECASE)
            complexidade += len(matches)

        return complexidade

    def extrair_funcoes(self, conteudo: str, linguagem: str) -> List[Dict[str, Any]]:
        """Extrai informações detalhadas sobre funções"""
        if linguagem in self.parsers:
            return self._extrair_funcoes_tree_sitter(conteudo, linguagem)
        else:
            return self._extrair_funcoes_regex(conteudo, linguagem)

    def _extrair_funcoes_tree_sitter(self, conteudo: str, linguagem: str) -> List[Dict[str, Any]]:
        """Extração de funções usando Tree-sitter"""
        funcoes = []

        try:
            parser = self.parsers[linguagem]
            tree = parser.parse(bytes(conteudo, "utf8"))
            linhas = conteudo.split('\n')

            def visitar_no(node):
                if node.type == 'function_definition':
                    try:
                        # Extrair nome da função
                        nome_node = node.child_by_field_name('name')
                        nome = nome_node.text.decode('utf8') if nome_node else "função_anônima"

                        # Extrair parâmetros
                        params_node = node.child_by_field_name('parameters')
                        parametros = []
                        if params_node:
                            for param in params_node.children:
                                if param.type == 'parameter':
                                    param_nome = param.child_by_field_name('name')
                                    if param_nome:
                                        parametros.append(param_nome.text.decode('utf8'))

                        # Extrair corpo da função
                        body_node = node.child_by_field_name('body')
                        linha_inicio = node.start_point[0] + 1
                        linha_fim = node.end_point[0] + 1

                        codigo_funcao = '\n'.join(linhas[linha_inicio-1:linha_fim])

                        # Calcular métricas
                        complexidade = self._calcular_complexidade_funcao(codigo_funcao, linguagem)
                        linhas_codigo = len([l for l in codigo_funcao.split('\n') if l.strip() and not l.strip().startswith('//')])

                        # Extrair documentação
                        documentacao = self._extrair_documentacao_funcao(linhas, linha_inicio - 1)

                        funcao = {
                            'nome': nome,
                            'parametros': parametros,
                            'linha_inicio': linha_inicio,
                            'linha_fim': linha_fim,
                            'linhas_codigo': linhas_codigo,
                            'complexidade': complexidade,
                            'documentacao': documentacao,
                            'codigo': codigo_funcao,
                            'tipo_retorno': self._detectar_tipo_retorno(codigo_funcao, linguagem),
                            'modificadores': self._extrair_modificadores(codigo_funcao, linguagem),
                            'chamadas_funcoes': self._extrair_chamadas_funcoes(codigo_funcao),
                            'variaveis_locais': self._extrair_variaveis_locais(codigo_funcao, linguagem)
                        }

                        funcoes.append(funcao)

                    except Exception as e:
                        montar_log(f"Erro ao extrair função: {e}", "WARNING")

                for child in node.children:
                    visitar_no(child)

            visitar_no(tree.root_node)

        except Exception as e:
            montar_log(f"Erro na extração Tree-sitter de funções: {e}", "WARNING")
            return self._extrair_funcoes_regex(conteudo, linguagem)

        return funcoes

    def _extrair_funcoes_regex(self, conteudo: str, linguagem: str) -> List[Dict[str, Any]]:
        """Extração de funções usando regex (fallback)"""
        import re

        funcoes = []
        linhas = conteudo.split('\n')

        # Padrões por linguagem
        padroes_funcao = {
            'c': r'^[a-zA-Z_][a-zA-Z0-9_\s\*]*\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*\{?',
            'cpp': r'^[a-zA-Z_][a-zA-Z0-9_\s\*:]*\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*\{?',
            'python': r'^def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*:',
            'javascript': r'^function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*\{?',
            'java': r'^[a-zA-Z_][a-zA-Z0-9_\s]*\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*\{?'
        }

        padrao = padroes_funcao.get(linguagem, padroes_funcao['c'])

        for i, linha in enumerate(linhas):
            match = re.match(padrao, linha.strip())
            # Garante que o match foi encontrado E que o grupo de captura (nome da função) não é nulo
            if match and match.group(1) and not linha.strip().startswith('//') and not linha.strip().startswith('/*'):
                nome_funcao = match.group(1)

                # Encontrar fim da função (aproximado)
                linha_fim = i + 1
                nivel_chaves = 0
                for j in range(i, len(linhas)):
                    nivel_chaves += linhas[j].count('{') - linhas[j].count('}')
                    if nivel_chaves == 0 and '{' in linhas[j]:
                        linha_fim = j + 1
                        break

                codigo_funcao = '\n'.join(linhas[i:linha_fim])
                documentacao = self._extrair_documentacao_funcao(linhas, i)

                funcao = {
                    'nome': nome_funcao,
                    'parametros': self._extrair_parametros_regex(linha, linguagem),
                    'linha_inicio': i + 1,
                    'linha_fim': linha_fim,
                    'linhas_codigo': len([l for l in codigo_funcao.split('\n') if l.strip()]),
                    'complexidade': self._calcular_complexidade_funcao(codigo_funcao, linguagem),
                    'documentacao': documentacao,
                    'codigo': codigo_funcao,
                    'tipo_retorno': self._detectar_tipo_retorno(linha, linguagem),
                    'modificadores': self._extrair_modificadores(linha, linguagem),
                    'chamadas_funcoes': self._extrair_chamadas_funcoes(codigo_funcao),
                    'variaveis_locais': []
                }

                funcoes.append(funcao)

        return funcoes

    def _calcular_complexidade_funcao(self, codigo: str, linguagem: str) -> int:
        """Calcula complexidade específica de uma função"""
        return self.analisar_complexidade(codigo, linguagem)

    def _extrair_documentacao_funcao(self, linhas: List[str], linha_funcao: int) -> str:
        """Extrai documentação de uma função"""
        documentacao = []

        # Procurar comentários acima da função
        for i in range(linha_funcao - 1, -1, -1):
            linha = linhas[i].strip()
            if linha.startswith('/**') or linha.startswith('/*') or linha.startswith('*') or linha.startswith('//') or linha.startswith('#'):
                documentacao.insert(0, linha)
            elif linha == '':
                continue
            else:
                break

        return '\n'.join(documentacao)

    def _detectar_tipo_retorno(self, codigo: str, linguagem: str) -> str:
        """Detecta tipo de retorno da função"""
        import re

        if linguagem in ['c', 'cpp', 'java']:
            # Procurar tipo antes do nome da função
            match = re.search(r'^([a-zA-Z_][a-zA-Z0-9_\*\s]*)\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\(', codigo.strip())
            if match:
                return match.group(1).strip()

        elif linguagem == 'python':
            # Procurar anotação de tipo
            match = re.search(r'->\s*([a-zA-Z_][a-zA-Z0-9_\[\],\s]*)\s*:', codigo)
            if match:
                return match.group(1).strip()

        return 'unknown'

    def _extrair_modificadores(self, codigo: str, linguagem: str) -> List[str]:
        """Extrai modificadores da função"""
        modificadores = []

        if linguagem in ['c', 'cpp']:
            if 'static' in codigo:
                modificadores.append('static')
            if 'inline' in codigo:
                modificadores.append('inline')
            if 'extern' in codigo:
                modificadores.append('extern')

        elif linguagem == 'java':
            if 'public' in codigo:
                modificadores.append('public')
            if 'private' in codigo:
                modificadores.append('private')
            if 'protected' in codigo:
                modificadores.append('protected')
            if 'static' in codigo:
                modificadores.append('static')
            if 'final' in codigo:
                modificadores.append('final')

        return modificadores

    def _extrair_chamadas_funcoes(self, codigo: str) -> List[str]:
        """Extrai chamadas de funções no código"""
        import re

        # Padrão para chamadas de função
        pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
        matches = re.findall(pattern, codigo)

        # Filtrar palavras-chave
        palavras_chave = {'if', 'while', 'for', 'switch', 'return', 'sizeof', 'typeof'}
        chamadas = [m for m in matches if m not in palavras_chave]

        return list(set(chamadas))  # Remover duplicatas

    def _extrair_variaveis_locais(self, codigo: str, linguagem: str) -> List[str]:
        """Extrai variáveis locais da função"""
        import re

        variaveis = []

        if linguagem in ['c', 'cpp']:
            # Padrão para declarações de variáveis
            pattern = r'\b(int|char|float|double|long|short|unsigned|signed|void|bool)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            matches = re.findall(pattern, codigo)
            variaveis.extend([m[1] for m in matches])

        elif linguagem == 'python':
            # Padrão para atribuições
            pattern = r'^[ \t]*([a-zA-Z_][a-zA-Z0-9_]*)\s*='
            matches = re.findall(pattern, codigo, re.MULTILINE)
            variaveis.extend(matches)

        return list(set(variaveis))

    def _extrair_parametros_regex(self, linha: str, linguagem: str) -> List[str]:
        """Extrai parâmetros usando regex"""
        import re

        # Extrair conteúdo entre parênteses
        match = re.search(r'\(([^)]*)\)', linha)
        if not match:
            return []

        params_str = match.group(1).strip()
        if not params_str:
            return []

        parametros = []

        if linguagem in ['c', 'cpp', 'java']:
            # Dividir por vírgula e extrair nomes
            for param in params_str.split(','):
                param = param.strip()
                if param:
                    # Pegar última palavra (nome do parâmetro)
                    palavras = param.split()
                    if palavras:
                        parametros.append(palavras[-1])

        elif linguagem == 'python':
            # Dividir por vírgula
            for param in params_str.split(','):
                param = param.strip()
                if param and '=' in param:
                    param = param.split('=')[0].strip()
                if param:
                    parametros.append(param)

        return parametros

    def detectar_vulnerabilidades(self, conteudo: str, linguagem: str) -> List[Dict[str, Any]]:
        """Detecta vulnerabilidades de segurança no código"""
        vulnerabilidades = []

        # Análise com ML se disponível
        if TRANSFORMERS_AVAILABLE and 'vulnerability_detector' in self.modelos_ml:
            vulnerabilidades.extend(self._detectar_vulnerabilidades_ml(conteudo))

        # Análise baseada em regras
        vulnerabilidades.extend(self._detectar_vulnerabilidades_regras(conteudo, linguagem))

        return vulnerabilidades

    def _detectar_vulnerabilidades_ml(self, conteudo: str) -> List[Dict[str, Any]]:
        """Detecta vulnerabilidades usando Machine Learning"""
        vulnerabilidades = []

        try:
            # Dividir código em chunks para análise
            chunks = [conteudo[i:i+512] for i in range(0, len(conteudo), 512)]

            # CÓDIGO NOVO E CORRETO
            for i, chunk in enumerate(chunks):
                # O pipeline da HuggingFace retorna uma lista contendo uma lista de dicionários
                # Exemplo: [[{'label': '...', 'score': ...}, {'label': '...', 'score': ...}]]
                resultado_pipeline = self.modelos_ml['vulnerability_detector'](chunk)

                # Verificamos se o resultado não está vazio e pegamos a primeira lista interna
                if resultado_pipeline and isinstance(resultado_pipeline, list) and len(resultado_pipeline) > 0:
                    predictions = resultado_pipeline[0]
                    for pred in predictions:
                        # Checamos se 'pred' é um dicionário e tem as chaves necessárias
                        if isinstance(pred, dict) and 'score' in pred and 'label' in pred:
                            if pred['score'] > 0.7 and 'vulnerability' in pred['label'].lower():
                                vulnerabilidades.append({
                                    'tipo': 'ml_detected',
                                    'categoria': pred['label'],
                                    'confianca': pred['score'],
                                    'localizacao': f'chunk_{i}',
                                    'descricao': f"Possível vulnerabilidade detectada por ML: {pred['label']}",
                                    'severidade': 'media' if pred['score'] > 0.8 else 'baixa'
                                })

        except Exception as e:
            montar_log(f"Erro na detecção ML de vulnerabilidades: {e}", "WARNING")

        return vulnerabilidades

    def _detectar_vulnerabilidades_regras(self, conteudo: str, linguagem: str) -> List[Dict[str, Any]]:
        """Detecta vulnerabilidades usando regras predefinidas"""
        import re

        vulnerabilidades = []
        linhas = conteudo.split('\n')

        # Regras por linguagem
        regras = {
            'c': [
                (r'\bstrcpy\s*\(', 'buffer_overflow', 'Uso de strcpy pode causar buffer overflow'),
                (r'\bsprintf\s*\(', 'buffer_overflow', 'Uso de sprintf pode causar buffer overflow'),
                (r'\bgets\s*\(', 'buffer_overflow', 'Uso de gets é inseguro'),
                (r'\bmalloc\s*\([^)]*\)\s*;?\s*$', 'memory_leak', 'malloc sem verificação de retorno'),
                (r'\bsystem\s*\(', 'command_injection', 'Uso de system() pode ser inseguro'),
            ],
            'cpp': [
                (r'\bstrcpy\s*\(', 'buffer_overflow', 'Uso de strcpy pode causar buffer overflow'),
                (r'\bnew\s+[^;]*;\s*$', 'memory_leak', 'new sem delete correspondente'),
                (r'\bsystem\s*\(', 'command_injection', 'Uso de system() pode ser inseguro'),
            ],
            'python': [
                (r'\beval\s*\(', 'code_injection', 'Uso de eval() é perigoso'),
                (r'\bexec\s*\(', 'code_injection', 'Uso de exec() é perigoso'),
                (r'\bos\.system\s*\(', 'command_injection', 'Uso de os.system() pode ser inseguro'),
                (r'\bsubprocess\.call\s*\([^)]*shell\s*=\s*True', 'command_injection', 'subprocess com shell=True é inseguro'),
            ],
            'javascript': [
                (r'\beval\s*\(', 'code_injection', 'Uso de eval() é perigoso'),
                (r'\bdocument\.write\s*\(', 'xss', 'document.write pode causar XSS'),
                (r'\binnerHTML\s*=', 'xss', 'innerHTML pode causar XSS'),
                (r'\bsetTimeout\s*\(\s*["\']', 'code_injection', 'setTimeout com string é perigoso'),
            ]
        }

        regras_lang = regras.get(linguagem, [])

        for i, linha in enumerate(linhas):
            for padrao, categoria, descricao in regras_lang:
                if re.search(padrao, linha):
                    vulnerabilidades.append({
                        'tipo': 'rule_based',
                        'categoria': categoria,
                        'linha': i + 1,
                        'codigo': linha.strip(),
                        'descricao': descricao,
                        'severidade': self._calcular_severidade_vulnerabilidade(categoria),
                        'recomendacao': self._obter_recomendacao_vulnerabilidade(categoria)
                    })

        return vulnerabilidades

    def _calcular_severidade_vulnerabilidade(self, categoria: str) -> str:
        """Calcula severidade da vulnerabilidade"""
        severidades = {
            'buffer_overflow': 'alta',
            'code_injection': 'critica',
            'command_injection': 'alta',
            'xss': 'media',
            'memory_leak': 'media',
            'sql_injection': 'critica'
        }

        return severidades.get(categoria, 'baixa')

    def _obter_recomendacao_vulnerabilidade(self, categoria: str) -> str:
        """Obtém recomendação para corrigir vulnerabilidade"""
        recomendacoes = {
            'buffer_overflow': 'Use strncpy, snprintf ou funções seguras equivalentes',
            'code_injection': 'Evite eval/exec, use parsing seguro',
            'command_injection': 'Use subprocess com lista de argumentos, não shell',
            'xss': 'Sanitize entrada do usuário, use textContent ao invés de innerHTML',
            'memory_leak': 'Verifique retorno de malloc, use free correspondente',
            'sql_injection': 'Use prepared statements ou ORM'
        }

        return recomendacoes.get(categoria, 'Revise o código para práticas seguras')


class ScannerAvancado:
    """Scanner de última geração para repositórios e arquivos"""

    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or min(32, (os.cpu_count() or 1) + 4)
        self.analisador_linguagem = AnalisadorLinguagem()

        # Estatísticas
        self.estatisticas = {
            'arquivos_escaneados': 0,
            'repositorios_escaneados': 0,
            'tempo_total_escaneamento': 0.0,
            'erros_encontrados': 0,
            'vulnerabilidades_detectadas': 0
        }

        # Cache para otimização
        self.cache_arquivos = {}
        self.cache_repositorios = {}

        montar_log(f"ScannerAvancado inicializado com {self.max_workers} workers", "INFO")

    async def escanear_repositorio_github(self, url_repo: str, branch: str = "main") -> RepositorioEscaneado:
        """Escaneia um repositório do GitHub automaticamente"""
        montar_log(f"Iniciando escaneamento automático do repositório: {url_repo}", "INFO")

        inicio = time.time()

        try:
            # 1. Clonar repositório
            diretorio_temp = await self._clonar_repositorio(url_repo, branch)

            # 2. Escanear repositório local
            resultado = await self.escanear_repositorio_local(diretorio_temp, url_repo)

            # 3. Análise específica do GitHub
            await self._analisar_metadados_github(resultado, url_repo)

            # 4. Limpeza
            shutil.rmtree(diretorio_temp, ignore_errors=True)

            tempo_total = time.time() - inicio
            self.estatisticas['tempo_total_escaneamento'] += tempo_total
            self.estatisticas['repositorios_escaneados'] += 1

            montar_log(f"Repositório escaneado em {tempo_total:.2f}s: {resultado.total_arquivos} arquivos", "SUCCESS")

            return resultado

        except Exception as e:
            montar_log(f"Erro ao escanear repositório {url_repo}: {e}", "ERROR")
            self.estatisticas['erros_encontrados'] += 1
            raise

    async def _clonar_repositorio(self, url: str, branch: str) -> str:
        """Clona repositório para diretório temporário"""
        diretorio_temp = tempfile.mkdtemp(prefix="scanner_repo_")

        try:
            # Comando git clone
            cmd = [
                'git', 'clone',
                '--depth', '1',  # Clone shallow para economizar tempo/espaço
                '--branch', branch,
                url,
                diretorio_temp
            ]

            processo = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await processo.communicate()

            if processo.returncode != 0:
                raise Exception(f"Erro ao clonar repositório: {stderr.decode()}")

            montar_log(f"Repositório clonado para: {diretorio_temp}", "INFO")
            return diretorio_temp

        except Exception as e:
            shutil.rmtree(diretorio_temp, ignore_errors=True)
            raise e

    async def escanear_repositorio_local(self, caminho: str, url_origem: str = "") -> RepositorioEscaneado:
        """Escaneia um repositório local completamente"""
        montar_log(f"Escaneando repositório local: {caminho}", "INFO")

        inicio = time.time()
        caminho_repo = Path(caminho)

        if not caminho_repo.exists():
            raise ValueError(f"Caminho não existe: {caminho}")

        # Inicializar resultado
        resultado = RepositorioEscaneado(
            url=url_origem or str(caminho_repo),
            nome=caminho_repo.name,
            descricao="",
            linguagem_principal="",
            linguagens_detectadas={},
            total_arquivos=0,
            total_linhas_codigo=0,
            estrutura_diretorios={},
            dependencias_projeto=[],
            frameworks_utilizados=[],
            padroes_arquiteturais=[],
            qualidade_geral=0.0,
            complexidade_geral=0.0,
            cobertura_documentacao=0.0,
            vulnerabilidades_criticas=0,
            licenca_projeto=None,
            contribuidores=[],
            commits_analisados=0,
            data_ultimo_commit=None,
            atividade_projeto="unknown",
            maturidade_projeto="unknown",
            tags_projeto=[],
            categoria_projeto="unknown",
            readme_analisado={},
            changelog_analisado={},
            issues_analisadas={},
            metricas_git={},
            arquivos_escaneados=[],
            relatorio_completo={}
        )

        try:
            # 1. Análise da estrutura de diretórios
            resultado.estrutura_diretorios = await self._analisar_estrutura_diretorios(caminho_repo)

            # 2. Encontrar e escanear arquivos
            arquivos_codigo = await self._encontrar_arquivos_codigo(caminho_repo)
            resultado.total_arquivos = len(arquivos_codigo)

            # 3. Escanear arquivos em paralelo
            arquivos_escaneados = await self._escanear_arquivos_paralelo(arquivos_codigo)
            resultado.arquivos_escaneados = arquivos_escaneados

            # 4. Análise agregada
            await self._analisar_metricas_agregadas(resultado)

            # 5. Análise de arquivos especiais
            await self._analisar_arquivos_especiais(resultado, caminho_repo)

            # 6. Análise Git
            await self._analisar_repositorio_git(resultado, caminho_repo)

            # 7. Detecção de frameworks e padrões
            await self._detectar_frameworks_padroes(resultado)

            # 8. Classificação e categorização
            await self._classificar_projeto(resultado)

            # 9. Gerar relatório completo
            resultado.relatorio_completo = await self._gerar_relatorio_completo(resultado)

            tempo_total = time.time() - inicio
            montar_log(f"Escaneamento completo em {tempo_total:.2f}s", "SUCCESS")

            return resultado

        except Exception as e:
            montar_log(f"Erro durante escaneamento: {e}", "ERROR")
            self.estatisticas['erros_encontrados'] += 1
            raise

    async def _analisar_estrutura_diretorios(self, caminho_repo: Path) -> Dict[str, Any]:
        """Analisa a estrutura de diretórios do projeto"""
        estrutura = {
            'diretorios_principais': [],
            'profundidade_maxima': 0,
            'total_diretorios': 0,
            'padroes_organizacao': []
        }

        try:
            for root, dirs, files in os.walk(caminho_repo):
                nivel = root.replace(str(caminho_repo), '').count(os.sep)
                estrutura['profundidade_maxima'] = max(estrutura['profundidade_maxima'], nivel)
                estrutura['total_diretorios'] += len(dirs)

                # Identificar diretórios principais (nível 1)
                if nivel == 1:
                    estrutura['diretorios_principais'].extend(dirs)

            # Detectar padrões de organização
            dirs_principais = set(estrutura['diretorios_principais'])

            if {'src', 'include'}.issubset(dirs_principais):
                estrutura['padroes_organizacao'].append('c_cpp_tradicional')

            if {'lib', 'bin', 'include'}.issubset(dirs_principais):
                estrutura['padroes_organizacao'].append('biblioteca_c')

            if {'app', 'components', 'pages'}.issubset(dirs_principais):
                estrutura['padroes_organizacao'].append('aplicacao_web')

            if {'models', 'views', 'controllers'}.issubset(dirs_principais):
                estrutura['padroes_organizacao'].append('mvc')

            if {'tests', 'test'}.intersection(dirs_principais):
                estrutura['padroes_organizacao'].append('com_testes')

            if {'docs', 'documentation'}.intersection(dirs_principais):
                estrutura['padroes_organizacao'].append('bem_documentado')

        except Exception as e:
            montar_log(f"Erro na análise de estrutura: {e}", "WARNING")

        return estrutura

    async def _encontrar_arquivos_codigo(self, caminho_repo: Path) -> List[Path]:
        """Encontra todos os arquivos de código no repositório"""
        extensoes_codigo = {
            '.c', '.h', '.cpp', '.hpp', '.cc', '.cxx',
            '.py', '.pyx', '.pyi',
            '.js', '.jsx', '.ts', '.tsx',
            '.java', '.kt', '.scala',
            '.go', '.rs', '.swift',
            '.php', '.rb', '.pl', '.sh',
            '.sql', '.html', '.css',
            '.xml', '.json', '.yaml', '.yml',
            '.toml', '.ini', '.cfg', '.conf'
        }

        arquivos = []

        # Diretórios a ignorar
        diretorios_ignorar = {
            '.git', '.svn', '.hg',
            'node_modules', '__pycache__', '.pytest_cache',
            'build', 'dist', 'target', 'bin', 'obj',
            '.vscode', '.idea', '.vs'
        }

        for root, dirs, files in os.walk(caminho_repo):
            # Filtrar diretórios
            dirs[:] = [d for d in dirs if d not in diretorios_ignorar]

            for arquivo in files:
                caminho_arquivo = Path(root) / arquivo

                # Verificar extensão
                if caminho_arquivo.suffix.lower() in extensoes_codigo:
                    # Verificar tamanho (ignorar arquivos muito grandes)
                    try:
                        if caminho_arquivo.stat().st_size < 10 * 1024 * 1024:  # 10MB
                            arquivos.append(caminho_arquivo)
                    except OSError:
                        continue

        montar_log(f"Encontrados {len(arquivos)} arquivos de código", "INFO")
        return arquivos

    async def _escanear_arquivos_paralelo(self, arquivos: List[Path]) -> List[ArquivoEscaneado]:
        """Escaneia arquivos em paralelo para máxima performance"""
        montar_log(f"Escaneando {len(arquivos)} arquivos em paralelo...", "INFO")

        # Dividir arquivos em lotes
        lote_tamanho = max(1, len(arquivos) // self.max_workers)
        lotes = [arquivos[i:i + lote_tamanho] for i in range(0, len(arquivos), lote_tamanho)]

        # Processar lotes em paralelo
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []

            for lote in lotes:
                future = executor.submit(self._escanear_lote_arquivos, lote)
                futures.append(future)

            # Coletar resultados
            arquivos_escaneados = []
            for future in futures:
                try:
                    resultado_lote = future.result(timeout=300)  # 5 minutos timeout
                    arquivos_escaneados.extend(resultado_lote)
                except Exception as e:
                    montar_log(f"Erro no processamento de lote: {e}", "ERROR")
                    self.estatisticas['erros_encontrados'] += 1

        self.estatisticas['arquivos_escaneados'] += len(arquivos_escaneados)
        montar_log(f"Escaneamento paralelo concluído: {len(arquivos_escaneados)} arquivos processados", "SUCCESS")

        return arquivos_escaneados

    def _escanear_lote_arquivos(self, lote: List[Path]) -> List[ArquivoEscaneado]:
        """Escaneia um lote de arquivos (executado em thread separada)"""
        resultados = []

        for arquivo in lote:
            try:
                resultado = self._escanear_arquivo_individual(arquivo)
                if resultado:
                    resultados.append(resultado)
            except Exception as e:
                montar_log(f"Erro ao escanear {arquivo}: {e}", "WARNING")

        return resultados

    def _escanear_arquivo_individual(self, arquivo: Path) -> Optional[ArquivoEscaneado]:
        """Escaneia um arquivo individual completamente"""
        try:
            # Verificar cache
            cache_key = f"{arquivo}_{arquivo.stat().st_mtime}"
            if cache_key in self.cache_arquivos:
                return self.cache_arquivos[cache_key]

            # Ler arquivo
            try:
                with open(arquivo, 'r', encoding='utf-8', errors='ignore') as f:
                    conteudo = f.read()
            except Exception:
                # Tentar outras codificações
                for encoding in ['latin-1', 'cp1252', 'iso-8859-1']:
                    try:
                        with open(arquivo, 'r', encoding=encoding) as f:
                            conteudo = f.read()
                        break
                    except Exception:
                        continue
                else:
                    return None

            # Informações básicas
            stat = arquivo.stat()
            hash_md5 = hashlib.md5(conteudo.encode()).hexdigest()
            hash_sha256 = hashlib.sha256(conteudo.encode()).hexdigest()

            # Detectar tipo MIME
            tipo_mime = mimetypes.guess_type(str(arquivo))[0] or 'text/plain'

            # Detectar linguagem
            linguagem = self.analisador_linguagem.detectar_linguagem(str(arquivo), conteudo)

            # Análise de linhas
            linhas = conteudo.split('\n')
            linhas_codigo = len([l for l in linhas if l.strip() and not l.strip().startswith(('#', '//', '/*', '*'))])
            linhas_comentario = len([l for l in linhas if l.strip().startswith(('#', '//', '/*', '*'))])
            linhas_branco = len([l for l in linhas if not l.strip()])

            # Análise de complexidade
            complexidade = self.analisador_linguagem.analisar_complexidade(conteudo, linguagem)

            # Extrair funções
            funcoes = self.analisador_linguagem.extrair_funcoes(conteudo, linguagem)

            # Detectar vulnerabilidades
            vulnerabilidades = self.analisador_linguagem.detectar_vulnerabilidades(conteudo, linguagem)

            # Extrair imports/includes
            imports = self._extrair_imports(conteudo, linguagem)

            # Extrair comentários
            comentarios = self._extrair_comentarios(conteudo, linguagem)

            # Detectar licença e autor
            licenca, autor = self._detectar_licenca_autor(conteudo)

            # Calcular qualidade do código
            qualidade = self._calcular_qualidade_codigo(conteudo, linguagem, vulnerabilidades, linhas_codigo, linhas_comentario)

            # Gerar tags automáticas
            tags = self._gerar_tags_automaticas(arquivo, conteudo, linguagem, funcoes)

            # Categorizar arquivo
            categoria, subcategoria = self._categorizar_arquivo(arquivo, conteudo, linguagem)

            # Detectar framework
            framework = self._detectar_framework_arquivo(conteudo, linguagem)

            # Detectar padrões de design
            padroes = self._detectar_padroes_design(conteudo, linguagem)

            # Métricas avançadas
            metricas = self._calcular_metricas_avancadas(conteudo, linguagem, funcoes)

            # Criar resultado
            resultado = ArquivoEscaneado(
                caminho=str(arquivo),
                nome=arquivo.name,
                extensao=arquivo.suffix,
                tamanho=stat.st_size,
                hash_md5=hash_md5,
                hash_sha256=hash_sha256,
                tipo_mime=tipo_mime,
                linguagem=linguagem,
                encoding='utf-8',  # Simplificado
                linhas_codigo=linhas_codigo,
                linhas_comentario=linhas_comentario,
                linhas_branco=linhas_branco,
                complexidade_ciclomatica=complexidade,
                qualidade_codigo=qualidade,
                vulnerabilidades=vulnerabilidades,
                dependencias=[],  # Será preenchido na análise agregada
                imports=imports,
                funcoes=funcoes,
                classes=[],  # Será implementado conforme necessário
                variaveis=[],  # Será implementado conforme necessário
                constantes=[],  # Será implementado conforme necessário
                comentarios_extraidos=comentarios,
                documentacao=self._extrair_documentacao_arquivo(conteudo),
                licenca=licenca,
                autor=autor,
                data_criacao=None,  # Seria obtido do Git
                data_modificacao=datetime.fromtimestamp(stat.st_mtime),
                tags_automaticas=tags,
                categoria=categoria,
                subcategoria=subcategoria,
                framework_detectado=framework,
                padroes_design=padroes,
                metricas_avancadas=metricas,
                embeddings=None,  # Será gerado posteriormente se necessário
                relacionamentos=[],  # Será preenchido na análise de relacionamentos
                metadados_extras={}
            )

            # Adicionar ao cache
            self.cache_arquivos[cache_key] = resultado

            return resultado

        except Exception as e:
            montar_log(f"Erro detalhado ao escanear {arquivo}: {e}", "ERROR")
            return None

    def _extrair_imports(self, conteudo: str, linguagem: str) -> List[str]:
        """Extrai imports/includes do arquivo"""
        import re

        imports = []

        if linguagem in ['c', 'cpp']:
            # #include statements
            matches = re.findall(r'#include\s*[<"](.*?)[>"]', conteudo)
            imports.extend(matches)

        elif linguagem == 'python':
            # import statements
            matches = re.findall(r'^\s*import\s+([a-zA-Z_][a-zA-Z0-9_\.]*)', conteudo, re.MULTILINE)
            imports.extend(matches)
            matches = re.findall(r'^\s*from\s+([a-zA-Z_][a-zA-Z0-9_\.]*)\s+import', conteudo, re.MULTILINE)
            imports.extend(matches)

        elif linguagem in ['javascript', 'typescript']:
            # import statements
            matches = re.findall(r'import.*?from\s+[\'"]([^\'"]*)[\'"]', conteudo)
            imports.extend(matches)
            matches = re.findall(r'require\s*\(\s*[\'"]([^\'"]*)[\'"]', conteudo)
            imports.extend(matches)

        elif linguagem == 'java':
            # import statements
            matches = re.findall(r'import\s+([a-zA-Z_][a-zA-Z0-9_\.]*)', conteudo)
            imports.extend(matches)

        return list(set(imports))  # Remover duplicatas

    def _extrair_comentarios(self, conteudo: str, linguagem: str) -> List[str]:
        """Extrai comentários do código"""
        import re

        comentarios = []

        if linguagem in ['c', 'cpp', 'java', 'javascript']:
            # Comentários de linha
            matches = re.findall(r'//\s*(.*)', conteudo)
            comentarios.extend(matches)

            # Comentários de bloco
            matches = re.findall(r'/\*(.*?)\*/', conteudo, re.DOTALL)
            comentarios.extend([c.strip() for c in matches])

        elif linguagem == 'python':
            # Comentários de linha
            matches = re.findall(r'#\s*(.*)', conteudo)
            comentarios.extend(matches)

            # Docstrings
            matches = re.findall(r'"""(.*?)"""', conteudo, re.DOTALL)
            comentarios.extend([c.strip() for c in matches])
            matches = re.findall(r"'''(.*?)'''", conteudo, re.DOTALL)
            comentarios.extend([c.strip() for c in matches])

        # Filtrar comentários vazios
        comentarios = [c.strip() for c in comentarios if c.strip()]

        return comentarios

    def _detectar_licenca_autor(self, conteudo: str) -> Tuple[Optional[str], Optional[str]]:
        """Detecta licença e autor do arquivo"""
        import re

        licenca = None
        autor = None

        # Procurar nas primeiras 50 linhas
        linhas_inicio = conteudo.split('\n')[:50]
        texto_inicio = '\n'.join(linhas_inicio).lower()

        # Detectar licenças comuns
        licencas = {
            'mit': r'mit\s+license',
            'gpl': r'gnu\s+general\s+public\s+license',
            'apache': r'apache\s+license',
            'bsd': r'bsd\s+license',
            'lgpl': r'gnu\s+lesser\s+general\s+public\s+license'
        }

        for nome_licenca, padrao in licencas.items():
            if re.search(padrao, texto_inicio):
                licenca = nome_licenca.upper()
                break

        # Detectar autor
        padroes_autor = [
            r'author[:\s]+([^\n\r]+)',
            r'copyright.*?(\d{4}).*?([^\n\r]+)',
            r'@author\s+([^\n\r]+)',
            r'written\s+by[:\s]+([^\n\r]+)'
        ]

        for padrao in padroes_autor:
            match = re.search(padrao, texto_inicio, re.IGNORECASE)
            if match:
                autor = match.group(-1).strip()
                break

        return licenca, autor

    def _calcular_qualidade_codigo(self, conteudo: str, linguagem: str, vulnerabilidades: List[Dict], linhas_codigo: int, linhas_comentario: int) -> float:
        """Calcula score de qualidade do código"""
        score = 100.0

        # Penalizar por vulnerabilidades
        for vuln in vulnerabilidades:
            if vuln.get('severidade') == 'critica':
                score -= 20
            elif vuln.get('severidade') == 'alta':
                score -= 10
            elif vuln.get('severidade') == 'media':
                score -= 5
            else:
                score -= 2

        # Bonificar por documentação
        if linhas_codigo > 0:
            ratio_comentarios = linhas_comentario / linhas_codigo
            if ratio_comentarios > 0.3:
                score += 10
            elif ratio_comentarios > 0.1:
                score += 5

        # Penalizar por linhas muito longas
        linhas = conteudo.split('\n')
        linhas_longas = len([l for l in linhas if len(l) > 120])
        if linhas_longas > linhas_codigo * 0.1:
            score -= 5

        # Bonificar por estrutura organizada
        if linguagem in ['c', 'cpp'] and '#include' in conteudo:
            score += 2

        if linguagem == 'python' and ('def ' in conteudo or 'class ' in conteudo):
            score += 2

        return max(0.0, min(100.0, score))

    def _gerar_tags_automaticas(self, arquivo: Path, conteudo: str, linguagem: str, funcoes: List[Dict]) -> List[str]:
        """Gera tags automáticas para o arquivo"""
        tags = [linguagem]

        # Tags baseadas no nome do arquivo
        nome_lower = arquivo.name.lower()

        if 'test' in nome_lower:
            tags.append('test')
        if 'main' in nome_lower:
            tags.append('main')
        if 'config' in nome_lower:
            tags.append('config')
        if 'util' in nome_lower or 'helper' in nome_lower:
            tags.append('utility')

        # Tags baseadas no conteúdo
        conteudo_lower = conteudo.lower()

        if 'malloc' in conteudo_lower or 'free' in conteudo_lower:
            tags.append('memory_management')

        if 'thread' in conteudo_lower or 'mutex' in conteudo_lower:
            tags.append('concurrency')

        if 'socket' in conteudo_lower or 'network' in conteudo_lower:
            tags.append('networking')

        if 'file' in conteudo_lower or 'fopen' in conteudo_lower:
            tags.append('file_io')

        if 'crypto' in conteudo_lower or 'encrypt' in conteudo_lower:
            tags.append('cryptography')

        # Tags baseadas nas funções
        if len(funcoes) > 10:
            tags.append('complex')
        elif len(funcoes) > 5:
            tags.append('moderate')
        else:
            tags.append('simple')

        return list(set(tags))

    def _categorizar_arquivo(self, arquivo: Path, conteudo: str, linguagem: str) -> Tuple[str, str]:
        """Categoriza o arquivo"""
        caminho_str = str(arquivo).lower()

        # Categoria principal
        if '/test' in caminho_str or 'test_' in arquivo.name.lower():
            return 'test', 'unit_test'

        if '/doc' in caminho_str or 'readme' in arquivo.name.lower():
            return 'documentation', 'readme'

        if '/config' in caminho_str or arquivo.suffix in ['.ini', '.cfg', '.conf']:
            return 'configuration', 'config_file'

        if '/script' in caminho_str or arquivo.suffix in ['.sh', '.bat']:
            return 'script', 'automation'

        if linguagem in ['c', 'cpp']:
            if arquivo.suffix in ['.h', '.hpp']:
                return 'source_code', 'header'
            else:
                return 'source_code', 'implementation'

        if linguagem == 'python':
            if 'main' in arquivo.name.lower():
                return 'source_code', 'main_module'
            else:
                return 'source_code', 'module'

        return 'source_code', 'general'

    def _detectar_framework_arquivo(self, conteudo: str, linguagem: str) -> Optional[str]:
        """Detecta framework usado no arquivo"""
        conteudo_lower = conteudo.lower()

        frameworks = {
            'react': ['import react', 'from react', 'usestate', 'useeffect'],
            'angular': ['@angular', '@component', '@injectable'],
            'vue': ['vue.js', 'new vue', 'vue.component'],
            'flask': ['from flask', 'flask import', 'app = flask'],
            'django': ['from django', 'django.', 'models.model'],
            'express': ['express()', 'app.get', 'app.post'],
            'spring': ['@springboot', '@controller', '@service'],
            'qt': ['#include <qt', 'qapplication', 'qwidget'],
            'gtk': ['#include <gtk', 'gtk_init', 'gtk_widget']
        }

        for framework, padroes in frameworks.items():
            if any(padrao in conteudo_lower for padrao in padroes):
                return framework

        return None

    def _detectar_padroes_design(self, conteudo: str, linguagem: str) -> List[str]:
        """Detecta padrões de design no código"""
        padroes = []
        conteudo_lower = conteudo.lower()

        # Singleton
        if 'singleton' in conteudo_lower or ('static' in conteudo_lower and 'instance' in conteudo_lower):
            padroes.append('singleton')

        # Factory
        if 'factory' in conteudo_lower or 'create' in conteudo_lower:
            padroes.append('factory')

        # Observer
        if 'observer' in conteudo_lower or ('notify' in conteudo_lower and 'update' in conteudo_lower):
            padroes.append('observer')

        # Strategy
        if 'strategy' in conteudo_lower or 'algorithm' in conteudo_lower:
            padroes.append('strategy')

        # MVC
        if any(palavra in conteudo_lower for palavra in ['model', 'view', 'controller']):
            padroes.append('mvc')

        return padroes

    def _calcular_metricas_avancadas(self, conteudo: str, linguagem: str, funcoes: List[Dict]) -> Dict[str, Any]:
        """Calcula métricas avançadas do arquivo"""
        linhas = conteudo.split('\n')

        metricas = {
            'total_linhas': len(linhas),
            'densidade_comentarios': 0.0,
            'complexidade_media_funcoes': 0.0,
            'funcoes_grandes': 0,
            'funcoes_pequenas': 0,
            'duplicacao_codigo': 0.0,
            'coesao': 0.0,
            'acoplamento': 0.0
        }

        # Densidade de comentários
        linhas_comentario = len([l for l in linhas if l.strip().startswith(('#', '//', '/*'))])
        if len(linhas) > 0:
            metricas['densidade_comentarios'] = linhas_comentario / len(linhas)

        # Métricas de funções
        if funcoes:
            complexidades = [f.get('complexidade', 1) for f in funcoes]
            metricas['complexidade_media_funcoes'] = sum(complexidades) / len(complexidades)

            # Funções grandes (>50 linhas) e pequenas (<10 linhas)
            for funcao in funcoes:
                linhas_funcao = funcao.get('linhas_codigo', 0)
                if linhas_funcao > 50:
                    metricas['funcoes_grandes'] += 1
                elif linhas_funcao < 10:
                    metricas['funcoes_pequenas'] += 1

        # Estimativa de duplicação (simplificada)
        linhas_unicas = set(l.strip() for l in linhas if l.strip())
        if len(linhas) > 0:
            metricas['duplicacao_codigo'] = 1.0 - (len(linhas_unicas) / len(linhas))

        return metricas

    def _extrair_documentacao_arquivo(self, conteudo: str) -> str:
        """Extrai documentação principal do arquivo"""
        linhas = conteudo.split('\n')
        documentacao = []

        # Procurar bloco de comentário no início
        em_comentario = False
        for linha in linhas[:20]:  # Primeiras 20 linhas
            linha_strip = linha.strip()

            if linha_strip.startswith('/*'):
                em_comentario = True
                documentacao.append(linha_strip)
            elif em_comentario and '*/' in linha_strip:
                documentacao.append(linha_strip)
                break
            elif em_comentario:
                documentacao.append(linha_strip)
            elif linha_strip.startswith('//') or linha_strip.startswith('#'):
                documentacao.append(linha_strip)
            elif linha_strip == '':
                continue
            else:
                break

        return '\n'.join(documentacao)

    async def _analisar_metricas_agregadas(self, resultado: RepositorioEscaneado):
        """Analisa métricas agregadas do repositório"""
        arquivos = resultado.arquivos_escaneados

        if not arquivos:
            return

        # Contagem de linguagens
        for arquivo in arquivos:
            lang = arquivo.linguagem
            resultado.linguagens_detectadas[lang] = resultado.linguagens_detectadas.get(lang, 0) + 1

        # Linguagem principal
        if resultado.linguagens_detectadas:
            resultado.linguagem_principal = max(resultado.linguagens_detectadas.items(), key=lambda x: x[1])[0]

        # Total de linhas de código
        resultado.total_linhas_codigo = sum(a.linhas_codigo for a in arquivos)

        # Qualidade geral
        qualidades = [a.qualidade_codigo for a in arquivos if a.qualidade_codigo > 0]
        if qualidades:
            resultado.qualidade_geral = sum(qualidades) / len(qualidades)

        # Complexidade geral
        complexidades = [a.complexidade_ciclomatica for a in arquivos if a.complexidade_ciclomatica > 0]
        if complexidades:
            resultado.complexidade_geral = sum(complexidades) / len(complexidades)

        # Cobertura de documentação
        arquivos_com_doc = len([a for a in arquivos if a.documentacao])
        if arquivos:
            resultado.cobertura_documentacao = arquivos_com_doc / len(arquivos)

        # Vulnerabilidades críticas
        resultado.vulnerabilidades_criticas = sum(
            len([v for v in a.vulnerabilidades if v.get('severidade') == 'critica'])
            for a in arquivos
        )

        # Atualizar estatísticas globais
        self.estatisticas['vulnerabilidades_detectadas'] += sum(len(a.vulnerabilidades) for a in arquivos)

    async def _analisar_arquivos_especiais(self, resultado: RepositorioEscaneado, caminho_repo: Path):
        """Analisa arquivos especiais do projeto"""
        # README
        readme_files = list(caminho_repo.glob('README*')) + list(caminho_repo.glob('readme*'))
        if readme_files:
            resultado.readme_analisado = await self._analisar_readme(readme_files[0])

        # LICENSE
        license_files = list(caminho_repo.glob('LICENSE*')) + list(caminho_repo.glob('license*'))
        if license_files:
            resultado.licenca_projeto = await self._analisar_licenca(license_files[0])

        # CHANGELOG
        changelog_files = list(caminho_repo.glob('CHANGELOG*')) + list(caminho_repo.glob('changelog*'))
        if changelog_files:
            resultado.changelog_analisado = await self._analisar_changelog(changelog_files[0])

    async def _analisar_readme(self, arquivo_readme: Path) -> Dict[str, Any]:
        """Analisa arquivo README"""
        try:
            with open(arquivo_readme, 'r', encoding='utf-8', errors='ignore') as f:
                conteudo = f.read()

            return {
                'tamanho': len(conteudo),
                'secoes_detectadas': self._detectar_secoes_readme(conteudo),
                'tem_instalacao': 'install' in conteudo.lower(),
                'tem_exemplos': 'example' in conteudo.lower(),
                'tem_contribuicao': 'contribut' in conteudo.lower(),
                'badges_detectados': len(re.findall(r'!\[.*?\]\(.*?\)', conteudo))
            }
        except Exception:
            return {}

    def _detectar_secoes_readme(self, conteudo: str) -> List[str]:
        """Detecta seções no README"""
        import re

        secoes = []

        # Procurar por headers markdown
        headers = re.findall(r'^#+\s*(.+)', conteudo, re.MULTILINE)
        secoes.extend([h.strip().lower() for h in headers])

        return list(set(secoes))

    async def _analisar_licenca(self, arquivo_licenca: Path) -> Optional[str]:
        """Analisa arquivo de licença"""
        try:
            with open(arquivo_licenca, 'r', encoding='utf-8', errors='ignore') as f:
                conteudo = f.read().lower()

            if 'mit license' in conteudo:
                return 'MIT'
            elif 'apache license' in conteudo:
                return 'Apache'
            elif 'gnu general public license' in conteudo:
                return 'GPL'
            elif 'bsd license' in conteudo:
                return 'BSD'
            else:
                return 'Custom'
        except Exception:
            return None

    async def _analisar_changelog(self, arquivo_changelog: Path) -> Dict[str, Any]:
        """Analisa arquivo CHANGELOG"""
        try:
            with open(arquivo_changelog, 'r', encoding='utf-8', errors='ignore') as f:
                conteudo = f.read()

            return {
                'tamanho': len(conteudo),
                'versoes_detectadas': len(re.findall(r'##?\s*\[?v?\d+\.\d+', conteudo, re.IGNORECASE)),
                'ultima_atualizacao': 'recent' if '2024' in conteudo or '2023' in conteudo else 'old'
            }
        except Exception:
            return {}

    async def _analisar_repositorio_git(self, resultado: RepositorioEscaneado, caminho_repo: Path):
        """Analisa informações do repositório Git"""
        try:
            # Verificar se é repositório Git
            if not (caminho_repo / '.git').exists():
                return

            # Obter informações básicas
            cmd_log = ['git', 'log', '--oneline', '-n', '100']
            processo = await asyncio.create_subprocess_exec(
                *cmd_log,
                cwd=caminho_repo,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await processo.communicate()

            if processo.returncode == 0:
                commits = stdout.decode().strip().split('\n')
                resultado.commits_analisados = len([c for c in commits if c.strip()])

            # Obter data do último commit
            cmd_date = ['git', 'log', '-1', '--format=%ci']
            processo = await asyncio.create_subprocess_exec(
                *cmd_date,
                cwd=caminho_repo,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await processo.communicate()

            if processo.returncode == 0:
                date_str = stdout.decode().strip()
                try:
                    resultado.data_ultimo_commit = datetime.fromisoformat(date_str.replace(' ', 'T').split('+')[0])
                except Exception:
                    pass

            # Determinar atividade do projeto
            if resultado.data_ultimo_commit:
                dias_desde_ultimo = (datetime.now() - resultado.data_ultimo_commit).days
                if dias_desde_ultimo < 30:
                    resultado.atividade_projeto = 'ativo'
                elif dias_desde_ultimo < 180:
                    resultado.atividade_projeto = 'moderado'
                else:
                    resultado.atividade_projeto = 'inativo'

        except Exception as e:
            montar_log(f"Erro na análise Git: {e}", "WARNING")

    async def _detectar_frameworks_padroes(self, resultado: RepositorioEscaneado):
        """Detecta frameworks e padrões arquiteturais"""
        frameworks = set()
        padroes = set()

        for arquivo in resultado.arquivos_escaneados:
            if arquivo.framework_detectado:
                frameworks.add(arquivo.framework_detectado)

            padroes.update(arquivo.padroes_design)

        resultado.frameworks_utilizados = list(frameworks)
        resultado.padroes_arquiteturais = list(padroes)

        # Detectar padrões baseados na estrutura
        dirs_principais = set(resultado.estrutura_diretorios.get('diretorios_principais', []))

        if {'models', 'views', 'controllers'}.issubset(dirs_principais):
            resultado.padroes_arquiteturais.append('mvc')

        if {'src', 'test', 'docs'}.issubset(dirs_principais):
            resultado.padroes_arquiteturais.append('bem_estruturado')

    async def _classificar_projeto(self, resultado: RepositorioEscaneado):
        """Classifica o projeto"""
        # Determinar maturidade
        fatores_maturidade = 0

        if resultado.readme_analisado:
            fatores_maturidade += 1
        if resultado.licenca_projeto:
            fatores_maturidade += 1
        if resultado.cobertura_documentacao > 0.3:
            fatores_maturidade += 1
        if resultado.commits_analisados > 50:
            fatores_maturidade += 1
        if resultado.vulnerabilidades_criticas == 0:
            fatores_maturidade += 1

        if fatores_maturidade >= 4:
            resultado.maturidade_projeto = 'maduro'
        elif fatores_maturidade >= 3:
            resultado.maturidade_projeto = 'estavel'
        elif fatores_maturidade >= 2:
            resultado.maturidade_projeto = 'beta'
        else:
            resultado.maturidade_projeto = 'experimental'

        # Determinar categoria
        if resultado.linguagem_principal in ['c', 'cpp']:
            if any('kernel' in tag for tag in resultado.tags_projeto):
                resultado.categoria_projeto = 'sistema_operacional'
            elif any('driver' in tag for tag in resultado.tags_projeto):
                resultado.categoria_projeto = 'driver'
            else:
                resultado.categoria_projeto = 'sistema'
        elif resultado.linguagem_principal == 'python':
            resultado.categoria_projeto = 'aplicacao'
        elif resultado.linguagem_principal in ['javascript', 'typescript']:
            resultado.categoria_projeto = 'web'
        else:
            resultado.categoria_projeto = 'geral'

        # Gerar tags do projeto
        tags = [resultado.linguagem_principal, resultado.categoria_projeto, resultado.maturidade_projeto]
        tags.extend(resultado.frameworks_utilizados)
        tags.extend(resultado.padroes_arquiteturais)

        resultado.tags_projeto = list(set(tags))

    async def _gerar_relatorio_completo(self, resultado: RepositorioEscaneado) -> Dict[str, Any]:
        """Gera relatório completo do escaneamento"""
        return {
            'resumo_executivo': {
                'total_arquivos': resultado.total_arquivos,
                'linguagem_principal': resultado.linguagem_principal,
                'qualidade_geral': resultado.qualidade_geral,
                'maturidade': resultado.maturidade_projeto,
                'vulnerabilidades_criticas': resultado.vulnerabilidades_criticas
            },
            'metricas_detalhadas': {
                'linhas_codigo_total': resultado.total_linhas_codigo,
                'complexidade_media': resultado.complexidade_geral,
                'cobertura_documentacao': resultado.cobertura_documentacao,
                'distribuicao_linguagens': resultado.linguagens_detectadas
            },
            'analise_qualidade': {
                'arquivos_alta_qualidade': len([a for a in resultado.arquivos_escaneados if a.qualidade_codigo > 80]),
                'arquivos_baixa_qualidade': len([a for a in resultado.arquivos_escaneados if a.qualidade_codigo < 50]),
                'total_vulnerabilidades': sum(len(a.vulnerabilidades) for a in resultado.arquivos_escaneados)
            },
            'recomendacoes': self._gerar_recomendacoes(resultado),
            'timestamp_escaneamento': datetime.now().isoformat()
        }

    def _gerar_recomendacoes(self, resultado: RepositorioEscaneado) -> List[str]:
        """Gera recomendações baseadas na análise"""
        recomendacoes = []

        if resultado.vulnerabilidades_criticas > 0:
            recomendacoes.append(f"Corrigir {resultado.vulnerabilidades_criticas} vulnerabilidades críticas")

        if resultado.cobertura_documentacao < 0.3:
            recomendacoes.append("Melhorar documentação do código")

        if resultado.qualidade_geral < 70:
            recomendacoes.append("Refatorar código para melhorar qualidade")

        if not resultado.readme_analisado:
            recomendacoes.append("Adicionar arquivo README")

        if not resultado.licenca_projeto:
            recomendacoes.append("Adicionar licença ao projeto")

        if resultado.atividade_projeto == 'inativo':
            recomendacoes.append("Projeto parece inativo - considerar manutenção")

        return recomendacoes

    async def _analisar_metadados_github(self, resultado: RepositorioEscaneado, url_repo: str):
        """Analisa metadados específicos do GitHub"""
        try:
            # Extrair informações da URL
            if 'github.com' in url_repo:
                partes = url_repo.split('/')
                if len(partes) >= 2:
                    owner = partes[-2]
                    repo = partes[-1].replace('.git', '')

                    # Aqui poderia fazer chamadas à API do GitHub
                    # Por simplicidade, apenas extrair da URL
                    resultado.metadados_extras['github_owner'] = owner
                    resultado.metadados_extras['github_repo'] = repo

        except Exception as e:
            montar_log(f"Erro na análise de metadados GitHub: {e}", "WARNING")

    def obter_estatisticas(self) -> Dict[str, Any]:
        """Obtém estatísticas do scanner"""
        return {
            'estatisticas_gerais': self.estatisticas,
            'cache_info': {
                'arquivos_em_cache': len(self.cache_arquivos),
                'repositorios_em_cache': len(self.cache_repositorios)
            },
            'configuracao': {
                'max_workers': self.max_workers,
                'componentes_disponiveis': {
                    'tree_sitter': TREE_SITTER_AVAILABLE,
                    'transformers': TRANSFORMERS_AVAILABLE,
                    'spacy': SPACY_AVAILABLE,
                    'pygments': PYGMENTS_AVAILABLE,
                    'opencv': OPENCV_AVAILABLE,
                    'ocr': OCR_AVAILABLE
                }
            }
        }

    def limpar_cache(self):
        """Limpa cache do scanner"""
        self.cache_arquivos.clear()
        self.cache_repositorios.clear()
        montar_log("Cache do scanner limpo", "INFO")