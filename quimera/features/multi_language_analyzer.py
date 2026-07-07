#!/usr/bin/env python3
"""
🌐 QUIMERA MULTI-LANGUAGE CODE ANALYZER
Analisador ultra-avançado que suporta múltiplas linguagens de programação
"""

import os
import ast
import json
import re
import subprocess
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from pathlib import Path
import tempfile
from abc import ABC, abstractmethod

@dataclass
class AnalysisResult:
    """Resultado da análise de código"""
    language: str
    file_path: str
    complexity: int
    issues: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    security_score: float
    performance_score: float
    maintainability_score: float
    suggestions: List[str]

class LanguageAnalyzer(ABC):
    """Interface para analisadores de linguagem"""

    @abstractmethod
    def analyze(self, code: str, file_path: str) -> AnalysisResult:
        pass

    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        pass

class PythonAnalyzer(LanguageAnalyzer):
    """Analisador avançado para Python"""

    def analyze(self, code: str, file_path: str) -> AnalysisResult:
        issues = []
        metrics = {}

        try:
            # Parse AST
            tree = ast.parse(code)

            # Análise de complexidade
            complexity = self._calculate_complexity(tree)

            # Análise de segurança
            security_issues = self._analyze_security(code, tree)
            issues.extend(security_issues)

            # Análise de performance
            performance_issues = self._analyze_performance(code, tree)
            issues.extend(performance_issues)

            # Métricas de código
            metrics = self._calculate_metrics(code, tree)

            # Scores
            security_score = max(0, 100 - len(security_issues) * 10)
            performance_score = max(0, 100 - len(performance_issues) * 5)
            maintainability_score = max(0, 100 - complexity * 2)

            # Sugestões
            suggestions = self._generate_suggestions(issues, complexity)

        except SyntaxError as e:
            issues.append({
                "type": "syntax_error",
                "severity": "critical",
                "message": f"Erro de sintaxe: {e}",
                "line": e.lineno if hasattr(e, 'lineno') else 0
            })
            complexity = 0
            security_score = 0
            performance_score = 0
            maintainability_score = 0
            suggestions = ["Corrigir erro de sintaxe antes de continuar análise"]

        return AnalysisResult(
            language="python",
            file_path=file_path,
            complexity=complexity,
            issues=issues,
            metrics=metrics,
            security_score=security_score,
            performance_score=performance_score,
            maintainability_score=maintainability_score,
            suggestions=suggestions
        )

    def get_supported_extensions(self) -> List[str]:
        return ['.py', '.pyw', '.pyi']

    def _calculate_complexity(self, tree: ast.AST) -> int:
        complexity = 1
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                complexity += 1
            elif isinstance(node, ast.Try):
                complexity += len(node.handlers)
        return complexity

    def _analyze_security(self, code: str, tree: ast.AST) -> List[Dict[str, Any]]:
        issues = []

        # Detectar imports perigosos
        dangerous_imports = ['eval', 'exec', 'compile', 'subprocess', 'os.system']
        for line_num, line in enumerate(code.split('\n'), 1):
            for dangerous in dangerous_imports:
                if dangerous in line and not line.strip().startswith('#'):
                    issues.append({
                        "type": "security_risk",
                        "severity": "high",
                        "message": f"Uso potencialmente perigoso de '{dangerous}'",
                        "line": line_num
                    })

        # Detectar SQL injection potencial
        sql_patterns = [r'SELECT.*FROM.*WHERE.*%s', r'INSERT.*INTO.*VALUES.*%s']
        for pattern in sql_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                issues.append({
                    "type": "sql_injection_risk",
                    "severity": "critical",
                    "message": "Possível vulnerabilidade de SQL injection",
                    "line": 0
                })

        return issues

    def _analyze_performance(self, code: str, tree: ast.AST) -> List[Dict[str, Any]]:
        issues = []

        # Detectar loops aninhados
        for node in ast.walk(tree):
            if isinstance(node, (ast.For, ast.While)):
                for child in ast.walk(node):
                    if child != node and isinstance(child, (ast.For, ast.While)):
                        issues.append({
                            "type": "performance_warning",
                            "severity": "medium",
                            "message": "Loop aninhado detectado - considere otimização",
                            "line": getattr(node, 'lineno', 0)
                        })
                        break

        # Detectar imports desnecessários no meio do código
        lines = code.split('\n')
        import_after_code = False
        for i, line in enumerate(lines):
            if line.strip() and not line.strip().startswith('#'):
                if 'import ' in line and import_after_code:
                    issues.append({
                        "type": "performance_hint",
                        "severity": "low",
                        "message": "Import no meio do código pode afetar performance",
                        "line": i + 1
                    })
                elif not line.startswith('import') and not line.startswith('from'):
                    import_after_code = True

        return issues

    def _calculate_metrics(self, code: str, tree: ast.AST) -> Dict[str, Any]:
        lines = code.split('\n')
        return {
            "total_lines": len(lines),
            "code_lines": len([l for l in lines if l.strip() and not l.strip().startswith('#')]),
            "comment_lines": len([l for l in lines if l.strip().startswith('#')]),
            "functions": len([n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]),
            "classes": len([n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]),
            "imports": len([n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))])
        }

    def _generate_suggestions(self, issues: List[Dict[str, Any]], complexity: int) -> List[str]:
        suggestions = []

        if complexity > 10:
            suggestions.append("📊 Considere dividir funções complexas em funções menores")

        security_issues = [i for i in issues if i['type'].startswith('security')]
        if security_issues:
            suggestions.append("🔒 Revisar práticas de segurança no código")

        performance_issues = [i for i in issues if i['type'].startswith('performance')]
        if performance_issues:
            suggestions.append("⚡ Otimizar código para melhor performance")

        return suggestions

