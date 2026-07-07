# quimera/analise_codigo/code_quality_analyzer.py
"""
Code Quality Analyzer — Métricas de qualidade de código.

Calcula complexidade ciclomática, coesão, acoplamento,
índice de manutenibilidade e outras métricas.

Uso:
    from quimera.analise_codigo.code_quality_analyzer import CodeQualityAnalyzer
    
    analyzer = CodeQualityAnalyzer()
    report = analyzer.analyze_file("/path/to/file.c")
"""

import ast
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class QualityMetrics:
    """Métricas de qualidade de código."""
    file_path: str
    lines_total: int
    lines_code: int
    lines_comments: int
    functions_count: int
    avg_function_length: float
    cyclomatic_complexity: int
    maintainability_index: float
    duplication_ratio: float = 0.0
    issues: List[str] = field(default_factory=list)
    grade: str = "A"


class CodeQualityAnalyzer:
    """Analisador de qualidade de código."""
    
    def analyze_file(self, file_path: str) -> QualityMetrics:
        """Analisa um arquivo e retorna métricas."""
        path = Path(file_path)
        content = path.read_text(errors="ignore")
        lines = content.split('\n')
        
        lines_total = len(lines)
        lines_comments = sum(1 for l in lines if l.strip().startswith(('//', '/*', '*', '#')))
        lines_code = lines_total - lines_comments - sum(1 for l in lines if not l.strip())
        
        # Funções (aproximação para C)
        functions = self._count_c_functions(content)
        
        # Complexidade ciclomática
        complexity = self._cyclomatic_complexity(content)
        
        # Índice de manutenibilidade
        mi = self._maintainability_index(lines_code, complexity, lines_comments)
        
        # Issues
        issues = self._detect_issues(content, lines)
        
        # Grade
        grade = self._calculate_grade(mi, complexity, len(issues), lines_total)
        
        return QualityMetrics(
            file_path=str(path),
            lines_total=lines_total,
            lines_code=lines_code,
            lines_comments=lines_comments,
            functions_count=len(functions),
            avg_function_length=sum(f[1] for f in functions) / max(len(functions), 1),
            cyclomatic_complexity=complexity,
            maintainability_index=mi,
            issues=issues,
            grade=grade,
        )
    
    def _count_c_functions(self, content: str) -> List[tuple]:
        """Conta funções C."""
        import re
        pattern = r'(?:static\s+)?(?:\w+\s+)+\**(\w+)\s*\([^)]*\)\s*\{'
        matches = re.findall(pattern, content)
        return [(m, 0) for m in matches]
    
    def _cyclomatic_complexity(self, content: str) -> int:
        """Calcula complexidade ciclomática."""
        keywords = ['if ', 'else if', 'for ', 'while ', 'case ', '&&', '||', '?']
        return sum(content.count(kw) for kw in keywords) + 1
    
    def _maintainability_index(self, loc: int, complexity: int, comments: int) -> float:
        """Índice de manutenibilidade (0-100)."""
        if loc <= 0:
            return 100.0
        mi = 171 - 5.2 * math.log(loc) - 0.23 * complexity - 16.2 * math.log(max(comments, 1))
        return max(0, min(100, mi))
    
    def _detect_issues(self, content: str, lines: List[str]) -> List[str]:
        """Detecta issues comuns."""
        issues = []
        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                issues.append(f"L{i}: Linha muito longa ({len(line)} caracteres)")
            if '\t' in line:
                issues.append(f"L{i}: Tab detectado (use espaços)")
        if 'TODO' in content:
            issues.append("TODOs pendentes encontrados")
        return issues
    
    def _calculate_grade(self, mi: float, complexity: int, issues: int, loc: int) -> str:
        """Calcula nota A-F."""
        score = mi - issues * 2
        if loc > 1000:
            score -= 5
        if complexity > 50:
            score -= 10
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        return "F"
