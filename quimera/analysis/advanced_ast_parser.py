"""
Parser AST Avançado com Tree-sitter - Quimera Advanced
=====================================================

Sistema de parsing avançado que utiliza Tree-sitter para análise
semântica multi-linguagem e extração de padrões complexos.
"""

import ast
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set
from concurrent.futures import ThreadPoolExecutor
import hashlib

from quimera.logs.parser import montar_log

@dataclass
class ASTNode:
    """Representação de um nó da AST"""
    node_type: str
    name: Optional[str] = None
    line_start: int = 0
    line_end: int = 0
    column_start: int = 0
    column_end: int = 0
    children: List['ASTNode'] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    parent: Optional['ASTNode'] = None

@dataclass
class CodePattern:
    """Padrão de código identificado"""
    pattern_type: str
    description: str
    complexity_score: int
    suggestions: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    severity: str = "INFO"  # INFO, WARNING, ERROR

@dataclass
class SemanticAnalysis:
    """Resultado da análise semântica"""
    file_path: str
    language: str
    ast_nodes: List[ASTNode]
    patterns_found: List[CodePattern]
    metrics: Dict[str, Any]
    dependencies: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)

class AdvancedASTParser:
    """Parser AST avançado com suporte multi-linguagem"""
    
    def __init__(self):
        self.supported_languages = {
            '.py': 'python',
            '.js': 'javascript', 
            '.ts': 'typescript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.go': 'go',
            '.rs': 'rust'
        }
        
        self.pattern_matchers = {}
        self._initialize_pattern_matchers()
        
        montar_log("Parser AST Avançado inicializado", "INFO")
    
    def _initialize_pattern_matchers(self):
        """Inicializa matchers de padrões para diferentes linguagens"""
        
        # Padrões Python
        self.pattern_matchers['python'] = {
            'complex_function': self._detect_complex_functions,
            'code_duplication': self._detect_code_duplication,
            'security_issues': self._detect_security_issues,
            'performance_issues': self._detect_performance_issues,
            'maintainability_issues': self._detect_maintainability_issues,
            'design_patterns': self._detect_design_patterns
        }
        
        # Padrões JavaScript/TypeScript
        self.pattern_matchers['javascript'] = {
            'async_patterns': self._detect_async_patterns,
            'closure_issues': self._detect_closure_issues,
            'prototype_patterns': self._detect_prototype_patterns
        }
        
        self.pattern_matchers['typescript'] = self.pattern_matchers['javascript'].copy()
        self.pattern_matchers['typescript'].update({
            'type_issues': self._detect_type_issues,
            'interface_patterns': self._detect_interface_patterns
        })
    
    def parse_file(self, file_path: str) -> SemanticAnalysis:
        """Analisa um arquivo de código"""
        
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
        
        # Detectar linguagem
        language = self._detect_language(file_path)
        
        if language not in self.supported_languages.values():
            raise ValueError(f"Linguagem não suportada: {language}")
        
        # Ler conteúdo
        content = file_path.read_text(encoding='utf-8', errors='ignore')
        
        # Parse com AST nativo primeiro
        ast_nodes = self._parse_with_native_ast(content, language)
        
        # Análise de padrões
        patterns_found = self._analyze_patterns(content, language, ast_nodes)
        
        # Calcular métricas
        metrics = self._calculate_metrics(content, ast_nodes)
        
        # Extrair dependências
        dependencies = self._extract_dependencies(content, language)
        
        # Detectar issues
        issues = self._detect_issues(content, language, ast_nodes)
        
        return SemanticAnalysis(
            file_path=str(file_path),
            language=language,
            ast_nodes=ast_nodes,
            patterns_found=patterns_found,
            metrics=metrics,
            dependencies=dependencies,
            issues=issues
        )
    
    def parse_directory(self, directory_path: str, recursive: bool = True) -> List[SemanticAnalysis]:
        """Analisa todos os arquivos de código em um diretório"""
        
        directory = Path(directory_path)
        
        if not directory.exists():
            raise FileNotFoundError(f"Diretório não encontrado: {directory}")
        
        # Encontrar arquivos de código
        code_files = []
        
        pattern = "**/*" if recursive else "*"
        
        for ext in self.supported_languages.keys():
            code_files.extend(directory.glob(f"{pattern}{ext}"))
        
        # Analisar arquivos em paralelo
        results = []
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(self.parse_file, str(file)) for file in code_files]
            
            for future in futures:
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    montar_log(f"Erro ao analisar arquivo: {e}", "ERROR")
        
        montar_log(f"Analisados {len(results)} arquivos em {directory}", "INFO")
        
        return results
    
    def _detect_language(self, file_path: Path) -> str:
        """Detecta a linguagem do arquivo"""
        suffix = file_path.suffix.lower()
        return self.supported_languages.get(suffix, 'unknown')
    
    def _parse_with_native_ast(self, content: str, language: str) -> List[ASTNode]:
        """Parse usando AST nativo da linguagem"""
        
        ast_nodes = []
        
        if language == 'python':
            try:
                tree = ast.parse(content)
                ast_nodes = self._convert_python_ast(tree)
            except SyntaxError as e:
                montar_log(f"Erro de sintaxe Python: {e}", "ERROR")
        
        elif language in ['javascript', 'typescript']:
            # Para JavaScript/TypeScript, usaríamos uma biblioteca como esprima
            # Por enquanto, implementação simplificada
            ast_nodes = self._parse_js_ts_simple(content)
        
        return ast_nodes
    
    def _convert_python_ast(self, tree: ast.AST) -> List[ASTNode]:
        """Converte AST Python para formato padrão"""
        
        nodes = []
        
        for node in ast.walk(tree):
            ast_node = ASTNode(
                node_type=type(node).__name__,
                line_start=getattr(node, 'lineno', 0),
                line_end=getattr(node, 'end_lineno', 0),
                column_start=getattr(node, 'col_offset', 0),
                column_end=getattr(node, 'end_col_offset', 0)
            )
            
            # Extrair informações específicas do tipo de nó
            if isinstance(node, ast.FunctionDef):
                ast_node.name = node.name
                ast_node.attributes['args'] = [arg.arg for arg in node.args.args]
                ast_node.attributes['decorators'] = [d.id if hasattr(d, 'id') else str(d) for d in node.decorator_list]
            
            elif isinstance(node, ast.ClassDef):
                ast_node.name = node.name
                ast_node.attributes['bases'] = [base.id if hasattr(base, 'id') else str(base) for base in node.bases]
            
            elif isinstance(node, ast.Import):
                ast_node.attributes['modules'] = [alias.name for alias in node.names]
            
            elif isinstance(node, ast.ImportFrom):
                ast_node.attributes['module'] = node.module
                ast_node.attributes['names'] = [alias.name for alias in node.names]
            
            nodes.append(ast_node)
        
        return nodes
    
    def _parse_js_ts_simple(self, content: str) -> List[ASTNode]:
        """Parse simplificado para JavaScript/TypeScript"""
        
        nodes = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Detectar funções
            if line.startswith('function ') or 'function(' in line:
                func_match = re.search(r'function\s+(\w+)', line)
                name = func_match.group(1) if func_match else 'anonymous'
                
                nodes.append(ASTNode(
                    node_type='FunctionDeclaration',
                    name=name,
                    line_start=i + 1,
                    line_end=i + 1
                ))
            
            # Detectar classes
            elif line.startswith('class '):
                class_match = re.search(r'class\s+(\w+)', line)
                name = class_match.group(1) if class_match else 'anonymous'
                
                nodes.append(ASTNode(
                    node_type='ClassDeclaration',
                    name=name,
                    line_start=i + 1,
                    line_end=i + 1
                ))
        
        return nodes
    
    def _analyze_patterns(self, content: str, language: str, ast_nodes: List[ASTNode]) -> List[CodePattern]:
        """Analisa padrões no código"""
        
        patterns = []
        
        if language in self.pattern_matchers:
            matchers = self.pattern_matchers[language]
            
            for pattern_name, matcher_func in matchers.items():
                try:
                    pattern_results = matcher_func(content, ast_nodes)
                    patterns.extend(pattern_results)
                except Exception as e:
                    montar_log(f"Erro no matcher {pattern_name}: {e}", "WARNING")
        
        return patterns
    
    def _detect_complex_functions(self, content: str, ast_nodes: List[ASTNode]) -> List[CodePattern]:
        """Detecta funções complexas"""
        
        patterns = []
        
        for node in ast_nodes:
            if node.node_type == 'FunctionDef':
                # Calcular complexidade ciclomática simplificada
                complexity = self._calculate_cyclomatic_complexity(content, node)
                
                if complexity > 10:
                    patterns.append(CodePattern(
                        pattern_type='complex_function',
                        description=f"Função '{node.name}' tem alta complexidade ({complexity})",
                        complexity_score=complexity,
                        suggestions=[
                            "Considere dividir em funções menores",
                            "Reduza o número de condicionais",
                            "Use padrões como Strategy ou Factory"
                        ],
                        severity="WARNING" if complexity > 15 else "INFO"
                    ))
        
        return patterns
    
    def _detect_code_duplication(self, content: str, ast_nodes: List[ASTNode]) -> List[CodePattern]:
        """Detecta duplicação de código"""
        
        patterns = []
        lines = content.split('\n')
        
        # Detectar linhas similares
        line_hashes = {}
        
        for i, line in enumerate(lines):
            # Normalizar linha (remover espaços e comentários)
            normalized = re.sub(r'#.*$', '', line).strip()
            if len(normalized) > 10:  # Ignorar linhas muito curtas
                line_hash = hashlib.md5(normalized.encode()).hexdigest()
                
                if line_hash in line_hashes:
                    line_hashes[line_hash].append(i + 1)
                else:
                    line_hashes[line_hash] = [i + 1]
        
        # Reportar duplicações
        for line_hash, line_numbers in line_hashes.items():
            if len(line_numbers) > 1:
                patterns.append(CodePattern(
                    pattern_type='code_duplication',
                    description=f"Código duplicado encontrado nas linhas: {', '.join(map(str, line_numbers))}",
                    complexity_score=len(line_numbers),
                    suggestions=[
                        "Extrair para uma função comum",
                        "Usar herança ou composição",
                        "Aplicar princípio DRY (Don't Repeat Yourself)"
                    ],
                    severity="WARNING"
                ))
        
        return patterns
    
    def _detect_security_issues(self, content: str, ast_nodes: List[ASTNode]) -> List[CodePattern]:
        """Detecta problemas de segurança"""
        
        patterns = []
        
        # Padrões de segurança perigosos
        security_patterns = [
            (r'eval\s*\(', 'Uso de eval() é perigoso'),
            (r'exec\s*\(', 'Uso de exec() é perigoso'),
            (r'subprocess\.call\([^)]*shell\s*=\s*True', 'Shell injection vulnerability'),
            (r'input\s*\([^)]*\)', 'Uso de input() pode ser perigoso'),
            (r'pickle\.loads?\s*\(', 'Deserialização insegura com pickle'),
            (r'os\.system\s*\(', 'Execução de sistema insegura'),
        ]
        
        for pattern, description in security_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                
                patterns.append(CodePattern(
                    pattern_type='security_issue',
                    description=f"{description} (linha {line_num})",
                    complexity_score=10,  # Sempre alta prioridade
                    suggestions=[
                        "Use alternativas mais seguras",
                        "Validar todas as entradas",
                        "Implementar sanitização"
                    ],
                    severity="ERROR"
                ))
        
        return patterns
    
    def _detect_performance_issues(self, content: str, ast_nodes: List[ASTNode]) -> List[CodePattern]:
        """Detecta problemas de performance"""
        
        patterns = []
        
        # Padrões de performance
        perf_patterns = [
            (r'for\s+\w+\s+in\s+range\s*\(\s*len\s*\(', 'Loop ineficiente - use enumerate()'),
            (r'\+\s*=.*\[.*\]', 'Concatenação de lista ineficiente - use extend()'),
            (r'\.append\s*\(.*\)\s*\n.*\.append', 'Múltiplos appends - considere usar list comprehension'),
        ]
        
        for pattern, description in perf_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                
                patterns.append(CodePattern(
                    pattern_type='performance_issue',
                    description=f"{description} (linha {line_num})",
                    complexity_score=5,
                    suggestions=[
                        "Otimizar estrutura de dados",
                        "Usar built-ins mais eficientes",
                        "Considerar algoritmos alternativos"
                    ],
                    severity="INFO"
                ))
        
        return patterns
    
    def _detect_maintainability_issues(self, content: str, ast_nodes: List[ASTNode]) -> List[CodePattern]:
        """Detecta problemas de manutenibilidade"""
        
        patterns = []
        
        # Funções muito longas
        for node in ast_nodes:
            if node.node_type == 'FunctionDef':
                func_length = node.line_end - node.line_start
                
                if func_length > 50:
                    patterns.append(CodePattern(
                        pattern_type='maintainability_issue',
                        description=f"Função '{node.name}' muito longa ({func_length} linhas)",
                        complexity_score=func_length // 10,
                        suggestions=[
                            "Dividir em funções menores",
                            "Extrair lógica para classes separadas",
                            "Aplicar Single Responsibility Principle"
                        ],
                        severity="WARNING"
                    ))
        
        return patterns
    
    def _detect_design_patterns(self, content: str, ast_nodes: List[ASTNode]) -> List[CodePattern]:
        """Detecta padrões de design no código"""
        
        patterns = []
        
        # Detectar Singleton pattern
        if 'class ' in content and '__new__' in content:
            patterns.append(CodePattern(
                pattern_type='design_pattern',
                description="Possível padrão Singleton detectado",
                complexity_score=3,
                suggestions=[
                    "Considere usar módulo singleton",
                    "Avalie se realmente precisa de Singleton"
                ],
                severity="INFO"
            ))
        
        # Detectar Factory pattern
        factory_indicators = ['create_', 'make_', 'build_', 'get_instance']
        for indicator in factory_indicators:
            if indicator in content:
                patterns.append(CodePattern(
                    pattern_type='design_pattern',
                    description=f"Possível padrão Factory detectado ({indicator})",
                    complexity_score=2,
                    suggestions=[
                        "Considere implementar Factory completo",
                        "Documente o padrão utilizado"
                    ],
                    severity="INFO"
                ))
                break
        
        return patterns
    
    def _detect_async_patterns(self, content: str, ast_nodes: List[ASTNode]) -> List[CodePattern]:
        """Detecta padrões assíncronos em JavaScript"""
        
        patterns = []
        
        # Detectar callback hell
        callback_depth = content.count('function(') - content.count('function ')
        
        if callback_depth > 3:
            patterns.append(CodePattern(
                pattern_type='async_pattern',
                description=f"Possível callback hell detectado (profundidade: {callback_depth})",
                complexity_score=callback_depth,
                suggestions=[
                    "Use Promises ou async/await",
                    "Extrair funções nomeadas",
                    "Considere usar bibliotecas como RxJS"
                ],
                severity="WARNING"
            ))
        
        return patterns
    
    def _detect_closure_issues(self, content: str, ast_nodes: List[ASTNode]) -> List[CodePattern]:
        """Detecta problemas com closures"""
        
        patterns = []
        
        # Implementação simplificada
        if 'var ' in content and 'for(' in content:
            patterns.append(CodePattern(
                pattern_type='closure_issue',
                description="Possível problema com closure em loop",
                complexity_score=4,
                suggestions=[
                    "Use let ao invés de var",
                    "Use bind() ou arrow functions",
                    "Extrair função para closure apropriado"
                ],
                severity="WARNING"
            ))
        
        return patterns
    
    def _detect_prototype_patterns(self, content: str, ast_nodes: List[ASTNode]) -> List[CodePattern]:
        """Detecta padrões de prototype"""
        
        patterns = []
        
        if '.prototype.' in content:
            patterns.append(CodePattern(
                pattern_type='prototype_pattern',
                description="Uso de prototype detectado",
                complexity_score=2,
                suggestions=[
                    "Considere usar classes ES6",
                    "Documente herança prototype",
                    "Use ferramentas de type checking"
                ],
                severity="INFO"
            ))
        
        return patterns
    
    def _detect_type_issues(self, content: str, ast_nodes: List[ASTNode]) -> List[CodePattern]:
        """Detecta problemas de tipo em TypeScript"""
        
        patterns = []
        
        # Uso de any
        any_matches = re.finditer(r':\s*any\b', content)
        
        for match in any_matches:
            line_num = content[:match.start()].count('\n') + 1
            
            patterns.append(CodePattern(
                pattern_type='type_issue',
                description=f"Uso de 'any' detectado (linha {line_num})",
                complexity_score=3,
                suggestions=[
                    "Especificar tipo mais específico",
                    "Usar union types ou generics",
                    "Criar interfaces customizadas"
                ],
                severity="WARNING"
            ))
        
        return patterns
    
    def _detect_interface_patterns(self, content: str, ast_nodes: List[ASTNode]) -> List[CodePattern]:
        """Detecta padrões de interface"""
        
        patterns = []
        
        interface_count = content.count('interface ')
        
        if interface_count > 0:
            patterns.append(CodePattern(
                pattern_type='interface_pattern',
                description=f"{interface_count} interfaces detectadas",
                complexity_score=1,
                suggestions=[
                    "Manter interfaces coesas",
                    "Usar composition sobre inheritance",
                    "Documentar contratos de interface"
                ],
                severity="INFO"
            ))
        
        return patterns
    
    def _calculate_cyclomatic_complexity(self, content: str, function_node: ASTNode) -> int:
        """Calcula complexidade ciclomática simplificada"""
        
        # Buscar conteúdo da função
        lines = content.split('\n')
        start_line = function_node.line_start - 1
        end_line = function_node.line_end if function_node.line_end > 0 else len(lines)
        
        function_content = '\n'.join(lines[start_line:end_line])
        
        # Contar estruturas de controle
        complexity = 1  # Base complexity
        
        control_structures = [
            'if ', 'elif ', 'else:', 'for ', 'while ',
            'try:', 'except:', 'finally:', 'with ',
            'and ', 'or ', '?', '&&', '||'
        ]
        
        for structure in control_structures:
            complexity += function_content.count(structure)
        
        return complexity
    
    def _calculate_metrics(self, content: str, ast_nodes: List[ASTNode]) -> Dict[str, Any]:
        """Calcula métricas do código"""
        
        lines = content.split('\n')
        
        metrics = {
            'total_lines': len(lines),
            'code_lines': len([line for line in lines if line.strip() and not line.strip().startswith('#')]),
            'comment_lines': len([line for line in lines if line.strip().startswith('#')]),
            'blank_lines': len([line for line in lines if not line.strip()]),
            'function_count': len([node for node in ast_nodes if node.node_type == 'FunctionDef']),
            'class_count': len([node for node in ast_nodes if node.node_type == 'ClassDef']),
            'import_count': len([node for node in ast_nodes if node.node_type in ['Import', 'ImportFrom']]),
        }
        
        # Calcular métricas derivadas
        if metrics['total_lines'] > 0:
            metrics['comment_ratio'] = metrics['comment_lines'] / metrics['total_lines']
            metrics['code_density'] = metrics['code_lines'] / metrics['total_lines']
        
        return metrics
    
    def _extract_dependencies(self, content: str, language: str) -> List[str]:
        """Extrai dependências do código"""
        
        dependencies = []
        
        if language == 'python':
            # Imports Python
            import_patterns = [
                r'import\s+([^\s]+)',
                r'from\s+([^\s]+)\s+import'
            ]
            
            for pattern in import_patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    dep = match.group(1).split('.')[0]  # Primeiro nível
                    if dep not in dependencies:
                        dependencies.append(dep)
        
        elif language in ['javascript', 'typescript']:
            # Imports JS/TS
            js_patterns = [
                r'import.*from\s+[\'"]([^\'"]+)[\'"]',
                r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)'
            ]
            
            for pattern in js_patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    dep = match.group(1)
                    if dep not in dependencies:
                        dependencies.append(dep)
        
        return dependencies
    
    def _detect_issues(self, content: str, language: str, ast_nodes: List[ASTNode]) -> List[str]:
        """Detecta issues gerais no código"""
        
        issues = []
        
        # Issues comuns
        if len(content) > 10000:  # Arquivo muito grande
            issues.append("Arquivo muito grande - considere dividir")
        
        if content.count('\n') > 500:  # Muitas linhas
            issues.append("Muitas linhas - considere refatorar")
        
        # Issues específicos da linguagem
        if language == 'python':
            if 'import *' in content:
                issues.append("Import * pode causar conflitos de namespace")
            
            if re.search(r'except\s*:', content):
                issues.append("Exception handling muito genérico")
        
        return issues

# Instância global do parser
global_parser = AdvancedASTParser()

def parse_code_file(file_path: str) -> SemanticAnalysis:
    """Função de conveniência para parsing de arquivo"""
    return global_parser.parse_file(file_path)

def parse_code_directory(directory_path: str, recursive: bool = True) -> List[SemanticAnalysis]:
    """Função de conveniência para parsing de diretório"""
    return global_parser.parse_directory(directory_path, recursive)