class JavaScriptAnalyzer(LanguageAnalyzer):
    """Analisador avançado para JavaScript/TypeScript"""

    def analyze(self, code: str, file_path: str) -> AnalysisResult:
        issues = []
        metrics = self._calculate_js_metrics(code)

        # Análise de segurança JS
        security_issues = self._analyze_js_security(code)
        issues.extend(security_issues)

        # Análise de performance JS
        performance_issues = self._analyze_js_performance(code)
        issues.extend(performance_issues)

        # Complexidade ciclomática simplificada
        complexity = self._calculate_js_complexity(code)

        # Scores
        security_score = max(0, 100 - len(security_issues) * 10)
        performance_score = max(0, 100 - len(performance_issues) * 5)
        maintainability_score = max(0, 100 - complexity * 2)

        suggestions = self._generate_js_suggestions(issues, complexity)

        return AnalysisResult(
            language="javascript",
            file_path=file_path,
            complexity=complexity,
            issues=issues,
            metrics=metrics,
            security_score=security_score,
            performance_score=performance_score,
            maintainability_score=maintainability_score,
            suggestions=suggestions
        )

    def get_supported_extensions(self) -> List[str]:
        return ['.js', '.jsx', '.ts', '.tsx', '.mjs']

    def _calculate_js_metrics(self, code: str) -> Dict[str, Any]:
        lines = code.split('\n')
        return {
            "total_lines": len(lines),
            "code_lines": len([l for l in lines if l.strip() and not l.strip().startswith('//')]),
            "comment_lines": len([l for l in lines if l.strip().startswith('//')]),
            "functions": len(re.findall(r'function\s+\w+', code)) + len(re.findall(r'=>', code)),
            "classes": len(re.findall(r'class\s+\w+', code)),
            "imports": len(re.findall(r'import\s+.*from', code))
        }

    def _calculate_js_complexity(self, code: str) -> int:
        complexity = 1
        patterns = [r'\bif\b', r'\bwhile\b', r'\bfor\b', r'\bcatch\b', r'\bswitch\b']
        for pattern in patterns:
            complexity += len(re.findall(pattern, code))
        return complexity

    def _analyze_js_security(self, code: str) -> List[Dict[str, Any]]:
        issues = []

        # Detectar eval e outras funções perigosas
        dangerous_patterns = ['eval(', 'innerHTML =', 'document.write(']
        for line_num, line in enumerate(code.split('\n'), 1):
            for dangerous in dangerous_patterns:
                if dangerous in line and not line.strip().startswith('//'):
                    issues.append({
                        "type": "security_risk",
                        "severity": "high",
                        "message": f"Uso perigoso de '{dangerous}'",
                        "line": line_num
                    })

        return issues

    def _analyze_js_performance(self, code: str) -> List[Dict[str, Any]]:
        issues = []

        # Detectar loops aninhados
        lines = code.split('\n')
        in_loop = False
        for i, line in enumerate(lines):
            if re.search(r'\b(for|while)\b.*\{', line):
                if in_loop:
                    issues.append({
                        "type": "performance_warning",
                        "severity": "medium",
                        "message": "Loop aninhado detectado",
                        "line": i + 1
                    })
                in_loop = True
            elif '}' in line:
                in_loop = False

        return issues

    def _generate_js_suggestions(self, issues: List[Dict[str, Any]], complexity: int) -> List[str]:
        suggestions = []

        if complexity > 10:
            suggestions.append("📊 Considere usar decomposição de funções")

        security_issues = [i for i in issues if i['type'].startswith('security')]
        if security_issues:
            suggestions.append("🔒 Implementar sanitização de dados")

        return suggestions

