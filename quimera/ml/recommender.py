"""
Sistema de Recomendação de Correções Inteligente - Quimera ML
===========================================================

Sistema avançado que usa Machine Learning para recomendar correções
de código baseadas em padrões históricos e análise semântica.
"""

import ast
import hashlib
import json
import pickle
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

from quimera.logs.parser import montar_log

@dataclass
class CorrectionRecommendation:
    """Recomendação de correção gerada pelo sistema ML"""
    problem_type: str
    original_code: str
    suggested_fix: str
    confidence_score: float
    explanation: str
    similar_cases: List[str] = field(default_factory=list)
    risk_assessment: str = "LOW"
    estimated_time: int = 5  # minutos

@dataclass
class MLTrainingData:
    """Dados de treino para o modelo ML"""
    problem_signature: str
    code_before: str
    code_after: str
    problem_category: str
    success_rate: float
    context_features: Dict[str, Any] = field(default_factory=dict)

class IntelligentCorrectionRecommender:
    """Sistema principal de recomendação inteligente"""
    
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or "quimera_ml_models"
        self.training_data = []
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 3)
        )
        self.classifier = RandomForestClassifier(
            n_estimators=100,
            random_state=42,
            max_depth=10
        )
        self.label_encoder = LabelEncoder()
        self.knowledge_base = {}
        self.pattern_cache = {}
        
        # Criar diretório para modelos
        Path(self.model_path).mkdir(exist_ok=True)
        
        # Carregar dados existentes
        self._load_existing_data()
        
        montar_log("Sistema de Recomendação ML inicializado", "INFO")
    
    def _load_existing_data(self):
        """Carrega dados de treino e modelos existentes"""
        try:
            # Carregar dados de treino
            training_file = Path(self.model_path) / "training_data.pkl"
            if training_file.exists():
                with open(training_file, 'rb') as f:
                    self.training_data = pickle.load(f)
                montar_log(f"Carregados {len(self.training_data)} exemplos de treino", "INFO")
            
            # Carregar base de conhecimento
            kb_file = Path(self.model_path) / "knowledge_base.json"
            if kb_file.exists():
                with open(kb_file, 'r') as f:
                    self.knowledge_base = json.load(f)
                montar_log(f"Base de conhecimento carregada: {len(self.knowledge_base)} padrões", "INFO")
            
            # Treinar modelo se houver dados
            if len(self.training_data) > 10:
                self._train_model()
                
        except Exception as e:
            montar_log(f"Erro ao carregar dados existentes: {e}", "WARNING")
    
    def add_training_example(self, 
                           problem_type: str,
                           code_before: str, 
                           code_after: str,
                           success_rate: float = 1.0,
                           context: Optional[Dict[str, Any]] = None):
        """Adiciona exemplo de treino ao dataset"""
        
        # Gerar assinatura do problema
        problem_signature = self._generate_problem_signature(code_before, problem_type)
        
        # Extrair features do contexto
        context_features = context or {}
        context_features.update(self._extract_code_features(code_before))
        
        # Criar exemplo de treino
        training_example = MLTrainingData(
            problem_signature=problem_signature,
            code_before=code_before,
            code_after=code_after,
            problem_category=problem_type,
            success_rate=success_rate,
            context_features=context_features
        )
        
        self.training_data.append(training_example)
        
        # Salvar dados atualizados
        self._save_training_data()
        
        montar_log(f"Exemplo de treino adicionado: {problem_type}", "INFO")
    
    def _generate_problem_signature(self, code: str, problem_type: str) -> str:
        """Gera assinatura única para um tipo de problema"""
        # Normalizar código
        normalized = re.sub(r'\s+', ' ', code.strip().lower())
        
        # Combinar com tipo do problema
        signature_input = f"{problem_type}:{normalized}"
        
        # Gerar hash
        return hashlib.md5(signature_input.encode()).hexdigest()
    
    def _extract_code_features(self, code: str) -> Dict[str, Any]:
        """Extrai features do código para análise ML"""
        features = {}
        
        try:
            # Parse AST
            tree = ast.parse(code)
            
            # Contar tipos de nós
            node_counts = {}
            for node in ast.walk(tree):
                node_type = type(node).__name__
                node_counts[node_type] = node_counts.get(node_type, 0) + 1
            
            features['ast_nodes'] = node_counts
            features['total_nodes'] = sum(node_counts.values())
            
            # Métricas básicas
            features['lines_count'] = len(code.split('\n'))
            features['char_count'] = len(code)
            features['complexity_estimate'] = len(re.findall(r'\b(if|for|while|try|except)\b', code))
            
            # Padrões sintáticos
            features['has_imports'] = 'import ' in code
            features['has_functions'] = 'def ' in code
            features['has_classes'] = 'class ' in code
            features['has_loops'] = any(keyword in code for keyword in ['for ', 'while '])
            features['has_conditionals'] = any(keyword in code for keyword in ['if ', 'elif ', 'else:'])
            
        except Exception as e:
            montar_log(f"Erro ao extrair features: {e}", "WARNING")
            features['parse_error'] = True
        
        return features

# Instância global do sistema de recomendação
global_recommender = IntelligentCorrectionRecommender()

def get_intelligent_recommendations(code: str, 
                                  problems: List[str],
                                  context: Optional[Dict[str, Any]] = None):
    """Função de conveniência para obter recomendações"""
    return global_recommender.recommend_correction(code, problems, context)

def add_correction_feedback(problem_type: str,
                          code_before: str,
                          code_after: str,
                          success: bool = True):
    """Adiciona feedback de correção para melhorar o modelo"""
    success_rate = 1.0 if success else 0.0
    global_recommender.add_training_example(
        problem_type, code_before, code_after, success_rate
    )