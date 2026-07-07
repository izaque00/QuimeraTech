"""
Agente Fiscal de Código Ultra-Especializado
Sistema automático de detecção e correção de problemas de código Python

Desenvolvido para o Projeto Quimera
Especialista em:
- Correção automática de sintaxe
- Formatação de código (black, autopep8, yapf)
- Organização de imports (isort)
- Detecção e correção de problemas de indentação
- Aplicação de padrões PEP8
- Detecção de code smells
- Análise de complexidade
- Geração de relatórios detalhados
"""

import ast
import os
import re
import sys
import json
import time
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict

# Imports do Quimera
from quimera.logs.parser import montar_log
from quimera.agentes.agente_base import AgenteBase

# Verificar disponibilidade de ferramentas
FORMATTERS_AVAILABLE = {}

def check_formatter_availability():
    """Verifica quais formatadores estão disponíveis"""
    formatters = {
        'black': 'black',
        'autopep8': 'autopep8',
        'yapf': 'yapf',
        'isort': 'isort',
        'flake8': 'flake8',
        'pylint': 'pylint',
        'mypy': 'mypy'
    }

    for name, cmd in formatters.items():
        try:
            result = subprocess.run([cmd, '--version'],
                                  capture_output=True, text=True, timeout=10)
            FORMATTERS_AVAILABLE[name] = result.returncode == 0
        except Exception:
            FORMATTERS_AVAILABLE[name] = False

    return FORMATTERS_AVAILABLE

# Verificar ferramentas na inicialização
check_formatter_availability()


@dataclass
class ProblemaDetectado:
    """Representa um problema detectado no código"""
    arquivo: str
    linha: int
    coluna: int
    tipo: str  # 'syntax', 'style', 'import', 'indentation', 'complexity'
    severidade: str  # 'critical', 'error', 'warning', 'info'
    descricao: str
    codigo_problema: str
    sugestao_correcao: str
    corrigivel_automaticamente: bool
    regra_violada: str = ""
    contexto: str = ""


@dataclass
class RelatorioFiscalizacao:
    """Relatório completo da fiscalização"""
    timestamp: datetime
    arquivos_analisados: int
    problemas_encontrados: List[ProblemaDetectado]
    problemas_corrigidos: List[ProblemaDetectado]
    estatisticas: Dict[str, Any]
    tempo_execucao: float
    ferramentas_utilizadas: List[str]
    configuracao_utilizada: Dict[str, Any]


