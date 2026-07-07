"""
Quimera Mark X — Full Codebase Knowledge (Mind Enhancement)

Extends CodebaseKnowledge to index ALL project files, not just .py:
  - Dockerfiles, docker-compose.yml, CI/CD (.github/workflows/*.yml)
  - Configuration (.json, .toml, .ini, .cfg)
  - Documentation (.md, .rst, .txt)
  - Scripts (.sh, .bash)
  - Manifest / metadata files

This gives the Mind complete awareness of the ENTIRE project,
not just the Python code.

Usage:
    full_kb = FullCodebaseKnowledge("/path/to/project")
    await full_kb.index()
    
    # Now the Mind knows about Docker, CI/CD, docs, configs too
    results = full_kb.search("docker redis port")
"""

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("quimera.mind.full_knowledge")


@dataclass
class UniversalFileIndex:
    """Index of any file type in the project."""
    path: str
    relative_path: str
    type: str           # python, docker, yaml, json, markdown, config, script, other
    size_bytes: int
    lines: int
    content_preview: str  # First 500 chars
    keywords: List[str]
    horizon: Optional[str] = None
    purpose: str = ""   # Inferred purpose (e.g., "CI/CD pipeline", "API server config")


# ═══════════════════════════════════════════════════════════════════════════
# File Type Classifier
# ═══════════════════════════════════════════════════════════════════════════

class FileClassifier:
    """Classifies any project file by type and purpose."""

    TYPE_MAP = {
        ".py": "python",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".json": "json",
        ".toml": "toml",
        ".ini": "config",
        ".cfg": "config",
        ".conf": "config",
        ".md": "markdown",
        ".rst": "documentation",
        ".txt": "documentation",
        ".sh": "script",
        ".bash": "script",
        ".dockerfile": "docker",
        ".dockerignore": "docker",
        ".gitignore": "config",
        ".env": "config",
        ".sql": "database",
        ".db": "database",
    }

    PURPOSE_PATTERNS = {
        r'(?i)docker': "Container configuration",
        r'(?i)docker-compose': "Orchestration configuration",
        r'(?i)ci[.-]?\s*yml|workflows': "CI/CD pipeline",
        r'(?i)readme': "Project documentation",
        r'(?i)requirements': "Dependency specification",
        r'(?i)alembic': "Database migration config",
        r'(?i)manifesto': "Project manifest / vision",
        r'(?i)pyproject': "Python project metadata",
        r'(?i)\.env': "Environment variables",
        r'(?i)migration': "Database migration",
        r'(?i)test': "Test file",
        r'(?i)makefile': "Build automation",
    }

    @classmethod
    def classify(cls, file_path: str) -> UniversalFileIndex:
        path = Path(file_path)
        ext = path.suffix.lower()
        name = path.name.lower()

        file_type = cls.TYPE_MAP.get(ext, "other")

        # Special cases
        if name == "dockerfile" or name.startswith("dockerfile."):
            file_type = "docker"
        elif name == "makefile":
            file_type = "script"

        # Infer purpose
        purpose = ""
        for pattern, desc in cls.PURPOSE_PATTERNS.items():
            if re.search(pattern, name) or re.search(pattern, str(path)):
                purpose = desc
                break

        return file_type, purpose


# ═══════════════════════════════════════════════════════════════════════════
# Full Codebase Knowledge
# ═══════════════════════════════════════════════════════════════════════════

