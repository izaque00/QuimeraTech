from contextlib import contextmanager
# quimera/db/base.py

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from typing import Generator

# Importa a URL do banco de dados do arquivo de configuração centralizado.
from quimera import config

# Configuração do logger para este módulo.
logger = logging.getLogger(__name__)

# --- Configuração do Engine do SQLAlchemy ---

# Cria o motor (engine) de conexão com o banco de dados.
# O engine é a interface de baixo nível para o DB.
# 'connect_args' é passado diretamente para o driver do DB (DBAPI).
# {"check_same_thread": False} é um requisito específico para SQLite
# para permitir que a conexão seja usada em mais de um thread.
try:
    engine = create_engine(
        config.DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False  # Mantenha como False em produção para não poluir os logs com queries SQL.
    )
    logger.info(f"Engine do banco de dados configurado para: {config.DATABASE_URL}")
except Exception as e:
    logger.critical(f"Falha crítica ao criar o engine do banco de dados: {e}", exc_info=True)
    raise

# --- Configuração da Base Declarativa ---

# Cria uma classe Base da qual todos os modelos ORM (tabelas) irão herdar.
# Este é o padrão moderno do SQLAlchemy 2.0+.
class Base(DeclarativeBase):
    pass

# --- Configuração da Sessão ---

# Cria uma "fábrica" de sessões configurada (SessionLocal).
# Cada instância de SessionLocal será uma nova sessão de banco de dados.
# A sessão é a interface principal para interagir com o DB em um nível mais alto (ORM).
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """
    Inicializa o banco de dados, criando todas as tabelas definidas nos modelos.
    Esta função deve ser chamada uma vez na inicialização do aplicativo principal
    (ex: em __main__.py) para garantir que o schema do DB esteja pronto.
    """
    try:
        logger.info("Inicializando o schema do banco de dados...")
        # Importa todos os modelos aqui, dentro da função.
        # Isso é crucial para garantir que os modelos sejam registrados com a 'Base'
        # antes de 'create_all' ser chamado, e evita problemas de importação circular.
        from quimera.db import models

        Base.metadata.create_all(bind=engine)
        logger.info("Tabelas do banco de dados verificadas/criadas com sucesso.")
    except Exception as e:
        logger.critical(f"Falha ao inicializar o banco de dados: {e}", exc_info=True)
        raise

@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Função geradora que fornece uma sessão de banco de dados para uma transação.
    Este padrão garante que a sessão seja sempre fechada corretamente, mesmo
    se ocorrerem erros.

    Uso recomendado:
    with get_db() as db:
        # use a sessão 'db' aqui
        ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()