class DetectorProblemas:
    """Especialista em detectar todos os tipos de problemas de código"""

    def __init__(self):
        self.problemas_conhecidos = self._carregar_padroes_problemas()

    def _carregar_padroes_problemas(self) -> Dict[str, Any]:
        """Carrega padrões conhecidos de problemas"""
        return {
            'indentacao_inconsistente': [
                r'^\s*\t\s*\S',  # Tab seguido de espaços
                r'^ {1,3}\S',    # Indentação com 1-3 espaços
                r'^ {5,7}\S',    # Indentação com 5-7 espaços
            ],
            'imports_desordenados': [
                r'^from\s+\S+\s+import.*\n^import',  # from depois de import
            ],
            'linhas_muito_longas': {
                'limite': 88,  # Padrão black
                'limite_estrito': 79  # PEP8
            },
            'espacamentos_incorretos': [
                r'\w\s{2,}\=',      # Múltiplos espaços antes de =
                r'\=\s{2,}\w',      # Múltiplos espaços depois de =
                r',\S',             # Vírgula sem espaço
                r'\(\s+\w',        # Espaço depois de (
                r'\w\s+\)',        # Espaço antes de )
            ],
            'strings_problematicas': [
                r'""".*""".*"""',   # Múltiplas docstrings
                r"'.*\".*'",        # Mistura de aspas
            ]
        }

    def detectar_problemas_sintaxe(self, arquivo: Path) -> List[ProblemaDetectado]:
        """Detecta problemas de sintaxe usando AST"""
        problemas = []

        try:
            with open(arquivo, 'r', encoding='utf-8') as f:
                conteudo = f.read()

            try:
                ast.parse(conteudo)
            except SyntaxError as e:
                problema = ProblemaDetectado(
                    arquivo=str(arquivo),
                    linha=e.lineno or 0,
                    coluna=e.offset or 0,
                    tipo='syntax',
                    severidade='critical',
                    descricao=f"Erro de sintaxe: {e.msg}",
                    codigo_problema=e.text or "",
                    sugestao_correcao=self._sugerir_correcao_sintaxe(e),
                    corrigivel_automaticamente=self._pode_corrigir_sintaxe(e),
                    regra_violada='SyntaxError',
                    contexto=self._extrair_contexto(conteudo, e.lineno or 0)
                )
                problemas.append(problema)

        except Exception as e:
            montar_log(f"Erro ao analisar sintaxe de {arquivo}: {e}", "ERROR")

        return problemas

    def detectar_problemas_indentacao(self, arquivo: Path) -> List[ProblemaDetectado]:
        """Detecta problemas de indentação"""
        problemas = []

        try:
            with open(arquivo, 'r', encoding='utf-8') as f:
                linhas = f.readlines()

            for i, linha in enumerate(linhas, 1):
                # Detectar mistura de tabs e espaços
                if '\t' in linha and ' ' in linha.lstrip('\t'):
                    problemas.append(ProblemaDetectado(
                        arquivo=str(arquivo),
                        linha=i,
                        coluna=0,
                        tipo='indentation',
                        severidade='error',
                        descricao="Mistura de tabs e espaços na indentação",
                        codigo_problema=linha.rstrip(),
                        sugestao_correcao="Usar apenas espaços (4 por nível)",
                        corrigivel_automaticamente=True,
                        regra_violada='E101',
                        contexto=self._extrair_contexto_linha(linhas, i)
                    ))

                # Detectar indentação inconsistente
                espacos_inicio = len(linha) - len(linha.lstrip(' '))
                if espacos_inicio > 0 and espacos_inicio % 4 != 0:
                    problemas.append(ProblemaDetectado(
                        arquivo=str(arquivo),
                        linha=i,
                        coluna=0,
                        tipo='indentation',
                        severidade='warning',
                        descricao=f"Indentação inconsistente: {espacos_inicio} espaços",
                        codigo_problema=linha.rstrip(),
                        sugestao_correcao="Usar múltiplos de 4 espaços",
                        corrigivel_automaticamente=True,
                        regra_violada='E111',
                        contexto=self._extrair_contexto_linha(linhas, i)
                    ))

        except Exception as e:
            montar_log(f"Erro ao analisar indentação de {arquivo}: {e}", "ERROR")

        return problemas

    def detectar_problemas_estilo(self, arquivo: Path) -> List[ProblemaDetectado]:
        """Detecta problemas de estilo PEP8"""
        problemas = []

        try:
            with open(arquivo, 'r', encoding='utf-8') as f:
                linhas = f.readlines()

            for i, linha in enumerate(linhas, 1):
                linha_limpa = linha.rstrip()

                # Linhas muito longas
                if len(linha_limpa) > 88:
                    problemas.append(ProblemaDetectado(
                        arquivo=str(arquivo),
                        linha=i,
                        coluna=88,
                        tipo='style',
                        severidade='warning',
                        descricao=f"Linha muito longa ({len(linha_limpa)} caracteres)",
                        codigo_problema=linha_limpa,
                        sugestao_correcao="Quebrar linha em múltiplas linhas",
                        corrigivel_automaticamente=True,
                        regra_violada='E501',
                        contexto=self._extrair_contexto_linha(linhas, i)
                    ))

                # Espaços em branco no final
                if linha.endswith(' \n') or linha.endswith('\t\n'):
                    problemas.append(ProblemaDetectado(
                        arquivo=str(arquivo),
                        linha=i,
                        coluna=len(linha_limpa),
                        tipo='style',
                        severidade='info',
                        descricao="Espaços em branco no final da linha",
                        codigo_problema=linha.rstrip('\n'),
                        sugestao_correcao="Remover espaços em branco no final",
                        corrigivel_automaticamente=True,
                        regra_violada='W291',
                        contexto=self._extrair_contexto_linha(linhas, i)
                    ))

                # Múltiplas linhas em branco
                if i > 1 and linha.strip() == '' and linhas[i-2].strip() == '':
                    problemas.append(ProblemaDetectado(
                        arquivo=str(arquivo),
                        linha=i,
                        coluna=0,
                        tipo='style',
                        severidade='info',
                        descricao="Múltiplas linhas em branco consecutivas",
                        codigo_problema="",
                        sugestao_correcao="Usar apenas uma linha em branco",
                        corrigivel_automaticamente=True,
                        regra_violada='E303',
                        contexto=self._extrair_contexto_linha(linhas, i)
                    ))

        except Exception as e:
            montar_log(f"Erro ao analisar estilo de {arquivo}: {e}", "ERROR")

        return problemas

    def detectar_problemas_imports(self, arquivo: Path) -> List[ProblemaDetectado]:
        """Detecta problemas com imports"""
        problemas = []

        try:
            with open(arquivo, 'r', encoding='utf-8') as f:
                conteudo = f.read()
                linhas = conteudo.split('\n')

            imports_stdlib = []
            imports_terceiros = []
            imports_locais = []

            for i, linha in enumerate(linhas, 1):
                linha_limpa = linha.strip()

                if linha_limpa.startswith('import ') or linha_limpa.startswith('from '):
                    # Categorizar import
                    if self._eh_import_stdlib(linha_limpa):
                        imports_stdlib.append((i, linha_limpa))
                    elif self._eh_import_local(linha_limpa):
                        imports_locais.append((i, linha_limpa))
                    else:
                        imports_terceiros.append((i, linha_limpa))

                    # Detectar imports não utilizados
                    modulo = self._extrair_nome_modulo(linha_limpa)
                    if modulo and not self._modulo_utilizado(modulo, conteudo):
                        problemas.append(ProblemaDetectado(
                            arquivo=str(arquivo),
                            linha=i,
                            coluna=0,
                            tipo='import',
                            severidade='warning',
                            descricao=f"Import não utilizado: {modulo}",
                            codigo_problema=linha_limpa,
                            sugestao_correcao="Remover import não utilizado",
                            corrigivel_automaticamente=True,
                            regra_violada='F401',
                            contexto=self._extrair_contexto_linha(linhas, i)
                        ))

            # Verificar ordem dos imports
            todos_imports = imports_stdlib + imports_terceiros + imports_locais
            if len(todos_imports) > 1:
                for i in range(1, len(todos_imports)):
                    linha_atual = todos_imports[i][0]
                    linha_anterior = todos_imports[i-1][0]

                    if linha_atual < linha_anterior:
                        problemas.append(ProblemaDetectado(
                            arquivo=str(arquivo),
                            linha=linha_atual,
                            coluna=0,
                            tipo='import',
                            severidade='info',
                            descricao="Imports fora de ordem",
                            codigo_problema=todos_imports[i][1],
                            sugestao_correcao="Reorganizar imports (stdlib, terceiros, locais)",
                            corrigivel_automaticamente=True,
                            regra_violada='I001',
                            contexto=""
                        ))

        except Exception as e:
            montar_log(f"Erro ao analisar imports de {arquivo}: {e}", "ERROR")

        return problemas

    def detectar_complexidade(self, arquivo: Path) -> List[ProblemaDetectado]:
        """Detecta problemas de complexidade"""
        problemas = []

        try:
            with open(arquivo, 'r', encoding='utf-8') as f:
                conteudo = f.read()

            # Analisar AST para complexidade ciclomática
            tree = ast.parse(conteudo)

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    complexidade = self._calcular_complexidade_ciclomatica(node)

                    if complexidade > 10:  # Limite McCabe
                        problemas.append(ProblemaDetectado(
                            arquivo=str(arquivo),
                            linha=node.lineno,
                            coluna=node.col_offset,
                            tipo='complexity',
                            severidade='warning' if complexidade <= 15 else 'error',
                            descricao=f"Função '{node.name}' muito complexa (complexidade: {complexidade})",
                            codigo_problema=f"def {node.name}(...)",
                            sugestao_correcao="Dividir função em funções menores",
                            corrigivel_automaticamente=False,
                            regra_violada='C901',
                            contexto=f"Complexidade ciclomática: {complexidade}"
                        ))

        except Exception as e:
            montar_log(f"Erro ao analisar complexidade de {arquivo}: {e}", "ERROR")

        return problemas

    def _sugerir_correcao_sintaxe(self, erro: SyntaxError) -> str:
        """Sugere correção para erro de sintaxe"""
        msg = erro.msg.lower()

        if 'expected' in msg and 'indent' in msg:
            return "Adicionar indentação adequada"
        elif 'unmatched' in msg:
            return "Verificar parênteses, chaves ou colchetes não fechados"
        elif 'invalid syntax' in msg:
            return "Verificar sintaxe da linha anterior"
        elif 'unexpected eof' in msg:
            return "Arquivo incompleto - verificar estrutura"
        else:
            return "Verificar sintaxe Python"

    def _pode_corrigir_sintaxe(self, erro: SyntaxError) -> bool:
        """Verifica se erro de sintaxe pode ser corrigido automaticamente"""
        msgs_corrigiveis = [
            'expected an indented block',
            'unindent does not match',
            'trailing whitespace'
        ]
        return any(msg in erro.msg.lower() for msg in msgs_corrigiveis)

    def _extrair_contexto(self, conteudo: str, linha: int) -> str:
        """Extrai contexto ao redor de uma linha"""
        linhas = conteudo.split('\n')
        inicio = max(0, linha - 3)
        fim = min(len(linhas), linha + 2)
        return '\n'.join(f"{i+1:3}: {linhas[i]}" for i in range(inicio, fim))

    def _extrair_contexto_linha(self, linhas: List[str], linha: int) -> str:
        """Extrai contexto ao redor de uma linha específica"""
        inicio = max(0, linha - 3)
        fim = min(len(linhas), linha + 2)
        return '\n'.join(f"{i+1:3}: {linhas[i].rstrip()}" for i in range(inicio, fim))

    def _eh_import_stdlib(self, linha: str) -> bool:
        """Verifica se é import da biblioteca padrão"""
        stdlib_modules = {
            'os', 'sys', 'json', 'time', 'datetime', 'pathlib', 're', 'ast',
            'collections', 'typing', 'functools', 'itertools', 'subprocess'
        }

        if linha.startswith('import '):
            modulo = linha.replace('import ', '').split()[0].split('.')[0]
            return modulo in stdlib_modules
        elif linha.startswith('from '):
            modulo = linha.replace('from ', '').split()[0].split('.')[0]
            return modulo in stdlib_modules

        return False

    def _eh_import_local(self, linha: str) -> bool:
        """Verifica se é import local/relativo"""
        return 'from .' in linha or 'from quimera' in linha

    def _extrair_nome_modulo(self, linha: str) -> str:
        """Extrai nome do módulo de uma linha de import"""
        if linha.startswith('import '):
            return linha.replace('import ', '').split()[0].split('.')[0]
        elif linha.startswith('from '):
            parts = linha.split()
            if 'import' in parts:
                return parts[parts.index('import') + 1].split(',')[0].split('.')[0]
        return ""

    def _modulo_utilizado(self, modulo: str, conteudo: str) -> bool:
        """Verifica se módulo é utilizado no código"""
        # Busca simples - pode ser melhorada
        return modulo in conteudo.replace(f'import {modulo}', '').replace(f'from {modulo}', '')

    def _calcular_complexidade_ciclomatica(self, node: ast.AST) -> int:
        """Calcula complexidade ciclomática de uma função"""
        complexidade = 1  # Complexidade base

        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                complexidade += 1
            elif isinstance(child, ast.ExceptHandler):
                complexidade += 1
            elif isinstance(child, (ast.And, ast.Or)):
                complexidade += 1

        return complexidade