class GoAnalyzer(LanguageAnalyzer):
    """Analisador para Go"""

    def analyze(self, code: str, file_path: str) -> AnalysisResult:
        issues = []
        metrics = self._calculate_go_metrics(code)
        complexity = self._calculate_go_complexity(code)

        # Análises específicas do Go
        issues.extend(self._analyze_go_patterns(code))

        return AnalysisResult(
            language="go",
            file_path=file_path,
            complexity=complexity,
            issues=issues,
            metrics=metrics,
            security_score=85.0,  # Go tem boa segurança por padrão
            performance_score=90.0,  # Go tem boa performance
            maintainability_score=max(0, 100 - complexity * 2),
            suggestions=["Use go fmt para formatação automática", "Considere usar go vet para análise estática"]
        )

    def get_supported_extensions(self) -> List[str]:
        return ['.go']

    def _calculate_go_metrics(self, code: str) -> Dict[str, Any]:
        lines = code.split('\n')
        return {
            "total_lines": len(lines),
            "code_lines": len([l for l in lines if l.strip() and not l.strip().startswith('//')]),
            "functions": len(re.findall(r'func\s+\w+', code)),
            "structs": len(re.findall(r'type\s+\w+\s+struct', code)),
            "interfaces": len(re.findall(r'type\s+\w+\s+interface', code))
        }

    def _calculate_go_complexity(self, code: str) -> int:
        complexity = 1
        patterns = [r'\bif\b', r'\bfor\b', r'\bswitch\b', r'\bselect\b']
        for pattern in patterns:
            complexity += len(re.findall(pattern, code))
        return complexity

    def _analyze_go_patterns(self, code: str) -> List[Dict[str, Any]]:
        issues = []

        # Verificar tratamento de erros
        if 'err :=' in code and 'if err != nil' not in code:
            issues.append({
                "type": "go_pattern",
                "severity": "medium",
                "message": "Possível erro não tratado",
                "line": 0
            })

        return issues

