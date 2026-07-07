"""
Dual LLM Pattern - Sistema de Separação de Privilégios para LLMs
==============================================================

Implementa o padrão arquitetônico Dual LLM que:
- Separa LLM privilegiado (com ferramentas) do LLM em quarentena (sem ferramentas)
- Isola processamento de dados não confiáveis da execução de ações
- Cria forte fronteira de isolamento entre tomada de decisões e processamento
- É imune a injeção de prompt que causa uso de ferramentas por LLM em quarentena
"""

import asyncio
import time
import json
import hashlib
import threading
from typing import Dict, List, Optional, Any, Callable, Union, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from abc import ABC, abstractmethod

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


class LLMRole(Enum):
    """Papéis dos LLMs no padrão dual"""
    PRIVILEGED = "privileged"    # LLM com acesso a ferramentas
    QUARANTINE = "quarantine"    # LLM isolado sem ferramentas


class TrustLevel(Enum):
    """Níveis de confiança para dados"""
    TRUSTED = "trusted"          # Dados do sistema/configuração
    UNTRUSTED = "untrusted"      # Dados do usuário/externos
    MIXED = "mixed"              # Mistura de dados confiáveis e não confiáveis


class SecurityContext(Enum):
    """Contextos de segurança para operações"""
    SAFE = "safe"                # Contexto completamente seguro
    MONITORED = "monitored"      # Contexto monitorado
    RESTRICTED = "restricted"    # Contexto com restrições
    QUARANTINED = "quarantined"  # Contexto em quarentena


class OperationResult(Enum):
    """Resultados possíveis das operações"""
    SUCCESS = "success"
    FAILURE = "failure"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class QuarantineResult:
    """Resultado de processamento em quarentena"""
    analysis: str
    confidence_score: float
    safety_assessment: Dict
    processing_time: float
    metadata: Dict = field(default_factory=dict)
    is_safe: bool = True
    recommendations: List[str] = field(default_factory=list)


@dataclass
class PrivilegedOperation:
    """Operação a ser executada pelo LLM privilegiado"""
    operation_id: str
    operation_type: str
    parameters: Dict
    authorization_level: str
    timestamp: datetime = field(default_factory=datetime.now)
    approved: bool = False


@dataclass
class DualLLMResult:
    """Resultado completo do padrão Dual LLM"""
    operation_id: str
    quarantine_result: QuarantineResult
    privileged_result: Optional[Dict]
    overall_result: OperationResult
    security_metrics: Dict
    execution_time: float
    timestamp: datetime = field(default_factory=datetime.now)


class LLMInterface(ABC):
    """Interface abstrata para LLMs"""
    
    @abstractmethod
    async def process(self, prompt: str, context: Dict = None) -> Dict:
        """Processa prompt e retorna resultado"""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """Retorna lista de capacidades do LLM"""
        pass


