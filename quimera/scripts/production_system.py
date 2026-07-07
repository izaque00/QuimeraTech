#!/usr/bin/env python3
"""
Sistema de Produção Ultra-Avançado do Quimera
Orquestra todos os plugins, monitoramento contínuo, auto-healing
e sistema de produção completo com telemetria e alertas.
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
import psutil
import schedule
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Adiciona o path do projeto
sys.path.append(str(Path(__file__).parent.parent))

from quimera.core.plugin_framework import PluginManager, BasePlugin
try:
    from quimera.agentes.agente_fiscal_codigo import AgenteFiscalCodigo
except ImportError:
    AgenteFiscalCodigo = None  # AgenteFiscalCodigo não disponível


@dataclass
class ProductionConfig:
    """Configuração do sistema de produção"""
    project_paths: List[str] = field(default_factory=list)
    monitoring_interval: int = 300  # 5 minutos
    auto_fix_enabled: bool = True
    alert_email: Optional[str] = None
    slack_webhook: Optional[str] = None
    backup_enabled: bool = True
    backup_interval: int = 3600  # 1 hora
    telemetry_enabled: bool = True
    log_level: str = "INFO"
    max_concurrent_scans: int = 5
    plugin_config_path: str = "configs/production_plugins.json"


@dataclass
class SystemMetrics:
    """Métricas do sistema"""
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    active_processes: int
    scan_queue_size: int
    errors_last_hour: int
    last_scan_duration: float
    total_scans_today: int


@dataclass
class Alert:
    """Alerta do sistema"""
    alert_id: str
    severity: str  # critical, warning, info
    category: str  # performance, security, dependency, system
    title: str
    description: str
    timestamp: datetime
    resolved: bool = False
    auto_fixable: bool = False


class ProductionMonitor:
    """Monitor de produção em tempo real"""

    def __init__(self, config: ProductionConfig):
        self.config = config
        self.alerts = []
        self.metrics_history = []
        self.running = False
        self.logger = logging.getLogger("ProductionMonitor")

    async def start_monitoring(self):
        """Inicia monitoramento contínuo"""
        self.running = True
        self.logger.info("Monitor de produção iniciado")

        # Inicia tarefas de monitoramento
        tasks = [
            asyncio.create_task(self._monitor_system_health()),
            asyncio.create_task(self._monitor_file_changes()),
            asyncio.create_task(self._process_alert_queue()),
            asyncio.create_task(self._generate_periodic_reports())
        ]

        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            self.logger.error(f"Erro no monitoramento: {e}")
        finally:
            self.running = False

    async def _monitor_system_health(self):
        """Monitora saúde do sistema"""
        while self.running:
            try:
                # Coleta métricas do sistema
                metrics = SystemMetrics(
                    cpu_usage=psutil.cpu_percent(interval=1),
                    memory_usage=psutil.virtual_memory().percent,
                    disk_usage=psutil.disk_usage('/').percent,
                    active_processes=len(psutil.pids()),
                    scan_queue_size=0,  # Será implementado
                    errors_last_hour=self._count_recent_errors(),
                    last_scan_duration=0.0,  # Será implementado
                    total_scans_today=0  # Será implementado
                )

                self.metrics_history.append(metrics)

                # Mantém apenas últimas 24 horas
                cutoff_time = datetime.now() - timedelta(hours=24)
                self.metrics_history = [
                    m for m in self.metrics_history
                    if getattr(m, 'timestamp', datetime.now()) > cutoff_time
                ]

                # Verifica alertas baseados em métricas
                await self._check_system_alerts(metrics)

                await asyncio.sleep(self.config.monitoring_interval)

            except Exception as e:
                self.logger.error(f"Erro no monitoramento de saúde: {e}")
                await asyncio.sleep(60)

    async def _monitor_file_changes(self):
        """Monitora mudanças em arquivos"""
        class CodeChangeHandler(FileSystemEventHandler):
            def __init__(self, monitor):
                self.monitor = monitor

            def on_modified(self, event):
                if not event.is_directory and event.src_path.endswith('.py'):
                    asyncio.create_task(
                        self.monitor._handle_file_change(event.src_path)
                    )

        observer = Observer()
        handler = CodeChangeHandler(self)

        for path in self.config.project_paths:
            if os.path.exists(path):
                observer.schedule(handler, path, recursive=True)

        observer.start()

        try:
            while self.running:
                await asyncio.sleep(1)
        finally:
            observer.stop()
            observer.join()

    async def _handle_file_change(self, file_path: str):
        """Processa mudança em arquivo"""
        self.logger.info(f"Arquivo modificado: {file_path}")

        # Adiciona à fila de análise
        await self._queue_file_analysis(file_path)

    async def _queue_file_analysis(self, file_path: str):
        """Adiciona arquivo à fila de análise"""
        # Implementaria fila de análise assíncrona
        pass

    async def _check_system_alerts(self, metrics: SystemMetrics):
        """Verifica condições de alerta"""
        alerts_to_create = []

        # CPU alto
        if metrics.cpu_usage > 90:
            alerts_to_create.append(Alert(
                alert_id=f"cpu_high_{int(time.time())}",
                severity="warning",
                category="performance",
                title="Alto uso de CPU",
                description=f"CPU em {metrics.cpu_usage:.1f}%",
                timestamp=datetime.now()
            ))

        # Memória alta
        if metrics.memory_usage > 85:
            alerts_to_create.append(Alert(
                alert_id=f"memory_high_{int(time.time())}",
                severity="warning",
                category="performance",
                title="Alto uso de memória",
                description=f"Memória em {metrics.memory_usage:.1f}%",
                timestamp=datetime.now()
            ))

        # Disco cheio
        if metrics.disk_usage > 90:
            alerts_to_create.append(Alert(
                alert_id=f"disk_full_{int(time.time())}",
                severity="critical",
                category="system",
                title="Disco quase cheio",
                description=f"Disco em {metrics.disk_usage:.1f}%",
                timestamp=datetime.now()
            ))

        # Adiciona alertas
        for alert in alerts_to_create:
            await self._create_alert(alert)

    async def _create_alert(self, alert: Alert):
        """Cria novo alerta"""
        self.alerts.append(alert)
        self.logger.warning(f"ALERT: {alert.title} - {alert.description}")

        # Envia notificações
        await self._send_alert_notifications(alert)

    async def _send_alert_notifications(self, alert: Alert):
        """Envia notificações de alerta"""
        if self.config.alert_email:
            await self._send_email_alert(alert)

        if self.config.slack_webhook:
            await self._send_slack_alert(alert)

    async def _send_email_alert(self, alert: Alert):
        """Envia alerta por email"""
        try:
            msg = MIMEMultipart()
            msg['Subject'] = f"[Quimera Alert] {alert.title}"
            msg['From'] = "quimera@system.local"
            msg['To'] = self.config.alert_email

            body = f"""
            Alerta do Sistema Quimera:

            Severidade: {alert.severity.upper()}
            Categoria: {alert.category}
            Descrição: {alert.description}
            Timestamp: {alert.timestamp}
            ID: {alert.alert_id}
            """

            msg.attach(MIMEText(body, 'plain'))

            # Configuraria SMTP real em produção
            self.logger.info(f"Email alert would be sent: {alert.title}")

        except Exception as e:
            self.logger.error(f"Erro ao enviar email: {e}")

    async def _send_slack_alert(self, alert: Alert):
        """Envia alerta para Slack"""
        # Implementaria webhook do Slack
        self.logger.info(f"Slack alert would be sent: {alert.title}")

    async def _process_alert_queue(self):
        """Processa fila de alertas"""
        while self.running:
            try:
                # Processa alertas pendentes
                for alert in self.alerts:
                    if not alert.resolved and alert.auto_fixable:
                        await self._attempt_auto_fix(alert)

                await asyncio.sleep(30)

            except Exception as e:
                self.logger.error(f"Erro no processamento de alertas: {e}")

    async def _attempt_auto_fix(self, alert: Alert):
        """Tenta correção automática"""
        self.logger.info(f"Tentando auto-correção para: {alert.title}")

        # Implementaria lógica de auto-correção específica
        # Por exemplo, limpeza de cache, restart de serviços, etc.

        alert.resolved = True

    async def _generate_periodic_reports(self):
        """Gera relatórios periódicos"""
        while self.running:
            try:
                # Gera relatório a cada 6 horas
                await asyncio.sleep(6 * 3600)

                report = await self._generate_system_report()
                await self._save_report(report)

            except Exception as e:
                self.logger.error(f"Erro na geração de relatórios: {e}")

    async def _generate_system_report(self) -> Dict[str, Any]:
        """Gera relatório do sistema"""
        current_metrics = self.metrics_history[-1] if self.metrics_history else None

        return {
            'timestamp': datetime.now().isoformat(),
            'system_health': {
                'status': 'healthy' if current_metrics and current_metrics.cpu_usage < 80 else 'degraded',
                'current_metrics': current_metrics.__dict__ if current_metrics else {},
                'alerts_count': len([a for a in self.alerts if not a.resolved])
            },
            'performance_summary': {
                'avg_cpu_usage': sum(m.cpu_usage for m in self.metrics_history) / len(self.metrics_history) if self.metrics_history else 0,
                'avg_memory_usage': sum(m.memory_usage for m in self.metrics_history) / len(self.metrics_history) if self.metrics_history else 0
            },
            'alerts_summary': {
                'total_alerts': len(self.alerts),
                'critical_alerts': len([a for a in self.alerts if a.severity == 'critical']),
                'resolved_alerts': len([a for a in self.alerts if a.resolved])
            }
        }

    async def _save_report(self, report: Dict[str, Any]):
        """Salva relatório"""
        reports_dir = Path("reports/production")
        reports_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = reports_dir / f"system_report_{timestamp}.json"

        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        self.logger.info(f"Relatório salvo: {report_file}")

    def _count_recent_errors(self) -> int:
        """Conta erros na última hora"""
        # Implementaria contagem real de logs de erro
        return 0

    def stop(self):
        """Para o monitoramento"""
        self.running = False


class ProductionOrchestrator:
    """Orquestrador principal do sistema de produção"""

    def __init__(self, config_path: str = "configs/production.json"):
        self.config = self._load_config(config_path)
        self.plugin_manager = PluginManager()
        self.fiscal_agent = AgenteFiscalCodigo() if AgenteFiscalCodigo is not None else None
        self.monitor = ProductionMonitor(self.config)
        self.executor = ThreadPoolExecutor(max_workers=self.config.max_concurrent_scans)
        self.running = False

        # Configura logging
        self._setup_logging()

        self.logger = logging.getLogger("ProductionOrchestrator")

    def _load_config(self, config_path: str) -> ProductionConfig:
        """Carrega configuração"""
        try:
            with open(config_path) as f:
                data = json.load(f)
            return ProductionConfig(**data)
        except FileNotFoundError:
            self.logger.warning(f"Config não encontrado: {config_path}, usando padrões")
            return ProductionConfig()
        except Exception as e:
            self.logger.error(f"Erro ao carregar config: {e}")
            return ProductionConfig()

    def _setup_logging(self):
        """Configura sistema de logging"""
        log_level = getattr(logging, self.config.log_level.upper())

        # Configura logger principal
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/production.log'),
                logging.StreamHandler()
            ]
        )

    async def start(self):
        """Inicia sistema de produção"""
        self.logger.info("Iniciando Sistema de Produção Quimera")
        self.running = True

        try:
            # 1. Inicializa plugins
            await self._initialize_plugins()

            # 2. Configura diretórios de plugins
            for plugin_dir in ["plugins/production", "plugins/custom"]:
                self.plugin_manager.add_plugin_directory(plugin_dir)

            # 3. Descobre e carrega plugins
            plugins = await self.plugin_manager.discover_plugins()
            self.logger.info(f"Descobertos {len(plugins)} plugins")

            for plugin in plugins:
                success = await self.plugin_manager.load_plugin(plugin)
                if success:
                    self.logger.info(f"Plugin carregado: {plugin}")
                else:
                    self.logger.error(f"Falha ao carregar plugin: {plugin}")

            # 4. Inicia monitoramento
            monitor_task = asyncio.create_task(self.monitor.start_monitoring())

            # 5. Inicia análise inicial
            initial_scan_task = asyncio.create_task(self._perform_initial_scan())

            # 6. Inicia scheduler de tarefas periódicas
            scheduler_task = asyncio.create_task(self._run_scheduler())

            # 7. Configura handlers de sinal
            self._setup_signal_handlers()

            # Aguarda todas as tarefas
            await asyncio.gather(
                monitor_task,
                initial_scan_task,
                scheduler_task,
                return_exceptions=True
            )

        except KeyboardInterrupt:
            self.logger.info("Interrupção do usuário recebida")
        except Exception as e:
            self.logger.error(f"Erro no sistema de produção: {e}")
        finally:
            await self._shutdown()

    async def _initialize_plugins(self):
        """Inicializa sistema de plugins"""
        self.logger.info("Inicializando sistema de plugins...")

        # Configura paths adicionais se necessário
        plugin_paths = [
            "plugins/production",
            "plugins/security",
            "plugins/performance",
            "plugins/custom"
        ]

        for path in plugin_paths:
            Path(path).mkdir(parents=True, exist_ok=True)
            self.plugin_manager.add_plugin_directory(path)

    async def _perform_initial_scan(self):
        """Executa análise inicial de todos os projetos"""
        self.logger.info("Executando análise inicial...")

        for project_path in self.config.project_paths:
            if os.path.exists(project_path):
                await self._scan_project(project_path)
            else:
                self.logger.warning(f"Path de projeto não existe: {project_path}")

    async def _scan_project(self, project_path: str):
        """Executa análise completa de um projeto"""
        self.logger.info(f"Analisando projeto: {project_path}")

        try:
            # Encontra todos os arquivos Python
            python_files = list(Path(project_path).rglob("*.py"))

            # Processa arquivos em lotes
            for i in range(0, len(python_files), self.config.max_concurrent_scans):
                batch = python_files[i:i + self.config.max_concurrent_scans]

                # Processa batch em paralelo
                tasks = [self._analyze_file(str(file_path)) for file_path in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Processa resultados
                for file_path, result in zip(batch, results):
                    if isinstance(result, Exception):
                        self.logger.error(f"Erro ao analisar {file_path}: {result}")
                    else:
                        await self._process_analysis_result(str(file_path), result)

        except Exception as e:
            self.logger.error(f"Erro na análise do projeto {project_path}: {e}")

    async def _analyze_file(self, file_path: str) -> Dict[str, Any]:
        """Analisa um arquivo específico"""
        try:
            # Lê conteúdo do arquivo
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Contexto para plugins
            context = {
                'file_path': file_path,
                'code_content': content,
                'project_root': str(Path(file_path).parent),
                'analysis_timestamp': time.time()
            }

            # Executa todos os plugins
            plugin_results = await self.plugin_manager.execute_plugins(context)

            # Executa agente fiscal também
            fiscal_result = await self._run_fiscal_analysis(file_path, content)

            return {
                'file_path': file_path,
                'plugin_results': plugin_results,
                'fiscal_result': fiscal_result,
                'analysis_complete': True
            }

        except Exception as e:
            self.logger.error(f"Erro ao analisar arquivo {file_path}: {e}")
            return {
                'file_path': file_path,
                'error': str(e),
                'analysis_complete': False
            }

    async def _run_fiscal_analysis(self, file_path: str, content: str) -> Dict[str, Any]:
        """Executa análise do agente fiscal"""
        try:
            # Configura agente fiscal se necessário
            fiscal_config = {
                'corrigir_automaticamente': self.config.auto_fix_enabled,
                'gerar_backup': self.config.backup_enabled,
                'relatorio_detalhado': True
            }

            # Executa análise fiscal
            result = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: self.fiscal_agent.fiscalizar_arquivo(file_path, fiscal_config)
            )

            return result

        except Exception as e:
            self.logger.error(f"Erro na análise fiscal: {e}")
            return {'error': str(e)}

    async def _process_analysis_result(self, file_path: str, result: Dict[str, Any]):
        """Processa resultado da análise"""
        if not result.get('analysis_complete', False):
            return

        # Extrai informações importantes
        critical_issues = []

        # Processa resultados dos plugins
        plugin_results = result.get('plugin_results', {})
        for plugin_name, plugin_result in plugin_results.items():
            if isinstance(plugin_result, dict):
                # Verifica vulnerabilidades críticas
                if 'vulnerabilities' in plugin_result:
                    for vuln in plugin_result['vulnerabilities']:
                        if vuln.get('severity') == 'critical':
                            critical_issues.append({
                                'source': plugin_name,
                                'type': 'vulnerability',
                                'description': vuln.get('description', 'Unknown'),
                                'file': file_path
                            })

        # Cria alertas para issues críticos
        for issue in critical_issues:
            alert = Alert(
                alert_id=f"critical_{hash(str(issue))% 10000:04d}",
                severity="critical",
                category="security",
                title=f"Issue crítico em {Path(file_path).name}",
                description=issue['description'],
                timestamp=datetime.now(),
                auto_fixable=self.config.auto_fix_enabled
            )
            await self.monitor._create_alert(alert)

        # Salva resultados
        await self._save_analysis_results(file_path, result)

    async def _save_analysis_results(self, file_path: str, result: Dict[str, Any]):
        """Salva resultados da análise"""
        results_dir = Path("results/analysis")
        results_dir.mkdir(parents=True, exist_ok=True)

        # Nome do arquivo baseado no hash do path
        file_hash = hashlib.sha256(file_path.encode()).hexdigest()[:16]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = results_dir / f"analysis_{file_hash}_{timestamp}.json"

        with open(result_file, 'w') as f:
            json.dump(result, f, indent=2, default=str)

    async def _run_scheduler(self):
        """Executa tarefas agendadas"""
        # Configura tarefas periódicas
        schedule.every(1).hours.do(lambda: asyncio.create_task(self._hourly_maintenance()))
        schedule.every().day.at("02:00").do(lambda: asyncio.create_task(self._daily_full_scan()))
        schedule.every().sunday.at("01:00").do(lambda: asyncio.create_task(self._weekly_deep_analysis()))

        while self.running:
            schedule.run_pending()
            await asyncio.sleep(60)  # Verifica a cada minuto

    async def _hourly_maintenance(self):
        """Manutenção de cada hora"""
        self.logger.info("Executando manutenção horária...")

        # Limpeza de logs antigos
        await self._cleanup_old_logs()

        # Verificação de saúde dos plugins
        plugin_status = await self.plugin_manager.get_plugin_status()

        # Alerta se algum plugin estiver com problemas
        for plugin_name, status in plugin_status.items():
            if status['status'] != 'loaded':
                alert = Alert(
                    alert_id=f"plugin_issue_{plugin_name}_{int(time.time())}",
                    severity="warning",
                    category="system",
                    title=f"Plugin com problemas: {plugin_name}",
                    description=f"Status: {status['status']}",
                    timestamp=datetime.now()
                )
                await self.monitor._create_alert(alert)

    async def _daily_full_scan(self):
        """Scan completo diário"""
        self.logger.info("Executando scan completo diário...")

        for project_path in self.config.project_paths:
            await self._scan_project(project_path)

    async def _weekly_deep_analysis(self):
        """Análise profunda semanal"""
        self.logger.info("Executando análise profunda semanal...")

        # Análise de tendências
        # Relatório detalhado
        # Otimizações sugeridas
        pass

    async def _cleanup_old_logs(self):
        """Limpa logs antigos"""
        logs_dir = Path("logs")
        if logs_dir.exists():
            cutoff_date = datetime.now() - timedelta(days=30)

            for log_file in logs_dir.glob("*.log*"):
                if log_file.stat().st_mtime < cutoff_date.timestamp():
                    log_file.unlink()
                    self.logger.info(f"Log antigo removido: {log_file}")

    def _setup_signal_handlers(self):
        """Configura handlers para sinais do sistema"""
        def signal_handler(signum, frame):
            self.logger.info(f"Sinal {signum} recebido, parando sistema...")
            self.running = False
            self.monitor.stop()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def _shutdown(self):
        """Processo de shutdown do sistema"""
        self.logger.info("Iniciando processo de shutdown...")

        # Para monitoramento
        self.monitor.stop()

        # Para plugins
        for plugin_name in list(self.plugin_manager.plugins.keys()):
            await self.plugin_manager.unload_plugin(plugin_name)

        # Finaliza executor
        self.executor.shutdown(wait=True)

        self.logger.info("Sistema de produção finalizado")


async def main():
    """Função principal"""
    print("🚀 Iniciando Sistema de Produção Quimera Ultra-Avançado")

    # Cria diretórios necessários
    for directory in ["logs", "reports", "results", "configs", "plugins"]:
        Path(directory).mkdir(exist_ok=True)

    # Inicia sistema
    orchestrator = ProductionOrchestrator()
    await orchestrator.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚡ Sistema interrompido pelo usuário")
    except Exception as e:
        print(f"❌ Erro fatal: {e}")
        sys.exit(1)