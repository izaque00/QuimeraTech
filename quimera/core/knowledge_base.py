# quimera/core/knowledge_base.py

import logging
import os
import json
import time
from pathlib import Path
from typing import Optional, Dict, List, Any

from quimera.logs.parser import montar_log
from quimera.utils.validators import safe_json_load, KNOWN_CASES_SCHEMA

# NOTA: Removido import direto de quimera.agentes.roteador_modelos
# para evitar violação de camadas arquiteturais (core -> agentes).
# O roteador deve ser injetado via parâmetro ou factory function.
# Exemplo de uso correto:
#   from quimera.agentes.roteador_modelos import RoteadorModelos
#   kb = KnowledgeBase()
#   kb.setup_synthesis_llm(RoteadorModelos())

# --- Bloco de Importação e Verificação de Dependências ---
try:
    from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext, Settings, Document
    # CORREÇÃO: Importar o modelo de embedding do HuggingFace
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding
    from llama_index.llms.langchain import LangChainLLM
    from llama_index.vector_stores.chroma import ChromaVectorStore
    from llama_index.core.retrievers import VectorIndexRetriever # Usaremos um retriever mais simples
    import chromadb
    from sentence_transformers import CrossEncoder
    LLAMA_INDEX_AVAILABLE = True
except ImportError as e:
    LLAMA_INDEX_AVAILABLE = False
    logging.getLogger(__name__).warning(f"Dependências do LlamaIndex/Sentence-Transformers ausentes ({e}). KnowledgeBase (RAG) será desativada.")

# --- Configurações ---
DOCS_PATH = "quimera/dados/documentacao_kernel"
PERSIST_DIR = "quimera/dados/vector_store"
KNOWN_CASES_PATH = "quimera/dados/casos_de_reparo_conhecidos.json"
EMBEDDING_BATCH_SIZE = 15
BATCH_DELAY_SECONDS = 1 # Podemos reduzir o delay, pois a operação é local

