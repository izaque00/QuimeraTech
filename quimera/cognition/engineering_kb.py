"""
Engineering Knowledge Base — Pilar 11 da evolução Quimera.

Memória técnica reutilizável: acumula conhecimento sobre vulnerabilidades,
padrões de correção, estratégias bem-sucedidas e projetos analisados.

Depois de centenas de análises, o Quimera tem uma base de conhecimento
que acelera diagnósticos e melhora a qualidade dos patches.

Formato da base:
    Vulnerabilidade → Linguagem → Framework → Detecção → Correção → Casos → Taxa de sucesso

Autor: Quimera MarkX — MetaX
"""
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("quimera.knowledge_base")


@dataclass
class VulnerabilityEntry:
    """Entrada de vulnerabilidade na base de conhecimento."""
    vuln_id: str                                # Identificador único
    name: str                                   # Nome da vulnerabilidade
    category: str                               # OWASP / CWE category
    severity: str                               # critical, high, medium, low
    languages: List[str] = field(default_factory=list)
    frameworks: List[str] = field(default_factory=list)
    detection_pattern: str = ""                 # Regex ou padrão de detecção
    fix_pattern: str = ""                       # Padrão de correção
    description: str = ""
    cwe_id: str = ""
    owasp_id: str = ""
    
    # Estatísticas acumuladas
    times_detected: int = 0
    times_fixed: int = 0
    success_rate: float = 0.0                   # Taxa de sucesso das correções
    
    # Casos conhecidos
    known_cases: List[Dict] = field(default_factory=list)
    
    # Projetos onde apareceu
    projects: List[str] = field(default_factory=list)


@dataclass
class StrategyRecord:
    """Registro de uma estratégia bem-sucedida."""
    error_type: str
    strategy_name: str
    agent_name: str
    language: str
    success_count: int = 0
    total_attempts: int = 0
    avg_duration_ms: float = 0.0
    avg_fitness: float = 0.0
    
    @property
    def success_rate(self) -> float:
        return self.success_count / max(self.total_attempts, 1)


