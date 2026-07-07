# quimera/testes/test_db.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
import hashlib
import os

# Importações dos módulos do DB
from quimera.db.base import Base, get_db, init_db
from quimera.db.models import ScriptProfile, PatchHistory, DriftRecord, AgentMetric, Artifact
from quimera.db.service import (
    create_script_profile, get_script_profile_by_hash, get_script_profile_by_path,
    create_patch_history, get_patch_by_id, get_patches_for_script,
    create_drift_record, get_unresolved_drifts_for_script, mark_drift_as_resolved,
    create_agent_metric, get_latest_agent_metrics,
    create_artifact, get_artifact_by_key
)
from quimera.db import schemas # Para usar os Pydantic schemas

# Configuração de um banco de dados SQLite em memória para testes (isolado)
TEST_DATABASE_URL = "sqlite:///:memory:"

# --- Fixtures para Testes ---
@pytest.fixture(scope="module")
def setup_test_db():
    """Configura um banco de dados em memória para os testes do módulo."""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Substitui a função get_db globalmente para usar o DB de teste
    with patch('quimera.db.base.engine', new=engine), \
         patch('quimera.db.base.SessionLocal', new=SessionLocal):
        yield

    # Limpeza do DB após os testes do módulo
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session(setup_test_db):
    """Retorna uma sessão de DB para cada teste, garantindo que seja fechada."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback() # Garante que as mudanças sejam desfeitas após cada teste
        session.close()

# --- Funções Auxiliares para Testes ---
def criar_hash_mock(content: str) -> str:
    """Função auxiliar para criar hashes mock."""
    return hashlib.sha256(content.encode()).hexdigest()[:64]

# --- Testes para ScriptProfile ---
def test_create_script_profile(db_session: Session):
    path = "/app/test_script.py"
    code = "print('Hello')"
    script_hash = criar_hash_mock(code)

    script_data = schemas.ScriptProfileCreate(file_path=path, current_hash=script_hash)
    script = create_script_profile(db_session, script_data)

    assert script.id is not None
    assert script.file_path == path
    assert script.current_hash == script_hash
    assert script.last_modified is not None

def test_get_script_profile(db_session: Session):
    path = "/app/script2.py"
    code = "a = 1"
    script_hash = criar_hash_mock(code)

    create_script_profile(db_session, schemas.ScriptProfileCreate(file_path=path, current_hash=script_hash))

    retrieved_script = get_script_profile_by_hash(db_session, script_hash)
    assert retrieved_script is not None
    assert retrieved_script.file_path == path

    retrieved_script_by_path = get_script_profile_by_path(db_session, path)
    assert retrieved_script_by_path is not None
    assert retrieved_script_by_path.current_hash == script_hash

# --- Testes para PatchHistory ---
def test_create_patch_history(db_session: Session):
    script_profile_data = schemas.ScriptProfileCreate(file_path="/app/script3.py", current_hash=criar_hash_mock("def func(): pass"))
    script = create_script_profile(db_session, script_profile_data)

    patch_id = "patch_abc123"
    patch_content = "diff -u a/old b/new"
    patch_data = schemas.PatchHistoryCreate(
        patch_id=patch_id,
        script_profile_id=script.id,
        patch_content=patch_content,
        status="aplicado",
        agente_criador="AgenteGerador"
    )
    patch = create_patch_history(db_session, patch_data)

    assert patch.id is not None
    assert patch.patch_id == patch_id
    assert patch.script_profile_id == script.id

def test_get_patches_for_script(db_session: Session):
    script_profile_data = schemas.ScriptProfileCreate(file_path="/app/script4.py", current_hash=criar_hash_mock("initial"))
    script = create_script_profile(db_session, script_profile_data)

    create_patch_history(db_session, schemas.PatchHistoryCreate(patch_id="p1", script_profile_id=script.id, patch_content="c1", status="aplicado", agente_criador="A1"))
    create_patch_history(db_session, schemas.PatchHistoryCreate(patch_id="p2", script_profile_id=script.id, patch_content="c2", status="revertido", agente_criador="A2"))

    patches = get_patches_for_script(db_session, script.id)
    assert len(patches) == 2
    assert patches[0].patch_id == "p2" # Deve vir em ordem decrescente de data
    assert patches[1].patch_id == "p1"

# --- Testes para DriftRecord ---
def test_create_drift_record(db_session: Session):
    script_profile_data = schemas.ScriptProfileCreate(file_path="/app/script5.py", current_hash=criar_hash_mock("code"))
    script = create_script_profile(db_session, script_profile_data)

    drift_data = schemas.DriftRecordCreate(script_profile_id=script.id, drift_type="logica", drift_score=0.75, details="Loop infinito detectado.")
    drift = create_drift_record(db_session, drift_data)

    assert drift.id is not None
    assert drift.drift_type == "logica"
    assert drift.drift_score == 0.75
    assert drift.resolved is False

def test_mark_drift_as_resolved(db_session: Session):
    script_profile_data = schemas.ScriptProfileCreate(file_path="/app/script6.py", current_hash=criar_hash_mock("code_x"))
    script = create_script_profile(db_session, script_profile_data)

    drift = create_drift_record(db_session, schemas.DriftRecordCreate(script_profile_id=script.id, drift_type="sintaxe", drift_score=0.9))

    resolved_drift = mark_drift_as_resolved(db_session, drift.id)
    assert resolved_drift.resolved is True

# --- Testes para AgentMetric ---
def test_create_agent_metric(db_session: Session):
    metric_data = schemas.AgentMetricCreate(agent_name="AgenteGerador", success_count=5, failure_count=1, total_attempts=6, feedback_score=0.8)
    metric = create_agent_metric(db_session, metric_data)

    assert metric.id is not None
    assert metric.agent_name == "AgenteGerador"
    assert metric.total_attempts == 6

def test_get_latest_agent_metrics(db_session: Session):
    metric1 = create_agent_metric(db_session, schemas.AgentMetricCreate(agent_name="AgenteCritico", success_count=1, total_attempts=2))
    time.sleep(0.01) # Garante timestamp diferente
    metric2 = create_agent_metric(db_session, schemas.AgentMetricCreate(agent_name="AgenteCritico", success_count=2, total_attempts=3, feedback_score=0.6))

    latest = get_latest_agent_metrics(db_session, "AgenteCritico")
    assert latest.id == metric2.id # Deve ser o mais recente

# --- Testes para Artifact ---
def test_create_artifact(db_session: Session):
    content = {"log": "log de compilacao", "timestamp": "2024-01-01"}
    artifact_data = schemas.ArtifactCreate(key="Log_Compilacao_Erro", content=content, author="Sistema", metadata_json={"version": "v1.0"})
    artifact = create_artifact(db_session, artifact_data)

    assert artifact.id is not None
    assert artifact.key == "Log_Compilacao_Erro"
    assert artifact.content == content # Conteúdo deve ser Python dict após parse_json_data
    assert artifact.author == "Sistema"
    assert artifact.metadata_json == {"version": "v1.0"}

def test_get_artifact_by_key(db_session: Session):
    content = {"analise": "causa raiz identificada"}
    create_artifact(db_session, schemas.ArtifactCreate(key="Analise_Final", content=content, author="AgenteAnalista"))

    retrieved_artifact = get_artifact_by_key(db_session, "Analise_Final")
    assert retrieved_artifact is not None
    assert retrieved_artifact.content == content