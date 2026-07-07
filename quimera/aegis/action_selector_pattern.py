"""
Action-Selector Pattern - Padrão de Seleção de Ações Seguras
===========================================================

Implementa separação entre seleção e execução de ações para reduzir 
riscos de comandos maliciosos e garantir controle granular sobre operações.
"""

import uuid
import time
import json
import hashlib
from typing import Dict, List, Optional, Any, Callable, Set, Union
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque

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


class ActionRiskLevel(Enum):
    """Níveis de risco para ações"""
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    FORBIDDEN = "forbidden"


class ActionCategory(Enum):
    """Categorias de ações"""
    FILE_OPERATION = "file_operation"
    NETWORK_OPERATION = "network_operation"
    SYSTEM_COMMAND = "system_command"
    LLM_INTERACTION = "llm_interaction"
    DATA_PROCESSING = "data_processing"
    PLUGIN_EXECUTION = "plugin_execution"
    USER_INTERACTION = "user_interaction"


class ActionStatus(Enum):
    """Status de execução de ações"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class ActionRequest:
    """Solicitação de ação"""
    action_id: str
    action_name: str
    category: ActionCategory
    description: str
    parameters: Dict[str, Any]
    risk_level: ActionRiskLevel = ActionRiskLevel.MEDIUM
    requester: str = "unknown"
    timestamp: datetime = field(default_factory=datetime.now)
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionApproval:
    """Aprovação de ação"""
    action_id: str
    approved: bool
    approver: str
    reason: str
    conditions: List[str] = field(default_factory=list)
    expiry: Optional[datetime] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ActionExecution:
    """Execução de ação"""
    action_id: str
    executor: str
    status: ActionStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    execution_log: List[str] = field(default_factory=list)


class ActionSelectorAgent:
    """
    Agente de Seleção de Ações
    
    Implementa o padrão Action-Selector que separa:
    - Análise e seleção de ações
    - Aprovação baseada em políticas
    - Execução controlada
    - Auditoria completa
    """
    
    def __init__(self, agent_name: str, strict_mode: bool = True):
        self.agent_name = agent_name
        self.strict_mode = strict_mode
        
        # Armazenamento de ações
        self.pending_actions: Dict[str, ActionRequest] = {}
        self.approved_actions: Dict[str, ActionApproval] = {}
        self.executing_actions: Dict[str, ActionExecution] = {}
        self.completed_actions: Dict[str, ActionExecution] = {}
        
        # Políticas de segurança
        self.risk_policies: Dict[ActionRiskLevel, Dict] = {}
        self.category_policies: Dict[ActionCategory, Dict] = {}
        self.forbidden_actions: Set[str] = set()
        
        # Estatísticas
        self.stats = {
            'total_requests': 0,
            'approved_requests': 0,
            'rejected_requests': 0,
            'completed_executions': 0,
            'failed_executions': 0,
            'timeout_executions': 0,
            'actions_by_category': defaultdict(int),
            'actions_by_risk': defaultdict(int)
        }
        
        # Log de auditoria
        self.audit_log: deque = deque(maxlen=10000)
        
        # Cache de decisões
        self._decision_cache: Dict[str, ActionApproval] = {}
        self._cache_ttl = timedelta(minutes=5)
        
        # Inicializar sistema
        self._initialize_default_policies()
        
        montar_log(f"🎯 Action-Selector Agent '{agent_name}' inicializado (strict: {strict_mode})", "INFO")
    
    def _initialize_default_policies(self):
        """Inicializa políticas padrão de segurança"""
        
        # Políticas por nível de risco
        self.risk_policies = {
            ActionRiskLevel.SAFE: {
                'auto_approve': True,
                'requires_review': False,
                'timeout_seconds': 30,
                'max_retries': 3
            },
            ActionRiskLevel.LOW: {
                'auto_approve': True,
                'requires_review': False,
                'timeout_seconds': 60,
                'max_retries': 2
            },
            ActionRiskLevel.MEDIUM: {
                'auto_approve': not self.strict_mode,
                'requires_review': True,
                'timeout_seconds': 120,
                'max_retries': 1
            },
            ActionRiskLevel.HIGH: {
                'auto_approve': False,
                'requires_review': True,
                'timeout_seconds': 300,
                'max_retries': 1
            },
            ActionRiskLevel.CRITICAL: {
                'auto_approve': False,
                'requires_review': True,
                'timeout_seconds': 600,
                'max_retries': 0
            },
            ActionRiskLevel.FORBIDDEN: {
                'auto_approve': False,
                'requires_review': False,
                'timeout_seconds': 0,
                'max_retries': 0
            }
        }
        
        # Políticas por categoria
        self.category_policies = {
            ActionCategory.FILE_OPERATION: {
                'allowed_extensions': ['.txt', '.json', '.csv', '.md', '.py'],
                'forbidden_paths': ['/etc', '/sys', '/proc'],
                'max_file_size': 100 * 1024 * 1024  # 100MB
            },
            ActionCategory.NETWORK_OPERATION: {
                'allowed_domains': [],
                'forbidden_domains': ['localhost', '127.0.0.1'],
                'max_request_size': 10 * 1024 * 1024  # 10MB
            },
            ActionCategory.SYSTEM_COMMAND: {
                'forbidden_commands': ['rm', 'del', 'format', 'fdisk', 'dd'],
                'requires_sandbox': True
            },
            ActionCategory.LLM_INTERACTION: {
                'max_context_size': 32000,
                'forbidden_prompts': ['ignore previous', 'jailbreak']
            }
        }
        
        # Ações explicitamente proibidas
        self.forbidden_actions.update([
            'delete_system_files',
            'modify_security_settings',
            'access_private_keys',
            'execute_arbitrary_code',
            'bypass_security_checks'
        ])
    
    def request_action(
        self,
        action_name: str,
        category: ActionCategory,
        description: str,
        parameters: Dict[str, Any],
        requester: str = "system",
        context: Optional[Dict] = None
    ) -> str:
        """
        Solicita execução de uma ação
        
        Returns:
            str: ID da ação para acompanhamento
        """
        try:
            # Gerar ID único
            action_id = self._generate_action_id(action_name, requester)
            
            # Avaliar risco da ação
            risk_level = self._evaluate_action_risk(action_name, category, parameters)
            
            # Criar solicitação
            request = ActionRequest(
                action_id=action_id,
                action_name=action_name,
                category=category,
                description=description,
                parameters=parameters,
                risk_level=risk_level,
                requester=requester,
                context=context or {}
            )
            
            self.pending_actions[action_id] = request
            self.stats['total_requests'] += 1
            self.stats['actions_by_category'][category.value] += 1
            self.stats['actions_by_risk'][risk_level.value] += 1
            
            # Log de auditoria
            self._log_audit_event(
                event_type="action_requested",
                action_id=action_id,
                details={
                    'action_name': action_name,
                    'category': category.value,
                    'risk_level': risk_level.value,
                    'requester': requester
                }
            )
            
            montar_log(
                f"🎯 Action-Selector: Ação '{action_name}' solicitada (risco: {risk_level.value})",
                "INFO"
            )
            
            return action_id
            
        except Exception as e:
            montar_log(f"❌ Erro ao solicitar ação: {e}", "ERROR")
            raise
    
    def _generate_action_id(self, action_name: str, requester: str) -> str:
        """Gera ID único para ação"""
        timestamp = str(int(time.time() * 1000))
        data = f"{action_name}:{requester}:{timestamp}"
        hash_part = hashlib.sha256(data.encode()).hexdigest()[:8]
        return f"act_{hash_part}_{timestamp[-6:]}"
    
    def _evaluate_action_risk(
        self,
        action_name: str,
        category: ActionCategory,
        parameters: Dict[str, Any]
    ) -> ActionRiskLevel:
        """Avalia nível de risco da ação"""
        
        # Verificar ações proibidas
        if action_name in self.forbidden_actions:
            return ActionRiskLevel.FORBIDDEN
        
        # Verificar palavras-chave perigosas
        dangerous_keywords = [
            'delete', 'remove', 'destroy', 'format', 'wipe',
            'privilege', 'admin', 'root', 'sudo', 'exec'
        ]
        
        if any(keyword in action_name.lower() for keyword in dangerous_keywords):
            return ActionRiskLevel.HIGH
        
        # Avaliar baseado na categoria
        if category == ActionCategory.SYSTEM_COMMAND:
            return ActionRiskLevel.HIGH
        elif category == ActionCategory.NETWORK_OPERATION:
            return ActionRiskLevel.MEDIUM
        elif category == ActionCategory.FILE_OPERATION:
            # Verificar parâmetros de arquivo
            if 'path' in parameters:
                path = str(parameters['path']).lower()
                forbidden_paths = self.category_policies[category]['forbidden_paths']
                if any(forbidden in path for forbidden in forbidden_paths):
                    return ActionRiskLevel.CRITICAL
            return ActionRiskLevel.LOW
        
        # Padrão para outras categorias
        return ActionRiskLevel.MEDIUM
    
    def approve_action(self, action_id: str, manual_override: bool = False) -> bool:
        """
        Aprova uma ação pendente
        
        Args:
            action_id: ID da ação
            manual_override: Ignorar políticas automáticas
            
        Returns:
            bool: True se aprovada
        """
        try:
            if action_id not in self.pending_actions:
                montar_log(f"⚠️ Ação {action_id} não encontrada", "WARNING")
                return False
            
            request = self.pending_actions[action_id]
            
            # Verificar cache de decisões
            cache_key = self._generate_decision_cache_key(request)
            if cache_key in self._decision_cache:
                cached_approval = self._decision_cache[cache_key]
                if datetime.now() - cached_approval.timestamp < self._cache_ttl:
                    return cached_approval.approved
            
            # Aplicar políticas
            approval_result = self._apply_approval_policies(request, manual_override)
            
            # Salvar aprovação
            approval = ActionApproval(
                action_id=action_id,
                approved=approval_result['approved'],
                approver=approval_result['approver'],
                reason=approval_result['reason'],
                conditions=approval_result.get('conditions', [])
            )
            
            if approval.approved:
                self.approved_actions[action_id] = approval
                self.stats['approved_requests'] += 1
                del self.pending_actions[action_id]
            else:
                self.stats['rejected_requests'] += 1
                del self.pending_actions[action_id]
            
            # Cache decisão
            self._decision_cache[cache_key] = approval
            
            # Log de auditoria
            self._log_audit_event(
                event_type="action_approved" if approval.approved else "action_rejected",
                action_id=action_id,
                details={
                    'approver': approval.approver,
                    'reason': approval.reason,
                    'manual_override': manual_override
                }
            )
            
            status = "APROVADA" if approval.approved else "REJEITADA"
            montar_log(
                f"🎯 Action-Selector: Ação {action_id} {status} - {approval.reason}",
                "INFO"
            )
            
            return approval.approved
            
        except Exception as e:
            montar_log(f"❌ Erro ao aprovar ação: {e}", "ERROR")
            return False
    
    def _apply_approval_policies(
        self,
        request: ActionRequest,
        manual_override: bool
    ) -> Dict[str, Any]:
        """Aplica políticas de aprovação"""
        
        risk_policy = self.risk_policies[request.risk_level]
        
        # Override manual
        if manual_override:
            return {
                'approved': True,
                'approver': f"{self.agent_name}_manual",
                'reason': "Aprovação manual com override",
                'conditions': ['manual_override_applied']
            }
        
        # Ações proibidas
        if request.risk_level == ActionRiskLevel.FORBIDDEN:
            return {
                'approved': False,
                'approver': f"{self.agent_name}_policy",
                'reason': "Ação classificada como proibida"
            }
        
        # Aprovação automática
        if risk_policy['auto_approve']:
            return {
                'approved': True,
                'approver': f"{self.agent_name}_auto",
                'reason': f"Aprovação automática - risco {request.risk_level.value}"
            }
        
        # Verificações específicas por categoria
        category_check = self._check_category_policies(request)
        if not category_check['passed']:
            return {
                'approved': False,
                'approver': f"{self.agent_name}_policy",
                'reason': f"Falha na política de categoria: {category_check['reason']}"
            }
        
        # Aprovação com condições
        if request.risk_level in [ActionRiskLevel.HIGH, ActionRiskLevel.CRITICAL]:
            return {
                'approved': True,
                'approver': f"{self.agent_name}_conditional",
                'reason': "Aprovada com condições especiais",
                'conditions': [
                    'requires_monitoring',
                    'limited_execution_time',
                    'enhanced_logging'
                ]
            }
        
        # Aprovação padrão
        return {
            'approved': True,
            'approver': f"{self.agent_name}_standard",
            'reason': "Aprovada por políticas padrão"
        }
    
    def _check_category_policies(self, request: ActionRequest) -> Dict[str, Any]:
        """Verifica políticas específicas da categoria"""
        
        category_policy = self.category_policies.get(request.category, {})
        
        if request.category == ActionCategory.FILE_OPERATION:
            # Verificar extensões permitidas
            if 'path' in request.parameters:
                path = str(request.parameters['path'])
                allowed_exts = category_policy.get('allowed_extensions', [])
                if allowed_exts and not any(path.endswith(ext) for ext in allowed_exts):
                    return {
                        'passed': False,
                        'reason': f"Extensão de arquivo não permitida: {path}"
                    }
        
        elif request.category == ActionCategory.SYSTEM_COMMAND:
            # Verificar comandos proibidos
            command = request.parameters.get('command', '')
            forbidden_cmds = category_policy.get('forbidden_commands', [])
            if any(cmd in command.lower() for cmd in forbidden_cmds):
                return {
                    'passed': False,
                    'reason': f"Comando proibido detectado: {command}"
                }
        
        elif request.category == ActionCategory.LLM_INTERACTION:
            # Verificar prompts proibidos
            prompt = request.parameters.get('prompt', '')
            forbidden_prompts = category_policy.get('forbidden_prompts', [])
            if any(forbidden in prompt.lower() for forbidden in forbidden_prompts):
                return {
                    'passed': False,
                    'reason': "Prompt proibido detectado"
                }
        
        return {'passed': True, 'reason': 'Políticas de categoria atendidas'}
    
    def _generate_decision_cache_key(self, request: ActionRequest) -> str:
        """Gera chave para cache de decisões"""
        data = f"{request.action_name}:{request.category.value}:{request.risk_level.value}"
        return hashlib.md5(data.encode()).hexdigest()
    
    def execute_approved_action(
        self,
        action_id: str,
        executor_function: Callable,
        timeout_override: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Executa uma ação aprovada
        
        Args:
            action_id: ID da ação aprovada
            executor_function: Função que executa a ação
            timeout_override: Override do timeout padrão
            
        Returns:
            Dict com resultado da execução
        """
        try:
            if action_id not in self.approved_actions:
                return {
                    'success': False,
                    'error': f"Ação {action_id} não aprovada ou não encontrada"
                }
            
            approval = self.approved_actions[action_id]
            request = None
            
            # Buscar request original nas ações pendentes (caso ainda esteja lá)
            # ou recriar baseado na aprovação
            for req_id, req in self.pending_actions.items():
                if req_id == action_id:
                    request = req
                    break
            
            if not request:
                return {
                    'success': False,
                    'error': "Request original não encontrado"
                }
            
            # Criar execução
            execution = ActionExecution(
                action_id=action_id,
                executor=f"{self.agent_name}_executor",
                status=ActionStatus.EXECUTING
            )
            
            self.executing_actions[action_id] = execution
            
            # Log início da execução
            self._log_audit_event(
                event_type="action_execution_started",
                action_id=action_id,
                details={'executor': execution.executor}
            )
            
            # Executar com timeout
            timeout = timeout_override or self.risk_policies[request.risk_level]['timeout_seconds']
            
            try:
                # Executar função
                result = executor_function(request.parameters)
                
                execution.status = ActionStatus.COMPLETED
                execution.result = result
                execution.end_time = datetime.now()
                
                self.stats['completed_executions'] += 1
                
                # Mover para concluídas
                self.completed_actions[action_id] = execution
                del self.executing_actions[action_id]
                del self.approved_actions[action_id]
                
                self._log_audit_event(
                    event_type="action_execution_completed",
                    action_id=action_id,
                    details={'result_type': type(result).__name__}
                )
                
                montar_log(
                    f"🎯 Action-Selector: Ação {action_id} executada com sucesso",
                    "INFO"
                )
                
                return {
                    'success': True,
                    'result': result,
                    'execution_time': (execution.end_time - execution.start_time).total_seconds()
                }
                
            except Exception as exec_error:
                execution.status = ActionStatus.FAILED
                execution.error = str(exec_error)
                execution.end_time = datetime.now()
                
                self.stats['failed_executions'] += 1
                
                self.completed_actions[action_id] = execution
                del self.executing_actions[action_id]
                del self.approved_actions[action_id]
                
                self._log_audit_event(
                    event_type="action_execution_failed",
                    action_id=action_id,
                    details={'error': str(exec_error)}
                )
                
                return {
                    'success': False,
                    'error': str(exec_error)
                }
                
        except Exception as e:
            montar_log(f"❌ Erro ao executar ação: {e}", "ERROR")
            return {
                'success': False,
                'error': f"Erro interno: {e}"
            }
    
    def _log_audit_event(
        self,
        event_type: str,
        action_id: str,
        details: Dict[str, Any]
    ):
        """Registra evento na auditoria"""
        
        audit_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'action_id': action_id,
            'agent': self.agent_name,
            'details': details
        }
        
        self.audit_log.append(audit_entry)
    
    def get_action_status(self, action_id: str) -> Dict[str, Any]:
        """Retorna status de uma ação"""
        
        # Verificar em todas as listas
        if action_id in self.pending_actions:
            return {
                'status': 'pending',
                'details': self.pending_actions[action_id].__dict__
            }
        elif action_id in self.approved_actions:
            return {
                'status': 'approved',
                'details': self.approved_actions[action_id].__dict__
            }
        elif action_id in self.executing_actions:
            return {
                'status': 'executing',
                'details': self.executing_actions[action_id].__dict__
            }
        elif action_id in self.completed_actions:
            execution = self.completed_actions[action_id]
            return {
                'status': execution.status.value,
                'details': execution.__dict__
            }
        else:
            return {
                'status': 'not_found',
                'details': {}
            }
    
    def get_action_statistics(self) -> Dict[str, Any]:
        """Retorna estatísticas do agente"""
        
        # Estatísticas em tempo real
        current_stats = {
            'pending_actions': len(self.pending_actions),
            'approved_actions': len(self.approved_actions),
            'executing_actions': len(self.executing_actions),
            'completed_actions': len(self.completed_actions),
            'audit_entries': len(self.audit_log),
            'cache_entries': len(self._decision_cache)
        }
        
        # Estatísticas históricas
        historical_stats = dict(self.stats)
        
        # Calcular taxas
        rates = {}
        if historical_stats['total_requests'] > 0:
            rates['approval_rate'] = historical_stats['approved_requests'] / historical_stats['total_requests']
            rates['rejection_rate'] = historical_stats['rejected_requests'] / historical_stats['total_requests']
        
        if historical_stats['completed_executions'] + historical_stats['failed_executions'] > 0:
            total_executions = historical_stats['completed_executions'] + historical_stats['failed_executions']
            rates['success_rate'] = historical_stats['completed_executions'] / total_executions
            rates['failure_rate'] = historical_stats['failed_executions'] / total_executions
        
        return {
            'agent_name': self.agent_name,
            'strict_mode': self.strict_mode,
            'current_statistics': current_stats,
            'historical_statistics': historical_stats,
            'rates': rates,
            'system_info': {
                'policies_loaded': len(self.risk_policies) + len(self.category_policies),
                'forbidden_actions': len(self.forbidden_actions)
            }
        }
    
    def get_audit_log(self, limit: int = 100) -> List[Dict]:
        """Retorna log de auditoria"""
        return list(self.audit_log)[-limit:]
    
    def clear_completed_actions(self, older_than_hours: int = 24):
        """Remove ações concluídas antigas"""
        
        cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
        
        to_remove = [
            action_id for action_id, execution in self.completed_actions.items()
            if execution.end_time and execution.end_time < cutoff_time
        ]
        
        for action_id in to_remove:
            del self.completed_actions[action_id]
        
        montar_log(
            f"🎯 Action-Selector: {len(to_remove)} ações antigas removidas",
            "INFO"
        )