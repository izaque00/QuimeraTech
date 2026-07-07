"""
Biblioteca de Alexandria Digital - Sistema de Indexação Automática
Sistema de biblioteca de código comparável aos projetos do Google
Tecnologia de ponta para organização e catalogação automática de repositórios
"""

import asyncio
import logging
import os
import json
import time
import hashlib
import pickle
import sqlite3
import threading
from typing import Dict, List, Any, Optional, Tuple, Set, Union, AsyncGenerator
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import multiprocessing as mp
from contextlib import asynccontextmanager
import tempfile
import shutil
import gzip
import lzma

# Banco de dados avançado
try:
    import neo4j
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    import elasticsearch
    ELASTICSEARCH_AVAILABLE = True
except ImportError:
    ELASTICSEARCH_AVAILABLE = False

# Machine Learning e embeddings
try:
    import numpy as np
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

# Processamento de linguagem natural
try:
    import spacy
    from spacy import displacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

# Análise de código avançada
try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False

from quimera.logs.parser import montar_log
try:
    from .scanner_avancado import ScannerAvancado, RepositorioEscaneado, ArquivoEscaneado
except ImportError:
    ScannerAvancado = None  # ScannerAvancado não disponível, RepositorioEscaneado, ArquivoEscaneado

logger = logging.getLogger(__name__)


@dataclass
class EntidadeCodigo:
    """Representa uma entidade de código (função, classe, variável, etc.)"""
    id: str
    nome: str
    tipo: str  # 'function', 'class', 'variable', 'constant', 'macro', etc.
    arquivo: str
    linha_inicio: int
    linha_fim: int
    linguagem: str
    assinatura: str
    documentacao: str
    codigo_fonte: str
    hash_codigo: str
    complexidade: int
    qualidade: float
    tags: List[str]
    metadados: Dict[str, Any]
    relacionamentos: List[str]  # IDs de outras entidades relacionadas
    embeddings: Optional[List[float]]
    data_criacao: datetime
    data_modificacao: datetime


@dataclass
class RelacionamentoCodigo:
    """Representa um relacionamento entre entidades de código"""
    id: str
    origem_id: str
    destino_id: str
    tipo: str  # 'calls', 'inherits', 'imports', 'uses', 'defines', etc.
    peso: float
    contexto: str
    metadados: Dict[str, Any]
    data_criacao: datetime


@dataclass
class RepositorioIndexado:
    """Representa um repositório completamente indexado"""
    id: str
    nome: str
    url: str
    branch: str
    hash_commit: str
    data_indexacao: datetime
    data_ultima_atualizacao: datetime
    total_arquivos: int
    total_entidades: int
    total_relacionamentos: int
    linguagens: List[str]
    frameworks: List[str]
    tags: List[str]
    qualidade_geral: float
    complexidade_geral: float
    maturidade: str
    categoria: str
    metadados: Dict[str, Any]
    estatisticas: Dict[str, Any]


@dataclass
class ConsultaInteligente:
    """Representa uma consulta inteligente à biblioteca"""
    id: str
    query: str
    tipo_consulta: str  # 'semantic', 'structural', 'similarity', 'pattern'
    filtros: Dict[str, Any]
    limite: int
    timestamp: datetime
    usuario: str
    contexto: Dict[str, Any]


@dataclass
class ResultadoConsulta:
    """Resultado de uma consulta à biblioteca"""
    consulta_id: str
    resultados: List[Dict[str, Any]]
    total_encontrados: int
    tempo_execucao: float
    score_relevancia: float
    sugestoes: List[str]
    metadados: Dict[str, Any]


class IndiceSemantico:
    """Índice semântico avançado usando embeddings e busca vetorial"""

    def __init__(self, dimensao: int = 768):
        self.dimensao = dimensao
        self.indice_faiss = None
        self.mapeamento_ids = {}
        self.embeddings_cache = {}
        self.modelo_embeddings = None

        if FAISS_AVAILABLE:
            self.indice_faiss = faiss.IndexFlatIP(dimensao)  # Inner Product para similaridade

        if SENTENCE_TRANSFORMERS_AVAILABLE:
            self._inicializar_modelo_embeddings()

    def _inicializar_modelo_embeddings(self):
        """Inicializa modelo de embeddings"""
        try:
            # Usar modelo otimizado para código
            self.modelo_embeddings = SentenceTransformer('microsoft/codebert-base')
            montar_log("Modelo de embeddings CodeBERT inicializado", "INFO")
        except Exception as e:
            try:
                # Fallback para modelo geral
                self.modelo_embeddings = SentenceTransformer('all-MiniLM-L6-v2')
                montar_log("Modelo de embeddings MiniLM inicializado", "INFO")
            except Exception as e2:
                montar_log(f"Erro ao inicializar modelos de embeddings: {e2}", "WARNING")
                self.modelo_embeddings = None

    def gerar_embedding(self, texto: str) -> Optional[List[float]]:
        """Gera embedding para um texto"""
        if not self.modelo_embeddings:
            return None

        try:
            # Cache para evitar recomputação
            hash_texto = hashlib.md5(texto.encode()).hexdigest()
            if hash_texto in self.embeddings_cache:
                return self.embeddings_cache[hash_texto]

            # Gerar embedding
            embedding = self.modelo_embeddings.encode(texto, convert_to_tensor=False)
            embedding_list = embedding.tolist()

            # Cache
            self.embeddings_cache[hash_texto] = embedding_list

            return embedding_list

        except Exception as e:
            montar_log(f"Erro ao gerar embedding: {e}", "WARNING")
            return None

    def adicionar_entidade(self, entidade: EntidadeCodigo):
        """Adiciona entidade ao índice semântico"""
        if not self.indice_faiss or not entidade.embeddings:
            return

        try:
            # Converter para numpy array
            embedding = np.array(entidade.embeddings, dtype=np.float32).reshape(1, -1)

            # Adicionar ao índice FAISS
            self.indice_faiss.add(embedding)

            # Mapear ID
            indice_atual = self.indice_faiss.ntotal - 1
            self.mapeamento_ids[indice_atual] = entidade.id

        except Exception as e:
            montar_log(f"Erro ao adicionar entidade ao índice: {e}", "WARNING")

    def buscar_similares(self, query: str, k: int = 10) -> List[Tuple[str, float]]:
        """Busca entidades similares semanticamente"""
        if not self.indice_faiss or not self.modelo_embeddings:
            return []

        try:
            # Gerar embedding da query
            query_embedding = self.gerar_embedding(query)
            if not query_embedding:
                return []

            # Buscar no índice
            query_vector = np.array(query_embedding, dtype=np.float32).reshape(1, -1)
            scores, indices = self.indice_faiss.search(query_vector, k)

            # Mapear resultados
            resultados = []
            for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
                if idx in self.mapeamento_ids:
                    entidade_id = self.mapeamento_ids[idx]
                    resultados.append((entidade_id, float(score)))

            return resultados

        except Exception as e:
            montar_log(f"Erro na busca semântica: {e}", "WARNING")
            return []

    def salvar_indice(self, caminho: str):
        """Salva índice em disco"""
        try:
            if self.indice_faiss:
                faiss.write_index(self.indice_faiss, f"{caminho}.faiss")

            with open(f"{caminho}.mapping", 'wb') as f:
                pickle.dump(self.mapeamento_ids, f)

            with open(f"{caminho}.cache", 'wb') as f:
                pickle.dump(self.embeddings_cache, f)

            montar_log(f"Índice semântico salvo em {caminho}", "INFO")

        except Exception as e:
            montar_log(f"Erro ao salvar índice: {e}", "ERROR")

    def carregar_indice(self, caminho: str):
        """Carrega índice do disco"""
        try:
            if os.path.exists(f"{caminho}.faiss"):
                self.indice_faiss = faiss.read_index(f"{caminho}.faiss")

            if os.path.exists(f"{caminho}.mapping"):
                with open(f"{caminho}.mapping", 'rb') as f:
                    self.mapeamento_ids = pickle.load(f)

            if os.path.exists(f"{caminho}.cache"):
                with open(f"{caminho}.cache", 'rb') as f:
                    self.embeddings_cache = pickle.load(f)

            montar_log(f"Índice semântico carregado de {caminho}", "INFO")

        except Exception as e:
            montar_log(f"Erro ao carregar índice: {e}", "ERROR")


