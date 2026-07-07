#!/usr/bin/env python3
"""
Quimera - Cognitive Librarian Ultra-Advanced
Sistema Bibliotecário Cognitivo de Última Geração

Este é o sistema integrado final que coordena TODOS os módulos especializados
do Bibliotecário Cognitivo, oferecendo uma interface unificada de alto nível
para análise, otimização e melhoria automática de código-fonte.

Módulos Integrados:
- MultiLLMOrchestrator: Orquestração de múltiplos LLMs especializados
- VulnerabilityDetectionEngine: Detecção avançada de vulnerabilidades
- PerformanceProfilingEngine: Análise e otimização de performance
- DocumentationGenerator: Geração automática de documentação
- CodeQualityAnalyzer: Análise profunda de qualidade de código
- IntelligentRefactoringEngine: Sugestões e aplicação de refatorações
- AITestGenerationEngine: Geração automática de testes abrangentes

Características Ultra-Avançadas:
- Análise holística e contextual de projetos completos
- Workflows automáticos de análise e melhoria
- Relatórios executivos multi-dimensionais
- Integração com sistemas CI/CD e IDEs
- API REST e interfaces programáticas
- Monitoramento e métricas em tempo real
- Cache distribuído e otimização de performance
- Análise preditiva e machine learning
- Integração com ferramentas de desenvolvimento
- Suporte a múltiplas linguagens e frameworks
- Análise de dependências e arquitetura
- Detecção de padrões e anti-padrões
- Otimização automatizada de código
- Geração de insights e recomendações
- Análise de impacto e riscos
- Versionamento e histórico detalhado

Author: Quimera AI System
Version: 2.0.0 Ultra-Advanced Final
"""


# Verificações de dependências adicionadas automaticamente
def verificar_dependencia(nome_modulo, funcionalidade="essa funcionalidade"):
    """Verifica se uma dependência está disponível"""
    try:
        __import__(nome_modulo)
        return True
    except ImportError:
        print(f"⚠️  {nome_modulo} não instalado - {funcionalidade} não disponível")
        return False

import logging
_logger = logging.getLogger(__name__)


def _unavailable_feature(feature_name: str, *args, **kwargs):
    """Loga warning quando funcionalidade não está disponível por falta de dependências."""
    _logger.warning(f"Funcionalidade '{feature_name}' indisponível — dependência não instalada")
    return None

import os
import re
import ast
import json
import sqlite3
import hashlib
import datetime
import asyncio
import threading
import multiprocessing
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple, Union, Callable
from dataclasses import dataclass, asdict, field
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from collections import defaultdict, Counter, deque
import logging
import time

# Core libraries
import networkx as nx
from networkx.algorithms import shortest_path, connected_components
try:
    import pandas as pd
except ImportError:
    pd = None  # Mock
try:
    import numpy as np
except ImportError:
    np = None  # Mock

# Web and API libraries
try:
    from flask import Flask, request, jsonify
except ImportError:
    # flask não disponível - funcionalidade limitada
    pass
try:
    from flask_cors import CORS
except ImportError:
    # flask_cors não disponível - funcionalidade limitada
    pass
import requests

# Monitoring and metrics
import psutil
try:
    from prometheus_client import Counter as PrometheusCounter, Histogram, Gauge, start_http_server
except ImportError:
    # prometheus_client não disponível - funcionalidade limitada
    pass

# Advanced analytics
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score

# Visualization and reporting
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# Import ALL our ultra-advanced components
try:
    from .multi_llm_orchestrator import MultiLLMOrchestrator
except ImportError:
    MultiLLMOrchestrator = None  # MultiLLMOrchestrator não disponível

try:
    from .vulnerability_detection_engine import VulnerabilityDetectionEngine
except ImportError:
    VulnerabilityDetectionEngine = None  # VulnerabilityDetectionEngine não disponível
try:
    from .performance_profiling_engine import PerformanceProfilingEngine
except ImportError:
    PerformanceProfilingEngine = None  # PerformanceProfilingEngine não disponível
    
try:
    from .documentation_generator import DocumentationGenerator
except ImportError:
    DocumentationGenerator = None  # DocumentationGenerator não disponível
    
try:
    from .code_quality_analyzer import CodeQualityAnalyzer
except ImportError:
    CodeQualityAnalyzer = None  # CodeQualityAnalyzer não disponível, QualityMetrics
try:
    from .intelligent_refactoring_engine import IntelligentRefactoringEngine
except ImportError:
    IntelligentRefactoringEngine = None  # IntelligentRefactoringEngine não disponível, RefactoringOpportunity
    
try:
    from .ai_test_generation_engine import AITestGenerationEngine
except ImportError:
    AITestGenerationEngine = None  # AITestGenerationEngine não disponível, TestSuite
except ImportError:
    # from multi_llm_orchestrator import \1  # Import corrigido automaticamente
    from vulnerability_detection_engine import VulnerabilityDetectionEngine
    from performance_profiling_engine import PerformanceProfilingEngine
    from documentation_generator import DocumentationGenerator
    from code_quality_analyzer import CodeQualityAnalyzer, QualityMetrics
    from intelligent_refactoring_engine import IntelligentRefactoringEngine, RefactoringOpportunity
    from ai_test_generation_engine import AITestGenerationEngine, TestSuite

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ProjectAnalysis:
    """Análise completa de um projeto"""
    project_id: str
    project_path: str
    analysis_timestamp: str

    # Métricas gerais
    total_files: int
    total_lines_of_code: int
    languages_detected: List[str]
    framework_detected: Optional[str]

    # Análises por arquivo
    file_analyses: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Métricas agregadas
    overall_quality_score: float = 0.0
    overall_security_score: float = 0.0
    overall_performance_score: float = 0.0
    overall_maintainability_score: float = 0.0
    overall_test_coverage: float = 0.0

    # Análises especializadas
    vulnerability_summary: Dict[str, Any] = field(default_factory=dict)
    performance_summary: Dict[str, Any] = field(default_factory=dict)
    quality_summary: Dict[str, Any] = field(default_factory=dict)
    refactoring_summary: Dict[str, Any] = field(default_factory=dict)
    testing_summary: Dict[str, Any] = field(default_factory=dict)
    documentation_summary: Dict[str, Any] = field(default_factory=dict)

    # Grafo de dependências
    dependency_graph: Dict[str, List[str]] = field(default_factory=dict)
    critical_files: List[str] = field(default_factory=list)
    dependency_cycles: List[List[str]] = field(default_factory=list)

    # Recomendações e insights
    executive_summary: str = ""
    key_insights: List[str] = field(default_factory=list)
    priority_recommendations: List[str] = field(default_factory=list)
    risk_assessment: Dict[str, Any] = field(default_factory=dict)

    # Comparações e benchmarks
    industry_benchmarks: Dict[str, float] = field(default_factory=dict)
    historical_comparison: Dict[str, float] = field(default_factory=dict)
    peer_comparison: Dict[str, float] = field(default_factory=dict)

    # Metadados de execução
    analysis_duration: float = 0.0
    modules_used: List[str] = field(default_factory=list)
    cache_hit_rate: float = 0.0
    performance_metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class WorkflowConfig:
    """Configuração de workflow de análise"""
    workflow_id: str
    name: str
    description: str

    # Módulos a executar
    enable_quality_analysis: bool = True
    enable_security_analysis: bool = True
    enable_performance_analysis: bool = True
    enable_refactoring_analysis: bool = True
    enable_test_generation: bool = True
    enable_documentation_generation: bool = True

    # Configurações específicas
    target_quality_score: float = 0.8
    target_security_score: float = 0.9
    target_performance_score: float = 0.8
    target_test_coverage: float = 0.85

    # Configurações de execução
    parallel_execution: bool = True
    max_workers: int = 4
    cache_enabled: bool = True
    detailed_reporting: bool = True

    # Filtros e limites
    max_file_size_mb: float = 50.0
    include_patterns: List[str] = field(default_factory=lambda: ["*.py", "*.js", "*.ts", "*.java"])
    exclude_patterns: List[str] = field(default_factory=lambda: ["*/node_modules/*", "*/__pycache__/*", "*/venv/*"])

    # Integração e saída
    generate_reports: bool = True
    export_metrics: bool = True
    send_notifications: bool = False
    webhook_url: Optional[str] = None


@dataclass
class SystemMetrics:
    """Métricas do sistema em tempo real"""
    timestamp: str

    # Performance do sistema
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    active_threads: int
    active_processes: int

    # Métricas de análise
    analyses_completed: int
    analyses_in_progress: int
    analyses_queued: int
    average_analysis_time: float
    cache_hit_rate: float

    # Métricas de qualidade
    total_files_analyzed: int
    total_vulnerabilities_found: int
    total_refactoring_opportunities: int
    total_tests_generated: int

    # Métricas de uso de LLM
    llm_requests_made: int
    llm_tokens_consumed: int
    llm_average_response_time: float
    llm_success_rate: float

    # Métricas de erro
    errors_count: int
    warnings_count: int
    failed_analyses: int


