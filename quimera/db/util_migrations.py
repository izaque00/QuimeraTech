# quimera/db/util_migrations.py
"""
Utilitários para integração de migrações no ciclo de vida do Quimera.

Substitui Base.metadata.create_all() por Alembic upgrade.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def run_migrations(alembic_ini_path: Optional[str] = None) -> bool:
    """Executa migrações pendentes via Alembic.
    
    Args:
        alembic_ini_path: Caminho para alembic.ini. Default: db/migrations/alembic.ini
        
    Returns:
        True se migrações foram aplicadas com sucesso.
    """
    try:
        from alemic import command
        from alembic.config import Config
        
        if alembic_ini_path is None:
            base = Path(__file__).parent
            alembic_ini_path = str(base / "migrations" / "alembic.ini")
        
        alembic_cfg = Config(alembic_ini_path)
        command.upgrade(alembic_cfg, "head")
        logger.info("Migrações aplicadas com sucesso.")
        return True
        
    except ImportError:
        logger.warning("Alembic não instalado. Instale com: pip install alembic")
        logger.warning("Usando fallback: Base.metadata.create_all()")
        _fallback_create_all()
        return False
    except Exception as e:
        logger.error(f"Erro ao executar migrações: {e}")
        logger.warning("Usando fallback: Base.metadata.create_all()")
        _fallback_create_all()
        return False


def _fallback_create_all():
    """Fallback: cria tabelas via SQLAlchemy."""
    from quimera.db.base import Base, engine
    from quimera.db import models  # noqa: registra modelos
    Base.metadata.create_all(bind=engine)
    logger.info("Fallback: tabelas criadas via create_all()")


def generate_migration(message: str = "auto") -> bool:
    """Gera uma nova migração automaticamente.
    
    Args:
        message: Descrição da migração.
        
    Returns:
        True se migração foi gerada com sucesso.
    """
    try:
        from alembic import command
        from alembic.config import Config
        
        base = Path(__file__).parent
        alembic_ini = str(base / "migrations" / "alembic.ini")
        alembic_cfg = Config(alembic_ini)
        
        command.revision(alembic_cfg, autogenerate=True, message=message)
        logger.info(f"Migração gerada: '{message}'")
        return True
        
    except ImportError:
        logger.warning("Alembic não instalado. Instale com: pip install alembic")
        return False
    except Exception as e:
        logger.error(f"Erro ao gerar migração: {e}")
        return False
