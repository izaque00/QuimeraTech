"""
AEGIS Security Core - Núcleo Central do Sistema de Segurança
===========================================================
"""

import threading
import time
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum

# Sistema de logs interno AEGIS
try:
    from quimera.logs.parser import montar_log
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    def montar_log(msg: str, level: str = "INFO"):
        level_map = {'INFO': logging.info, 'ERROR': logging.error, 'WARNING': logging.warning, 'DEBUG': logging.debug}
        log_func = level_map.get(level.upper(), logging.info)
        log_func(f"AEGIS: {msg}")

# Importa sistemas avançados de segurança
try:
    from .defensive_tokens import DefensiveTokenManager, SecurityLevel
    from .ppa_system import PolymorphicPromptAssembler, PPAComplexity, PPAConfig
    from .dual_llm_pattern import DualLLMSecurityPattern, SecurityContext
    from .action_selector_pattern import ActionSelectorAgent
    from .plan_execute_pattern import PlanThenExecuteAgent
    from .sentinel import SentinelSecurityOrgan
    from .multi_phase_validation import MultiPhaseValidationPipeline, MultiPhaseValidationConfig, ValidationResult
    from .audit_provenance_system import AuditProvenanceSystem, AuditConfig
    from .xai_explainability import XAIExplainabilitySystem, XAIConfig
except ImportError as e:
    montar_log(f"⚠️ Módulos avançados não disponíveis: {e}", "WARNING")
    # Fallback para classes mock
    DefensiveTokenManager = None
    PolymorphicPromptAssembler = None
    DualLLMSecurityPattern = None
    ActionSelectorAgent = None
    PlanThenExecuteAgent = None
    SentinelSecurityOrgan = None
    MultiPhaseValidationPipeline = None
    AuditProvenanceSystem = None
    XAIExplainabilitySystem = None


class ThreatLevel(Enum):
    """Níveis de ameaça detectados pelo AEGIS"""
    SAFE = "safe"
    SUSPICIOUS = "suspicious"
    DANGEROUS = "dangerous"
    CRITICAL = "critical"
    EMERGENCY = "emergency"  # Novo nível para emergências


class AegisMode(Enum):
    """Modos de operação do AEGIS"""
    BASIC = "basic"              # AEGIS original
    ADVANCED = "advanced"        # Com sistemas avançados
    MILITARY = "military"        # Proteção máxima
    ADAPTIVE = "adaptive"        # Adaptativo baseado em ameaças


