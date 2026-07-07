"""
Project Intelligence — Modelo Mental do Projeto (completo).

Analisa deterministicamente um projeto e constrói um ProjectContext tipado.
Usa ProjectContext (não dicionários) como saída.
"""
import json, logging, os, re
from pathlib import Path
from typing import List, Tuple

from quimera.cognition.project_context import (
    ProjectContext, ComponentInfo, DependencyInfo, Risk, RiskLevel,
    ProjectHealth, ArchitecturePattern, create_empty_context,
)

logger = logging.getLogger("quimera.project_intelligence")


class ProjectIntelligence:
    def __init__(self, max_files=500, max_lines_per_file=1000):
        self.max_files = max_files
        self.max_lines_per_file = max_lines_per_file
    
    def analyze(self, project_path: str) -> ProjectContext:
        path = Path(project_path).resolve()
        ctx = create_empty_context(project_path)
        if not path.exists():
            return ctx
        
        ctx.primary_language = self._detect_language(path)
        ctx.frameworks = self._detect_frameworks(path, ctx.primary_language)
        ctx.build_system = self._detect_build_system(path, ctx.primary_language)
        ctx.package_manager = self._detect_package_manager(path, ctx.primary_language)
        ctx.purpose = self._extract_purpose(path)
        ctx.domain = self._infer_domain(ctx.purpose, ctx.project_name)
        ctx.source_dirs = self._find_source_dirs(path, ctx.primary_language)
        ctx.test_dirs = self._find_test_dirs(path)
        ctx.config_files = self._find_config_files(path)
        ctx.entry_point = self._find_entry_point(path, ctx.primary_language)
        ctx.file_count, ctx.total_lines = self._count_files_and_lines(path, ctx.primary_language)
        ctx.architecture = ArchitecturePattern(self._infer_architecture(path, ctx.primary_language))
        ctx.dependencies = self._analyze_dependencies(path, ctx.primary_language)
        ctx.components = self._build_knowledge_graph(path, ctx.primary_language)
        ctx.data_flows = self._infer_data_flows(ctx)
        ctx.has_tests = bool(ctx.test_dirs) or self._has_test_files(path, ctx.primary_language)
        ctx.has_linting = self._has_linting(path, ctx.primary_language)
        ctx.has_type_checking = self._has_type_checking(path, ctx.primary_language)
        ctx.has_ci = self._has_ci(path)
        ctx.has_docker = self._has_docker(path)
        ctx.has_docs = (path / "README.md").exists() or (path / "docs").exists()
        ctx.health_score = self._calculate_health(ctx)
        ctx.health = self._classify_health(ctx.health_score)
        ctx.risks = self._detect_risks(path, ctx)
        
        logger.info(f"Project model built: {ctx.project_name} ({ctx.primary_language}, "
                     f"{len(ctx.components)} components, {ctx.file_count} files, "
                     f"health={ctx.health_score:.0f}/100, risks={len(ctx.risks)})")
        return ctx
    
    # ── Detectors ──
    def _detect_language(self, p):
        ind = {"python":["pyproject.toml","setup.py","requirements.txt","Pipfile"],
               "javascript":["package.json"],"typescript":["tsconfig.json"],
               "rust":["Cargo.toml"],"go":["go.mod"],"java":["pom.xml","build.gradle"]}
        for lang, fs in ind.items():
            for f in fs:
                if (p/f).exists():
                    if lang=="javascript" and (p/"tsconfig.json").exists(): return "typescript"
                    return lang
        ext = {'.py':'python','.js':'javascript','.ts':'typescript','.rs':'rust','.go':'go','.java':'java'}
        cnt = {}
        for e, l in ext.items():
            c = len(list(p.rglob(f'*{e}')))
            if c: cnt[l] = c
        return max(cnt,key=cnt.get) if cnt else "unknown"
    
    def _detect_frameworks(self, p, lang):
        fm = {"python":{"fastapi":"FastAPI","flask":"Flask","django":"Django",
              "sqlalchemy":"SQLAlchemy","pydantic":"Pydantic","celery":"Celery"},
              "javascript":{"express":"Express","react":"React","next":"Next.js","vue":"Vue"},
              "typescript":{"express":"Express","@nestjs":"NestJS","react":"React","prisma":"Prisma"},
              "rust":{"actix":"Actix","rocket":"Rocket","tokio":"Tokio","serde":"Serde"}}
        deps = {"python":["requirements.txt","pyproject.toml"],"javascript":["package.json"],
                "typescript":["package.json"],"rust":["Cargo.toml"]}
        found = []
        for df in deps.get(lang,[]):
            fp = p/df
            if fp.exists():
                c = fp.read_text(errors='ignore').lower()
                for kw,nm in fm.get(lang,{}).items():
                    if kw.lower() in c: found.append(nm)
        return list(set(found))
    
    def _detect_build_system(self, p, lang):
        s = {"python":"pip","javascript":"npm","typescript":"npm","rust":"cargo","go":"go modules","java":"maven"}
        return s.get(lang,"")
    
    def _detect_package_manager(self, p, lang):
        s = {"python":"pip","javascript":"npm","typescript":"npm","rust":"cargo","go":"go mod"}
        return s.get(lang,"")
    
    def _extract_purpose(self, p):
        for r in ["README.md","README.rst","README.txt"]:
            rp = p/r
            if rp.exists():
                ls = rp.read_text(errors='ignore')[:3000].split('\n')
                after_title = False
                for l in ls:
                    l = l.strip()
                    if l.startswith('#'): after_title = True; continue
                    if after_title and l and len(l)>20: return l[:300]
        return ""
    
    def _infer_domain(self, purpose, name):
        dm = {"bank":"fintech","payment":"fintech","shop":"e-commerce","store":"e-commerce",
              "auth":"security","login":"security","token":"security","api":"api-service",
              "chat":"communication","ml":"machine-learning","pipeline":"data-processing"}
        c = (purpose+" "+name).lower()
        for k,d in dm.items():
            if k in c: return d
        return "general"
    
    def _find_source_dirs(self, p, lang):
        cm = {"python":["src","lib","app","api","core","services","models","utils"],
              "javascript":["src","lib","app","components","pages","api","utils"],
              "rust":["src"],"go":["cmd","pkg","internal","api"]}
        return [d for d in cm.get(lang,[]) if (p/d).exists()] or ["."]
    
    def _find_test_dirs(self, p):
        return [d for d in ["tests","test","__tests__","spec"] if (p/d).exists()]
    
    def _find_config_files(self, p):
        return [c for c in [".env",".env.example","config.py","config.json","config.yaml"] if (p/c).exists()]
    
    def _find_entry_point(self, p, lang):
        cm = {"python":["main.py","app.py","run.py","manage.py"],
              "javascript":["index.js","app.js","server.js"],
              "typescript":["index.ts","app.ts","server.ts"],
              "rust":["src/main.rs"],"go":["main.go"]}
        for c in cm.get(lang,[]):
            if (p/c).exists(): return c
        return ""
    
    def _count_files_and_lines(self, p, lang):
        em = {"python":[".py"],"javascript":[".js",".jsx"],"typescript":[".ts",".tsx"],
              "rust":[".rs"],"go":[".go"],"java":[".java"]}
        tf = 0; tl = 0
        for ext in em.get(lang,[".py"]):
            for f in p.rglob(f'*{ext}'):
                if any(x in str(f) for x in ['node_modules','.git','target','__pycache__']): continue
                tf += 1
                try: tl += len(f.read_text(errors='ignore').split('\n'))
                except: pass  # noqa: bare-except — non-critical fallback
        return tf, tl
    
    def _infer_architecture(self, p, lang):
        if (p/"models").exists() and ((p/"controllers").exists() or (p/"views").exists()): return "mvc"
        if (p/"api").exists() and (p/"core").exists(): return "hexagonal"
        if (p/"docker-compose.yml").exists(): return "microservices"
        if (p/"services").exists() and (p/"repositories").exists(): return "layered"
        return "monolith"
    
    def _analyze_dependencies(self, p, lang):
        deps = []
        if lang=="python" and (p/"requirements.txt").exists():
            for line in (p/"requirements.txt").read_text().split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    name = line.split('==')[0].split('>=')[0].strip()
                    deps.append(DependencyInfo(name=name, version=""))
        elif lang in ("javascript","typescript") and (p/"package.json").exists():
            data = json.loads((p/"package.json").read_text())
            for name in data.get("dependencies",{}):
                deps.append(DependencyInfo(name=name, version=data["dependencies"][name]))
            for name in data.get("devDependencies",{}):
                deps.append(DependencyInfo(name=name, version=data["devDependencies"][name], is_dev=True))
        elif lang=="rust" and (p/"Cargo.toml").exists():
            for line in (p/"Cargo.toml").read_text().split('\n'):
                if '=' in line and not line.startswith('['):
                    deps.append(DependencyInfo(name=line.split('=')[0].strip()))
        return deps[:50]
    
    def _build_knowledge_graph(self, p, lang):
        graph = {}
        ext = {"python":[".py"],"javascript":[".js",".jsx"],"typescript":[".ts",".tsx"],"rust":[".rs"],"go":[".go"]}
        py_files = []
        for e in ext.get(lang,[".py"]):
            py_files.extend(p.rglob(f'*{e}'))
        py_files = py_files[:self.max_files]
        
        for pf in py_files:
            try:
                c = pf.read_text(errors='ignore')[:self.max_lines_per_file*100]
                node = ComponentInfo(
                    name=pf.stem, type="module", file_path=str(pf.relative_to(p)),
                    language=lang, lines=len(c.split('\n')),
                    complexity=c.count('if ')+c.count('for ')+c.count('while '),
                    purpose=self._extract_component_purpose(c),
                )
                if 'class' in c and ('Model' in c or 'Base' in c): node.type = "model"
                elif 'route' in pf.stem.lower() or 'endpoint' in pf.stem.lower() or '@app' in c: node.type = "endpoint"
                elif 'controller' in pf.stem.lower(): node.type = "controller"
                elif 'service' in pf.stem.lower(): node.type = "service"
                elif 'test' in pf.stem.lower(): node.type = "test"
                graph[pf.stem] = node
            except: pass  # noqa: bare-except — non-critical fallback
        
        for name, node in graph.items():
            try:
                pf = p / node.file_path
                c = pf.read_text(errors='ignore')
                imports = re.findall(r'(?:from\s+[.\w]+\s+import\s+[\w,]+|import\s+[\w.]+)', c)
                for imp in imports:
                    for other in graph:
                        if other in imp and other != name:
                            node.dependencies.append(other)
            except: pass  # noqa: bare-except — non-critical fallback
        
        return graph
    
    def _extract_component_purpose(self, content):
        m = re.search(r'"""(.*?)"""', content, re.DOTALL)
        if m:
            fl = m.group(1).strip().split('\n')[0].strip()
            if len(fl)>10: return fl[:100]
        return ""
    
    def _infer_data_flows(self, ctx):
        flows = []
        ep = [n for n, c in ctx.components.items() if c.type in ("endpoint","controller") or n in ("main","app","index")]
        for e in ep[:5]:
            path = [e]; visited = {e}; cur = e
            for _ in range(10):
                node = ctx.components.get(cur)
                if not node or not node.dependencies: break
                nd = next((d for d in node.dependencies if d not in visited), None)
                if not nd: break
                path.append(nd); visited.add(nd); cur = nd
            flows.append(path)
        return flows
    
    def _has_test_files(self, p, lang):
        pt = {"python":["test_*.py","*_test.py"],"javascript":["*.test.js","*.spec.js"],
              "typescript":["*.test.ts","*.spec.ts"],"rust":["*tests*"],"go":["*_test.go"]}
        for pat in pt.get(lang,[]):
            if list(p.rglob(pat)): return True
        return False
    
    def _has_linting(self, p, lang):
        lt = {"python":[".flake8",".pylintrc","pyproject.toml"],
              "javascript":[".eslintrc",".eslintrc.js"],"typescript":[".eslintrc"]}
        for f in lt.get(lang,[]):
            if (p/f).exists(): return True
        return False
    
    def _has_type_checking(self, p, lang):
        if lang=="python" and (p/"pyproject.toml").exists():
            return "mypy" in (p/"pyproject.toml").read_text().lower()
        return lang in ("typescript",)
    
    def _has_ci(self, p):
        return ((p/".github/workflows").exists() or (p/".gitlab-ci.yml").exists())
    
    def _has_docker(self, p):
        return ((p/"Dockerfile").exists() or (p/"docker-compose.yml").exists())
    
    def _calculate_health(self, ctx):
        s = 0.0
        if ctx.has_tests: s += 30
        if ctx.has_linting: s += 15
        if ctx.has_type_checking: s += 10
        if ctx.has_ci: s += 20
        if ctx.has_docker: s += 10
        if ctx.has_docs: s += 5
        if not ctx.risks: s += 10
        return min(s, 100.0)
    
    def _classify_health(self, score):
        if score >= 80: return ProjectHealth.HEALTHY
        if score >= 50: return ProjectHealth.WARNING
        return ProjectHealth.CRITICAL
    
    def _detect_risks(self, p, ctx):
        risks = []
        rid = 0
        
        if (p/"requirements.txt").exists():
            c = (p/"requirements.txt").read_text()
            if "==" not in c and ">=" not in c:
                rid += 1
                risks.append(Risk(id=f"R{rid:03d}", area="security", severity=RiskLevel.MEDIUM,
                    description="Dependencies not version-pinned in requirements.txt",
                    recommendation="Pin dependency versions with == or >="))
        
        for f in list(p.rglob("*.py"))[:200]:
            try:
                c = f.read_text(errors='ignore')
                fn = f.name
                if re.search(r'SECRET_KEY\s*=\s*["\'][^"\']{1,20}["\']', c):
                    rid += 1
                    risks.append(Risk(id=f"R{rid:03d}", area="security", severity=RiskLevel.CRITICAL,
                        file_path=str(f.relative_to(p)),
                        description=f"Hardcoded secret in {fn}",
                        recommendation="Use environment variables or secrets manager", cwe_id="CWE-798"))
                if "yaml.load(" in c and "yaml.safe_load(" not in c:
                    rid += 1
                    risks.append(Risk(id=f"R{rid:03d}", area="security", severity=RiskLevel.CRITICAL,
                        file_path=str(f.relative_to(p)),
                        description=f"Unsafe YAML deserialization in {fn}",
                        recommendation="Use yaml.safe_load() instead of yaml.load()", cwe_id="CWE-502"))
                if re.search(r'(execute|query)\s*\(\s*["\'].*\{.*\}', c):
                    rid += 1
                    risks.append(Risk(id=f"R{rid:03d}", area="security", severity=RiskLevel.CRITICAL,
                        file_path=str(f.relative_to(p)),
                        description=f"Potential SQL injection via f-string in {fn}",
                        recommendation="Use parameterized queries with ? placeholders", cwe_id="CWE-89"))
                if re.search(r'(os\.system|subprocess\.call|eval\(|exec\()', c):
                    rid += 1
                    risks.append(Risk(id=f"R{rid:03d}", area="security", severity=RiskLevel.HIGH,
                        file_path=str(f.relative_to(p)),
                        description=f"Potentially unsafe execution in {fn}",
                        recommendation="Avoid eval/exec/os.system with user input", cwe_id="CWE-78"))
            except: pass  # noqa: bare-except — non-critical fallback
        
        if len(ctx.components) > 0 and ctx.architecture == ArchitecturePattern.MONOLITH and ctx.file_count > 50:
            rid += 1
            risks.append(Risk(id=f"R{rid:03d}", area="maintainability", severity=RiskLevel.MEDIUM,
                description=f"Large monolithic project ({ctx.file_count} files). Consider modularization."))
        
        if ctx.file_count > 1000 and not ctx.has_tests:
            rid += 1
            risks.append(Risk(id=f"R{rid:03d}", area="maintainability", severity=RiskLevel.HIGH,
                description=f"Large codebase ({ctx.file_count} files) with no automated tests."))
        
        return risks[:30]


project_intelligence = ProjectIntelligence()
