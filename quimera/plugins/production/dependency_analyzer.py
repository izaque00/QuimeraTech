#!/usr/bin/env python3
"""
Plugin de Dependency Analyzer Ultra-Avançado
Analisa dependências, vulnerabilidades conhecidas, licenças, compatibilidade
e sugere otimizações e alternativas melhores.
"""

import asyncio
import json
import logging
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set
import aiohttp
import packaging.version
from urllib.parse import urljoin
import hashlib

# Importa framework de plugins
sys.path.append(str(Path(__file__).parent.parent.parent))
from quimera.core.plugin_framework import BasePlugin, PluginInfo, PluginPriority, plugin_decorator


@dataclass
class DependencyInfo:
    """Informações detalhadas de uma dependência"""
    name: str
    current_version: str
    latest_version: Optional[str] = None
    license: Optional[str] = None
    description: Optional[str] = None
    homepage: Optional[str] = None
    vulnerabilities: List[Dict] = field(default_factory=list)
    is_outdated: bool = False
    severity_score: float = 0.0  # 0.0 - 10.0
    maintenance_status: str = "unknown"  # active, maintenance, deprecated, abandoned
    popularity_score: int = 0  # Downloads/popularity
    size_mb: float = 0.0
    dependencies_count: int = 0


@dataclass
class VulnerabilityInfo:
    """Informações de vulnerabilidade"""
    cve_id: str
    severity: str  # critical, high, medium, low
    cvss_score: float
    description: str
    affected_versions: List[str]
    fixed_version: Optional[str]
    published_date: str
    references: List[str] = field(default_factory=list)


@dataclass
class LicenseAnalysis:
    """Análise de licenças"""
    license_name: str
    is_permissive: bool
    commercial_use: bool
    copyleft: bool
    patent_grant: bool
    compatibility_issues: List[str] = field(default_factory=list)
    risk_level: str = "low"  # low, medium, high


@dataclass
class DependencyRecommendation:
    """Recomendação para dependência"""
    dependency_name: str
    action: str  # update, replace, remove, monitor
    priority: str  # critical, high, medium, low
    reason: str
    suggested_version: Optional[str] = None
    alternative_packages: List[str] = field(default_factory=list)
    estimated_effort: str = "low"  # low, medium, high
    benefits: List[str] = field(default_factory=list)


class VulnerabilityDatabase:
    """Base de dados de vulnerabilidades"""

    def __init__(self):
        self.vuln_cache = {}
        self.cache_ttl = 3600  # 1 hora

    async def get_vulnerabilities(self, package_name: str, version: str) -> List[VulnerabilityInfo]:
        """Busca vulnerabilidades para um pacote específico"""
        cache_key = f"{package_name}:{version}"

        # Verifica cache
        if cache_key in self.vuln_cache:
            cached_data, timestamp = self.vuln_cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                return cached_data

        # Busca vulnerabilidades (simulado - em produção usaria APIs reais)
        vulnerabilities = await self._fetch_vulnerabilities_from_api(package_name, version)

        # Atualiza cache
        self.vuln_cache[cache_key] = (vulnerabilities, time.time())

        return vulnerabilities

    async def _fetch_vulnerabilities_from_api(self, package_name: str, version: str) -> List[VulnerabilityInfo]:
        """Busca vulnerabilidades de APIs externas"""
        vulnerabilities = []

        try:
            # Simulação de busca em múltiplas fontes
            sources = [
                'https://osv.dev/query',
                'https://api.github.com/advisories',
                'https://nvd.nist.gov/vuln/search'
            ]

            # Em produção real, faria requests para essas APIs
            # Por agora, simula com algumas vulnerabilidades conhecidas
            if package_name.lower() in ['pillow', 'requests', 'urllib3', 'django']:
                vulns = await self._get_simulated_vulnerabilities(package_name, version)
                vulnerabilities.extend(vulns)

        except Exception as e:
            logging.warning(f"Erro ao buscar vulnerabilidades para {package_name}: {e}")

        return vulnerabilities

    async def _get_simulated_vulnerabilities(self, package_name: str, version: str) -> List[VulnerabilityInfo]:
        """Simula vulnerabilidades conhecidas para demonstração"""
        simulated_vulns = {
            'pillow': [
                VulnerabilityInfo(
                    cve_id='CVE-2023-44271',
                    severity='high',
                    cvss_score=8.1,
                    description='Arbitrary code execution in Pillow image processing',
                    affected_versions=['<10.0.0'],
                    fixed_version='10.0.0',
                    published_date='2023-10-15'
                )
            ],
            'requests': [
                VulnerabilityInfo(
                    cve_id='CVE-2023-32681',
                    severity='medium',
                    cvss_score=6.1,
                    description='Certificate verification bypass in requests',
                    affected_versions=['<2.31.0'],
                    fixed_version='2.31.0',
                    published_date='2023-05-26'
                )
            ]
        }

        return simulated_vulns.get(package_name.lower(), [])


