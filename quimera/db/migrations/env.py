# quimera/db/migrations/env.py
"""
Environment configuration for Alembic migrations.

Configurado para auto-detectar modelos do Quimera
e gerar migrações automaticamente.
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Adiciona raiz do projeto ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

# Config Alembic
config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata dos modelos
from quimera.db.base import Base
target_metadata = Base.metadata

# URL do banco via EnvConfig
from quimera.core.env_config import env
config.set_main_option("sqlalchemy.url", env.DATABASE_URL.replace("sqlite:///./", "sqlite:///"))


def run_migrations_offline() -> None:
    """Executa migrações em modo offline (gera SQL)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Executa migrações em modo online (conecta ao banco)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
