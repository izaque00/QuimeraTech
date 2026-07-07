"""
AEGIS XAI (Explainable AI) System
===============================

Sistema de explicabilidade para IA do Quimera:
- Explicações de decisões de LLM
- Análise de confiança e incerteza
- Visualização de processo de raciocínio
- Transparência em decisões de segurança

Otimizado para mobile (6GB RAM mínimo)
"""

import json
import time
import re
import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
from collections import defaultdict

from quimera.logs.parser import montar_log


class ExplanationType(Enum):
    """Tipos de explicação"""
    DECISION_TREE = "decision_tree"
    ATTENTION_WEIGHTS = "attention_weights"
    FEATURE_IMPORTANCE = "feature_importance"
    STEP_BY_STEP = "step_by_step"
    CONFIDENCE_ANALYSIS = "confidence_analysis"
    RISK_ASSESSMENT = "risk_assessment"


class ConfidenceLevel(Enum):
    """Níveis de confiança"""
    VERY_LOW = "very_low"      # 0-20%
    LOW = "low"                # 20-40%
    MEDIUM = "medium"          # 40-70%
    HIGH = "high"              # 70-90%
    VERY_HIGH = "very_high"    # 90-100%


@dataclass
class ExplanationContext:
    """Contexto para geração de explicação"""
    component: str
    action: str
    input_data: Any
    output_data: Any
    model_used: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ConfidenceScore:
    """Score de confiança com detalhamento"""
    overall_confidence: float  # 0.0-1.0
    level: ConfidenceLevel
    factors: Dict[str, float] = field(default_factory=dict)
    uncertainties: List[str] = field(default_factory=list)
    reasoning: str = ""


