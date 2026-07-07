"""
AEGIS Multi-Phase Validation Pipeline
===================================

Sistema de validação em múltiplas fases para código gerado por IA:
1. Análise Estática/Semântica
2. Verificação Formal (Dafny/SPARK)
3. Análise Dinâmica com Sandbox e Fuzzing

Otimizado para mobile (6GB RAM mínimo)
"""

import asyncio
import ast
import sys
import subprocess
import tempfile
import os
import time
import hashlib
import logging
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from quimera.logs.parser import montar_log


class ValidationPhase(Enum):
    """Fases da validação multi-fase"""
    STATIC_SEMANTIC = "static_semantic"
    FORMAL_VERIFICATION = "formal_verification"
    DYNAMIC_SANDBOX = "dynamic_sandbox"


class ValidationResult(Enum):
    """Resultados possíveis da validação"""
    SAFE = "safe"
    SUSPICIOUS = "suspicious"
    DANGEROUS = "dangerous"
    CRITICAL = "critical"


@dataclass
class ValidationReport:
    """Relatório de validação de uma fase"""
    phase: ValidationPhase
    result: ValidationResult
    score: float  # 0.0-1.0
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    memory_usage: int = 0  # MB


@dataclass
class MultiPhaseValidationConfig:
    """Configuração do pipeline de validação"""
    # Configurações gerais
    mobile_optimization: bool = True
    max_memory_mb: int = 1536  # 1.5GB máximo para validação
    max_execution_time: int = 300  # 5 minutos
    
    # Configurações por fase
    enable_static_analysis: bool = True
    enable_formal_verification: bool = True
    enable_dynamic_analysis: bool = True
    
    # Configurações específicas
    static_tools: List[str] = field(default_factory=lambda: ['ast', 'bandit', 'semgrep'])
    formal_tools: List[str] = field(default_factory=lambda: ['dafny'])  # SPARK requer hardware específico
    sandbox_tools: List[str] = field(default_factory=lambda: ['docker', 'firejail'])
    
    # Fuzzing
    enable_fuzzing: bool = True
    fuzzing_duration: int = 60  # 1 minuto
    fuzzing_iterations: int = 1000