class PrivilegedLLM(LLMInterface):
    """LLM privilegiado com acesso a ferramentas do sistema"""
    
    def __init__(self, tools: Dict[str, Callable] = None):
        self.tools = tools or {}
        self.operation_log = []
        self.access_controls = {
            'max_operations_per_minute': 60,
            'allowed_operations': set(),
            'forbidden_patterns': [],
            'require_approval_for': []
        }
        self._operation_count = 0
        self._last_reset = datetime.now()
        
    async def process(self, prompt: str, context: Dict = None) -> Dict:
        """Processa prompt com acesso a ferramentas"""
        start_time = time.time()
        
        try:
            # Verificar rate limiting
            if not self._check_rate_limit():
                return {
                    'success': False,
                    'error': 'Rate limit exceeded',
                    'result': None
                }
            
            # Log da operação
            operation_id = self._generate_operation_id()
            self.operation_log.append({
                'operation_id': operation_id,
                'timestamp': datetime.now(),
                'prompt_hash': hashlib.sha256(prompt.encode()).hexdigest()[:16],
                'context': context
            })
            
            # Simulação de processamento LLM com acesso a ferramentas
            result = await self._process_with_tools(prompt, context)
            
            processing_time = time.time() - start_time
            
            return {
                'success': True,
                'result': result,
                'operation_id': operation_id,
                'processing_time': processing_time,
                'tools_used': result.get('tools_used', [])
            }
            
        except Exception as e:
            montar_log(f"❌ Erro no LLM privilegiado: {e}", "ERROR")
            return {
                'success': False,
                'error': str(e),
                'result': None
            }
    
    async def _process_with_tools(self, prompt: str, context: Dict) -> Dict:
        """Processa prompt com acesso a ferramentas"""
        
        # Análise do prompt para identificar ferramentas necessárias
        required_tools = self._identify_required_tools(prompt)
        
        # Verificar autorização para ferramentas
        authorized_tools = []
        for tool_name in required_tools:
            if self._is_tool_authorized(tool_name, context):
                authorized_tools.append(tool_name)
        
        # Executar com ferramentas autorizadas
        tools_used = []
        results = {}
        
        for tool_name in authorized_tools:
            if tool_name in self.tools:
                try:
                    tool_result = await self._execute_tool(tool_name, prompt, context)
                    results[tool_name] = tool_result
                    tools_used.append(tool_name)
                except Exception as e:
                    montar_log(f"⚠️ Erro na ferramenta {tool_name}: {e}", "WARNING")
                    results[tool_name] = {'error': str(e)}
        
        return {
            'analysis': f"Processed prompt with {len(tools_used)} tools",
            'tool_results': results,
            'tools_used': tools_used,
            'authorized_tools': authorized_tools,
            'requested_tools': required_tools
        }
    
    def _identify_required_tools(self, prompt: str) -> List[str]:
        """Identifica ferramentas necessárias baseado no prompt"""
        
        # Mapeamento de palavras-chave para ferramentas
        tool_keywords = {
            'analisar_arquivo': ['analyze', 'file', 'código', 'code'],
            'propor_patch': ['fix', 'patch', 'correct', 'repair'],
            'verificar_sintaxe': ['syntax', 'check', 'validate'],
            'executar_comando': ['run', 'execute', 'command'],
            'consultar_base': ['search', 'query', 'database'],
            'gerar_relatorio': ['report', 'generate', 'document']
        }
        
        required_tools = []
        prompt_lower = prompt.lower()
        
        for tool_name, keywords in tool_keywords.items():
            if any(keyword in prompt_lower for keyword in keywords):
                required_tools.append(tool_name)
        
        return required_tools
    
    def _is_tool_authorized(self, tool_name: str, context: Dict) -> bool:
        """Verifica se ferramenta está autorizada"""
        
        # Verificar se está na lista de permitidas
        if self.access_controls['allowed_operations'] and \
           tool_name not in self.access_controls['allowed_operations']:
            return False
        
        # Verificar padrões proibidos
        for pattern in self.access_controls['forbidden_patterns']:
            if pattern in tool_name:
                return False
        
        # Verificar nível de autorização no contexto
        auth_level = context.get('authorization_level', 'user')
        if tool_name in self.access_controls['require_approval_for'] and \
           auth_level != 'admin':
            return False
        
        return True
    
    async def _execute_tool(self, tool_name: str, prompt: str, context: Dict) -> Dict:
        """Executa ferramenta específica"""
        
        if tool_name not in self.tools:
            return {'error': f'Tool {tool_name} not available'}
        
        try:
            tool_func = self.tools[tool_name]
            
            # Se a ferramenta é async
            if asyncio.iscoroutinefunction(tool_func):
                result = await tool_func(prompt, context)
            else:
                result = tool_func(prompt, context)
            
            return {
                'success': True,
                'result': result,
                'tool': tool_name
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'tool': tool_name
            }
    
    def _check_rate_limit(self) -> bool:
        """Verifica rate limiting"""
        now = datetime.now()
        
        # Reset contador se passou 1 minuto
        if now - self._last_reset > timedelta(minutes=1):
            self._operation_count = 0
            self._last_reset = now
        
        # Verificar limite
        if self._operation_count >= self.access_controls['max_operations_per_minute']:
            return False
        
        self._operation_count += 1
        return True
    
    def _generate_operation_id(self) -> str:
        """Gera ID único para operação"""
        timestamp = str(int(time.time() * 1000))
        thread_id = str(threading.current_thread().ident)
        return hashlib.sha256(f"{timestamp}:{thread_id}".encode()).hexdigest()[:12]
    
    def get_capabilities(self) -> List[str]:
        """Retorna capacidades do LLM privilegiado"""
        return [
            'tool_execution',
            'system_access',
            'file_operations',
            'privileged_analysis'
        ] + list(self.tools.keys())
    
    def add_tool(self, name: str, tool_func: Callable):
        """Adiciona nova ferramenta"""
        self.tools[name] = tool_func
        montar_log(f"🔧 Ferramenta {name} adicionada ao LLM privilegiado", "INFO")
    
    def set_access_control(self, control_type: str, value: Any):
        """Define controle de acesso"""
        if control_type in self.access_controls:
            self.access_controls[control_type] = value
            montar_log(f"🔒 Controle de acesso {control_type} atualizado", "INFO")