@dataclass
class DecisionExplanation:
    """Explicação de uma decisão de IA"""
    explanation_id: str
    context: ExplanationContext
    explanation_type: ExplanationType
    confidence: ConfidenceScore
    main_reasoning: str
    step_by_step: List[str] = field(default_factory=list)
    key_factors: Dict[str, float] = field(default_factory=dict)
    alternatives_considered: List[Dict[str, Any]] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário"""
        return {
            'explanation_id': self.explanation_id,
            'context': {
                'component': self.context.component,
                'action': self.context.action,
                'model_used': self.context.model_used,
                'timestamp': self.context.timestamp.isoformat(),
                'parameters': self.context.parameters
            },
            'explanation_type': self.explanation_type.value,
            'confidence': {
                'overall_confidence': self.confidence.overall_confidence,
                'level': self.confidence.level.value,
                'factors': self.confidence.factors,
                'uncertainties': self.confidence.uncertainties,
                'reasoning': self.confidence.reasoning
            },
            'main_reasoning': self.main_reasoning,
            'step_by_step': self.step_by_step,
            'key_factors': self.key_factors,
            'alternatives_considered': self.alternatives_considered,
            'risk_factors': self.risk_factors,
            'recommendations': self.recommendations,
            'metadata': self.metadata
        }


class LLMDecisionAnalyzer:
    """Analisador de decisões de LLM"""
    
    def __init__(self, mobile_optimized: bool = True):
        self.mobile_optimized = mobile_optimized
        
        # Padrões para detectar raciocínio em respostas LLM
        self.reasoning_patterns = [
            r'because\s+(.+?)[\.\,\n]',
            r'since\s+(.+?)[\.\,\n]',
            r'due to\s+(.+?)[\.\,\n]',
            r'therefore\s+(.+?)[\.\,\n]',
            r'as a result\s+(.+?)[\.\,\n]',
            r'considering\s+(.+?)[\.\,\n]',
            r'given that\s+(.+?)[\.\,\n]'
        ]
        
        # Palavras de confiança
        self.confidence_words = {
            'high': ['definitely', 'certainly', 'clearly', 'obviously', 'undoubtedly'],
            'medium': ['likely', 'probably', 'seems', 'appears', 'suggests'],
            'low': ['might', 'could', 'possibly', 'perhaps', 'maybe', 'uncertain']
        }
    
    def analyze_llm_response(self, prompt: str, response: str, model_name: str) -> Tuple[ConfidenceScore, List[str]]:
        """Analisa resposta de LLM para extrair confiança e raciocínio"""
        
        # Análise de confiança baseada em palavras-chave
        confidence_indicators = self._extract_confidence_indicators(response)
        
        # Extração de raciocínio
        reasoning_steps = self._extract_reasoning_steps(response)
        
        # Análise de incerteza
        uncertainties = self._detect_uncertainties(response)
        
        # Calcula score de confiança
        overall_confidence = self._calculate_confidence_score(confidence_indicators, uncertainties, response)
        
        # Determina nível
        if overall_confidence >= 0.9:
            level = ConfidenceLevel.VERY_HIGH
        elif overall_confidence >= 0.7:
            level = ConfidenceLevel.HIGH
        elif overall_confidence >= 0.4:
            level = ConfidenceLevel.MEDIUM
        elif overall_confidence >= 0.2:
            level = ConfidenceLevel.LOW
        else:
            level = ConfidenceLevel.VERY_LOW
        
        confidence_score = ConfidenceScore(
            overall_confidence=overall_confidence,
            level=level,
            factors=confidence_indicators,
            uncertainties=uncertainties,
            reasoning=f"Análise baseada em {len(reasoning_steps)} passos de raciocínio e {len(confidence_indicators)} indicadores"
        )
        
        return confidence_score, reasoning_steps
    
    def _extract_confidence_indicators(self, text: str) -> Dict[str, float]:
        """Extrai indicadores de confiança do texto"""
        indicators = {}
        text_lower = text.lower()
        
        for level, words in self.confidence_words.items():
            count = sum(text_lower.count(word) for word in words)
            if count > 0:
                indicators[f'{level}_confidence_words'] = count / len(words)
        
        # Análise de estrutura da resposta
        if '?' in text:
            indicators['questions_asked'] = text.count('?') / len(text.split())
        
        if 'but' in text_lower or 'however' in text_lower:
            indicators['contradictions'] = (text_lower.count('but') + text_lower.count('however')) / len(text.split())
        
        return indicators
    
    def _extract_reasoning_steps(self, text: str) -> List[str]:
        """Extrai passos de raciocínio do texto"""
        reasoning_steps = []
        
        # Busca por padrões de raciocínio
        for pattern in self.reasoning_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            reasoning_steps.extend(matches)
        
        # Busca por listas numeradas ou com bullets
        numbered_pattern = r'(\d+[\.\)]\s+.+?)(?=\d+[\.\)]|\n\n|$)'
        numbered_matches = re.findall(numbered_pattern, text, re.DOTALL)
        reasoning_steps.extend([match.strip() for match in numbered_matches])
        
        # Busca por bullets
        bullet_pattern = r'[•\-\*]\s+(.+?)(?=[•\-\*]|\n\n|$)'
        bullet_matches = re.findall(bullet_pattern, text, re.DOTALL)
        reasoning_steps.extend([match.strip() for match in bullet_matches])
        
        return reasoning_steps[:10]  # Limita para mobile
    
    def _detect_uncertainties(self, text: str) -> List[str]:
        """Detecta incertezas no texto"""
        uncertainties = []
        
        uncertainty_patterns = [
            r'(not sure about .+?)[\.\,\n]',
            r'(unclear .+?)[\.\,\n]',
            r'(difficult to determine .+?)[\.\,\n]',
            r'(uncertain .+?)[\.\,\n]',
            r'(ambiguous .+?)[\.\,\n]'
        ]
        
        for pattern in uncertainty_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            uncertainties.extend(matches)
        
        return uncertainties
    
    def _calculate_confidence_score(self, indicators: Dict[str, float], 
                                  uncertainties: List[str], text: str) -> float:
        """Calcula score de confiança baseado em indicadores"""
        
        base_score = 0.5  # Score base
        
        # Ajusta baseado em palavras de confiança
        high_conf = indicators.get('high_confidence_words', 0)
        medium_conf = indicators.get('medium_confidence_words', 0)
        low_conf = indicators.get('low_confidence_words', 0)
        
        base_score += high_conf * 0.3
        base_score += medium_conf * 0.1
        base_score -= low_conf * 0.2
        
        # Penaliza por incertezas
        base_score -= len(uncertainties) * 0.1
        
        # Penaliza por perguntas excessivas
        questions = indicators.get('questions_asked', 0)
        base_score -= questions * 0.3
        
        # Penaliza por contradições
        contradictions = indicators.get('contradictions', 0)
        base_score -= contradictions * 0.2
        
        # Ajusta baseado no comprimento da resposta (respostas muito curtas = menos confiança)
        words = len(text.split())
        if words < 10:
            base_score -= 0.2
        elif words > 100:
            base_score += 0.1
        
        return max(0.0, min(1.0, base_score))


class SecurityDecisionExplainer:
    """Explicador de decisões de segurança"""
    
    def __init__(self):
        self.threat_level_explanations = {
            'SAFE': 'Nenhuma ameaça significativa detectada',
            'SUSPICIOUS': 'Padrões suspeitos que requerem atenção',
            'DANGEROUS': 'Ameaças sérias que precisam ser mitigadas',
            'CRITICAL': 'Ameaças críticas que requerem ação imediata',
            'EMERGENCY': 'Situação de emergência - intervenção urgente necessária'
        }
    
    def explain_security_decision(self, decision_data: Dict[str, Any]) -> DecisionExplanation:
        """Explica decisão de segurança"""
        
        threat_level = decision_data.get('threat_level', 'UNKNOWN')
        detected_threats = decision_data.get('threats', [])
        mitigation_actions = decision_data.get('mitigations', [])
        confidence_score = decision_data.get('confidence', 0.5)
        
        # Análise de confiança
        confidence = ConfidenceScore(
            overall_confidence=confidence_score,
            level=self._get_confidence_level(confidence_score),
            factors={
                'threat_detection_accuracy': confidence_score,
                'pattern_match_strength': decision_data.get('pattern_strength', 0.5),
                'historical_accuracy': decision_data.get('historical_accuracy', 0.8)
            },
            uncertainties=decision_data.get('uncertainties', []),
            reasoning=f"Confiança baseada em {len(detected_threats)} ameaças detectadas"
        )
        
        # Raciocínio principal
        main_reasoning = self.threat_level_explanations.get(threat_level, 'Análise de segurança realizada')
        
        # Passos do raciocínio
        step_by_step = []
        step_by_step.append("1. Análise inicial de padrões de código")
        
        if detected_threats:
            step_by_step.append(f"2. Detectadas {len(detected_threats)} ameaças potenciais")
            for i, threat in enumerate(detected_threats[:3]):  # Limita para mobile
                step_by_step.append(f"   - {threat.get('type', 'Ameaça desconhecida')}: {threat.get('description', '')}")
        
        step_by_step.append(f"3. Classificação de risco como {threat_level}")
        
        if mitigation_actions:
            step_by_step.append("4. Ações de mitigação recomendadas:")
            for action in mitigation_actions[:3]:  # Limita para mobile
                step_by_step.append(f"   - {action}")
        
        # Fatores-chave
        key_factors = {
            'threat_count': len(detected_threats),
            'severity_score': decision_data.get('severity_score', 0),
            'pattern_matches': decision_data.get('pattern_matches', 0),
            'risk_score': decision_data.get('risk_score', 0)
        }
        
        # Fatores de risco
        risk_factors = [f"Ameaça: {threat.get('type', 'Desconhecida')}" for threat in detected_threats]
        
        # Recomendações
        recommendations = []
        if threat_level in ['DANGEROUS', 'CRITICAL', 'EMERGENCY']:
            recommendations.append("Revisar código manualmente antes da execução")
            recommendations.append("Aplicar todas as mitigações sugeridas")
        elif threat_level == 'SUSPICIOUS':
            recommendations.append("Monitorar execução de perto")
            recommendations.append("Considerar testes adicionais")
        else:
            recommendations.append("Código aprovado para uso normal")
        
        context = ExplanationContext(
            component="security_analyzer",
            action="threat_assessment",
            input_data=decision_data.get('input', {}),
            output_data=decision_data.get('output', {}),
            model_used=decision_data.get('model', 'aegis_security')
        )
        
        return DecisionExplanation(
            explanation_id=f"security_{int(time.time())}",
            context=context,
            explanation_type=ExplanationType.RISK_ASSESSMENT,
            confidence=confidence,
            main_reasoning=main_reasoning,
            step_by_step=step_by_step,
            key_factors=key_factors,
            risk_factors=risk_factors,
            recommendations=recommendations,
            metadata={
                'threat_level': threat_level,
                'threats_analyzed': len(detected_threats),
                'mitigations_available': len(mitigation_actions)
            }
        )
    
    def _get_confidence_level(self, score: float) -> ConfidenceLevel:
        """Converte score numérico para nível de confiança"""
        if score >= 0.9:
            return ConfidenceLevel.VERY_HIGH
        elif score >= 0.7:
            return ConfidenceLevel.HIGH
        elif score >= 0.4:
            return ConfidenceLevel.MEDIUM
        elif score >= 0.2:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW


class CodeGenerationExplainer:
    """Explicador de decisões de geração de código"""
    
    def explain_code_generation(self, generation_data: Dict[str, Any]) -> DecisionExplanation:
        """Explica processo de geração de código"""
        
        prompt = generation_data.get('prompt', '')
        generated_code = generation_data.get('code', '')
        model_used = generation_data.get('model', 'unknown')
        parameters = generation_data.get('parameters', {})
        
        # Análise de confiança baseada em parâmetros do modelo
        temperature = parameters.get('temperature', 0.7)
        top_p = parameters.get('top_p', 0.9)
        
        # Confiança inversamente relacionada à temperatura
        confidence_score = max(0.1, 1.0 - temperature)
        
        confidence = ConfidenceScore(
            overall_confidence=confidence_score,
            level=self._get_confidence_level(confidence_score),
            factors={
                'model_temperature': 1.0 - temperature,
                'prompt_clarity': self._assess_prompt_clarity(prompt),
                'output_completeness': self._assess_output_completeness(generated_code)
            },
            reasoning=f"Confiança baseada em temperatura {temperature} e clareza do prompt"
        )
        
        # Raciocínio principal
        main_reasoning = f"Código gerado pelo modelo {model_used} baseado no prompt fornecido"
        
        # Passos do processo
        step_by_step = [
            "1. Análise do prompt de entrada",
            f"2. Tokenização e processamento pelo modelo {model_used}",
            f"3. Geração usando temperatura {temperature}",
            "4. Decodificação e formatação da saída",
            "5. Verificações básicas de sintaxe"
        ]
        
        # Fatores-chave
        key_factors = {
            'prompt_length': len(prompt.split()),
            'code_length': len(generated_code.split('\n')),
            'temperature': temperature,
            'top_p': top_p,
            'model_confidence': confidence_score
        }
        
        # Recomendações
        recommendations = []
        if temperature > 0.8:
            recommendations.append("Alta temperatura pode gerar código mais criativo mas menos previsível")
        if confidence_score < 0.5:
            recommendations.append("Revisar código gerado cuidadosamente")
        if len(prompt.split()) < 10:
            recommendations.append("Prompts mais detalhados tendem a gerar melhores resultados")
        
        context = ExplanationContext(
            component="code_generator",
            action="generate_code",
            input_data={'prompt': prompt[:200]},  # Trunca para mobile
            output_data={'code_preview': generated_code[:200]},
            model_used=model_used,
            parameters=parameters
        )
        
        return DecisionExplanation(
            explanation_id=f"codegen_{int(time.time())}",
            context=context,
            explanation_type=ExplanationType.STEP_BY_STEP,
            confidence=confidence,
            main_reasoning=main_reasoning,
            step_by_step=step_by_step,
            key_factors=key_factors,
            recommendations=recommendations,
            metadata={
                'generation_approach': 'LLM-based',
                'post_processing': 'basic_validation'
            }
        )
    
    def _assess_prompt_clarity(self, prompt: str) -> float:
        """Avalia clareza do prompt"""
        if not prompt:
            return 0.0
        
        words = prompt.split()
        if len(words) < 5:
            return 0.3
        elif len(words) > 100:
            return 0.8
        else:
            return 0.6
    
    def _assess_output_completeness(self, code: str) -> float:
        """Avalia completude do código gerado"""
        if not code:
            return 0.0
        
        lines = code.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        
        if len(non_empty_lines) < 3:
            return 0.4
        elif len(non_empty_lines) > 50:
            return 0.9
        else:
            return 0.7
    
    def _get_confidence_level(self, score: float) -> ConfidenceLevel:
        """Converte score numérico para nível de confiança"""
        if score >= 0.9:
            return ConfidenceLevel.VERY_HIGH
        elif score >= 0.7:
            return ConfidenceLevel.HIGH
        elif score >= 0.4:
            return ConfidenceLevel.MEDIUM
        elif score >= 0.2:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW


@dataclass
class XAIConfig:
    """Configuração do sistema XAI"""
    mobile_optimization: bool = True
    max_explanations_memory: int = 100  # Máximo para mobile
    enable_llm_analysis: bool = True
    enable_security_explanations: bool = True
    enable_code_explanations: bool = True
    detailed_reasoning: bool = True
    confidence_threshold: float = 0.3  # Mínimo para gerar explicação


class XAIExplainabilitySystem:
    """Sistema principal de explicabilidade (XAI)"""
    
    def __init__(self, config: Optional[XAIConfig] = None):
        self.config = config or XAIConfig()
        
        # Componentes especializados
        self.llm_analyzer = LLMDecisionAnalyzer(self.config.mobile_optimization)
        self.security_explainer = SecurityDecisionExplainer()
        self.code_explainer = CodeGenerationExplainer()
        
        # Armazenamento de explicações (limitado para mobile)
        self.explanations: Dict[str, DecisionExplanation] = {}
        
        # Estatísticas
        self.stats = {
            'explanations_generated': 0,
            'llm_analyses_performed': 0,
            'security_decisions_explained': 0,
            'code_generations_explained': 0,
            'average_confidence': 0.0
        }
        
        montar_log(f"🧠 XAI Explainability System inicializado (mobile: {self.config.mobile_optimization})", "INFO")
    
    async def explain_llm_decision(self, prompt: str, response: str, 
                                 model_name: str, context: Dict[str, Any] = None) -> DecisionExplanation:
        """Gera explicação para decisão de LLM"""
        
        if not self.config.enable_llm_analysis:
            return None
        
        # Analisa resposta do LLM
        confidence, reasoning_steps = self.llm_analyzer.analyze_llm_response(prompt, response, model_name)
        
        # Cria contexto
        explanation_context = ExplanationContext(
            component="llm_processor",
            action="generate_response",
            input_data={'prompt': prompt[:200]},  # Trunca para mobile
            output_data={'response': response[:200]},
            model_used=model_name,
            parameters=context or {}
        )
        
        # Gera explicação
        explanation = DecisionExplanation(
            explanation_id=f"llm_{int(time.time())}",
            context=explanation_context,
            explanation_type=ExplanationType.STEP_BY_STEP,
            confidence=confidence,
            main_reasoning=f"Resposta gerada pelo modelo {model_name} com confiança {confidence.level.value}",
            step_by_step=reasoning_steps,
            key_factors=confidence.factors,
            recommendations=self._generate_llm_recommendations(confidence, response),
            metadata={
                'response_length': len(response),
                'reasoning_steps_found': len(reasoning_steps),
                'confidence_level': confidence.level.value
            }
        )
        
        # Armazena explicação
        self._store_explanation(explanation)
        
        self.stats['llm_analyses_performed'] += 1
        self.stats['explanations_generated'] += 1
        
        return explanation
    
    async def explain_security_decision(self, decision_data: Dict[str, Any]) -> DecisionExplanation:
        """Gera explicação para decisão de segurança"""
        
        if not self.config.enable_security_explanations:
            return None
        
        explanation = self.security_explainer.explain_security_decision(decision_data)
        
        # Armazena explicação
        self._store_explanation(explanation)
        
        self.stats['security_decisions_explained'] += 1
        self.stats['explanations_generated'] += 1
        
        return explanation
    
    async def explain_code_generation(self, generation_data: Dict[str, Any]) -> DecisionExplanation:
        """Gera explicação para geração de código"""
        
        if not self.config.enable_code_explanations:
            return None
        
        explanation = self.code_explainer.explain_code_generation(generation_data)
        
        # Armazena explicação
        self._store_explanation(explanation)
        
        self.stats['code_generations_explained'] += 1
        self.stats['explanations_generated'] += 1
        
        return explanation
    
    def _store_explanation(self, explanation: DecisionExplanation):
        """Armazena explicação com limite para mobile"""
        
        # Limite de memória para mobile
        if len(self.explanations) >= self.config.max_explanations_memory:
            # Remove explicação mais antiga
            oldest_id = min(self.explanations.keys(), 
                          key=lambda x: self.explanations[x].context.timestamp)
            del self.explanations[oldest_id]
        
        self.explanations[explanation.explanation_id] = explanation
        
        # Atualiza estatísticas
        confidence_sum = sum(exp.confidence.overall_confidence for exp in self.explanations.values())
        self.stats['average_confidence'] = confidence_sum / len(self.explanations)
    
    def _generate_llm_recommendations(self, confidence: ConfidenceScore, response: str) -> List[str]:
        """Gera recomendações baseadas na análise de confiança"""
        recommendations = []
        
        if confidence.level == ConfidenceLevel.VERY_LOW:
            recommendations.append("Revisar resposta cuidadosamente - confiança muito baixa")
            recommendations.append("Considerar reformular o prompt")
        elif confidence.level == ConfidenceLevel.LOW:
            recommendations.append("Validar resposta com fontes adicionais")
        elif confidence.level == ConfidenceLevel.MEDIUM:
            recommendations.append("Resposta aceitável - verificação recomendada")
        else:
            recommendations.append("Resposta com alta confiança - pode ser usada normalmente")
        
        if len(confidence.uncertainties) > 0:
            recommendations.append("Atenção às incertezas identificadas na resposta")
        
        if len(response.split()) < 20:
            recommendations.append("Resposta muito curta - considerar prompt mais específico")
        
        return recommendations
    
    def get_explanation(self, explanation_id: str) -> Optional[DecisionExplanation]:
        """Obtém explicação por ID"""
        return self.explanations.get(explanation_id)
    
    def get_recent_explanations(self, limit: int = 10) -> List[DecisionExplanation]:
        """Obtém explicações recentes"""
        sorted_explanations = sorted(
            self.explanations.values(),
            key=lambda x: x.context.timestamp,
            reverse=True
        )
        return sorted_explanations[:limit]
    
    def generate_transparency_report(self) -> Dict[str, Any]:
        """Gera relatório de transparência"""
        
        # Agrupa explicações por tipo
        explanations_by_type = defaultdict(int)
        confidence_by_type = defaultdict(list)
        
        for explanation in self.explanations.values():
            exp_type = explanation.explanation_type.value
            explanations_by_type[exp_type] += 1
            confidence_by_type[exp_type].append(explanation.confidence.overall_confidence)
        
        # Calcula médias de confiança por tipo
        avg_confidence_by_type = {}
        for exp_type, confidences in confidence_by_type.items():
            avg_confidence_by_type[exp_type] = sum(confidences) / len(confidences)
        
        report = {
            'report_generated_at': datetime.now(timezone.utc).isoformat(),
            'total_explanations': len(self.explanations),
            'explanations_by_type': dict(explanations_by_type),
            'average_confidence_by_type': avg_confidence_by_type,
            'overall_statistics': self.stats.copy(),
            'recent_explanations': [
                {
                    'id': exp.explanation_id,
                    'type': exp.explanation_type.value,
                    'confidence': exp.confidence.level.value,
                    'component': exp.context.component,
                    'timestamp': exp.context.timestamp.isoformat()
                }
                for exp in self.get_recent_explanations(20)  # Últimas 20 para mobile
            ],
            'system_health': {
                'memory_usage': len(self.explanations) / self.config.max_explanations_memory,
                'analysis_accuracy': self.stats.get('average_confidence', 0.0),
                'components_active': {
                    'llm_analysis': self.config.enable_llm_analysis,
                    'security_explanations': self.config.enable_security_explanations,
                    'code_explanations': self.config.enable_code_explanations
                }
            }
        }
        
        return report
    
    def get_system_status(self) -> Dict[str, Any]:
        """Retorna status do sistema XAI"""
        return {
            'config': {
                'mobile_optimized': self.config.mobile_optimization,
                'max_explanations': self.config.max_explanations_memory,
                'components_enabled': {
                    'llm_analysis': self.config.enable_llm_analysis,
                    'security_explanations': self.config.enable_security_explanations,
                    'code_explanations': self.config.enable_code_explanations
                }
            },
            'current_state': {
                'explanations_stored': len(self.explanations),
                'memory_usage_percent': (len(self.explanations) / self.config.max_explanations_memory) * 100,
                'average_confidence': self.stats.get('average_confidence', 0.0)
            },
            'statistics': self.stats.copy()
        }