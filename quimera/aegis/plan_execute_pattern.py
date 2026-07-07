"""
Plan-Then-Execute Pattern - Padrão de Planejamento e Execução Controlada
=======================================================================

Implementa separação entre planejamento e execução para reduzir riscos
de sequências de ações maliciosas e garantir análise prévia de planos.
"""

import uuid
import time
import json
import hashlib
from typing import Dict, List, Optional, Any, Callable, Set, Union, Tuple
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


class PlanStatus(Enum):
    """Status do plano"""
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(Enum):
    """Status do passo individual"""
    PENDING = "pending"
    READY = "ready"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class PlanRiskLevel(Enum):
    """Níveis de risco do plano"""
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    FORBIDDEN = "forbidden"


class StepType(Enum):
    """Tipos de passos"""
    ANALYSIS = "analysis"
    VALIDATION = "validation"
    TRANSFORMATION = "transformation"
    COMMUNICATION = "communication"
    STORAGE = "storage"
    COMPUTATION = "computation"
    DECISION = "decision"


@dataclass
class PlanStep:
    """Passo individual do plano"""
    step_id: str
    step_name: str
    step_type: StepType
    description: str
    action_name: str
    parameters: Dict[str, Any]
    dependencies: List[str] = field(default_factory=list)
    conditions: List[str] = field(default_factory=list)
    timeout_seconds: int = 300
    retry_count: int = 0
    max_retries: int = 2
    status: StepStatus = StepStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionPlan:
    """Plano de execução completo"""
    plan_id: str
    plan_name: str
    description: str
    creator: str
    steps: List[PlanStep]
    status: PlanStatus = PlanStatus.DRAFT
    risk_level: PlanRiskLevel = PlanRiskLevel.MEDIUM
    created_at: datetime = field(default_factory=datetime.now)
    approved_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    approver: Optional[str] = None
    approval_reason: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanExecution:
    """Execução do plano"""
    plan_id: str
    execution_id: str
    current_step: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    skipped_steps: int = 0
    execution_log: List[str] = field(default_factory=list)
    step_results: Dict[str, Any] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class PlanThenExecuteAgent:
    """
    Agente de Planejamento e Execução
    
    Implementa o padrão Plan-Then-Execute que:
    - Cria planos detalhados antes da execução
    - Analisa riscos de sequências de ações
    - Permite revisão e aprovação de planos
    - Executa planos com controle granular
    - Mantém auditoria completa
    """
    
    def __init__(self, agent_name: str, strict_planning: bool = True):
        self.agent_name = agent_name
        self.strict_planning = strict_planning
        
        # Armazenamento de planos
        self.draft_plans: Dict[str, ExecutionPlan] = {}
        self.approved_plans: Dict[str, ExecutionPlan] = {}
        self.executing_plans: Dict[str, PlanExecution] = {}
        self.completed_plans: Dict[str, ExecutionPlan] = {}
        
        # Políticas de planejamento
        self.risk_policies: Dict[PlanRiskLevel, Dict] = {}
        self.step_policies: Dict[StepType, Dict] = {}
        self.forbidden_patterns: Set[str] = set()
        
        # Executores de ações
        self.action_executors: Dict[str, Callable] = {}
        
        # Estatísticas
        self.stats = {
            'total_plans': 0,
            'approved_plans': 0,
            'rejected_plans': 0,
            'completed_plans': 0,
            'failed_plans': 0,
            'total_steps_executed': 0,
            'steps_by_type': defaultdict(int),
            'plans_by_risk': defaultdict(int)
        }
        
        # Log de auditoria
        self.audit_log: deque = deque(maxlen=10000)
        
        # Templates de planos comuns
        self.plan_templates: Dict[str, Dict] = {}
        
        # Inicializar sistema
        self._initialize_policies()
        self._initialize_templates()
        
        montar_log(f"📋 Plan-Then-Execute Agent '{agent_name}' inicializado (strict: {strict_planning})", "INFO")
    
    def _initialize_policies(self):
        """Inicializa políticas de planejamento"""
        
        # Políticas por nível de risco
        self.risk_policies = {
            PlanRiskLevel.SAFE: {
                'auto_approve': True,
                'requires_review': False,
                'max_steps': 50,
                'max_execution_time': 1800  # 30 minutos
            },
            PlanRiskLevel.LOW: {
                'auto_approve': True,
                'requires_review': False,
                'max_steps': 20,
                'max_execution_time': 3600  # 1 hora
            },
            PlanRiskLevel.MEDIUM: {
                'auto_approve': not self.strict_planning,
                'requires_review': True,
                'max_steps': 10,
                'max_execution_time': 7200  # 2 horas
            },
            PlanRiskLevel.HIGH: {
                'auto_approve': False,
                'requires_review': True,
                'max_steps': 5,
                'max_execution_time': 3600  # 1 hora
            },
            PlanRiskLevel.CRITICAL: {
                'auto_approve': False,
                'requires_review': True,
                'max_steps': 3,
                'max_execution_time': 1800  # 30 minutos
            },
            PlanRiskLevel.FORBIDDEN: {
                'auto_approve': False,
                'requires_review': False,
                'max_steps': 0,
                'max_execution_time': 0
            }
        }
        
        # Políticas por tipo de passo
        self.step_policies = {
            StepType.ANALYSIS: {
                'default_timeout': 300,
                'max_retries': 2,
                'requires_validation': False
            },
            StepType.VALIDATION: {
                'default_timeout': 180,
                'max_retries': 1,
                'requires_validation': False
            },
            StepType.TRANSFORMATION: {
                'default_timeout': 600,
                'max_retries': 1,
                'requires_validation': True
            },
            StepType.COMMUNICATION: {
                'default_timeout': 120,
                'max_retries': 3,
                'requires_validation': False
            },
            StepType.STORAGE: {
                'default_timeout': 300,
                'max_retries': 2,
                'requires_validation': True
            },
            StepType.COMPUTATION: {
                'default_timeout': 900,
                'max_retries': 1,
                'requires_validation': True
            },
            StepType.DECISION: {
                'default_timeout': 60,
                'max_retries': 0,
                'requires_validation': True
            }
        }
        
        # Padrões proibidos de sequências
        self.forbidden_patterns.update([
            'delete_then_create_similar',
            'bypass_then_access',
            'escalate_then_execute',
            'hide_then_modify'
        ])
    
    def _initialize_templates(self):
        """Inicializa templates de planos comuns"""
        
        self.plan_templates = {
            'code_analysis': {
                'name': 'Análise de Código',
                'steps': [
                    {
                        'name': 'carregar_codigo',
                        'type': StepType.STORAGE,
                        'action': 'load_file',
                        'description': 'Carrega arquivo de código'
                    },
                    {
                        'name': 'analisar_sintaxe',
                        'type': StepType.ANALYSIS,
                        'action': 'syntax_analysis',
                        'description': 'Analisa sintaxe do código',
                        'dependencies': ['carregar_codigo']
                    },
                    {
                        'name': 'detectar_problemas',
                        'type': StepType.ANALYSIS,
                        'action': 'detect_issues',
                        'description': 'Detecta problemas no código',
                        'dependencies': ['analisar_sintaxe']
                    },
                    {
                        'name': 'gerar_relatorio',
                        'type': StepType.COMMUNICATION,
                        'action': 'generate_report',
                        'description': 'Gera relatório de análise',
                        'dependencies': ['detectar_problemas']
                    }
                ]
            },
            'data_processing': {
                'name': 'Processamento de Dados',
                'steps': [
                    {
                        'name': 'validar_entrada',
                        'type': StepType.VALIDATION,
                        'action': 'validate_input',
                        'description': 'Valida dados de entrada'
                    },
                    {
                        'name': 'transformar_dados',
                        'type': StepType.TRANSFORMATION,
                        'action': 'transform_data',
                        'description': 'Transforma dados conforme regras',
                        'dependencies': ['validar_entrada']
                    },
                    {
                        'name': 'salvar_resultado',
                        'type': StepType.STORAGE,
                        'action': 'save_result',
                        'description': 'Salva resultado processado',
                        'dependencies': ['transformar_dados']
                    }
                ]
            }
        }
    
    def create_plan(
        self,
        plan_name: str,
        description: str,
        steps: List[Dict[str, Any]],
        creator: str = "system",
        template_name: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> str:
        """
        Cria um novo plano de execução
        
        Args:
            plan_name: Nome do plano
            description: Descrição do plano
            steps: Lista de passos do plano
            creator: Criador do plano
            template_name: Nome do template a usar (opcional)
            context: Contexto adicional
            
        Returns:
            str: ID do plano criado
        """
        try:
            # Gerar ID único
            plan_id = self._generate_plan_id(plan_name, creator)
            
            # Usar template se especificado
            if template_name and template_name in self.plan_templates:
                template = self.plan_templates[template_name]
                steps = template['steps']
                if not plan_name.startswith(template['name']):
                    plan_name = f"{template['name']} - {plan_name}"
            
            # Converter steps para objetos PlanStep
            plan_steps = []
            for i, step_data in enumerate(steps):
                step = self._create_plan_step(i, step_data)
                plan_steps.append(step)
            
            # Avaliar risco do plano
            risk_level = self._evaluate_plan_risk(plan_steps)
            
            # Criar plano
            plan = ExecutionPlan(
                plan_id=plan_id,
                plan_name=plan_name,
                description=description,
                creator=creator,
                steps=plan_steps,
                risk_level=risk_level,
                context=context or {}
            )
            
            self.draft_plans[plan_id] = plan
            self.stats['total_plans'] += 1
            self.stats['plans_by_risk'][risk_level.value] += 1
            
            # Log de auditoria
            self._log_audit_event(
                event_type="plan_created",
                plan_id=plan_id,
                details={
                    'plan_name': plan_name,
                    'step_count': len(plan_steps),
                    'risk_level': risk_level.value,
                    'creator': creator
                }
            )
            
            montar_log(
                f"📋 Plan-Execute: Plano '{plan_name}' criado com {len(plan_steps)} passos (risco: {risk_level.value})",
                "INFO"
            )
            
            return plan_id
            
        except Exception as e:
            montar_log(f"❌ Erro ao criar plano: {e}", "ERROR")
            raise
    
    def _generate_plan_id(self, plan_name: str, creator: str) -> str:
        """Gera ID único para plano"""
        timestamp = str(int(time.time() * 1000))
        data = f"{plan_name}:{creator}:{timestamp}"
        hash_part = hashlib.sha256(data.encode()).hexdigest()[:8]
        return f"plan_{hash_part}_{timestamp[-6:]}"
    
    def _create_plan_step(self, index: int, step_data: Dict[str, Any]) -> PlanStep:
        """Cria um passo do plano"""
        
        step_id = f"step_{index:03d}_{step_data['name']}"
        step_type = StepType(step_data.get('type', StepType.COMPUTATION))
        
        # Aplicar políticas do tipo de passo
        policies = self.step_policies.get(step_type, {})
        
        return PlanStep(
            step_id=step_id,
            step_name=step_data['name'],
            step_type=step_type,
            description=step_data.get('description', ''),
            action_name=step_data.get('action', ''),
            parameters=step_data.get('parameters', {}),
            dependencies=step_data.get('dependencies', []),
            conditions=step_data.get('conditions', []),
            timeout_seconds=step_data.get('timeout', policies.get('default_timeout', 300)),
            max_retries=policies.get('max_retries', 1),
            metadata=step_data.get('metadata', {})
        )
    
    def _evaluate_plan_risk(self, steps: List[PlanStep]) -> PlanRiskLevel:
        """Avalia risco do plano"""
        
        # Análise básica por número de passos
        if len(steps) > 20:
            base_risk = PlanRiskLevel.HIGH
        elif len(steps) > 10:
            base_risk = PlanRiskLevel.MEDIUM
        else:
            base_risk = PlanRiskLevel.LOW
        
        # Verificar tipos de passos perigosos
        dangerous_types = [StepType.STORAGE, StepType.DECISION]
        dangerous_count = sum(1 for step in steps if step.step_type in dangerous_types)
        
        if dangerous_count > 3:
            base_risk = PlanRiskLevel.HIGH
        elif dangerous_count > 1:
            base_risk = max(base_risk, PlanRiskLevel.MEDIUM)
        
        # Verificar padrões proibidos
        if self._detect_forbidden_patterns(steps):
            return PlanRiskLevel.FORBIDDEN
        
        # Verificar ações perigosas
        dangerous_actions = ['delete', 'remove', 'modify_security', 'execute_system']
        for step in steps:
            if any(danger in step.action_name.lower() for danger in dangerous_actions):
                return PlanRiskLevel.CRITICAL
        
        return base_risk
    
    def _detect_forbidden_patterns(self, steps: List[PlanStep]) -> bool:
        """Detecta padrões proibidos na sequência de passos"""
        
        # Converter para sequência de ações
        actions = [step.action_name.lower() for step in steps]
        action_sequence = ' -> '.join(actions)
        
        # Verificar padrões específicos
        dangerous_sequences = [
            ['delete', 'create'],
            ['bypass', 'access'],
            ['escalate', 'execute'],
            ['modify_security', 'access']
        ]
        
        for dangerous_seq in dangerous_sequences:
            if all(action in action_sequence for action in dangerous_seq):
                # Verificar se estão em sequência próxima
                indices = [actions.index(action) for action in dangerous_seq if action in actions]
                if indices and max(indices) - min(indices) <= 3:
                    return True
        
        return False
    
    def approve_plan(self, plan_id: str, approver: str, reason: str = "") -> bool:
        """
        Aprova um plano para execução
        
        Args:
            plan_id: ID do plano
            approver: Quem está aprovando
            reason: Razão da aprovação
            
        Returns:
            bool: True se aprovado
        """
        try:
            if plan_id not in self.draft_plans:
                montar_log(f"⚠️ Plano {plan_id} não encontrado nos rascunhos", "WARNING")
                return False
            
            plan = self.draft_plans[plan_id]
            
            # Verificar políticas
            risk_policy = self.risk_policies[plan.risk_level]
            
            if plan.risk_level == PlanRiskLevel.FORBIDDEN:
                montar_log(f"❌ Plano {plan_id} rejeitado - nível FORBIDDEN", "ERROR")
                plan.status = PlanStatus.REJECTED
                return False
            
            # Validações adicionais
            validation_result = self._validate_plan_for_approval(plan)
            if not validation_result['valid']:
                montar_log(f"❌ Plano {plan_id} rejeitado - {validation_result['reason']}", "ERROR")
                plan.status = PlanStatus.REJECTED
                return False
            
            # Aprovar plano
            plan.status = PlanStatus.APPROVED
            plan.approved_at = datetime.now()
            plan.approver = approver
            plan.approval_reason = reason or "Aprovado conforme políticas"
            
            # Mover para lista de aprovados
            self.approved_plans[plan_id] = plan
            del self.draft_plans[plan_id]
            
            self.stats['approved_plans'] += 1
            
            # Log de auditoria
            self._log_audit_event(
                event_type="plan_approved",
                plan_id=plan_id,
                details={
                    'approver': approver,
                    'reason': plan.approval_reason,
                    'risk_level': plan.risk_level.value
                }
            )
            
            montar_log(
                f"📋 Plan-Execute: Plano '{plan.plan_name}' aprovado por {approver}",
                "INFO"
            )
            
            return True
            
        except Exception as e:
            montar_log(f"❌ Erro ao aprovar plano: {e}", "ERROR")
            return False
    
    def _validate_plan_for_approval(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """Valida plano para aprovação"""
        
        # Verificar número máximo de passos
        risk_policy = self.risk_policies[plan.risk_level]
        max_steps = risk_policy['max_steps']
        
        if len(plan.steps) > max_steps:
            return {
                'valid': False,
                'reason': f"Plano excede máximo de {max_steps} passos para risco {plan.risk_level.value}"
            }
        
        # Verificar dependências
        step_names = {step.step_name for step in plan.steps}
        for step in plan.steps:
            for dep in step.dependencies:
                if dep not in step_names:
                    return {
                        'valid': False,
                        'reason': f"Dependência '{dep}' não encontrada no passo '{step.step_name}'"
                    }
        
        # Verificar círculos de dependência
        if self._has_circular_dependencies(plan.steps):
            return {
                'valid': False,
                'reason': "Dependências circulares detectadas"
            }
        
        return {'valid': True, 'reason': 'Validação aprovada'}
    
    def _has_circular_dependencies(self, steps: List[PlanStep]) -> bool:
        """Verifica se há dependências circulares"""
        
        # Implementação simplificada - busca por ciclos básicos
        step_deps = {step.step_name: set(step.dependencies) for step in steps}
        
        def has_cycle(node, visited, rec_stack):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in step_deps.get(node, set()):
                if neighbor not in visited:
                    if has_cycle(neighbor, visited, rec_stack):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        visited = set()
        for step_name in step_deps:
            if step_name not in visited:
                if has_cycle(step_name, visited, set()):
                    return True
        
        return False
    
    def execute_plan(
        self,
        plan_id: str,
        executor_context: Optional[Dict] = None
    ) -> str:
        """
        Executa um plano aprovado
        
        Args:
            plan_id: ID do plano aprovado
            executor_context: Contexto adicional para execução
            
        Returns:
            str: ID da execução
        """
        try:
            if plan_id not in self.approved_plans:
                raise ValueError(f"Plano {plan_id} não aprovado ou não encontrado")
            
            plan = self.approved_plans[plan_id]
            
            # Criar execução
            execution_id = f"exec_{plan_id}_{int(time.time())}"
            execution = PlanExecution(
                plan_id=plan_id,
                execution_id=execution_id,
                variables=executor_context or {},
                start_time=datetime.now()
            )
            
            self.executing_plans[plan_id] = execution
            plan.status = PlanStatus.EXECUTING
            plan.started_at = datetime.now()
            
            # Log início da execução
            self._log_audit_event(
                event_type="plan_execution_started",
                plan_id=plan_id,
                details={'execution_id': execution_id}
            )
            
            montar_log(
                f"📋 Plan-Execute: Iniciando execução do plano '{plan.plan_name}'",
                "INFO"
            )
            
            # Executar passos em sequência
            self._execute_plan_steps(plan, execution)
            
            return execution_id
            
        except Exception as e:
            montar_log(f"❌ Erro ao executar plano: {e}", "ERROR")
            raise
    
    def _execute_plan_steps(self, plan: ExecutionPlan, execution: PlanExecution):
        """Executa os passos do plano"""
        
        try:
            # Ordenar passos por dependências (topological sort simplificado)
            ordered_steps = self._order_steps_by_dependencies(plan.steps)
            
            for step in ordered_steps:
                if not self._can_execute_step(step, execution):
                    step.status = StepStatus.BLOCKED
                    execution.execution_log.append(f"Passo {step.step_name} bloqueado")
                    continue
                
                # Executar passo
                self._execute_single_step(step, execution)
                
                # Verificar se houve falha crítica
                if step.status == StepStatus.FAILED and step.step_type == StepType.DECISION:
                    execution.execution_log.append(f"Execução interrompida por falha crítica em {step.step_name}")
                    break
            
            # Finalizar execução
            self._finalize_plan_execution(plan, execution)
            
        except Exception as e:
            execution.execution_log.append(f"Erro fatal na execução: {e}")
            plan.status = PlanStatus.FAILED
            execution.end_time = datetime.now()
            montar_log(f"❌ Erro fatal na execução do plano: {e}", "ERROR")
    
    def _order_steps_by_dependencies(self, steps: List[PlanStep]) -> List[PlanStep]:
        """Ordena passos por dependências (topological sort)"""
        
        # Implementação simplificada
        step_map = {step.step_name: step for step in steps}
        ordered = []
        visited = set()
        
        def visit(step_name):
            if step_name in visited:
                return
            
            step = step_map.get(step_name)
            if not step:
                return
            
            # Visitar dependências primeiro
            for dep in step.dependencies:
                if dep in step_map:
                    visit(dep)
            
            visited.add(step_name)
            ordered.append(step)
        
        for step in steps:
            visit(step.step_name)
        
        return ordered
    
    def _can_execute_step(self, step: PlanStep, execution: PlanExecution) -> bool:
        """Verifica se um passo pode ser executado"""
        
        # Verificar dependências
        for dep in step.dependencies:
            if dep not in execution.step_results:
                return False
            
            # Verificar se dependência foi bem-sucedida
            dep_result = execution.step_results[dep]
            if not dep_result.get('success', False):
                return False
        
        # Verificar condições
        for condition in step.conditions:
            if not self._evaluate_condition(condition, execution):
                return False
        
        return True
    
    def _evaluate_condition(self, condition: str, execution: PlanExecution) -> bool:
        """Avalia condição de execução"""
        
        # Implementação simplificada de condições
        # Na prática, isso seria um sistema mais robusto
        
        if condition.startswith('var:'):
            # Verificar variável
            var_name = condition[4:]
            return execution.variables.get(var_name, False)
        
        elif condition.startswith('result:'):
            # Verificar resultado de passo anterior
            step_name = condition[7:]
            return execution.step_results.get(step_name, {}).get('success', False)
        
        # Condição sempre verdadeira por padrão
        return True
    
    def _execute_single_step(self, step: PlanStep, execution: PlanExecution):
        """Executa um único passo"""
        
        try:
            step.status = StepStatus.EXECUTING
            step.start_time = datetime.now()
            
            execution.execution_log.append(f"Iniciando passo: {step.step_name}")
            
            # Buscar executor
            executor = self.action_executors.get(step.action_name)
            if not executor:
                raise ValueError(f"Executor não encontrado para ação: {step.action_name}")
            
            # Executar com timeout
            result = executor(step.parameters)
            
            # Sucesso
            step.status = StepStatus.COMPLETED
            step.result = result
            step.end_time = datetime.now()
            
            execution.step_results[step.step_name] = {
                'success': True,
                'result': result,
                'execution_time': (step.end_time - step.start_time).total_seconds()
            }
            
            execution.completed_steps += 1
            self.stats['total_steps_executed'] += 1
            self.stats['steps_by_type'][step.step_type.value] += 1
            
            execution.execution_log.append(f"Passo {step.step_name} completado com sucesso")
            
        except Exception as e:
            # Falha
            step.status = StepStatus.FAILED
            step.error = str(e)
            step.end_time = datetime.now()
            
            execution.step_results[step.step_name] = {
                'success': False,
                'error': str(e)
            }
            
            execution.failed_steps += 1
            execution.execution_log.append(f"Passo {step.step_name} falhou: {e}")
            
            # Tentar retry se permitido
            if step.retry_count < step.max_retries:
                step.retry_count += 1
                step.status = StepStatus.PENDING
                execution.execution_log.append(f"Tentando novamente passo {step.step_name} (tentativa {step.retry_count + 1})")
                self._execute_single_step(step, execution)
    
    def _finalize_plan_execution(self, plan: ExecutionPlan, execution: PlanExecution):
        """Finaliza execução do plano"""
        
        execution.end_time = datetime.now()
        plan.completed_at = execution.end_time
        
        # Determinar status final
        if execution.failed_steps == 0:
            plan.status = PlanStatus.COMPLETED
            self.stats['completed_plans'] += 1
        else:
            plan.status = PlanStatus.FAILED
            self.stats['failed_plans'] += 1
        
        # Mover para lista de concluídos
        self.completed_plans[plan.plan_id] = plan
        del self.approved_plans[plan.plan_id]
        del self.executing_plans[plan.plan_id]
        
        # Log de auditoria
        self._log_audit_event(
            event_type="plan_execution_completed",
            plan_id=plan.plan_id,
            details={
                'status': plan.status.value,
                'completed_steps': execution.completed_steps,
                'failed_steps': execution.failed_steps,
                'execution_time': (execution.end_time - execution.start_time).total_seconds()
            }
        )
        
        status_msg = "CONCLUÍDO" if plan.status == PlanStatus.COMPLETED else "FALHOU"
        montar_log(
            f"📋 Plan-Execute: Plano '{plan.plan_name}' {status_msg} - "
            f"{execution.completed_steps} passos ok, {execution.failed_steps} falhas",
            "INFO"
        )
    
    def register_action_executor(self, action_name: str, executor_function: Callable):
        """Registra executor para uma ação"""
        self.action_executors[action_name] = executor_function
        montar_log(f"📋 Plan-Execute: Executor registrado para ação '{action_name}'", "INFO")
    
    def _log_audit_event(self, event_type: str, plan_id: str, details: Dict[str, Any]):
        """Registra evento na auditoria"""
        
        audit_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'plan_id': plan_id,
            'agent': self.agent_name,
            'details': details
        }
        
        self.audit_log.append(audit_entry)
    
    def get_plan_status(self, plan_id: str) -> Dict[str, Any]:
        """Retorna status de um plano"""
        
        # Buscar em todas as listas
        for plan_list, status_prefix in [
            (self.draft_plans, 'draft'),
            (self.approved_plans, 'approved'),
            (self.completed_plans, 'completed')
        ]:
            if plan_id in plan_list:
                plan = plan_list[plan_id]
                result = {
                    'status': plan.status.value,
                    'plan_details': {
                        'name': plan.plan_name,
                        'description': plan.description,
                        'creator': plan.creator,
                        'risk_level': plan.risk_level.value,
                        'step_count': len(plan.steps),
                        'created_at': plan.created_at.isoformat()
                    }
                }
                
                # Adicionar detalhes de execução se disponível
                if plan_id in self.executing_plans:
                    execution = self.executing_plans[plan_id]
                    result['execution_details'] = {
                        'execution_id': execution.execution_id,
                        'current_step': execution.current_step,
                        'completed_steps': execution.completed_steps,
                        'failed_steps': execution.failed_steps
                    }
                
                return result
        
        return {
            'status': 'not_found',
            'plan_details': {}
        }
    
    def get_plan_statistics(self) -> Dict[str, Any]:
        """Retorna estatísticas do agente"""
        
        # Estatísticas em tempo real
        current_stats = {
            'draft_plans': len(self.draft_plans),
            'approved_plans': len(self.approved_plans),
            'executing_plans': len(self.executing_plans),
            'completed_plans': len(self.completed_plans),
            'registered_executors': len(self.action_executors),
            'audit_entries': len(self.audit_log)
        }
        
        # Estatísticas históricas
        historical_stats = dict(self.stats)
        
        # Calcular taxas
        rates = {}
        if historical_stats['total_plans'] > 0:
            rates['approval_rate'] = historical_stats['approved_plans'] / historical_stats['total_plans']
            rates['completion_rate'] = historical_stats['completed_plans'] / historical_stats['total_plans']
        
        return {
            'agent_name': self.agent_name,
            'strict_planning': self.strict_planning,
            'current_statistics': current_stats,
            'historical_statistics': historical_stats,
            'rates': rates,
            'available_templates': list(self.plan_templates.keys())
        }