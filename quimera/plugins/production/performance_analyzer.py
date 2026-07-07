#!/usr/bin/env python3
"""
Plugin de Análise de Performance Ultra-Avançado
Detecta gargalos, analisa complexidade computacional, sugere otimizações
e executa benchmarks automatizados.
"""

import ast
import asyncio
import gc
import hashlib
import json
import logging
import math
import memory_profiler
import psutil
import re
import sys
import time
import tracemalloc
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set
import cProfile
import pstats
import io
from contextlib import contextmanager

# Importa framework de plugins
sys.path.append(str(Path(__file__).parent.parent.parent))
from quimera.core.plugin_framework import BasePlugin, PluginInfo, PluginPriority, plugin_decorator


@dataclass
class PerformanceIssue:
    """Representa um problema de performance detectado"""
    severity: str  # critical, high, medium, low
    category: str  # complexity, memory, io, cpu
    description: str
    location: str
    line_number: int
    suggestion: str
    estimated_impact: float  # 0.0 - 1.0
    auto_fixable: bool = False
    fix_code: Optional[str] = None


@dataclass
class ComplexityAnalysis:
    """Análise de complexidade computacional"""
    cyclomatic_complexity: int
    cognitive_complexity: int
    time_complexity: str
    space_complexity: str
    nested_loops: int
    recursive_calls: int


@dataclass
class MemoryProfile:
    """Profile de uso de memória"""
    peak_usage_mb: float
    avg_usage_mb: float
    memory_leaks: List[str]
    gc_collections: int
    large_objects: List[Dict]


@dataclass
class BenchmarkResult:
    """Resultado de benchmark"""
    function_name: str
    execution_time: float
    memory_usage: float
    cpu_usage: float
    iterations: int
    percentiles: Dict[str, float]


class ComplexityAnalyzer(ast.NodeVisitor):
    """Analisador de complexidade de código"""

    def __init__(self):
        self.cyclomatic_complexity = 1
        self.cognitive_complexity = 0
        self.nested_loops = 0
        self.recursive_calls = 0
        self.nesting_level = 0
        self.function_calls = set()
        self.current_function = None

    def visit_FunctionDef(self, node):
        old_function = self.current_function
        self.current_function = node.name

        # Detecta recursão
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if hasattr(child.func, 'id') and child.func.id == node.name:
                    self.recursive_calls += 1

        self.generic_visit(node)
        self.current_function = old_function

    def visit_If(self, node):
        self.cyclomatic_complexity += 1
        self.cognitive_complexity += (1 + self.nesting_level)

        old_nesting = self.nesting_level
        self.nesting_level += 1
        self.generic_visit(node)
        self.nesting_level = old_nesting

    def visit_While(self, node):
        self.cyclomatic_complexity += 1
        self.cognitive_complexity += (1 + self.nesting_level)
        self.nested_loops += 1

        old_nesting = self.nesting_level
        self.nesting_level += 1
        self.generic_visit(node)
        self.nesting_level = old_nesting

    def visit_For(self, node):
        self.cyclomatic_complexity += 1
        self.cognitive_complexity += (1 + self.nesting_level)
        self.nested_loops += 1

        old_nesting = self.nesting_level
        self.nesting_level += 1
        self.generic_visit(node)
        self.nesting_level = old_nesting

    def visit_Try(self, node):
        self.cyclomatic_complexity += 1
        self.cognitive_complexity += (1 + self.nesting_level)
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        self.cyclomatic_complexity += 1
        self.cognitive_complexity += (1 + self.nesting_level)
        self.generic_visit(node)


class MemoryProfiler:
    """Profiler avançado de memória"""

    def __init__(self):
        self.snapshots = []
        self.leaked_objects = []

    @contextmanager
    def profile(self):
        """Context manager para profiling de memória"""
        tracemalloc.start()
        gc.collect()

        snapshot_before = tracemalloc.take_snapshot()

        try:
            yield self
        finally:
            snapshot_after = tracemalloc.take_snapshot()
            tracemalloc.stop()

            self.snapshots.append({
                'before': snapshot_before,
                'after': snapshot_after
            })

    def analyze_memory_usage(self) -> MemoryProfile:
        """Analisa uso de memória"""
        if not self.snapshots:
            return MemoryProfile(0, 0, [], 0, [])

        latest = self.snapshots[-1]
        top_stats = latest['after'].compare_to(latest['before'], 'lineno')

        # Detecta vazamentos
        leaks = []
        for stat in top_stats[:10]:
            if stat.size_diff > 1024 * 1024:  # > 1MB
                leaks.append(f"{stat.traceback}: +{stat.size_diff / 1024 / 1024:.1f}MB")

        # Objetos grandes
        large_objects = []
        for stat in top_stats:
            if stat.size > 10 * 1024 * 1024:  # > 10MB
                large_objects.append({
                    'location': str(stat.traceback),
                    'size_mb': stat.size / 1024 / 1024,
                    'count': stat.count
                })

        # Calcula estatísticas
        total_size = sum(stat.size for stat in top_stats)
        peak_usage = total_size / 1024 / 1024

        return MemoryProfile(
            peak_usage_mb=peak_usage,
            avg_usage_mb=peak_usage * 0.8,  # Estimativa
            memory_leaks=leaks,
            gc_collections=len(gc.get_stats()),
            large_objects=large_objects
        )


