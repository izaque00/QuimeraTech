# quimera/core/vector_manager.py

# Verificações de dependências adicionadas automaticamente
def verificar_dependencia(nome_modulo, funcionalidade="essa funcionalidade"):
    """Verifica se uma dependência está disponível"""
    try:
        __import__(nome_modulo)
        return True
    except ImportError:
        print(f"⚠️  {nome_modulo} não instalado - {funcionalidade} não disponível")
        return False

import logging
_logger = logging.getLogger(__name__)


def _unavailable_feature(feature_name: str, *args, **kwargs):
    """Loga warning quando funcionalidade não está disponível por falta de dependências."""
    _logger.warning(f"Funcionalidade '{feature_name}' indisponível — dependência não instalada")
    return None

try:
    import numpy as np
except ImportError:
    np = None  # Mock
import logging
import os
import hashlib
import json
import re
from typing import Dict, Any, List, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from pathlib import Path

logger = logging.getLogger(__name__)

class VectorManager:
    """
    Gerenciador para vetorização e busca de similaridade.
    Agora gerencia dois tipos de memória:
    1. Memória de Refatoração: Busca por patches similares (baseado no conteúdo do patch).
    2. Memória de Solução de Erros: Busca soluções (patches) com base na similaridade de logs de erro.
    """

    def __init__(self,
                 refatoracao_db_path: str = "quimera/dados/memoria_refatoracao.json",
                 solucao_erros_db_path: str = "quimera/dados/memoria_solucao_erros.json"):

        # --- Memória de Refatoração (Funcionalidade Existente) ---
        self.refatoracao_db_path = Path(refatoracao_db_path)
        self.memoria_refatoracao: Dict[str, str] = {} # {ref_id: patch_content}

        # --- NOVA: Memória de Solução de Erros ---
        self.solucao_erros_db_path = Path(solucao_erros_db_path)
        self.memoria_solucoes: Dict[str, Dict[str, str]] = {} # {error_hash: {"log_erro": "...", "patch_vencedor": "..."}}

        # --- Vetorizadores ---
        self.vectorizer_refatoracao = TfidfVectorizer(min_df=1, stop_words=None)
        self.vectorizer_solucoes = TfidfVectorizer(min_df=1, stop_words=None)

        # Matrizes de vetores e chaves para busca rápida
        self.refatoracao_vectors = None
        self.refatoracao_keys = []
        self.solucao_vectors = None
        self.solucao_keys = []

        self._load_all_memories()
        logger.info(f"VectorManager inicializado com {len(self.memoria_refatoracao)} refatorações e {len(self.memoria_solucoes)} soluções de erro.")

    def _preprocess_text(self, text: str) -> str:
        """Limpa e normaliza o texto para vetorização."""
        text = re.sub(r'[\\/:*?"<>|]', ' ', text) # Remove caracteres de caminho
        text = re.sub(r'\d+', ' NUMBER ', text) # Normaliza números
        return text.lower()

    def _load_all_memories(self):
        """Carrega ambas as memórias e treina os respectivos vetorizadores."""
        # Carregar memória de refatoração
        if self.refatoracao_db_path.exists():
            try:
                with open(self.refatoracao_db_path, 'r', encoding='utf-8') as f:
                    self.memoria_refatoracao = json.load(f)
                if self.memoria_refatoracao:
                    corpus = [self._preprocess_text(patch) for patch in self.memoria_refatoracao.values()]
                    self.refatoracao_keys = list(self.memoria_refatoracao.keys())
                    self.refatoracao_vectors = self.vectorizer_refatoracao.fit_transform(corpus)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Erro ao carregar memória de refatoração: {e}. Iniciando vazia.")
                self.memoria_refatoracao = {}

        # Carregar memória de soluções de erro
        if self.solucao_erros_db_path.exists():
            try:
                with open(self.solucao_erros_db_path, 'r', encoding='utf-8') as f:
                    self.memoria_solucoes = json.load(f)
                if self.memoria_solucoes:
                    corpus = [self._preprocess_text(item["log_erro"]) for item in self.memoria_solucoes.values()]
                    self.solucao_keys = list(self.memoria_solucoes.keys())
                    self.solucao_vectors = self.vectorizer_solucoes.fit_transform(corpus)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Erro ao carregar memória de soluções: {e}. Iniciando vazia.")
                self.memoria_solucoes = {}

    def _save_memory(self, db_path: Path, memory_dict: dict):
        """Salva um dicionário de memória em um arquivo JSON."""
        try:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            with open(db_path, 'w', encoding='utf-8') as f:
                json.dump(memory_dict, f, indent=2)
        except IOError as e:
            logger.error(f"Erro ao salvar memória em {db_path}: {e}")

    # --- Métodos para Memória de Refatoração (Existente) ---

    def adicionar_refatoracao(self, refatoracao_id: str, patch_content: str):
        """Adiciona um exemplo de patch de refatoração à memória."""
        self.memoria_refatoracao[refatoracao_id] = patch_content
        self._save_memory(self.refatoracao_db_path, self.memoria_refatoracao)
        self._load_all_memories() # Recarrega para manter os vetores sincronizados
        logger.info(f"Refatoração ID '{refatoracao_id}' adicionada à memória.")

    def buscar_refatoracoes_similares(self, query_patch: str, top_k: int = 2) -> List[str]:
        """Busca por patches similares a um patch de consulta."""
        if not self.memoria_refatoracao or self.refatoracao_vectors is None:
            return []

        processed_query = self._preprocess_text(query_patch)
        query_vector = self.vectorizer_refatoracao.transform([processed_query])
        similarities = cosine_similarity(query_vector, self.refatoracao_vectors).flatten()

        top_k_indices = similarities.argsort()[-top_k:][::-1]

        return [self.memoria_refatoracao[self.refatoracao_keys[i]] for i in top_k_indices if similarities[i] > 0.7]

    # --- NOVOS Métodos para Memória de Solução de Erros ---

    def adicionar_solucao_de_erro(self, log_erro: str, patch_vencedor: str):
        """Adiciona um novo par de erro/solução à memória de soluções."""
        error_hash = hashlib.sha256(self._preprocess_text(log_erro).encode()).hexdigest()
        if error_hash in self.memoria_solucoes:
            logger.debug(f"Solução para o erro hash {error_hash[:12]} já existe. Ignorando.")
            return

        self.memoria_solucoes[error_hash] = {
            "log_erro": log_erro,
            "patch_vencedor": patch_vencedor
        }
        self._save_memory(self.solucao_erros_db_path, self.memoria_solucoes)
        self._load_all_memories() # Recarrega e retreina
        logger.info(f"Nova solução de erro adicionada à memória. Hash: {error_hash[:12]}")

    def buscar_solucoes_por_similaridade_de_erro(self, log_erro_novo: str, top_k: int = 2) -> List[str]:
        """Busca os patches das K soluções mais similares com base no log de erro."""
        if not self.memoria_solucoes or self.solucao_vectors is None:
            return []

        processed_new_log = self._preprocess_text(log_erro_novo)
        new_vector = self.vectorizer_solucoes.transform([processed_new_log])

        similarities = cosine_similarity(new_vector, self.solucao_vectors).flatten()

        top_k_indices = similarities.argsort()[-top_k:][::-1]

        patches_similares = [
            self.memoria_solucoes[self.solucao_keys[i]]["patch_vencedor"]
            for i in top_k_indices if similarities[i] > 0.75
        ]

        if patches_similares:
            logger.info(f"Encontrados {len(patches_similares)} patches de soluções similares com alta confiança.")

        return patches_similares