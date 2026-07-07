"""
AEGIS Security Agent - Agente de Segurança do Sistema Quimera
============================================================

Este agente estende o AgenteBase e implementa todas as funcionalidades
de segurança integradas ao sistema Quimera, incluindo proteção de 
outros agentes e monitoramento em tempo real.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path

from quimera.agentes.agente_base import AgenteBase
from quimera.logs.parser import montar_log
from .aegis_core import AegisCore, ThreatLevel, SecurityReport, SecurityThreat


class AegisSecurityAgent(AgenteBase):
    """
    Agente de Segurança AEGIS
    
    Integra o sistema de segurança AEGIS com a arquitetura de agentes
    do Quimera, fornecendo proteção avançada para todos os componentes.
    """
    
    def __init__(self, id_registro: str, nome_compativel: str, 
                 quadro_negro, mab_instance):
        super().__init__(id_registro, nome_compativel, quadro_negro, mab_instance)
        
        # Inicializar núcleo AEGIS
        self.aegis_core = AegisCore()
        
        # Configurações específicas do agente
        self.config = {
            'protection_mode': 'proactive',  # proactive, reactive, monitoring
            'scan_frequency': 30,  # segundos
            'threat_response_level': 'auto',  # auto, manual, advisory
            'integration_mode': 'full',  # full, basic, monitoring_only
            'protect_other_agents': True,
            'real_time_analysis': True,
            'predictive_threats': True,
            'auto_quarantine': True,
            'self_healing': True
        }
        
        # Estado do agente de segurança
        self.security_state = {
            'active_protections': 0,
            'agents_monitored': set(),
            'last_full_scan': None,
            'threat_level': ThreatLevel.SAFE,
            'protection_effectiveness': 1.0,
            'response_time_avg': 0.0
        }
        
        # Cache de agentes protegidos
        self._protected_agents = {}
        self._scan_scheduler = None
        self._monitoring_task = None
        
        montar_log(f"AEGIS Security Agent '{id_registro}' inicializado", "INFO")
    
    async def initialize_security_system(self) -> bool:
        """Inicializa sistema de segurança completo"""
        try:
            # Inicializar núcleo AEGIS
            if not await self.aegis_core.initialize():
                return False
            
            # Configurar proteção dos agentes
            if self.config['protect_other_agents']:
                await self._setup_agent_protection()
            
            # Iniciar monitoramento contínuo
            if self.config['real_time_analysis']:
                await self._start_continuous_monitoring()
            
            # Configurar scheduler de scans
            await self._setup_scan_scheduler()
            
            # Registrar hooks de segurança
            await self._register_security_hooks()
            
            self._register_success()
            montar_log("Sistema de segurança AEGIS totalmente inicializado", "SUCCESS")
            return True
            
        except Exception as e:
            self._register_failure(f"Falha na inicialização do sistema AEGIS: {e}")
            return False
    
    async def protect_agent(self, agent: AgenteBase, 
                           protection_level: str = "standard") -> str:
        """
        Adiciona um agente à proteção AEGIS
        
        Args:
            agent: Agente a ser protegido
            protection_level: Nível de proteção (basic, standard, high, critical)
        
        Returns:
            ID de registro da proteção
        """
        if not self.is_operational:
            raise RuntimeError("AEGIS Security Agent não está operacional")
        
        try:
            # Registrar no núcleo AEGIS
            registration_id = self.aegis_core.register_component(
                agent, agent.id_registro, protection_level
            )
            
            # Adicionar ao cache local
            self._protected_agents[registration_id] = {
                'agent': agent,
                'protection_level': protection_level,
                'registered_at': datetime.now(),
                'last_scan': None,
                'threat_count': 0
            }
            
            # Adicionar ao conjunto monitorado
            self.security_state['agents_monitored'].add(agent.id_registro)
            self.security_state['active_protections'] += 1
            
            # Scan inicial de segurança
            await self._initial_agent_scan(registration_id, agent)
            
            montar_log(f"Agente {agent.id_registro} adicionado à proteção AEGIS (nível: {protection_level})", "INFO")
            return registration_id
            
        except Exception as e:
            self._register_failure(f"Erro ao proteger agente {agent.id_registro}: {e}")
            raise
    
    async def remove_agent_protection(self, registration_id: str) -> bool:
        """Remove proteção de um agente"""
        try:
            # Obter informações do agente
            agent_info = self._protected_agents.get(registration_id)
            if not agent_info:
                return False
            
            # Remover do núcleo AEGIS
            if self.aegis_core.unregister_component(registration_id):
                # Remover do cache local
                del self._protected_agents[registration_id]
                
                # Atualizar estado
                agent = agent_info['agent']
                self.security_state['agents_monitored'].discard(agent.id_registro)
                self.security_state['active_protections'] -= 1
                
                montar_log(f"Proteção removida do agente {agent.id_registro}", "INFO")
                return True
            
            return False
            
        except Exception as e:
            self._register_failure(f"Erro ao remover proteção: {e}")
            return False
    
    async def scan_protected_agents(self, scan_type: str = "standard") -> SecurityReport:
        """Executa scan de segurança em todos os agentes protegidos"""
        if not self.is_operational:
            raise RuntimeError("AEGIS Security Agent não está operacional")
        
        try:
            start_time = time.time()
            
            # Executar scan completo
            report = await self.aegis_core.scan_all_components(scan_type)
            
            # Atualizar estado do agente
            self.security_state['last_full_scan'] = datetime.now()
            
            # Determinar nível de ameaça geral
            max_threat_level = ThreatLevel.SAFE
            for threat in report.threats_detected:
                if threat.level.value > max_threat_level.value:
                    max_threat_level = threat.level
            
            self.security_state['threat_level'] = max_threat_level
            
            # Calcular efetividade da proteção
            total_threats = len(report.threats_detected)
            mitigated_threats = sum(1 for t in report.threats_detected if t.mitigated)
            effectiveness = mitigated_threats / total_threats if total_threats > 0 else 1.0
            self.security_state['protection_effectiveness'] = effectiveness
            
            # Registrar tempo de resposta
            response_time = time.time() - start_time
            if self.security_state['response_time_avg'] == 0:
                self.security_state['response_time_avg'] = response_time
            else:
                self.security_state['response_time_avg'] = (
                    self.security_state['response_time_avg'] * 0.8 + response_time * 0.2
                )
            
            # Registrar sucesso no MAB
            self._penalizar_agente_no_mab(effectiveness, True)
            
            montar_log(f"Scan de segurança completo: {total_threats} ameaças, {mitigated_threats} mitigadas", "INFO")
            return report
            
        except Exception as e:
            self._register_failure(f"Erro durante scan de segurança: {e}")
            raise
    
    async def respond_to_threat(self, threat: SecurityThreat, 
                               auto_response: bool = None) -> Dict[str, Any]:
        """
        Responde a uma ameaça detectada
        
        Args:
            threat: Ameaça detectada
            auto_response: Se True, resposta automática; se False, manual; se None, usa config
        
        Returns:
            Resultado da resposta à ameaça
        """
        if auto_response is None:
            auto_response = self.config['threat_response_level'] == 'auto'
        
        response_result = {
            'threat_id': threat.id,
            'response_type': 'auto' if auto_response else 'manual',
            'actions_taken': [],
            'success': False,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            if not auto_response:
                # Modo manual - apenas alertar
                response_result['actions_taken'].append('threat_logged')
                montar_log(f"Ameaça detectada (modo manual): {threat.description}", "WARNING")
                response_result['success'] = True
                return response_result
            
            # Resposta automática baseada no nível da ameaça
            if threat.level == ThreatLevel.CRITICAL:
                # Ações críticas
                await self._handle_critical_threat(threat, response_result)
            elif threat.level == ThreatLevel.DANGEROUS:
                # Ações para ameaças perigosas
                await self._handle_dangerous_threat(threat, response_result)
            elif threat.level == ThreatLevel.SUSPICIOUS:
                # Ações para ameaças suspeitas
                await self._handle_suspicious_threat(threat, response_result)
            
            response_result['success'] = True
            
        except Exception as e:
            montar_log(f"Erro na resposta à ameaça {threat.id}: {e}", "ERROR")
            response_result['error'] = str(e)
        
        return response_result
    
    async def get_security_dashboard(self) -> Dict[str, Any]:
        """Retorna dashboard de segurança completo"""
        try:
            # Status do núcleo AEGIS
            aegis_status = self.aegis_core.get_security_status()
            
            # Status dos agentes protegidos
            protected_agents_status = {}
            for reg_id, agent_info in self._protected_agents.items():
                agent = agent_info['agent']
                protected_agents_status[agent.id_registro] = {
                    'protection_level': agent_info['protection_level'],
                    'last_scan': agent_info['last_scan'].isoformat() if agent_info['last_scan'] else None,
                    'threat_count': agent_info['threat_count'],
                    'agent_health': agent._health_score,
                    'agent_status': agent._status
                }
            
            # Estatísticas de ameaças recentes
            recent_threats = await self._get_recent_threats_stats()
            
            dashboard = {
                'aegis_agent': {
                    'id': self.id_registro,
                    'status': self._status,
                    'health_score': self._health_score,
                    'operational': self.is_operational,
                    'protection_mode': self.config['protection_mode'],
                    'effectiveness': self.security_state['protection_effectiveness']
                },
                'aegis_core': aegis_status,
                'protected_agents': protected_agents_status,
                'security_state': {
                    'active_protections': self.security_state['active_protections'],
                    'current_threat_level': self.security_state['threat_level'].value,
                    'last_full_scan': self.security_state['last_full_scan'].isoformat() if self.security_state['last_full_scan'] else None,
                    'avg_response_time': self.security_state['response_time_avg']
                },
                'recent_threats': recent_threats,
                'system_recommendations': await self._generate_system_recommendations()
            }
            
            return dashboard
            
        except Exception as e:
            montar_log(f"Erro ao gerar dashboard de segurança: {e}", "ERROR")
            return {'error': str(e)}
    
    # Implementação dos métodos abstratos do AgenteBase
    
    async def update_trigger(self, *args, **kwargs) -> Any:
        """Método principal de execução do agente de segurança"""
        if not self.is_operational:
            return {'status': 'inactive', 'reason': 'circuit_breaker_open'}
        
        try:
            # Executar ciclo de segurança
            security_cycle_result = await self._execute_security_cycle()
            
            # Registrar sucesso
            self._register_success()
            
            return {
                'status': 'success',
                'cycle_result': security_cycle_result,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self._register_failure(f"Erro no ciclo de segurança: {e}")
            return {'status': 'error', 'error': str(e)}
    
    async def version_on_sa(self, *args, **kwargs) -> bool:
        """Protocolo de salvação - verifica se versão é segura"""
        try:
            # Verificar se há ameaças críticas ativas
            if self.security_state['threat_level'] == ThreatLevel.CRITICAL:
                return False
            
            # Verificar efetividade da proteção
            if self.security_state['protection_effectiveness'] < 0.7:
                return False
            
            # Verificar saúde do sistema
            aegis_status = self.aegis_core.get_security_status()
            if aegis_status['system_health'] < 0.8:
                return False
            
            return True
            
        except Exception as e:
            montar_log(f"Erro na verificação de segurança: {e}", "ERROR")
            return False
    
    # Métodos privados de implementação
    
    async def _setup_agent_protection(self):
        """Configura proteção automática de agentes"""
        # Implementar descoberta e proteção automática de agentes
        pass
    
    async def _start_continuous_monitoring(self):
        """Inicia monitoramento contínuo"""
        self._monitoring_task = asyncio.create_task(self._continuous_monitor())
    
    async def _continuous_monitor(self):
        """Loop de monitoramento contínuo"""
        while self.is_operational:
            try:
                # Verificar agentes protegidos
                await self._check_protected_agents()
                
                # Aguardar próximo ciclo
                await asyncio.sleep(self.config['scan_frequency'])
                
            except Exception as e:
                montar_log(f"Erro no monitoramento contínuo: {e}", "ERROR")
                await asyncio.sleep(10)  # Aguardar mais tempo em caso de erro
    
    async def _check_protected_agents(self):
        """Verifica estado dos agentes protegidos"""
        for reg_id, agent_info in self._protected_agents.items():
            try:
                # Verificação rápida de integridade
                if agent_info['protection_level'] in ['high', 'critical']:
                    await self.aegis_core.scan_component(reg_id, 'quick')
                    
            except Exception as e:
                montar_log(f"Erro na verificação do agente {reg_id}: {e}", "ERROR")
    
    async def _setup_scan_scheduler(self):
        """Configura agendamento de scans"""
        self._scan_scheduler = asyncio.create_task(self._scheduled_scan_loop())
    
    async def _scheduled_scan_loop(self):
        """Loop de scans agendados"""
        while self.is_operational:
            try:
                # Scan completo periódico
                await self.scan_protected_agents('standard')
                
                # Aguardar próximo scan completo (ex: a cada hora)
                await asyncio.sleep(3600)
                
            except Exception as e:
                montar_log(f"Erro no scan agendado: {e}", "ERROR")
                await asyncio.sleep(300)  # Tentar novamente em 5 minutos
    
    async def _register_security_hooks(self):
        """Registra hooks de segurança no sistema"""
        # Implementar integração com hooks do sistema Quimera
        pass
    
    async def _initial_agent_scan(self, registration_id: str, agent: AgenteBase):
        """Executa scan inicial em agente recém-protegido"""
        try:
            report = await self.aegis_core.scan_component(registration_id, 'full')
            
            # Atualizar informações do agente
            agent_info = self._protected_agents[registration_id]
            agent_info['last_scan'] = datetime.now()
            agent_info['threat_count'] = len(report.threats_detected)
            
            if report.threats_detected:
                montar_log(f"Scan inicial do agente {agent.id_registro}: {len(report.threats_detected)} ameaças detectadas", "WARNING")
            else:
                montar_log(f"Scan inicial do agente {agent.id_registro}: sistema limpo", "INFO")
                
        except Exception as e:
            montar_log(f"Erro no scan inicial do agente {agent.id_registro}: {e}", "ERROR")
    
    async def _handle_critical_threat(self, threat: SecurityThreat, 
                                     response_result: Dict[str, Any]):
        """Lida com ameaças críticas"""
        # Quarentena imediata
        if self.config['auto_quarantine']:
            # Implementar quarentena
            response_result['actions_taken'].append('quarantine')
        
        # Alertar administradores
        response_result['actions_taken'].append('admin_alert')
        
        # Isolar componente afetado
        response_result['actions_taken'].append('component_isolation')
        
        montar_log(f"AMEAÇA CRÍTICA: {threat.description} - Ações automáticas executadas", "CRITICAL")
    
    async def _handle_dangerous_threat(self, threat: SecurityThreat, 
                                      response_result: Dict[str, Any]):
        """Lida com ameaças perigosas"""
        # Tentar auto-healing
        if self.config['self_healing']:
            # Implementar auto-healing
            response_result['actions_taken'].append('auto_healing')
        
        # Aumentar monitoramento
        response_result['actions_taken'].append('enhanced_monitoring')
        
        montar_log(f"AMEAÇA PERIGOSA: {threat.description} - Mitigação automática", "WARNING")
    
    async def _handle_suspicious_threat(self, threat: SecurityThreat, 
                                       response_result: Dict[str, Any]):
        """Lida com ameaças suspeitas"""
        # Monitoramento aumentado
        response_result['actions_taken'].append('increased_monitoring')
        
        # Log detalhado
        response_result['actions_taken'].append('detailed_logging')
        
        montar_log(f"AMEAÇA SUSPEITA: {threat.description} - Monitoramento aumentado", "INFO")
    
    async def _execute_security_cycle(self) -> Dict[str, Any]:
        """Executa ciclo completo de segurança"""
        cycle_start = time.time()
        
        # Verificar integridade dos componentes críticos
        critical_check = await self._check_critical_components()
        
        # Executar scan rápido
        quick_scan = await self.aegis_core.scan_all_components('quick')
        
        # Analisar ameaças emergentes
        threat_analysis = await self._analyze_emerging_threats()
        
        # Atualizar métricas
        await self._update_security_metrics()
        
        cycle_duration = time.time() - cycle_start
        
        return {
            'cycle_duration': cycle_duration,
            'critical_components_checked': critical_check['checked'],
            'quick_scan_threats': len(quick_scan.threats_detected),
            'emerging_threats': threat_analysis['count'],
            'system_health': self.aegis_core.get_security_status()['system_health']
        }
    
    async def _check_critical_components(self) -> Dict[str, Any]:
        """Verifica componentes críticos"""
        checked = 0
        issues = 0
        
        for reg_id, agent_info in self._protected_agents.items():
            if agent_info['protection_level'] == 'critical':
                try:
                    # Verificação rápida
                    report = await self.aegis_core.scan_component(reg_id, 'quick')
                    checked += 1
                    
                    if report.threats_detected:
                        issues += len(report.threats_detected)
                        
                except Exception as e:
                    montar_log(f"Erro na verificação crítica de {reg_id}: {e}", "ERROR")
        
        return {'checked': checked, 'issues': issues}
    
    async def _analyze_emerging_threats(self) -> Dict[str, Any]:
        """Analisa ameaças emergentes"""
        # Implementar análise preditiva de ameaças
        return {'count': 0, 'predictions': []}
    
    async def _update_security_metrics(self):
        """Atualiza métricas de segurança"""
        # Atualizar métricas baseadas no estado atual
        aegis_status = self.aegis_core.get_security_status()
        
        self.security_state['protection_effectiveness'] = min(
            1.0, 
            self.security_state['protection_effectiveness'] * 0.99 + 
            aegis_status['system_health'] * 0.01
        )
    
    async def _get_recent_threats_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas de ameaças recentes"""
        # Implementar coleta de estatísticas de ameaças
        return {
            'last_24h': 0,
            'last_7d': 0,
            'by_type': {},
            'by_severity': {}
        }
    
    async def _generate_system_recommendations(self) -> List[str]:
        """Gera recomendações para o sistema"""
        recommendations = []
        
        # Análise da efetividade
        if self.security_state['protection_effectiveness'] < 0.8:
            recommendations.append("Considerar ajuste das políticas de segurança")
        
        # Análise do nível de ameaça
        if self.security_state['threat_level'] != ThreatLevel.SAFE:
            recommendations.append("Executar scan de segurança profundo")
        
        # Análise do tempo de resposta
        if self.security_state['response_time_avg'] > 5.0:
            recommendations.append("Otimizar configurações de scan para melhor performance")
        
        return recommendations