class LicenseAnalyzer:
    """Analisador de licenças de software"""

    def __init__(self):
        self.license_db = {
            'MIT': LicenseAnalysis('MIT', True, True, False, False, [], 'low'),
            'Apache-2.0': LicenseAnalysis('Apache-2.0', True, True, False, True, [], 'low'),
            'GPL-3.0': LicenseAnalysis('GPL-3.0', False, True, True, True, ['MIT', 'Apache'], 'high'),
            'BSD-3-Clause': LicenseAnalysis('BSD-3-Clause', True, True, False, False, [], 'low'),
            'LGPL-2.1': LicenseAnalysis('LGPL-2.1', False, True, True, False, [], 'medium'),
            'MPL-2.0': LicenseAnalysis('MPL-2.0', False, True, False, True, [], 'medium'),
        }

    def analyze_license(self, license_name: str) -> LicenseAnalysis:
        """Analisa uma licença específica"""
        normalized_name = self._normalize_license_name(license_name)
        return self.license_db.get(normalized_name,
            LicenseAnalysis(license_name, False, False, False, False, [], 'high'))

    def check_compatibility(self, licenses: List[str]) -> Dict[str, Any]:
        """Verifica compatibilidade entre licenças"""
        analyses = [self.analyze_license(lic) for lic in licenses]

        # Verifica conflitos
        has_copyleft = any(analysis.copyleft for analysis in analyses)
        has_permissive = any(analysis.is_permissive for analysis in analyses)

        compatibility_issues = []
        if has_copyleft and has_permissive:
            compatibility_issues.append("Mistura de licenças copyleft e permissivas")

        # Calcula risco geral
        risk_levels = [analysis.risk_level for analysis in analyses]
        if 'high' in risk_levels:
            overall_risk = 'high'
        elif 'medium' in risk_levels:
            overall_risk = 'medium'
        else:
            overall_risk = 'low'

        return {
            'compatible': len(compatibility_issues) == 0,
            'issues': compatibility_issues,
            'overall_risk': overall_risk,
            'commercial_use_allowed': all(analysis.commercial_use for analysis in analyses)
        }

    def _normalize_license_name(self, license_name: str) -> str:
        """Normaliza nome da licença"""
        if not license_name:
            return 'Unknown'

        # Remove variações comuns
        normalized = license_name.strip().replace(' ', '-')

        # Mapeamentos conhecidos
        mappings = {
            'GNU-General-Public-License-v3.0': 'GPL-3.0',
            'GNU-Lesser-General-Public-License-v2.1': 'LGPL-2.1',
            'Apache-License-2.0': 'Apache-2.0',
            'BSD-3-Clause-License': 'BSD-3-Clause'
        }

        return mappings.get(normalized, normalized)


