"""
Intent Interpreter — Pilares 8-9 da evolução Quimera.

Transforma linguagem natural do usuário em um plano de execução estruturado,
combinando interpretação de intenção com análise determinística do projeto.

Fluxo:
    Usuário → Intent Interpreter → ProjectContext → Execution Planner → Pipeline

Autor: Quimera MarkX — MetaX
"""
import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("quimera.intent_interpreter")


class IntentType(str, Enum):
    """Tipos de intenção que o Quimera entende."""
    REPAIR = "repair"           # Corrigir bugs, compilação, erros
    AUDIT = "audit"             # Auditar segurança, qualidade
    BENCHMARK = "benchmark"     # Medir desempenho
    OPTIMIZE = "optimize"       # Melhorar performance
    MIGRATE = "migrate"         # Migrar para outra linguagem
    EXPLAIN = "explain"         # Explicar arquitetura
    TEST = "test"               # Gerar/executar testes
    DOCUMENT = "document"       # Gerar documentação
    MONITOR = "monitor"         # Monitorar em produção
    UNKNOWN = "unknown"         # Intenção não identificada


@dataclass
class ProjectContext:
    """Modelo mental do projeto — o que o Quimera sabe sobre ele."""
    # Identidade
    project_name: str = ""
    project_path: str = "."
    
    # Linguagens e frameworks
    primary_language: str = "unknown"
    secondary_languages: List[str] = field(default_factory=list)
    frameworks: List[str] = field(default_factory=list)
    
    # Propósito
    purpose: str = ""                        # Ex: "API REST bancária"
    domain: str = ""                         # Ex: "fintech", "e-commerce"
    
    # Arquitetura
    architecture: str = ""                   # Ex: "MVC", "microservices"
    entry_point: str = ""                    # Ex: "uvicorn main:app"
    build_command: str = ""                  # Ex: "cargo build"
    test_command: str = ""                   # Ex: "pytest"
    
    # Dependências
    dependencies: List[str] = field(default_factory=list)
    dev_dependencies: List[str] = field(default_factory=list)
    
    # Estado atual
    has_tests: bool = False
    has_docker: bool = False
    has_ci: bool = False
    has_docs: bool = False
    
    # Problema detectado
    current_error: str = ""                  # Erro atual se houver
    expected_behavior: str = ""              # Como deveria funcionar
    actual_behavior: str = ""                # Como está funcionando
    
    # Knowledge Graph (navegação pelo sistema)
    components: Dict[str, List[str]] = field(default_factory=dict)  # component → [dependencies]
    data_flow: List[str] = field(default_factory=list)              # Ordem de execução
    
    def to_dict(self) -> Dict:
        return {
            "project_name": self.project_name,
            "primary_language": self.primary_language,
            "frameworks": self.frameworks,
            "purpose": self.purpose,
            "architecture": self.architecture,
            "entry_point": self.entry_point,
            "has_tests": self.has_tests,
            "current_error": self.current_error,
            "components": self.components,
        }