class CognitiveLibrarianUltraAdvanced:
    """
    Sistema Bibliotecário Cognitivo de Última Geração

    Coordena e integra TODOS os módulos especializados para fornecer
    análise holística e otimização automática de projetos de software.
    """

    def __init__(self,
                 project_path: str = "./",
                 config_file: Optional[str] = None,
                 cache_dir: str = "./quimera_cache"):
        """
        Inicializa o Bibliotecário Cognitivo Ultra-Avançado

        Args:
            project_path: Caminho do projeto a ser analisado
            config_file: Arquivo de configuração (JSON)
            cache_dir: Diretório para cache distribuído
        """
        self.project_path = Path(project_path).resolve()
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Carregar configuração
        self.config = self._load_configuration(config_file)

        # Inicializar todos os módulos especializados
        self._initialize_specialized_modules()

        # Configurar sistema de métricas
        self._setup_metrics_system()

        # Configurar banco de dados principal
        self._setup_master_database()

        # Inicializar API e interfaces
        self._setup_api_server()

        # Cache e otimização
        self._setup_distributed_cache()

        # Workflows e automação
        self.workflows = {}
        self._load_predefined_workflows()

        # Estado do sistema
        self.system_state = {
            'status': 'ready',
            'active_analyses': {},
            'analysis_queue': deque(),
            'last_analysis': None,
            'total_analyses_completed': 0,
            'startup_time': datetime.datetime.now().isoformat()
        }

        # Thread pool para análises concorrentes
        self.executor = ThreadPoolExecutor(max_workers=self.config.get('max_workers', 8))

        # Métricas Prometheus
        self.metrics = {
            'analyses_total': PrometheusCounter('quimera_analyses_total', 'Total analyses completed'),
            'analysis_duration': Histogram('quimera_analysis_duration_seconds', 'Analysis duration'),
            'quality_score': Gauge('quimera_quality_score', 'Current quality score'),
            'security_score': Gauge('quimera_security_score', 'Current security score'),
            'files_analyzed': PrometheusCounter('quimera_files_analyzed_total', 'Total files analyzed')
        }

        # Iniciar servidor de métricas
        if self.config.get('enable_metrics_server', True):
            start_http_server(self.config.get('metrics_port', 8000))

        logger.info("Bibliotecário Cognitivo Ultra-Avançado inicializado com sucesso")

    def _load_configuration(self, config_file: Optional[str]) -> Dict[str, Any]:
        """Carrega configuração do sistema"""
        default_config = {
            'max_workers': 8,
            'cache_ttl': 3600,
            'enable_api_server': True,
            'api_port': 5000,
            'enable_metrics_server': True,
            'metrics_port': 8000,
            'enable_distributed_cache': True,
            'log_level': 'INFO',
            'analysis_timeout': 1800,  # 30 minutos
            'max_concurrent_analyses': 10,
            'enable_ml_optimizations': True,
            'enable_predictive_analysis': True,
            'enable_auto_improvements': False,  # Seguro por padrão
            'notification_channels': [],
            'integrations': {
                'github': {'enabled': False},
                'jira': {'enabled': False},
                'slack': {'enabled': False}
            }
        }

        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    user_config = json.load(f)
                default_config.update(user_config)
            except Exception as e:
                logger.warning(f"Erro ao carregar configuração: {e}")

        return default_config

    def _initialize_specialized_modules(self):
        """Inicializa todos os módulos especializados"""
        logger.info("Inicializando módulos especializados...")

        try:
            # Orquestrador de LLMs (núcleo)
            self.llm_orchestrator = MultiLLMOrchestrator() if MultiLLMOrchestrator is not None else None
            logger.info("✓ MultiLLMOrchestrator inicializado")

            # Módulo de detecção de vulnerabilidades
            self.vulnerability_engine = VulnerabilityDetectionEngine(str(self.cache_dir)) if VulnerabilityDetectionEngine is not None else None if VulnerabilityDetectionEngine is not None else None if VulnerabilityDetectionEngine is not None else None
            logger.info("✓ VulnerabilityDetectionEngine inicializado")

            # Módulo de análise de performance
            self.performance_engine = PerformanceProfilingEngine(str(self.cache_dir)) if PerformanceProfilingEngine is not None else None if PerformanceProfilingEngine is not None else None if PerformanceProfilingEngine is not None else None
            logger.info("✓ PerformanceProfilingEngine inicializado")

            # Gerador de documentação
            self.documentation_generator = DocumentationGenerator(str(self.cache_dir)) if DocumentationGenerator is not None else None if DocumentationGenerator is not None else None if DocumentationGenerator is not None else None
            logger.info("✓ DocumentationGenerator inicializado")

            # Analisador de qualidade de código
            self.quality_analyzer = CodeQualityAnalyzer(str(self.cache_dir)) if CodeQualityAnalyzer is not None else None if CodeQualityAnalyzer is not None else None if CodeQualityAnalyzer is not None else None
            logger.info("✓ CodeQualityAnalyzer inicializado")

            # Engine de refatoração inteligente
            self.refactoring_engine = IntelligentRefactoringEngine(str(self.project_path), str(self.cache_dir)) if IntelligentRefactoringEngine is not None else None if IntelligentRefactoringEngine is not None else None if IntelligentRefactoringEngine is not None else None
            logger.info("✓ IntelligentRefactoringEngine inicializado")

            # Engine de geração de testes
            self.test_generation_engine = AITestGenerationEngine(str(self.project_path), str(self.cache_dir)) if AITestGenerationEngine is not None else None if AITestGenerationEngine is not None else None if AITestGenerationEngine is not None else None
            logger.info("✓ AITestGenerationEngine inicializado")

            self.modules_initialized = True
            logger.info("Todos os módulos especializados inicializados com sucesso")

        except Exception as e:
            logger.error(f"Erro ao inicializar módulos: {e}")
            self.modules_initialized = False
            raise

    def _setup_metrics_system(self):
        """Configura sistema de métricas e monitoramento"""
        self.metrics_db_path = self.cache_dir / "metrics.db"

        with sqlite3.connect(self.metrics_db_path) as conn:
            # Tabela de métricas do sistema
            conn.execute("""
                CREATE TABLE IF NOT EXISTS system_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metric_name TEXT,
                    metric_value REAL,
                    metric_type TEXT,
                    context TEXT
                )
            """)

            # Tabela de análises executadas
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analysis_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id TEXT,
                    project_path TEXT,
                    workflow_config TEXT,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    duration REAL,
                    status TEXT,
                    results_json TEXT,
                    error_message TEXT
                )
            """)

            # Tabela de comparações e benchmarks
            conn.execute("""
                CREATE TABLE IF NOT EXISTS benchmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    benchmark_type TEXT,
                    language TEXT,
                    framework TEXT,
                    metric_name TEXT,
                    benchmark_value REAL,
                    percentile REAL,
                    source TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def _setup_master_database(self):
        """Configura banco de dados mestre"""
        self.master_db_path = self.cache_dir / "cognitive_librarian_master.db"

        with sqlite3.connect(self.master_db_path) as conn:
            # Tabela de projetos analisados
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analyzed_projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT UNIQUE,
                    project_path TEXT,
                    project_name TEXT,
                    analysis_data TEXT,
                    last_analyzed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    analysis_count INTEGER DEFAULT 1,
                    total_analysis_time REAL DEFAULT 0.0
                )
            """)

            # Tabela de insights e recomendações
            conn.execute("""
                CREATE TABLE IF NOT EXISTS insights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT,
                    insight_type TEXT,
                    insight_content TEXT,
                    confidence REAL,
                    priority INTEGER,
                    status TEXT DEFAULT 'new',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES analyzed_projects (project_id)
                )
            """)

            # Tabela de workflows executados
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workflow_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_id TEXT,
                    project_id TEXT,
                    execution_config TEXT,
                    execution_results TEXT,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    status TEXT
                )
            """)

    def _setup_api_server(self):
        """Configura servidor API REST"""
        if not self.config.get('enable_api_server', True):
            return

        self.app = Flask(__name__)
        CORS(self.app)

        # Endpoints da API
        @self.app.route('/api/v1/analyze', methods=['POST'])
        def api_analyze():
            data = request.get_json()
            project_path = data.get('project_path')
            workflow_config = data.get('workflow_config', 'comprehensive')

            if not project_path:
                return jsonify({'error': 'project_path is required'}), 400

            try:
                analysis_id = self.start_analysis_async(project_path, workflow_config)
                return jsonify({'analysis_id': analysis_id, 'status': 'started'})
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/v1/analysis/<analysis_id>', methods=['GET'])
        def api_get_analysis(analysis_id):
            analysis = self.get_analysis_status(analysis_id)
            if analysis:
                return jsonify(analysis)
            else:
                return jsonify({'error': 'Analysis not found'}), 404

        @self.app.route('/api/v1/projects', methods=['GET'])
        def api_list_projects():
            projects = self.list_analyzed_projects()
            return jsonify({'projects': projects})

        @self.app.route('/api/v1/metrics', methods=['GET'])
        def api_get_metrics():
            metrics = self.get_system_metrics()
            return jsonify(metrics)

        @self.app.route('/api/v1/workflows', methods=['GET'])
        def api_list_workflows():
            return jsonify({'workflows': list(self.workflows.keys())})

        @self.app.route('/api/v1/health', methods=['GET'])
        def api_health():
            return jsonify({
                'status': 'healthy',
                'modules_initialized': self.modules_initialized,
                'active_analyses': len(self.system_state['active_analyses']),
                'analyses_completed': self.system_state['total_analyses_completed'],
                'uptime': self._get_uptime()
            })

        # Iniciar servidor em thread separada
        def run_api_server():
            self.app.run(
                host='0.0.0.0',
                port=self.config.get('api_port', 5000),
                debug=False,
                threaded=True
            )

        api_thread = threading.Thread(target=run_api_server, daemon=True)
        api_thread.start()
        logger.info(f"Servidor API iniciado na porta {self.config.get('api_port', 5000)}")

    def _setup_distributed_cache(self):
        """Configura cache distribuído (Redis se disponível, senão SQLite)"""
        try:
            import redis
            self.cache = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            self.cache.ping()  # Testar conexão
            self.cache_type = 'redis'
            logger.info("Cache distribuído Redis inicializado")
        except (ImportError, redis.exceptions.ConnectionError):
            # Fallback para SQLite
            self.cache_db_path = self.cache_dir / "distributed_cache.db"
            self.cache_type = 'sqlite'

            with sqlite3.connect(self.cache_db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cache_entries (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        expiry TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

            logger.info("Cache SQLite inicializado (fallback)")

    def _load_predefined_workflows(self):
        """Carrega workflows pré-definidos"""
        # Workflow abrangente (padrão)
        self.workflows['comprehensive'] = WorkflowConfig(
            workflow_id='comprehensive',
            name='Análise Abrangente',
            description='Análise completa com todos os módulos ativados',
            enable_quality_analysis=True,
            enable_security_analysis=True,
            enable_performance_analysis=True,
            enable_refactoring_analysis=True,
            enable_test_generation=True,
            enable_documentation_generation=True,
            target_quality_score=0.8,
            target_security_score=0.9,
            target_performance_score=0.8,
            target_test_coverage=0.85,
            parallel_execution=True,
            max_workers=6,
            detailed_reporting=True
        )

        # Workflow rápido
        self.workflows['quick'] = WorkflowConfig(
            workflow_id='quick',
            name='Análise Rápida',
            description='Análise rápida focada em qualidade e segurança',
            enable_quality_analysis=True,
            enable_security_analysis=True,
            enable_performance_analysis=False,
            enable_refactoring_analysis=False,
            enable_test_generation=False,
            enable_documentation_generation=False,
            parallel_execution=True,
            max_workers=4,
            detailed_reporting=False
        )

        # Workflow de segurança
        self.workflows['security_focused'] = WorkflowConfig(
            workflow_id='security_focused',
            name='Foco em Segurança',
            description='Análise especializada em segurança e vulnerabilidades',
            enable_quality_analysis=False,
            enable_security_analysis=True,
            enable_performance_analysis=False,
            enable_refactoring_analysis=True,
            enable_test_generation=True,
            enable_documentation_generation=False,
            target_security_score=0.95,
            parallel_execution=True,
            max_workers=4,
            detailed_reporting=True
        )

        # Workflow de qualidade
        self.workflows['quality_focused'] = WorkflowConfig(
            workflow_id='quality_focused',
            name='Foco em Qualidade',
            description='Análise especializada em qualidade e manutenibilidade',
            enable_quality_analysis=True,
            enable_security_analysis=False,
            enable_performance_analysis=False,
            enable_refactoring_analysis=True,
            enable_test_generation=True,
            enable_documentation_generation=True,
            target_quality_score=0.9,
            target_test_coverage=0.9,
            parallel_execution=True,
            max_workers=4,
            detailed_reporting=True
        )

        # Workflow de CI/CD
        self.workflows['ci_cd'] = WorkflowConfig(
            workflow_id='ci_cd',
            name='CI/CD Pipeline',
            description='Análise otimizada para integração contínua',
            enable_quality_analysis=True,
            enable_security_analysis=True,
            enable_performance_analysis=False,
            enable_refactoring_analysis=False,
            enable_test_generation=False,
            enable_documentation_generation=False,
            target_quality_score=0.7,
            target_security_score=0.8,
            parallel_execution=True,
            max_workers=2,
            cache_enabled=True,
            detailed_reporting=False
        )

        logger.info(f"Carregados {len(self.workflows)} workflows pré-definidos")

    def analyze_project(self,
                       project_path: Optional[str] = None,
                       workflow_config: Union[str, WorkflowConfig] = 'comprehensive') -> ProjectAnalysis:
        """
        Executa análise completa do projeto usando workflow especificado

        Args:
            project_path: Caminho do projeto (usa self.project_path se None)
            workflow_config: Nome do workflow ou objeto WorkflowConfig

        Returns:
            Análise completa do projeto
        """
        start_time = datetime.datetime.now()

        # Resolver configuração do workflow
        if isinstance(workflow_config, str):
            if workflow_config not in self.workflows:
                raise ValueError(f"Workflow '{workflow_config}' não encontrado")
            config = self.workflows[workflow_config]
        else:
            config = workflow_config

        # Usar project_path fornecido ou padrão
        if project_path:
            target_path = Path(project_path).resolve()
        else:
            target_path = self.project_path

        logger.info(f"Iniciando análise do projeto: {target_path}")
        logger.info(f"Workflow: {config.name} ({config.workflow_id})")

        # Criar análise base
        project_id = self._generate_project_id(str(target_path))
        analysis = ProjectAnalysis(
            project_id=project_id,
            project_path=str(target_path),
            analysis_timestamp=start_time.isoformat()
        )

        try:
            # Descobrir arquivos do projeto
            source_files = self._discover_source_files(target_path, config)
            analysis.total_files = len(source_files)
            analysis.languages_detected = self._detect_languages(source_files)
            analysis.framework_detected = self._detect_framework(target_path, source_files)

            logger.info(f"Encontrados {len(source_files)} arquivos fonte")
            logger.info(f"Linguagens detectadas: {', '.join(analysis.languages_detected)}")

            # Executar análises especializadas
            if config.parallel_execution:
                analysis = self._execute_parallel_analysis(analysis, source_files, config)
            else:
                analysis = self._execute_sequential_analysis(analysis, source_files, config)

            # Construir grafo de dependências
            analysis.dependency_graph = self._build_dependency_graph(source_files)
            analysis.critical_files = self._identify_critical_files(analysis.dependency_graph)
            analysis.dependency_cycles = self._detect_dependency_cycles(analysis.dependency_graph)

            # Calcular métricas agregadas
            analysis = self._calculate_aggregate_metrics(analysis)

            # Gerar insights executivos
            analysis = self._generate_executive_insights(analysis, config)

            # Comparações e benchmarks
            analysis = self._add_benchmarks_and_comparisons(analysis)

            # Finalizar análise
            end_time = datetime.datetime.now()
            analysis.analysis_duration = (end_time - start_time).total_seconds()
            analysis.modules_used = self._get_modules_used(config)

            # Atualizar métricas
            self._update_analysis_metrics(analysis)

            # Salvar análise
            self._save_project_analysis(analysis)

            logger.info(f"Análise concluída em {analysis.analysis_duration:.2f}s")
            logger.info(f"Score geral de qualidade: {analysis.overall_quality_score:.2%}")

            return analysis

        except Exception as e:
            logger.error(f"Erro durante análise: {e}")
            analysis.analysis_duration = (datetime.datetime.now() - start_time).total_seconds()
            raise

    def _discover_source_files(self, project_path: Path, config: WorkflowConfig) -> List[str]:
        """Descobre arquivos fonte no projeto"""
        source_files = []

        # Padrões para incluir e excluir
        include_patterns = config.include_patterns
        exclude_patterns = config.exclude_patterns

        for pattern in include_patterns:
            files = list(project_path.rglob(pattern))
            for file_path in files:
                file_str = str(file_path)

                # Verificar exclusões
                excluded = False
                for exclude_pattern in exclude_patterns:
                    if exclude_pattern.replace('*/', '') in file_str:
                        excluded = True
                        break

                # Verificar tamanho
                if not excluded and file_path.is_file():
                    try:
                        file_size_mb = file_path.stat().st_size / (1024 * 1024)
                        if file_size_mb <= config.max_file_size_mb:
                            source_files.append(file_str)
                        else:
                            logger.warning(f"Arquivo muito grande ignorado: {file_path} ({file_size_mb:.1f}MB)")
                    except Exception as e:
                        logger.warning(f"Erro ao verificar arquivo {file_path}: {e}")

        # Remover duplicatas e ordenar
        source_files = sorted(list(set(source_files)))

        return source_files

    def _detect_languages(self, source_files: List[str]) -> List[str]:
        """Detecta linguagens de programação no projeto"""
        languages = set()

        extension_map = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.java': 'Java',
            '.cpp': 'C++',
            '.c': 'C',
            '.cs': 'C#',
            '.php': 'PHP',
            '.rb': 'Ruby',
            '.go': 'Go',
            '.rs': 'Rust',
            '.kt': 'Kotlin',
            '.swift': 'Swift',
            '.scala': 'Scala',
            '.r': 'R',
            '.m': 'Objective-C',
            '.sh': 'Shell'
        }

        for file_path in source_files:
            ext = Path(file_path).suffix.lower()
            if ext in extension_map:
                languages.add(extension_map[ext])

        return sorted(list(languages))

    def _detect_framework(self, project_path: Path, source_files: List[str]) -> Optional[str]:
        """Detecta framework principal do projeto"""
        # Verificar arquivos de configuração
        config_files = {
            'package.json': 'Node.js',
            'requirements.txt': 'Python',
            'Pipfile': 'Python',
            'setup.py': 'Python',
            'pom.xml': 'Maven/Java',
            'build.gradle': 'Gradle/Java',
            'Cargo.toml': 'Rust',
            'go.mod': 'Go',
            'composer.json': 'PHP'
        }

        for config_file, framework in config_files.items():
            if (project_path / config_file).exists():
                return framework

        # Verificar estrutura de diretórios
        common_dirs = [d.name for d in project_path.iterdir() if d.is_dir()]

        if 'src' in common_dirs and 'test' in common_dirs:
            return 'Maven/Gradle'
        elif 'lib' in common_dirs and any('.py' in f for f in source_files):
            return 'Python Package'
        elif 'node_modules' in common_dirs:
            return 'Node.js'

        return None

    def _execute_parallel_analysis(self,
                                 analysis: ProjectAnalysis,
                                 source_files: List[str],
                                 config: WorkflowConfig) -> ProjectAnalysis:
        """Executa análises em paralelo"""
        logger.info("Executando análises em paralelo...")

        futures = {}

        with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
            # Análise de qualidade
            if config.enable_quality_analysis:
                futures['quality'] = executor.submit(self._run_quality_analysis, source_files)

            # Análise de segurança
            if config.enable_security_analysis:
                futures['security'] = executor.submit(self._run_security_analysis, source_files)

            # Análise de performance
            if config.enable_performance_analysis:
                futures['performance'] = executor.submit(self._run_performance_analysis, source_files)

            # Análise de refatoração
            if config.enable_refactoring_analysis:
                futures['refactoring'] = executor.submit(self._run_refactoring_analysis, source_files)

            # Geração de testes
            if config.enable_test_generation:
                futures['testing'] = executor.submit(self._run_test_generation, source_files)

            # Geração de documentação
            if config.enable_documentation_generation:
                futures['documentation'] = executor.submit(self._run_documentation_generation, source_files)

            # Coletar resultados
            for analysis_type, future in futures.items():
                try:
                    result = future.result(timeout=self.config.get('analysis_timeout', 1800))
                    setattr(analysis, f"{analysis_type}_summary", result)
                    logger.info(f"✓ Análise de {analysis_type} concluída")
                except Exception as e:
                    logger.error(f"✗ Erro na análise de {analysis_type}: {e}")
                    setattr(analysis, f"{analysis_type}_summary", {'error': str(e)})

        return analysis

    def _execute_sequential_analysis(self,
                                   analysis: ProjectAnalysis,
                                   source_files: List[str],
                                   config: WorkflowConfig) -> ProjectAnalysis:
        """Executa análises sequencialmente"""
        logger.info("Executando análises sequencialmente...")

        analyses = [
            ('quality', config.enable_quality_analysis, self._run_quality_analysis),
            ('security', config.enable_security_analysis, self._run_security_analysis),
            ('performance', config.enable_performance_analysis, self._run_performance_analysis),
            ('refactoring', config.enable_refactoring_analysis, self._run_refactoring_analysis),
            ('testing', config.enable_test_generation, self._run_test_generation),
            ('documentation', config.enable_documentation_generation, self._run_documentation_generation)
        ]

        for analysis_type, enabled, analysis_func in analyses:
            if enabled:
                try:
                    logger.info(f"Executando análise de {analysis_type}...")
                    result = analysis_func(source_files)
                    setattr(analysis, f"{analysis_type}_summary", result)
                    logger.info(f"✓ Análise de {analysis_type} concluída")
                except Exception as e:
                    logger.error(f"✗ Erro na análise de {analysis_type}: {e}")
                    setattr(analysis, f"{analysis_type}_summary", {'error': str(e)})

        return analysis

    def _run_quality_analysis(self, source_files: List[str]) -> Dict[str, Any]:
        """Executa análise de qualidade em todos os arquivos"""
        quality_results = {
            'files_analyzed': 0,
            'average_quality_score': 0.0,
            'total_code_smells': 0,
            'quality_distribution': {},
            'top_issues': [],
            'recommendations': []
        }

        try:
            total_quality = 0.0
            quality_scores = []
            all_smells = []

            for file_path in source_files:
                try:
                    report = self.quality_analyzer.analyze_file_quality(file_path)

                    quality_results['files_analyzed'] += 1
                    total_quality += report.metrics.overall_quality_score
                    quality_scores.append(report.metrics.overall_quality_score)

                    all_smells.extend(report.code_smells)

                    # Armazenar análise detalhada
                    quality_results[file_path] = {
                        'quality_score': report.metrics.overall_quality_score,
                        'complexity': report.metrics.cyclomatic_complexity,
                        'maintainability': report.metrics.maintainability_index,
                        'code_smells_count': len(report.code_smells)
                    }

                except Exception as e:
                    logger.warning(f"Erro na análise de qualidade de {file_path}: {e}")

            # Calcular estatísticas agregadas
            if quality_results['files_analyzed'] > 0:
                quality_results['average_quality_score'] = total_quality / quality_results['files_analyzed']
                quality_results['total_code_smells'] = len(all_smells)

                # Distribuição de qualidade
                quality_results['quality_distribution'] = {
                    'excellent': len([s for s in quality_scores if s >= 0.9]),
                    'good': len([s for s in quality_scores if 0.7 <= s < 0.9]),
                    'fair': len([s for s in quality_scores if 0.5 <= s < 0.7]),
                    'poor': len([s for s in quality_scores if s < 0.5])
                }

                # Top issues
                smell_counter = Counter([smell.smell_type for smell in all_smells])
                quality_results['top_issues'] = smell_counter.most_common(5)

        except Exception as e:
            logger.error(f"Erro na análise de qualidade: {e}")
            quality_results['error'] = str(e)

        return quality_results

    def _run_security_analysis(self, source_files: List[str]) -> Dict[str, Any]:
        """Executa análise de segurança em todos os arquivos"""
        security_results = {
            'files_analyzed': 0,
            'vulnerabilities_found': 0,
            'critical_vulnerabilities': 0,
            'high_vulnerabilities': 0,
            'medium_vulnerabilities': 0,
            'low_vulnerabilities': 0,
            'security_score': 1.0,
            'vulnerability_types': {},
            'recommendations': []
        }

        try:
            all_vulnerabilities = []

            for file_path in source_files:
                try:
                    results = self.vulnerability_engine.analyze_file(file_path)
                    security_results['files_analyzed'] += 1

                    if 'vulnerabilities' in results:
                        vulnerabilities = results['vulnerabilities']
                        all_vulnerabilities.extend(vulnerabilities)

                        # Contabilizar por severidade
                        for vuln in vulnerabilities:
                            severity = vuln.get('severity', 'low')
                            security_results[f'{severity}_vulnerabilities'] += 1

                            vuln_type = vuln.get('type', 'unknown')
                            security_results['vulnerability_types'][vuln_type] = (
                                security_results['vulnerability_types'].get(vuln_type, 0) + 1
                            )

                except Exception as e:
                    logger.warning(f"Erro na análise de segurança de {file_path}: {e}")

            # Calcular score de segurança
            security_results['vulnerabilities_found'] = len(all_vulnerabilities)

            if security_results['vulnerabilities_found'] > 0:
                # Penalizar baseado na severidade
                penalty = (
                    security_results['critical_vulnerabilities'] * 0.4 +
                    security_results['high_vulnerabilities'] * 0.3 +
                    security_results['medium_vulnerabilities'] * 0.2 +
                    security_results['low_vulnerabilities'] * 0.1
                )

                security_results['security_score'] = max(0.0, 1.0 - (penalty / 10))

        except Exception as e:
            logger.error(f"Erro na análise de segurança: {e}")
            security_results['error'] = str(e)

        return security_results

    def _run_performance_analysis(self, source_files: List[str]) -> Dict[str, Any]:
        """Executa análise de performance em todos os arquivos"""
        performance_results = {
            'files_analyzed': 0,
            'bottlenecks_found': 0,
            'average_performance_score': 0.0,
            'optimization_opportunities': 0,
            'performance_distribution': {},
            'recommendations': []
        }

        try:
            total_performance = 0.0
            performance_scores = []
            all_bottlenecks = []

            for file_path in source_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        source_code = f.read()

                    results = self.performance_engine.analyze_code_performance(source_code, file_path)
                    performance_results['files_analyzed'] += 1

                    score = results.get('overall_score', 0.8)
                    total_performance += score
                    performance_scores.append(score)

                    if 'bottlenecks' in results:
                        bottlenecks = results['bottlenecks']
                        all_bottlenecks.extend(bottlenecks)

                except Exception as e:
                    logger.warning(f"Erro na análise de performance de {file_path}: {e}")

            # Calcular estatísticas
            if performance_results['files_analyzed'] > 0:
                performance_results['average_performance_score'] = total_performance / performance_results['files_analyzed']
                performance_results['bottlenecks_found'] = len(all_bottlenecks)

                # Distribuição de performance
                performance_results['performance_distribution'] = {
                    'excellent': len([s for s in performance_scores if s >= 0.9]),
                    'good': len([s for s in performance_scores if 0.7 <= s < 0.9]),
                    'fair': len([s for s in performance_scores if 0.5 <= s < 0.7]),
                    'poor': len([s for s in performance_scores if s < 0.5])
                }

        except Exception as e:
            logger.error(f"Erro na análise de performance: {e}")
            performance_results['error'] = str(e)

        return performance_results

    def _run_refactoring_analysis(self, source_files: List[str]) -> Dict[str, Any]:
        """Executa análise de oportunidades de refatoração"""
        refactoring_results = {
            'files_analyzed': 0,
            'opportunities_found': 0,
            'high_priority_opportunities': 0,
            'estimated_improvement': 0.0,
            'refactoring_types': {},
            'recommendations': []
        }

        try:
            all_opportunities = []

            for file_path in source_files:
                try:
                    opportunities = self.refactoring_engine.analyze_refactoring_opportunities(file_path)
                    refactoring_results['files_analyzed'] += 1
                    all_opportunities.extend(opportunities)

                    # Contar por tipo
                    for opp in opportunities:
                        ref_type = opp.refactoring_type
                        refactoring_results['refactoring_types'][ref_type] = (
                            refactoring_results['refactoring_types'].get(ref_type, 0) + 1
                        )

                except Exception as e:
                    logger.warning(f"Erro na análise de refatoração de {file_path}: {e}")

            # Estatísticas
            refactoring_results['opportunities_found'] = len(all_opportunities)
            refactoring_results['high_priority_opportunities'] = len([
                opp for opp in all_opportunities if opp.severity in ['high', 'critical']
            ])

            # Estimar melhoria total
            if all_opportunities:
                total_improvement = sum(opp.quality_impact for opp in all_opportunities)
                refactoring_results['estimated_improvement'] = total_improvement / len(all_opportunities)

        except Exception as e:
            logger.error(f"Erro na análise de refatoração: {e}")
            refactoring_results['error'] = str(e)

        return refactoring_results

    def _run_test_generation(self, source_files: List[str]) -> Dict[str, Any]:
        """Executa geração de testes para os arquivos"""
        testing_results = {
            'files_analyzed': 0,
            'test_suites_generated': 0,
            'total_tests_generated': 0,
            'estimated_coverage': 0.0,
            'test_types': {
                'unit': 0,
                'integration': 0,
                'property': 0,
                'performance': 0,
                'security': 0
            },
            'recommendations': []
        }

        try:
            total_coverage = 0.0
            suites_generated = 0

            # Gerar testes para arquivos principais (limite para não sobrecarregar)
            main_files = [f for f in source_files if not f.endswith('_test.py') and not 'test_' in f][:10]

            for file_path in main_files:
                try:
                    test_suite = self.test_generation_engine.generate_test_suite(file_path)
                    testing_results['files_analyzed'] += 1
                    suites_generated += 1

                    testing_results['total_tests_generated'] += test_suite.total_tests
                    total_coverage += test_suite.line_coverage

                    # Contar tipos de teste
                    testing_results['test_types']['unit'] += len(test_suite.unit_tests)
                    testing_results['test_types']['integration'] += len(test_suite.integration_tests)
                    testing_results['test_types']['property'] += len(test_suite.property_tests)
                    testing_results['test_types']['performance'] += len(test_suite.performance_tests)
                    testing_results['test_types']['security'] += len(test_suite.security_tests)

                except Exception as e:
                    logger.warning(f"Erro na geração de testes para {file_path}: {e}")

            testing_results['test_suites_generated'] = suites_generated
            if suites_generated > 0:
                testing_results['estimated_coverage'] = total_coverage / suites_generated

        except Exception as e:
            logger.error(f"Erro na geração de testes: {e}")
            testing_results['error'] = str(e)

        return testing_results

    def _run_documentation_generation(self, source_files: List[str]) -> Dict[str, Any]:
        """Executa geração de documentação"""
        documentation_results = {
            'files_analyzed': 0,
            'documentation_generated': 0,
            'coverage_score': 0.0,
            'documentation_types': {
                'api': 0,
                'architecture': 0,
                'tutorial': 0
            },
            'recommendations': []
        }

        try:
            total_coverage = 0.0
            docs_generated = 0

            # Gerar documentação para arquivos principais
            main_files = [f for f in source_files if f.endswith('.py')][:5]

            for file_path in main_files:
                try:
                    doc_result = self.documentation_generator.generate_documentation(
                        file_path, doc_type='api', output_format='markdown'
                    )

                    documentation_results['files_analyzed'] += 1
                    docs_generated += 1

                    coverage = doc_result['metrics']['completeness_score']
                    total_coverage += coverage

                    documentation_results['documentation_types']['api'] += 1

                except Exception as e:
                    logger.warning(f"Erro na geração de documentação para {file_path}: {e}")

            documentation_results['documentation_generated'] = docs_generated
            if docs_generated > 0:
                documentation_results['coverage_score'] = total_coverage / docs_generated

        except Exception as e:
            logger.error(f"Erro na geração de documentação: {e}")
            documentation_results['error'] = str(e)

        return documentation_results

    def _build_dependency_graph(self, source_files: List[str]) -> Dict[str, List[str]]:
        """Constrói grafo de dependências do projeto"""
        dependency_graph = {}

        try:
            for file_path in source_files:
                if not file_path.endswith('.py'):
                    continue

                dependencies = []

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Parse AST para encontrar imports
                    tree = ast.parse(content)

                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                dependencies.append(alias.name)
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                dependencies.append(node.module)

                    dependency_graph[file_path] = dependencies

                except Exception as e:
                    logger.debug(f"Erro ao analisar dependências de {file_path}: {e}")
                    dependency_graph[file_path] = []

        except Exception as e:
            logger.error(f"Erro ao construir grafo de dependências: {e}")

        return dependency_graph

    def _identify_critical_files(self, dependency_graph: Dict[str, List[str]]) -> List[str]:
        """Identifica arquivos críticos baseado no grafo de dependências"""
        # Contar quantas vezes cada arquivo é importado
        import_counts = Counter()

        for file_path, dependencies in dependency_graph.items():
            for dep in dependencies:
                # Mapear dependência para arquivo se possível
                for potential_file in dependency_graph.keys():
                    if dep in potential_file or potential_file.endswith(f"/{dep}.py"):
                        import_counts[potential_file] += 1

        # Retornar top 10 mais importados
        critical_files = [file for file, count in import_counts.most_common(10)]
        return critical_files

    def _detect_dependency_cycles(self, dependency_graph: Dict[str, List[str]]) -> List[List[str]]:
        """Detecta ciclos de dependência"""
        cycles = []

        try:
            # Criar grafo NetworkX
            G = nx.DiGraph()

            for file_path, dependencies in dependency_graph.items():
                G.add_node(file_path)
                for dep in dependencies:
                    # Mapear dependência para arquivo
                    for potential_file in dependency_graph.keys():
                        if dep in potential_file:
                            G.add_edge(file_path, potential_file)

            # Encontrar ciclos
            try:
                cycles_found = list(nx.simple_cycles(G))
                cycles = cycles_found[:10]  # Limitar a 10 ciclos
            except nx.NetworkXError:
                pass

        except Exception as e:
            logger.error(f"Erro ao detectar ciclos: {e}")

        return cycles

    def _calculate_aggregate_metrics(self, analysis: ProjectAnalysis) -> ProjectAnalysis:
        """Calcula métricas agregadas da análise"""
        try:
            # Qualidade geral
            if 'average_quality_score' in analysis.quality_summary:
                analysis.overall_quality_score = analysis.quality_summary['average_quality_score']

            # Segurança geral
            if 'security_score' in analysis.security_summary:
                analysis.overall_security_score = analysis.security_summary['security_score']

            # Performance geral
            if 'average_performance_score' in analysis.performance_summary:
                analysis.overall_performance_score = analysis.performance_summary['average_performance_score']

            # Manutenibilidade (baseada em qualidade e refatoração)
            quality_component = analysis.overall_quality_score * 0.7
            refactoring_component = 0.3

            if 'estimated_improvement' in analysis.refactoring_summary:
                # Inverter melhoria estimada (mais oportunidades = menor manutenibilidade atual)
                refactoring_component = max(0.0, 1.0 - analysis.refactoring_summary['estimated_improvement'])

            analysis.overall_maintainability_score = quality_component + refactoring_component * 0.3

            # Cobertura de testes
            if 'estimated_coverage' in analysis.testing_summary:
                analysis.overall_test_coverage = analysis.testing_summary['estimated_coverage']

            # Calcular LOC total
            total_loc = 0
            for file_analysis in analysis.file_analyses.values():
                if 'lines_of_code' in file_analysis:
                    total_loc += file_analysis['lines_of_code']

            analysis.total_lines_of_code = total_loc

        except Exception as e:
            logger.error(f"Erro ao calcular métricas agregadas: {e}")

        return analysis

    def _generate_executive_insights(self, analysis: ProjectAnalysis, config: WorkflowConfig) -> ProjectAnalysis:
        """Gera insights executivos usando IA"""
        try:
            if not self.llm_orchestrator:
                return analysis

            # Preparar contexto para IA
            context = {
                'project_path': analysis.project_path,
                'total_files': analysis.total_files,
                'languages': analysis.languages_detected,
                'framework': analysis.framework_detected,
                'quality_score': analysis.overall_quality_score,
                'security_score': analysis.overall_security_score,
                'performance_score': analysis.overall_performance_score,
                'maintainability_score': analysis.overall_maintainability_score,
                'test_coverage': analysis.overall_test_coverage
            }

            # Task para geração de insights
            insights_task = LLMTask(
                task_type='executive_analysis',
                specialization='project_insights',
                complexity='high',
                domain='software_engineering',
                requirements=['strategic_analysis', 'actionable_recommendations', 'risk_assessment'],
                constraints=['executive_level', 'business_focused', 'prioritized_actions']
            )

            insights_prompt = f"""
            Analyze this software project and provide executive-level insights:

            Project Overview:
            - Path: {context['project_path']}
            - Files: {context['total_files']}
            - Languages: {', '.join(context['languages'])}
            - Framework: {context['framework']}

            Current Metrics:
            - Quality Score: {context['quality_score']:.1%}
            - Security Score: {context['security_score']:.1%}
            - Performance Score: {context['performance_score']:.1%}
            - Maintainability: {context['maintainability_score']:.1%}
            - Test Coverage: {context['test_coverage']:.1%}

            Provide:
            1. Executive Summary (2-3 sentences)
            2. Top 3 Key Insights
            3. Top 5 Priority Recommendations
            4. Risk Assessment (High/Medium/Low risks)

            Focus on business impact and actionable strategies.
            """

            response = self.llm_orchestrator.process_task(insights_task, insights_prompt)

            if response and response.content:
                # Parse da resposta
                content = response.content

                # Extrair executive summary
                if 'executive summary' in content.lower():
                    summary_section = content.split('executive summary')[1].split('\n')[0:3]
                    analysis.executive_summary = ' '.join(summary_section).strip()

                # Extrair insights
                insights_section = self._extract_section(content, 'key insights', 'insights')
                if insights_section:
                    analysis.key_insights = self._parse_numbered_list(insights_section)

                # Extrair recomendações
                recommendations_section = self._extract_section(content, 'priority recommendations', 'recommendations')
                if recommendations_section:
                    analysis.priority_recommendations = self._parse_numbered_list(recommendations_section)

                # Extrair riscos
                risk_section = self._extract_section(content, 'risk assessment', 'risk')
                if risk_section:
                    analysis.risk_assessment = self._parse_risk_assessment(risk_section)

        except Exception as e:
            logger.error(f"Erro ao gerar insights executivos: {e}")
            # Fallback para insights básicos
            analysis.executive_summary = self._generate_basic_summary(analysis)
            analysis.key_insights = self._generate_basic_insights(analysis)
            analysis.priority_recommendations = self._generate_basic_recommendations(analysis)

        return analysis

    def _extract_section(self, content: str, *keywords) -> Optional[str]:
        """Extrai seção específica do conteúdo"""
        content_lower = content.lower()

        for keyword in keywords:
            if keyword in content_lower:
                start_idx = content_lower.find(keyword)
                # Encontrar próxima seção ou fim
                next_sections = ['executive summary', 'key insights', 'recommendations', 'risk assessment']
                end_idx = len(content)

                for section in next_sections:
                    if section != keyword and section in content_lower[start_idx + len(keyword):]:
                        section_idx = content_lower.find(section, start_idx + len(keyword))
                        end_idx = min(end_idx, section_idx)

                return content[start_idx:end_idx].strip()

        return None

    def _parse_numbered_list(self, text: str) -> List[str]:
        """Parse lista numerada do texto"""
        items = []
        lines = text.split('\n')

        for line in lines:
            line = line.strip()
            if re.match(r'^\d+\.', line) or line.startswith('- '):
                # Remover numeração
                cleaned = re.sub(r'^\d+\.\s*', '', line)
                cleaned = cleaned.lstrip('- ').strip()
                if cleaned:
                    items.append(cleaned)

        return items[:10]  # Limitar a 10 itens

    def _parse_risk_assessment(self, text: str) -> Dict[str, Any]:
        """Parse da avaliação de riscos"""
        risks = {
            'high_risks': [],
            'medium_risks': [],
            'low_risks': [],
            'overall_risk_level': 'medium'
        }

        text_lower = text.lower()

        # Buscar menções de níveis de risco
        if 'high risk' in text_lower or 'critical' in text_lower:
            risks['overall_risk_level'] = 'high'
        elif 'low risk' in text_lower and 'medium' not in text_lower:
            risks['overall_risk_level'] = 'low'

        return risks

    def _generate_basic_summary(self, analysis: ProjectAnalysis) -> str:
        """Gera resumo executivo básico"""
        quality_status = "excellent" if analysis.overall_quality_score >= 0.8 else "needs improvement"
        security_status = "secure" if analysis.overall_security_score >= 0.8 else "has security concerns"

        return f"This {analysis.framework_detected or 'software'} project with {analysis.total_files} files shows {quality_status} code quality ({analysis.overall_quality_score:.1%}) and {security_status} ({analysis.overall_security_score:.1%}). Immediate attention should focus on {'security' if analysis.overall_security_score < 0.7 else 'maintainability' if analysis.overall_maintainability_score < 0.7 else 'optimization'}."

    def _generate_basic_insights(self, analysis: ProjectAnalysis) -> List[str]:
        """Gera insights básicos"""
        insights = []

        if analysis.overall_quality_score < 0.7:
            insights.append("Code quality is below industry standards and requires systematic improvement")

        if analysis.overall_security_score < 0.8:
            insights.append("Security vulnerabilities pose potential risks and should be addressed promptly")

        if analysis.overall_test_coverage < 0.6:
            insights.append("Test coverage is insufficient, increasing risk of bugs in production")

        if len(analysis.dependency_cycles) > 0:
            insights.append("Circular dependencies detected, indicating architectural issues")

        if analysis.overall_performance_score < 0.7:
            insights.append("Performance bottlenecks identified that may impact user experience")

        return insights[:5]

    def _generate_basic_recommendations(self, analysis: ProjectAnalysis) -> List[str]:
        """Gera recomendações básicas"""
        recommendations = []

        if analysis.overall_quality_score < 0.7:
            recommendations.append("Implement automated code quality checks in CI/CD pipeline")

        if analysis.overall_security_score < 0.8:
            recommendations.append("Conduct security audit and implement recommended fixes")

        if analysis.overall_test_coverage < 0.6:
            recommendations.append("Increase test coverage to at least 80% through automated test generation")

        if 'opportunities_found' in analysis.refactoring_summary and analysis.refactoring_summary['opportunities_found'] > 10:
            recommendations.append("Prioritize refactoring of high-impact code sections")

        recommendations.append("Establish continuous monitoring and improvement processes")

        return recommendations[:5]

    def _add_benchmarks_and_comparisons(self, analysis: ProjectAnalysis) -> ProjectAnalysis:
        """Adiciona benchmarks e comparações da indústria"""
        try:
            # Benchmarks da indústria (valores típicos)
            industry_benchmarks = {
                'quality_score': 0.75,
                'security_score': 0.85,
                'performance_score': 0.80,
                'test_coverage': 0.70,
                'maintainability_score': 0.75
            }

            # Ajustar benchmarks baseado na linguagem/framework
            if 'Python' in analysis.languages_detected:
                industry_benchmarks['test_coverage'] = 0.80  # Python tem melhor cultura de testes

            if analysis.framework_detected and 'Java' in analysis.framework_detected:
                industry_benchmarks['quality_score'] = 0.80  # Java tende a ter código mais estruturado

            analysis.industry_benchmarks = industry_benchmarks

            # Comparação histórica (simulada - seria baseada em análises anteriores)
            analysis.historical_comparison = {
                'quality_trend': 'stable',
                'security_trend': 'improving',
                'performance_trend': 'stable'
            }

        except Exception as e:
            logger.error(f"Erro ao adicionar benchmarks: {e}")

        return analysis

    def _get_modules_used(self, config: WorkflowConfig) -> List[str]:
        """Retorna lista de módulos utilizados na análise"""
        modules = []

        if config.enable_quality_analysis:
            modules.append('CodeQualityAnalyzer')
        if config.enable_security_analysis:
            modules.append('VulnerabilityDetectionEngine')
        if config.enable_performance_analysis:
            modules.append('PerformanceProfilingEngine')
        if config.enable_refactoring_analysis:
            modules.append('IntelligentRefactoringEngine')
        if config.enable_test_generation:
            modules.append('AITestGenerationEngine')
        if config.enable_documentation_generation:
            modules.append('DocumentationGenerator')

        return modules

    def _update_analysis_metrics(self, analysis: ProjectAnalysis):
        """Atualiza métricas Prometheus"""
        try:
            self.metrics['analyses_total'].inc()
            self.metrics['analysis_duration'].observe(analysis.analysis_duration)
            self.metrics['quality_score'].set(analysis.overall_quality_score)
            self.metrics['security_score'].set(analysis.overall_security_score)
            self.metrics['files_analyzed'].inc(analysis.total_files)
        except Exception as e:
            logger.error(f"Erro ao atualizar métricas: {e}")

    def _save_project_analysis(self, analysis: ProjectAnalysis):
        """Salva análise no banco de dados mestre"""
        try:
            with sqlite3.connect(self.master_db_path) as conn:
                # Salvar ou atualizar projeto
                conn.execute("""
                    INSERT OR REPLACE INTO analyzed_projects
                    (project_id, project_path, project_name, analysis_data,
                     last_analyzed, analysis_count, total_analysis_time)
                    VALUES (?, ?, ?, ?, ?,
                           COALESCE((SELECT analysis_count FROM analyzed_projects WHERE project_id = ?) + 1, 1),
                           COALESCE((SELECT total_analysis_time FROM analyzed_projects WHERE project_id = ?) + ?, ?))
                """, (
                    analysis.project_id,
                    analysis.project_path,
                    Path(analysis.project_path).name,
                    json.dumps(asdict(analysis)),
                    analysis.analysis_timestamp,
                    analysis.project_id,
                    analysis.project_id,
                    analysis.analysis_duration,
                    analysis.analysis_duration
                ))

                # Salvar insights
                for insight in analysis.key_insights:
                    conn.execute("""
                        INSERT INTO insights
                        (project_id, insight_type, insight_content, confidence, priority)
                        VALUES (?, ?, ?, ?, ?)
                    """, (analysis.project_id, 'key_insight', insight, 0.8, 1))

                for recommendation in analysis.priority_recommendations:
                    conn.execute("""
                        INSERT INTO insights
                        (project_id, insight_type, insight_content, confidence, priority)
                        VALUES (?, ?, ?, ?, ?)
                    """, (analysis.project_id, 'recommendation', recommendation, 0.9, 1))

        except Exception as e:
            logger.error(f"Erro ao salvar análise: {e}")

    def _generate_project_id(self, project_path: str) -> str:
        """Gera ID único para o projeto"""
        return hashlib.md5(project_path.encode()).hexdigest()[:16]

    def start_analysis_async(self,
                           project_path: str,
                           workflow_config: Union[str, WorkflowConfig] = 'comprehensive') -> str:
        """
        Inicia análise assíncrona e retorna ID para acompanhamento

        Args:
            project_path: Caminho do projeto
            workflow_config: Configuração do workflow

        Returns:
            ID da análise para acompanhamento
        """
        analysis_id = f"analysis_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(project_path) % 10000}"

        # Adicionar à fila de análises
        analysis_info = {
            'analysis_id': analysis_id,
            'project_path': project_path,
            'workflow_config': workflow_config,
            'status': 'queued',
            'started_at': datetime.datetime.now().isoformat(),
            'progress': 0.0
        }

        self.system_state['active_analyses'][analysis_id] = analysis_info

        # Executar análise em thread separada
        def run_analysis():
            try:
                analysis_info['status'] = 'running'
                analysis_info['progress'] = 0.1

                result = self.analyze_project(project_path, workflow_config)

                analysis_info['status'] = 'completed'
                analysis_info['progress'] = 1.0
                analysis_info['result'] = asdict(result)
                analysis_info['completed_at'] = datetime.datetime.now().isoformat()

                self.system_state['total_analyses_completed'] += 1
                self.system_state['last_analysis'] = analysis_id

            except Exception as e:
                analysis_info['status'] = 'failed'
                analysis_info['error'] = str(e)
                analysis_info['failed_at'] = datetime.datetime.now().isoformat()
                logger.error(f"Erro na análise {analysis_id}: {e}")

        self.executor.submit(run_analysis)

        logger.info(f"Análise {analysis_id} iniciada para {project_path}")
        return analysis_id

    def get_analysis_status(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """Retorna status de uma análise"""
        return self.system_state['active_analyses'].get(analysis_id)

    def list_analyzed_projects(self) -> List[Dict[str, Any]]:
        """Lista projetos analisados"""
        projects = []

        try:
            with sqlite3.connect(self.master_db_path) as conn:
                cursor = conn.execute("""
                    SELECT project_id, project_path, project_name, last_analyzed,
                           analysis_count, total_analysis_time
                    FROM analyzed_projects
                    ORDER BY last_analyzed DESC
                    LIMIT 100
                """)

                for row in cursor.fetchall():
                    projects.append({
                        'project_id': row[0],
                        'project_path': row[1],
                        'project_name': row[2],
                        'last_analyzed': row[3],
                        'analysis_count': row[4],
                        'total_analysis_time': row[5]
                    })

        except Exception as e:
            logger.error(f"Erro ao listar projetos: {e}")

        return projects

    def get_system_metrics(self) -> SystemMetrics:
        """Retorna métricas atuais do sistema"""
        try:
            return SystemMetrics(
                timestamp=datetime.datetime.now().isoformat(),
                cpu_usage=psutil.cpu_percent(),
                memory_usage=psutil.virtual_memory().percent,
                disk_usage=psutil.disk_usage('/').percent,
                active_threads=threading.active_count(),
                active_processes=len(psutil.pids()),
                analyses_completed=self.system_state['total_analyses_completed'],
                analyses_in_progress=len([a for a in self.system_state['active_analyses'].values()
                                        if a['status'] == 'running']),
                analyses_queued=len([a for a in self.system_state['active_analyses'].values()
                                   if a['status'] == 'queued']),
                average_analysis_time=0.0,  # Seria calculado do histórico
                cache_hit_rate=0.0,  # Seria calculado do cache
                total_files_analyzed=0,  # Seria somado do histórico
                total_vulnerabilities_found=0,  # Seria somado do histórico
                total_refactoring_opportunities=0,  # Seria somado do histórico
                total_tests_generated=0,  # Seria somado do histórico
                llm_requests_made=0,  # Seria obtido do orchestrator
                llm_tokens_consumed=0,  # Seria obtido do orchestrator
                llm_average_response_time=0.0,  # Seria obtido do orchestrator
                llm_success_rate=0.0,  # Seria obtido do orchestrator
                errors_count=0,  # Seria contado dos logs
                warnings_count=0,  # Seria contado dos logs
                failed_analyses=len([a for a in self.system_state['active_analyses'].values()
                                   if a['status'] == 'failed'])
            )
        except Exception as e:
            logger.error(f"Erro ao obter métricas: {e}")
            return SystemMetrics(
                timestamp=datetime.datetime.now().isoformat(),
                cpu_usage=0.0, memory_usage=0.0, disk_usage=0.0,
                active_threads=0, active_processes=0,
                analyses_completed=0, analyses_in_progress=0, analyses_queued=0,
                average_analysis_time=0.0, cache_hit_rate=0.0,
                total_files_analyzed=0, total_vulnerabilities_found=0,
                total_refactoring_opportunities=0, total_tests_generated=0,
                llm_requests_made=0, llm_tokens_consumed=0,
                llm_average_response_time=0.0, llm_success_rate=0.0,
                errors_count=0, warnings_count=0, failed_analyses=0
            )

    def _get_uptime(self) -> str:
        """Retorna tempo de atividade do sistema"""
        startup_time = datetime.datetime.fromisoformat(self.system_state['startup_time'])
        uptime = datetime.datetime.now() - startup_time

        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        return f"{days}d {hours}h {minutes}m {seconds}s"

    def generate_executive_report(self, analysis: ProjectAnalysis) -> str:
        """Gera relatório executivo em HTML"""
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Relatório Executivo - {project_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background: #2c3e50; color: white; padding: 20px; }}
        .metric {{ display: inline-block; margin: 10px; padding: 15px; border: 1px solid #ddd; }}
        .excellent {{ background: #2ecc71; color: white; }}
        .good {{ background: #f39c12; color: white; }}
        .poor {{ background: #e74c3c; color: white; }}
        .insight {{ margin: 10px 0; padding: 10px; background: #ecf0f1; }}
        .recommendation {{ margin: 5px 0; padding: 8px; background: #3498db; color: white; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Relatório Executivo</h1>
        <h2>{project_name}</h2>
        <p>Gerado em: {timestamp}</p>
    </div>

    <h2>Resumo Executivo</h2>
    <p>{executive_summary}</p>

    <h2>Métricas Principais</h2>
    <div class="metric {quality_class}">
        <h3>Qualidade</h3>
        <p>{quality_score:.1%}</p>
    </div>
    <div class="metric {security_class}">
        <h3>Segurança</h3>
        <p>{security_score:.1%}</p>
    </div>
    <div class="metric {performance_class}">
        <h3>Performance</h3>
        <p>{performance_score:.1%}</p>
    </div>
    <div class="metric {maintainability_class}">
        <h3>Manutenibilidade</h3>
        <p>{maintainability_score:.1%}</p>
    </div>

    <h2>Insights Principais</h2>
    {insights_html}

    <h2>Recomendações Prioritárias</h2>
    {recommendations_html}

    <h2>Detalhes Técnicos</h2>
    <ul>
        <li>Total de arquivos: {total_files}</li>
        <li>Linguagens: {languages}</li>
        <li>Framework: {framework}</li>
        <li>Linhas de código: {total_loc:,}</li>
        <li>Duração da análise: {analysis_duration:.1f}s</li>
    </ul>
</body>
</html>
        """

        # Determinar classes CSS baseadas nos scores
        def get_score_class(score):
            if score >= 0.8:
                return 'excellent'
            elif score >= 0.6:
                return 'good'
            else:
                return 'poor'

        # Gerar HTML dos insights
        insights_html = ''.join([
            f'<div class="insight">• {insight}</div>'
            for insight in analysis.key_insights
        ])

        # Gerar HTML das recomendações
        recommendations_html = ''.join([
            f'<div class="recommendation">{i+1}. {rec}</div>'
            for i, rec in enumerate(analysis.priority_recommendations)
        ])

        # Preencher template
        report_html = html_template.format(
            project_name=Path(analysis.project_path).name,
            timestamp=datetime.datetime.now().strftime('%d/%m/%Y %H:%M'),
            executive_summary=analysis.executive_summary or "Análise completa do projeto executada com sucesso.",
            quality_score=analysis.overall_quality_score,
            security_score=analysis.overall_security_score,
            performance_score=analysis.overall_performance_score,
            maintainability_score=analysis.overall_maintainability_score,
            quality_class=get_score_class(analysis.overall_quality_score),
            security_class=get_score_class(analysis.overall_security_score),
            performance_class=get_score_class(analysis.overall_performance_score),
            maintainability_class=get_score_class(analysis.overall_maintainability_score),
            insights_html=insights_html,
            recommendations_html=recommendations_html,
            total_files=analysis.total_files,
            languages=', '.join(analysis.languages_detected),
            framework=analysis.framework_detected or 'Não detectado',
            total_loc=analysis.total_lines_of_code,
            analysis_duration=analysis.analysis_duration
        )

        return report_html

    def shutdown(self):
        """Finaliza o sistema graciosamente"""
        logger.info("Iniciando shutdown do Bibliotecário Cognitivo...")

        # Aguardar análises em andamento
        active_analyses = [a for a in self.system_state['active_analyses'].values()
                         if a['status'] == 'running']

        if active_analyses:
            logger.info(f"Aguardando {len(active_analyses)} análises em andamento...")
            # Implementar timeout e wait

        # Finalizar executor
        self.executor.shutdown(wait=True)

        # Salvar estado final
        self._save_system_state()

        logger.info("Bibliotecário Cognitivo finalizado com sucesso")

    def _save_system_state(self):
        """Salva estado atual do sistema"""
        try:
            state_file = self.cache_dir / "system_state.json"
            with open(state_file, 'w') as f:
                json.dump(self.system_state, f, indent=2)
        except Exception as e:
            logger.error(f"Erro ao salvar estado do sistema: {e}")


def main():
    """Função principal para demonstração e teste"""
    print("=== Bibliotecário Cognitivo Ultra-Avançado ===")
    print("Inicializando sistema...")

    try:
        # Inicializar sistema
        if CognitiveLibrarianUltraAdvanced is not None:
            librarian = CognitiveLibrarianUltraAdvanced(
                project_path="./",
                cache_dir="./quimera_cache_demo"
            )
        else:
            librarian = None # Ou lidar com o caso onde não está disponível
        print("✓ Sistema inicializado com sucesso")
        print(f"✓ API disponível em http://localhost:5000")
        print(f"✓ Métricas disponíveis em http://localhost:8000")

        # Executar análise de demonstração
        print("\nExecutando análise de demonstração...")

        analysis = librarian.analyze_project(
            project_path="./",
            workflow_config='comprehensive'
        )

        print(f"\n=== RESULTADOS DA ANÁLISE ===")
        print(f"Projeto: {Path(analysis.project_path).name}")
        print(f"Arquivos analisados: {analysis.total_files}")
        print(f"Linguagens: {', '.join(analysis.languages_detected)}")
        print(f"Framework: {analysis.framework_detected}")
        print(f"Duração: {analysis.analysis_duration:.1f}s")
        print()
        print(f"📊 MÉTRICAS PRINCIPAIS:")
        print(f"   Qualidade Geral: {analysis.overall_quality_score:.1%}")
        print(f"   Segurança: {analysis.overall_security_score:.1%}")
        print(f"   Performance: {analysis.overall_performance_score:.1%}")
        print(f"   Manutenibilidade: {analysis.overall_maintainability_score:.1%}")
        print(f"   Cobertura de Testes: {analysis.overall_test_coverage:.1%}")
        print()
        print(f"🎯 INSIGHTS PRINCIPAIS:")
        for i, insight in enumerate(analysis.key_insights[:3], 1):
            print(f"   {i}. {insight}")
        print()
        print(f"💡 RECOMENDAÇÕES PRIORITÁRIAS:")
        for i, rec in enumerate(analysis.priority_recommendations[:3], 1):
            print(f"   {i}. {rec}")

        # Gerar relatório executivo
        report_html = librarian.generate_executive_report(analysis)
        report_file = "./executive_report.html"

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_html)

        print(f"\n📋 Relatório executivo salvo em: {report_file}")

        # Mostrar métricas do sistema
        metrics = librarian.get_system_metrics()
        print(f"\n⚡ MÉTRICAS DO SISTEMA:")
        print(f"   CPU: {metrics.cpu_usage:.1f}%")
        print(f"   Memória: {metrics.memory_usage:.1f}%")
        print(f"   Análises completadas: {metrics.analyses_completed}")
        print(f"   Uptime: {librarian._get_uptime()}")

        print(f"\n🚀 Sistema pronto para uso!")
        print(f"   Use a API REST ou integre diretamente com o código Python")
        print(f"   Workflows disponíveis: {list(librarian.workflows.keys())}")

        # Manter sistema ativo para demonstração
        print(f"\nPressione Ctrl+C para finalizar...")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nFinalizando sistema...")
            librarian.shutdown()

    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()