class QuarantineLLM(LLMInterface):
    """LLM em quarentena sem acesso a ferramentas"""
    
    def __init__(self):
        self.processing_log = []
        self.restrictions = {
            'max_processing_time': 30,  # segundos
            'max_prompt_length': 10000,  # caracteres
            'forbidden_keywords': [
                'execute', 'run', 'system', 'command', 'shell',
                'file', 'write', 'delete', 'modify'
            ],
            'memory_limit': 100 * 1024 * 1024  # 100MB
        }
        self.safety_filters = [
            self._check_injection_attempt,
            self._check_malicious_content,
            self._check_prompt_manipulation,
            self._check_system_extraction
        ]
        
    async def process(self, prompt: str, context: Dict = None) -> Dict:
        """Processa prompt em ambiente isolado"""
        start_time = time.time()
        
        try:
            # Verificações de segurança pré-processamento
            safety_check = await self._run_safety_checks(prompt)
            if not safety_check['safe']:
                return {
                    'success': False,
                    'error': f"Safety check failed: {safety_check['reason']}",
                    'safety_assessment': safety_check
                }
            
            # Verificar restrições
            if not self._check_restrictions(prompt):
                return {
                    'success': False,
                    'error': 'Prompt violates quarantine restrictions',
                    'restrictions_violated': self._get_violated_restrictions(prompt)
                }
            
            # Processar em ambiente isolado
            result = await self._process_in_isolation(prompt, context)
            
            processing_time = time.time() - start_time
            
            # Log do processamento
            self.processing_log.append({
                'timestamp': datetime.now(),
                'prompt_hash': hashlib.sha256(prompt.encode()).hexdigest()[:16],
                'processing_time': processing_time,
                'safety_score': safety_check['score']
            })
            
            return {
                'success': True,
                'result': result,
                'processing_time': processing_time,
                'safety_assessment': safety_check
            }
            
        except Exception as e:
            montar_log(f"❌ Erro no LLM em quarentena: {e}", "ERROR")
            return {
                'success': False,
                'error': str(e),
                'result': None
            }
    
    async def _run_safety_checks(self, prompt: str) -> Dict:
        """Executa verificações de segurança"""
        
        safety_results = []
        total_score = 0.0
        
        for filter_func in self.safety_filters:
            try:
                result = await filter_func(prompt)
                safety_results.append(result)
                total_score += result['score']
            except Exception as e:
                safety_results.append({
                    'filter': filter_func.__name__,
                    'score': 0.0,
                    'safe': False,
                    'reason': f"Filter error: {e}"
                })
        
        avg_score = total_score / len(self.safety_filters) if self.safety_filters else 1.0
        overall_safe = all(result['safe'] for result in safety_results)
        
        if not overall_safe:
            failed_filters = [r['filter'] for r in safety_results if not r['safe']]
            reason = f"Failed filters: {', '.join(failed_filters)}"
        else:
            reason = "All safety checks passed"
        
        return {
            'safe': overall_safe,
            'score': avg_score,
            'reason': reason,
            'filter_results': safety_results
        }
    
    async def _check_injection_attempt(self, prompt: str) -> Dict:
        """Verifica tentativas de injeção de prompt"""
        
        injection_patterns = [
            r'ignore\s+previous\s+instructions',
            r'forget\s+everything',
            r'new\s+instructions?',
            r'system\s*:',
            r'user\s*:',
            r'assistant\s*:',
            r'jailbreak',
            r'override\s+security',
            r'disable\s+safety',
            r'act\s+as\s+if',
            r'pretend\s+to\s+be',
            r'role\s*play\s+as'
        ]
        
        injection_score = 0.0
        detected_patterns = []
        
        for pattern in injection_patterns:
            import re
            if re.search(pattern, prompt, re.IGNORECASE):
                injection_score += 0.2
                detected_patterns.append(pattern)
        
        injection_score = min(injection_score, 1.0)
        is_safe = injection_score < 0.3
        
        return {
            'filter': 'injection_attempt',
            'score': 1.0 - injection_score,
            'safe': is_safe,
            'reason': f"Injection patterns detected: {detected_patterns}" if detected_patterns else "No injection detected",
            'detected_patterns': detected_patterns
        }
    
    async def _check_malicious_content(self, prompt: str) -> Dict:
        """Verifica conteúdo malicioso"""
        
        malicious_keywords = [
            'malware', 'virus', 'trojan', 'backdoor', 'exploit',
            'hack', 'crack', 'bypass', 'privilege escalation',
            'sql injection', 'xss', 'csrf', 'buffer overflow'
        ]
        
        malicious_score = 0.0
        found_keywords = []
        
        prompt_lower = prompt.lower()
        for keyword in malicious_keywords:
            if keyword in prompt_lower:
                malicious_score += 0.15
                found_keywords.append(keyword)
        
        malicious_score = min(malicious_score, 1.0)
        is_safe = malicious_score < 0.2
        
        return {
            'filter': 'malicious_content',
            'score': 1.0 - malicious_score,
            'safe': is_safe,
            'reason': f"Malicious keywords found: {found_keywords}" if found_keywords else "No malicious content detected",
            'found_keywords': found_keywords
        }
    
    async def _check_prompt_manipulation(self, prompt: str) -> Dict:
        """Verifica tentativas de manipulação de prompt"""
        
        manipulation_indicators = [
            'temperature', 'top_p', 'max_tokens', 'stop_sequence',
            'system_message', 'context_window', 'embedding',
            'fine_tune', 'training_data', 'model_weights'
        ]
        
        manipulation_score = 0.0
        found_indicators = []
        
        prompt_lower = prompt.lower()
        for indicator in manipulation_indicators:
            if indicator.replace('_', ' ') in prompt_lower or indicator in prompt_lower:
                manipulation_score += 0.1
                found_indicators.append(indicator)
        
        manipulation_score = min(manipulation_score, 1.0)
        is_safe = manipulation_score < 0.2
        
        return {
            'filter': 'prompt_manipulation',
            'score': 1.0 - manipulation_score,
            'safe': is_safe,
            'reason': f"Manipulation indicators: {found_indicators}" if found_indicators else "No manipulation detected",
            'found_indicators': found_indicators
        }
    
    async def _check_system_extraction(self, prompt: str) -> Dict:
        """Verifica tentativas de extração de informações do sistema"""
        
        extraction_patterns = [
            r'what\s+are\s+your\s+instructions',
            r'show\s+me\s+your\s+prompt',
            r'reveal\s+your\s+system',
            r'dump\s+configuration',
            r'display\s+settings',
            r'print\s+system\s+info',
            r'export\s+data',
            r'backup\s+system'
        ]
        
        extraction_score = 0.0
        detected_patterns = []
        
        for pattern in extraction_patterns:
            import re
            if re.search(pattern, prompt, re.IGNORECASE):
                extraction_score += 0.25
                detected_patterns.append(pattern)
        
        extraction_score = min(extraction_score, 1.0)
        is_safe = extraction_score < 0.3
        
        return {
            'filter': 'system_extraction',
            'score': 1.0 - extraction_score,
            'safe': is_safe,
            'reason': f"Extraction patterns: {detected_patterns}" if detected_patterns else "No extraction attempt detected",
            'detected_patterns': detected_patterns
        }
    
    def _check_restrictions(self, prompt: str) -> bool:
        """Verifica se prompt viola restrições"""
        
        # Comprimento máximo
        if len(prompt) > self.restrictions['max_prompt_length']:
            return False
        
        # Palavras-chave proibidas
        prompt_lower = prompt.lower()
        for keyword in self.restrictions['forbidden_keywords']:
            if keyword in prompt_lower:
                return False
        
        return True
    
    def _get_violated_restrictions(self, prompt: str) -> List[str]:
        """Retorna lista de restrições violadas"""
        violations = []
        
        if len(prompt) > self.restrictions['max_prompt_length']:
            violations.append(f"Prompt too long: {len(prompt)} > {self.restrictions['max_prompt_length']}")
        
        prompt_lower = prompt.lower()
        for keyword in self.restrictions['forbidden_keywords']:
            if keyword in prompt_lower:
                violations.append(f"Forbidden keyword: {keyword}")
        
        return violations
    
    async def _process_in_isolation(self, prompt: str, context: Dict) -> QuarantineResult:
        """Processa prompt em isolamento completo"""
        
        # Simulação de processamento seguro sem acesso a ferramentas
        analysis = await self._safe_analysis(prompt, context)
        
        # Avaliação de segurança do resultado
        safety_assessment = await self._assess_result_safety(analysis)
        
        # Gerar recomendações
        recommendations = self._generate_recommendations(prompt, analysis, safety_assessment)
        
        return QuarantineResult(
            analysis=analysis,
            confidence_score=safety_assessment['confidence'],
            safety_assessment=safety_assessment,
            processing_time=0.0,  # Será preenchido pelo chamador
            is_safe=safety_assessment['safe'],
            recommendations=recommendations
        )
    
    async def _safe_analysis(self, prompt: str, context: Dict) -> str:
        """Análise segura do prompt"""
        
        # Análise estrutural do prompt
        structure_analysis = f"Prompt length: {len(prompt)} characters"
        
        # Análise de conteúdo (sem executar nada)
        content_analysis = "Content analysis: General text processing request"
        
        # Análise de intenção
        intent_keywords = ['analyze', 'review', 'check', 'examine', 'study']
        if any(keyword in prompt.lower() for keyword in intent_keywords):
            intent_analysis = "Intent: Analysis or review request"
        else:
            intent_analysis = "Intent: General information request"
        
        return f"{structure_analysis}. {content_analysis}. {intent_analysis}"
    
    async def _assess_result_safety(self, analysis: str) -> Dict:
        """Avalia segurança do resultado da análise"""
        
        # Verifica se o resultado contém informações sensíveis
        sensitive_indicators = [
            'password', 'key', 'token', 'secret', 'credential',
            'private', 'confidential', 'internal', 'restricted'
        ]
        
        sensitivity_score = 0.0
        analysis_lower = analysis.lower()
        
        for indicator in sensitive_indicators:
            if indicator in analysis_lower:
                sensitivity_score += 0.2
        
        sensitivity_score = min(sensitivity_score, 1.0)
        is_safe = sensitivity_score < 0.3
        confidence = 1.0 - sensitivity_score
        
        return {
            'safe': is_safe,
            'confidence': confidence,
            'sensitivity_score': sensitivity_score,
            'reason': 'Safe analysis result' if is_safe else 'Potentially sensitive content in result'
        }
    
    def _generate_recommendations(self, prompt: str, analysis: str, safety: Dict) -> List[str]:
        """Gera recomendações baseadas na análise"""
        recommendations = []
        
        if not safety['safe']:
            recommendations.append("Review result for sensitive information before sharing")
        
        if len(prompt) > 5000:
            recommendations.append("Consider breaking down large prompts into smaller parts")
        
        if safety['confidence'] < 0.7:
            recommendations.append("Low confidence result - consider additional validation")
        
        recommendations.append("Analysis completed in quarantine environment - no system access occurred")
        
        return recommendations
    
    def get_capabilities(self) -> List[str]:
        """Retorna capacidades do LLM em quarentena"""
        return [
            'safe_text_analysis',
            'isolated_processing',
            'security_assessment',
            'content_review'
        ]