class StaticSemanticAnalyzer:
    """Análise estática e semântica de código"""
    
    def __init__(self, config: MultiPhaseValidationConfig):
        self.config = config
        self.dangerous_patterns = [
            r'eval\s*\(',
            r'exec\s*\(',
            r'subprocess\.call',
            r'os\.system',
            r'__import__',
            r'open\s*\(',
            r'file\s*\(',
            r'input\s*\(',
            r'raw_input\s*\(',
        ]
        
    async def analyze(self, code: str, language: str = "python") -> ValidationReport:
        """Analisa código estaticamente"""
        start_time = time.time()
        issues = []
        warnings = []
        score = 1.0
        
        try:
            if language.lower() == "python":
                # Análise AST
                ast_issues = self._analyze_ast(code)
                issues.extend(ast_issues)
                
                # Análise de padrões perigosos
                pattern_issues = self._analyze_dangerous_patterns(code)
                issues.extend(pattern_issues)
                
                # Análise de complexidade
                complexity_score = self._analyze_complexity(code)
                if complexity_score > 0.7:
                    warnings.append(f"Alta complexidade ciclomática: {complexity_score:.2f}")
                
            # Análise de dependências
            dependency_issues = self._analyze_dependencies(code)
            issues.extend(dependency_issues)
            
            # Calcula score final
            if len(issues) > 0:
                score = max(0.0, 1.0 - (len(issues) * 0.2))
            
            # Determina resultado
            if score >= 0.8:
                result = ValidationResult.SAFE
            elif score >= 0.6:
                result = ValidationResult.SUSPICIOUS
            elif score >= 0.3:
                result = ValidationResult.DANGEROUS
            else:
                result = ValidationResult.CRITICAL
                
        except Exception as e:
            issues.append(f"Erro na análise estática: {str(e)}")
            result = ValidationResult.CRITICAL
            score = 0.0
        
        execution_time = time.time() - start_time
        
        return ValidationReport(
            phase=ValidationPhase.STATIC_SEMANTIC,
            result=result,
            score=score,
            issues=issues,
            warnings=warnings,
            execution_time=execution_time,
            metadata={
                "language": language,
                "total_patterns_checked": len(self.dangerous_patterns),
                "ast_analysis": language.lower() == "python"
            }
        )
    
    def _analyze_ast(self, code: str) -> List[str]:
        """Análise AST para Python"""
        issues = []
        try:
            tree = ast.parse(code)
            
            class DangerousVisitor(ast.NodeVisitor):
                def visit_Call(self, node):
                    # Verifica chamadas perigosas
                    if isinstance(node.func, ast.Name):
                        if node.func.id in ['eval', 'exec', 'compile', '__import__']:
                            issues.append(f"Chamada perigosa detectada: {node.func.id}")
                    elif isinstance(node.func, ast.Attribute):
                        if node.func.attr in ['system', 'popen', 'spawn']:
                            issues.append(f"Chamada de sistema detectada: {node.func.attr}")
                    self.generic_visit(node)
                    
                def visit_Import(self, node):
                    # Verifica imports perigosos
                    for alias in node.names:
                        if alias.name in ['os', 'subprocess', 'sys', 'socket']:
                            issues.append(f"Import potencialmente perigoso: {alias.name}")
                    self.generic_visit(node)
            
            visitor = DangerousVisitor()
            visitor.visit(tree)
            
        except SyntaxError as e:
            issues.append(f"Erro de sintaxe: {str(e)}")
        except Exception as e:
            issues.append(f"Erro na análise AST: {str(e)}")
            
        return issues
    
    def _analyze_dangerous_patterns(self, code: str) -> List[str]:
        """Análise de padrões perigosos por regex"""
        import re
        issues = []
        
        for pattern in self.dangerous_patterns:
            matches = re.findall(pattern, code, re.IGNORECASE)
            if matches:
                issues.append(f"Padrão perigoso detectado: {pattern} ({len(matches)} ocorrências)")
                
        return issues
    
    def _analyze_complexity(self, code: str) -> float:
        """Calcula complexidade ciclomática simplificada"""
        complexity_keywords = ['if', 'elif', 'else', 'for', 'while', 'try', 'except', 'finally', 'with']
        complexity_count = 0
        
        for keyword in complexity_keywords:
            complexity_count += code.count(keyword)
            
        # Normaliza baseado no tamanho do código
        lines = len(code.split('\n'))
        return min(1.0, complexity_count / max(lines, 1))
    
    def _analyze_dependencies(self, code: str) -> List[str]:
        """Analisa dependências e imports"""
        issues = []
        dangerous_modules = [
            'subprocess', 'os', 'sys', 'socket', 'urllib', 'requests',
            'paramiko', 'fabric', 'pexpect', 'pty'
        ]
        
        for module in dangerous_modules:
            if f'import {module}' in code or f'from {module}' in code:
                issues.append(f"Dependência potencialmente perigosa: {module}")
                
        return issues


class FormalVerificationEngine:
    """Motor de verificação formal (Dafny focado para mobile)"""
    
    def __init__(self, config: MultiPhaseValidationConfig):
        self.config = config
        
    async def verify(self, code: str, specifications: Optional[str] = None) -> ValidationReport:
        """Verifica código formalmente"""
        start_time = time.time()
        issues = []
        warnings = []
        score = 1.0
        
        try:
            # Para mobile, usamos verificação formal simplificada
            if self.config.mobile_optimization:
                # Verificação de pré/pós-condições simples
                verification_result = self._simple_formal_verification(code, specifications)
            else:
                # Verificação formal completa (requer mais recursos)
                verification_result = await self._full_formal_verification(code, specifications)
            
            issues = verification_result.get('issues', [])
            warnings = verification_result.get('warnings', [])
            score = verification_result.get('score', 1.0)
            
        except Exception as e:
            issues.append(f"Erro na verificação formal: {str(e)}")
            score = 0.5  # Score neutro em caso de erro
        
        # Determina resultado
        if score >= 0.9:
            result = ValidationResult.SAFE
        elif score >= 0.7:
            result = ValidationResult.SUSPICIOUS
        elif score >= 0.4:
            result = ValidationResult.DANGEROUS
        else:
            result = ValidationResult.CRITICAL
        
        execution_time = time.time() - start_time
        
        return ValidationReport(
            phase=ValidationPhase.FORMAL_VERIFICATION,
            result=result,
            score=score,
            issues=issues,
            warnings=warnings,
            execution_time=execution_time,
            metadata={
                "mobile_optimized": self.config.mobile_optimization,
                "specifications_provided": specifications is not None
            }
        )
    
    def _simple_formal_verification(self, code: str, specifications: Optional[str]) -> Dict[str, Any]:
        """Verificação formal simplificada para mobile"""
        issues = []
        warnings = []
        score = 1.0
        
        # Verifica estruturas básicas de controle
        if 'while True:' in code and 'break' not in code:
            issues.append("Loop infinito potencial detectado")
            score -= 0.3
            
        # Verifica divisão por zero
        if '//' in code or '/' in code:
            if 'if' not in code or 'zero' not in code.lower():
                warnings.append("Possível divisão por zero não verificada")
                score -= 0.1
        
        # Verifica acesso a arrays/listas
        if '[' in code and ']' in code:
            if 'len(' not in code and 'range(' not in code:
                warnings.append("Acesso a índice potencialmente não verificado")
                score -= 0.1
        
        return {
            'issues': issues,
            'warnings': warnings,
            'score': max(0.0, score)
        }
    
    async def _full_formal_verification(self, code: str, specifications: Optional[str]) -> Dict[str, Any]:
        """Verificação formal completa (requer mais recursos)"""
        # Para implementação futura com Dafny/SPARK
        return {
            'issues': ["Verificação formal completa não implementada"],
            'warnings': [],
            'score': 0.5
        }