class FullCodebaseKnowledge:
    """Indexes ALL project files for complete awareness."""

    def __init__(self, root_path: str = "."):
        self.root = Path(root_path)
        self.version = ""
        self.file_count = 0
        self.total_lines = 0

        # Indices
        self._files: Dict[str, UniversalFileIndex] = {}
        self._keyword_index: Dict[str, Set[str]] = defaultdict(set)
        self._by_type: Dict[str, List[str]] = defaultdict(list)
        self._by_purpose: Dict[str, List[str]] = defaultdict(list)

        # File types to index (everything except binaries)
        self._index_extensions = {
            ".py", ".yml", ".yaml", ".json", ".toml", ".ini", ".cfg", ".conf",
            ".md", ".rst", ".txt", ".sh", ".bash", ".sql",
            ".dockerfile", ".dockerignore", ".gitignore", ".env",
        }
        self._index_names = {
            "dockerfile", "makefile", "docker-compose.yml", "docker-compose.yaml",
            "pyproject.toml", "alembic.ini", "requirements.txt",
            "manifesto_quimera.json",
        }

        self._indexed = False

    async def index(self) -> "FullCodebaseKnowledge":
        t0 = time.monotonic()
        logger.info(f"FullCodebaseKnowledge: indexing ALL files in {self.root}...")

        for file_path in self.root.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix == ".pyc" or file_path.suffix == ".pyo":
                continue
            if "__pycache__" in str(file_path):
                continue
            if file_path.suffix == ".db" or file_path.name.endswith(".db"):
                continue  # Skip database files

            name = file_path.name.lower()
            ext = file_path.suffix.lower()

            # Only index recognized types
            if ext not in self._index_extensions and name not in self._index_names:
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            rel = str(file_path.relative_to(self.root))
            file_type, purpose = FileClassifier.classify(str(file_path))

            # Extract keywords
            keywords = self._extract_keywords(content, file_type)

            # Preview
            preview = content[:500]

            # Horizon detection from path
            horizon = self._detect_horizon(rel)

            entry = UniversalFileIndex(
                path=str(file_path),
                relative_path=rel,
                type=file_type,
                size_bytes=file_path.stat().st_size,
                lines=content.count("\n") + 1,
                content_preview=preview,
                keywords=keywords,
                horizon=horizon,
                purpose=purpose,
            )

            self._files[rel] = entry
            self._by_type[file_type].append(rel)
            if purpose:
                self._by_purpose[purpose].append(rel)

            for kw in keywords:
                self._keyword_index[kw].add(rel)

            self.file_count += 1
            self.total_lines += entry.lines

        self.version = hex(hash(str(self.file_count) + str(self.total_lines)))[:8]
        self._indexed = True

        elapsed = (time.monotonic() - t0) * 1000
        logger.info(
            f"FullCodebaseKnowledge: {self.file_count} files ({self.total_lines} lines) "
            f"indexed in {elapsed:.0f}ms"
        )
        logger.info(f"  By type: {dict((k, len(v)) for k, v in self._by_type.items())}")

        return self

    def _extract_keywords(self, content: str, file_type: str) -> List[str]:
        """Extract meaningful keywords from any file type."""
        keywords = []

        if file_type == "python":
            # Class names, function names, imports
            words = re.findall(r'(?:class|def)\s+(\w+)', content)
            keywords.extend(words)
            imports = re.findall(r'(?:import|from)\s+(\w+)', content)
            keywords.extend(imports)

        elif file_type in ("yaml", "docker"):
            # Keys and important values
            keys = re.findall(r'^(\w[\w-]*):', content, re.MULTILINE)
            keywords.extend(keys)
            images = re.findall(r'image:\s*"?(\S+)"?', content)
            keywords.extend(images)
            ports = re.findall(r'"(\d+:\d+)"', content)
            keywords.extend(ports)

        elif file_type == "json":
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    keywords.extend(data.keys())
                elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                    keywords.extend(data[0].keys())
            except json.JSONDecodeError:
                pass

        elif file_type in ("markdown", "documentation"):
            # Headers and code blocks
            headers = re.findall(r'^#+\s+(.+)$', content, re.MULTILINE)
            keywords.extend([h.strip() for h in headers])
            # Also technical terms
            tech_terms = re.findall(r'\b(?:docker|redis|api|rest|websocket|postgres|sqlite|sandbox|kernel|llm|agent|repair)\b', content, re.IGNORECASE)
            keywords.extend(tech_terms)

        elif file_type == "script":
            # Commands and variables
            commands = re.findall(r'\b(\w+)\s*=', content)
            keywords.extend(commands)
            tools = re.findall(r'\b(python|pip|docker|git|uvicorn|gunicorn|redis|curl)\b', content)
            keywords.extend(tools)

        elif file_type == "config":
            # Sections and keys
            sections = re.findall(r'^\[(\w+)\]', content, re.MULTILINE)
            keywords.extend(sections)
            keys = re.findall(r'^(\w+)\s*=', content, re.MULTILINE)
            keywords.extend(keys)

        # Always extract general meaningful words
        general = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]{3,}\b', content)
        # Filter common words
        stopwords = {"the", "and", "for", "that", "this", "with", "from", "have", "been", "were", "they", "their"}
        keywords.extend([w.lower() for w in general if w.lower() not in stopwords])

        return list(set(keywords))[:100]  # Cap at 100 keywords per file

    def _detect_horizon(self, rel_path: str) -> Optional[str]:
        rel = rel_path.lower()
        if "distributed" in rel: return "H1"
        if "memory" in rel: return "H2"
        if "integration_backends" in rel or "z3" in rel or "ebpf" in rel: return "H3"
        if "agentes" in rel and ("genetic" in rel or "coevolution" in rel or "refinador" in rel): return "H4"
        if "seguranca" in rel or "red_team" in rel or "fuzzing" in rel or "cve" in rel: return "H5"
        if "plugins" in rel or "multi_lang" in rel: return "H6"
        if "mind" in rel: return "Mind"
        if "db" in rel: return "DB"
        return None

    # ── Search ───────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 10, file_type: Optional[str] = None) -> List[Dict]:
        """Search across ALL file types."""
        query_words = set(query.lower().split())
        results = []

        for word in query_words:
            word = word.strip('"\'.,!?()[]{}:;')
            if word in self._keyword_index:
                for rel in self._keyword_index[word]:
                    entry = self._files.get(rel)
                    if not entry:
                        continue
                    if file_type and entry.type != file_type:
                        continue
                    score = sum(1 for w in query_words if w in entry.keywords)
                    results.append({
                        "file": rel,
                        "type": entry.type,
                        "lines": entry.lines,
                        "horizon": entry.horizon,
                        "purpose": entry.purpose,
                        "preview": entry.content_preview[:200],
                        "relevance": score,
                    })

        # Deduplicate and sort
        seen = set()
        unique = []
        for r in sorted(results, key=lambda x: x["relevance"], reverse=True):
            if r["file"] not in seen:
                seen.add(r["file"])
                unique.append(r)

        return unique[:top_k]

    def get_files_by_type(self, file_type: str) -> List[str]:
        return sorted(self._by_type.get(file_type, []))

    def get_files_by_purpose(self, purpose: str) -> List[str]:
        return sorted(self._by_purpose.get(purpose, []))

    def get_project_summary(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "total_files": self.file_count,
            "total_lines": self.total_lines,
            "by_type": {t: len(fs) for t, fs in self._by_type.items()},
            "by_purpose": {p: len(fs) for p, fs in self._by_purpose.items()},
            "horizons": {},
        }