class GrafoConhecimento:
    """Grafo de conhecimento para relacionamentos entre entidades"""

    def __init__(self):
        self.grafo = None
        self.conexao_neo4j = None

        if NETWORKX_AVAILABLE:
            self.grafo = nx.MultiDiGraph()

        if NEO4J_AVAILABLE:
            self._conectar_neo4j()

    def _conectar_neo4j(self):
        """Conecta ao Neo4j se disponível"""
        try:
            # Em produção, usar configurações reais
            self.conexao_neo4j = neo4j.GraphDatabase.driver(
                "bolt://localhost:7687",
                auth=("neo4j", "password")
            )
            montar_log("Conectado ao Neo4j", "INFO")
        except Exception as e:
            montar_log(f"Neo4j não disponível: {e}", "WARNING")
            self.conexao_neo4j = None

    def adicionar_entidade(self, entidade: EntidadeCodigo):
        """Adiciona entidade ao grafo"""
        if self.grafo:
            self.grafo.add_node(
                entidade.id,
                nome=entidade.nome,
                tipo=entidade.tipo,
                arquivo=entidade.arquivo,
                linguagem=entidade.linguagem,
                complexidade=entidade.complexidade,
                qualidade=entidade.qualidade,
                tags=entidade.tags
            )

        if self.conexao_neo4j:
            self._adicionar_entidade_neo4j(entidade)

    def _adicionar_entidade_neo4j(self, entidade: EntidadeCodigo):
        """Adiciona entidade ao Neo4j"""
        try:
            with self.conexao_neo4j.session() as session:
                session.run(
                    """
                    MERGE (e:Entidade {id: $id})
                    SET e.nome = $nome,
                        e.tipo = $tipo,
                        e.arquivo = $arquivo,
                        e.linguagem = $linguagem,
                        e.complexidade = $complexidade,
                        e.qualidade = $qualidade,
                        e.tags = $tags
                    """,
                    id=entidade.id,
                    nome=entidade.nome,
                    tipo=entidade.tipo,
                    arquivo=entidade.arquivo,
                    linguagem=entidade.linguagem,
                    complexidade=entidade.complexidade,
                    qualidade=entidade.qualidade,
                    tags=entidade.tags
                )
        except Exception as e:
            montar_log(f"Erro ao adicionar entidade ao Neo4j: {e}", "WARNING")

    def adicionar_relacionamento(self, relacionamento: RelacionamentoCodigo):
        """Adiciona relacionamento ao grafo"""
        if self.grafo:
            self.grafo.add_edge(
                relacionamento.origem_id,
                relacionamento.destino_id,
                id=relacionamento.id,
                tipo=relacionamento.tipo,
                peso=relacionamento.peso,
                contexto=relacionamento.contexto
            )

        if self.conexao_neo4j:
            self._adicionar_relacionamento_neo4j(relacionamento)

    def _adicionar_relacionamento_neo4j(self, relacionamento: RelacionamentoCodigo):
        """Adiciona relacionamento ao Neo4j"""
        try:
            with self.conexao_neo4j.session() as session:
                session.run(
                    f"""
                    MATCH (origem:Entidade {{id: $origem_id}})
                    MATCH (destino:Entidade {{id: $destino_id}})
                    MERGE (origem)-[r:{relacionamento.tipo.upper()} {{id: $id}}]->(destino)
                    SET r.peso = $peso,
                        r.contexto = $contexto
                    """,
                    origem_id=relacionamento.origem_id,
                    destino_id=relacionamento.destino_id,
                    id=relacionamento.id,
                    peso=relacionamento.peso,
                    contexto=relacionamento.contexto
                )
        except Exception as e:
            montar_log(f"Erro ao adicionar relacionamento ao Neo4j: {e}", "WARNING")

    def buscar_relacionados(self, entidade_id: str, tipos: List[str] = None, profundidade: int = 2) -> List[Dict[str, Any]]:
        """Busca entidades relacionadas"""
        if self.conexao_neo4j:
            return self._buscar_relacionados_neo4j(entidade_id, tipos, profundidade)
        elif self.grafo:
            return self._buscar_relacionados_networkx(entidade_id, tipos, profundidade)
        else:
            return []

    def _buscar_relacionados_neo4j(self, entidade_id: str, tipos: List[str], profundidade: int) -> List[Dict[str, Any]]:
        """Busca relacionados usando Neo4j"""
        try:
            with self.conexao_neo4j.session() as session:
                tipos_filter = ""
                if tipos:
                    tipos_upper = [t.upper() for t in tipos]
                    tipos_filter = f"WHERE type(r) IN {tipos_upper}"

                query = f"""
                MATCH (origem:Entidade {{id: $entidade_id}})-[r*1..{profundidade}]-(relacionado:Entidade)
                {tipos_filter}
                RETURN relacionado, r
                LIMIT 100
                """

                resultado = session.run(query, entidade_id=entidade_id)

                relacionados = []
                for record in resultado:
                    relacionado = record["relacionado"]
                    relacionados.append({
                        'id': relacionado['id'],
                        'nome': relacionado['nome'],
                        'tipo': relacionado['tipo'],
                        'arquivo': relacionado['arquivo'],
                        'relacionamento': record["r"]
                    })

                return relacionados

        except Exception as e:
            montar_log(f"Erro na busca Neo4j: {e}", "WARNING")
            return []

    def _buscar_relacionados_networkx(self, entidade_id: str, tipos: List[str], profundidade: int) -> List[Dict[str, Any]]:
        """Busca relacionados usando NetworkX"""
        try:
            if entidade_id not in self.grafo:
                return []

            relacionados = []

            # BFS para encontrar nós relacionados
            visitados = set()
            fila = deque([(entidade_id, 0)])

            while fila:
                no_atual, nivel = fila.popleft()

                if nivel >= profundidade or no_atual in visitados:
                    continue

                visitados.add(no_atual)

                # Adicionar vizinhos
                for vizinho in self.grafo.neighbors(no_atual):
                    if vizinho not in visitados:
                        # Verificar tipo de relacionamento se especificado
                        edges = self.grafo.get_edge_data(no_atual, vizinho)
                        if edges:
                            for edge_data in edges.values():
                                if not tipos or edge_data.get('tipo') in tipos:
                                    relacionados.append({
                                        'id': vizinho,
                                        'dados': self.grafo.nodes[vizinho],
                                        'relacionamento': edge_data
                                    })
                                    fila.append((vizinho, nivel + 1))
                                    break

            return relacionados[:100]  # Limitar resultados

        except Exception as e:
            montar_log(f"Erro na busca NetworkX: {e}", "WARNING")
            return []

    def analisar_centralidade(self) -> Dict[str, float]:
        """Analisa centralidade dos nós no grafo"""
        if not self.grafo:
            return {}

        try:
            # Calcular diferentes métricas de centralidade
            centralidades = {}

            if self.grafo.number_of_nodes() > 0:
                # Centralidade de grau
                degree_centrality = nx.degree_centrality(self.grafo)

                # Centralidade de intermediação
                if self.grafo.number_of_nodes() < 1000:  # Evitar computação pesada
                    betweenness_centrality = nx.betweenness_centrality(self.grafo)
                else:
                    betweenness_centrality = {}

                # Combinar métricas
                for node in self.grafo.nodes():
                    score = degree_centrality.get(node, 0.0)
                    if node in betweenness_centrality:
                        score += betweenness_centrality[node]
                    centralidades[node] = score

            return centralidades

        except Exception as e:
            montar_log(f"Erro na análise de centralidade: {e}", "WARNING")
            return {}

    def detectar_comunidades(self) -> Dict[str, int]:
        """Detecta comunidades no grafo"""
        if not self.grafo:
            return {}

        try:
            # Converter para grafo não direcionado para detecção de comunidades
            grafo_nao_direcionado = self.grafo.to_undirected()

            # Usar algoritmo de Louvain se disponível
            try:
                import community as community_louvain
                partition = community_louvain.best_partition(grafo_nao_direcionado)
                return partition
            except ImportError:
                # Fallback para componentes conectados
                componentes = nx.connected_components(grafo_nao_direcionado)
                partition = {}
                for i, componente in enumerate(componentes):
                    for node in componente:
                        partition[node] = i
                return partition

        except Exception as e:
            montar_log(f"Erro na detecção de comunidades: {e}", "WARNING")
            return {}

    def obter_estatisticas(self) -> Dict[str, Any]:
        """Obtém estatísticas do grafo"""
        if not self.grafo:
            return {}

        try:
            stats = {
                'total_nos': self.grafo.number_of_nodes(),
                'total_arestas': self.grafo.number_of_edges(),
                'densidade': nx.density(self.grafo),
                'componentes_conectados': nx.number_weakly_connected_components(self.grafo),
                'nos_mais_centrais': [],
                'comunidades': 0
            }

            # Nós mais centrais
            centralidades = self.analisar_centralidade()
            if centralidades:
                nos_ordenados = sorted(centralidades.items(), key=lambda x: x[1], reverse=True)
                stats['nos_mais_centrais'] = nos_ordenados[:10]

            # Número de comunidades
            comunidades = self.detectar_comunidades()
            if comunidades:
                stats['comunidades'] = len(set(comunidades.values()))

            return stats

        except Exception as e:
            montar_log(f"Erro ao obter estatísticas: {e}", "WARNING")
            return {}