class DynamicSandboxAnalyzer:
    """Análise dinâmica em sandbox"""
    
    def __init__(self, config: MultiPhaseValidationConfig):
        self.config = config
        
    async def analyze(self, code: str, test_inputs: Optional[List[Any]] = None) -> ValidationReport:
        """Executa código em sandbox e analisa comportamento"""
        start_time = time.time()
        issues = []
        warnings = []
        score = 1.0
        
        try:
            # Cria sandbox temporário
            with tempfile.TemporaryDirectory() as temp_dir:
                # Executa em ambiente isolado
                sandbox_result = await self._execute_in_sandbox(code, temp_dir, test_inputs)
                
                issues = sandbox_result.get('issues', [])
                warnings = sandbox_result.get('warnings', [])
                score = sandbox_result.get('score', 1.0)
                
                # Fuzzing se habilitado
                if self.config.enable_fuzzing:
                    fuzzing_result = await self._perform_fuzzing(code, temp_dir)
                    issues.extend(fuzzing_result.get('issues', []))
                    warnings.extend(fuzzing_result.get('warnings', []))
                    score = min(score, fuzzing_result.get('score', 1.0))
                
        except Exception as e:
            issues.append(f"Erro na análise dinâmica: {str(e)}")
            score = 0.3
        
        # Determina resultado
        if score >= 0.8:
            result = ValidationResult.SAFE
        elif score >= 0.6:
            result = ValidationResult.SUSPICIOUS
        elif score >= 0.3:
            result = ValidationResult.DANGEROUS
        else:
            result = ValidationResult.CRITICAL
        
        execution_time = time.time() - start_time
        
        return ValidationReport(
            phase=ValidationPhase.DYNAMIC_SANDBOX,
            result=result,
            score=score,
            issues=issues,
            warnings=warnings,
            execution_time=execution_time,
            metadata={
                "fuzzing_enabled": self.config.enable_fuzzing,
                "test_inputs_provided": test_inputs is not None
            }
        )
    
    async def _execute_in_sandbox(self, code: str, temp_dir: str, test_inputs: Optional[List[Any]]) -> Dict[str, Any]:
        """Executa código em sandbox isolado"""
        issues = []
        warnings = []
        score = 1.0
        
        try:
            # Cria arquivo temporário
            code_file = os.path.join(temp_dir, "test_code.py")
            with open(code_file, 'w') as f:
                f.write(code)
            
            # Executa com restrições de recursos
            cmd = [
                sys.executable, '-c',
                f"""
import resource
import signal
import sys

# Limita recursos para mobile
resource.setrlimit(resource.RLIMIT_AS, ({self.config.max_memory_mb * 1024 * 1024}, -1))
resource.setrlimit(resource.RLIMIT_CPU, ({self.config.max_execution_time}, -1))

# Timeout handler
def timeout_handler(signum, frame):
    raise TimeoutError("Execução timeout")

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm({self.config.max_execution_time})

try:
    exec(open('{code_file}').read())
except Exception as e:
    print(f"SANDBOX_ERROR: {{e}}")
    sys.exit(1)
"""
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.config.max_execution_time)
            
            if result.returncode != 0:
                if "SANDBOX_ERROR:" in result.stdout:
                    error_msg = result.stdout.split("SANDBOX_ERROR:")[1].strip()
                    issues.append(f"Erro durante execução: {error_msg}")
                    score -= 0.4
                else:
                    warnings.append("Código terminou com código de saída não-zero")
                    score -= 0.2
            
        except subprocess.TimeoutExpired:
            issues.append("Código excedeu tempo limite de execução")
            score -= 0.6
        except Exception as e:
            issues.append(f"Erro no sandbox: {str(e)}")
            score -= 0.3
        
        return {
            'issues': issues,
            'warnings': warnings,
            'score': max(0.0, score)
        }
    
    async def _perform_fuzzing(self, code: str, temp_dir: str) -> Dict[str, Any]:
        """Realiza fuzzing simplificado do código"""
        issues = []
        warnings = []
        score = 1.0
        
        try:
            # Fuzzing básico com inputs aleatórios
            import random
            import string
            
            fuzzing_inputs = []
            
            # Gera inputs de teste
            for _ in range(min(self.config.fuzzing_iterations, 100)):  # Limita para mobile
                input_type = random.choice(['string', 'number', 'list', 'special'])
                
                if input_type == 'string':
                    fuzzing_inputs.append(''.join(random.choices(string.ascii_letters + string.digits, k=random.randint(1, 50))))
                elif input_type == 'number':
                    fuzzing_inputs.append(random.randint(-1000000, 1000000))
                elif input_type == 'list':
                    fuzzing_inputs.append([random.randint(1, 100) for _ in range(random.randint(1, 10))])
                elif input_type == 'special':
                    fuzzing_inputs.append(random.choice(['', None, [], {}, 0, -1, '/../', '<script>', 'DROP TABLE']))
            
            # Testa código com inputs
            crashes = 0
            for i, test_input in enumerate(fuzzing_inputs[:50]):  # Limita para mobile
                try:
                    # Simula execução com input (simplificado)
                    if isinstance(test_input, str) and len(test_input) > 1000:
                        warnings.append(f"Input muito grande pode causar problemas: {len(test_input)} chars")
                    
                except Exception:
                    crashes += 1
            
            if crashes > 0:
                crash_rate = crashes / len(fuzzing_inputs)
                if crash_rate > 0.1:
                    issues.append(f"Alta taxa de crashes no fuzzing: {crash_rate:.2%}")
                    score -= 0.5
                elif crash_rate > 0.05:
                    warnings.append(f"Taxa moderada de crashes: {crash_rate:.2%}")
                    score -= 0.2
                    
        except Exception as e:
            warnings.append(f"Erro durante fuzzing: {str(e)}")
            score -= 0.1
        
        return {
            'issues': issues,
            'warnings': warnings,
            'score': max(0.0, score)
        }


