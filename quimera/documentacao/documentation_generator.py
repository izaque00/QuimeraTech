# quimera/documentacao/documentation_generator.py
"""
Documentation Generator — Geração automática de documentação.

Gera docs a partir de docstrings, comentários e estrutura de código.

Uso:
    from quimera.documentacao.documentation_generator import DocumentationGenerator
    
    gen = DocumentationGenerator()
    docs = gen.generate_module_docs("/path/to/module")
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ModuleDoc:
    """Documentação de um módulo."""
    module_name: str
    description: str
    classes: List[Dict]
    functions: List[Dict]
    dependencies: List[str]
    examples: List[str]


@dataclass  
class APIDoc:
    """Documentação de API."""
    title: str
    version: str
    modules: List[ModuleDoc] = field(default_factory=list)
    index: Dict[str, str] = field(default_factory=dict)


class DocumentationGenerator:
    """Gerador de documentação automática."""
    
    def generate_module_docs(self, file_path: str) -> ModuleDoc:
        """Gera documentação para um módulo Python."""
        path = Path(file_path)
        content = path.read_text(errors="ignore")
        
        # Extrai docstring do módulo
        description = self._extract_docstring(content)
        
        # Extrai classes e funções
        classes = self._extract_classes(content)
        functions = self._extract_functions(content)
        
        # Dependências
        deps = self._extract_imports(content)
        
        return ModuleDoc(
            module_name=path.stem,
            description=description,
            classes=classes,
            functions=functions,
            dependencies=deps,
            examples=[],
        )
    
    def generate_api_docs(self, package_path: str) -> APIDoc:
        """Gera documentação completa de API para um pacote."""
        root = Path(package_path)
        modules = []
        index = {}
        
        for py_file in root.rglob("*.py"):
            if '__pycache__' in str(py_file):
                continue
            try:
                doc = self.generate_module_docs(str(py_file))
                modules.append(doc)
                index[doc.module_name] = str(py_file.relative_to(root))
            except Exception as e:
                logger.debug(f"Falha ao documentar {py_file}: {e}")
        
        return APIDoc(
            title=f"API Documentation — {root.name}",
            version="auto-generated",
            modules=modules,
            index=index,
        )
    
    def _extract_docstring(self, content: str) -> str:
        """Extrai docstring do módulo."""
        import re
        match = re.search(r'"""(.*?)"""', content, re.DOTALL)
        if match:
            return match.group(1).strip().split('\n')[0]
        return "No description"
    
    def _extract_classes(self, content: str) -> List[Dict]:
        """Extrai classes com docstrings."""
        import re
        classes = []
        pattern = r'class\s+(\w+)(?:\([^)]*\))?:\s*\n\s*"""([^"]*)"""'
        for match in re.finditer(pattern, content, re.DOTALL):
            classes.append({
                "name": match.group(1),
                "doc": match.group(2).strip().split('\n')[0],
            })
        return classes
    
    def _extract_functions(self, content: str) -> List[Dict]:
        """Extrai funções com docstrings."""
        import re
        funcs = []
        pattern = r'def\s+(\w+)\s*\([^)]*\)(?:\s*->.*?)?:\s*\n\s*"""([^"]*)"""'
        for match in re.finditer(pattern, content, re.DOTALL):
            funcs.append({
                "name": match.group(1),
                "doc": match.group(2).strip().split('\n')[0],
            })
        return funcs
    
    def _extract_imports(self, content: str) -> List[str]:
        """Extrai imports."""
        deps = []
        for line in content.split('\n'):
            if line.startswith('import ') or line.startswith('from '):
                deps.append(line.strip())
        return deps