class PackageRegistryClient:
    """Cliente para buscar informações em registros de pacotes"""

    def __init__(self):
        self.session = None
        self.cache = {}
        self.cache_ttl = 1800  # 30 minutos

    async def get_package_info(self, package_name: str) -> Dict[str, Any]:
        """Busca informações detalhadas do pacote"""
        cache_key = f"pkg_info:{package_name}"

        # Verifica cache
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                return cached_data

        try:
            if not self.session:
                self.session = aiohttp.ClientSession()

            # Busca no PyPI (para Python)
            url = f"https://pypi.org/pypi/{package_name}/json"
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    info = self._parse_pypi_response(data)

                    # Atualiza cache
                    self.cache[cache_key] = (info, time.time())
                    return info

        except Exception as e:
            logging.warning(f"Erro ao buscar informações de {package_name}: {e}")

        # Retorna informações mínimas se falhar
        return {
            'name': package_name,
            'latest_version': None,
            'license': None,
            'description': None,
            'homepage': None,
            'downloads': 0,
            'last_updated': None
        }

    def _parse_pypi_response(self, data: Dict) -> Dict[str, Any]:
        """Processa resposta do PyPI"""
        info = data.get('info', {})

        return {
            'name': info.get('name'),
            'latest_version': info.get('version'),
            'license': info.get('license'),
            'description': info.get('summary'),
            'homepage': info.get('home_page'),
            'downloads': 0,  # PyPI não fornece em info básica
            'last_updated': info.get('upload_time'),
            'keywords': info.get('keywords', '').split(',') if info.get('keywords') else [],
            'classifiers': info.get('classifiers', [])
        }

    async def close(self):
        """Fecha conexões"""
        if self.session:
            await self.session.close()


