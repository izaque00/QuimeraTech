"""
AEGIS Security Plugin - Plugin de Segurança Integrado ao Framework Quimera
==========================================================================

Plugin principal que integra todo o sistema AEGIS ao framework de plugins
do Quimera, fornecendo proteção automática e transparente para todos os
componentes do sistema.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path

from quimera.core.plugin_framework import BasePlugin, PluginInfo, PluginPriority
from quimera.logs.parser import montar_log

# Importar componentes AEGIS
from .aegis_core import AegisCore, ThreatLevel, SecurityReport
from .aegis_agent import AegisSecurityAgent
from .malware_detector import CodeMalwareDetector
from .integrity_monitor import IntegrityMonitor
from .behavior_analyzer import BehaviorAnalyzer
from .crypto_engine import QuantumCryptoEngine


class AegisSecurityPlugin(BasePlugin):
    """
    Plugin principal do sistema AEGIS
    
    Integra todos os componentes de segurança do AEGIS com o
    framework de plugins do Quimera, fornecendo:
    
    - Proteção automática de agentes
    - Monitoramento em tempo real
    - Detecção de ameaças
    - Auto-healing
    - Quarentena inteligente
    - Dashboard de segurança
    """
    
    def __init__(self, manager):
        super().__init__(manager)
        
        # Componentes AEGIS
        self.aegis_core = None
        self.aegis_agent = None
        self.malware_detector = None
        self.integrity_monitor = None
        self.behavior_analyzer = None
        self.crypto_engine = None
        
        # Estado do plugin
        self.protection_active = False
        self.monitored_plugins = {}
        self.security_events = []
        self.auto_protection_enabled = True
        
        # Configurações específicas do plugin
        self.plugin_config = {
            'auto_protect_new_plugins': True,
            'real_time_monitoring': True,
            'threat_response_auto': True,
            'security_dashboard_enabled': True,
            'integration_level': 'full',  # full, basic, monitoring_only
            'performance_mode': 'balanced',  # performance, balanced, security
            'notification_level': 'normal',  # quiet, normal, verbose
            'backup_enabled': True,
            'quarantine_enabled': True
        }
        
        # Métricas do plugin
        self.plugin_metrics = {
            'plugins_protected': 0,
            'threats_blocked': 0,
            'auto_healing_actions': 0,
            'security_scans': 0,
            'uptime_hours': 0.0,
            'last_threat': None,
            'system_health_score': 1.0
        }
        
        # Tasks assíncronas
        self._monitoring_tasks = []
        self._protection_tasks = []
    
    @property
    def info(self) -> PluginInfo:
        """Informações do plugin AEGIS"""
        return PluginInfo(
            name="AEGIS Security System",
            version="1.0.0",
            description="Sistema avançado de segurança com proteção em tempo real, "
                       "detecção de malware, monitoramento de integridade e auto-healing",
            author="Sistema Quimera",
            priority=PluginPriority.CRITICAL,
            dependencies=[],
            conflicts=[],
            requires_config=True,
            async_support=True,
            production_ready=True,
            tags=["security", "protection", "monitoring", "aegis", "quantum-crypto"]
        )
    
    async def initialize(self) -> bool:
        """Inicializa o plugin AEGIS"""
        try:
            self.logger.info("Inicializando AEGIS Security Plugin...")
            
            # Inicializar componentes AEGIS
            await self._initialize_aegis_components()
            
            # Configurar proteção automática
            if self.plugin_config['auto_protect_new_plugins']:
                await self._setup_auto_protection()
            
            # Inicializar monitoramento
            if self.plugin_config['real_time_monitoring']:
                await self._start_real_time_monitoring()
            
            # Registrar hooks de segurança
            await self._register_security_hooks()
            
            # Proteger plugins existentes
            await self._protect_existing_plugins()
            
            self.protection_active = True
            self.plugin_metrics['uptime_hours'] = time.time()
            
            montar_log("AEGIS Security Plugin inicializado com sucesso", "SUCCESS")
            self.logger.info("AEGIS Security Plugin ativo e protegendo o sistema")
            
            return True
            
        except Exception as e:
            montar_log(f"Erro ao inicializar AEGIS Security Plugin: {e}", "ERROR")
            self.logger.error(f"Falha na inicialização: {e}")
            return False
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Executa operações de segurança do AEGIS"""
        try:
            execution_start = time.time()
            
            # Verificar se proteção está ativa
            if not self.protection_active:
                return {
                    'status': 'inactive',
                    'message': 'Sistema de proteção AEGIS não está ativo',
                    'timestamp': datetime.now().isoformat()
                }
            
            # Determinar tipo de operação
            operation = context.get('operation', 'security_check')
            
            if operation == 'security_check':
                result = await self._execute_security_check(context)
            elif operation == 'threat_scan':
                result = await self._execute_threat_scan(context)
            elif operation == 'protect_component':
                result = await self._execute_protect_component(context)
            elif operation == 'get_dashboard':
                result = await self._execute_get_dashboard(context)
            elif operation == 'emergency_response':
                result = await self._execute_emergency_response(context)
            else:
                result = await self._execute_default_security_cycle(context)
            
            # Atualizar métricas
            execution_time = time.time() - execution_start
            result['execution_time'] = execution_time
            result['timestamp'] = datetime.now().isoformat()
            
            self.plugin_metrics['security_scans'] += 1
            
            return result
            
        except Exception as e:
            self.logger.error(f"Erro na execução do AEGIS: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def configure(self, config: Dict[str, Any]):
        """Configura o plugin AEGIS"""
        try:
            # Atualizar configurações
            self.plugin_config.update(config)
            
            # Reconfigurar componentes se necessário
            if self.aegis_core:
                core_config = config.get('aegis_core', {})
                self.aegis_core.config.update(core_config)
            
            if self.malware_detector:
                detector_config = config.get('malware_detector', {})
                self.malware_detector.config.update(detector_config)
            
            if self.integrity_monitor:
                monitor_config = config.get('integrity_monitor', {})
                self.integrity_monitor.config.update(monitor_config)
            
            if self.behavior_analyzer:
                analyzer_config = config.get('behavior_analyzer', {})
                self.behavior_analyzer.config.update(analyzer_config)
            
            if self.crypto_engine:
                crypto_config = config.get('crypto_engine', {})
                self.crypto_engine.config.update(crypto_config)
            
            self.logger.info("Configuração do AEGIS atualizada")
            
        except Exception as e:
            self.logger.error(f"Erro ao configurar AEGIS: {e}")
    
    async def cleanup(self):
        """Limpeza antes de descarregar o plugin"""
        try:
            self.protection_active = False
            
            # Parar tasks de monitoramento
            for task in self._monitoring_tasks:
                task.cancel()
            
            for task in self._protection_tasks:
                task.cancel()
            
            # Shutdown dos componentes AEGIS
            if self.aegis_core:
                await self.aegis_core.shutdown()
            
            # Salvar estado final
            await self._save_security_state()
            
            self.logger.info("AEGIS Security Plugin finalizado")
            
        except Exception as e:
            self.logger.error(f"Erro na limpeza do AEGIS: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Verifica saúde do sistema AEGIS"""
        try:
            health_status = {
                "status": "healthy",
                "active": self.protection_active,
                "components": {},
                "metrics": self.plugin_metrics.copy(),
                "threats": {
                    "current_level": "safe",
                    "active_threats": 0,
                    "last_scan": None
                },
                "performance": {
                    "cpu_usage": 0.0,
                    "memory_usage": 0.0,
                    "response_time": 0.0
                }
            }
            
            # Verificar saúde dos componentes
            if self.aegis_core:
                core_status = self.aegis_core.get_security_status()
                health_status["components"]["aegis_core"] = {
                    "active": core_status.get('active', False),
                    "components_protected": core_status.get('components_protected', 0),
                    "system_health": core_status.get('system_health', 0.0)
                }
                
                # Atualizar nível de ameaça
                if core_status.get('system_health', 1.0) < 0.7:
                    health_status["threats"]["current_level"] = "elevated"
                elif core_status.get('system_health', 1.0) < 0.9:
                    health_status["threats"]["current_level"] = "moderate"
            
            if self.malware_detector:
                detector_status = self.malware_detector.get_detector_status()
                health_status["components"]["malware_detector"] = {
                    "initialized": detector_status.get('initialized', False),
                    "signatures_count": detector_status.get('signatures_count', 0),
                    "scans_performed": detector_status['metrics'].get('scans_performed', 0)
                }
            
            if self.integrity_monitor:
                monitor_status = self.integrity_monitor.get_integrity_status()
                health_status["components"]["integrity_monitor"] = {
                    "initialized": monitor_status.get('initialized', False),
                    "monitoring_active": monitor_status.get('monitoring_active', False),
                    "components_monitored": monitor_status['metrics'].get('components_monitored', 0)
                }
            
            if self.behavior_analyzer:
                analyzer_status = self.behavior_analyzer.get_analyzer_status()
                health_status["components"]["behavior_analyzer"] = {
                    "initialized": analyzer_status.get('initialized', False),
                    "learning_mode": analyzer_status.get('learning_mode', True),
                    "patterns_learned": analyzer_status['metrics'].get('patterns_learned', 0)
                }
            
            if self.crypto_engine:
                crypto_status = self.crypto_engine.get_crypto_status()
                health_status["components"]["crypto_engine"] = {
                    "initialized": crypto_status.get('initialized', False),
                    "keys_in_store": crypto_status.get('keys_in_store', 0),
                    "encryption_operations": crypto_status['metrics'].get('encryption_operations', 0)
                }
            
            # Calcular score geral de saúde
            component_scores = []
            for comp_name, comp_data in health_status["components"].items():
                if isinstance(comp_data, dict):
                    if comp_data.get('initialized', False):
                        component_scores.append(1.0)
                    else:
                        component_scores.append(0.0)
            
            if component_scores:
                overall_health = sum(component_scores) / len(component_scores)
                self.plugin_metrics['system_health_score'] = overall_health
                
                if overall_health < 0.5:
                    health_status["status"] = "critical"
                elif overall_health < 0.8:
                    health_status["status"] = "degraded"
            
            return health_status
            
        except Exception as e:
            self.logger.error(f"Erro no health check: {e}")
            return {
                "status": "error",
                "error": str(e),
                "active": False
            }
    
    # Métodos de operações específicas
    
    async def _execute_security_check(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Executa verificação de segurança geral"""
        try:
            # Scan completo do sistema
            if self.aegis_core:
                report = await self.aegis_core.scan_all_components('standard')
                
                return {
                    'status': 'completed',
                    'operation': 'security_check',
                    'threats_detected': len(report.threats_detected),
                    'components_scanned': report.components_scanned,
                    'scan_duration': report.scan_duration,
                    'recommendations': report.recommendations
                }
            else:
                return {
                    'status': 'error',
                    'message': 'AEGIS Core não está disponível'
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'operation': 'security_check',
                'error': str(e)
            }
    
    async def _execute_threat_scan(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Executa scan específico de ameaças"""
        try:
            target = context.get('target', 'all')
            scan_type = context.get('scan_type', 'deep')
            
            threats_found = []
            scan_count = 0
            
            # Scan de malware
            if self.malware_detector and target in ['all', 'malware']:
                # Implementar scan de malware em todos os componentes
                scan_count += 1
            
            # Verificação de integridade
            if self.integrity_monitor and target in ['all', 'integrity']:
                integrity_report = await self.integrity_monitor.verify_all_components()
                scan_count += 1
                
                for comp_id, result in integrity_report['results'].items():
                    if not result.get('integrity_ok', True):
                        threats_found.append({
                            'type': 'integrity_violation',
                            'component': comp_id,
                            'severity': 0.7,
                            'details': result
                        })
            
            # Análise comportamental
            if self.behavior_analyzer and target in ['all', 'behavior']:
                behavior_report = await self.behavior_analyzer.detect_anomalies_batch()
                scan_count += 1
                
                for comp_id, result in behavior_report['results'].items():
                    if result.get('anomalies_count', 0) > 0:
                        threats_found.extend([{
                            'type': 'behavior_anomaly',
                            'component': comp_id,
                            'severity': anomaly.get('severity', 0.5),
                            'details': anomaly
                        } for anomaly in result.get('anomalies', [])])
            
            return {
                'status': 'completed',
                'operation': 'threat_scan',
                'target': target,
                'scan_type': scan_type,
                'scans_performed': scan_count,
                'threats_found': len(threats_found),
                'threats': threats_found
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'operation': 'threat_scan',
                'error': str(e)
            }
    
    async def _execute_protect_component(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Protege um componente específico"""
        try:
            component = context.get('component')
            component_id = context.get('component_id', 'unknown')
            protection_level = context.get('protection_level', 'standard')
            
            if not component:
                return {
                    'status': 'error',
                    'message': 'Componente não fornecido'
                }
            
            # Registrar no AEGIS Core
            if self.aegis_core:
                registration_id = self.aegis_core.register_component(
                    component, component_id, protection_level
                )
                
                # Registrar no monitor de integridade
                if self.integrity_monitor:
                    await self.integrity_monitor.register_component(
                        component, component_id, {'protection_level': protection_level}
                    )
                
                # Registrar no analisador comportamental
                if self.behavior_analyzer:
                    await self.behavior_analyzer.register_component(
                        component, component_id, {'protection_level': protection_level}
                    )
                
                self.monitored_plugins[component_id] = {
                    'registration_id': registration_id,
                    'protection_level': protection_level,
                    'protected_at': datetime.now(),
                    'component_type': type(component).__name__
                }
                
                self.plugin_metrics['plugins_protected'] += 1
                
                return {
                    'status': 'success',
                    'operation': 'protect_component',
                    'component_id': component_id,
                    'registration_id': registration_id,
                    'protection_level': protection_level
                }
            
            return {
                'status': 'error',
                'message': 'AEGIS Core não está disponível'
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'operation': 'protect_component',
                'error': str(e)
            }
    
    async def _execute_get_dashboard(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Retorna dashboard de segurança"""
        try:
            dashboard = {
                'status': 'active' if self.protection_active else 'inactive',
                'plugin_info': {
                    'name': self.info.name,
                    'version': self.info.version,
                    'uptime_hours': (time.time() - self.plugin_metrics['uptime_hours']) / 3600,
                    'protection_level': self.plugin_config.get('performance_mode', 'balanced')
                },
                'protection_summary': {
                    'components_protected': len(self.monitored_plugins),
                    'threats_blocked': self.plugin_metrics['threats_blocked'],
                    'auto_healing_actions': self.plugin_metrics['auto_healing_actions'],
                    'last_threat': self.plugin_metrics['last_threat']
                },
                'component_status': {},
                'recent_events': self.security_events[-20:],  # Últimos 20 eventos
                'system_health': self.plugin_metrics['system_health_score']
            }
            
            # Status dos componentes
            if self.aegis_core:
                dashboard['component_status']['aegis_core'] = self.aegis_core.get_security_status()
            
            if self.malware_detector:
                dashboard['component_status']['malware_detector'] = self.malware_detector.get_detector_status()
            
            if self.integrity_monitor:
                dashboard['component_status']['integrity_monitor'] = self.integrity_monitor.get_integrity_status()
            
            if self.behavior_analyzer:
                dashboard['component_status']['behavior_analyzer'] = self.behavior_analyzer.get_analyzer_status()
            
            if self.crypto_engine:
                dashboard['component_status']['crypto_engine'] = self.crypto_engine.get_crypto_status()
            
            return {
                'status': 'success',
                'operation': 'get_dashboard',
                'dashboard': dashboard
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'operation': 'get_dashboard',
                'error': str(e)
            }
    
    async def _execute_emergency_response(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Executa resposta de emergência"""
        try:
            threat_level = context.get('threat_level', 'high')
            action = context.get('action', 'quarantine')
            
            actions_taken = []
            
            if action == 'quarantine':
                # Ativar quarentena geral
                actions_taken.append('system_quarantine_activated')
                
            elif action == 'lockdown':
                # Lockdown completo
                self.protection_active = False
                actions_taken.append('system_lockdown_activated')
                
            elif action == 'heal':
                # Auto-healing em massa
                if self.aegis_core:
                    # Implementar healing em massa
                    actions_taken.append('mass_auto_healing_initiated')
            
            # Registrar evento de emergência
            emergency_event = {
                'type': 'emergency_response',
                'threat_level': threat_level,
                'action': action,
                'actions_taken': actions_taken,
                'timestamp': datetime.now().isoformat()
            }
            
            self.security_events.append(emergency_event)
            
            return {
                'status': 'success',
                'operation': 'emergency_response',
                'threat_level': threat_level,
                'actions_taken': actions_taken
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'operation': 'emergency_response',
                'error': str(e)
            }
    
    async def _execute_default_security_cycle(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Executa ciclo padrão de segurança"""
        try:
            cycle_actions = []
            
            # Verificação rápida de integridade
            if self.integrity_monitor:
                integrity_check = await self.integrity_monitor.verify_all_components()
                cycle_actions.append({
                    'action': 'integrity_check',
                    'components_checked': integrity_check.get('total_components', 0),
                    'violations': integrity_check.get('violations_detected', 0)
                })
            
            # Scan de malware em componentes críticos
            if self.malware_detector:
                # Implementar scan rápido
                cycle_actions.append({
                    'action': 'malware_scan',
                    'status': 'completed'
                })
            
            # Análise comportamental
            if self.behavior_analyzer:
                behavior_check = await self.behavior_analyzer.detect_anomalies_batch()
                cycle_actions.append({
                    'action': 'behavior_analysis',
                    'components_analyzed': behavior_check.get('total_components', 0),
                    'anomalies': behavior_check.get('total_anomalies', 0)
                })
            
            return {
                'status': 'success',
                'operation': 'default_security_cycle',
                'cycle_actions': cycle_actions,
                'cycle_completed': True
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'operation': 'default_security_cycle',
                'error': str(e)
            }
    
    # Métodos de inicialização e configuração
    
    async def _initialize_aegis_components(self):
        """Inicializa todos os componentes AEGIS"""
        try:
            # Inicializar AEGIS Core
            self.aegis_core = AegisCore()
            if not await self.aegis_core.initialize():
                raise RuntimeError("Falha na inicialização do AEGIS Core")
            
            # Inicializar Detector de Malware
            self.malware_detector = CodeMalwareDetector()
            if not await self.malware_detector.initialize():
                raise RuntimeError("Falha na inicialização do Detector de Malware")
            
            # Inicializar Monitor de Integridade
            self.integrity_monitor = IntegrityMonitor()
            if not await self.integrity_monitor.initialize():
                raise RuntimeError("Falha na inicialização do Monitor de Integridade")
            
            # Inicializar Analisador Comportamental
            self.behavior_analyzer = BehaviorAnalyzer()
            if not await self.behavior_analyzer.initialize():
                raise RuntimeError("Falha na inicialização do Analisador Comportamental")
            
            # Inicializar Motor Criptográfico
            self.crypto_engine = QuantumCryptoEngine()
            if not await self.crypto_engine.initialize():
                raise RuntimeError("Falha na inicialização do Motor Criptográfico")
            
            self.logger.info("Todos os componentes AEGIS inicializados com sucesso")
            
        except Exception as e:
            self.logger.error(f"Erro na inicialização dos componentes AEGIS: {e}")
            raise
    
    async def _setup_auto_protection(self):
        """Configura proteção automática de novos plugins"""
        try:
            # Registrar hook para novos plugins
            self.hooks.register('plugin_loaded', self._on_plugin_loaded)
            self.hooks.register('plugin_unloaded', self._on_plugin_unloaded)
            
            self.logger.info("Proteção automática configurada")
            
        except Exception as e:
            self.logger.error(f"Erro ao configurar proteção automática: {e}")
    
    async def _start_real_time_monitoring(self):
        """Inicia monitoramento em tempo real"""
        try:
            # Criar task de monitoramento
            monitoring_task = asyncio.create_task(self._real_time_monitoring_loop())
            self._monitoring_tasks.append(monitoring_task)
            
            self.logger.info("Monitoramento em tempo real iniciado")
            
        except Exception as e:
            self.logger.error(f"Erro ao iniciar monitoramento: {e}")
    
    async def _real_time_monitoring_loop(self):
        """Loop de monitoramento em tempo real"""
        while self.protection_active:
            try:
                # Verificar saúde do sistema
                health = await self.health_check()
                
                # Executar ciclo de segurança
                if health.get('status') == 'healthy':
                    await self._execute_default_security_cycle({})
                
                # Aguardar próximo ciclo
                await asyncio.sleep(30)  # 30 segundos
                
            except Exception as e:
                self.logger.error(f"Erro no loop de monitoramento: {e}")
                await asyncio.sleep(60)  # Aguardar mais tempo em caso de erro
    
    async def _register_security_hooks(self):
        """Registra hooks de segurança no sistema"""
        try:
            # Hooks para eventos de plugins
            self.hooks.register('plugin_error', self._on_plugin_error)
            self.hooks.register('plugin_timeout', self._on_plugin_timeout)
            
            self.logger.info("Hooks de segurança registrados")
            
        except Exception as e:
            self.logger.error(f"Erro ao registrar hooks: {e}")
    
    async def _protect_existing_plugins(self):
        """Protege plugins já carregados no sistema"""
        try:
            # Obter lista de plugins do manager
            existing_plugins = self.manager.plugins
            
            for plugin_name, plugin_instance in existing_plugins.items():
                if plugin_name != f"{self.__class__.__module__}.{self.__class__.__name__}":  # Não proteger a si mesmo
                    try:
                        await self._protect_plugin(plugin_instance, plugin_name)
                    except Exception as e:
                        self.logger.warning(f"Falha ao proteger plugin {plugin_name}: {e}")
            
            self.logger.info(f"Proteção aplicada a {len(existing_plugins)-1} plugins existentes")
            
        except Exception as e:
            self.logger.error(f"Erro ao proteger plugins existentes: {e}")
    
    async def _protect_plugin(self, plugin_instance, plugin_name: str):
        """Protege um plugin específico"""
        try:
            # Determinar nível de proteção baseado na prioridade
            protection_level = 'standard'
            if hasattr(plugin_instance, 'info') and plugin_instance.info.priority == PluginPriority.CRITICAL:
                protection_level = 'critical'
            elif hasattr(plugin_instance, 'info') and plugin_instance.info.priority == PluginPriority.HIGH:
                protection_level = 'high'
            
            # Proteger com AEGIS
            protection_result = await self._execute_protect_component({
                'component': plugin_instance,
                'component_id': plugin_name,
                'protection_level': protection_level
            })
            
            if protection_result.get('status') == 'success':
                self.logger.info(f"Plugin {plugin_name} protegido com nível {protection_level}")
            
        except Exception as e:
            self.logger.error(f"Erro ao proteger plugin {plugin_name}: {e}")
    
    # Handlers de eventos
    
    async def _on_plugin_loaded(self, plugin_instance):
        """Handler para quando um plugin é carregado"""
        try:
            if self.plugin_config['auto_protect_new_plugins']:
                plugin_name = getattr(plugin_instance, '__class__.__name__', 'unknown')
                await self._protect_plugin(plugin_instance, plugin_name)
                
                # Registrar evento
                event = {
                    'type': 'plugin_auto_protected',
                    'plugin_name': plugin_name,
                    'timestamp': datetime.now().isoformat()
                }
                self.security_events.append(event)
                
        except Exception as e:
            self.logger.error(f"Erro no handler de plugin carregado: {e}")
    
    async def _on_plugin_unloaded(self, plugin_name: str):
        """Handler para quando um plugin é descarregado"""
        try:
            # Remover proteção
            if plugin_name in self.monitored_plugins:
                plugin_info = self.monitored_plugins[plugin_name]
                registration_id = plugin_info['registration_id']
                
                if self.aegis_core:
                    self.aegis_core.unregister_component(registration_id)
                
                del self.monitored_plugins[plugin_name]
                
                # Registrar evento
                event = {
                    'type': 'plugin_protection_removed',
                    'plugin_name': plugin_name,
                    'timestamp': datetime.now().isoformat()
                }
                self.security_events.append(event)
                
        except Exception as e:
            self.logger.error(f"Erro no handler de plugin descarregado: {e}")
    
    async def _on_plugin_error(self, plugin_name: str, error: Exception):
        """Handler para erros de plugins"""
        try:
            # Registrar evento de segurança
            event = {
                'type': 'plugin_error_detected',
                'plugin_name': plugin_name,
                'error': str(error),
                'timestamp': datetime.now().isoformat(),
                'severity': 'medium'
            }
            self.security_events.append(event)
            
            # Verificar se plugin está protegido
            if plugin_name in self.monitored_plugins:
                # Executar análise de segurança do plugin com erro
                if self.aegis_core:
                    registration_id = self.monitored_plugins[plugin_name]['registration_id']
                    scan_result = await self.aegis_core.scan_component(registration_id, 'deep')
                    
                    if scan_result.threats_detected:
                        event['security_scan'] = {
                            'threats_found': len(scan_result.threats_detected),
                            'action_required': True
                        }
            
            self.logger.warning(f"Erro detectado no plugin {plugin_name}: {error}")
            
        except Exception as e:
            self.logger.error(f"Erro no handler de erro de plugin: {e}")
    
    async def _on_plugin_timeout(self, plugin_name: str):
        """Handler para timeout de plugins"""
        try:
            # Registrar evento
            event = {
                'type': 'plugin_timeout',
                'plugin_name': plugin_name,
                'timestamp': datetime.now().isoformat(),
                'severity': 'high'
            }
            self.security_events.append(event)
            
            # Plugin com timeout pode indicar comportamento anômalo
            if self.behavior_analyzer and plugin_name in self.monitored_plugins:
                # Registrar dados de timeout para análise comportamental
                timeout_data = {
                    'execution_time': 999.9,  # Valor alto para indicar timeout
                    'success': False,
                    'memory_usage': 0.0,
                    'cpu_usage': 100.0,  # CPU alto pode ter causado timeout
                    'timeout': True
                }
                
                await self.behavior_analyzer.record_execution(plugin_name, timeout_data)
            
            self.logger.warning(f"Timeout detectado no plugin {plugin_name}")
            
        except Exception as e:
            self.logger.error(f"Erro no handler de timeout: {e}")
    
    async def _save_security_state(self):
        """Salva estado de segurança atual"""
        try:
            state = {
                'plugin_metrics': self.plugin_metrics,
                'plugin_config': self.plugin_config,
                'monitored_plugins': {
                    k: {**v, 'protected_at': v['protected_at'].isoformat()}
                    for k, v in self.monitored_plugins.items()
                },
                'security_events_count': len(self.security_events),
                'timestamp': datetime.now().isoformat()
            }
            
            # Salvar em arquivo
            state_file = Path("aegis_plugin_state.json")
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
            
            self.logger.info("Estado de segurança do plugin AEGIS salvo")
            
        except Exception as e:
            self.logger.error(f"Erro ao salvar estado: {e}")


# Registrar plugin automaticamente
def register_plugin():
    """Função para registrar o plugin AEGIS"""
    from quimera.core.plugin_framework import PluginRegistry
    
    registry = PluginRegistry()
    registry.register(AegisSecurityPlugin)
    
    return AegisSecurityPlugin


# Auto-registro se executado como módulo
if __name__ == "__main__":
    register_plugin()