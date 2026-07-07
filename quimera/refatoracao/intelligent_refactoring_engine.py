# quimera/refatoracao/intelligent_refactoring_engine.py
"""
Intelligent Refactoring Engine — Refatoração automática guiada por métricas.

Identifica code smells, propõe refatorações, e aplica mudanças
guiadas pelas métricas do CodeQualityAnalyzer.

Uso:
    from quimera.refatoracao.intelligent_refactoring_engine import IntelligentRefactoringEngine
    
    engine = IntelligentRefactoringEngine()
    suggestions = engine.suggest_refactorings(file_path)
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RefactoringSuggestion:
    """Sugestão de refatoração."""
    type: str
    location: str
    description: str
    impact: str
    auto_applicable: bool
    estimated_improvement: float


class IntelligentRefactoringEngine:
    """Motor de refatoração inteligente."""
    
    def suggest_refactorings(self, file_path: str) -> List[RefactoringSuggestion]:
        """Analisa arquivo e sugere refatorações."""
        path = Path(file_path)
        if not path.exists():
            return []
        
        content = path.read_text(errors="ignore")
        lines = content.split('\n')
        suggestions = []
        
        # Funções longas (> 50 linhas)
        suggestions.extend(self._detect_long_functions(content, lines))
        
        # Código duplicado (padrões repetidos)
        suggestions.extend(self._detect_duplication(lines))
        
        # Magic numbers
        suggestions.extend(self._detect_magic_numbers(lines))
        
        # Deep nesting (> 4 níveis)
        suggestions.extend(self._detect_deep_nesting(lines))
        
        logger.info(f"IntelligentRefactoringEngine: {len(suggestions)} sugestões para '{file_path}'")
        return suggestions
    
    def _detect_long_functions(self, content: str, lines: List[str]) -> List[RefactoringSuggestion]:
        suggestions = []
        import re
        func_starts = [(i, m.group(1)) for i, line in enumerate(lines) 
                       if (m := re.match(r'(?:static\s+)?(?:\w+\s+)+\**(\w+)\s*\([^)]*\)\s*\{', line))]
        
        for i in range(len(func_starts)):
            start_line, name = func_starts[i]
            end_line = func_starts[i+1][0] if i+1 < len(func_starts) else len(lines)
            length = end_line - start_line
            if length > 50:
                suggestions.append(RefactoringSuggestion(
                    type="long_function",
                    location=f"L{start_line+1}",
                    description=f"Função '{name}' com {length} linhas",
                    impact="Alta complexidade, difícil testar",
                    auto_applicable=False,
                    estimated_improvement=0.3,
                ))
        return suggestions
    
    def _detect_duplication(self, lines: List[str]) -> List[RefactoringSuggestion]:
        suggestions = []
        seen = {}
        for i, line in enumerate(lines):
            stripped = line.strip()
            if len(stripped) > 30 and stripped not in ('{', '}'):
                if stripped in seen and (i - seen[stripped]) > 5:
                    suggestions.append(RefactoringSuggestion(
                        type="duplication",
                        location=f"L{seen[stripped]+1} e L{i+1}",
                        description="Código duplicado detectado",
                        impact="Manutenção dobrada",
                        auto_applicable=True,
                        estimated_improvement=0.2,
                    ))
                    break
                seen[stripped] = i
        return suggestions[:3]
    
    def _detect_magic_numbers(self, lines: List[str]) -> List[RefactoringSuggestion]:
        suggestions = []
        import re
        for i, line in enumerate(lines, 1):
            nums = re.findall(r'(?<![a-zA-Z_#])\d{2,}(?![a-zA-Z_])', line)
            if nums and not line.strip().startswith(('#', '//')):
                suggestions.append(RefactoringSuggestion(
                    type="magic_number",
                    location=f"L{i}",
                    description=f"Magic numbers: {', '.join(nums[:3])}",
                    impact="Dificulta entendimento",
                    auto_applicable=True,
                    estimated_improvement=0.1,
                ))
        return suggestions[:5]
    
    def _detect_deep_nesting(self, lines: List[str]) -> List[RefactoringSuggestion]:
        suggestions = []
        depth = 0
        for i, line in enumerate(lines, 1):
            depth += line.count('{') - line.count('}')
            if depth > 4:
                suggestions.append(RefactoringSuggestion(
                    type="deep_nesting",
                    location=f"L{i}",
                    description=f"Nesting profundo (nível {depth})",
                    impact="Baixa legibilidade",
                    auto_applicable=False,
                    estimated_improvement=0.25,
                ))
        return suggestions[:3]