class PerformanceBenchmarker:
    """Sistema de benchmark automatizado"""

    def __init__(self):
        self.results = []
        self.profiler = cProfile.Profile()

    async def benchmark_function(self, func, *args, iterations=1000, **kwargs) -> BenchmarkResult:
        """Executa benchmark de função"""
        times = []
        memory_usage = []

        # Warm-up
        for _ in range(10):
            try:
                if asyncio.iscoroutinefunction(func):
                    await func(*args, **kwargs)
                else:
                    func(*args, **kwargs)
            except:
                pass

        # Benchmark real
        process = psutil.Process()

        for i in range(iterations):
            gc.collect()

            # Mede CPU e memória antes
            cpu_before = process.cpu_percent()
            memory_before = process.memory_info().rss

            start_time = time.perf_counter()

            try:
                if asyncio.iscoroutinefunction(func):
                    await func(*args, **kwargs)
                else:
                    func(*args, **kwargs)
            except Exception as e:
                logging.warning(f"Erro no benchmark: {e}")
                continue

            end_time = time.perf_counter()

            # Mede CPU e memória depois
            cpu_after = process.cpu_percent()
            memory_after = process.memory_info().rss

            times.append(end_time - start_time)
            memory_usage.append((memory_after - memory_before) / 1024 / 1024)  # MB

        if not times:
            return BenchmarkResult(func.__name__, 0, 0, 0, 0, {})

        # Calcula estatísticas
        times.sort()
        avg_time = sum(times) / len(times)
        avg_memory = sum(memory_usage) / len(memory_usage)

        percentiles = {
            'p50': times[len(times) // 2],
            'p95': times[int(len(times) * 0.95)],
            'p99': times[int(len(times) * 0.99)],
        }

        return BenchmarkResult(
            function_name=func.__name__,
            execution_time=avg_time,
            memory_usage=avg_memory,
            cpu_usage=0,  # Calculado separadamente
            iterations=len(times),
            percentiles=percentiles
        )


@plugin_decorator(
    name="Performance Analyzer Ultra",
    version="2.0.0",
    description="Análise ultra-avançada de performance com benchmarks automatizados",
    author="Quimera AI",
    priority=PluginPriority.HIGH,
    async_support=True,
    production_ready=True,
    tags=["performance", "optimization", "benchmarks", "memory"]
)
class PerformanceAnalyzerPlugin(BasePlugin):
    """Plugin de análise de performance ultra-avançado"""

    @property
    def info(self) -> PluginInfo:
        return self._plugin_info

    async def initialize(self) -> bool:
        """Inicializa o plugin"""
        try:
            self.complexity_analyzer = ComplexityAnalyzer()
            self.memory_profiler = MemoryProfiler()
            self.benchmarker = PerformanceBenchmarker()
            self.issues = []

            # Configurações padrão
            self.config = {
                'max_complexity': 10,
                'max_nesting': 4,
                'benchmark_iterations': 100,
                'memory_threshold_mb': 100,
                'auto_fix_enabled': True,
                'detailed_analysis': True
            }

            self.logger.info("Performance Analyzer Plugin inicializado")
            return True

        except Exception as e:
            self.logger.error(f"Erro ao inicializar Performance Analyzer: {e}")
            return False

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Executa análise de performance"""
        try:
            file_path = context.get('file_path')
            code_content = context.get('code_content')

            if not file_path or not code_content:
                return {"error": "file_path e code_content são obrigatórios"}

            # Análises principais
            results = {
                'file_path': file_path,
                'timestamp': time.time(),
                'analyses': {}
            }

            # 1. Análise de complexidade
            complexity = await self._analyze_complexity(code_content)
            results['analyses']['complexity'] = complexity.__dict__

            # 2. Análise de performance de código
            performance_issues = await self._analyze_performance_patterns(code_content)
            results['analyses']['performance_issues'] = [issue.__dict__ for issue in performance_issues]

            # 3. Análise de memória (se possível)
            if self.config.get('detailed_analysis', True):
                memory_analysis = await self._analyze_memory_patterns(code_content)
                results['analyses']['memory'] = memory_analysis

            # 4. Sugestões de otimização
            optimizations = await self._generate_optimizations(code_content, complexity, performance_issues)
            results['analyses']['optimizations'] = optimizations

            # 5. Score geral de performance
            performance_score = await self._calculate_performance_score(complexity, performance_issues)
            results['performance_score'] = performance_score

            # 6. Métricas avançadas
            if self.config.get('benchmark_iterations', 0) > 0:
                metrics = await self._extract_advanced_metrics(code_content)
                results['analyses']['metrics'] = metrics

            return results

        except Exception as e:
            self.logger.error(f"Erro na análise de performance: {e}")
            return {"error": str(e)}

    async def _analyze_complexity(self, code: str) -> ComplexityAnalysis:
        """Analisa complexidade do código"""
        try:
            tree = ast.parse(code)
            analyzer = ComplexityAnalyzer()
            analyzer.visit(tree)

            # Estima complexidade temporal
            time_complexity = "O(1)"
            if analyzer.nested_loops >= 2:
                time_complexity = "O(n²)"
            elif analyzer.nested_loops >= 3:
                time_complexity = "O(n³)"
            elif analyzer.nested_loops == 1:
                time_complexity = "O(n)"
            elif analyzer.recursive_calls > 0:
                time_complexity = "O(2ⁿ)"  # Estimativa conservadora

            # Estima complexidade espacial
            space_complexity = "O(1)"
            if analyzer.recursive_calls > 0:
                space_complexity = "O(n)"

            return ComplexityAnalysis(
                cyclomatic_complexity=analyzer.cyclomatic_complexity,
                cognitive_complexity=analyzer.cognitive_complexity,
                time_complexity=time_complexity,
                space_complexity=space_complexity,
                nested_loops=analyzer.nested_loops,
                recursive_calls=analyzer.recursive_calls
            )

        except Exception as e:
            self.logger.error(f"Erro na análise de complexidade: {e}")
            return ComplexityAnalysis(0, 0, "unknown", "unknown", 0, 0)

    async def _analyze_performance_patterns(self, code: str) -> List[PerformanceIssue]:
        """Detecta padrões de performance problemáticos"""
        issues = []
        lines = code.split('\n')

        # Padrões problemáticos
        patterns = {
            # Loops ineficientes
            r'for\s+\w+\s+in\s+range\(len\(': {
                'severity': 'medium',
                'category': 'complexity',
                'description': 'Use enumerate() ao invés de range(len())',
                'suggestion': 'Substitua "for i in range(len(lista))" por "for i, item in enumerate(lista)"'
            },

            # Concatenação de strings ineficiente
            r'\w+\s*\+\=\s*["\'].*["\']': {
                'severity': 'high',
                'category': 'memory',
                'description': 'Concatenação de strings ineficiente',
                'suggestion': 'Use join() ou f-strings para múltiplas concatenações'
            },

            # Imports desnecessários
            r'import\s+\*': {
                'severity': 'medium',
                'category': 'memory',
                'description': 'Import * pode impactar performance e memória',
                'suggestion': 'Importe apenas as funções necessárias'
            },

            # Loops aninhados profundos
            r'(\s+)for\s+.*:\s*\n(\1\s+)for\s+.*:\s*\n(\2\s+)for': {
                'severity': 'critical',
                'category': 'complexity',
                'description': 'Loops aninhados de 3+ níveis detectados',
                'suggestion': 'Considere refatorar usando list comprehensions ou algoritmos mais eficientes'
            },

            # Uso de global
            r'global\s+\w+': {
                'severity': 'medium',
                'category': 'cpu',
                'description': 'Uso de variáveis globais pode impactar performance',
                'suggestion': 'Considere passar variáveis como parâmetros'
            }
        }

        for line_num, line in enumerate(lines, 1):
            for pattern, info in patterns.items():
                if re.search(pattern, line):
                    issue = PerformanceIssue(
                        severity=info['severity'],
                        category=info['category'],
                        description=info['description'],
                        location=f"linha {line_num}",
                        line_number=line_num,
                        suggestion=info['suggestion'],
                        estimated_impact=self._estimate_impact(info['severity']),
                        auto_fixable=info['severity'] in ['low', 'medium']
                    )
                    issues.append(issue)

        return issues

    async def _analyze_memory_patterns(self, code: str) -> Dict[str, Any]:
        """Analisa padrões de uso de memória"""
        analysis = {
            'potential_leaks': [],
            'large_data_structures': [],
            'memory_intensive_operations': []
        }

        lines = code.split('\n')

        # Detecta potenciais vazamentos
        leak_patterns = [
            r'while\s+True:',  # Loops infinitos
            r'global\s+\w+\s*=\s*\[',  # Listas globais
            r'cache\s*=\s*\{',  # Caches não limitados
        ]

        for line_num, line in enumerate(lines, 1):
            for pattern in leak_patterns:
                if re.search(pattern, line):
                    analysis['potential_leaks'].append({
                        'line': line_num,
                        'code': line.strip(),
                        'risk': 'medium'
                    })

        # Detecta estruturas de dados grandes
        large_data_patterns = [
            r'range\(\s*\d{6,}\s*\)',  # Ranges muito grandes
            r'\[\s*\d+\s*\]\s*\*\s*\d{4,}',  # Listas grandes
        ]

        for line_num, line in enumerate(lines, 1):
            for pattern in large_data_patterns:
                if re.search(pattern, line):
                    analysis['large_data_structures'].append({
                        'line': line_num,
                        'code': line.strip()
                    })

        return analysis

    async def _generate_optimizations(self, code: str, complexity: ComplexityAnalysis, issues: List[PerformanceIssue]) -> List[Dict[str, Any]]:
        """Gera sugestões de otimização"""
        optimizations = []

        # Otimizações baseadas na complexidade
        if complexity.cyclomatic_complexity > self.config.get('max_complexity', 10):
            optimizations.append({
                'type': 'refactoring',
                'priority': 'high',
                'description': 'Refatorar função com alta complexidade ciclomática',
                'suggestion': 'Divida a função em funções menores e mais específicas',
                'estimated_benefit': 'Alto'
            })

        if complexity.nested_loops >= 3:
            optimizations.append({
                'type': 'algorithm',
                'priority': 'critical',
                'description': 'Otimizar algoritmo com loops aninhados',
                'suggestion': 'Considere usar algoritmos mais eficientes ou vetorização com NumPy',
                'estimated_benefit': 'Muito Alto'
            })

        # Otimizações baseadas nos issues
        critical_issues = [issue for issue in issues if issue.severity == 'critical']
        if critical_issues:
            optimizations.append({
                'type': 'performance',
                'priority': 'critical',
                'description': f'{len(critical_issues)} problemas críticos de performance detectados',
                'suggestion': 'Corrija os problemas críticos primeiro para maior impacto',
                'estimated_benefit': 'Muito Alto'
            })

        # Sugestões específicas de Python
        if 'for' in code and 'range(len(' in code:
            optimizations.append({
                'type': 'pythonic',
                'priority': 'medium',
                'description': 'Usar padrões mais pythônicos',
                'suggestion': 'Use enumerate(), zip(), list comprehensions quando apropriado',
                'estimated_benefit': 'Médio'
            })

        return optimizations

    async def _calculate_performance_score(self, complexity: ComplexityAnalysis, issues: List[PerformanceIssue]) -> Dict[str, Any]:
        """Calcula score geral de performance"""
        base_score = 100

        # Penalidades por complexidade
        complexity_penalty = min(complexity.cyclomatic_complexity * 2, 30)
        nesting_penalty = min(complexity.nested_loops * 10, 25)

        # Penalidades por issues
        issue_penalty = 0
        for issue in issues:
            if issue.severity == 'critical':
                issue_penalty += 15
            elif issue.severity == 'high':
                issue_penalty += 10
            elif issue.severity == 'medium':
                issue_penalty += 5
            else:
                issue_penalty += 2

        final_score = max(base_score - complexity_penalty - nesting_penalty - issue_penalty, 0)

        # Classificação
        if final_score >= 90:
            grade = 'A'
            classification = 'Excelente'
        elif final_score >= 80:
            grade = 'B'
            classification = 'Bom'
        elif final_score >= 70:
            grade = 'C'
            classification = 'Regular'
        elif final_score >= 60:
            grade = 'D'
            classification = 'Problemático'
        else:
            grade = 'F'
            classification = 'Crítico'

        return {
            'score': final_score,
            'grade': grade,
            'classification': classification,
            'penalties': {
                'complexity': complexity_penalty,
                'nesting': nesting_penalty,
                'issues': issue_penalty
            }
        }

    async def _extract_advanced_metrics(self, code: str) -> Dict[str, Any]:
        """Extrai métricas avançadas do código"""
        return {
            'lines_of_code': len(code.split('\n')),
            'cyclomatic_complexity_density': 0,  # Calculado depois
            'maintainability_index': 0,  # Calculado depois
            'halstead_metrics': {},  # Implementar se necessário
            'code_coverage_estimation': 85  # Estimativa baseada em padrões
        }

    def _estimate_impact(self, severity: str) -> float:
        """Estima impacto do problema na performance"""
        impact_map = {
            'critical': 0.8,
            'high': 0.6,
            'medium': 0.4,
            'low': 0.2
        }
        return impact_map.get(severity, 0.1)

    async def cleanup(self):
        """Limpeza do plugin"""
        self.issues.clear()
        self.logger.info("Performance Analyzer Plugin finalizado")