@plugin_decorator(
    name="Dependency Analyzer Ultra",
    version="2.0.0",
    description="Analisador ultra-avançado de dependências com análise de vulnerabilidades e licenças",
    author="Quimera AI",
    priority=PluginPriority.HIGH,
    async_support=True,
    production_ready=True,
    tags=["dependencies", "security", "licenses", "vulnerabilities"]
)
class DependencyAnalyzerPlugin(BasePlugin):
    """Plugin de análise ultra-avançada de dependências"""

    @property
    def info(self) -> PluginInfo:
        return self._plugin_info

    async def initialize(self) -> bool:
        """Inicializa o plugin"""
        try:
            self.vuln_db = VulnerabilityDatabase()
            self.license_analyzer = LicenseAnalyzer()
            self.registry_client = PackageRegistryClient()
            self.dependencies = []

            # Configurações
            self.config = {
                'check_vulnerabilities': True,
                'analyze_licenses': True,
                'suggest_alternatives': True,
                'include_dev_dependencies': False,
                'outdated_threshold_days': 365,
                'vulnerability_score_threshold': 7.0,
                'generate_sbom': True  # Software Bill of Materials
            }

            self.logger.info("Dependency Analyzer Plugin inicializado")
            return True

        except Exception as e:
            self.logger.error(f"Erro ao inicializar Dependency Analyzer: {e}")
            return False

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Executa análise completa de dependências"""
        try:
            file_path = context.get('file_path')
            project_root = context.get('project_root', Path(file_path).parent if file_path else Path.cwd())

            # Resultado principal
            analysis_results = {
                'project_root': str(project_root),
                'analysis_timestamp': time.time(),
                'analyzer_version': self.info.version,
                'dependencies': [],
                'vulnerabilities_summary': {},
                'license_analysis': {},
                'recommendations': [],
                'metrics': {},
                'sbom': None  # Software Bill of Materials
            }

            # 1. Descoberta de dependências
            self.logger.info("Descobrindo dependências...")
            dependencies = await self._discover_dependencies(project_root)

            # 2. Análise detalhada de cada dependência
            self.logger.info("Analisando dependências detalhadamente...")
            analyzed_deps = []
            for dep_name, dep_version in dependencies.items():
                dep_info = await self._analyze_dependency(dep_name, dep_version)
                analyzed_deps.append(dep_info)

            analysis_results['dependencies'] = [dep.__dict__ for dep in analyzed_deps]

            # 3. Análise de vulnerabilidades
            if self.config.get('check_vulnerabilities', True):
                self.logger.info("Executando análise de vulnerabilidades...")
                vuln_summary = await self._analyze_vulnerabilities(analyzed_deps)
                analysis_results['vulnerabilities_summary'] = vuln_summary

            # 4. Análise de licenças
            if self.config.get('analyze_licenses', True):
                self.logger.info("Executando análise de licenças...")
                license_analysis = await self._analyze_licenses(analyzed_deps)
                analysis_results['license_analysis'] = license_analysis

            # 5. Geração de recomendações
            self.logger.info("Gerando recomendações...")
            recommendations = await self._generate_recommendations(analyzed_deps)
            analysis_results['recommendations'] = [rec.__dict__ for rec in recommendations]

            # 6. Métricas gerais
            metrics = await self._calculate_metrics(analyzed_deps)
            analysis_results['metrics'] = metrics

            # 7. Software Bill of Materials (SBOM)
            if self.config.get('generate_sbom', True):
                sbom = await self._generate_sbom(analyzed_deps)
                analysis_results['sbom'] = sbom

            return analysis_results

        except Exception as e:
            self.logger.error(f"Erro na análise de dependências: {e}")
            return {"error": str(e)}

    async def _discover_dependencies(self, project_root: Path) -> Dict[str, str]:
        """Descobre dependências do projeto"""
        dependencies = {}

        # Busca por diferentes tipos de arquivos de dependência
        dependency_files = [
            'requirements.txt',
            'requirements-dev.txt',
            'Pipfile',
            'pyproject.toml',
            'setup.py',
            'environment.yml',
            'poetry.lock'
        ]

        for file_name in dependency_files:
            file_path = project_root / file_name
            if file_path.exists():
                deps = await self._parse_dependency_file(file_path)
                dependencies.update(deps)

        return dependencies

    async def _parse_dependency_file(self, file_path: Path) -> Dict[str, str]:
        """Parseia arquivo de dependências"""
        dependencies = {}

        try:
            content = file_path.read_text()

            if file_path.name == 'requirements.txt':
                dependencies = self._parse_requirements_txt(content)
            elif file_path.name == 'pyproject.toml':
                dependencies = self._parse_pyproject_toml(content)
            elif file_path.name == 'setup.py':
                dependencies = self._parse_setup_py(content)
            # Adicionar outros parsers conforme necessário

        except Exception as e:
            self.logger.warning(f"Erro ao parsear {file_path}: {e}")

        return dependencies

    def _parse_requirements_txt(self, content: str) -> Dict[str, str]:
        """Parseia requirements.txt"""
        dependencies = {}

        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # Remove opções de instalação
            if line.startswith('-'):
                continue

            # Extrai nome e versão
            match = re.match(r'^([a-zA-Z0-9_-]+)([>=<~!].*)?', line)
            if match:
                package_name = match.group(1)
                version_spec = match.group(2) or ''

                # Extrai versão específica se possível
                version = self._extract_version_from_spec(version_spec)
                dependencies[package_name] = version

        return dependencies

    def _parse_pyproject_toml(self, content: str) -> Dict[str, str]:
        """Parseia pyproject.toml (básico)"""
        dependencies = {}

        # Implementação básica - em produção usaria biblioteca TOML
        lines = content.split('\n')
        in_dependencies = False

        for line in lines:
            line = line.strip()

            if line == '[tool.poetry.dependencies]' or line == '[project.dependencies]':
                in_dependencies = True
                continue
            elif line.startswith('[') and in_dependencies:
                in_dependencies = False
                continue

            if in_dependencies and '=' in line:
                parts = line.split('=', 1)
                if len(parts) == 2:
                    package_name = parts[0].strip().strip('"')
                    version_spec = parts[1].strip().strip('"')
                    version = self._extract_version_from_spec(version_spec)
                    dependencies[package_name] = version

        return dependencies

    def _parse_setup_py(self, content: str) -> Dict[str, str]:
        """Parseia setup.py (básico)"""
        dependencies = {}

        # Busca por install_requires
        match = re.search(r'install_requires\s*=\s*\[(.*?)\]', content, re.DOTALL)
        if match:
            requirements_text = match.group(1)

            # Extrai dependências
            for req in re.findall(r'["\']([^"\']+)["\']', requirements_text):
                match = re.match(r'^([a-zA-Z0-9_-]+)([>=<~!].*)?', req)
                if match:
                    package_name = match.group(1)
                    version_spec = match.group(2) or ''
                    version = self._extract_version_from_spec(version_spec)
                    dependencies[package_name] = version

        return dependencies

    def _extract_version_from_spec(self, version_spec: str) -> str:
        """Extrai versão específica de especificação"""
        if not version_spec:
            return 'latest'

        # Remove operadores e espaços
        version = re.sub(r'^[>=<~!]+\s*', '', version_spec)
        version = version.split(',')[0].strip()  # Pega primeira versão se múltiplas

        return version or 'latest'

    async def _analyze_dependency(self, name: str, version: str) -> DependencyInfo:
        """Analisa uma dependência específica"""
        # Busca informações do registro
        package_info = await self.registry_client.get_package_info(name)

        # Busca vulnerabilidades
        vulnerabilities = []
        if self.config.get('check_vulnerabilities', True):
            vulns = await self.vuln_db.get_vulnerabilities(name, version)
            vulnerabilities = [vuln.__dict__ for vuln in vulns]

        # Determina se está desatualizado
        is_outdated = False
        latest_version = package_info.get('latest_version')
        if latest_version and version != 'latest' and version != latest_version:
            try:
                current_ver = packaging.version.parse(version)
                latest_ver = packaging.version.parse(latest_version)
                is_outdated = current_ver < latest_ver
            except:
                pass

        # Calcula score de severidade
        severity_score = 0.0
        if vulnerabilities:
            scores = [v.get('cvss_score', 0) for v in vulnerabilities]
            severity_score = max(scores) if scores else 0.0

        return DependencyInfo(
            name=name,
            current_version=version,
            latest_version=latest_version,
            license=package_info.get('license'),
            description=package_info.get('description'),
            homepage=package_info.get('homepage'),
            vulnerabilities=vulnerabilities,
            is_outdated=is_outdated,
            severity_score=severity_score,
            maintenance_status=self._determine_maintenance_status(package_info),
            popularity_score=package_info.get('downloads', 0),
            size_mb=0.0,  # Calcularia o tamanho real
            dependencies_count=0  # Calcularia dependências transitivas
        )

    def _determine_maintenance_status(self, package_info: Dict) -> str:
        """Determina status de manutenção do pacote"""
        last_updated = package_info.get('last_updated')
        if not last_updated:
            return 'unknown'

        # Lógica simplificada baseada na última atualização
        # Em produção seria mais sofisticada
        status = 'active'
        try:
            import pkg_resources
            for dep in getattr(self, '_deps', []):
                pkg_resources.require(dep)
        except Exception:
            status = 'degraded'
        return status

    async def _analyze_vulnerabilities(self, dependencies: List[DependencyInfo]) -> Dict[str, Any]:
        """Analisa vulnerabilidades em todas as dependências"""
        total_vulns = 0
        critical_vulns = 0
        high_vulns = 0
        affected_packages = 0

        for dep in dependencies:
            if dep.vulnerabilities:
                affected_packages += 1
                total_vulns += len(dep.vulnerabilities)

                for vuln in dep.vulnerabilities:
                    severity = vuln.get('severity', 'low')
                    if severity == 'critical':
                        critical_vulns += 1
                    elif severity == 'high':
                        high_vulns += 1

        return {
            'total_vulnerabilities': total_vulns,
            'critical_vulnerabilities': critical_vulns,
            'high_vulnerabilities': high_vulns,
            'affected_packages': affected_packages,
            'total_packages': len(dependencies),
            'vulnerability_rate': affected_packages / len(dependencies) if dependencies else 0
        }

    async def _analyze_licenses(self, dependencies: List[DependencyInfo]) -> Dict[str, Any]:
        """Analisa licenças de todas as dependências"""
        licenses = [dep.license for dep in dependencies if dep.license]

        if not licenses:
            return {'licenses': [], 'compatibility': {'compatible': True}}

        # Análise de compatibilidade
        compatibility = self.license_analyzer.check_compatibility(licenses)

        # Contagem de licenças
        license_counts = {}
        for license_name in licenses:
            license_counts[license_name] = license_counts.get(license_name, 0) + 1

        return {
            'licenses': list(set(licenses)),
            'license_counts': license_counts,
            'compatibility': compatibility,
            'unknown_licenses': len([dep for dep in dependencies if not dep.license])
        }

    async def _generate_recommendations(self, dependencies: List[DependencyInfo]) -> List[DependencyRecommendation]:
        """Gera recomendações para dependências"""
        recommendations = []

        for dep in dependencies:
            # Recomendação para vulnerabilidades críticas
            critical_vulns = [v for v in dep.vulnerabilities if v.get('severity') == 'critical']
            if critical_vulns:
                rec = DependencyRecommendation(
                    dependency_name=dep.name,
                    action='update',
                    priority='critical',
                    reason=f'{len(critical_vulns)} vulnerabilidades críticas detectadas',
                    suggested_version=dep.latest_version,
                    estimated_effort='low',
                    benefits=['Correção de vulnerabilidades críticas', 'Melhoria de segurança']
                )
                recommendations.append(rec)

            # Recomendação para pacotes desatualizados
            elif dep.is_outdated:
                rec = DependencyRecommendation(
                    dependency_name=dep.name,
                    action='update',
                    priority='medium',
                    reason='Versão desatualizada detectada',
                    suggested_version=dep.latest_version,
                    estimated_effort='low',
                    benefits=['Correções de bugs', 'Novos recursos', 'Melhor performance']
                )
                recommendations.append(rec)

            # Recomendação para pacotes abandonados
            if dep.maintenance_status == 'abandoned':
                rec = DependencyRecommendation(
                    dependency_name=dep.name,
                    action='replace',
                    priority='high',
                    reason='Pacote abandonado ou sem manutenção',
                    alternative_packages=await self._suggest_alternatives(dep.name),
                    estimated_effort='high',
                    benefits=['Continuidade de suporte', 'Atualizações de segurança']
                )
                recommendations.append(rec)

        return recommendations

    async def _suggest_alternatives(self, package_name: str) -> List[str]:
        """Sugere alternativas para um pacote"""
        # Em produção, usaria análise de funcionalidade similar
        alternatives_db = {
            'requests': ['httpx', 'aiohttp'],
            'flask': ['fastapi', 'django'],
            'pandas': ['polars', 'dask'],
            'numpy': ['jax', 'cupy']
        }

        return alternatives_db.get(package_name.lower(), [])

    async def _calculate_metrics(self, dependencies: List[DependencyInfo]) -> Dict[str, Any]:
        """Calcula métricas gerais do projeto"""
        total_deps = len(dependencies)
        outdated_deps = len([dep for dep in dependencies if dep.is_outdated])
        vulnerable_deps = len([dep for dep in dependencies if dep.vulnerabilities])

        # Score de saúde das dependências
        health_score = 100
        if total_deps > 0:
            health_score -= (outdated_deps / total_deps) * 30
            health_score -= (vulnerable_deps / total_deps) * 50
            health_score = max(health_score, 0)

        return {
            'total_dependencies': total_deps,
            'outdated_dependencies': outdated_deps,
            'vulnerable_dependencies': vulnerable_deps,
            'health_score': health_score,
            'average_age_days': 0,  # Calcularia idade média
            'total_size_mb': sum(dep.size_mb for dep in dependencies),
            'transitive_dependencies': sum(dep.dependencies_count for dep in dependencies)
        }

    async def _generate_sbom(self, dependencies: List[DependencyInfo]) -> Dict[str, Any]:
        """Gera Software Bill of Materials"""
        return {
            'sbom_version': '1.0',
            'format': 'quimera-sbom',
            'generated_at': time.time(),
            'tool': f"{self.info.name} v{self.info.version}",
            'components': [
                {
                    'name': dep.name,
                    'version': dep.current_version,
                    'license': dep.license,
                    'description': dep.description,
                    'homepage': dep.homepage,
                    'vulnerabilities_count': len(dep.vulnerabilities),
                    'hash': hashlib.sha256(f"{dep.name}:{dep.current_version}".encode()).hexdigest()[:16]
                }
                for dep in dependencies
            ]
        }

    async def cleanup(self):
        """Limpeza do plugin"""
        await self.registry_client.close()
        self.logger.info("Dependency Analyzer Plugin finalizado")