class EngineeringKnowledgeBase:
    """Base de conhecimento de engenharia de software.
    
    Armazena e consulta:
      - Vulnerabilidades conhecidas por linguagem/framework
      - Padrões de detecção e correção
      - Estratégias bem-sucedidas por tipo de erro
      - Projetos analisados e seus contextos
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path) if storage_path else Path("logs/engineering_kb.json")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._vulnerabilities: Dict[str, VulnerabilityEntry] = {}
        self._strategies: Dict[str, StrategyRecord] = {}
        self._projects: Dict[str, Dict] = {}
        
        self._load()
        
        # Se vazio, popular com conhecimento base
        if not self._vulnerabilities:
            self._seed_base_knowledge()
    
    def _load(self):
        if self.storage_path.exists():
            with open(self.storage_path) as f:
                data = json.load(f)
            
            for vdata in data.get("vulnerabilities", {}).values():
                self._vulnerabilities[vdata["vuln_id"]] = VulnerabilityEntry(**vdata)
            
            for skey, sdata in data.get("strategies", {}).items():
                self._strategies[skey] = StrategyRecord(**sdata)
            
            self._projects = data.get("projects", {})
    
    def _save(self):
        with open(self.storage_path, 'w') as f:
            json.dump({
                "vulnerabilities": {
                    vid: {
                        "vuln_id": v.vuln_id, "name": v.name, "category": v.category,
                        "severity": v.severity, "languages": v.languages,
                        "frameworks": v.frameworks, "detection_pattern": v.detection_pattern,
                        "fix_pattern": v.fix_pattern, "description": v.description,
                        "cwe_id": v.cwe_id, "owasp_id": v.owasp_id,
                        "times_detected": v.times_detected, "times_fixed": v.times_fixed,
                        "success_rate": v.success_rate, "known_cases": v.known_cases[-10:],
                        "projects": v.projects[-20:],
                    }
                    for vid, v in self._vulnerabilities.items()
                },
                "strategies": {
                    skey: {
                        "error_type": s.error_type, "strategy_name": s.strategy_name,
                        "agent_name": s.agent_name, "language": s.language,
                        "success_count": s.success_count, "total_attempts": s.total_attempts,
                        "avg_duration_ms": s.avg_duration_ms, "avg_fitness": s.avg_fitness,
                    }
                    for skey, s in self._strategies.items()
                },
                "projects": self._projects,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }, f, indent=2, default=str)
    
    def _seed_base_knowledge(self):
        """Popula a base com conhecimento fundamental de engenharia."""
        base_vulns = [
            VulnerabilityEntry(
                vuln_id="VULN-001", name="SQL Injection", category="Injection",
                severity="critical", languages=["python", "javascript", "java", "php", "go", "rust"],
                frameworks=["SQLAlchemy", "Django ORM", "Sequelize", "JDBC"],
                detection_pattern=r'(execute|query)\s*\(\s*["\'].*\{.*\}',
                fix_pattern="Use parameterized queries with ? or %s placeholders",
                description="User input concatenated directly into SQL queries",
                cwe_id="CWE-89", owasp_id="A03:2021",
            ),
            VulnerabilityEntry(
                vuln_id="VULN-002", name="Hardcoded Secrets", category="Cryptographic Failures",
                severity="critical", languages=["*"],
                frameworks=["*"],
                detection_pattern=r'(SECRET|API_KEY|PASSWORD|TOKEN)\s*=\s*["\'][A-Za-z0-9]',
                fix_pattern="Use environment variables or secrets manager",
                description="Secrets hardcoded in source code",
                cwe_id="CWE-798", owasp_id="A02:2021",
            ),
            VulnerabilityEntry(
                vuln_id="VULN-003", name="Command Injection", category="Injection",
                severity="critical", languages=["python", "javascript", "java", "php", "ruby"],
                frameworks=["*"],
                detection_pattern=r'(os\.system|subprocess\.|exec\(|eval\(|shell_exec)',
                fix_pattern="Use subprocess.run with args list and shell=False",
                description="User input passed to system command execution",
                cwe_id="CWE-78", owasp_id="A03:2021",
            ),
            VulnerabilityEntry(
                vuln_id="VULN-004", name="Path Traversal", category="Broken Access Control",
                severity="high", languages=["python", "javascript", "java", "php"],
                frameworks=["Flask", "Express", "Spring"],
                detection_pattern=r'(open|read|send_file)\s*\(\s*.*\+.*request',
                fix_pattern="Use os.path.basename() or path sanitization",
                description="User input used to construct file paths without sanitization",
                cwe_id="CWE-22", owasp_id="A01:2021",
            ),
            VulnerabilityEntry(
                vuln_id="VULN-005", name="XSS (Cross-Site Scripting)", category="Injection",
                severity="high", languages=["javascript", "typescript", "python", "java", "php"],
                frameworks=["React", "Vue", "Django", "Flask", "Express"],
                detection_pattern=r'(innerHTML|dangerouslySetInnerHTML|Markup\()',
                fix_pattern="Use auto-escaping template engines. Sanitize user input.",
                description="User input rendered without escaping",
                cwe_id="CWE-79", owasp_id="A03:2021",
            ),
            VulnerabilityEntry(
                vuln_id="VULN-006", name="Insecure Deserialization", category="Insecure Design",
                severity="high", languages=["python", "java", "javascript", "php"],
                frameworks=["*"],
                detection_pattern=r'(pickle\.load|yaml\.load\(|ObjectInputStream|unserialize)',
                fix_pattern="Use safe loaders: yaml.safe_load(), never pickle.load() on user data",
                description="User-controlled data deserialized without validation",
                cwe_id="CWE-502", owasp_id="A08:2021",
            ),
            VulnerabilityEntry(
                vuln_id="VULN-007", name="SSRF", category="Security Misconfiguration",
                severity="high", languages=["python", "javascript", "java", "go"],
                frameworks=["*"],
                detection_pattern=r'(requests\.get|fetch|http\.get|urlopen)\s*\(\s*.*request\.',
                fix_pattern="Whitelist allowed URLs. Never pass user input directly to HTTP clients.",
                description="User-controlled URL fetched by server",
                cwe_id="CWE-918", owasp_id="A10:2021",
            ),
            VulnerabilityEntry(
                vuln_id="VULN-008", name="SSTI (Server-Side Template Injection)", category="Injection",
                severity="critical", languages=["python", "javascript", "java"],
                frameworks=["Jinja2", "Django Templates", "EJS", "Thymeleaf"],
                detection_pattern=r'(jinja2\.Template|render_template_string)\s*\(',
                fix_pattern="Never concatenate user input into template strings. Use template variables.",
                description="User input embedded directly in template engine",
                cwe_id="CWE-94", owasp_id="A03:2021",
            ),
            VulnerabilityEntry(
                vuln_id="VULN-009", name="Mass Assignment", category="Broken Access Control",
                severity="high", languages=["python", "javascript", "java", "ruby"],
                frameworks=["Django", "Flask", "Express", "Rails", "Spring"],
                detection_pattern=r'\*\*\w+,\s*\*\*|Object\.assign\(.*req\.body',
                fix_pattern="Explicitly whitelist updatable fields. Never use spread on request body.",
                description="All request body fields assigned to model without filtering",
                cwe_id="CWE-915", owasp_id="A01:2021",
            ),
            VulnerabilityEntry(
                vuln_id="VULN-010", name="Buffer Overflow", category="Memory Safety",
                severity="critical", languages=["c", "cpp", "rust(unsafe)"],
                frameworks=["*"],
                detection_pattern=r'(strcpy|strcat|sprintf|gets|scanf)\s*\(',
                fix_pattern="Use strncpy, snprintf, or safe alternatives. Check buffer bounds.",
                description="Unchecked buffer operations leading to memory corruption",
                cwe_id="CWE-120", owasp_id="N/A",
            ),
        ]
        
        for v in base_vulns:
            self._vulnerabilities[v.vuln_id] = v
        
        self._save()
        logger.info(f"Knowledge base seeded with {len(base_vulns)} vulnerability patterns")
    
    # ──── Consulta ──────────────────────────────────────────────────
    
    def find_vulnerabilities(
        self,
        language: str,
        framework: Optional[str] = None,
        severity: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[VulnerabilityEntry]:
        """Encontra vulnerabilidades relevantes para um contexto."""
        results = []
        for vuln in self._vulnerabilities.values():
            if language not in vuln.languages and "*" not in vuln.languages:
                continue
            if framework and framework not in vuln.frameworks and "*" not in vuln.frameworks:
                continue
            if severity and vuln.severity != severity:
                continue
            if category and vuln.category != category:
                continue
            results.append(vuln)
        
        return sorted(results, key=lambda v: (
            {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(v.severity, 4)
        ))
    
    def get_detection_patterns(self, language: str, framework: str = "") -> List[Tuple[str, str]]:
        """Retorna padrões de detecção para uma linguagem/framework."""
        vulns = self.find_vulnerabilities(language, framework)
        return [(v.name, v.detection_pattern) for v in vulns if v.detection_pattern]
    
    def get_fix_patterns(self, vuln_name: str) -> Optional[str]:
        """Retorna o padrão de correção para uma vulnerabilidade."""
        for vuln in self._vulnerabilities.values():
            if vuln.name.lower() == vuln_name.lower():
                return vuln.fix_pattern
        return None
    
    # ──── Registro ──────────────────────────────────────────────────
    
    def record_detection(self, vuln_id: str, project_name: str, language: str):
        """Registra que uma vulnerabilidade foi detectada."""
        if vuln_id in self._vulnerabilities:
            v = self._vulnerabilities[vuln_id]
            v.times_detected += 1
            if project_name not in v.projects:
                v.projects.append(project_name)
            self._save()
    
    def record_fix(self, vuln_id: str, success: bool, case_data: Optional[Dict] = None):
        """Registra o resultado de uma tentativa de correção."""
        if vuln_id in self._vulnerabilities:
            v = self._vulnerabilities[vuln_id]
            v.times_fixed += 1
            if success:
                # Atualizar taxa de sucesso
                successes = sum(1 for c in v.known_cases if c.get("success"))
                v.success_rate = successes / max(len(v.known_cases), 1) if v.known_cases else 0.5
            if case_data:
                v.known_cases.append(case_data)
            self._save()
    
    def record_strategy(
        self,
        error_type: str,
        strategy_name: str,
        agent_name: str,
        language: str,
        success: bool,
        fitness: float = 0.0,
        duration_ms: float = 0.0,
    ):
        """Registra o resultado de uma estratégia."""
        key = f"{error_type}:{strategy_name}:{agent_name}:{language}"
        if key not in self._strategies:
            self._strategies[key] = StrategyRecord(
                error_type=error_type, strategy_name=strategy_name,
                agent_name=agent_name, language=language,
            )
        
        s = self._strategies[key]
        s.total_attempts += 1
        if success:
            s.success_count += 1
            s.avg_fitness = (s.avg_fitness * (s.success_count - 1) + fitness) / s.success_count
        s.avg_duration_ms = (s.avg_duration_ms * (s.total_attempts - 1) + duration_ms) / s.total_attempts
        
        self._save()
    
    def record_project(self, project_name: str, context: Dict):
        """Registra o contexto de um projeto analisado."""
        self._projects[project_name] = {
            **context,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save()
    
    # ──── Recomendação ──────────────────────────────────────────────
    
    def get_best_strategy(
        self, error_type: str, language: str, min_attempts: int = 3
    ) -> Optional[Dict]:
        """Recomenda a melhor estratégia baseada em histórico."""
        candidates = []
        for key, s in self._strategies.items():
            if s.error_type == error_type and s.language == language and s.total_attempts >= min_attempts:
                score = s.success_rate * max(s.avg_fitness, 0.1)
                candidates.append((key, score, s))
        
        if not candidates:
            return None
        
        best = max(candidates, key=lambda x: x[1])
        _, _, record = best
        
        return {
            "strategy": record.strategy_name,
            "agent": record.agent_name,
            "success_rate": f"{record.success_rate:.1%}",
            "avg_fitness": round(record.avg_fitness, 3),
            "avg_duration_ms": round(record.avg_duration_ms, 0),
            "attempts": record.total_attempts,
        }
    
    def get_project_recommendations(self, language: str, frameworks: List[str]) -> List[Dict]:
        """Recomenda verificações baseadas no tipo de projeto."""
        vulns = self.find_vulnerabilities(language)
        return [
            {
                "vuln_id": v.vuln_id,
                "name": v.name,
                "severity": v.severity,
                "description": v.description,
                "pattern": v.detection_pattern[:80] if v.detection_pattern else "",
            }
            for v in vulns
        ]
    
    # ──── Estatísticas ──────────────────────────────────────────────
    
    def get_stats(self) -> Dict:
        """Estatísticas da base de conhecimento."""
        return {
            "total_vulnerabilities": len(self._vulnerabilities),
            "total_detections": sum(v.times_detected for v in self._vulnerabilities.values()),
            "total_fixes": sum(v.times_fixed for v in self._vulnerabilities.values()),
            "strategies_tracked": len(self._strategies),
            "projects_analyzed": len(self._projects),
            "top_vulnerabilities": [
                {"name": v.name, "detections": v.times_detected, "severity": v.severity}
                for v in sorted(self._vulnerabilities.values(), key=lambda x: -x.times_detected)[:5]
            ],
        }


# Global
engineering_kb = EngineeringKnowledgeBase()