class MultiLanguageAnalyzer:
    """Analisador principal que coordena todos os analisadores de linguagem"""

    def __init__(self):
        self.analyzers = {
            'python': PythonAnalyzer(),
            'javascript': JavaScriptAnalyzer(),
            'go': GoAnalyzer()
        }

        # Mapeamento de extensões para analisadores
        self.extension_map = {}
        for lang, analyzer in self.analyzers.items():
            for ext in analyzer.get_supported_extensions():
                self.extension_map[ext] = lang

    def analyze_file(self, file_path: str) -> Optional[AnalysisResult]:
        """Analisa um arquivo específico"""
        path = Path(file_path)

        if not path.exists():
            return None

        extension = path.suffix.lower()
        if extension not in self.extension_map:
            return None

        language = self.extension_map[extension]
        analyzer = self.analyzers[language]

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()

            return analyzer.analyze(code, file_path)
        except Exception as e:
            return AnalysisResult(
                language=language,
                file_path=file_path,
                complexity=0,
                issues=[{
                    "type": "analysis_error",
                    "severity": "critical",
                    "message": f"Erro ao analisar arquivo: {e}",
                    "line": 0
                }],
                metrics={},
                security_score=0,
                performance_score=0,
                maintainability_score=0,
                suggestions=["Verificar codificação e integridade do arquivo"]
            )

    def analyze_directory(self, directory_path: str, recursive: bool = True) -> List[AnalysisResult]:
        """Analisa todos os arquivos suportados em um diretório"""
        results = []
        path = Path(directory_path)

        if not path.exists():
            return results

        pattern = "**/*" if recursive else "*"

        for file_path in path.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in self.extension_map:
                result = self.analyze_file(str(file_path))
                if result:
                    results.append(result)

        return results

    def generate_summary_report(self, results: List[AnalysisResult]) -> Dict[str, Any]:
        """Gera relatório resumo das análises"""
        if not results:
            return {"message": "Nenhum arquivo analisado"}

        # Estatísticas por linguagem
        lang_stats = {}
        for result in results:
            lang = result.language
            if lang not in lang_stats:
                lang_stats[lang] = {
                    "files": 0,
                    "total_complexity": 0,
                    "total_issues": 0,
                    "avg_security_score": 0,
                    "avg_performance_score": 0,
                    "avg_maintainability_score": 0
                }

            stats = lang_stats[lang]
            stats["files"] += 1
            stats["total_complexity"] += result.complexity
            stats["total_issues"] += len(result.issues)
            stats["avg_security_score"] += result.security_score
            stats["avg_performance_score"] += result.performance_score
            stats["avg_maintainability_score"] += result.maintainability_score

        # Calcular médias
        for lang, stats in lang_stats.items():
            files = stats["files"]
            stats["avg_complexity"] = stats["total_complexity"] / files
            stats["avg_security_score"] /= files
            stats["avg_performance_score"] /= files
            stats["avg_maintainability_score"] /= files

        # Issues críticos
        critical_issues = []
        for result in results:
            for issue in result.issues:
                if issue.get('severity') == 'critical':
                    critical_issues.append({
                        "file": result.file_path,
                        "language": result.language,
                        "issue": issue
                    })

        return {
            "total_files": len(results),
            "languages_analyzed": list(lang_stats.keys()),
            "language_statistics": lang_stats,
            "critical_issues_count": len(critical_issues),
            "critical_issues": critical_issues[:10],  # Top 10
            "overall_scores": {
                "security": sum(r.security_score for r in results) / len(results),
                "performance": sum(r.performance_score for r in results) / len(results),
                "maintainability": sum(r.maintainability_score for r in results) / len(results)
            }
        }

    def get_supported_languages(self) -> List[str]:
        """Retorna lista de linguagens suportadas"""
        return list(self.analyzers.keys())

    def get_supported_extensions(self) -> List[str]:
        """Retorna lista de extensões suportadas"""
        return list(self.extension_map.keys())

