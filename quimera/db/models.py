# quimera/db/models.py
# Quimera Mark X — Complete ORM Models
# Merged: 7 legacy models + 12 new models from migrations 001-004

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, JSON, Boolean, Float, ForeignKey
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from quimera.db.base import Base


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


# ═══════════════════════════════════════════════════════════════════
# LEGACY MODELS (existing in FINAL, keep unchanged)
# ═══════════════════════════════════════════════════════════════════

class ScriptProfile(Base):
    __tablename__ = "perfis_script"
    id = Column(Integer, primary_key=True, index=True)
    caminho_arquivo = Column(String, unique=True, index=True, nullable=False)
    hash_atual = Column(String(64), index=True, nullable=False)
    ultima_modificacao = Column(DateTime(timezone=True), onupdate=func.now(), default=func.now())
    patches = relationship("HistoricoPatch", back_populates="perfil_script", cascade="all, delete-orphan")
    drifts = relationship("RegistroDrift", back_populates="perfil_script", cascade="all, delete-orphan")


class HistoricoPatch(Base):
    __tablename__ = "historico_patches"
    id = Column(Integer, primary_key=True, index=True)
    patch_id = Column(String(64), unique=True, index=True, nullable=False)
    perfil_script_id = Column(Integer, ForeignKey("perfis_script.id"), nullable=False)
    conteudo_patch = Column(Text, nullable=False)
    timestamp_aplicacao = Column(DateTime(timezone=True), default=func.now())
    status = Column(String, default="proposto", nullable=False)
    agente_criador = Column(String, nullable=False)
    score_avaliacao = Column(Float, nullable=True)
    comentario = Column(Text, nullable=True)
    perfil_script = relationship("ScriptProfile", back_populates="patches")


class RegistroDrift(Base):
    __tablename__ = "registros_drift"
    id = Column(Integer, primary_key=True, index=True)
    perfil_script_id = Column(Integer, ForeignKey("perfis_script.id"), nullable=False)
    tipo_drift = Column(String, nullable=False)
    score_drift = Column(Float, nullable=False)
    detectado_em = Column(DateTime(timezone=True), default=func.now())
    detalhes = Column(Text, nullable=True)
    resolvido = Column(Boolean, default=False, nullable=False)
    perfil_script = relationship("ScriptProfile", back_populates="drifts")


class MetricaAgente(Base):
    __tablename__ = "metricas_agentes"
    id = Column(Integer, primary_key=True, index=True)
    nome_modelo = Column(String, unique=True, index=True, nullable=False)
    usos = Column(Integer, default=0, nullable=False)
    score_total = Column(Float, default=0.0, nullable=False)
    sucessos = Column(Integer, default=0, nullable=False)


class MissaoTecnica(Base):
    __tablename__ = "missoes_tecnicas"
    id = Column(Integer, primary_key=True, index=True)
    iniciada_em = Column(DateTime(timezone=True), default=func.now())
    finalizada_em = Column(DateTime(timezone=True), nullable=True)
    log_erro_inicial = Column(Text, nullable=False)
    status_final = Column(String, nullable=False)
    mensagem_final = Column(Text, nullable=True)
    patch_vencedor_id = Column(Integer, ForeignKey("historico_patches.id"), nullable=True)
    patch_vencedor = relationship("HistoricoPatch")


class HistoricoRefatoracao(Base):
    __tablename__ = "historico_refatoracao"
    id = Column(Integer, primary_key=True, index=True)
    modelo_gerador = Column(String, nullable=False)
    log_erro_original = Column(Text, nullable=False)
    analise_causa_raiz = Column(JSON, nullable=False)
    patch_content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=func.now())


class EntradaAnaliseModel(Base):
    __tablename__ = "entradas_analise"
    id = Column(Integer, primary_key=True, index=True)
    modelo = Column(String, nullable=False)
    log_bruto = Column(Text, nullable=False)
    resultado = Column(JSON, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=func.now())


# ═══════════════════════════════════════════════════════════════════
# NEW MODELS — Migration 001: Core Tables
# ═══════════════════════════════════════════════════════════════════

class Mission(Base):
    __tablename__ = "missions"
    id = Column(String(64), primary_key=True, default=_new_id)
    type = Column(String(32), nullable=False, index=True)
    status = Column(String(16), nullable=False, default="pending", server_default="pending")
    target_file = Column(String(512), nullable=False)
    original_code = Column(Text, nullable=True)
    patched_code = Column(Text, nullable=True)
    error_context = Column(Text, nullable=True)
    language = Column(String(16), nullable=False, default="c", server_default="c")
    priority = Column(Integer, nullable=False, default=0, server_default="0")
    max_attempts = Column(Integer, nullable=False, default=3, server_default="3")
    attempt_count = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    patches = relationship("Patch", back_populates="mission", lazy="selectin")
    populations = relationship("GeneticPopulation", back_populates="mission", lazy="selectin")
    coevolution_sessions = relationship("CoevolutionSession", back_populates="mission", lazy="selectin")