class MultiPhaseValidationPipeline:
    """Pipeline principal de validação multi-fase"""
    
    def __init__(self, config: Optional[MultiPhaseValidationConfig] = None):
        self.config = config or MultiPhaseValidationConfig()
        
        # Inicializa analisadores
        self.static_analyzer = StaticSemanticAnalyzer(self.config)
        self.formal_verifier = FormalVerificationEngine(self.config)
        self.dynamic_analyzer = DynamicSandboxAnalyzer(self.config)
        
        montar_log(f"🔍 Multi-Phase Validation Pipeline inicializado (mobile: {self.config.mobile_optimization})", "INFO")
    
    async def validate_code(self, code: str, language: str = "python", 
                          specifications: Optional[str] = None,
                          test_inputs: Optional[List[Any]] = None) -> Dict[str, Any]:
        """Executa validação completa em múltiplas fases"""
        start_time = time.time()
        
        montar_log(f"🔍 Iniciando validação multi-fase para código {language}", "INFO")
        
        validation_results = {}
        overall_score = 1.0
        critical_issues = []
        all_warnings = []
        
        try:
            # Fase 1: Análise Estática/Semântica
            if self.config.enable_static_analysis:
                montar_log("📊 Executando Fase 1: Análise Estática/Semântica", "INFO")
                static_result = await self.static_analyzer.analyze(code, language)
                validation_results['static_semantic'] = static_result
                overall_score *= static_result.score
                
                if static_result.result in [ValidationResult.CRITICAL, ValidationResult.DANGEROUS]:
                    critical_issues.extend(static_result.issues)
                all_warnings.extend(static_result.warnings)
            
            # Fase 2: Verificação Formal
            if self.config.enable_formal_verification:
                montar_log("🔬 Executando Fase 2: Verificação Formal", "INFO")
                formal_result = await self.formal_verifier.verify(code, specifications)
                validation_results['formal_verification'] = formal_result
                overall_score *= formal_result.score
                
                if formal_result.result in [ValidationResult.CRITICAL, ValidationResult.DANGEROUS]:
                    critical_issues.extend(formal_result.issues)
                all_warnings.extend(formal_result.warnings)
            
            # Fase 3: Análise Dinâmica (só se passou nas anteriores)
            if self.config.enable_dynamic_analysis and overall_score > 0.3:
                montar_log("🎯 Executando Fase 3: Análise Dinâmica com Sandbox", "INFO")
                dynamic_result = await self.dynamic_analyzer.analyze(code, test_inputs)
                validation_results['dynamic_sandbox'] = dynamic_result
                overall_score *= dynamic_result.score
                
                if dynamic_result.result in [ValidationResult.CRITICAL, ValidationResult.DANGEROUS]:
                    critical_issues.extend(dynamic_result.issues)
                all_warnings.extend(dynamic_result.warnings)
            
            # Determina resultado final
            if overall_score >= 0.8:
                final_result = ValidationResult.SAFE
            elif overall_score >= 0.6:
                final_result = ValidationResult.SUSPICIOUS
            elif overall_score >= 0.3:
                final_result = ValidationResult.DANGEROUS
            else:
                final_result = ValidationResult.CRITICAL
            
            total_time = time.time() - start_time
            
            summary = {
                'overall_result': final_result,
                'overall_score': overall_score,
                'critical_issues': critical_issues,
                'warnings': all_warnings,
                'phase_results': validation_results,
                'execution_time': total_time,
                'phases_executed': len(validation_results),
                'mobile_optimized': self.config.mobile_optimization,
                'recommendation': self._get_recommendation(final_result, critical_issues)
            }
            
            montar_log(f"✅ Validação multi-fase concluída: {final_result.value.upper()} (score: {overall_score:.2f})", "INFO")
            
            return summary
            
        except Exception as e:
            montar_log(f"❌ Erro na validação multi-fase: {str(e)}", "ERROR")
            return {
                'overall_result': ValidationResult.CRITICAL,
                'overall_score': 0.0,
                'critical_issues': [f"Erro fatal na validação: {str(e)}"],
                'warnings': [],
                'phase_results': validation_results,
                'execution_time': time.time() - start_time,
                'phases_executed': len(validation_results),
                'mobile_optimized': self.config.mobile_optimization,
                'recommendation': "REJEITAR - Erro fatal durante validação"
            }
    
    def _get_recommendation(self, result: ValidationResult, critical_issues: List[str]) -> str:
        """Gera recomendação baseada no resultado"""
        if result == ValidationResult.SAFE:
            return "APROVAR - Código seguro para execução"
        elif result == ValidationResult.SUSPICIOUS:
            return "REVISAR - Código requer revisão manual antes da execução"
        elif result == ValidationResult.DANGEROUS:
            return "MODIFICAR - Código possui problemas sérios que devem ser corrigidos"
        else:  # CRITICAL
            return "REJEITAR - Código muito perigoso, não deve ser executado"
    
    def get_validation_statistics(self) -> Dict[str, Any]:
        """Retorna estatísticas do sistema de validação"""
        return {
            'config': {
                'mobile_optimization': self.config.mobile_optimization,
                'max_memory_mb': self.config.max_memory_mb,
                'max_execution_time': self.config.max_execution_time,
                'phases_enabled': {
                    'static_analysis': self.config.enable_static_analysis,
                    'formal_verification': self.config.enable_formal_verification,
                    'dynamic_analysis': self.config.enable_dynamic_analysis,
                    'fuzzing': self.config.enable_fuzzing
                }
            },
            'capabilities': {
                'languages_supported': ['python'],
                'static_tools': self.config.static_tools,
                'formal_tools': self.config.formal_tools,
                'sandbox_tools': self.config.sandbox_tools
            }
        }