class DualLLMSecurityPattern:
    """Implementação do padrão de segurança Dual LLM"""
    
    def __init__(self):
        self.privileged_llm = PrivilegedLLM()
        self.quarantine_llm = QuarantineLLM()
        
        self.operation_log = []
        self.security_metrics = {
            'total_operations': 0,
            'quarantine_blocks': 0,
            'privileged_executions': 0,
            'security_violations': 0,
            'average_processing_time': 0.0
        }
        
        # Configurações de segurança
        self.security_config = {
            'require_quarantine_approval': True,
            'min_safety_score': 0.7,
            'max_processing_time': 60,
            'enable_cross_validation': True
        }
        
    async def secure_analysis(
        self,
        user_input: str,
        analysis_task: str,
        trust_level: TrustLevel = TrustLevel.UNTRUSTED,
        context: Dict = None
    ) -> DualLLMResult:
        """
        Executa análise segura usando padrão Dual LLM
        
        Args:
            user_input: Input do usuário (não confiável)
            analysis_task: Tarefa de análise a ser executada
            trust_level: Nível de confiança dos dados
            context: Contexto adicional da operação
            
        Returns:
            DualLLMResult com resultado completo
        """
        start_time = time.time()
        operation_id = self._generate_operation_id()
        
        self.security_metrics['total_operations'] += 1
        
        try:
            montar_log(f"🔄 Iniciando análise Dual LLM: {operation_id}", "INFO")
            
            # Fase 1: Processamento em quarentena
            quarantine_result = await self._quarantine_phase(
                user_input, analysis_task, context
            )
            
            # Verificar se quarentena aprovou o processamento
            if not quarantine_result.is_safe:
                self.security_metrics['quarantine_blocks'] += 1
                
                return DualLLMResult(
                    operation_id=operation_id,
                    quarantine_result=quarantine_result,
                    privileged_result=None,
                    overall_result=OperationResult.BLOCKED,
                    security_metrics={'quarantine_blocked': True},
                    execution_time=time.time() - start_time
                )
            
            # Fase 2: Execução privilegiada (se aprovada)
            if (quarantine_result.confidence_score >= self.security_config['min_safety_score']):
                privileged_result = await self._privileged_phase(
                    quarantine_result, analysis_task, context
                )
                
                self.security_metrics['privileged_executions'] += 1
                overall_result = OperationResult.SUCCESS
            else:
                privileged_result = None
                overall_result = OperationResult.BLOCKED
                
                montar_log(
                    f"⚠️ Análise bloqueada: score {quarantine_result.confidence_score} < {self.security_config['min_safety_score']}",
                    "WARNING"
                )
            
            # Calcular métricas de segurança
            security_metrics = self._calculate_security_metrics(
                quarantine_result, privileged_result
            )
            
            execution_time = time.time() - start_time
            self.security_metrics['average_processing_time'] = (
                (self.security_metrics['average_processing_time'] * 
                 (self.security_metrics['total_operations'] - 1) + execution_time) /
                self.security_metrics['total_operations']
            )
            
            result = DualLLMResult(
                operation_id=operation_id,
                quarantine_result=quarantine_result,
                privileged_result=privileged_result,
                overall_result=overall_result,
                security_metrics=security_metrics,
                execution_time=execution_time
            )
            
            # Log da operação
            self.operation_log.append({
                'operation_id': operation_id,
                'timestamp': datetime.now(),
                'trust_level': trust_level.value,
                'result': overall_result.value,
                'processing_time': execution_time
            })
            
            montar_log(
                f"✅ Análise Dual LLM concluída: {overall_result.value} ({execution_time:.2f}s)",
                "INFO"
            )
            
            return result
            
        except Exception as e:
            self.security_metrics['security_violations'] += 1
            
            montar_log(f"❌ Erro na análise Dual LLM: {e}", "ERROR")
            
            return DualLLMResult(
                operation_id=operation_id,
                quarantine_result=QuarantineResult(
                    analysis=f"Error: {str(e)}",
                    confidence_score=0.0,
                    safety_assessment={'safe': False, 'error': str(e)},
                    processing_time=time.time() - start_time,
                    is_safe=False
                ),
                privileged_result=None,
                overall_result=OperationResult.ERROR,
                security_metrics={'error': str(e)},
                execution_time=time.time() - start_time
            )
    
    async def _quarantine_phase(
        self,
        user_input: str,
        analysis_task: str,
        context: Dict
    ) -> QuarantineResult:
        """Executa fase de quarentena"""
        
        montar_log("🔒 Fase 1: Processamento em quarentena", "INFO")
        
        # Combinar input do usuário com tarefa de análise
        quarantine_prompt = f"""
Tarefa de análise: {analysis_task}

Dados do usuário para análise:
{user_input}

Analise os dados fornecidos de forma segura, sem executar nenhuma ação.
Forneça apenas análise e recomendações.
"""
        
        # Processar em quarentena
        quarantine_response = await self.quarantine_llm.process(
            quarantine_prompt, context
        )
        
        if not quarantine_response['success']:
            return QuarantineResult(
                analysis=f"Quarantine failed: {quarantine_response['error']}",
                confidence_score=0.0,
                safety_assessment=quarantine_response.get('safety_assessment', {}),
                processing_time=quarantine_response.get('processing_time', 0.0),
                is_safe=False,
                recommendations=["Review input for security issues"]
            )
        
        return quarantine_response['result']
    
    async def _privileged_phase(
        self,
        quarantine_result: QuarantineResult,
        analysis_task: str,
        context: Dict
    ) -> Dict:
        """Executa fase privilegiada"""
        
        montar_log("🔓 Fase 2: Execução privilegiada", "INFO")
        
        # Criar prompt para LLM privilegiado baseado na análise da quarentena
        privileged_prompt = f"""
Análise da quarentena aprovada: {quarantine_result.analysis}

Recomendações: {'; '.join(quarantine_result.recommendations)}

Tarefa: {analysis_task}

Execute as ações necessárias com base na análise aprovada.
"""
        
        # Processar com LLM privilegiado
        privileged_response = await self.privileged_llm.process(
            privileged_prompt, context
        )
        
        return privileged_response
    
    def _calculate_security_metrics(
        self,
        quarantine_result: QuarantineResult,
        privileged_result: Optional[Dict]
    ) -> Dict:
        """Calcula métricas de segurança da operação"""
        
        metrics = {
            'quarantine_safety_score': quarantine_result.confidence_score,
            'quarantine_approved': quarantine_result.is_safe,
            'privileged_executed': privileged_result is not None,
            'tools_used': [],
            'security_level': 'high'
        }
        
        if privileged_result:
            metrics['tools_used'] = privileged_result.get('tools_used', [])
            metrics['privileged_success'] = privileged_result.get('success', False)
        
        # Determinar nível de segurança baseado nos resultados
        if not quarantine_result.is_safe:
            metrics['security_level'] = 'blocked'
        elif quarantine_result.confidence_score < 0.5:
            metrics['security_level'] = 'low'
        elif quarantine_result.confidence_score < 0.8:
            metrics['security_level'] = 'medium'
        else:
            metrics['security_level'] = 'high'
        
        return metrics
    
    def _generate_operation_id(self) -> str:
        """Gera ID único para operação"""
        timestamp = str(int(time.time() * 1000))
        thread_id = str(threading.current_thread().ident)
        return f"dual-{hashlib.sha256(f'{timestamp}:{thread_id}'.encode()).hexdigest()[:12]}"
    
    def add_privileged_tool(self, name: str, tool_func: Callable):
        """Adiciona ferramenta ao LLM privilegiado"""
        self.privileged_llm.add_tool(name, tool_func)
        montar_log(f"🔧 Ferramenta {name} adicionada ao padrão Dual LLM", "INFO")
    
    def configure_security(self, config_updates: Dict):
        """Atualiza configurações de segurança"""
        self.security_config.update(config_updates)
        montar_log("🔒 Configurações de segurança atualizadas", "INFO")
    
    def get_security_status(self) -> Dict:
        """Retorna status de segurança do sistema"""
        
        success_rate = 0.0
        if self.security_metrics['total_operations'] > 0:
            success_rate = (
                self.security_metrics['privileged_executions'] /
                self.security_metrics['total_operations']
            )
        
        block_rate = 0.0
        if self.security_metrics['total_operations'] > 0:
            block_rate = (
                self.security_metrics['quarantine_blocks'] /
                self.security_metrics['total_operations']
            )
        
        return {
            'metrics': self.security_metrics.copy(),
            'success_rate': success_rate,
            'block_rate': block_rate,
            'security_config': self.security_config.copy(),
            'privileged_capabilities': self.privileged_llm.get_capabilities(),
            'quarantine_capabilities': self.quarantine_llm.get_capabilities(),
            'recent_operations': len([
                op for op in self.operation_log[-100:]
                if (datetime.now() - op['timestamp']).total_seconds() < 3600
            ])
        }
    
    def optimize_security_parameters(self) -> Dict:
        """Otimiza parâmetros de segurança baseado no histórico"""
        
        optimizations = {
            'parameters_adjusted': 0,
            'recommendations': []
        }
        
        # Analisar taxa de bloqueio
        if self.security_metrics['total_operations'] > 100:
            block_rate = (
                self.security_metrics['quarantine_blocks'] /
                self.security_metrics['total_operations']
            )
            
            if block_rate > 0.5:
                # Taxa de bloqueio muito alta
                old_threshold = self.security_config['min_safety_score']
                self.security_config['min_safety_score'] = max(0.5, old_threshold - 0.1)
                optimizations['parameters_adjusted'] += 1
                optimizations['recommendations'].append(
                    f"Reduced safety threshold from {old_threshold} to {self.security_config['min_safety_score']}"
                )
            
            elif block_rate < 0.1:
                # Taxa de bloqueio muito baixa
                old_threshold = self.security_config['min_safety_score']
                self.security_config['min_safety_score'] = min(0.9, old_threshold + 0.1)
                optimizations['parameters_adjusted'] += 1
                optimizations['recommendations'].append(
                    f"Increased safety threshold from {old_threshold} to {self.security_config['min_safety_score']}"
                )
        
        # Analisar tempo de processamento
        if self.security_metrics['average_processing_time'] > 30:
            optimizations['recommendations'].append(
                "Consider optimizing processing pipeline for better performance"
            )
        
        return optimizations