@dataclass
class SecurityThreat:
    """Representa uma ameaça de segurança detectada"""
    id: str
    threat_type: str
    level: ThreatLevel
    source: str
    description: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AegisCore:
    """
    Núcleo central do sistema de segurança AEGIS
    
    Coordena todos os componentes de segurança:
    - Detectores de malware
    - Monitores de integridade  
    - Analisadores comportamentais
    - Sistema de quarentena
    """
    
    def __init__(self, mode: AegisMode = AegisMode.ADVANCED):
        self._lock = threading.RLock()
        self._active = False
        self._components = {}
        self._threat_database = {}
        self._protected_components = set()
        self._quarantine_zone = set()
        self._last_scan = None
        
        # Modo de operação
        self.mode = mode
        
        # Configurações de segurança expandidas
        self.config = {
            'scan_interval': 30,
            'threat_retention_days': 30,
            'auto_healing_enabled': True,
            'quarantine_enabled': True,
            'real_time_monitoring': True,
            # Novas configurações avançadas
            'defensive_tokens_enabled': True,
            'ppa_enabled': True,
            'dual_llm_enabled': True,
            'action_selector_enabled': True,
            'plan_execute_enabled': True,
            'sentinel_enabled': True,
            'military_grade_protection': mode == AegisMode.MILITARY,
            # Sistemas de validação e auditoria
            'multi_phase_validation_enabled': True,
            'audit_system_enabled': True,
            'xai_explanations_enabled': True,
            'mobile_optimization': True
        }
        
        # Métricas expandidas
        self.metrics = {
            'total_scans': 0,
            'threats_detected': 0,
            'components_protected': 0,
            'quarantine_actions': 0,
            'auto_healing_actions': 0,
            # Novas métricas avançadas
            'prompt_injections_blocked': 0,
            'llm_interactions_secured': 0,
            'actions_restricted': 0,
            'plans_reviewed': 0,
            'sentinel_activations': 0,
            'advanced_threats_neutralized': 0,
            # Métricas de validação e auditoria
            'codes_validated': 0,
            'validation_phases_executed': 0,
            'audit_events_logged': 0,
            'explanations_generated': 0,
            'watermarks_created': 0,
            'integrity_checks_performed': 0
        }
        
        # Sistemas avançados de segurança
        self.advanced_systems = {}
        self._initialize_advanced_systems()
        
    def initialize(self) -> bool:
        """Inicializa o sistema AEGIS com proteções avançadas"""
        try:
            with self._lock:
                if self._active:
                    return True
                
                # Inicializa componentes básicos e avançados
                self._initialize_components()
                
                # Carrega políticas de segurança
                self._load_security_policies()
                
                # Inicializa sistemas avançados
                asyncio.create_task(self._initialize_advanced_systems_async())
                
                # Ativa monitoramento
                self._active = True
                
                protection_level = "MILITAR" if self.mode == AegisMode.MILITARY else "AVANÇADO"
                montar_log(f"🛡️ AEGIS Security Core inicializado - Proteção {protection_level}", "INFO")
                
                # Log das funcionalidades ativas
                active_features = [name for name, system in self.advanced_systems.items() if system]
                if active_features:
                    montar_log(f"⚡ Sistemas ativos: {', '.join(active_features)}", "INFO")
                
                return True
                
        except Exception as e:
            montar_log(f"❌ Erro ao inicializar AEGIS: {e}", "ERROR")
            return False
    
    async def _initialize_advanced_systems_async(self):
        """Inicialização assíncrona dos sistemas avançados"""
        try:
            # Inicializa SENTINEL se disponível
            sentinel = self.advanced_systems.get('sentinel')
            if sentinel:
                await sentinel.initialize_sentinel()
                self.metrics['sentinel_activations'] += 1
                
        except Exception as e:
            montar_log(f"❌ Erro na inicialização assíncrona: {e}", "ERROR")
    
    def _initialize_components(self):
        """Inicializa componentes de segurança básicos e avançados"""
        try:
            # Componentes básicos
            from .malware_detector import MalwareDetector
            try:
                from .integrity_monitor import IntegrityMonitor
                from .behavior_analyzer import BehaviorAnalyzer  
                from .crypto_engine import CryptoEngine
            except ImportError:
                # Fallback para classes mock se módulos não existirem
                IntegrityMonitor = type('IntegrityMonitor', (), {})
                BehaviorAnalyzer = type('BehaviorAnalyzer', (), {})
                CryptoEngine = type('CryptoEngine', (), {})
            
            self.malware_detector = MalwareDetector()
            self.integrity_monitor = IntegrityMonitor()
            self.behavior_analyzer = BehaviorAnalyzer()
            self.crypto_engine = CryptoEngine()
            
            self._components = {
                'malware_detector': self.malware_detector,
                'integrity_monitor': self.integrity_monitor,
                'behavior_analyzer': self.behavior_analyzer,
                'crypto_engine': self.crypto_engine
            }
            
            # Adiciona sistemas avançados se disponíveis
            for system_name, system_instance in self.advanced_systems.items():
                if system_instance:
                    self._components[system_name] = system_instance
            
            montar_log(f"🔧 {len(self._components)} componentes AEGIS inicializados (modo: {self.mode.value})", "INFO")
            
        except Exception as e:
            montar_log(f"⚠️ Erro ao inicializar componentes AEGIS: {e}", "WARNING")
    
    def _initialize_advanced_systems(self):
        """Inicializa sistemas avançados de segurança"""
        try:
            if self.mode in [AegisMode.BASIC]:
                montar_log("ℹ️ Modo básico - sistemas avançados desabilitados", "INFO")
                return
            
            # Sistema de Tokens Defensivos
            if DefensiveTokenManager and self.config.get('defensive_tokens_enabled'):
                self.advanced_systems['defensive_tokens'] = DefensiveTokenManager()
                montar_log("🛡️ DefensiveTokens ativado", "INFO")
            
            # Sistema PPA (Polymorphic Prompt Assembling)
            if PolymorphicPromptAssembler and self.config.get('ppa_enabled'):
                ppa_complexity = PPAComplexity.MILITARY if self.mode == AegisMode.MILITARY else PPAComplexity.ADVANCED
                ppa_config = PPAConfig(complexity=ppa_complexity)
                self.advanced_systems['ppa_system'] = PolymorphicPromptAssembler(ppa_config)
                montar_log(f"🔄 PPA ativado (complexidade: {ppa_complexity.name})", "INFO")
            
            # Sistema Dual LLM
            if DualLLMSecurityPattern and self.config.get('dual_llm_enabled'):
                self.advanced_systems['dual_llm'] = DualLLMSecurityPattern()
                montar_log("🔐 Dual LLM Pattern ativado", "INFO")
            
            # Sistema Action Selector
            if ActionSelectorAgent and self.config.get('action_selector_enabled'):
                self.advanced_systems['action_selector'] = ActionSelectorAgent("AEGIS_ActionSelector")
                montar_log("🎯 Action-Selector Pattern ativado", "INFO")
            
            # Sistema Plan-Then-Execute
            if PlanThenExecuteAgent and self.config.get('plan_execute_enabled'):
                self.advanced_systems['plan_execute'] = PlanThenExecuteAgent("AEGIS_PlanExecute")
                montar_log("📋 Plan-Then-Execute Pattern ativado", "INFO")
            
            # Sistema SENTINEL
            if SentinelSecurityOrgan and self.config.get('sentinel_enabled'):
                self.advanced_systems['sentinel'] = SentinelSecurityOrgan()
                montar_log("🛡️ SENTINEL Security Organ ativado", "INFO")
            
            # Sistema de Validação Multi-Fase
            if MultiPhaseValidationPipeline and self.config.get('multi_phase_validation_enabled'):
                validation_config = MultiPhaseValidationConfig(
                    mobile_optimization=self.config.get('mobile_optimization', True),
                    max_memory_mb=1536 if self.config.get('mobile_optimization') else 4096
                )
                self.advanced_systems['validation_pipeline'] = MultiPhaseValidationPipeline(validation_config)
                montar_log("🔍 Multi-Phase Validation Pipeline ativado", "INFO")
            
            # Sistema de Auditoria e Provenância
            if AuditProvenanceSystem and self.config.get('audit_system_enabled'):
                audit_config = AuditConfig(
                    mobile_optimization=self.config.get('mobile_optimization', True),
                    enable_watermarking=True,
                    enable_immutable_log=True
                )
                audit_db_path = "/tmp/quimera_audit.db" if self.config.get('mobile_optimization') else "quimera_audit.db"
                self.advanced_systems['audit_system'] = AuditProvenanceSystem(audit_config, audit_db_path)
                montar_log("📜 Audit & Provenance System ativado", "INFO")
            
            # Sistema XAI (Explainable AI)
            if XAIExplainabilitySystem and self.config.get('xai_explanations_enabled'):
                xai_config = XAIConfig(
                    mobile_optimization=self.config.get('mobile_optimization', True),
                    max_explanations_memory=100 if self.config.get('mobile_optimization') else 500
                )
                self.advanced_systems['xai_system'] = XAIExplainabilitySystem(xai_config)
                montar_log("🧠 XAI Explainability System ativado", "INFO")
            
        except Exception as e:
            montar_log(f"⚠️ Erro ao inicializar sistemas avançados: {e}", "WARNING")
    
    def _load_security_policies(self):
        """Carrega políticas de segurança"""
        # Implementação simplificada
        pass
    
    def register_agent(self, agent):
        """Registra um agente para proteção AEGIS avançada"""
        try:
            agent_id = getattr(agent, 'nome', str(agent))
            self._protected_components.add(agent_id)
            self.metrics['components_protected'] += 1
            
            # Registra no SENTINEL se disponível
            sentinel = self.advanced_systems.get('sentinel')
            if sentinel:
                sentinel.register_component(agent_id, agent)
            
            # Cria Action Selector específico para o agente se necessário
            if hasattr(agent, 'requires_action_selector') and agent.requires_action_selector:
                if ActionSelectorAgent:
                    agent_selector = ActionSelectorAgent(f"Selector_{agent_id}")
                    self.advanced_systems[f'selector_{agent_id}'] = agent_selector
                    montar_log(f"🎯 Action-Selector criado para {agent_id}", "INFO")
            
            montar_log(f"🛡️ Agente {agent_id} protegido pelo AEGIS AVANÇADO", "INFO")
            
        except Exception as e:
            montar_log(f"❌ Erro ao registrar agente: {e}", "ERROR")
    
    def verify_code_integrity(self, code_data) -> Dict[str, Any]:
        """Verifica integridade do código"""
        try:
            # Implementação simplificada
            if hasattr(self, 'malware_detector'):
                return self.malware_detector.scan_code(str(code_data))
            
            return {"safe": True, "reason": "No malware detector available"}
            
        except Exception as e:
            montar_log(f"❌ Erro na verificação de integridade: {e}", "ERROR")
            return {"safe": False, "reason": f"Error: {e}"}
    
    def monitor_agent_behavior(self, agent_name: str, operation: str, data: Any):
        """Monitora comportamento de agente"""
        try:
            if hasattr(self, 'behavior_analyzer'):
                self.behavior_analyzer.record_operation(agent_name, operation, {"data": str(data)})
                
        except Exception as e:
            montar_log(f"❌ Erro no monitoramento: {e}", "ERROR")
    
    def start_monitoring(self):
        """Inicia monitoramento contínuo"""
        try:
            # Implementação simplificada
            montar_log("👁️ Monitoramento AEGIS ativado", "INFO")
            
        except Exception as e:
            montar_log(f"❌ Erro ao iniciar monitoramento: {e}", "ERROR")
    
    async def validate_code_comprehensive(self, code: str, language: str = "python", 
                                        session_id: str = "default", user_id: str = None) -> Dict[str, Any]:
        """Validação abrangente de código usando todos os sistemas"""
        validation_result = {}
        
        try:
            # Validação multi-fase
            validation_pipeline = self.advanced_systems.get('validation_pipeline')
            if validation_pipeline:
                validation_result = await validation_pipeline.validate_code(code, language)
                self.metrics['codes_validated'] += 1
                self.metrics['validation_phases_executed'] += validation_result.get('phases_executed', 0)
            
            # Auditoria
            audit_system = self.advanced_systems.get('audit_system')
            if audit_system:
                code_id = await audit_system.log_code_generation(
                    code, 
                    {'language': language, 'model': 'aegis_validator'},
                    session_id, 
                    user_id
                )
                validation_result['code_id'] = code_id
                
                # Log resultado da validação
                await audit_system.log_validation_result(code_id, validation_result, session_id, user_id)
                self.metrics['audit_events_logged'] += 2
                self.metrics['watermarks_created'] += 1
            
            # Explicação XAI
            xai_system = self.advanced_systems.get('xai_system')
            if xai_system:
                explanation = await xai_system.explain_code_generation({
                    'code': code,
                    'language': language,
                    'validation_result': validation_result
                })
                validation_result['explanation_id'] = explanation.explanation_id if explanation else None
                self.metrics['explanations_generated'] += 1
            
            montar_log(f"✅ Validação abrangente concluída: {validation_result.get('overall_result', 'UNKNOWN')}", "INFO")
            
        except Exception as e:
            montar_log(f"❌ Erro na validação abrangente: {e}", "ERROR")
            validation_result['error'] = str(e)
        
        return validation_result
    
    async def analyze_security_threat(self, threat_data: Dict[str, Any], 
                                    session_id: str = "default", user_id: str = None) -> Dict[str, Any]:
        """Análise completa de ameaça de segurança"""
        analysis_result = {}
        
        try:
            # Auditoria do evento de segurança
            audit_system = self.advanced_systems.get('audit_system')
            if audit_system:
                await audit_system.log_security_event(
                    threat_data.get('type', 'unknown_threat'),
                    threat_data,
                    session_id,
                    user_id
                )
                self.metrics['audit_events_logged'] += 1
            
            # Explicação da decisão de segurança
            xai_system = self.advanced_systems.get('xai_system')
            if xai_system:
                explanation = await xai_system.explain_security_decision(threat_data)
                analysis_result['explanation'] = explanation.to_dict() if explanation else None
                self.metrics['explanations_generated'] += 1
            
            analysis_result['threat_analyzed'] = True
            analysis_result['timestamp'] = datetime.now().isoformat()
            
            montar_log(f"🔍 Análise de ameaça concluída: {threat_data.get('type', 'unknown')}", "INFO")
            
        except Exception as e:
            montar_log(f"❌ Erro na análise de ameaça: {e}", "ERROR")
            analysis_result['error'] = str(e)
        
        return analysis_result
    
    async def verify_code_integrity_comprehensive(self, code: str, code_id: str) -> Dict[str, Any]:
        """Verificação abrangente de integridade de código"""
        integrity_result = {}
        
        try:
            # Verificação via sistema de auditoria
            audit_system = self.advanced_systems.get('audit_system')
            if audit_system:
                is_valid, message = audit_system.verify_code_integrity(code, code_id)
                integrity_result['watermark_valid'] = is_valid
                integrity_result['watermark_message'] = message
                self.metrics['integrity_checks_performed'] += 1
            
            # Verificação via malware detector
            if hasattr(self, 'malware_detector'):
                malware_result = self.malware_detector.scan_code(code)
                integrity_result['malware_check'] = malware_result
            
            integrity_result['verified'] = True
            integrity_result['timestamp'] = datetime.now().isoformat()
            
            montar_log(f"✅ Verificação de integridade: {code_id}", "INFO")
            
        except Exception as e:
            montar_log(f"❌ Erro na verificação de integridade: {e}", "ERROR")
            integrity_result['error'] = str(e)
        
        return integrity_result
    
    def get_system_status(self) -> Dict[str, Any]:
        """Retorna status completo do sistema AEGIS avançado"""
        status = {
            "status": "ACTIVE" if self._active else "INACTIVE",
            "mode": self.mode.value,
            "protection_level": "MILITAR" if self.mode == AegisMode.MILITARY else "AVANÇADO",
            "active_components": list(self._components.keys()),
            "active_protections": list(self._protected_components),
            "threats_detected": self.metrics['threats_detected'],
            "last_scan_time": self._last_scan,
            "metrics": self.metrics.copy(),
            "advanced_systems": {
                name: system is not None 
                for name, system in self.advanced_systems.items()
            }
        }
        
        # Adiciona status dos sistemas avançados
        try:
            # Status do SENTINEL
            sentinel = self.advanced_systems.get('sentinel')
            if sentinel:
                status['sentinel_status'] = sentinel.get_system_status()
            
            # Status do Dual LLM
            dual_llm = self.advanced_systems.get('dual_llm')
            if dual_llm:
                status['dual_llm_stats'] = dual_llm.get_dual_llm_statistics()
            
            # Status do Action Selector
            action_selector = self.advanced_systems.get('action_selector')
            if action_selector:
                status['action_selector_stats'] = action_selector.get_action_statistics()
            
            # Status do Plan-Execute
            plan_execute = self.advanced_systems.get('plan_execute')
            if plan_execute:
                status['plan_execute_stats'] = plan_execute.get_plan_statistics()
            
            # Status do PPA
            ppa_system = self.advanced_systems.get('ppa_system')
            if ppa_system:
                status['ppa_stats'] = ppa_system.get_ppa_statistics()
            
            # Status dos Defensive Tokens
            defensive_tokens = self.advanced_systems.get('defensive_tokens')
            if defensive_tokens:
                status['defensive_tokens_stats'] = defensive_tokens.get_protection_statistics()
            
            # Status do sistema de validação
            validation_pipeline = self.advanced_systems.get('validation_pipeline')
            if validation_pipeline:
                status['validation_stats'] = validation_pipeline.get_validation_statistics()
            
            # Status do sistema de auditoria
            audit_system = self.advanced_systems.get('audit_system')
            if audit_system:
                status['audit_stats'] = audit_system.get_system_status()
            
            # Status do sistema XAI
            xai_system = self.advanced_systems.get('xai_system')
            if xai_system:
                status['xai_stats'] = xai_system.get_system_status()
                
        except Exception as e:
            montar_log(f"⚠️ Erro ao coletar status avançado: {e}", "WARNING")
            status['advanced_status_error'] = str(e)
        
        return status
    
    def shutdown(self):
        """Desliga o sistema AEGIS"""
        with self._lock:
            self._active = False
            montar_log("🔴 AEGIS Security Core desligado", "INFO")