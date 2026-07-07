"""
AEGIS Dashboard - Interface de Monitoramento e Controle
======================================================

Sistema de dashboard para monitoramento em tempo real do AEGIS,
fornecendo interface para visualização de ameaças, métricas de
segurança e controle do sistema de proteção.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import statistics

from quimera.logs.parser import montar_log


class AegisDashboard:
    """
    Dashboard avançado para monitoramento do sistema AEGIS
    
    Funcionalidades:
    - Visualização em tempo real de métricas
    - Monitor de ameaças ativas
    - Status dos componentes
    - Controles de sistema
    - Relatórios de segurança
    - Alertas e notificações
    """
    
    def __init__(self, aegis_plugin=None):
        self.aegis_plugin = aegis_plugin
        self._dashboard_active = False
        self._update_interval = 5  # segundos
        self._data_retention_hours = 24
        
        # Dados do dashboard
        self.dashboard_data = {
            'system_status': {},
            'threat_summary': {},
            'component_metrics': {},
            'performance_data': {},
            'recent_events': [],
            'alerts': [],
            'statistics': {}
        }
        
        # Histórico de dados para gráficos
        self.metrics_history = {
            'threats_over_time': [],
            'performance_metrics': [],
            'component_health': [],
            'system_load': []
        }
        
        # Configurações do dashboard
        self.config = {
            'refresh_rate': 'auto',  # auto, manual, custom
            'alert_threshold': 'medium',  # low, medium, high
            'display_mode': 'full',  # full, compact, minimal
            'auto_refresh': True,
            'sound_alerts': False,
            'email_notifications': False,
            'export_enabled': True
        }
        
        # Tasks assíncronas
        self._update_tasks = []
    
    async def initialize(self) -> bool:
        """Inicializa o dashboard"""
        try:
            # Verificar se AEGIS Plugin está disponível
            if not self.aegis_plugin:
                montar_log("Dashboard iniciado sem conexão com AEGIS Plugin", "WARNING")
            
            # Carregar dados históricos se existirem
            await self._load_historical_data()
            
            # Iniciar atualizações automáticas
            if self.config['auto_refresh']:
                await self._start_auto_updates()
            
            self._dashboard_active = True
            
            montar_log("AEGIS Dashboard inicializado", "INFO")
            return True
            
        except Exception as e:
            montar_log(f"Erro ao inicializar dashboard: {e}", "ERROR")
            return False
    
    async def get_dashboard_data(self) -> Dict[str, Any]:
        """Retorna dados completos do dashboard"""
        try:
            if self.aegis_plugin:
                await self._update_from_aegis()
            
            # Adicionar timestamp da última atualização
            self.dashboard_data['last_updated'] = datetime.now().isoformat()
            
            return self.dashboard_data.copy()
            
        except Exception as e:
            montar_log(f"Erro ao obter dados do dashboard: {e}", "ERROR")
            return {
                'error': str(e),
                'last_updated': datetime.now().isoformat()
            }
    
    async def get_system_overview(self) -> Dict[str, Any]:
        """Retorna visão geral do sistema"""
        try:
            overview = {
                'system_health': 'unknown',
                'protection_status': 'unknown',
                'components_active': 0,
                'threats_active': 0,
                'last_scan': 'never',
                'uptime': '0:00:00',
                'performance_score': 0.0
            }
            
            if self.aegis_plugin:
                # Obter health check
                health = await self.aegis_plugin.health_check()
                
                overview.update({
                    'system_health': health.get('status', 'unknown'),
                    'protection_status': 'active' if health.get('active', False) else 'inactive',
                    'components_active': sum(1 for comp in health.get('components', {}).values() 
                                           if isinstance(comp, dict) and comp.get('initialized', False)),
                    'threats_active': health.get('threats', {}).get('active_threats', 0),
                    'performance_score': health.get('performance', {}).get('response_time', 0.0)
                })
                
                # Calcular uptime
                uptime_hours = self.aegis_plugin.plugin_metrics.get('uptime_hours', 0)
                if uptime_hours > 0:
                    uptime_seconds = time.time() - uptime_hours
                    overview['uptime'] = self._format_uptime(uptime_seconds)
            
            return overview
            
        except Exception as e:
            montar_log(f"Erro ao obter visão geral: {e}", "ERROR")
            return {
                'error': str(e)
            }
    
    async def get_threat_analysis(self) -> Dict[str, Any]:
        """Retorna análise detalhada de ameaças"""
        try:
            threat_analysis = {
                'current_threats': [],
                'threat_trends': {},
                'risk_assessment': 'low',
                'recommendations': [],
                'blocked_attacks': 0,
                'false_positives': 0
            }
            
            if self.aegis_plugin:
                # Obter dados de ameaças do plugin
                dashboard = await self.aegis_plugin._execute_get_dashboard({})
                
                if dashboard.get('status') == 'success':
                    dash_data = dashboard.get('dashboard', {})
                    
                    # Ameaças atuais
                    recent_events = dash_data.get('recent_events', [])
                    threat_events = [e for e in recent_events if e.get('type', '').endswith('_threat')]
                    threat_analysis['current_threats'] = threat_events
                    
                    # Estatísticas
                    protection_summary = dash_data.get('protection_summary', {})
                    threat_analysis['blocked_attacks'] = protection_summary.get('threats_blocked', 0)
                    
                    # Avaliação de risco baseada na saúde do sistema
                    system_health = dash_data.get('system_health', 1.0)
                    if system_health < 0.5:
                        threat_analysis['risk_assessment'] = 'critical'
                    elif system_health < 0.7:
                        threat_analysis['risk_assessment'] = 'high'
                    elif system_health < 0.9:
                        threat_analysis['risk_assessment'] = 'medium'
                    else:
                        threat_analysis['risk_assessment'] = 'low'
                    
                    # Recomendações baseadas no risco
                    if threat_analysis['risk_assessment'] in ['high', 'critical']:
                        threat_analysis['recommendations'].extend([
                            'Executar scan de segurança profundo',
                            'Verificar integridade de componentes críticos',
                            'Revisar logs de segurança recentes'
                        ])
            
            return threat_analysis
            
        except Exception as e:
            montar_log(f"Erro na análise de ameaças: {e}", "ERROR")
            return {
                'error': str(e)
            }
    
    async def get_component_status(self) -> Dict[str, Any]:
        """Retorna status detalhado dos componentes"""
        try:
            component_status = {
                'aegis_core': {'status': 'unknown', 'metrics': {}},
                'malware_detector': {'status': 'unknown', 'metrics': {}},
                'integrity_monitor': {'status': 'unknown', 'metrics': {}},
                'behavior_analyzer': {'status': 'unknown', 'metrics': {}},
                'crypto_engine': {'status': 'unknown', 'metrics': {}}
            }
            
            if self.aegis_plugin:
                # Obter health check detalhado
                health = await self.aegis_plugin.health_check()
                components_data = health.get('components', {})
                
                for comp_name, comp_data in components_data.items():
                    if comp_name in component_status:
                        status = 'healthy' if comp_data.get('initialized', False) else 'error'
                        component_status[comp_name] = {
                            'status': status,
                            'metrics': comp_data,
                            'last_check': datetime.now().isoformat()
                        }
            
            return component_status
            
        except Exception as e:
            montar_log(f"Erro ao obter status dos componentes: {e}", "ERROR")
            return {
                'error': str(e)
            }
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Retorna métricas de performance"""
        try:
            metrics = {
                'response_times': {
                    'encryption': 0.0,
                    'scanning': 0.0,
                    'analysis': 0.0
                },
                'throughput': {
                    'scans_per_minute': 0.0,
                    'threats_per_hour': 0.0,
                    'data_processed_mb': 0.0
                },
                'resource_usage': {
                    'cpu_usage': 0.0,
                    'memory_usage': 0.0,
                    'disk_usage': 0.0
                },
                'efficiency_scores': {
                    'detection_rate': 0.0,
                    'false_positive_rate': 0.0,
                    'response_accuracy': 0.0
                }
            }
            
            if self.aegis_plugin:
                # Obter métricas dos componentes
                if hasattr(self.aegis_plugin, 'crypto_engine') and self.aegis_plugin.crypto_engine:
                    crypto_metrics = self.aegis_plugin.crypto_engine.metrics
                    metrics['response_times']['encryption'] = crypto_metrics.get('average_encryption_time', 0.0)
                
                if hasattr(self.aegis_plugin, 'malware_detector') and self.aegis_plugin.malware_detector:
                    detector_metrics = self.aegis_plugin.malware_detector.metrics
                    metrics['throughput']['scans_per_minute'] = detector_metrics.get('scans_performed', 0) / max(1, time.time() / 60)
                
                if hasattr(self.aegis_plugin, 'behavior_analyzer') and self.aegis_plugin.behavior_analyzer:
                    analyzer_metrics = self.aegis_plugin.behavior_analyzer.metrics
                    metrics['response_times']['analysis'] = analyzer_metrics.get('average_analysis_time', 0.0)
                    metrics['efficiency_scores']['detection_rate'] = analyzer_metrics.get('model_accuracy', 0.0)
            
            return metrics
            
        except Exception as e:
            montar_log(f"Erro ao obter métricas de performance: {e}", "ERROR")
            return {
                'error': str(e)
            }
    
    async def get_security_report(self, period: str = '24h') -> Dict[str, Any]:
        """Gera relatório de segurança para período especificado"""
        try:
            report = {
                'period': period,
                'generated_at': datetime.now().isoformat(),
                'summary': {
                    'total_scans': 0,
                    'threats_detected': 0,
                    'threats_mitigated': 0,
                    'false_positives': 0,
                    'uptime_percentage': 0.0
                },
                'threat_breakdown': {
                    'malware': 0,
                    'integrity_violations': 0,
                    'behavioral_anomalies': 0,
                    'other': 0
                },
                'performance_summary': {
                    'avg_response_time': 0.0,
                    'peak_load_time': '',
                    'efficiency_score': 0.0
                },
                'recommendations': []
            }
            
            if self.aegis_plugin:
                # Calcular período
                period_hours = self._parse_period(period)
                cutoff_time = datetime.now() - timedelta(hours=period_hours)
                
                # Filtrar eventos do período
                recent_events = [
                    event for event in self.aegis_plugin.security_events
                    if datetime.fromisoformat(event.get('timestamp', '1970-01-01')) > cutoff_time
                ]
                
                # Calcular estatísticas
                report['summary']['total_scans'] = len([e for e in recent_events if 'scan' in e.get('type', '')])
                threat_events = [e for e in recent_events if 'threat' in e.get('type', '')]
                report['summary']['threats_detected'] = len(threat_events)
                
                # Breakdown de ameaças
                for event in threat_events:
                    event_type = event.get('type', '')
                    if 'malware' in event_type:
                        report['threat_breakdown']['malware'] += 1
                    elif 'integrity' in event_type:
                        report['threat_breakdown']['integrity_violations'] += 1
                    elif 'behavior' in event_type:
                        report['threat_breakdown']['behavioral_anomalies'] += 1
                    else:
                        report['threat_breakdown']['other'] += 1
                
                # Calcular uptime
                total_seconds = period_hours * 3600
                downtime_events = [e for e in recent_events if e.get('type') == 'system_down']
                downtime_seconds = len(downtime_events) * 60  # Estimar 1 min por evento
                uptime_percentage = ((total_seconds - downtime_seconds) / total_seconds) * 100
                report['summary']['uptime_percentage'] = uptime_percentage
                
                # Gerar recomendações
                if report['summary']['threats_detected'] > 10:
                    report['recommendations'].append('Considerar aumentar frequência de scans')
                
                if uptime_percentage < 99.9:
                    report['recommendations'].append('Investigar causas de downtime')
                
                if report['threat_breakdown']['malware'] > 0:
                    report['recommendations'].append('Atualizar assinaturas de malware')
            
            return report
            
        except Exception as e:
            montar_log(f"Erro ao gerar relatório: {e}", "ERROR")
            return {
                'error': str(e)
            }
    
    async def execute_command(self, command: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Executa comando no sistema AEGIS"""
        try:
            params = params or {}
            
            if not self.aegis_plugin:
                return {
                    'success': False,
                    'error': 'AEGIS Plugin não está disponível'
                }
            
            if command == 'start_scan':
                scan_type = params.get('scan_type', 'standard')
                result = await self.aegis_plugin.execute({
                    'operation': 'threat_scan',
                    'scan_type': scan_type,
                    'target': params.get('target', 'all')
                })
                
            elif command == 'emergency_stop':
                result = await self.aegis_plugin.execute({
                    'operation': 'emergency_response',
                    'action': 'lockdown',
                    'threat_level': 'critical'
                })
                
            elif command == 'quarantine_component':
                component_id = params.get('component_id')
                if not component_id:
                    return {
                        'success': False,
                        'error': 'component_id é obrigatório'
                    }
                
                result = await self.aegis_plugin.execute({
                    'operation': 'emergency_response',
                    'action': 'quarantine',
                    'component_id': component_id
                })
                
            elif command == 'update_config':
                new_config = params.get('config', {})
                await self.aegis_plugin.configure(new_config)
                result = {
                    'status': 'success',
                    'message': 'Configuração atualizada'
                }
                
            elif command == 'export_logs':
                # Implementar exportação de logs
                result = await self._export_security_logs(params)
                
            else:
                return {
                    'success': False,
                    'error': f'Comando não reconhecido: {command}'
                }
            
            return {
                'success': result.get('status') == 'success',
                'result': result,
                'executed_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            montar_log(f"Erro ao executar comando {command}: {e}", "ERROR")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_live_metrics(self) -> Dict[str, Any]:
        """Retorna métricas em tempo real"""
        try:
            live_metrics = {
                'timestamp': datetime.now().isoformat(),
                'system_load': 0.0,
                'active_scans': 0,
                'threat_level': 'safe',
                'response_time': 0.0,
                'memory_usage': 0.0,
                'cpu_usage': 0.0,
                'network_activity': 0.0,
                'components_status': {}
            }
            
            if self.aegis_plugin:
                # Obter métricas em tempo real
                health = await self.aegis_plugin.health_check()
                
                live_metrics.update({
                    'threat_level': health.get('threats', {}).get('current_level', 'safe'),
                    'response_time': health.get('performance', {}).get('response_time', 0.0),
                    'memory_usage': health.get('performance', {}).get('memory_usage', 0.0),
                    'cpu_usage': health.get('performance', {}).get('cpu_usage', 0.0)
                })
                
                # Status dos componentes
                for comp_name, comp_data in health.get('components', {}).items():
                    live_metrics['components_status'][comp_name] = {
                        'status': 'online' if comp_data.get('initialized', False) else 'offline',
                        'load': comp_data.get('cpu_usage', 0.0)
                    }
                
                # Calcular carga do sistema
                active_components = sum(1 for comp in live_metrics['components_status'].values() 
                                      if comp['status'] == 'online')
                total_components = len(live_metrics['components_status'])
                live_metrics['system_load'] = (active_components / max(1, total_components)) * 100
            
            return live_metrics
            
        except Exception as e:
            montar_log(f"Erro ao obter métricas live: {e}", "ERROR")
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    # Métodos privados de suporte
    
    async def _update_from_aegis(self):
        """Atualiza dados do dashboard a partir do AEGIS"""
        try:
            # Obter dados do plugin
            dashboard_result = await self.aegis_plugin._execute_get_dashboard({})
            
            if dashboard_result.get('status') == 'success':
                aegis_dashboard = dashboard_result.get('dashboard', {})
                
                # Atualizar dados do dashboard
                self.dashboard_data['system_status'] = {
                    'protection_active': aegis_dashboard.get('status') == 'active',
                    'uptime': aegis_dashboard.get('plugin_info', {}).get('uptime_hours', 0),
                    'protection_level': aegis_dashboard.get('plugin_info', {}).get('protection_level', 'unknown'),
                    'last_update': datetime.now().isoformat()
                }
                
                self.dashboard_data['threat_summary'] = aegis_dashboard.get('protection_summary', {})
                self.dashboard_data['recent_events'] = aegis_dashboard.get('recent_events', [])
                
                # Atualizar métricas de componentes
                component_status = aegis_dashboard.get('component_status', {})
                self.dashboard_data['component_metrics'] = component_status
                
                # Adicionar ao histórico
                self._add_to_history(aegis_dashboard)
            
        except Exception as e:
            montar_log(f"Erro ao atualizar dados do AEGIS: {e}", "ERROR")
    
    def _add_to_history(self, dashboard_data: Dict[str, Any]):
        """Adiciona dados ao histórico para gráficos"""
        try:
            timestamp = time.time()
            
            # Threats over time
            threats_count = len(dashboard_data.get('recent_events', []))
            self.metrics_history['threats_over_time'].append({
                'timestamp': timestamp,
                'count': threats_count
            })
            
            # System health
            system_health = dashboard_data.get('system_health', 1.0)
            self.metrics_history['component_health'].append({
                'timestamp': timestamp,
                'health_score': system_health
            })
            
            # Limitar tamanho do histórico
            max_history_points = 1440  # 24 horas em minutos
            for history_type in self.metrics_history:
                if len(self.metrics_history[history_type]) > max_history_points:
                    self.metrics_history[history_type] = self.metrics_history[history_type][-max_history_points:]
            
        except Exception as e:
            montar_log(f"Erro ao adicionar ao histórico: {e}", "ERROR")
    
    async def _load_historical_data(self):
        """Carrega dados históricos se existirem"""
        try:
            history_file = Path("aegis_dashboard_history.json")
            if history_file.exists():
                with open(history_file, 'r') as f:
                    data = json.load(f)
                    self.metrics_history.update(data.get('metrics_history', {}))
                    
                montar_log("Dados históricos do dashboard carregados", "INFO")
            
        except Exception as e:
            montar_log(f"Erro ao carregar dados históricos: {e}", "ERROR")
    
    async def _save_historical_data(self):
        """Salva dados históricos"""
        try:
            data = {
                'metrics_history': self.metrics_history,
                'saved_at': datetime.now().isoformat()
            }
            
            history_file = Path("aegis_dashboard_history.json")
            with open(history_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            montar_log(f"Erro ao salvar dados históricos: {e}", "ERROR")
    
    async def _start_auto_updates(self):
        """Inicia atualizações automáticas do dashboard"""
        try:
            update_task = asyncio.create_task(self._auto_update_loop())
            self._update_tasks.append(update_task)
            
        except Exception as e:
            montar_log(f"Erro ao iniciar auto-updates: {e}", "ERROR")
    
    async def _auto_update_loop(self):
        """Loop de atualização automática"""
        while self._dashboard_active:
            try:
                if self.aegis_plugin:
                    await self._update_from_aegis()
                
                # Salvar dados históricos periodicamente
                if int(time.time()) % 300 == 0:  # A cada 5 minutos
                    await self._save_historical_data()
                
                await asyncio.sleep(self._update_interval)
                
            except Exception as e:
                montar_log(f"Erro no loop de atualização: {e}", "ERROR")
                await asyncio.sleep(30)  # Aguardar mais tempo em caso de erro
    
    async def _export_security_logs(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Exporta logs de segurança"""
        try:
            format_type = params.get('format', 'json')  # json, csv, txt
            period = params.get('period', '24h')
            
            # Obter eventos do período
            period_hours = self._parse_period(period)
            cutoff_time = datetime.now() - timedelta(hours=period_hours)
            
            events = []
            if self.aegis_plugin:
                events = [
                    event for event in self.aegis_plugin.security_events
                    if datetime.fromisoformat(event.get('timestamp', '1970-01-01')) > cutoff_time
                ]
            
            # Gerar arquivo de exportação
            export_filename = f"aegis_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}"
            export_path = Path(export_filename)
            
            if format_type == 'json':
                with open(export_path, 'w') as f:
                    json.dump(events, f, indent=2)
            elif format_type == 'csv':
                # Implementar exportação CSV
                import csv
                with open(export_path, 'w', newline='') as f:
                    if events:
                        writer = csv.DictWriter(f, fieldnames=events[0].keys())
                        writer.writeheader()
                        writer.writerows(events)
            else:
                # Formato texto
                with open(export_path, 'w') as f:
                    for event in events:
                        f.write(f"{event.get('timestamp', 'N/A')} - {event.get('type', 'N/A')} - {event.get('description', 'N/A')}\n")
            
            return {
                'status': 'success',
                'filename': export_filename,
                'events_exported': len(events),
                'format': format_type
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _parse_period(self, period: str) -> float:
        """Converte período string para horas"""
        try:
            if period.endswith('h'):
                return float(period[:-1])
            elif period.endswith('d'):
                return float(period[:-1]) * 24
            elif period.endswith('w'):
                return float(period[:-1]) * 24 * 7
            else:
                return 24.0  # Padrão: 24 horas
                
        except:
            return 24.0
    
    def _format_uptime(self, seconds: float) -> str:
        """Formata uptime em string legível"""
        try:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
            
        except:
            return "0:00:00"
    
    async def shutdown(self):
        """Finaliza o dashboard"""
        try:
            self._dashboard_active = False
            
            # Parar tasks
            for task in self._update_tasks:
                task.cancel()
            
            # Salvar dados finais
            await self._save_historical_data()
            
            montar_log("AEGIS Dashboard finalizado", "INFO")
            
        except Exception as e:
            montar_log(f"Erro ao finalizar dashboard: {e}", "ERROR")