class IntentInterpreter:
    """Interpreta linguagem natural e contexto do projeto em um plano de execução.
    
    Combina:
      - LLM local: interpreta intenção do usuário
      - Análise determinística: detecta linguagens, frameworks, estrutura
      - Heurísticas: mapeia intenção → estratégia
    """
    
    # Mapeamento de palavras-chave → intenção
    INTENT_KEYWORDS = {
        IntentType.REPAIR: [
            "não compila", "não funciona", "quebrou", "bug", "erro", "corrig",
            "consert", "arrum", "fix", "broken", "crash", "fail", "500", "traceback",
            "exception", "não roda", "parou", "quebrado",
        ],
        IntentType.AUDIT: [
            "audit", "segurança", "vulnerabilidade", "security", "vuln", "cve",
            "owasp", "breach", "hack", "exploit", "inseguro",
        ],
        IntentType.BENCHMARK: [
            "benchmark", "velocidade", "tempo", "compar", "métrica", "perfil",
            "profiler", "latência", "throughput",
        ],
        IntentType.OPTIMIZE: [
            "lento", "devagar", "otimiz", "optimiz", "performance", "rápido",
            "memória", "cpu", "gargalo", "bottleneck", "consumo",
        ],
        IntentType.MIGRATE: [
            "migrar", "converter", "transform", "portar", "reescrever", "migrat",
            "python para rust", "javascript para typescript",
        ],
        IntentType.EXPLAIN: [
            "explica", "explique", "como funciona", "arquitetura", "entender",
            "documenta", "descreve", "o que faz",
        ],
        IntentType.TEST: [
            "teste", "test", "cobertura", "coverage", "tdd", "pytest",
            "testar", "testando",
        ],
        IntentType.DOCUMENT: [
            "documenta", "readme", "docstring", "documentação", "docs",
        ],
        IntentType.MONITOR: [
            "monitora", "watch", "observa", "alerta", "notifica",
        ],
    }
    
    # Mapeamento intenção → estratégia
    INTENT_TO_STRATEGY = {
        IntentType.REPAIR: "repair_pipeline",
        IntentType.AUDIT: "security_audit",
        IntentType.BENCHMARK: "performance_benchmark",
        IntentType.OPTIMIZE: "performance_optimization",
        IntentType.MIGRATE: "language_migration",
        IntentType.EXPLAIN: "project_analysis",
        IntentType.TEST: "test_generation",
        IntentType.DOCUMENT: "documentation_generation",
        IntentType.MONITOR: "continuous_monitoring",
    }
    
    def __init__(self, use_llm: bool = False):
        self.use_llm = use_llm
    
    def interpret(self, user_message: str, project_path: str = ".") -> Tuple[IntentType, ProjectContext, Dict]:
        """Interpreta a mensagem do usuário e retorna intenção + contexto + plano.
        
        Args:
            user_message: Mensagem em linguagem natural
            project_path: Caminho do projeto
            
        Returns:
            (intent_type, project_context, execution_plan)
        """
        # 1. Interpretar intenção
        intent = self._detect_intent(user_message)
        logger.info(f"Intent detected: {intent.value} from '{user_message[:60]}...'")
        
        # 2. Analisar projeto deterministicamente
        context = self._analyze_project(project_path)
        
        # 3. Extrair detalhes da mensagem
        self._enrich_context_from_message(context, user_message)
        
        # 4. Gerar plano de execução
        plan = self._generate_plan(intent, context, user_message)
        
        return intent, context, plan
    
    def _detect_intent(self, message: str) -> IntentType:
        """Detecta a intenção do usuário por palavras-chave."""
        message_lower = message.lower()
        scores = {}
        
        for intent, keywords in self.INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in message_lower)
            if score > 0:
                scores[intent] = score
        
        if not scores:
            return IntentType.UNKNOWN
        
        # Intent com mais matches
        return max(scores, key=scores.get)
    
    def _analyze_project(self, project_path: str) -> ProjectContext:
        """Análise determinística do projeto."""
        ctx = ProjectContext(project_path=project_path)
        path = Path(project_path)
        
        if not path.exists():
            return ctx
        
        # Nome do projeto
        ctx.project_name = path.name
        
        # Detectar linguagem principal
        ctx.primary_language = self._detect_language(path)
        
        # Detectar frameworks
        ctx.frameworks = self._detect_frameworks(path, ctx.primary_language)
        
        # Detectar dependências
        ctx.dependencies = self._detect_dependencies(path, ctx.primary_language)
        
        # Propósito (via README)
        ctx.purpose = self._extract_purpose(path)
        
        # Entry point
        ctx.entry_point = self._detect_entry_point(path, ctx.primary_language)
        
        # Comandos
        ctx.build_command = self._detect_build_command(path, ctx.primary_language)
        ctx.test_command = self._detect_test_command(path, ctx.primary_language)
        
        # Capacidades
        ctx.has_tests = self._has_tests(path, ctx.primary_language)
        ctx.has_docker = (path / "Dockerfile").exists() or (path / "docker-compose.yml").exists()
        ctx.has_ci = (path / ".github" / "workflows").exists() or (path / ".gitlab-ci.yml").exists()
        ctx.has_docs = (path / "docs").exists() or (path / "README.md").exists()
        
        # Knowledge Graph básico
        ctx.components = self._build_component_graph(path, ctx.primary_language)
        
        logger.info(f"Project analyzed: {ctx.primary_language}, {len(ctx.frameworks)} frameworks, "
                    f"tests={ctx.has_tests}, docker={ctx.has_docker}")
        
        return ctx
    
    def _detect_language(self, path: Path) -> str:
        """Detecta a linguagem principal do projeto."""
        indicators = {
            "python": ["pyproject.toml", "setup.py", "requirements.txt", "Pipfile", "poetry.lock"],
            "javascript": ["package.json", "yarn.lock", "node_modules"],
            "typescript": ["tsconfig.json", "package.json"],
            "rust": ["Cargo.toml", "Cargo.lock"],
            "go": ["go.mod", "go.sum"],
            "java": ["pom.xml", "build.gradle", "build.gradle.kts", "gradlew"],
            "c": ["Makefile", "CMakeLists.txt", "configure"],
            "cpp": ["CMakeLists.txt", "Makefile", "configure"],
            "ruby": ["Gemfile", "Rakefile"],
            "php": ["composer.json", "composer.lock"],
            "swift": ["Package.swift"],
            "kotlin": ["build.gradle.kts", "settings.gradle.kts"],
        }
        
        for lang, files in indicators.items():
            for f in files:
                if (path / f).exists():
                    return lang
        
        # Fallback: contar extensões de arquivo
        ext_counts = {}
        for ext in ['.py', '.js', '.ts', '.rs', '.go', '.java', '.c', '.cpp', '.rb', '.php']:
            count = len(list(path.rglob(f'*{ext}')))
            if count > 0:
                ext_counts[ext] = count
        
        if ext_counts:
            top_ext = max(ext_counts, key=ext_counts.get)
            lang_map = {
                '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
                '.rs': 'rust', '.go': 'go', '.java': 'java',
                '.c': 'c', '.cpp': 'cpp', '.rb': 'ruby', '.php': 'php',
            }
            return lang_map.get(top_ext, 'unknown')
        
        return "unknown"
    
    def _detect_frameworks(self, path: Path, language: str) -> List[str]:
        """Detecta frameworks do projeto."""
        framework_indicators = {
            "python": {
                "FastAPI": ["fastapi", "starlette"],
                "Flask": ["flask"],
                "Django": ["django"],
                "SQLAlchemy": ["sqlalchemy"],
                "Pydantic": ["pydantic"],
                "Celery": ["celery"],
                "Pytest": ["pytest"],
            },
            "javascript": {
                "Express": ["express"],
                "React": ["react"],
                "Next.js": ["next"],
                "Vue": ["vue"],
                "Angular": ["@angular/core"],
                "Jest": ["jest"],
                "Mocha": ["mocha"],
            },
            "typescript": {
                "Express": ["express"],
                "NestJS": ["@nestjs/core"],
                "React": ["react"],
                "Next.js": ["next"],
                "Prisma": ["prisma"],
            },
            "rust": {
                "Actix": ["actix"],
                "Rocket": ["rocket"],
                "Tokio": ["tokio"],
                "Serde": ["serde"],
                "Diesel": ["diesel"],
            },
        }
        
        found = []
        indicators = framework_indicators.get(language, {})
        
        # Verificar arquivos de dependência
        dep_files = {
            "python": ["requirements.txt", "pyproject.toml", "Pipfile"],
            "javascript": ["package.json"],
            "typescript": ["package.json", "tsconfig.json"],
            "rust": ["Cargo.toml"],
        }
        
        for dep_file in dep_files.get(language, []):
            dep_path = path / dep_file
            if dep_path.exists():
                content = dep_path.read_text(errors='ignore')
                for framework, keywords in indicators.items():
                    for kw in keywords:
                        if kw in content.lower():
                            found.append(framework)
                            break
        
        return list(set(found))
    
    def _detect_dependencies(self, path: Path, language: str) -> List[str]:
        """Extrai lista de dependências principais."""
        deps = []
        
        if language in ("python",):
            for f in ["requirements.txt"]:
                fp = path / f
                if fp.exists():
                    for line in fp.read_text().split('\n'):
                        line = line.strip()
                        if line and not line.startswith('#'):
                            deps.append(line.split('==')[0].split('>=')[0].strip())
        
        elif language in ("javascript", "typescript"):
            pkg = path / "package.json"
            if pkg.exists():
                data = json.loads(pkg.read_text())
                deps = list(data.get("dependencies", {}).keys())
        
        elif language == "rust":
            cargo = path / "Cargo.toml"
            if cargo.exists():
                for line in cargo.read_text().split('\n'):
                    if '=' in line and not line.startswith('['):
                        deps.append(line.split('=')[0].strip().strip('"'))
        
        return deps[:20]
    
    def _extract_purpose(self, path: Path) -> str:
        """Extrai o propósito do projeto via README."""
        for readme in ["README.md", "README.rst", "README.txt", "README"]:
            rp = path / readme
            if rp.exists():
                content = rp.read_text(errors='ignore')[:2000]
                # Procurar descrição na primeira seção
                lines = content.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('#') and len(line) > 20:
                        return line[:200]
        return ""
    
    def _detect_entry_point(self, path: Path, language: str) -> str:
        """Detecta o ponto de entrada do projeto."""
        candidates = {
            "python": ["main.py", "app.py", "run.py", "manage.py", "wsgi.py"],
            "javascript": ["index.js", "app.js", "server.js", "main.js"],
            "typescript": ["index.ts", "app.ts", "server.ts", "main.ts"],
            "rust": ["src/main.rs"],
            "go": ["main.go"],
        }
        
        for candidate in candidates.get(language, []):
            if (path / candidate).exists():
                return candidate
        
        return ""
    
    def _detect_build_command(self, path: Path, language: str) -> str:
        """Detecta comando de build."""
        commands = {
            "python": "",
            "javascript": "npm run build",
            "typescript": "npm run build",
            "rust": "cargo build --release",
            "go": "go build ./...",
            "java": "mvn package",
        }
        return commands.get(language, "")
    
    def _detect_test_command(self, path: Path, language: str) -> str:
        """Detecta comando de teste."""
        if (path / "pyproject.toml").exists():
            content = (path / "pyproject.toml").read_text()
            if "pytest" in content:
                return "pytest"
        
        commands = {
            "python": "pytest" if self._has_tests(path, "python") else "",
            "javascript": "npm test",
            "typescript": "npm test",
            "rust": "cargo test",
            "go": "go test ./...",
            "java": "mvn test",
        }
        return commands.get(language, "")
    
    def _has_tests(self, path: Path, language: str) -> bool:
        """Verifica se o projeto tem testes."""
        test_dirs = ["tests", "test", "__tests__", "spec", "test"]
        test_patterns = {
            "python": ["test_*.py", "*_test.py"],
            "javascript": ["*.test.js", "*.spec.js", "*.test.ts", "*.spec.ts"],
            "typescript": ["*.test.ts", "*.spec.ts"],
            "rust": ["*tests*"],
            "go": ["*_test.go"],
            "java": ["*Test.java", "*Tests.java"],
        }
        
        for test_dir in test_dirs:
            if (path / test_dir).exists():
                return True
        
        for pattern in test_patterns.get(language, []):
            if list(path.rglob(pattern)):
                return True
        
        return False
    
    def _build_component_graph(self, path: Path, language: str) -> Dict[str, List[str]]:
        """Constrói um grafo simplificado de componentes."""
        graph = {}
        
        if language == "python":
            py_files = list(path.rglob("*.py"))
            for pf in py_files[:30]:
                name = pf.stem
                try:
                    content = pf.read_text(errors='ignore')
                    imports = re.findall(r'from\s+[.\w]+\s+import\s+[\w,]+|import\s+[\w.]+', content)
                    deps = []
                    for imp in imports:
                        for other in py_files:
                            if other.stem in imp and other.stem != name:
                                deps.append(other.stem)
                    if deps:
                        graph[name] = list(set(deps))
                except:
                    pass  # noqa: bare-except — non-critical fallback
        
        return graph
    
    def _enrich_context_from_message(self, ctx: ProjectContext, message: str):
        """Extrai informações adicionais da mensagem do usuário."""
        # Detectar menção de erro específico
        error_patterns = [
            r'(Traceback.*?)(?:\n|$)',
            r'(Error:.*?)(?:\n|$)',
            r'(Exception:.*?)(?:\n|$)',
            r'(\d{3}\s+(?:Internal Server|Bad Request|Not Found).*?)(?:\n|$)',
        ]
        for pattern in error_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                ctx.current_error = match.group(1).strip()[:200]
                ctx.actual_behavior = ctx.current_error
                break
        
        # Detectar expectativa
        expect_patterns = [
            r'(?:deveria|should|expected to|era para)\s+(.*?)(?:\.|$|mas)',
            r'(?:funcionava|worked)\s+(.*?)(?:\.|$|mas)',
        ]
        for pattern in expect_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                ctx.expected_behavior = match.group(1).strip()[:200]
                break
    
    def _generate_plan(self, intent: IntentType, ctx: ProjectContext, message: str) -> Dict:
        """Gera um plano de execução baseado na intenção e contexto."""
        strategy = self.INTENT_TO_STRATEGY.get(intent, "full_pipeline")
        
        base_plan = {
            "intent": intent.value,
            "strategy": strategy,
            "project_name": ctx.project_name,
            "language": ctx.primary_language,
            "frameworks": ctx.frameworks,
            "context": ctx.to_dict(),
            "message": message[:500],
        }
        
        # Planos específicos por intenção
        if intent == IntentType.REPAIR:
            base_plan["stages"] = [
                "analyze_project",
                "run_tests" if ctx.has_tests else "skip_tests",
                "collect_errors",
                "plan_repair",
                "evolve",
                "verify",
                "generate_report",
            ]
            base_plan["error_type"] = self._classify_error(ctx.current_error)
        
        elif intent == IntentType.AUDIT:
            base_plan["stages"] = [
                "analyze_project",
                "static_analysis",
                "dependency_scan",
                "vulnerability_detection",
                "generate_patches",
                "security_report",
            ]
        
        elif intent == IntentType.BENCHMARK:
            base_plan["stages"] = [
                "analyze_project",
                "run_benchmarks",
                "profile_code",
                "identify_bottlenecks",
                "generate_report",
            ]
        
        elif intent == IntentType.OPTIMIZE:
            base_plan["stages"] = [
                "analyze_project",
                "profile_code",
                "identify_bottlenecks",
                "generate_optimizations",
                "verify_optimizations",
                "generate_report",
            ]
        
        elif intent == IntentType.MIGRATE:
            target = self._extract_migration_target(message)
            base_plan["stages"] = [
                "analyze_project",
                f"translate_to_{target}" if target else "translate_code",
                "verify_translation",
                "generate_report",
            ]
            base_plan["migration_target"] = target
        
        else:
            base_plan["stages"] = [
                "analyze_project",
                "full_pipeline",
                "generate_report",
            ]
        
        logger.info(f"Plan generated: {strategy} with {len(base_plan.get('stages', []))} stages")
        return base_plan
    
    def _classify_error(self, error_text: str) -> str:
        """Classifica o tipo de erro a partir do texto."""
        error_map = {
            "syntax_error": ["SyntaxError", "syntax error", "invalid syntax"],
            "import_error": ["ImportError", "ModuleNotFoundError", "No module named"],
            "attribute_error": ["AttributeError", "has no attribute"],
            "type_error": ["TypeError"],
            "value_error": ["ValueError"],
            "key_error": ["KeyError"],
            "index_error": ["IndexError", "list index out of range"],
            "buffer_overflow": ["buffer overflow", "heap-buffer-overflow", "stack-buffer-overflow"],
            "null_deref": ["null pointer", "NoneType", "None has no"],
            "compilation_error": ["compilation error", "failed to compile", "build failed"],
            "timeout": ["timeout", "timed out", "took too long"],
            "memory_leak": ["memory leak", "out of memory", "OOM"],
            "connection_error": ["connection refused", "connection error", "cannot connect"],
            "auth_error": ["401", "403", "unauthorized", "forbidden", "permission denied"],
            "not_found": ["404", "not found"],
            "server_error": ["500", "internal server error"],
        }
        
        error_lower = error_text.lower()
        for error_type, patterns in error_map.items():
            for pattern in patterns:
                if pattern.lower() in error_lower:
                    return error_type
        
        return "unknown_error"
    
    def _extract_migration_target(self, message: str) -> str:
        """Extrai a linguagem alvo de migração."""
        targets = ["rust", "go", "typescript", "python", "java", "kotlin", "swift"]
        message_lower = message.lower()
        for target in targets:
            if target in message_lower:
                return target
        return ""


# Global
intent_interpreter = IntentInterpreter()