class Patch(Base):
    __tablename__ = "patches"
    id = Column(String(64), primary_key=True, default=_new_id)
    mission_id = Column(String(64), ForeignKey("missions.id"), nullable=False, index=True)
    patch_code = Column(Text, nullable=False)
    original_code = Column(Text, nullable=True)
    diff_unified = Column(Text, nullable=True)
    fitness_score = Column(Float, nullable=True)
    generation = Column(Integer, nullable=True)
    status = Column(String(16), nullable=False, default="pending", server_default="pending")
    created_by_agent = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    applied_at = Column(DateTime, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    mission = relationship("Mission", back_populates="patches")
    vulnerabilities = relationship("Vulnerability", back_populates="patch", lazy="selectin")
    supply_chain_checks = relationship("SupplyChainCheck", back_populates="patch", lazy="selectin")


class Agent(Base):
    __tablename__ = "agents"
    id = Column(String(64), primary_key=True, default=_new_id)
    name = Column(String(128), nullable=False)
    type = Column(String(32), nullable=False, index=True)
    language = Column(String(16), nullable=False)
    version = Column(String(16), nullable=False, default="1.0.0", server_default="1.0.0")
    status = Column(String(16), nullable=False, default="active", server_default="active")
    total_missions = Column(Integer, nullable=False, default=0, server_default="0")
    successful_missions = Column(Integer, nullable=False, default=0, server_default="0")
    avg_fitness = Column(Float, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    config_json = Column(JSON, nullable=True)


# ═══════════════════════════════════════════════════════════════════
# NEW MODELS — Migration 002: Security Tables
# ═══════════════════════════════════════════════════════════════════

class Vulnerability(Base):
    __tablename__ = "vulnerabilities"
    id = Column(String(64), primary_key=True, default=_new_id)
    patch_id = Column(String(64), ForeignKey("patches.id"), nullable=True, index=True)
    cve_id = Column(String(32), nullable=True, index=True)
    type = Column(String(32), nullable=False, index=True)
    severity = Column(String(16), nullable=False, default="MEDIUM", server_default="MEDIUM")
    description = Column(Text, nullable=False)
    location_file = Column(String(256), nullable=True)
    location_line = Column(Integer, nullable=True)
    exploit_code = Column(Text, nullable=True)
    remediation = Column(Text, nullable=True)
    status = Column(String(16), nullable=False, default="open", server_default="open")
    detected_by = Column(String(64), nullable=True)
    detected_at = Column(DateTime, nullable=False, server_default=func.now())
    resolved_at = Column(DateTime, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    patch = relationship("Patch", back_populates="vulnerabilities")


class CVECache(Base):
    __tablename__ = "cve_cache"
    cve_id = Column(String(32), primary_key=True)
    description = Column(Text, nullable=True)
    severity = Column(String(16), nullable=True)
    cvss_score = Column(Float, nullable=True)
    cwe_ids = Column(JSON, nullable=True)
    affected_products = Column(JSON, nullable=True)
    patch_links = Column(JSON, nullable=True)
    published_date = Column(DateTime, nullable=True)
    last_modified = Column(DateTime, nullable=True)
    fetched_at = Column(DateTime, nullable=False, server_default=func.now())
    raw_json = Column(JSON, nullable=True)


class FuzzingSession(Base):
    __tablename__ = "fuzzing_sessions"
    id = Column(String(64), primary_key=True, default=_new_id)
    target_file = Column(String(256), nullable=False)
    strategy = Column(String(32), nullable=False, default="mutation", server_default="mutation")
    total_iterations = Column(Integer, nullable=False, default=0, server_default="0")
    unique_crashes = Column(Integer, nullable=False, default=0, server_default="0")
    coverage_pct = Column(Float, nullable=True)
    executions_per_second = Column(Float, nullable=True)
    started_at = Column(DateTime, nullable=False, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Float, nullable=True)
    crash_data = Column(JSON, nullable=True)


# ═══════════════════════════════════════════════════════════════════
# NEW MODELS — Migration 003: Evolution Tables
# ═══════════════════════════════════════════════════════════════════

class GeneticPopulation(Base):
    __tablename__ = "genetic_populations"
    id = Column(String(64), primary_key=True, default=_new_id)
    mission_id = Column(String(64), ForeignKey("missions.id"), nullable=False, index=True)
    generation = Column(Integer, nullable=False)
    population_size = Column(Integer, nullable=False)
    best_fitness = Column(Float, nullable=True)
    avg_fitness = Column(Float, nullable=True)
    median_fitness = Column(Float, nullable=True)
    diversity = Column(Float, nullable=True)
    pareto_front_size = Column(Integer, nullable=True)
    elapsed_ms = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    individuals_json = Column(JSON, nullable=True)
    mission = relationship("Mission", back_populates="populations")
    individuals = relationship("GeneticIndividual", back_populates="population", lazy="selectin")


class GeneticIndividual(Base):
    __tablename__ = "genetic_individuals"
    id = Column(String(64), primary_key=True, default=_new_id)
    population_id = Column(String(64), ForeignKey("genetic_populations.id"), nullable=False, index=True)
    patch_id = Column(String(64), ForeignKey("patches.id"), nullable=True)
    patch_code = Column(Text, nullable=True)
    fitness_json = Column(JSON, nullable=True)
    generation_born = Column(Integer, nullable=False)
    parent_ids = Column(JSON, nullable=True)
    pareto_rank = Column(Integer, nullable=True)
    crowding_distance = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    population = relationship("GeneticPopulation", back_populates="individuals")


class CoevolutionSession(Base):
    __tablename__ = "coevolution_sessions"
    id = Column(String(64), primary_key=True, default=_new_id)
    mission_id = Column(String(64), ForeignKey("missions.id"), nullable=True, index=True)
    generation = Column(Integer, nullable=False)
    patch_best_fitness = Column(Float, nullable=True)
    test_best_effectiveness = Column(Float, nullable=True)
    arms_race_intensity = Column(Float, nullable=True)
    robust_patches_count = Column(Integer, nullable=True)
    elapsed_ms = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    tests_json = Column(JSON, nullable=True)
    mission = relationship("Mission", back_populates="coevolution_sessions")


# ═══════════════════════════════════════════════════════════════════
# NEW MODELS — Migration 004: Multi-Language Tables
# ═══════════════════════════════════════════════════════════════════

class PluginRegistry(Base):
    __tablename__ = "plugin_registry"
    id = Column(String(64), primary_key=True, default=_new_id)
    name = Column(String(128), nullable=False)
    language = Column(String(32), nullable=False, index=True)
    version = Column(String(16), nullable=False, default="1.0.0", server_default="1.0.0")
    class_name = Column(String(128), nullable=False)
    module_path = Column(String(256), nullable=False)
    status = Column(String(16), nullable=False, default="active", server_default="active")
    capabilities = Column(JSON, nullable=True)
    registered_at = Column(DateTime, nullable=False, server_default=func.now())
    last_health_check = Column(DateTime, nullable=True)
    metadata_json = Column(JSON, nullable=True)


class MultiLangFile(Base):
    __tablename__ = "multi_lang_files"
    id = Column(String(64), primary_key=True, default=_new_id)
    file_path = Column(String(512), nullable=False)
    language = Column(String(32), nullable=False, index=True)
    original_code = Column(Text, nullable=True)
    patched_code = Column(Text, nullable=True)
    issues_found = Column(Integer, nullable=False, default=0, server_default="0")
    issues_fixed = Column(Integer, nullable=False, default=0, server_default="0")
    agent_used = Column(String(64), nullable=True)
    verified = Column(Boolean, nullable=False, default=False, server_default="false")
    processed_at = Column(DateTime, nullable=False, server_default=func.now())
    repair_duration_ms = Column(Float, nullable=True)
    issues_json = Column(JSON, nullable=True)


class IDESession(Base):
    __tablename__ = "ide_sessions"
    id = Column(String(64), primary_key=True, default=_new_id)
    ide_type = Column(String(32), nullable=False)
    ide_version = Column(String(32), nullable=True)
    workspace_path = Column(String(512), nullable=True)
    files_processed = Column(Integer, nullable=False, default=0, server_default="0")
    total_repairs = Column(Integer, nullable=False, default=0, server_default="0")
    session_start = Column(DateTime, nullable=False, server_default=func.now())
    session_end = Column(DateTime, nullable=True)
    commands_executed = Column(JSON, nullable=True)


class SupplyChainCheck(Base):
    __tablename__ = "supply_chain_checks"
    id = Column(String(64), primary_key=True, default=_new_id)
    file_path = Column(String(512), nullable=False, index=True)
    patch_id = Column(String(64), ForeignKey("patches.id"), nullable=True)
    vulnerable_deps = Column(JSON, nullable=True)
    license_issues = Column(JSON, nullable=True)
    third_party_detected = Column(Boolean, nullable=False, default=False, server_default="false")
    risk_score = Column(Float, nullable=True)
    checked_at = Column(DateTime, nullable=False, server_default=func.now())
    patch = relationship("Patch", back_populates="supply_chain_checks")

PatchHistory = HistoricoPatch
DriftRecord = RegistroDrift
Artifact = EntradaAnaliseModel
AgentMetric = MetricaAgente