class BibliotecaAlexandria:
    """
    Biblioteca de Alexandria Digital - Sistema de indexação automática de última geração
    Comparável aos projetos do Google em termos de tecnologia e automação
    """

    def __init__(self, diretorio_base: str):
        self.diretorio_base = Path(diretorio_base)
        self.diretorio_base.mkdir(parents=True, exist_ok=True)

        # Componentes principais
        self.scanner = ScannerAvancado()
        self.indice_semantico = IndiceSemantico()
        self.grafo_conhecimento = GrafoConhecimento()

        # Banco de dados principal
        self.db_path = self.diretorio_base / "biblioteca.db"
        self.conexao_db = None

        # Cache e otimizações
        self.cache_redis = None
        self.indice_elasticsearch = None

        # Estatísticas e monitoramento
        self.estatisticas = {
            'repositorios_indexados': 0,
            'entidades_catalogadas': 0,
            'relacionamentos_mapeados': 0,
            'consultas_realizadas': 0,
            'tempo_total_indexacao': 0.0,
            'ultima_atualizacao': None
        }

        # Configurações
        self.config = {
            'max_workers_indexacao': min(32, (os.cpu_count() or 1) + 4),
            'batch_size_entidades': 1000,
            'intervalo_backup': 3600,  # 1 hora
            'compressao_ativa': True,
            'cache_embeddings': True,
            'auto_otimizacao': True
        }

        # Inicializar componentes
        self._inicializar_banco_dados()
        self._inicializar_cache()
        self._inicializar_indices_externos()

        montar_log("Biblioteca de Alexandria Digital inicializada", "SUCCESS")

    def _inicializar_banco_dados(self):
        """Inicializa banco de dados SQLite principal"""
        try:
            self.conexao_db = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0
            )

            # Configurações de performance
            self.conexao_db.execute("PRAGMA journal_mode=WAL")
            self.conexao_db.execute("PRAGMA synchronous=NORMAL")
            self.conexao_db.execute("PRAGMA cache_size=10000")
            self.conexao_db.execute("PRAGMA temp_store=MEMORY")

            # Criar tabelas
            self._criar_esquema_banco()

            montar_log("Banco de dados principal inicializado", "INFO")

        except Exception as e:
            montar_log(f"Erro ao inicializar banco de dados: {e}", "ERROR")
            raise

    def _criar_esquema_banco(self):
        """Cria esquema do banco de dados"""
        esquemas = [
            """
            CREATE TABLE IF NOT EXISTS repositorios (
                id TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                url TEXT NOT NULL,
                branch TEXT NOT NULL,
                hash_commit TEXT,
                data_indexacao TIMESTAMP,
                data_ultima_atualizacao TIMESTAMP,
                total_arquivos INTEGER,
                total_entidades INTEGER,
                total_relacionamentos INTEGER,
                linguagens TEXT,
                frameworks TEXT,
                tags TEXT,
                qualidade_geral REAL,
                complexidade_geral REAL,
                maturidade TEXT,
                categoria TEXT,
                metadados TEXT,
                estatisticas TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS entidades (
                id TEXT PRIMARY KEY,
                repositorio_id TEXT,
                nome TEXT NOT NULL,
                tipo TEXT NOT NULL,
                arquivo TEXT NOT NULL,
                linha_inicio INTEGER,
                linha_fim INTEGER,
                linguagem TEXT,
                assinatura TEXT,
                documentacao TEXT,
                codigo_fonte TEXT,
                hash_codigo TEXT,
                complexidade INTEGER,
                qualidade REAL,
                tags TEXT,
                metadados TEXT,
                embeddings BLOB,
                data_criacao TIMESTAMP,
                data_modificacao TIMESTAMP,
                FOREIGN KEY (repositorio_id) REFERENCES repositorios (id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS relacionamentos (
                id TEXT PRIMARY KEY,
                repositorio_id TEXT,
                origem_id TEXT,
                destino_id TEXT,
                tipo TEXT NOT NULL,
                peso REAL,
                contexto TEXT,
                metadados TEXT,
                data_criacao TIMESTAMP,
                FOREIGN KEY (repositorio_id) REFERENCES repositorios (id),
                FOREIGN KEY (origem_id) REFERENCES entidades (id),
                FOREIGN KEY (destino_id) REFERENCES entidades (id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS consultas (
                id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                tipo_consulta TEXT,
                filtros TEXT,
                limite INTEGER,
                timestamp TIMESTAMP,
                usuario TEXT,
                contexto TEXT,
                resultados TEXT,
                tempo_execucao REAL,
                score_relevancia REAL
            )
            """
        ]

        # Índices para performance
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_entidades_repositorio ON entidades(repositorio_id)",
            "CREATE INDEX IF NOT EXISTS idx_entidades_tipo ON entidades(tipo)",
            "CREATE INDEX IF NOT EXISTS idx_entidades_linguagem ON entidades(linguagem)",
            "CREATE INDEX IF NOT EXISTS idx_entidades_nome ON entidades(nome)",
            "CREATE INDEX IF NOT EXISTS idx_relacionamentos_origem ON relacionamentos(origem_id)",
            "CREATE INDEX IF NOT EXISTS idx_relacionamentos_destino ON relacionamentos(destino_id)",
            "CREATE INDEX IF NOT EXISTS idx_relacionamentos_tipo ON relacionamentos(tipo)",
            "CREATE INDEX IF NOT EXISTS idx_consultas_timestamp ON consultas(timestamp)"
        ]

        try:
            for esquema in esquemas:
                self.conexao_db.execute(esquema)

            for indice in indices:
                self.conexao_db.execute(indice)

            self.conexao_db.commit()
            montar_log("Esquema do banco de dados criado", "INFO")

        except Exception as e:
            montar_log(f"Erro ao criar esquema: {e}", "ERROR")
            raise

    def _inicializar_cache(self):
        """Inicializa sistema de cache Redis"""
        if REDIS_AVAILABLE:
            try:
                self.cache_redis = redis.Redis(
                    host='localhost',
                    port=6379,
                    db=0,
                    decode_responses=True,
                    socket_timeout=5
                )

                # Testar conexão
                self.cache_redis.ping()
                montar_log("Cache Redis inicializado", "INFO")

            except Exception as e:
                montar_log(f"Redis não disponível: {e}", "WARNING")
                self.cache_redis = None

    def _inicializar_indices_externos(self):
        """Inicializa índices externos (Elasticsearch)"""
        if ELASTICSEARCH_AVAILABLE:
            try:
                self.indice_elasticsearch = elasticsearch.Elasticsearch(
                    [{'host': 'localhost', 'port': 9200}],
                    timeout=30
                )

                # Testar conexão
                if self.indice_elasticsearch.ping():
                    montar_log("Elasticsearch inicializado", "INFO")
                else:
                    self.indice_elasticsearch = None

            except Exception as e:
                montar_log(f"Elasticsearch não disponível: {e}", "WARNING")
                self.indice_elasticsearch = None

    async def indexar_repositorio_automatico(self, url_repo: str, branch: str = "main") -> RepositorioIndexado:
        """
        Indexação automática completa de um repositório a partir de uma URL.
        """
        montar_log(f"=== INICIANDO INDEXAÇÃO AUTOMÁTICA (URL): {url_repo} ===", "INFO")

        # 1. Escaneamento avançado do repositório
        repo_escaneado = await self.scanner.escanear_repositorio_github(url_repo, branch)

        # 2. Executar pipeline de indexação
        return await self._pipeline_indexacao(repo_escaneado)

    async def indexar_repositorio_local(self, caminho_repo: str, branch: str = "main") -> RepositorioIndexado:
        """
        Indexação automática completa de um repositório a partir de um caminho local.
        """
        montar_log(f"=== INICIANDO INDEXAÇÃO AUTOMÁTICA (LOCAL): {caminho_repo} ===", "INFO")

        # 1. Escaneamento avançado do repositório local
        repo_escaneado = await self.scanner.escanear_repositorio_local(caminho_repo)

        # 2. Executar pipeline de indexação
        return await self._pipeline_indexacao(repo_escaneado)

    async def _pipeline_indexacao(self, repo_escaneado: RepositorioEscaneado) -> RepositorioIndexado:
        """Pipeline de indexação comum para repositórios locais e remotos."""
        inicio = time.time()

        try:
            # Criar registro do repositório
            repo_indexado = await self._criar_repositorio_indexado(repo_escaneado)

            # Indexação paralela de entidades
            entidades = await self._extrair_entidades_paralelo(repo_escaneado)

            # Geração de embeddings em lote
            await self._gerar_embeddings_lote(entidades)

            # Análise de relacionamentos
            relacionamentos = await self._analisar_relacionamentos(entidades)

            # Construção do grafo de conhecimento
            await self._construir_grafo_conhecimento(entidades, relacionamentos)

            # Indexação semântica
            await self._indexar_semanticamente(entidades)

            # Persistência otimizada
            await self._persistir_dados_otimizado(repo_indexado, entidades, relacionamentos)

            # Indexação em sistemas externos
            await self._indexar_sistemas_externos(repo_indexado, entidades)

            # Otimização automática
            await self._otimizar_indices()

            # Backup automático
            await self._backup_automatico()

            tempo_total = time.time() - inicio

            # Atualizar estatísticas
            self._atualizar_estatisticas(repo_indexado, entidades, relacionamentos, tempo_total)

            montar_log(f"Repositório indexado automaticamente em {tempo_total:.2f}s", "SUCCESS")
            montar_log(f"Entidades: {len(entidades)}, Relacionamentos: {len(relacionamentos)}", "INFO")

            return repo_indexado

        except Exception as e:
            montar_log(f"Erro no pipeline de indexação: {e}", "ERROR")
            raise

    async def _criar_repositorio_indexado(self, repo_escaneado: RepositorioEscaneado) -> RepositorioIndexado:
        """Cria registro de repositório indexado"""
        repo_id = hashlib.sha256(f"{repo_escaneado.url}_{repo_escaneado.nome}".encode()).hexdigest()

        return RepositorioIndexado(
            id=repo_id,
            nome=repo_escaneado.nome,
            url=repo_escaneado.url,
            branch="main",  # Será atualizado conforme necessário
            hash_commit="",  # Será obtido do Git
            data_indexacao=datetime.now(),
            data_ultima_atualizacao=datetime.now(),
            total_arquivos=repo_escaneado.total_arquivos,
            total_entidades=0,  # Será atualizado
            total_relacionamentos=0,  # Será atualizado
            linguagens=list(repo_escaneado.linguagens_detectadas.keys()),
            frameworks=repo_escaneado.frameworks_utilizados,
            tags=repo_escaneado.tags_projeto,
            qualidade_geral=repo_escaneado.qualidade_geral,
            complexidade_geral=repo_escaneado.complexidade_geral,
            maturidade=repo_escaneado.maturidade_projeto,
            categoria=repo_escaneado.categoria_projeto,
            metadados=repo_escaneado.relatorio_completo,
            estatisticas={}
        )

    async def _extrair_entidades_paralelo(self, repo_escaneado: RepositorioEscaneado) -> List[EntidadeCodigo]:
        """Extrai entidades de código em paralelo"""
        montar_log("Extraindo entidades de código em paralelo...", "INFO")

        entidades = []

        # Processar arquivos em lotes
        arquivos = repo_escaneado.arquivos_escaneados
        lote_tamanho = self.config['batch_size_entidades']

        with ThreadPoolExecutor(max_workers=self.config['max_workers_indexacao']) as executor:
            futures = []

            for i in range(0, len(arquivos), lote_tamanho):
                lote = arquivos[i:i + lote_tamanho]
                future = executor.submit(self._extrair_entidades_lote, lote)
                futures.append(future)

            # Coletar resultados
            for future in futures:
                try:
                    entidades_lote = future.result(timeout=300)
                    entidades.extend(entidades_lote)
                except Exception as e:
                    montar_log(f"Erro no processamento de lote: {e}", "ERROR")

        montar_log(f"Extraídas {len(entidades)} entidades", "SUCCESS")
        return entidades

    def _extrair_entidades_lote(self, arquivos: List[ArquivoEscaneado]) -> List[EntidadeCodigo]:
        """Extrai entidades de um lote de arquivos"""
        entidades = []

        for arquivo in arquivos:
            try:
                # Extrair funções como entidades
                for funcao in arquivo.funcoes:
                    entidade_id = hashlib.sha256(
                        f"{arquivo.caminho}_{funcao['nome']}_{funcao['linha_inicio']}".encode()
                    ).hexdigest()

                    entidade = EntidadeCodigo(
                        id=entidade_id,
                        nome=funcao['nome'],
                        tipo='function',
                        arquivo=arquivo.caminho,
                        linha_inicio=funcao['linha_inicio'],
                        linha_fim=funcao['linha_fim'],
                        linguagem=arquivo.linguagem,
                        assinatura=self._gerar_assinatura_funcao(funcao),
                        documentacao=funcao.get('documentacao', ''),
                        codigo_fonte=funcao.get('codigo', ''),
                        hash_codigo=hashlib.md5(funcao.get('codigo', '').encode()).hexdigest(),
                        complexidade=funcao.get('complexidade', 1),
                        qualidade=arquivo.qualidade_codigo,
                        tags=arquivo.tags_automaticas + [f"lang_{arquivo.linguagem}"],
                        metadados={
                            'parametros': funcao.get('parametros', []),
                            'tipo_retorno': funcao.get('tipo_retorno', 'unknown'),
                            'modificadores': funcao.get('modificadores', []),
                            'chamadas_funcoes': funcao.get('chamadas_funcoes', []),
                            'variaveis_locais': funcao.get('variaveis_locais', [])
                        },
                        relacionamentos=[],
                        embeddings=None,  # Será gerado posteriormente
                        data_criacao=datetime.now(),
                        data_modificacao=arquivo.data_modificacao
                    )

                    entidades.append(entidade)

                # Extrair outras entidades (classes, variáveis globais, etc.)
                # Implementação adicional conforme necessário

            except Exception as e:
                montar_log(f"Erro ao extrair entidades de {arquivo.caminho}: {e}", "WARNING")

        return entidades

    def _gerar_assinatura_funcao(self, funcao: Dict[str, Any]) -> str:
        """Gera assinatura única da função"""
        nome = funcao.get('nome', '')
        parametros = funcao.get('parametros', [])
        tipo_retorno = funcao.get('tipo_retorno', 'unknown')

        assinatura = f"{tipo_retorno} {nome}({', '.join(parametros)})"
        return assinatura

    async def _gerar_embeddings_lote(self, entidades: List[EntidadeCodigo]):
        """Gera embeddings para entidades em lote"""
        montar_log("Gerando embeddings semânticos...", "INFO")

        if not self.indice_semantico.modelo_embeddings:
            montar_log("Modelo de embeddings não disponível", "WARNING")
            return

        # Preparar textos para embedding
        textos = []
        for entidade in entidades:
            # Combinar informações relevantes
            texto = f"{entidade.nome} {entidade.assinatura} {entidade.documentacao} {entidade.codigo_fonte[:500]}"
            textos.append(texto)

        # Gerar embeddings em lote (mais eficiente)
        try:
            embeddings_batch = self.indice_semantico.modelo_embeddings.encode(
                textos,
                batch_size=32,
                show_progress_bar=True,
                convert_to_tensor=False
            )

            # Atribuir embeddings às entidades
            for entidade, embedding in zip(entidades, embeddings_batch):
                entidade.embeddings = embedding.tolist()

            montar_log(f"Embeddings gerados para {len(entidades)} entidades", "SUCCESS")

        except Exception as e:
            montar_log(f"Erro ao gerar embeddings: {e}", "ERROR")

    async def _analisar_relacionamentos(self, entidades: List[EntidadeCodigo]) -> List[RelacionamentoCodigo]:
        """Analisa relacionamentos entre entidades"""
        montar_log("Analisando relacionamentos entre entidades...", "INFO")

        relacionamentos = []

        # Criar mapeamento por arquivo para otimização
        entidades_por_arquivo = defaultdict(list)
        for entidade in entidades:
            entidades_por_arquivo[entidade.arquivo].append(entidade)

        # Analisar relacionamentos dentro de cada arquivo
        for arquivo, entidades_arquivo in entidades_por_arquivo.items():
            relacionamentos.extend(self._analisar_relacionamentos_arquivo(entidades_arquivo))

        # Analisar relacionamentos entre arquivos
        relacionamentos.extend(self._analisar_relacionamentos_inter_arquivos(entidades))

        montar_log(f"Identificados {len(relacionamentos)} relacionamentos", "SUCCESS")
        return relacionamentos

    def _analisar_relacionamentos_arquivo(self, entidades: List[EntidadeCodigo]) -> List[RelacionamentoCodigo]:
        """Analisa relacionamentos dentro de um arquivo"""
        relacionamentos = []

        for i, entidade1 in enumerate(entidades):
            for j, entidade2 in enumerate(entidades):
                if i != j:
                    # Verificar se entidade1 chama entidade2
                    chamadas = entidade1.metadados.get('chamadas_funcoes', [])
                    if entidade2.nome in chamadas:
                        rel_id = hashlib.sha256(f"{entidade1.id}_calls_{entidade2.id}".encode()).hexdigest()

                        relacionamento = RelacionamentoCodigo(
                            id=rel_id,
                            origem_id=entidade1.id,
                            destino_id=entidade2.id,
                            tipo='calls',
                            peso=1.0,
                            contexto=f"{entidade1.nome} chama {entidade2.nome}",
                            metadados={'arquivo': entidade1.arquivo},
                            data_criacao=datetime.now()
                        )

                        relacionamentos.append(relacionamento)

        return relacionamentos

    def _analisar_relacionamentos_inter_arquivos(self, entidades: List[EntidadeCodigo]) -> List[RelacionamentoCodigo]:
        """Analisa relacionamentos entre arquivos"""
        relacionamentos = []

        # Criar índice de entidades por nome para busca rápida
        entidades_por_nome = defaultdict(list)
        for entidade in entidades:
            entidades_por_nome[entidade.nome].append(entidade)

        # Analisar chamadas entre arquivos
        for entidade in entidades:
            chamadas = entidade.metadados.get('chamadas_funcoes', [])

            for chamada in chamadas:
                # Buscar entidades com esse nome em outros arquivos
                entidades_chamadas = entidades_por_nome.get(chamada, [])

                for entidade_chamada in entidades_chamadas:
                    if entidade_chamada.arquivo != entidade.arquivo:
                        rel_id = hashlib.sha256(f"{entidade.id}_calls_external_{entidade_chamada.id}".encode()).hexdigest()

                        relacionamento = RelacionamentoCodigo(
                            id=rel_id,
                            origem_id=entidade.id,
                            destino_id=entidade_chamada.id,
                            tipo='calls_external',
                            peso=0.8,  # Peso menor para chamadas externas
                            contexto=f"{entidade.nome} chama {entidade_chamada.nome} (inter-arquivo)",
                            metadados={
                                'arquivo_origem': entidade.arquivo,
                                'arquivo_destino': entidade_chamada.arquivo
                            },
                            data_criacao=datetime.now()
                        )

                        relacionamentos.append(relacionamento)

        return relacionamentos

    async def _construir_grafo_conhecimento(self, entidades: List[EntidadeCodigo], relacionamentos: List[RelacionamentoCodigo]):
        """Constrói grafo de conhecimento"""
        montar_log("Construindo grafo de conhecimento...", "INFO")

        # Adicionar entidades ao grafo
        for entidade in entidades:
            self.grafo_conhecimento.adicionar_entidade(entidade)

        # Adicionar relacionamentos ao grafo
        for relacionamento in relacionamentos:
            self.grafo_conhecimento.adicionar_relacionamento(relacionamento)

        montar_log("Grafo de conhecimento construído", "SUCCESS")

    async def _indexar_semanticamente(self, entidades: List[EntidadeCodigo]):
        """Indexa entidades semanticamente"""
        montar_log("Indexando semanticamente...", "INFO")

        for entidade in entidades:
            if entidade.embeddings:
                self.indice_semantico.adicionar_entidade(entidade)

        montar_log("Indexação semântica concluída", "SUCCESS")

    async def _persistir_dados_otimizado(self, repo: RepositorioIndexado, entidades: List[EntidadeCodigo], relacionamentos: List[RelacionamentoCodigo]):
        """Persiste dados de forma otimizada"""
        montar_log("Persistindo dados otimizadamente...", "INFO")

        try:
            # Atualizar contadores
            repo.total_entidades = len(entidades)
            repo.total_relacionamentos = len(relacionamentos)

            # Inserir repositório
            self._inserir_repositorio(repo)

            # Inserir entidades em lote
            self._inserir_entidades_lote(entidades, repo.id)

            # Inserir relacionamentos em lote
            self._inserir_relacionamentos_lote(relacionamentos, repo.id)

            # Commit final
            self.conexao_db.commit()

            montar_log("Dados persistidos com sucesso", "SUCCESS")

        except Exception as e:
            self.conexao_db.rollback()
            montar_log(f"Erro ao persistir dados: {e}", "ERROR")
            raise

    def _inserir_repositorio(self, repo: RepositorioIndexado):
        """Insere repositório no banco"""
        sql = """
        INSERT OR REPLACE INTO repositorios (
            id, nome, url, branch, hash_commit, data_indexacao, data_ultima_atualizacao,
            total_arquivos, total_entidades, total_relacionamentos, linguagens, frameworks,
            tags, qualidade_geral, complexidade_geral, maturidade, categoria, metadados, estatisticas
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        self.conexao_db.execute(sql, (
            repo.id, repo.nome, repo.url, repo.branch, repo.hash_commit,
            repo.data_indexacao, repo.data_ultima_atualizacao,
            repo.total_arquivos, repo.total_entidades, repo.total_relacionamentos,
            json.dumps(repo.linguagens), json.dumps(repo.frameworks),
            json.dumps(repo.tags), repo.qualidade_geral, repo.complexidade_geral,
            repo.maturidade, repo.categoria, json.dumps(repo.metadados),
            json.dumps(repo.estatisticas)
        ))

    def _inserir_entidades_lote(self, entidades: List[EntidadeCodigo], repo_id: str):
        """Insere entidades em lote"""
        sql = """
        INSERT OR REPLACE INTO entidades (
            id, repositorio_id, nome, tipo, arquivo, linha_inicio, linha_fim,
            linguagem, assinatura, documentacao, codigo_fonte, hash_codigo,
            complexidade, qualidade, tags, metadados, embeddings,
            data_criacao, data_modificacao
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        dados = []
        for entidade in entidades:
            # Serializar embeddings
            embeddings_blob = None
            if entidade.embeddings:
                embeddings_blob = pickle.dumps(entidade.embeddings)
                if self.config['compressao_ativa']:
                    embeddings_blob = gzip.compress(embeddings_blob)

            dados.append((
                entidade.id, repo_id, entidade.nome, entidade.tipo, entidade.arquivo,
                entidade.linha_inicio, entidade.linha_fim, entidade.linguagem,
                entidade.assinatura, entidade.documentacao, entidade.codigo_fonte,
                entidade.hash_codigo, entidade.complexidade, entidade.qualidade,
                json.dumps(entidade.tags), json.dumps(entidade.metadados),
                embeddings_blob, entidade.data_criacao, entidade.data_modificacao
            ))

        self.conexao_db.executemany(sql, dados)

    def _inserir_relacionamentos_lote(self, relacionamentos: List[RelacionamentoCodigo], repo_id: str):
        """Insere relacionamentos em lote"""
        sql = """
        INSERT OR REPLACE INTO relacionamentos (
            id, repositorio_id, origem_id, destino_id, tipo, peso, contexto, metadados, data_criacao
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        dados = []
        for rel in relacionamentos:
            dados.append((
                rel.id, repo_id, rel.origem_id, rel.destino_id, rel.tipo,
                rel.peso, rel.contexto, json.dumps(rel.metadados), rel.data_criacao
            ))

        self.conexao_db.executemany(sql, dados)

    async def _indexar_sistemas_externos(self, repo: RepositorioIndexado, entidades: List[EntidadeCodigo]):
        """Indexa em sistemas externos (Elasticsearch, etc.)"""
        if self.indice_elasticsearch:
            await self._indexar_elasticsearch(repo, entidades)

    async def _indexar_elasticsearch(self, repo: RepositorioIndexado, entidades: List[EntidadeCodigo]):
        """Indexa no Elasticsearch"""
        try:
            # Criar índice se não existir
            indice_nome = f"biblioteca_alexandria_{repo.id}"

            if not self.indice_elasticsearch.indices.exists(index=indice_nome):
                mapping = {
                    "mappings": {
                        "properties": {
                            "nome": {"type": "text", "analyzer": "standard"},
                            "tipo": {"type": "keyword"},
                            "linguagem": {"type": "keyword"},
                            "arquivo": {"type": "keyword"},
                            "documentacao": {"type": "text"},
                            "codigo_fonte": {"type": "text"},
                            "tags": {"type": "keyword"},
                            "qualidade": {"type": "float"},
                            "complexidade": {"type": "integer"}
                        }
                    }
                }

                self.indice_elasticsearch.indices.create(index=indice_nome, body=mapping)

            # Indexar entidades
            for entidade in entidades:
                doc = {
                    "nome": entidade.nome,
                    "tipo": entidade.tipo,
                    "linguagem": entidade.linguagem,
                    "arquivo": entidade.arquivo,
                    "documentacao": entidade.documentacao,
                    "codigo_fonte": entidade.codigo_fonte[:1000],  # Limitar tamanho
                    "tags": entidade.tags,
                    "qualidade": entidade.qualidade,
                    "complexidade": entidade.complexidade
                }

                self.indice_elasticsearch.index(
                    index=indice_nome,
                    id=entidade.id,
                    body=doc
                )

            montar_log(f"Entidades indexadas no Elasticsearch: {len(entidades)}", "INFO")

        except Exception as e:
            montar_log(f"Erro ao indexar no Elasticsearch: {e}", "WARNING")

    async def _otimizar_indices(self):
        """Otimiza índices automaticamente"""
        try:
            # Otimizar banco SQLite
            self.conexao_db.execute("ANALYZE")
            self.conexao_db.execute("VACUUM")

            # Salvar índice semântico
            indice_path = self.diretorio_base / "indice_semantico"
            self.indice_semantico.salvar_indice(str(indice_path))

            montar_log("Índices otimizados", "INFO")

        except Exception as e:
            montar_log(f"Erro na otimização: {e}", "WARNING")

    async def _backup_automatico(self):
        """Executa backup automático"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = self.diretorio_base / "backups" / timestamp
            backup_dir.mkdir(parents=True, exist_ok=True)

            # Backup do banco principal
            shutil.copy2(self.db_path, backup_dir / "biblioteca.db")

            # Backup do índice semântico
            indice_files = list(self.diretorio_base.glob("indice_semantico.*"))
            for arquivo in indice_files:
                shutil.copy2(arquivo, backup_dir / arquivo.name)

            # Compactar backup se configurado
            if self.config['compressao_ativa']:
                backup_tar = backup_dir.parent / f"{timestamp}.tar.xz"
                shutil.make_archive(str(backup_tar).replace('.tar.xz', ''), 'xztar', backup_dir)
                shutil.rmtree(backup_dir)

            montar_log(f"Backup automático criado: {timestamp}", "INFO")

        except Exception as e:
            montar_log(f"Erro no backup: {e}", "WARNING")

    def _atualizar_estatisticas(self, repo: RepositorioIndexado, entidades: List[EntidadeCodigo], relacionamentos: List[RelacionamentoCodigo], tempo: float):
        """Atualiza estatísticas da biblioteca"""
        self.estatisticas['repositorios_indexados'] += 1
        self.estatisticas['entidades_catalogadas'] += len(entidades)
        self.estatisticas['relacionamentos_mapeados'] += len(relacionamentos)
        self.estatisticas['tempo_total_indexacao'] += tempo
        self.estatisticas['ultima_atualizacao'] = datetime.now().isoformat()

    async def consultar_inteligente(self, query: str, tipo_consulta: str = "semantic", filtros: Dict[str, Any] = None, limite: int = 10) -> ResultadoConsulta:
        """
        Consulta inteligente à biblioteca
        Suporta busca semântica, estrutural, por similaridade e padrões
        """
        montar_log(f"Executando consulta inteligente: {query}", "INFO")

        inicio = time.time()
        consulta_id = hashlib.sha256(f"{query}_{time.time()}".encode()).hexdigest()

        try:
            resultados = []

            if tipo_consulta == "semantic":
                resultados = await self._consulta_semantica(query, filtros, limite)
            elif tipo_consulta == "structural":
                resultados = await self._consulta_estrutural(query, filtros, limite)
            elif tipo_consulta == "similarity":
                resultados = await self._consulta_similaridade(query, filtros, limite)
            elif tipo_consulta == "pattern":
                resultados = await self._consulta_padroes(query, filtros, limite)
            else:
                # Consulta híbrida (combina múltiplos tipos)
                resultados = await self._consulta_hibrida(query, filtros, limite)

            tempo_execucao = time.time() - inicio

            # Calcular score de relevância
            score_relevancia = self._calcular_score_relevancia(resultados, query)

            # Gerar sugestões
            sugestoes = self._gerar_sugestoes(query, resultados)

            # Criar resultado
            resultado_consulta = ResultadoConsulta(
                consulta_id=consulta_id,
                resultados=resultados,
                total_encontrados=len(resultados),
                tempo_execucao=tempo_execucao,
                score_relevancia=score_relevancia,
                sugestoes=sugestoes,
                metadados={
                    'tipo_consulta': tipo_consulta,
                    'filtros': filtros,
                    'timestamp': datetime.now().isoformat()
                }
            )

            # Registrar consulta
            await self._registrar_consulta(query, tipo_consulta, filtros, limite, resultado_consulta)

            # Atualizar estatísticas
            self.estatisticas['consultas_realizadas'] += 1

            montar_log(f"Consulta executada em {tempo_execucao:.2f}s: {len(resultados)} resultados", "SUCCESS")

            return resultado_consulta

        except Exception as e:
            montar_log(f"Erro na consulta inteligente: {e}", "ERROR")
            raise

    async def _consulta_semantica(self, query: str, filtros: Dict[str, Any], limite: int) -> List[Dict[str, Any]]:
        """Consulta semântica usando embeddings"""
        resultados = []

        # Buscar entidades similares semanticamente
        entidades_similares = self.indice_semantico.buscar_similares(query, limite * 2)

        # Buscar detalhes das entidades no banco
        for entidade_id, score in entidades_similares:
            entidade = self._buscar_entidade_por_id(entidade_id)
            if entidade and self._aplicar_filtros(entidade, filtros):
                resultados.append({
                    'entidade': entidade,
                    'score': score,
                    'tipo_match': 'semantic'
                })

        return resultados[:limite]

    async def _consulta_estrutural(self, query: str, filtros: Dict[str, Any], limite: int) -> List[Dict[str, Any]]:
        """Consulta estrutural baseada no grafo de conhecimento"""
        resultados = []

        # Buscar entidades por nome/tipo
        entidades_base = self._buscar_entidades_por_nome(query)

        # Para cada entidade base, buscar relacionadas
        for entidade in entidades_base:
            if self._aplicar_filtros(entidade, filtros):
                # Buscar entidades relacionadas
                relacionadas = self.grafo_conhecimento.buscar_relacionados(entidade['id'], profundidade=2)

                resultados.append({
                    'entidade': entidade,
                    'relacionadas': relacionadas,
                    'score': 1.0,
                    'tipo_match': 'structural'
                })

        return resultados[:limite]

    async def _consulta_similaridade(self, query: str, filtros: Dict[str, Any], limite: int) -> List[Dict[str, Any]]:
        """Consulta por similaridade de código"""
        resultados = []

        # Buscar entidades com código similar
        cursor = self.conexao_db.execute(
            "SELECT * FROM entidades WHERE codigo_fonte LIKE ? LIMIT ?",
            (f"%{query}%", limite * 2)
        )

        for row in cursor.fetchall():
            entidade = self._row_to_entidade(row)
            if self._aplicar_filtros(entidade, filtros):
                # Calcular similaridade de código
                score = self._calcular_similaridade_codigo(query, entidade['codigo_fonte'])

                resultados.append({
                    'entidade': entidade,
                    'score': score,
                    'tipo_match': 'similarity'
                })

        # Ordenar por score
        resultados.sort(key=lambda x: x['score'], reverse=True)

        return resultados[:limite]

    async def _consulta_padroes(self, query: str, filtros: Dict[str, Any], limite: int) -> List[Dict[str, Any]]:
        """Consulta por padrões de código"""
        resultados = []

        # Buscar por padrões específicos
        padroes_query = self._extrair_padroes_query(query)

        for padrao in padroes_query:
            cursor = self.conexao_db.execute(
                "SELECT * FROM entidades WHERE tags LIKE ? OR metadados LIKE ? LIMIT ?",
                (f"%{padrao}%", f"%{padrao}%", limite)
            )

            for row in cursor.fetchall():
                entidade = self._row_to_entidade(row)
                if self._aplicar_filtros(entidade, filtros):
                    resultados.append({
                        'entidade': entidade,
                        'padrao_encontrado': padrao,
                        'score': 0.8,
                        'tipo_match': 'pattern'
                    })

        return resultados[:limite]

    async def _consulta_hibrida(self, query: str, filtros: Dict[str, Any], limite: int) -> List[Dict[str, Any]]:
        """Consulta híbrida combinando múltiplos tipos"""
        resultados_finais = []

        # Executar diferentes tipos de consulta
        resultados_semanticos = await self._consulta_semantica(query, filtros, limite // 2)
        resultados_estruturais = await self._consulta_estrutural(query, filtros, limite // 4)
        resultados_similaridade = await self._consulta_similaridade(query, filtros, limite // 4)

        # Combinar e rankear resultados
        todos_resultados = resultados_semanticos + resultados_estruturais + resultados_similaridade

        # Remover duplicatas e rankear
        entidades_vistas = set()
        for resultado in todos_resultados:
            entidade_id = resultado['entidade']['id']
            if entidade_id not in entidades_vistas:
                entidades_vistas.add(entidade_id)
                resultados_finais.append(resultado)

        # Ordenar por score combinado
        resultados_finais.sort(key=lambda x: x['score'], reverse=True)

        return resultados_finais[:limite]

    def _buscar_entidade_por_id(self, entidade_id: str) -> Optional[Dict[str, Any]]:
        """Busca entidade por ID"""
        cursor = self.conexao_db.execute(
            "SELECT * FROM entidades WHERE id = ?",
            (entidade_id,)
        )

        row = cursor.fetchone()
        return self._row_to_entidade(row) if row else None

    def _buscar_entidades_por_nome(self, nome: str) -> List[Dict[str, Any]]:
        """Busca entidades por nome"""
        cursor = self.conexao_db.execute(
            "SELECT * FROM entidades WHERE nome LIKE ? LIMIT 50",
            (f"%{nome}%",)
        )

        return [self._row_to_entidade(row) for row in cursor.fetchall()]

    def _row_to_entidade(self, row) -> Dict[str, Any]:
        """Converte row do banco para dicionário de entidade"""
        if not row:
            return None

        # Desserializar embeddings se existir
        embeddings = None
        if row[16]:  # embeddings blob
            try:
                embeddings_blob = row[16]
                if self.config['compressao_ativa']:
                    embeddings_blob = gzip.decompress(embeddings_blob)
                embeddings = pickle.loads(embeddings_blob)
            except Exception:
                pass

        return {
            'id': row[0],
            'repositorio_id': row[1],
            'nome': row[2],
            'tipo': row[3],
            'arquivo': row[4],
            'linha_inicio': row[5],
            'linha_fim': row[6],
            'linguagem': row[7],
            'assinatura': row[8],
            'documentacao': row[9],
            'codigo_fonte': row[10],
            'hash_codigo': row[11],
            'complexidade': row[12],
            'qualidade': row[13],
            'tags': json.loads(row[14]) if row[14] else [],
            'metadados': json.loads(row[15]) if row[15] else {},
            'embeddings': embeddings,
            'data_criacao': row[17],
            'data_modificacao': row[18]
        }

    def _aplicar_filtros(self, entidade: Dict[str, Any], filtros: Dict[str, Any]) -> bool:
        """Aplica filtros à entidade"""
        if not filtros:
            return True

        for chave, valor in filtros.items():
            if chave == 'linguagem' and entidade.get('linguagem') != valor:
                return False
            elif chave == 'tipo' and entidade.get('tipo') != valor:
                return False
            elif chave == 'qualidade_min' and entidade.get('qualidade', 0) < valor:
                return False
            elif chave == 'complexidade_max' and entidade.get('complexidade', 0) > valor:
                return False
            elif chave == 'tags' and not any(tag in entidade.get('tags', []) for tag in valor):
                return False

        return True

    def _calcular_similaridade_codigo(self, query: str, codigo: str) -> float:
        """Calcula similaridade entre query e código"""
        # Implementação simplificada - poderia usar algoritmos mais sofisticados
        query_words = set(query.lower().split())
        codigo_words = set(codigo.lower().split())

        if not query_words:
            return 0.0

        intersecao = len(query_words.intersection(codigo_words))
        uniao = len(query_words.union(codigo_words))

        return intersecao / uniao if uniao > 0 else 0.0

    def _extrair_padroes_query(self, query: str) -> List[str]:
        """Extrai padrões da query"""
        # Padrões comuns de programação
        padroes = []

        query_lower = query.lower()

        if 'singleton' in query_lower:
            padroes.append('singleton')
        if 'factory' in query_lower:
            padroes.append('factory')
        if 'observer' in query_lower:
            padroes.append('observer')
        if 'mvc' in query_lower:
            padroes.append('mvc')

        # Adicionar a própria query como padrão
        padroes.append(query.strip())

        return padroes

    def _calcular_score_relevancia(self, resultados: List[Dict[str, Any]], query: str) -> float:
        """Calcula score geral de relevância dos resultados"""
        if not resultados:
            return 0.0

        scores = [r.get('score', 0.0) for r in resultados]
        return sum(scores) / len(scores)

    def _gerar_sugestoes(self, query: str, resultados: List[Dict[str, Any]]) -> List[str]:
        """Gera sugestões baseadas na query e resultados"""
        sugestoes = []

        # Sugestões baseadas em entidades encontradas
        linguagens = set()
        tipos = set()

        for resultado in resultados[:5]:  # Primeiros 5 resultados
            entidade = resultado.get('entidade', {})
            linguagens.add(entidade.get('linguagem', ''))
            tipos.add(entidade.get('tipo', ''))

        # Gerar sugestões
        for linguagem in linguagens:
            if linguagem and linguagem != 'unknown':
                sugestoes.append(f"{query} linguagem:{linguagem}")

        for tipo in tipos:
            if tipo:
                sugestoes.append(f"{query} tipo:{tipo}")

        return sugestoes[:5]  # Máximo 5 sugestões

    async def _registrar_consulta(self, query: str, tipo_consulta: str, filtros: Dict[str, Any], limite: int, resultado: ResultadoConsulta):
        """Registra consulta no banco para análise"""
        try:
            sql = """
            INSERT INTO consultas (
                id, query, tipo_consulta, filtros, limite, timestamp, usuario, contexto,
                resultados, tempo_execucao, score_relevancia
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            self.conexao_db.execute(sql, (
                resultado.consulta_id, query, tipo_consulta, json.dumps(filtros or {}),
                limite, datetime.now(), 'sistema', json.dumps({}),
                json.dumps([r.get('entidade', {}).get('id') for r in resultado.resultados]),
                resultado.tempo_execucao, resultado.score_relevancia
            ))

            self.conexao_db.commit()

        except Exception as e:
            montar_log(f"Erro ao registrar consulta: {e}", "WARNING")

    def obter_estatisticas_completas(self) -> Dict[str, Any]:
        """Obtém estatísticas completas da biblioteca"""
        stats_grafo = self.grafo_conhecimento.obter_estatisticas()
        stats_scanner = self.scanner.obter_estatisticas()

        return {
            'sistema': self.estatisticas,
            'grafo_conhecimento': stats_grafo,
            'scanner': stats_scanner,
            'configuracao': self.config,
            'componentes_disponiveis': {
                'neo4j': NEO4J_AVAILABLE,
                'redis': REDIS_AVAILABLE,
                'elasticsearch': ELASTICSEARCH_AVAILABLE,
                'faiss': FAISS_AVAILABLE,
                'sentence_transformers': SENTENCE_TRANSFORMERS_AVAILABLE,
                'spacy': SPACY_AVAILABLE,
                'networkx': NETWORKX_AVAILABLE
            }
        }

    def limpar_cache(self):
        """Limpa todos os caches"""
        self.scanner.limpar_cache()
        self.indice_semantico.embeddings_cache.clear()

        if self.cache_redis:
            try:
                self.cache_redis.flushdb()
            except Exception:
                pass

        montar_log("Cache da biblioteca limpo", "INFO")

    def fechar(self):
        """Fecha conexões e libera recursos"""
        try:
            if self.conexao_db:
                self.conexao_db.close()

            if self.grafo_conhecimento.conexao_neo4j:
                self.grafo_conhecimento.conexao_neo4j.close()

            montar_log("Biblioteca de Alexandria fechada", "INFO")

        except Exception as e:
            montar_log(f"Erro ao fechar biblioteca: {e}", "WARNING")

    def __del__(self):
        """Destrutor para garantir limpeza"""
        try:
            self.fechar()
        except:
            pass  # noqa: bare-except — non-critical fallback