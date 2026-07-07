"""
Quimera Knowledge Indexer — Indexa TODO o código-fonte do Quimera.
Extrai: módulos, classes, funções, docstrings, imports, complexidade.
Gera: knowledge_base.json (estruturado) + rag_index.json (busca semântica).
"""
import os, re, json, ast
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime

@dataclass
class FunctionInfo:
    name: str
    signature: str = ""
    docstring: str = ""
    line_start: int = 0
    line_end: int = 0
    decorators: List[str] = field(default_factory=list)
    complexity: int = 0  # linhas de código

@dataclass  
class ClassInfo:
    name: str
    docstring: str = ""
    line_start: int = 0
    line_end: int = 0
    methods: List[FunctionInfo] = field(default_factory=list)
    bases: List[str] = field(default_factory=list)

@dataclass
class ModuleInfo:
    path: str
    name: str
    docstring: str = ""
    functions: List[FunctionInfo] = field(default_factory=list)
    classes: List[ClassInfo] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    total_lines: int = 0
    code_lines: int = 0
    complexity_score: int = 0
    purpose: str = ""  # inferido

class QuimeraKnowledgeIndexer:
    """Analisa e indexa todo o código Quimera."""
    
    def __init__(self, project_root: str):
        self.root = Path(project_root)
        self.modules: Dict[str, ModuleInfo] = {}
        self.global_index: Dict[str, Any] = {}
        
    def build(self) -> Dict[str, Any]:
        """Constrói a base de conhecimento completa."""
        py_files = sorted(self.root.rglob("*.py"))
        py_files = [f for f in py_files if '__pycache__' not in str(f)]
        
        print(f"📊 Indexando {len(py_files)} arquivos...")
        
        for i, fpath in enumerate(py_files):
            rel = str(fpath.relative_to(self.root))
            try:
                module = self._analyze_file(fpath, rel)
                self.modules[rel] = module
                if i % 50 == 0:
                    print(f"   {i}/{len(py_files)}: {rel}")
            except Exception as e:
                print(f"   ⚠️ {rel}: {e}")
        
        # Análise global
        self._build_global_index()
        self._infer_purposes()
        self._compute_cross_references()
        
        print(f"✅ Indexados: {len(self.modules)} módulos")
        print(f"   Funções: {sum(len(m.functions) for m in self.modules.values())}")
        print(f"   Classes: {sum(len(m.classes) for m in self.modules.values())}")
        
        return self.export()
    
    def _analyze_file(self, path: Path, rel: str) -> ModuleInfo:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            source = f.read()
        
        lines = source.split('\n')
        total = len(lines)
        code_lines = sum(1 for l in lines if l.strip() and not l.strip().startswith('#'))
        
        # AST parsing
        functions, classes, imports, docstring = [], [], [], ""
        try:
            tree = ast.parse(source)
            
            # Module docstring
            docstring = ast.get_docstring(tree) or ""
            
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.FunctionDef):
                    funcs = self._extract_function(node, lines)
                    functions.extend(funcs)
                elif isinstance(node, ast.ClassDef):
                    cinfo = self._extract_class(node, lines)
                    classes.append(cinfo)
                elif isinstance(node, ast.Import):
                    imports.extend(a.name for a in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imports.append(f"{node.module or ''}.{node.names[0].name if node.names else '*'}")
        except SyntaxError:
            # Fallback regex
            for i, l in enumerate(lines):
                if l.strip().startswith('def '):
                    name = l.strip()[4:].split('(')[0].strip()
                    functions.append(FunctionInfo(name=name, line_start=i+1))
                elif l.strip().startswith('class '):
                    name = l.strip()[6:].split('(')[0].split(':')[0].strip()
                    classes.append(ClassInfo(name=name, line_start=i+1))
                elif l.strip().startswith('import ') or l.strip().startswith('from '):
                    imports.append(l.strip())
        
        # Complexity
        complexity = sum(f.complexity for f in (sum([c.methods for c in classes], []) + functions))
        
        return ModuleInfo(
            path=rel, name=rel.replace('/', '.').replace('.py', ''),
            docstring=docstring,
            functions=functions, classes=classes,
            imports=imports[:30],
            total_lines=total, code_lines=code_lines,
            complexity_score=complexity or code_lines
        )
    
    def _extract_function(self, node: ast.FunctionDef, lines: List[str]) -> List[FunctionInfo]:
        funcs = []
        doc = ast.get_docstring(node) or ""
        sig = f"def {node.name}({self._format_args(node.args)})"
        decs = [self._format_decorator(d) for d in node.decorator_list]
        end = node.end_lineno or (node.lineno + len(node.body) * 2)
        funcs.append(FunctionInfo(
            name=node.name, signature=sig, docstring=doc,
            line_start=node.lineno, line_end=end,
            decorators=decs,
            complexity=max(1, end - node.lineno)
        ))
        return funcs
    
    def _extract_class(self, node: ast.ClassDef, lines: List[str]) -> ClassInfo:
        doc = ast.get_docstring(node) or ""
        bases = [self._format_base(b) for b in node.bases]
        methods = []
        for n in node.body:
            if isinstance(n, ast.FunctionDef):
                methods.extend(self._extract_function(n, lines))
        return ClassInfo(
            name=node.name, docstring=doc,
            line_start=node.lineno, line_end=node.end_lineno or node.lineno,
            methods=methods, bases=bases
        )
    
    def _format_args(self, args: ast.arguments) -> str:
        parts = []
        for a in args.args:
            annotation = f": {ast.unparse(a.annotation)}" if a.annotation else ""
            parts.append(a.arg + annotation)
        if args.vararg: parts.append(f"*{args.vararg.arg}")
        if args.kwarg: parts.append(f"**{args.kwarg.arg}")
        return ", ".join(parts)
    
    def _format_decorator(self, d) -> str:
        if isinstance(d, ast.Name): return f"@{d.id}"
        if isinstance(d, ast.Call) and isinstance(d.func, ast.Name): return f"@{d.func.id}(...)"
        return "@..."
    
    def _format_base(self, b) -> str:
        if isinstance(b, ast.Name): return b.id
        return ast.unparse(b) if hasattr(ast, 'unparse') else str(b)
    
    def _build_global_index(self):
        """Índice global: nome → módulo, para busca rápida."""
        idx = {"functions": {}, "classes": {}, "modules": {},
               "by_category": {}, "top_level_modules": []}
        
        for mod_path, mod in self.modules.items():
            idx["modules"][mod_path] = {
                "name": mod.name, "lines": mod.total_lines,
                "funcs": len(mod.functions), "classes": len(mod.classes),
                "doc": mod.docstring[:200]
            }
            
            for f in mod.functions:
                key = f.name.lower()
                if key not in idx["functions"]:
                    idx["functions"][key] = []
                idx["functions"][key].append({
                    "name": f.name, "module": mod_path,
                    "signature": f.signature, "doc": f.docstring[:150]
                })
            
            for c in mod.classes:
                key = c.name.lower()
                if key not in idx["classes"]:
                    idx["classes"][key] = []
                idx["classes"][key].append({
                    "name": c.name, "module": mod_path,
                    "doc": c.docstring[:150],
                    "methods": [m.name for m in c.methods]
                })
            
            # Categoriza
            parts = mod_path.split('/')
            if parts[0] not in idx["by_category"]:
                idx["by_category"][parts[0]] = []
            idx["by_category"][parts[0]].append(mod_path)
        
        # Top-level
        idx["top_level_modules"] = [
            m.path for m in self.modules.values()
            if m.path.count('/') == 1 and not m.path.startswith('_')
        ][:30]
        
        self.global_index = idx
    
    def _infer_purposes(self):
        """Inferência heurística do propósito de cada módulo."""
        keywords = {
            'pipeline': ['AutonomousPipeline', 'run', 'stages', 'repair', 'H1', 'H6'],
            'aegis': ['security', 'audit', 'malware', 'crypto', 'vulnerability'],
            'agent': ['agent', 'Agente', 'comando', 'missao', 'tarefa'],
            'memory': ['memory', 'cache', 'store', 'recall', 'memoria'],
            'api': ['server', 'API', 'FastAPI', 'endpoint', 'route'],
            'analysis': ['analyze', 'parser', 'ast', 'detect', 'static'],
            'validator': ['validate', 'test', 'check', 'assert', 'compile'],
            'evolution': ['genetic', 'evolve', 'fitness', 'mutation'],
            'plugin': ['plugin', 'extension', 'interface', 'hook'],
            'database': ['db', 'database', 'SQL', 'migration', 'schema'],
            'cli': ['cli', 'command', 'argparse', 'shell'],
            'config': ['config', 'settings', 'env', 'environment'],
            'tool': ['tool', 'utility', 'helper', 'util'],
        }
        
        for mod in self.modules.values():
            all_text = (mod.docstring + " " + 
                       " ".join(mod.imports) + " " +
                       " ".join(f.name for f in mod.functions) + " " +
                       " ".join(c.name for c in mod.classes)).lower()
            
            scores = {}
            for category, kws in keywords.items():
                scores[category] = sum(1 for kw in kws if kw.lower() in all_text)
            
            if scores:
                best = max(scores, key=scores.get)
                if scores[best] > 0:
                    mod.purpose = best
    
    def _compute_cross_references(self):
        """Calcula referências cruzadas entre módulos."""
        xref = {}
        for mod_path, mod in self.modules.items():
            for imp in mod.imports:
                base = imp.split('.')[0]
                for other_path in self.modules:
                    if other_path != mod_path and base in other_path.replace('.py','').split('/')[-1]:
                        key = f"{mod_path} → {other_path}"
                        if key not in xref: xref[key] = 0
                        xref[key] += 1
        
        self.global_index["cross_references"] = dict(
            sorted(xref.items(), key=lambda x: -x[1])[:100]
        )
    
    def export(self) -> Dict[str, Any]:
        """Exporta base de conhecimento completa."""
        return {
            "metadata": {
                "generated": datetime.now().isoformat(),
                "project": "Quimera MarkX v5.4",
                "total_modules": len(self.modules),
                "total_functions": sum(len(m.functions) for m in self.modules.values()),
                "total_classes": sum(len(m.classes) for m in self.modules.values()),
                "total_lines": sum(m.total_lines for m in self.modules.values()),
            },
            "modules": {k: asdict(v) for k, v in self.modules.items()},
            "global_index": self.global_index,
        }
    
    def generate_system_prompt(self) -> str:
        """Gera system prompt com conhecimento do Quimera."""
        meta = self.export()["metadata"]
        
        # Top modules by complexity
        top_modules = sorted(
            self.modules.values(),
            key=lambda m: m.complexity_score, reverse=True
        )[:20]
        
        # Key functions
        key_funcs = []
        for mod in top_modules[:10]:
            for f in mod.functions[:3]:
                key_funcs.append(f"   {mod.name}.{f.name}() — {f.docstring[:80]}")
        
        # Module categories
        cats = self.global_index.get("by_category", {})
        cat_desc = "\n".join(
            f"   📁 {cat}/ ({len(mods)} arquivos)" 
            for cat, mods in sorted(cats.items())
        )
        
        prompt = f"""VOCE E O QUIMERA MARKX v5.4 — Plataforma Autonoma de Engenharia de Codigo.

═══════════ CONHECIMENTO DO SISTEMA ═══════════
{meta['total_modules']} módulos | {meta['total_functions']} funções | {meta['total_classes']} classes | {meta['total_lines']} linhas

ESTRUTURA DO PROJETO:
{cat_desc}

MÓDULOS PRINCIPAIS:
{chr(10).join(f"   • {m.name} ({m.total_lines} linhas) — {m.purpose or m.docstring[:80]}" for m in top_modules[:15])}

FUNÇÕES-CHAVE:
{chr(10).join(key_funcs[:15])}

═══════════ FERRAMENTAS ═══════════
🔧 pipeline  — Pipeline H1-H6: detecção → patches → validação → evolução
🛡️ audit     — Aegis Security Core: vulnerabilidades, malware, criptografia
📊 health    — Diagnóstico completo via get_system_status()
🔍 explain   — Análise de código, pastas, arquitetura
🔎 search    — Busca arquivos por nome no projeto e dispositivo
🔑 register  — Cadastro de chaves API (Groq, OpenAI, Gemini, etc)
💬 chat      — Conversa livre

═══════════ REGRAS ═══════════
1. Voce NAO simula — voce EXECUTA via orquestrador nativo
2. "corrige/arruma X" → pipeline (orquestrador real)
3. "audita/seguranca X" → audit (Aegis nativo)
4. "como esta/sistema" → health
5. "analisa/explique X" → explain
6. target = EXATAMENTE o que o usuario falou
7. Responda em portugues do Brasil

JSON: {{"action":"...","target":"...","params":{{}},"explanation":"..."}}"""
        
        return prompt
    
    def generate_rag_context(self, query: str, max_chars: int = 3000) -> str:
        """Busca contexto relevante (RAG) — funções, classes, módulos, docstrings."""
        query_lower = query.lower()
        query_words = [w for w in query_lower.split() if len(w) > 2]
        relevant = []
        seen = set()

        # 1. Busca exata em nomes de funções e classes
        for func_name, entries in self.global_index.get("functions", {}).items():
            if func_name in query_lower:
                for e in entries[:2]:
                    key = f"f:{e['name']}"
                    if key not in seen:
                        seen.add(key)
                        relevant.append(f"🟢 {e['name']}() em {e['module']}: {e['doc']}")

        for cls_name, entries in self.global_index.get("classes", {}).items():
            if cls_name.lower() in query_lower:
                for e in entries[:2]:
                    key = f"c:{e['name']}"
                    if key not in seen:
                        seen.add(key)
                        relevant.append(f"🔵 {e['name']} em {e['module']}: {e['doc']}")

        # 2. Busca por palavras da query em nomes de funções/classes
        for func_name, entries in self.global_index.get("functions", {}).items():
            for w in query_words:
                if w in func_name:
                    for e in entries[:2]:
                        key = f"fw:{e['name']}"
                        if key not in seen:
                            seen.add(key)
                            relevant.append(f"🟢 {e['name']}() em {e['module']}: {e['doc']}")

        for cls_name, entries in self.global_index.get("classes", {}).items():
            for w in query_words:
                if w in cls_name.lower():
                    for e in entries[:2]:
                        key = f"cw:{e['name']}"
                        if key not in seen:
                            seen.add(key)
                            relevant.append(f"🔵 {e['name']} em {e['module']}: {e['doc']}")

        # 3. Busca em módulos
        for mod_path, info in self.global_index.get("modules", {}).items():
            for w in query_words:
                if w in mod_path.lower():
                    key = f"m:{mod_path}"
                    if key not in seen:
                        seen.add(key)
                        relevant.append(f"📁 {mod_path}: {info['doc'][:120]}")

        # 4. Busca em docstrings (mais profunda)
        for mod_path, mod in self.modules.items():
            mod_text = (mod.docstring or "").lower()
            for w in query_words:
                if w in mod_text:
                    key = f"md:{mod_path}"
                    if key not in seen:
                        seen.add(key)
                        relevant.append(f"📁 {mod.name}: {mod.docstring[:120]}")
                    break
            
            for f in mod.functions:
                f_text = (f.docstring or "").lower()
                for w in query_words:
                    if w in f_text:
                        key = f"fd:{mod.name}.{f.name}"
                        if key not in seen:
                            seen.add(key)
                            relevant.append(f"🟢 {mod.name}.{f.name}(): {f.docstring[:120]}")
                        break

            for cls in mod.classes:
                cls_text = (cls.docstring or "").lower()
                for w in query_words:
                    if w in cls_text:
                        key = f"cd:{mod.name}.{cls.name}"
                        if key not in seen:
                            seen.add(key)
                            relevant.append(f"🔵 {mod.name}.{cls.name}: {cls.docstring[:120]}")
                        break

        if not relevant:
            top = sorted(self.modules.values(), key=lambda m: m.complexity_score, reverse=True)[:8]
            relevant = [f"📁 {m.name} ({m.total_lines} linhas): {m.docstring[:100] or '(sem doc)'}" for m in top]

        return "\n".join(relevant[:25])[:max_chars]


# ═══════════════ EXECUÇÃO ═══════════════
if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    indexer = QuimeraKnowledgeIndexer(root)
    data = indexer.build()
    
    # Salva
    out_dir = Path(root) / "quimera" / "cognition"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    with open(out_dir / "quimera_knowledge.json", "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Salvo: {out_dir / 'quimera_knowledge.json'}")
    
    prompt = indexer.generate_system_prompt()
    with open(out_dir / "quimera_system_prompt.txt", "w") as f:
        f.write(prompt)
    print(f"💾 System prompt: {out_dir / 'quimera_system_prompt.txt'}")