class KnowledgeBase:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            if not LLAMA_INDEX_AVAILABLE:
                raise RuntimeError("Não é possível instanciar KnowledgeBase: dependências do LlamaIndex/Sentence-Transformers não estão instaladas.")
            cls._instance = super(KnowledgeBase, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, force_reload=False):
        if self._initialized and not force_reload:
            return

        self.index: Optional[VectorStoreIndex] = None
        self.cross_encoder: Optional[CrossEncoder] = None
        self._known_cases: List[Dict] = []

        # CORREÇÃO: Configurar o modelo de embedding ANTES de qualquer outra coisa.
        self._setup_embedding_model()

        self._load_cases()
        self._setup_synthesis_llm()
        self._load_reranker()
        self.load_data_into_vector_store()

        self._initialized = True
        montar_log("KnowledgeBase/RAG inicializada com sucesso.", "SUCCESS")

    def _setup_embedding_model(self):
        """Configura o modelo de embedding para ser um modelo HuggingFace local/gratuito."""
        try:
            # BAAI/bge-small-en-v1.5 é um modelo leve e de alta performance para embeddings.
            # Ele será baixado e cacheado automaticamente na primeira execução.
            Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
            montar_log("Modelo de embedding configurado para HuggingFace (BAAI/bge-small-en-v1.5).", "INFO")
        except Exception as e:
            montar_log(f"Falha ao configurar o modelo de embedding local: {e}", "CRITICAL")
            Settings.embed_model = None

    # O resto do arquivo permanece o mesmo...
    def _load_cases(self):
        db_path = Path(KNOWN_CASES_PATH)
        if db_path.exists():
            try:
                self._known_cases = safe_json_load(str(db_path), KNOWN_CASES_SCHEMA) or {}
            except Exception as e:
                montar_log(f"Falha ao carregar casos conhecidos de '{db_path}': {e}", "ERROR")

    def setup_synthesis_llm(self, model_router=None):
        """Configura o LLM para síntese de documentos RAG.
        
        Args:
            model_router: Instância de um roteador de modelos
                         (ex: RoteadorModelos do pacote agentes).
                         Deve implementar selecionar_agentes_para_tarefa().
        
        NOTA: Este método NÃO importa diretamente de quimera.agentes
        para manter o desacoplamento de camadas. O roteador deve ser
        injetado pelo código cliente.
        """
        try:
            if model_router is None:
                montar_log("Nenhum model_router fornecido. LLM para RAG desativado.", "WARNING")
                Settings.llm = None
                return

            agentes = model_router.selecionar_agentes_para_tarefa("sintese_de_codigo", 1)
            if agentes and agentes[0].get('cliente_llm'):
                Settings.llm = LangChainLLM(llm=agentes[0]['cliente_llm'])
            else:
                Settings.llm = None
        except Exception as e:
            montar_log(f"Falha ao configurar LLM para RAG: {e}", "ERROR")
            Settings.llm = None

    # Alias para compatibilidade com código antigo
    _setup_synthesis_llm = setup_synthesis_llm

    def _load_reranker(self):
        try:
            self.cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
        except Exception as e:
            self.cross_encoder = None
            montar_log(f"Não foi possível carregar CrossEncoder. Re-ranking desativado. Erro: {e}", "WARNING")

    def load_data_into_vector_store(self):
        if Settings.embed_model is None:
            montar_log("Modelo de embedding não está disponível. Abortando indexação.", "ERROR")
            self.index = None
            return

        docs_dir = Path(DOCS_PATH)
        persist_dir = Path(PERSIST_DIR)
        if not docs_dir.exists() or not any(docs_dir.iterdir()):
            self.index = None
            return

        try:
            db = chromadb.PersistentClient(path=str(persist_dir))
            coll = db.get_or_create_collection("quimera_kernel_docs")
            vector_store = ChromaVectorStore(chroma_collection=coll)

            if coll.count() == 0:
                montar_log(f"Construindo novo índice RAG a partir de '{docs_dir}'...", "INFO")
                docs = SimpleDirectoryReader(str(docs_dir), recursive=True, required_exts=[".txt"]).load_data()
                if not docs: return

                storage_context = StorageContext.from_defaults(vector_store=vector_store)
                # A indexação agora usará o Settings.embed_model configurado (HuggingFace)
                VectorStoreIndex.from_documents(docs, storage_context=storage_context, show_progress=True)

            self.index = VectorStoreIndex.from_vector_store(vector_store)
            montar_log("Índice RAG carregado/construído com sucesso.", "INFO")

        except Exception as e:
            montar_log(f"Falha crítica na inicialização do RAG: {e}", "CRITICAL", exc_info=True)
            self.index = None

    def find_similar_case(self, error_log: str, arquivo_afetado: str) -> Optional[Dict[str, Any]]:
        # ... (código sem alteração) ...
        if not self._known_cases: return None
        best, score_max = None, 0
        for case in self._known_cases:
            score = 0
            keys = case.get("keywords", []) + case.get("erro_tipo", "").split()
            for kw in keys:
                if kw.lower() in error_log.lower(): score += 1
            if arquivo_afetado and case.get("arquivos_afetados") and arquivo_afetado == case["arquivos_afetados"][0]:
                score += 2
            if score > score_max: best, score_max = case, score
        if best: montar_log(f"Caso de reparo similar encontrado com score {score_max}.", "INFO")
        return best

    def query(self, query_text: str, top_k: int = 5) -> str:
        if not self.index: return ""

        try:
            retriever = VectorIndexRetriever(index=self.index, similarity_top_k=top_k * 2)
            retrieved_nodes = retriever.retrieve(query_text)
            if not retrieved_nodes: return ""

            if self.cross_encoder:
                pairs = [[query_text, node.get_content()] for node in retrieved_nodes]
                scores = self.cross_encoder.predict(pairs, show_progress_bar=False)
                final_nodes = [node for _, node in sorted(zip(scores, retrieved_nodes), key=lambda x: x[0], reverse=True)[:top_k]]
            else:
                final_nodes = retrieved_nodes[:top_k]

            ctx = "\n### CONTEXTO DA DOCUMENTAÇÃO DO KERNEL (RAG) ###\n"
            for node in final_nodes:
                fn = Path(node.metadata.get('file_path', 'N/A')).name
                ctx += f"Fonte: {fn}\nTrecho: {node.get_content().strip()}\n---\n"
            return ctx
        except Exception as e:
            montar_log(f"Erro na consulta RAG: {e}", "ERROR", exc_info=True)
            return ""

    def obter_estatisticas_completas(self) -> Dict[str, Any]:
        """Retorna um dicionário com o status e estatísticas da KnowledgeBase."""
        status = {
            'status': 'operacional' if self._initialized and self.index else 'desativado',
            'motivo_desativacao': ''
        }
        if not LLAMA_INDEX_AVAILABLE:
            status['motivo_desativacao'] = 'Dependências do LlamaIndex/Sentence-Transformers ausentes.'
        elif not self._initialized:
            status['motivo_desativacao'] = 'Não inicializada.'
        elif not self.index:
            status['motivo_desativacao'] = 'Índice RAG não carregado ou construído.'

        return status