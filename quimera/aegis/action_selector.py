"""
Action-Selector Pattern - Sistema de Restrição de Ações para LLMs
================================================================

Implementa o padrão Action-Selector que:
- Restringe LLM a conjunto predefinido e enumerado de ações seguras
- Funciona como instrução "switch" para traduzir linguagem natural em ações
- É imune a injeções de prompt que visam executar ações novas/maliciosas
- Ideal para agentes com responsabilidades fixas como o "Bibliotecário Cognitivo"
"""

import time
import json
import hashlib
import re
from typing import Dict, List, Optional, Any, Callable, Union, Tuple, Set
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from abc import ABC, abstractmethod

from quimera.logs.parser import montar_log


class ActionStatus(Enum):
    """Status de execução da ação"""
    SUCCESS = "success"
    FAILURE = "failure"
    BLOCKED = "blocked"
    INVALID = "invalid"
    TIMEOUT = "timeout"
    ERROR = "error"


class ActionCategory(Enum):
    """Categorias de ações"""
    ANALYSIS = "analysis"
    SEARCH = "search"
    VALIDATION = "validation"
    REPORTING = "reporting"
    MAINTENANCE = "maintenance"
    CONFIGURATION = "configuration"


class SecurityLevel(Enum):
    """Níveis de segurança das ações"""
    PUBLIC = 1      # Ações públicas sem restrições
    USER = 2        # Ações que requerem autenticação de usuário
    ADMIN = 3       # Ações que requerem privilégios administrativos
    SYSTEM = 4      # Ações críticas do sistema


@dataclass
class ActionDefinition:
    """Definição de uma ação permitida"""
    action_id: str
    name: str
    description: str
    category: ActionCategory
    security_level: SecurityLevel
    parameters: List[str]
    function: Callable
    usage_count: int = 0
    last_used: Optional[datetime] = None
    success_rate: float = 1.0
    enabled: bool = True


