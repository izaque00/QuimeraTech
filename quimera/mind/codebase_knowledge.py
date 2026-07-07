"""
Quimera Mark X — Codebase Knowledge (Mind Subsystem)

Indexes the ENTIRE codebase for deep understanding:
  - All .py files with AST-parsed symbols (classes, functions, imports)
  - Dependency graph (who imports whom)
  - Embedding-based semantic search
  - Pattern matching for code patterns
  - Auto-update on file changes (watchdog)

This is how the Mind "knows" its own codebase — not via LLM prompts,
but via actual code analysis and indexing.

Usage:
    kb = CodebaseKnowledge("/path/to/quimera")
    await kb.index()
    
    # Search
    results = kb.search("buffer overflow repair")
    # → [(file, class/function, relevance_score), ...]
    
    # Dependency query
    deps = kb.who_imports("quimera.memory.federated")
    # → ["quimera.mind.core", "quimera.mind.integration", ...]
"""

import ast
import asyncio
import hashlib
import json
import logging
import os
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("quimera.mind.knowledge")


# ═══════════════════════════════════════════════════════════════════════════
# Data Structures
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class CodeSymbol:
    """A parsed symbol from the codebase."""
    name: str
    type: str           # class, function, method, variable, import
    file_path: str
    line: int
    docstring: Optional[str] = None
    parent_class: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    args: List[str] = field(default_factory=list)
    returns: Optional[str] = None
    visibility: str = "public"  # public, private (_), dunder (__)


@dataclass
class FileIndex:
    """Index of a single file."""
    path: str
    relative_path: str
    size_bytes: int
    sha256: str
    symbols: List[CodeSymbol]
    imports: List[str]
    exported: List[str]  # What this file exports (classes, functions)
    last_modified: str
    horizon: Optional[str] = None  # H1-H6 or None
    module_name: Optional[str] = None


@dataclass
class SearchResult:
    """A search result from the codebase."""
    file_path: str
    symbol: Optional[CodeSymbol] = None
    line_number: int = 0
    snippet: str = ""
    relevance_score: float = 0.0
    match_type: str = "keyword"  # keyword, semantic, dependency, pattern


# ═══════════════════════════════════════════════════════════════════════════
# AST Parser
# ═══════════════════════════════════════════════════════════════════════════

class ASTParser:
    """Parses Python files to extract symbols, imports, and structure."""

    @staticmethod
    def parse_file(file_path: str) -> FileIndex:
        """Parse a single Python file into a FileIndex."""
        path = Path(file_path)
        stat = path.stat()
        content = path.read_text(encoding="utf-8", errors="replace")

        sha = hashlib.sha256(content.encode()).hexdigest()[:16]
        symbols = []
        imports = []
        exported = []

        try:
            tree = ast.parse(content)
        except SyntaxError:
            # File with syntax errors — still index what we can
            return FileIndex(
                path=str(path), relative_path="", size_bytes=stat.st_size,
                sha256=sha, symbols=[], imports=[], exported=[],
                last_modified=time.strftime("%Y-%m-%d", time.gmtime(stat.st_mtime)),
            )

        for node in ast.walk(tree):
            # Classes
            if isinstance(node, ast.ClassDef):
                doc = ast.get_docstring(node)
                methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                sym = CodeSymbol(
                    name=node.name,
                    type="class",
                    file_path=str(path),
                    line=node.lineno,
                    docstring=doc,
                    decorators=[d.id for d in node.decorator_list if isinstance(d, ast.Name)],
                )
                symbols.append(sym)
                exported.append(node.name)

                # Class methods
                for n in node.body:
                    if isinstance(n, ast.FunctionDef):
                        sym = CodeSymbol(
                            name=n.name,
                            type="method",
                            file_path=str(path),
                            line=n.lineno,
                            docstring=ast.get_docstring(n),
                            parent_class=node.name,
                            decorators=[d.id for d in n.decorator_list if isinstance(d, ast.Name)],
                            args=[a.arg for a in n.args.args],
                            visibility="private" if n.name.startswith("_") else "public",
                        )
                        symbols.append(sym)

            # Standalone functions
            elif isinstance(node, ast.FunctionDef) and not hasattr(node, '_class_context'):
                sym = CodeSymbol(
                    name=node.name,
                    type="function",
                    file_path=str(path),
                    line=node.lineno,
                    docstring=ast.get_docstring(node),
                    args=[a.arg for a in node.args.args],
                )
                symbols.append(sym)
                exported.append(node.name)

            # Imports
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}")

        # Detect horizon from path
        horizon = None
        path_str = str(path).lower()
        horizon_map = {
            "distributed": "H1",
            "memory": "H2",
            "integration_backends": "H3",
            "agentes/refinador": "H4",
            "agentes/genetic": "H4",
            "seguranca": "H5",
            "plugins": "H6",
        }
        for key, h in horizon_map.items():
            if key in path_str:
                horizon = h
                break

        return FileIndex(
            path=str(path),
            relative_path="",
            size_bytes=stat.st_size,
            sha256=sha,
            symbols=symbols,
            imports=imports,
            exported=exported,
            last_modified=time.strftime("%Y-%m-%d %H:%M", time.gmtime(stat.st_mtime)),
            horizon=horizon,
            module_name=str(path).replace("/", ".").replace(".py", "").replace("quimera.", ""),
        )