class CorretorAutomatico:
    """Especialista em corrigir automaticamente problemas de código"""

    def __init__(self):
        self.formatters_config = self._carregar_configuracao_formatters()

    def _carregar_configuracao_formatters(self) -> Dict[str, Any]:
        """Carrega configuração para formatters"""
        return {
            'black': {
                'line_length': 88,
                'target_version': ['py38'],
                'skip_string_normalization': False
            },
            'autopep8': {
                'max_line_length': 88,
                'aggressive': 2,
                'experimental': True
            },
            'isort': {
                'profile': 'black',
                'multi_line_output': 3,
                'line_length': 88,
                'known_first_party': ['quimera']
            }
        }

    def corrigir_sintaxe(self, arquivo: Path, problemas: List[ProblemaDetectado]) -> List[ProblemaDetectado]:
        """Corrige problemas de sintaxe automaticamente"""
        corrigidos = []

        try:
            with open(arquivo, 'r', encoding='utf-8') as f:
                linhas = f.readlines()

            linhas_modificadas = linhas.copy()

            for problema in problemas:
                if problema.tipo == 'syntax' and problema.corrigivel_automaticamente:
                    if self._corrigir_problema_sintaxe(linhas_modificadas, problema):
                        corrigidos.append(problema)

            if corrigidos:
                with open(arquivo, 'w', encoding='utf-8') as f:
                    f.writelines(linhas_modificadas)

        except Exception as e:
            montar_log(f"Erro ao corrigir sintaxe de {arquivo}: {e}", "ERROR")

        return corrigidos

    def corrigir_formatacao_black(self, arquivo: Path) -> bool:
        """Aplica formatação Black"""
        if not FORMATTERS_AVAILABLE.get('black', False):
            montar_log("Black não disponível", "WARNING")
            return False

        try:
            cmd = [
                'black',
                '--line-length', str(self.formatters_config['black']['line_length']),
                '--quiet',
                str(arquivo)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                montar_log(f"Black aplicado com sucesso em {arquivo}", "INFO")
                return True
            else:
                montar_log(f"Erro no Black: {result.stderr}", "WARNING")
                return False

        except Exception as e:
            montar_log(f"Erro ao executar Black: {e}", "ERROR")
            return False

    def corrigir_formatacao_autopep8(self, arquivo: Path) -> bool:
        """Aplica formatação autopep8"""
        if not FORMATTERS_AVAILABLE.get('autopep8', False):
            montar_log("autopep8 não disponível", "WARNING")
            return False

        try:
            cmd = [
                'autopep8',
                '--in-place',
                '--max-line-length', str(self.formatters_config['autopep8']['max_line_length']),
                '--aggressive', '--aggressive',
                str(arquivo)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                montar_log(f"autopep8 aplicado com sucesso em {arquivo}", "INFO")
                return True
            else:
                montar_log(f"Erro no autopep8: {result.stderr}", "WARNING")
                return False

        except Exception as e:
            montar_log(f"Erro ao executar autopep8: {e}", "ERROR")
            return False

    def corrigir_imports_isort(self, arquivo: Path) -> bool:
        """Organiza imports com isort"""
        if not FORMATTERS_AVAILABLE.get('isort', False):
            montar_log("isort não disponível", "WARNING")
            return False

        try:
            cmd = [
                'isort',
                '--profile', 'black',
                '--line-length', str(self.formatters_config['isort']['line_length']),
                '--quiet',
                str(arquivo)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                montar_log(f"isort aplicado com sucesso em {arquivo}", "INFO")
                return True
            else:
                montar_log(f"Erro no isort: {result.stderr}", "WARNING")
                return False

        except Exception as e:
            montar_log(f"Erro ao executar isort: {e}", "ERROR")
            return False

    def corrigir_indentacao_manual(self, arquivo: Path, problemas: List[ProblemaDetectado]) -> List[ProblemaDetectado]:
        """Corrige problemas de indentação manualmente"""
        corrigidos = []

        try:
            with open(arquivo, 'r', encoding='utf-8') as f:
                conteudo = f.read()

            # Converter tabs para espaços
            conteudo_corrigido = conteudo.expandtabs(4)

            # Corrigir indentação inconsistente
            linhas = conteudo_corrigido.split('\n')
            linhas_corrigidas = []

            for linha in linhas:
                if linha.strip():  # Linha não vazia
                    espacos_inicio = len(linha) - len(linha.lstrip(' '))
                    if espacos_inicio > 0:
                        # Arredondar para múltiplo de 4
                        novo_espacos = ((espacos_inicio + 2) // 4) * 4
                        linha_corrigida = ' ' * novo_espacos + linha.lstrip()
                        linhas_corrigidas.append(linha_corrigida)
                    else:
                        linhas_corrigidas.append(linha)
                else:
                    linhas_corrigidas.append('')

            conteudo_final = '\n'.join(linhas_corrigidas)

            if conteudo_final != conteudo:
                with open(arquivo, 'w', encoding='utf-8') as f:
                    f.write(conteudo_final)

                # Marcar problemas como corrigidos
                for problema in problemas:
                    if problema.tipo == 'indentation':
                        corrigidos.append(problema)

        except Exception as e:
            montar_log(f"Erro ao corrigir indentação de {arquivo}: {e}", "ERROR")

        return corrigidos

    def _corrigir_problema_sintaxe(self, linhas: List[str], problema: ProblemaDetectado) -> bool:
        """Corrige um problema específico de sintaxe"""
        try:
            linha_idx = problema.linha - 1

            if 'expected an indented block' in problema.descricao:
                # Adicionar indentação
                if linha_idx < len(linhas):
                    linhas[linha_idx] = '    ' + linhas[linha_idx].lstrip()
                    return True

            elif 'trailing whitespace' in problema.descricao:
                # Remover espaços no final
                if linha_idx < len(linhas):
                    linhas[linha_idx] = linhas[linha_idx].rstrip() + '\n'
                    return True

        except Exception as e:
            montar_log(f"Erro ao corrigir problema de sintaxe: {e}", "ERROR")

        return False


class AgenteFiscalCodigo(AgenteBase):
    """
    Agente Fiscal de Código Ultra-Especializado

    Responsável por:
    - Detectar e corrigir automaticamente problemas de código
    - Aplicar formatação consistente
    - Garantir aderência aos padrões PEP8
    - Gerar relatórios detalhados
    - Integração com CI/CD
    """

    def __init__(self, configuracao: Optional[Dict[str, Any]] = None):
        super().__init__()

        self.nome = "Agente Fiscal de Código"
        self.versao = "1.0.0"
        self.especialidade = "Detecção e correção automática de problemas de código"

        self.detector = DetectorProblemas()
        self.corretor = CorretorAutomatico()

        # Configuração
        self.config = configuracao or self._carregar_configuracao_padrao()

        # Estatísticas
        self.estatisticas = {
            'arquivos_processados': 0,
            'problemas_detectados': 0,
            'problemas_corrigidos': 0,
            'tempo_total_execucao': 0.0,
            'execucoes_totais': 0
        }

        montar_log(f"{self.nome} v{self.versao} inicializado", "INFO")
        montar_log(f"Formatters disponíveis: {[k for k, v in FORMATTERS_AVAILABLE.items() if v]}", "INFO")

    def _carregar_configuracao_padrao(self) -> Dict[str, Any]:
        """Carrega configuração padrão"""
        return {
            'formatar_com_black': True,
            'formatar_com_autopep8': False,  # Usar apenas um formatter principal
            'organizar_imports': True,
            'corrigir_sintaxe': True,
            'corrigir_indentacao': True,
            'detectar_complexidade': True,
            'limite_complexidade': 10,
            'limite_linha': 88,
            'modo_agressivo': True,
            'backup_arquivos': True,
            'relatorio_detalhado': True,
            'executar_paralelo': True,
            'max_workers': 4,
            'timeout_por_arquivo': 60,
            'extensions_incluir': ['.py'],
            'diretorios_ignorar': [
                '__pycache__', '.git', '.venv', 'venv',
                'node_modules', 'build', 'dist'
            ],
            'arquivos_ignorar': [
                '__init__.py'  # Geralmente simples
            ]
        }

    async def fiscalizar_projeto(self, caminho_projeto: str) -> RelatorioFiscalizacao:
        """
        Fiscaliza um projeto completo

        Args:
            caminho_projeto: Caminho para o diretório do projeto

        Returns:
            Relatório completo da fiscalização
        """
        inicio = time.time()
        montar_log(f"Iniciando fiscalização do projeto: {caminho_projeto}", "INFO")

        # Encontrar arquivos Python
        arquivos_python = self._encontrar_arquivos_python(Path(caminho_projeto))

        if not arquivos_python:
            montar_log("Nenhum arquivo Python encontrado", "WARNING")
            return RelatorioFiscalizacao(
                timestamp=datetime.now(),
                arquivos_analisados=0,
                problemas_encontrados=[],
                problemas_corrigidos=[],
                estatisticas={},
                tempo_execucao=0.0,
                ferramentas_utilizadas=[],
                configuracao_utilizada=self.config
            )

        montar_log(f"Encontrados {len(arquivos_python)} arquivos Python", "INFO")

        # Criar backup se configurado
        if self.config['backup_arquivos']:
            self._criar_backup_projeto(Path(caminho_projeto))

        # Processar arquivos
        if self.config['executar_paralelo']:
            todos_problemas, todos_corrigidos = await self._processar_arquivos_paralelo(arquivos_python)
        else:
            todos_problemas, todos_corrigidos = await self._processar_arquivos_sequencial(arquivos_python)

        # Gerar relatório
        tempo_execucao = time.time() - inicio
        relatorio = self._gerar_relatorio(
            arquivos_python, todos_problemas, todos_corrigidos, tempo_execucao
        )

        # Atualizar estatísticas
        self._atualizar_estatisticas(relatorio)

        montar_log(f"Fiscalização concluída em {tempo_execucao:.2f}s", "SUCCESS")
        montar_log(f"Problemas encontrados: {len(todos_problemas)}", "INFO")
        montar_log(f"Problemas corrigidos: {len(todos_corrigidos)}", "INFO")

        return relatorio

    async def fiscalizar_arquivo(self, caminho_arquivo: str) -> RelatorioFiscalizacao:
        """
        Fiscaliza um arquivo específico

        Args:
            caminho_arquivo: Caminho para o arquivo Python

        Returns:
            Relatório da fiscalização do arquivo
        """
        inicio = time.time()
        arquivo = Path(caminho_arquivo)

        if not arquivo.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {caminho_arquivo}")

        if arquivo.suffix != '.py':
            raise ValueError(f"Arquivo não é Python: {caminho_arquivo}")

        montar_log(f"Fiscalizando arquivo: {arquivo}", "INFO")

        # Detectar problemas
        problemas = await self._detectar_problemas_arquivo(arquivo)

        # Corrigir problemas
        corrigidos = await self._corrigir_problemas_arquivo(arquivo, problemas)

        # Gerar relatório
        tempo_execucao = time.time() - inicio
        relatorio = self._gerar_relatorio([arquivo], problemas, corrigidos, tempo_execucao)

        return relatorio

    async def _detectar_problemas_arquivo(self, arquivo: Path) -> List[ProblemaDetectado]:
        """Detecta todos os problemas em um arquivo"""
        problemas = []

        try:
            # Sintaxe
            problemas.extend(self.detector.detectar_problemas_sintaxe(arquivo))

            # Indentação
            problemas.extend(self.detector.detectar_problemas_indentacao(arquivo))

            # Estilo
            problemas.extend(self.detector.detectar_problemas_estilo(arquivo))

            # Imports
            problemas.extend(self.detector.detectar_problemas_imports(arquivo))

            # Complexidade
            if self.config['detectar_complexidade']:
                problemas.extend(self.detector.detectar_complexidade(arquivo))

        except Exception as e:
            montar_log(f"Erro ao detectar problemas em {arquivo}: {e}", "ERROR")

        return problemas

    async def _corrigir_problemas_arquivo(self, arquivo: Path, problemas: List[ProblemaDetectado]) -> List[ProblemaDetectado]:
        """Corrige problemas em um arquivo"""
        corrigidos = []

        try:
            # Corrigir sintaxe primeiro
            if self.config['corrigir_sintaxe']:
                problemas_sintaxe = [p for p in problemas if p.tipo == 'syntax']
                corrigidos.extend(self.corretor.corrigir_sintaxe(arquivo, problemas_sintaxe))

            # Corrigir indentação manualmente
            if self.config['corrigir_indentacao']:
                problemas_indentacao = [p for p in problemas if p.tipo == 'indentation']
                corrigidos.extend(self.corretor.corrigir_indentacao_manual(arquivo, problemas_indentacao))

            # Organizar imports
            if self.config['organizar_imports']:
                if self.corretor.corrigir_imports_isort(arquivo):
                    problemas_import = [p for p in problemas if p.tipo == 'import']
                    corrigidos.extend(problemas_import)

            # Aplicar formatação principal
            if self.config['formatar_com_black']:
                if self.corretor.corrigir_formatacao_black(arquivo):
                    problemas_style = [p for p in problemas if p.tipo == 'style' and p.corrigivel_automaticamente]
                    corrigidos.extend(problemas_style)
            elif self.config['formatar_com_autopep8']:
                if self.corretor.corrigir_formatacao_autopep8(arquivo):
                    problemas_style = [p for p in problemas if p.tipo == 'style' and p.corrigivel_automaticamente]
                    corrigidos.extend(problemas_style)

        except Exception as e:
            montar_log(f"Erro ao corrigir problemas em {arquivo}: {e}", "ERROR")

        return corrigidos

    async def _processar_arquivos_paralelo(self, arquivos: List[Path]) -> Tuple[List[ProblemaDetectado], List[ProblemaDetectado]]:
        """Processa arquivos em paralelo"""
        todos_problemas = []
        todos_corrigidos = []

        with ThreadPoolExecutor(max_workers=self.config['max_workers']) as executor:
            futures = []

            for arquivo in arquivos:
                future = executor.submit(self._processar_arquivo_sync, arquivo)
                futures.append(future)

            for future in futures:
                try:
                    problemas, corrigidos = future.result(timeout=self.config['timeout_por_arquivo'])
                    todos_problemas.extend(problemas)
                    todos_corrigidos.extend(corrigidos)
                except Exception as e:
                    montar_log(f"Erro no processamento paralelo: {e}", "ERROR")

        return todos_problemas, todos_corrigidos

    async def _processar_arquivos_sequencial(self, arquivos: List[Path]) -> Tuple[List[ProblemaDetectado], List[ProblemaDetectado]]:
        """Processa arquivos sequencialmente"""
        todos_problemas = []
        todos_corrigidos = []

        for arquivo in arquivos:
            try:
                problemas = await self._detectar_problemas_arquivo(arquivo)
                corrigidos = await self._corrigir_problemas_arquivo(arquivo, problemas)

                todos_problemas.extend(problemas)
                todos_corrigidos.extend(corrigidos)

            except Exception as e:
                montar_log(f"Erro ao processar {arquivo}: {e}", "ERROR")

        return todos_problemas, todos_corrigidos

    def _processar_arquivo_sync(self, arquivo: Path) -> Tuple[List[ProblemaDetectado], List[ProblemaDetectado]]:
        """Versão síncrona para ThreadPoolExecutor"""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            problemas = loop.run_until_complete(self._detectar_problemas_arquivo(arquivo))
            corrigidos = loop.run_until_complete(self._corrigir_problemas_arquivo(arquivo, problemas))
            return problemas, corrigidos
        finally:
            loop.close()

    def _encontrar_arquivos_python(self, caminho: Path) -> List[Path]:
        """Encontra todos os arquivos Python no projeto"""
        arquivos = []

        for root, dirs, files in os.walk(caminho):
            # Filtrar diretórios ignorados
            dirs[:] = [d for d in dirs if d not in self.config['diretorios_ignorar']]

            for file in files:
                if any(file.endswith(ext) for ext in self.config['extensions_incluir']):
                    arquivo_path = Path(root) / file

                    # Verificar se arquivo deve ser ignorado
                    if file not in self.config['arquivos_ignorar']:
                        arquivos.append(arquivo_path)

        return arquivos

    def _criar_backup_projeto(self, caminho_projeto: Path):
        """Cria backup do projeto antes das modificações"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = caminho_projeto.parent / f"{caminho_projeto.name}_backup_{timestamp}"

            shutil.copytree(caminho_projeto, backup_dir, ignore=shutil.ignore_patterns(
                '__pycache__', '*.pyc', '.git', 'venv', '.venv'
            ))

            montar_log(f"Backup criado em: {backup_dir}", "INFO")

        except Exception as e:
            montar_log(f"Erro ao criar backup: {e}", "WARNING")

    def _gerar_relatorio(self, arquivos: List[Path], problemas: List[ProblemaDetectado],
                        corrigidos: List[ProblemaDetectado], tempo_execucao: float) -> RelatorioFiscalizacao:
        """Gera relatório completo da fiscalização"""

        # Estatísticas
        estatisticas = {
            'total_arquivos': len(arquivos),
            'total_problemas': len(problemas),
            'total_corrigidos': len(corrigidos),
            'taxa_correcao': len(corrigidos) / len(problemas) if problemas else 0,
            'problemas_por_tipo': {},
            'problemas_por_severidade': {},
            'arquivos_com_problemas': len(set(p.arquivo for p in problemas)),
            'arquivos_corrigidos': len(set(p.arquivo for p in corrigidos))
        }

        # Agrupar por tipo
        for problema in problemas:
            tipo = problema.tipo
            estatisticas['problemas_por_tipo'][tipo] = estatisticas['problemas_por_tipo'].get(tipo, 0) + 1

        # Agrupar por severidade
        for problema in problemas:
            sev = problema.severidade
            estatisticas['problemas_por_severidade'][sev] = estatisticas['problemas_por_severidade'].get(sev, 0) + 1

        # Ferramentas utilizadas
        ferramentas = []
        if self.config['formatar_com_black'] and FORMATTERS_AVAILABLE.get('black'):
            ferramentas.append('black')
        if self.config['formatar_com_autopep8'] and FORMATTERS_AVAILABLE.get('autopep8'):
            ferramentas.append('autopep8')
        if self.config['organizar_imports'] and FORMATTERS_AVAILABLE.get('isort'):
            ferramentas.append('isort')

        return RelatorioFiscalizacao(
            timestamp=datetime.now(),
            arquivos_analisados=len(arquivos),
            problemas_encontrados=problemas,
            problemas_corrigidos=corrigidos,
            estatisticas=estatisticas,
            tempo_execucao=tempo_execucao,
            ferramentas_utilizadas=ferramentas,
            configuracao_utilizada=self.config.copy()
        )

    def _atualizar_estatisticas(self, relatorio: RelatorioFiscalizacao):
        """Atualiza estatísticas globais do agente"""
        self.estatisticas['arquivos_processados'] += relatorio.arquivos_analisados
        self.estatisticas['problemas_detectados'] += len(relatorio.problemas_encontrados)
        self.estatisticas['problemas_corrigidos'] += len(relatorio.problemas_corrigidos)
        self.estatisticas['tempo_total_execucao'] += relatorio.tempo_execucao
        self.estatisticas['execucoes_totais'] += 1

    def salvar_relatorio_html(self, relatorio: RelatorioFiscalizacao, caminho_saida: str):
        """Salva relatório em formato HTML"""
        try:
            html_content = self._gerar_html_relatorio(relatorio)

            with open(caminho_saida, 'w', encoding='utf-8') as f:
                f.write(html_content)

            montar_log(f"Relatório HTML salvo em: {caminho_saida}", "INFO")

        except Exception as e:
            montar_log(f"Erro ao salvar relatório HTML: {e}", "ERROR")

    def salvar_relatorio_json(self, relatorio: RelatorioFiscalizacao, caminho_saida: str):
        """Salva relatório em formato JSON"""
        try:
            # Converter para dict serializável
            relatorio_dict = {
                'timestamp': relatorio.timestamp.isoformat(),
                'arquivos_analisados': relatorio.arquivos_analisados,
                'problemas_encontrados': [self._problema_to_dict(p) for p in relatorio.problemas_encontrados],
                'problemas_corrigidos': [self._problema_to_dict(p) for p in relatorio.problemas_corrigidos],
                'estatisticas': relatorio.estatisticas,
                'tempo_execucao': relatorio.tempo_execucao,
                'ferramentas_utilizadas': relatorio.ferramentas_utilizadas,
                'configuracao_utilizada': relatorio.configuracao_utilizada
            }

            with open(caminho_saida, 'w', encoding='utf-8') as f:
                json.dump(relatorio_dict, f, indent=2, ensure_ascii=False)

            montar_log(f"Relatório JSON salvo em: {caminho_saida}", "INFO")

        except Exception as e:
            montar_log(f"Erro ao salvar relatório JSON: {e}", "ERROR")

    def _problema_to_dict(self, problema: ProblemaDetectado) -> Dict[str, Any]:
        """Converte ProblemaDetectado para dicionário"""
        return {
            'arquivo': problema.arquivo,
            'linha': problema.linha,
            'coluna': problema.coluna,
            'tipo': problema.tipo,
            'severidade': problema.severidade,
            'descricao': problema.descricao,
            'codigo_problema': problema.codigo_problema,
            'sugestao_correcao': problema.sugestao_correcao,
            'corrigivel_automaticamente': problema.corrigivel_automaticamente,
            'regra_violada': problema.regra_violada,
            'contexto': problema.contexto
        }

    def _gerar_html_relatorio(self, relatorio: RelatorioFiscalizacao) -> str:
        """Gera HTML do relatório"""
        html = f"""
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Relatório de Fiscalização de Código - Quimera</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
                h2 {{ color: #34495e; margin-top: 30px; }}
                .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
                .card {{ background: #ecf0f1; padding: 20px; border-radius: 8px; text-align: center; }}
                .card h3 {{ margin: 0 0 10px 0; color: #2c3e50; }}
                .card .number {{ font-size: 2em; font-weight: bold; color: #3498db; }}
                .critical {{ color: #e74c3c !important; }}
                .error {{ color: #e67e22 !important; }}
                .warning {{ color: #f39c12 !important; }}
                .info {{ color: #3498db !important; }}
                .problema {{ margin: 10px 0; padding: 15px; border-left: 4px solid; border-radius: 0 5px 5px 0; }}
                .problema.critical {{ background: #fdf2f2; border-color: #e74c3c; }}
                .problema.error {{ background: #fef5f0; border-color: #e67e22; }}
                .problema.warning {{ background: #fefcf0; border-color: #f39c12; }}
                .problema.info {{ background: #f0f8ff; border-color: #3498db; }}
                .codigo {{ background: #2c3e50; color: #ecf0f1; padding: 10px; border-radius: 5px; font-family: 'Courier New', monospace; margin: 10px 0; overflow-x: auto; }}
                .badge {{ display: inline-block; padding: 3px 8px; border-radius: 12px; font-size: 0.8em; font-weight: bold; }}
                .badge.critical {{ background: #e74c3c; color: white; }}
                .badge.error {{ background: #e67e22; color: white; }}
                .badge.warning {{ background: #f39c12; color: white; }}
                .badge.info {{ background: #3498db; color: white; }}
                .tools {{ background: #ecf0f1; padding: 15px; border-radius: 8px; margin: 20px 0; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #3498db; color: white; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🔍 Relatório de Fiscalização de Código</h1>
                <p><strong>Gerado em:</strong> {relatorio.timestamp.strftime('%d/%m/%Y às %H:%M:%S')}</p>
                <p><strong>Tempo de execução:</strong> {relatorio.tempo_execucao:.2f} segundos</p>

                <div class="summary">
                    <div class="card">
                        <h3>Arquivos Analisados</h3>
                        <div class="number">{relatorio.arquivos_analisados}</div>
                    </div>
                    <div class="card">
                        <h3>Problemas Encontrados</h3>
                        <div class="number">{len(relatorio.problemas_encontrados)}</div>
                    </div>
                    <div class="card">
                        <h3>Problemas Corrigidos</h3>
                        <div class="number">{len(relatorio.problemas_corrigidos)}</div>
                    </div>
                    <div class="card">
                        <h3>Taxa de Correção</h3>
                        <div class="number">{relatorio.estatisticas.get('taxa_correcao', 0)*100:.1f}%</div>
                    </div>
                </div>

                <div class="tools">
                    <h3>🛠️ Ferramentas Utilizadas</h3>
                    <p>{', '.join(relatorio.ferramentas_utilizadas) if relatorio.ferramentas_utilizadas else 'Nenhuma ferramenta externa disponível'}</p>
                </div>

                <h2>📊 Estatísticas por Tipo</h2>
                <table>
                    <tr><th>Tipo</th><th>Quantidade</th><th>Percentual</th></tr>
        """

        total_problemas = len(relatorio.problemas_encontrados)
        for tipo, count in relatorio.estatisticas.get('problemas_por_tipo', {}).items():
            percentual = (count / total_problemas * 100) if total_problemas > 0 else 0
            html += f"<tr><td>{tipo.title()}</td><td>{count}</td><td>{percentual:.1f}%</td></tr>"

        html += """
                </table>

                <h2>⚠️ Estatísticas por Severidade</h2>
                <table>
                    <tr><th>Severidade</th><th>Quantidade</th><th>Percentual</th></tr>
        """

        for sev, count in relatorio.estatisticas.get('problemas_por_severidade', {}).items():
            percentual = (count / total_problemas * 100) if total_problemas > 0 else 0
            html += f"<tr><td><span class='badge {sev}'>{sev.upper()}</span></td><td>{count}</td><td>{percentual:.1f}%</td></tr>"

        html += """
                </table>

                <h2>🐛 Problemas Detectados</h2>
        """

        # Agrupar problemas por arquivo
        problemas_por_arquivo = defaultdict(list)
        for problema in relatorio.problemas_encontrados:
            problemas_por_arquivo[problema.arquivo].append(problema)

        for arquivo, problemas in problemas_por_arquivo.items():
            html += f"<h3>📄 {os.path.basename(arquivo)}</h3>"

            for problema in problemas:
                corrigido = any(c.arquivo == problema.arquivo and c.linha == problema.linha
                              for c in relatorio.problemas_corrigidos)
                status = "✅ CORRIGIDO" if corrigido else "❌ NÃO CORRIGIDO"

                html += f"""
                <div class="problema {problema.severidade}">
                    <p><strong>Linha {problema.linha}:</strong>
                       <span class="badge {problema.severidade}">{problema.severidade.upper()}</span>
                       <span style="margin-left: 10px;">{status}</span>
                    </p>
                    <p><strong>Problema:</strong> {problema.descricao}</p>
                    <p><strong>Regra:</strong> {problema.regra_violada}</p>
                    <p><strong>Sugestão:</strong> {problema.sugestao_correcao}</p>
                    <div class="codigo">{problema.codigo_problema}</div>
                </div>
                """

        html += """
                <h2>📋 Configuração Utilizada</h2>
                <table>
                    <tr><th>Parâmetro</th><th>Valor</th></tr>
        """

        for key, value in relatorio.configuracao_utilizada.items():
            html += f"<tr><td>{key}</td><td>{value}</td></tr>"

        html += """
                </table>

                <hr>
                <p style="text-align: center; color: #7f8c8d; margin-top: 30px;">
                    <em>Relatório gerado pelo Agente Fiscal de Código - Projeto Quimera</em>
                </p>
            </div>
        </body>
        </html>
        """

        return html

    def obter_estatisticas_globais(self) -> Dict[str, Any]:
        """Retorna estatísticas globais do agente"""
        return {
            'agente_info': {
                'nome': self.nome,
                'versao': self.versao,
                'especialidade': self.especialidade
            },
            'estatisticas': self.estatisticas.copy(),
            'formatters_disponiveis': FORMATTERS_AVAILABLE.copy(),
            'configuracao_atual': self.config.copy()
        }


# Função utilitária para uso direto
def fiscalizar_codigo(caminho: str, configuracao: Optional[Dict[str, Any]] = None) -> RelatorioFiscalizacao:
    """
    Função de conveniência para fiscalizar código

    Args:
        caminho: Caminho para arquivo ou diretório
        configuracao: Configuração opcional

    Returns:
        Relatório da fiscalização
    """
    import asyncio

    agente = AgenteFiscalCodigo(configuracao) if AgenteFiscalCodigo is not None else None

    if os.path.isfile(caminho):
        return asyncio.run(agente.fiscalizar_arquivo(caminho))
    else:
        return asyncio.run(agente.fiscalizar_projeto(caminho))


if __name__ == "__main__":
    # Exemplo de uso
    import sys

    if len(sys.argv) < 2:
        print("Uso: python agente_fiscal_codigo.py <caminho_projeto_ou_arquivo>")
        sys.exit(1)

    caminho = sys.argv[1]
    relatorio = fiscalizar_codigo(caminho)

    print(f"\n🎯 Fiscalização concluída!")
    print(f"   Arquivos analisados: {relatorio.arquivos_analisados}")
    print(f"   Problemas encontrados: {len(relatorio.problemas_encontrados)}")
    print(f"   Problemas corrigidos: {len(relatorio.problemas_corrigidos)}")
    print(f"   Tempo de execução: {relatorio.tempo_execucao:.2f}s")