@dataclass
class ActionRequest:
    """Solicitação de execução de ação"""
    request_id: str
    natural_language_request: str
    selected_action: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    user_context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ActionResult:
    """Resultado da execução de ação"""
    request_id: str
    action_id: str
    status: ActionStatus
    result: Any
    execution_time: float
    error_message: Optional[str] = None
    security_checks: Dict[str, bool] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class ActionSelector:
    """
    Seletor de ações que restringe LLM a conjunto predefinido
    
    Implementa padrão Action-Selector que funciona como "switch statement"
    traduzindo requisições em linguagem natural para ações predefinidas seguras.
    """
    
    def __init__(self, agent_name: str = "DefaultAgent"):
        self.agent_name = agent_name
        self.allowed_actions: Dict[str, ActionDefinition] = {}
        self.action_categories: Dict[ActionCategory, List[str]] = {}
        
        # Estatísticas de uso
        self.stats = {
            'total_requests': 0,
            'successful_actions': 0,
            'blocked_actions': 0,
            'invalid_requests': 0,
            'security_violations': 0,
            'average_execution_time': 0.0
        }
        
        # Configurações de segurança
        self.security_config = {
            'require_exact_match': False,
            'allow_parameter_inference': True,
            'max_execution_time': 30,
            'enable_security_logging': True,
            'whitelist_mode': True
        }
        
        # Padrões para reconhecimento de intenção
        self.intent_patterns = {
            'analysis': [
                r'analis[ae]', r'examin[ae]', r'review', r'inspect',
                r'check', r'verify', r'validate', r'study'
            ],
            'search': [
                r'search', r'find', r'look\s+for', r'locate',
                r'buscar', r'procurar', r'encontrar'
            ],
            'report': [
                r'report', r'generate', r'create', r'build',
                r'relat[oó]rio', r'gerar', r'criar'
            ],
            'fix': [
                r'fix', r'repair', r'correct', r'resolve',
                r'corrigir', r'reparar', r'resolver'
            ]
        }
        
        # Log de requisições
        self.request_log = []
        
        # Inicializar ações padrão
        self._initialize_default_actions()
        
    def _initialize_default_actions(self):
        """Inicializa conjunto padrão de ações seguras"""
        
        default_actions = [
            # Ações de análise
            {
                'action_id': 'analyze_file',
                'name': 'Analisar Arquivo',
                'description': 'Analisa conteúdo de arquivo de código',
                'category': ActionCategory.ANALYSIS,
                'security_level': SecurityLevel.USER,
                'parameters': ['file_path', 'analysis_type'],
                'function': self._action_analyze_file
            },
            {
                'action_id': 'check_syntax',
                'name': 'Verificar Sintaxe',
                'description': 'Verifica sintaxe de código Python',
                'category': ActionCategory.VALIDATION,
                'security_level': SecurityLevel.PUBLIC,
                'parameters': ['code_content'],
                'function': self._action_check_syntax
            },
            {
                'action_id': 'calculate_complexity',
                'name': 'Calcular Complexidade',
                'description': 'Calcula complexidade ciclomática do código',
                'category': ActionCategory.ANALYSIS,
                'security_level': SecurityLevel.PUBLIC,
                'parameters': ['code_content'],
                'function': self._action_calculate_complexity
            },
            
            # Ações de busca
            {
                'action_id': 'search_patterns',
                'name': 'Buscar Padrões',
                'description': 'Busca padrões específicos no código',
                'category': ActionCategory.SEARCH,
                'security_level': SecurityLevel.USER,
                'parameters': ['pattern', 'search_scope'],
                'function': self._action_search_patterns
            },
            {
                'action_id': 'find_vulnerabilities',
                'name': 'Encontrar Vulnerabilidades',
                'description': 'Procura vulnerabilidades conhecidas',
                'category': ActionCategory.ANALYSIS,
                'security_level': SecurityLevel.USER,
                'parameters': ['code_content', 'vuln_types'],
                'function': self._action_find_vulnerabilities
            },
            
            # Ações de relatório
            {
                'action_id': 'generate_report',
                'name': 'Gerar Relatório',
                'description': 'Gera relatório de análise',
                'category': ActionCategory.REPORTING,
                'security_level': SecurityLevel.USER,
                'parameters': ['analysis_results', 'report_format'],
                'function': self._action_generate_report
            },
            {
                'action_id': 'export_findings',
                'name': 'Exportar Descobertas',
                'description': 'Exporta descobertas em formato específico',
                'category': ActionCategory.REPORTING,
                'security_level': SecurityLevel.USER,
                'parameters': ['findings', 'export_format'],
                'function': self._action_export_findings
            },
            
            # Ações de manutenção
            {
                'action_id': 'cleanup_cache',
                'name': 'Limpar Cache',
                'description': 'Remove arquivos temporários e cache',
                'category': ActionCategory.MAINTENANCE,
                'security_level': SecurityLevel.ADMIN,
                'parameters': ['cache_type'],
                'function': self._action_cleanup_cache
            },
            {
                'action_id': 'update_patterns',
                'name': 'Atualizar Padrões',
                'description': 'Atualiza base de padrões de segurança',
                'category': ActionCategory.MAINTENANCE,
                'security_level': SecurityLevel.ADMIN,
                'parameters': ['pattern_source'],
                'function': self._action_update_patterns
            }
        ]
        
        # Registrar ações
        for action_data in default_actions:
            self.register_action(
                action_id=action_data['action_id'],
                name=action_data['name'],
                description=action_data['description'],
                category=action_data['category'],
                security_level=action_data['security_level'],
                parameters=action_data['parameters'],
                function=action_data['function']
            )
        
        montar_log(f"🎯 ActionSelector: {len(default_actions)} ações padrão registradas", "INFO")
    
    def register_action(
        self,
        action_id: str,
        name: str,
        description: str,
        category: ActionCategory,
        security_level: SecurityLevel,
        parameters: List[str],
        function: Callable
    ) -> bool:
        """
        Registra nova ação no conjunto permitido
        
        Args:
            action_id: ID único da ação
            name: Nome humano da ação
            description: Descrição detalhada
            category: Categoria da ação
            security_level: Nível de segurança necessário
            parameters: Lista de parâmetros necessários
            function: Função que implementa a ação
            
        Returns:
            True se registrada com sucesso
        """
        
        try:
            if action_id in self.allowed_actions:
                montar_log(f"⚠️ Ação {action_id} já existe, sobrescrevendo", "WARNING")
            
            action_def = ActionDefinition(
                action_id=action_id,
                name=name,
                description=description,
                category=category,
                security_level=security_level,
                parameters=parameters,
                function=function
            )
            
            self.allowed_actions[action_id] = action_def
            
            # Organizar por categoria
            if category not in self.action_categories:
                self.action_categories[category] = []
            
            if action_id not in self.action_categories[category]:
                self.action_categories[category].append(action_id)
            
            montar_log(f"✅ Ação {action_id} registrada com sucesso", "INFO")
            return True
            
        except Exception as e:
            montar_log(f"❌ Erro ao registrar ação {action_id}: {e}", "ERROR")
            return False
    
    async def process_request(
        self,
        natural_language_request: str,
        user_context: Dict[str, Any] = None
    ) -> ActionResult:
        """
        Processa requisição em linguagem natural e executa ação correspondente
        
        Args:
            natural_language_request: Solicitação em linguagem natural
            user_context: Contexto do usuário (auth, permissions, etc.)
            
        Returns:
            ActionResult com resultado da execução
        """
        
        start_time = time.time()
        request_id = self._generate_request_id()
        user_context = user_context or {}
        
        self.stats['total_requests'] += 1
        
        try:
            # Criar objeto de requisição
            request = ActionRequest(
                request_id=request_id,
                natural_language_request=natural_language_request,
                user_context=user_context
            )
            
            # Log da requisição
            if self.security_config['enable_security_logging']:
                self.request_log.append({
                    'request_id': request_id,
                    'timestamp': datetime.now(),
                    'request': natural_language_request[:100],
                    'user_context': {k: str(v)[:50] for k, v in user_context.items()}
                })
            
            montar_log(f"🎯 Processando requisição: {request_id}", "INFO")
            
            # Fase 1: Seleção de ação
            selected_action, confidence = await self._select_action(natural_language_request)
            
            if not selected_action:
                self.stats['invalid_requests'] += 1
                return ActionResult(
                    request_id=request_id,
                    action_id="NONE",
                    status=ActionStatus.INVALID,
                    result=None,
                    execution_time=time.time() - start_time,
                    error_message="Nenhuma ação válida encontrada para a requisição"
                )
            
            request.selected_action = selected_action
            
            # Fase 2: Extração de parâmetros
            parameters = await self._extract_parameters(
                natural_language_request, 
                selected_action,
                user_context
            )
            
            request.parameters = parameters
            
            # Fase 3: Verificações de segurança
            security_checks = await self._perform_security_checks(
                request, 
                user_context
            )
            
            if not all(security_checks.values()):
                self.stats['security_violations'] += 1
                failed_checks = [k for k, v in security_checks.items() if not v]
                
                return ActionResult(
                    request_id=request_id,
                    action_id=selected_action,
                    status=ActionStatus.BLOCKED,
                    result=None,
                    execution_time=time.time() - start_time,
                    error_message=f"Verificações de segurança falharam: {failed_checks}",
                    security_checks=security_checks
                )
            
            # Fase 4: Execução da ação
            execution_result = await self._execute_action(request)
            
            # Atualizar estatísticas
            if execution_result.status == ActionStatus.SUCCESS:
                self.stats['successful_actions'] += 1
            
            execution_time = time.time() - start_time
            self.stats['average_execution_time'] = (
                (self.stats['average_execution_time'] * (self.stats['total_requests'] - 1) + execution_time) /
                self.stats['total_requests']
            )
            
            execution_result.security_checks = security_checks
            
            montar_log(
                f"✅ Requisição {request_id} concluída: {execution_result.status.value} ({execution_time:.2f}s)",
                "INFO"
            )
            
            return execution_result
            
        except Exception as e:
            execution_time = time.time() - start_time
            montar_log(f"❌ Erro ao processar requisição {request_id}: {e}", "ERROR")
            
            return ActionResult(
                request_id=request_id,
                action_id="ERROR",
                status=ActionStatus.ERROR,
                result=None,
                execution_time=execution_time,
                error_message=str(e)
            )
    
    async def _select_action(self, request: str) -> Tuple[Optional[str], float]:
        """Seleciona ação mais apropriada para a requisição"""
        
        request_lower = request.lower()
        action_scores = {}
        
        # Método 1: Correspondência por palavras-chave
        for action_id, action_def in self.allowed_actions.items():
            if not action_def.enabled:
                continue
                
            score = 0.0
            
            # Score baseado no nome da ação
            name_words = action_def.name.lower().split()
            for word in name_words:
                if word in request_lower:
                    score += 0.3
            
            # Score baseado na descrição
            desc_words = action_def.description.lower().split()
            matching_desc_words = sum(1 for word in desc_words if word in request_lower)
            score += (matching_desc_words / len(desc_words)) * 0.2
            
            # Score baseado em padrões de intenção
            category_intent = action_def.category.value
            if category_intent in self.intent_patterns:
                for pattern in self.intent_patterns[category_intent]:
                    if re.search(pattern, request_lower):
                        score += 0.4
                        break
            
            # Bonus por histórico de sucesso
            score *= action_def.success_rate
            
            action_scores[action_id] = score
        
        # Método 2: Correspondência direta por ID ou nome
        for action_id, action_def in self.allowed_actions.items():
            if action_id.lower() in request_lower:
                action_scores[action_id] = max(action_scores.get(action_id, 0), 0.9)
            
            if action_def.name.lower() in request_lower:
                action_scores[action_id] = max(action_scores.get(action_id, 0), 0.8)
        
        # Selecionar ação com maior score
        if not action_scores:
            return None, 0.0
        
        best_action = max(action_scores.items(), key=lambda x: x[1])
        
        # Threshold mínimo para seleção
        if best_action[1] < 0.3:
            return None, best_action[1]
        
        return best_action[0], best_action[1]
    
    async def _extract_parameters(
        self,
        request: str,
        action_id: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extrai parâmetros da requisição para a ação selecionada"""
        
        action_def = self.allowed_actions[action_id]
        parameters = {}
        
        if not self.security_config['allow_parameter_inference']:
            return parameters
        
        # Extração básica de parâmetros baseada em heurísticas
        request_lower = request.lower()
        
        for param_name in action_def.parameters:
            param_value = None
            
            # Heurísticas específicas por tipo de parâmetro
            if 'file' in param_name or 'path' in param_name:
                # Procurar por caminhos de arquivo
                file_patterns = [
                    r'([a-zA-Z]:[\\\/][^\\\/\s]+)',  # Windows paths
                    r'(\/[^\/\s]+(?:\/[^\/\s]+)*)',  # Unix paths
                    r'([a-zA-Z_][a-zA-Z0-9_]*\.py)',  # Python files
                ]
                
                for pattern in file_patterns:
                    match = re.search(pattern, request)
                    if match:
                        param_value = match.group(1)
                        break
            
            elif 'code' in param_name:
                # Procurar por blocos de código
                code_patterns = [
                    r'```python\s*(.*?)\s*```',
                    r'```\s*(.*?)\s*```',
                    r'`([^`]+)`'
                ]
                
                for pattern in code_patterns:
                    match = re.search(pattern, request, re.DOTALL)
                    if match:
                        param_value = match.group(1).strip()
                        break
            
            elif 'pattern' in param_name:
                # Procurar por padrões entre aspas
                pattern_matches = re.findall(r'["\']([^"\']+)["\']', request)
                if pattern_matches:
                    param_value = pattern_matches[0]
            
            elif 'format' in param_name:
                # Formatos comuns
                format_keywords = ['json', 'xml', 'csv', 'pdf', 'html', 'markdown']
                for fmt in format_keywords:
                    if fmt in request_lower:
                        param_value = fmt
                        break
            
            elif 'type' in param_name:
                # Tipos de análise
                type_keywords = {
                    'security': ['security', 'vulnerability', 'segurança'],
                    'performance': ['performance', 'speed', 'optimization'],
                    'quality': ['quality', 'code quality', 'qualidade'],
                    'complexity': ['complexity', 'complexidade']
                }
                
                for type_name, keywords in type_keywords.items():
                    if any(keyword in request_lower for keyword in keywords):
                        param_value = type_name
                        break
            
            # Usar contexto como fallback
            if param_value is None and param_name in context:
                param_value = context[param_name]
            
            # Valores padrão
            if param_value is None:
                default_values = {
                    'analysis_type': 'general',
                    'search_scope': 'current_file',
                    'report_format': 'text',
                    'export_format': 'json',
                    'cache_type': 'all',
                    'pattern_source': 'default'
                }
                param_value = default_values.get(param_name)
            
            if param_value is not None:
                parameters[param_name] = param_value
        
        return parameters
    
    async def _perform_security_checks(
        self,
        request: ActionRequest,
        user_context: Dict[str, Any]
    ) -> Dict[str, bool]:
        """Executa verificações de segurança antes da execução"""
        
        checks = {}
        action_def = self.allowed_actions[request.selected_action]
        
        # Check 1: Ação está habilitada
        checks['action_enabled'] = action_def.enabled
        
        # Check 2: Verificação de nível de segurança
        user_level = SecurityLevel(user_context.get('security_level', SecurityLevel.PUBLIC.value))
        checks['security_level_ok'] = user_level.value >= action_def.security_level.value
        
        # Check 3: Ação está na whitelist (se habilitado)
        if self.security_config['whitelist_mode']:
            checks['whitelist_approved'] = request.selected_action in self.allowed_actions
        else:
            checks['whitelist_approved'] = True
        
        # Check 4: Parâmetros não contêm conteúdo malicioso
        checks['parameters_safe'] = await self._check_parameter_safety(request.parameters)
        
        # Check 5: Rate limiting por usuário
        user_id = user_context.get('user_id', 'anonymous')
        checks['rate_limit_ok'] = await self._check_rate_limit(user_id)
        
        # Check 6: Verificação de injeção na requisição original
        checks['no_injection'] = await self._check_injection_attempt(request.natural_language_request)
        
        return checks
    
    async def _check_parameter_safety(self, parameters: Dict[str, Any]) -> bool:
        """Verifica se parâmetros são seguros"""
        
        dangerous_patterns = [
            r'[;&|`$()]',  # Shell metacharacters
            r'\.\./',      # Directory traversal
            r'<script',    # XSS
            r'javascript:', # JavaScript URLs
            r'data:',      # Data URLs
            r'eval\s*\(',  # Code evaluation
            r'exec\s*\(',  # Code execution
        ]
        
        for param_name, param_value in parameters.items():
            if isinstance(param_value, str):
                for pattern in dangerous_patterns:
                    if re.search(pattern, param_value, re.IGNORECASE):
                        montar_log(f"🚨 Parâmetro perigoso detectado: {param_name}", "WARNING")
                        return False
        
        return True
    
    async def _check_rate_limit(self, user_id: str) -> bool:
        """Verifica rate limiting por usuário"""
        
        # Implementação simplificada - pode ser expandida
        current_time = datetime.now()
        recent_requests = [
            log for log in self.request_log[-100:]
            if (current_time - log['timestamp']).total_seconds() < 60
            and log.get('user_context', {}).get('user_id') == user_id
        ]
        
        # Máximo 30 requisições por minuto por usuário
        return len(recent_requests) < 30
    
    async def _check_injection_attempt(self, request: str) -> bool:
        """Verifica tentativas de injeção na requisição"""
        
        injection_patterns = [
            r'ignore\s+previous\s+instructions',
            r'forget\s+everything',
            r'new\s+instructions?',
            r'system\s*:',
            r'override\s+security',
            r'execute\s+command',
            r'run\s+shell',
            r'access\s+file\s+system'
        ]
        
        request_lower = request.lower()
        for pattern in injection_patterns:
            if re.search(pattern, request_lower):
                montar_log(f"🚨 Tentativa de injeção detectada: {pattern}", "WARNING")
                return False
        
        return True
    
    async def _execute_action(self, request: ActionRequest) -> ActionResult:
        """Executa a ação selecionada"""
        
        start_time = time.time()
        action_def = self.allowed_actions[request.selected_action]
        
        try:
            # Preparar parâmetros para execução
            execution_params = {
                'request': request.natural_language_request,
                'context': request.user_context,
                **request.parameters
            }
            
            # Executar com timeout
            import asyncio
            
            try:
                result = await asyncio.wait_for(
                    self._call_action_function(action_def.function, execution_params),
                    timeout=self.security_config['max_execution_time']
                )
                
                # Atualizar estatísticas da ação
                action_def.usage_count += 1
                action_def.last_used = datetime.now()
                
                # Atualizar taxa de sucesso
                if action_def.usage_count > 1:
                    action_def.success_rate = (
                        (action_def.success_rate * (action_def.usage_count - 1) + 1.0) /
                        action_def.usage_count
                    )
                
                return ActionResult(
                    request_id=request.request_id,
                    action_id=request.selected_action,
                    status=ActionStatus.SUCCESS,
                    result=result,
                    execution_time=time.time() - start_time
                )
                
            except asyncio.TimeoutError:
                return ActionResult(
                    request_id=request.request_id,
                    action_id=request.selected_action,
                    status=ActionStatus.TIMEOUT,
                    result=None,
                    execution_time=time.time() - start_time,
                    error_message=f"Timeout após {self.security_config['max_execution_time']}s"
                )
            
        except Exception as e:
            # Atualizar taxa de sucesso
            if action_def.usage_count > 0:
                action_def.success_rate = (
                    action_def.success_rate * action_def.usage_count / (action_def.usage_count + 1)
                )
            
            montar_log(f"❌ Erro na execução da ação {request.selected_action}: {e}", "ERROR")
            
            return ActionResult(
                request_id=request.request_id,
                action_id=request.selected_action,
                status=ActionStatus.ERROR,
                result=None,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )
    
    async def _call_action_function(self, function: Callable, params: Dict[str, Any]) -> Any:
        """Chama função de ação com parâmetros"""
        
        import asyncio
        
        # Se a função é async
        if asyncio.iscoroutinefunction(function):
            return await function(**params)
        else:
            return function(**params)
    
    def _generate_request_id(self) -> str:
        """Gera ID único para requisição"""
        timestamp = str(int(time.time() * 1000))
        import threading
        thread_id = str(threading.current_thread().ident)
        return f"req-{hashlib.sha256(f'{timestamp}:{thread_id}'.encode()).hexdigest()[:12]}"
    
    # ==================== IMPLEMENTAÇÕES DAS AÇÕES PADRÃO ====================
    
    def _action_analyze_file(self, **kwargs) -> Dict[str, Any]:
        """Implementação da ação analyze_file"""
        file_path = kwargs.get('file_path', '')
        analysis_type = kwargs.get('analysis_type', 'general')
        
        if not file_path:
            return {'error': 'file_path parameter required'}
        
        try:
            # Simulação de análise de arquivo
            analysis_result = {
                'file_path': file_path,
                'analysis_type': analysis_type,
                'file_size': 'unknown',
                'line_count': 'unknown',
                'issues_found': [],
                'recommendations': ['Análise simulada - arquivo não acessado por segurança']
            }
            
            return analysis_result
            
        except Exception as e:
            return {'error': f'Analysis failed: {str(e)}'}
    
    def _action_check_syntax(self, **kwargs) -> Dict[str, Any]:
        """Implementação da ação check_syntax"""
        code_content = kwargs.get('code_content', '')
        
        if not code_content:
            return {'error': 'code_content parameter required'}
        
        try:
            import ast
            ast.parse(code_content)
            
            return {
                'syntax_valid': True,
                'message': 'Syntax is valid',
                'issues': []
            }
            
        except SyntaxError as e:
            return {
                'syntax_valid': False,
                'message': f'Syntax error: {e.msg}',
                'line': e.lineno,
                'column': e.offset,
                'issues': [str(e)]
            }
        except Exception as e:
            return {'error': f'Syntax check failed: {str(e)}'}
    
    def _action_calculate_complexity(self, **kwargs) -> Dict[str, Any]:
        """Implementação da ação calculate_complexity"""
        code_content = kwargs.get('code_content', '')
        
        if not code_content:
            return {'error': 'code_content parameter required'}
        
        try:
            import ast
            
            tree = ast.parse(code_content)
            complexity = 1  # Base complexity
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.If, ast.While, ast.For, ast.Try)):
                    complexity += 1
                elif isinstance(node, ast.BoolOp):
                    complexity += len(node.values) - 1
            
            return {
                'cyclomatic_complexity': complexity,
                'complexity_level': 'low' if complexity <= 5 else 'medium' if complexity <= 10 else 'high',
                'recommendations': ['Consider refactoring if complexity > 10'] if complexity > 10 else []
            }
            
        except Exception as e:
            return {'error': f'Complexity calculation failed: {str(e)}'}
    
    def _action_search_patterns(self, **kwargs) -> Dict[str, Any]:
        """Implementação da ação search_patterns"""
        pattern = kwargs.get('pattern', '')
        search_scope = kwargs.get('search_scope', 'current_file')
        
        if not pattern:
            return {'error': 'pattern parameter required'}
        
        # Simulação de busca
        return {
            'pattern': pattern,
            'search_scope': search_scope,
            'matches_found': 0,
            'locations': [],
            'message': 'Pattern search simulated - no actual files accessed'
        }
    
    def _action_find_vulnerabilities(self, **kwargs) -> Dict[str, Any]:
        """Implementação da ação find_vulnerabilities"""
        code_content = kwargs.get('code_content', '')
        vuln_types = kwargs.get('vuln_types', 'all')
        
        if not code_content:
            return {'error': 'code_content parameter required'}
        
        # Verificações básicas de segurança
        vulnerabilities = []
        
        dangerous_patterns = [
            (r'eval\s*\(', 'Code Injection', 'high'),
            (r'exec\s*\(', 'Code Execution', 'high'),
            (r'os\.system\s*\(', 'Command Injection', 'critical'),
            (r'input\s*\(', 'Input Injection', 'medium'),
            (r'pickle\.loads?\s*\(', 'Deserialization', 'high')
        ]
        
        for pattern, vuln_name, severity in dangerous_patterns:
            import re
            if re.search(pattern, code_content):
                vulnerabilities.append({
                    'type': vuln_name,
                    'severity': severity,
                    'pattern': pattern,
                    'recommendation': f'Avoid using {vuln_name.lower()} or validate inputs'
                })
        
        return {
            'vulnerabilities_found': len(vulnerabilities),
            'vulnerabilities': vulnerabilities,
            'scan_type': vuln_types,
            'recommendations': ['Use static analysis tools for comprehensive scanning']
        }
    
    def _action_generate_report(self, **kwargs) -> Dict[str, Any]:
        """Implementação da ação generate_report"""
        analysis_results = kwargs.get('analysis_results', {})
        report_format = kwargs.get('report_format', 'text')
        
        report_content = f"""
=== RELATÓRIO DE ANÁLISE ===
Formato: {report_format}
Timestamp: {datetime.now().isoformat()}

Resultados da Análise:
{json.dumps(analysis_results, indent=2, default=str)}

=== FIM DO RELATÓRIO ===
"""
        
        return {
            'report_generated': True,
            'format': report_format,
            'content': report_content,
            'size': len(report_content)
        }
    
    def _action_export_findings(self, **kwargs) -> Dict[str, Any]:
        """Implementação da ação export_findings"""
        findings = kwargs.get('findings', [])
        export_format = kwargs.get('export_format', 'json')
        
        if export_format == 'json':
            export_content = json.dumps(findings, indent=2, default=str)
        elif export_format == 'csv':
            export_content = 'finding_type,severity,description\n'
            for finding in findings:
                export_content += f"{finding.get('type', '')},{finding.get('severity', '')},{finding.get('description', '')}\n"
        else:
            export_content = str(findings)
        
        return {
            'export_completed': True,
            'format': export_format,
            'findings_count': len(findings),
            'content': export_content
        }
    
    def _action_cleanup_cache(self, **kwargs) -> Dict[str, Any]:
        """Implementação da ação cleanup_cache"""
        cache_type = kwargs.get('cache_type', 'all')
        
        # Simulação de limpeza
        cleaned_items = 42  # Simulado
        freed_space = "15.3 MB"  # Simulado
        
        return {
            'cleanup_completed': True,
            'cache_type': cache_type,
            'items_cleaned': cleaned_items,
            'space_freed': freed_space,
            'message': 'Cache cleanup simulated'
        }
    
    def _action_update_patterns(self, **kwargs) -> Dict[str, Any]:
        """Implementação da ação update_patterns"""
        pattern_source = kwargs.get('pattern_source', 'default')
        
        # Simulação de atualização
        return {
            'update_completed': True,
            'pattern_source': pattern_source,
            'patterns_updated': 128,  # Simulado
            'new_patterns': 15,       # Simulado
            'message': 'Pattern database update simulated'
        }
    
    # ==================== MÉTODOS DE ADMINISTRAÇÃO ====================
    
    def get_available_actions(self) -> Dict[str, Dict]:
        """Retorna lista de ações disponíveis"""
        
        actions_info = {}
        
        for action_id, action_def in self.allowed_actions.items():
            actions_info[action_id] = {
                'name': action_def.name,
                'description': action_def.description,
                'category': action_def.category.value,
                'security_level': action_def.security_level.value,
                'parameters': action_def.parameters,
                'usage_count': action_def.usage_count,
                'success_rate': action_def.success_rate,
                'enabled': action_def.enabled,
                'last_used': action_def.last_used.isoformat() if action_def.last_used else None
            }
        
        return actions_info
    
    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estatísticas do ActionSelector"""
        
        success_rate = 0.0
        if self.stats['total_requests'] > 0:
            success_rate = self.stats['successful_actions'] / self.stats['total_requests']
        
        block_rate = 0.0
        if self.stats['total_requests'] > 0:
            block_rate = self.stats['blocked_actions'] / self.stats['total_requests']
        
        return {
            'agent_name': self.agent_name,
            'statistics': self.stats.copy(),
            'success_rate': success_rate,
            'block_rate': block_rate,
            'total_actions_registered': len(self.allowed_actions),
            'actions_by_category': {
                category.value: len(actions)
                for category, actions in self.action_categories.items()
            },
            'security_config': self.security_config.copy(),
            'most_used_actions': self._get_most_used_actions(5),
            'recent_requests': len([
                log for log in self.request_log[-50:]
                if (datetime.now() - log['timestamp']).total_seconds() < 3600
            ])
        }
    
    def _get_most_used_actions(self, limit: int = 5) -> List[Dict]:
        """Retorna ações mais usadas"""
        
        sorted_actions = sorted(
            self.allowed_actions.items(),
            key=lambda x: x[1].usage_count,
            reverse=True
        )
        
        return [
            {
                'action_id': action_id,
                'name': action_def.name,
                'usage_count': action_def.usage_count,
                'success_rate': action_def.success_rate
            }
            for action_id, action_def in sorted_actions[:limit]
        ]
    
    def enable_action(self, action_id: str) -> bool:
        """Habilita ação específica"""
        if action_id in self.allowed_actions:
            self.allowed_actions[action_id].enabled = True
            montar_log(f"✅ Ação {action_id} habilitada", "INFO")
            return True
        return False
    
    def disable_action(self, action_id: str) -> bool:
        """Desabilita ação específica"""
        if action_id in self.allowed_actions:
            self.allowed_actions[action_id].enabled = False
            montar_log(f"🔒 Ação {action_id} desabilitada", "INFO")
            return True
        return False
    
    def update_security_config(self, config_updates: Dict) -> bool:
        """Atualiza configurações de segurança"""
        try:
            self.security_config.update(config_updates)
            montar_log("🔧 Configurações de segurança atualizadas", "INFO")
            return True
        except Exception as e:
            montar_log(f"❌ Erro ao atualizar configurações: {e}", "ERROR")
            return False