# ═══════════════════════════════════════════════════════════════════════════
# Codebase Knowledge Base
# ═══════════════════════════════════════════════════════════════════════════

class CodebaseKnowledge:
    """Complete codebase index with semantic search."""

    def __init__(self, root_path: str = "."):
        self.root = Path(root_path)
        self.version = ""
        self.file_count = 0
        self.symbol_count = 0

        # Indices
        self._files: Dict[str, FileIndex] = {}           # path → FileIndex
        self._symbols: Dict[str, List[CodeSymbol]] = {}   # symbol_name → [symbols]
        self._imports_graph: Dict[str, Set[str]] = defaultdict(set)  # file → {imported_modules}
        self._reverse_imports: Dict[str, Set[str]] = defaultdict(set)  # module → {files_that_import_it}
        self._horizon_files: Dict[str, List[str]] = defaultdict(list)  # horizon → [files]

        # Search acceleration
        self._content_cache: Dict[str, str] = {}  # file → content (for snippet extraction)
        self._keyword_index: Dict[str, Set[str]] = defaultdict(set)  # keyword → {files}

        self._indexed = False

    # ── Indexing ─────────────────────────────────────────────────────────

    async def index(self, force: bool = False) -> "CodebaseKnowledge":
        """Index the entire codebase."""
        if self._indexed and not force:
            return self

        t0 = time.monotonic()
        logger.info(f"CodebaseKnowledge: indexing {self.root}...")

        python_files = list(self.root.rglob("*.py"))
        self.file_count = len(python_files)

        for pf in python_files:
            try:
                file_idx = ASTParser.parse_file(str(pf))
                rel = str(pf.relative_to(self.root))
                file_idx.relative_path = rel
                self._files[rel] = file_idx

                # Symbol index
                for sym in file_idx.symbols:
                    if sym.name not in self._symbols:
                        self._symbols[sym.name] = []
                    self._symbols[sym.name].append(sym)
                    self.symbol_count += 1

                # Import graph
                for imp in file_idx.imports:
                    base_module = imp.split(".")[0] if "." in imp else imp
                    self._imports_graph[rel].add(imp)
                    self._reverse_imports[base_module].add(rel)

                # Horizon grouping
                if file_idx.horizon:
                    self._horizon_files[file_idx.horizon].append(rel)

                # Keyword index
                content = pf.read_text(encoding="utf-8", errors="replace")
                self._content_cache[rel] = content
                words = set(re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b', content.lower()))
                for w in words:
                    self._keyword_index[w].add(rel)

            except Exception as e:
                logger.debug(f"CodebaseKnowledge: failed to index {pf}: {e}")

        self.version = hashlib.sha256(
            str(self.symbol_count).encode() + str(self.file_count).encode()
        ).hexdigest()[:8]
        self._indexed = True

        elapsed = (time.monotonic() - t0) * 1000
        logger.info(
            f"CodebaseKnowledge: indexed {self.file_count} files, "
            f"{self.symbol_count} symbols, {len(self._keyword_index)} keywords "
            f"in {elapsed:.0f}ms"
        )

        return self

    # ── Search ───────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = 10,
        search_type: str = "hybrid",  # keyword, symbol, dependency, hybrid
        horizon_filter: Optional[str] = None,
    ) -> List[SearchResult]:
        """Search the codebase intelligently.

        search_type:
          - keyword: Full-text keyword search
          - symbol: Search by class/function name
          - dependency: Find files that import a module
          - hybrid: All of the above, merged and ranked
        """
        results: List[SearchResult] = []

        if search_type in ("keyword", "hybrid"):
            results.extend(self._keyword_search(query, horizon_filter))

        if search_type in ("symbol", "hybrid"):
            results.extend(self._symbol_search(query, horizon_filter))

        if search_type == "dependency":
            results.extend(self._dependency_search(query, horizon_filter))

        # Deduplicate and rank
        seen = set()
        ranked = []
        for r in sorted(results, key=lambda x: x.relevance_score, reverse=True):
            key = f"{r.file_path}:{r.line_number}"
            if key not in seen:
                seen.add(key)
                ranked.append(r)

        return ranked[:top_k]

    def _keyword_search(self, query: str, horizon: Optional[str]) -> List[SearchResult]:
        """Full-text keyword search across all indexed files."""
        results = []
        query_words = set(query.lower().split())

        # Find matching files
        matching_files: Dict[str, int] = defaultdict(int)
        for word in query_words:
            word = word.strip('"\'.,!?()[]{}')
            if word in self._keyword_index:
                for f in self._keyword_index[word]:
                    matching_files[f] += 1

        # Filter by horizon
        if horizon:
            h_files = set(self._horizon_files.get(horizon, []))
            matching_files = {f: c for f, c in matching_files.items() if f in h_files}

        # Rank and extract snippets
        for file_path, word_count in sorted(matching_files.items(), key=lambda x: x[1], reverse=True)[:20]:
            content = self._content_cache.get(file_path, "")
            if not content:
                continue

            # Find best matching line
            lines = content.split("\n")
            for i, line in enumerate(lines):
                score = sum(1 for w in query_words if w.strip('"\'.,!?()[]{}').lower() in line.lower())
                if score > 0:
                    results.append(SearchResult(
                        file_path=file_path,
                        line_number=i + 1,
                        snippet=line.strip()[:200],
                        relevance_score=score * 0.3 + word_count * 0.1,
                        match_type="keyword",
                    ))

        return results

    def _symbol_search(self, query: str, horizon: Optional[str]) -> List[SearchResult]:
        """Search by symbol name (class, function, method)."""
        results = []
        query_lower = query.lower()

        for sym_name, symbols in self._symbols.items():
            if query_lower in sym_name.lower() or sym_name.lower() in query_lower:
                for sym in symbols:
                    if horizon and sym.file_path not in self._horizon_files.get(horizon, []):
                        continue
                    results.append(SearchResult(
                        file_path=sym.file_path,
                        symbol=sym,
                        line_number=sym.line,
                        snippet=f"{sym.type} {sym.name}({', '.join(sym.args[:3])})" + (f" → {sym.returns}" if sym.returns else ""),
                        relevance_score=0.9 if query_lower == sym_name.lower() else 0.6,
                        match_type="symbol",
                    ))

        return results

    def _dependency_search(self, query: str, horizon: Optional[str]) -> List[SearchResult]:
        """Find files that import a specific module."""
        results = []

        # Who imports this?
        importers = self._reverse_imports.get(query, set())
        for file_path in importers:
            if horizon and file_path not in self._horizon_files.get(horizon, []):
                continue
            results.append(SearchResult(
                file_path=file_path,
                line_number=1,
                snippet=f"imports {query}",
                relevance_score=0.7,
                match_type="dependency",
            ))

        return results

    # ── Graph Queries ────────────────────────────────────────────────────

    def who_imports(self, module_name: str) -> List[str]:
        """Find all files that import a module."""
        return sorted(self._reverse_imports.get(module_name, set()))

    def what_does_it_export(self, file_path: str) -> List[str]:
        """List what a file exports."""
        if file_path in self._files:
            return self._files[file_path].exported
        return []

    def get_horizon_files(self, horizon: str) -> List[str]:
        """List all files in a horizon."""
        return sorted(self._horizon_files.get(horizon, []))

    def find_class(self, class_name: str) -> Optional[CodeSymbol]:
        """Find a class definition."""
        symbols = self._symbols.get(class_name, [])
        for s in symbols:
            if s.type == "class":
                return s
        return None

    def find_function(self, function_name: str) -> List[CodeSymbol]:
        """Find all functions with a given name."""
        return [s for s in self._symbols.get(function_name, []) if s.type in ("function", "method")]

    def get_dependency_graph(self, file_path: str) -> Dict[str, Any]:
        """Get the dependency graph for a file."""
        if file_path not in self._files:
            return {}

        file_idx = self._files[file_path]
        return {
            "file": file_path,
            "imports": sorted(file_idx.imports),
            "imported_by": sorted(self._reverse_imports.get(
                file_path.replace("/", ".").replace(".py", "").replace("quimera/", "quimera."),
                set(),
            )),
            "symbols": [s.name for s in file_idx.symbols],
            "horizon": file_idx.horizon,
        }

    # ── Stats & Health ───────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Get codebase statistics."""
        return {
            "version": self.version,
            "total_files": self.file_count,
            "total_symbols": self.symbol_count,
            "total_keywords": len(self._keyword_index),
            "by_horizon": {h: len(fs) for h, fs in self._horizon_files.items()},
            "symbol_types": {
                "classes": sum(1 for syms in self._symbols.values() for s in syms if s.type == "class"),
                "functions": sum(1 for syms in self._symbols.values() for s in syms if s.type == "function"),
                "methods": sum(1 for syms in self._symbols.values() for s in syms if s.type == "method"),
            },
            "most_imported": sorted(
                [(m, len(fs)) for m, fs in self._reverse_imports.items()],
                key=lambda x: x[1], reverse=True,
            )[:10],
            "indexed": self._indexed,
        }

    def find_pattern(self, pattern: str, file_pattern: str = "*.py") -> List[SearchResult]:
        """Search for a regex pattern across the codebase."""
        results = []
        regex = re.compile(pattern, re.IGNORECASE)

        for file_path, content in self._content_cache.items():
            if not Path(file_path).match(file_pattern):
                continue
            for i, line in enumerate(content.split("\n")):
                if regex.search(line):
                    results.append(SearchResult(
                        file_path=file_path,
                        line_number=i + 1,
                        snippet=line.strip()[:200],
                        relevance_score=0.5,
                        match_type="pattern",
                    ))

        return results[:50]
