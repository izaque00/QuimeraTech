"""
Quimera Mark X — Async Session & Repository Layer

Adds async SQLAlchemy support alongside existing sync base.py.
Usage:
    from quimera.db.session import get_session, create_repos
    
    async with get_session() as session:
        repos = create_repos(session)
        mission = await repos["missions"].create(...)
"""

import os
import logging
from typing import Optional, AsyncGenerator, List, Dict, Any
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text, select, func as sql_func

from .base import Base
from . import models  # noqa: register all models with Base

logger = logging.getLogger("quimera.db.session")

DATABASE_URL = os.getenv(
    "QUIMERA_DATABASE_URL",
    "sqlite+aiosqlite:///quimera_markx.db"
)

_engine = None
_async_session_factory = None


def get_async_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            DATABASE_URL,
            echo=False,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
    return _engine


def get_async_session_factory():
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            get_async_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


async def init_db_async():
    """Create all tables via Base.metadata (dev mode)."""
    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Async DB tables created.")


async def check_db_health() -> bool:
    try:
        engine = get_async_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"DB health check failed: {e}")
        return False


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_async_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_scope():
    factory = get_async_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Generic CRUD ────────────────────────────────────────────────────

class BaseRepo:
    def __init__(self, model, session: AsyncSession):
        self.model = model
        self.session = session

    async def get(self, id):
        return await self.session.get(self.model, id)

    async def list(self, limit=100, offset=0, **filters):
        stmt = select(self.model).filter_by(**filters).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, **kwargs):
        obj = self.model(**kwargs)
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def update(self, id, **kwargs):
        obj = await self.session.get(self.model, id)
        if obj is None:
            return None
        for k, v in kwargs.items():
            if hasattr(obj, k):
                setattr(obj, k, v)
        await self.session.flush()
        return obj

    async def delete(self, id):
        obj = await self.session.get(self.model, id)
        if obj is None:
            return False
        await self.session.delete(obj)
        await self.session.flush()
        return True

    async def count(self, **filters):
        stmt = select(sql_func.count()).select_from(self.model).filter_by(**filters)
        result = await self.session.execute(stmt)
        return result.scalar_one()


# ── Specialized Repos ───────────────────────────────────────────────

class MissionRepo(BaseRepo):
    async def get_with_patches(self, mission_id):
        from sqlalchemy.orm import selectinload
        stmt = select(self.model).options(selectinload(self.model.patches)).where(self.model.id == mission_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active(self, limit=50):
        stmt = select(self.model).where(
            self.model.status.in_(["pending", "in_progress"])
        ).order_by(self.model.priority.desc(), self.model.created_at.asc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class VulnerabilityRepo(BaseRepo):
    async def get_open(self, severity=None):
        stmt = select(self.model).where(self.model.status == "open")
        if severity:
            stmt = stmt.where(self.model.severity == severity)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class CVECacheRepo(BaseRepo):
    async def upsert(self, cve_id, **kwargs):
        existing = await self.get(cve_id)
        if existing:
            return await self.update(cve_id, **kwargs)
        return await self.create(cve_id=cve_id, **kwargs)


class GeneticPopulationRepo(BaseRepo):
    async def get_by_mission_gen(self, mission_id, generation):
        stmt = select(self.model).where(
            self.model.mission_id == mission_id,
            self.model.generation == generation
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class PluginRegistryRepo(BaseRepo):
    async def get_active_for_language(self, language):
        stmt = select(self.model).where(
            self.model.language == language,
            self.model.status == "active"
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class CoevolutionRepo(BaseRepo):
    async def get_by_mission(self, mission_id):
        stmt = select(self.model).where(
            self.model.mission_id == mission_id
        ).order_by(self.model.generation)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


# ── Repo Factory ────────────────────────────────────────────────────

def create_repos(session: AsyncSession) -> Dict[str, BaseRepo]:
    return {
        "missions": MissionRepo(models.Mission, session),
        "patches": BaseRepo(models.Patch, session),
        "agents": BaseRepo(models.Agent, session),
        "vulnerabilities": VulnerabilityRepo(models.Vulnerability, session),
        "cve_cache": CVECacheRepo(models.CVECache, session),
        "fuzzing_sessions": BaseRepo(models.FuzzingSession, session),
        "genetic_populations": GeneticPopulationRepo(models.GeneticPopulation, session),
        "genetic_individuals": BaseRepo(models.GeneticIndividual, session),
        "coevolution_sessions": CoevolutionRepo(models.CoevolutionSession, session),
        "plugin_registry": PluginRegistryRepo(models.PluginRegistry, session),
        "multi_lang_files": BaseRepo(models.MultiLangFile, session),
        "ide_sessions": BaseRepo(models.IDESession, session),
        "supply_chain_checks": BaseRepo(models.SupplyChainCheck, session),
    }