def main():
    """Função principal para demonstração"""
    print("🌐 QUIMERA MULTI-LANGUAGE ANALYZER")
    print("=" * 50)

    analyzer = MultiLanguageAnalyzer()

    print(f"📋 Linguagens suportadas: {', '.join(analyzer.get_supported_languages())}")
    print(f"📋 Extensões suportadas: {', '.join(analyzer.get_supported_extensions())}")
    print()

    # Criar exemplos de código para demonstração
    examples = {
        "example.py": '''
import os
import subprocess

def vulnerable_function(user_input):
    # Potencial SQL injection
    query = f"SELECT * FROM users WHERE name = '{user_input}'"

    # Uso perigoso de eval
    result = eval(user_input)

    # Loop aninhado para demonstrar análise de performance
    for i in range(100):
        for j in range(100):
            print(i * j)

    return result

class ExampleClass:
    def complex_method(self, a, b, c):
        if a > 0:
            if b > 0:
                if c > 0:
                    for i in range(10):
                        while i < 5:
                            i += 1
                        return a + b + c
        return 0
''',
        "example.js": '''
function vulnerableFunction(userInput) {
    // Uso perigoso de eval
    eval(userInput);

    // innerHTML perigoso
    document.getElementById("output").innerHTML = userInput;

    // Loop aninhado
    for (let i = 0; i < 100; i++) {
        for (let j = 0; j < 100; j++) {
            console.log(i * j);
        }
    }
}

class ExampleClass {
    complexMethod(a, b, c) {
        if (a > 0) {
            if (b > 0) {
                if (c > 0) {
                    return a + b + c;
                }
            }
        }
        return 0;
    }
}
''',
        "example.go": '''
package main

import "fmt"

func vulnerableFunction(userInput string) error {
    // Simulação de análise
    err := someOperation()
    // Erro não tratado adequadamente

    return nil
}

func someOperation() error {
    return nil
}

type ExampleStruct struct {
    Name string
    Age  int
}

func (e ExampleStruct) ComplexMethod(a, b, c int) int {
    if a > 0 {
        if b > 0 {
            if c > 0 {
                for i := 0; i < 10; i++ {
                    switch i {
                    case 1:
                        return a + b + c
                    case 2:
                        return a * b * c
                    default:
                        continue
                    }
                }
            }
        }
    }
    return 0
}

func main() {
    fmt.Println("Hello, World!")
}
'''
    }

    # Criar arquivos temporários e analisá-los
    with tempfile.TemporaryDirectory() as temp_dir:
        results = []

        for filename, code in examples.items():
            file_path = os.path.join(temp_dir, filename)
            with open(file_path, 'w') as f:
                f.write(code)

            result = analyzer.analyze_file(file_path)
            if result:
                results.append(result)

                print(f"📁 Análise de {filename} ({result.language.upper()})")
                print(f"   🔢 Complexidade: {result.complexity}")
                print(f"   🔒 Segurança: {result.security_score:.1f}/100")
                print(f"   ⚡ Performance: {result.performance_score:.1f}/100")
                print(f"   🔧 Manutenibilidade: {result.maintainability_score:.1f}/100")
                print(f"   ⚠️  Issues encontrados: {len(result.issues)}")

                if result.issues:
                    for issue in result.issues[:3]:  # Mostrar apenas os 3 primeiros
                        print(f"      - {issue['severity'].upper()}: {issue['message']}")

                if result.suggestions:
                    print("   💡 Sugestões:")
                    for suggestion in result.suggestions:
                        print(f"      - {suggestion}")
                print()

    # Gerar relatório resumo
    if results:
        print("📊 RELATÓRIO RESUMO")
        print("=" * 30)
        summary = analyzer.generate_summary_report(results)

        print(f"Total de arquivos analisados: {summary['total_files']}")
        print(f"Linguagens: {', '.join(summary['languages_analyzed'])}")
        print(f"Issues críticos: {summary['critical_issues_count']}")
        print("\n🎯 Scores Gerais:")
        for metric, score in summary['overall_scores'].items():
            print(f"   {metric.capitalize()}: {score:.1f}/100")

        print("\n📈 Estatísticas por Linguagem:")
        for lang, stats in summary['language_statistics'].items():
            print(f"   {lang.upper()}:")
            print(f"      Arquivos: {stats['files']}")
            print(f"      Complexidade média: {stats['avg_complexity']:.1f}")
            print(f"      Issues totais: {stats['total_issues']}")

if __name__ == "__main__":
    main()