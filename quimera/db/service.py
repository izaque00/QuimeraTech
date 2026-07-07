# quimera/db/service.py

import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from sqlalchemy.sql import func # Adicionado: Importar func para func.now() se necessário
from datetime import datetime # Adicionado: Importar datetime para datetime.now()

# Importa os modelos e schemas do banco de dados
from quimera.db import models, schemas

# Configuração do logger para este módulo
logger = logging.getLogger(__name__)

# --- Funções de Serviço para ScriptProfile ---

def get_perfil_script_por_id(db: Session, perfil_id: int) -> Optional[models.ScriptProfile]:
    """Obtém um perfil de script pelo seu ID."""
    return db.query(models.ScriptProfile).filter(models.ScriptProfile.id == perfil_id).first()

def get_perfil_script_por_caminho(db: Session, caminho_arquivo: str) -> Optional[models.ScriptProfile]:
    """Obtém um perfil de script pelo seu caminho de arquivo."""
    return db.query(models.ScriptProfile).filter(models.ScriptProfile.caminho_arquivo == caminho_arquivo).first()

def get_or_create_script_profile(db: Session, perfil_data: schemas.ScriptProfileCreate) -> models.ScriptProfile:
    """
    Obtém um perfil de script se ele já existir (baseado no caminho), ou o cria se não existir.
    Atualiza o hash se o perfil já existir mas o hash for diferente.
    """
    db_perfil = get_perfil_script_por_caminho(db, perfil_data.caminho_arquivo)
    if db_perfil:
        if db_perfil.hash_atual != perfil_data.hash_atual:
            db_perfil.hash_atual = perfil_data.hash_atual
            db.commit()
            db.refresh(db_perfil)
            logger.info(f"Hash do perfil de script '{db_perfil.caminho_arquivo}' atualizado.")
        return db_perfil

    logger.info(f"Nenhum perfil encontrado para '{perfil_data.caminho_arquivo}'. Criando um novo.")
    novo_perfil = models.ScriptProfile(
        caminho_arquivo=perfil_data.caminho_arquivo,
        hash_atual=perfil_data.hash_atual
    )
    db.add(novo_perfil)
    db.commit()
    db.refresh(novo_perfil)
    return novo_perfil

# --- Funções de Serviço para HistoricoPatch ---

def create_historico_patch(db: Session, patch_data: schemas.HistoricoPatchCreate) -> models.HistoricoPatch:
    """Cria um novo registro de histórico de patch."""
    db_patch = models.HistoricoPatch(**patch_data.model_dump())
    db.add(db_patch)
    db.commit()
    db.refresh(db_patch)
    logger.info(f"Registro de patch '{db_patch.patch_id[:8]}' criado para o script ID {db_patch.perfil_script_id}.")
    return db_patch

def get_patch_por_patch_id(db: Session, patch_id: str) -> Optional[models.HistoricoPatch]:
    """Obtém um registro de patch pelo seu ID de patch (hash)."""
    return db.query(models.HistoricoPatch).filter(models.HistoricoPatch.patch_id == patch_id).first()

def get_patches_por_script_id(db: Session, perfil_script_id: int) -> List[models.HistoricoPatch]:
    """Obtém todos os patches associados a um ID de perfil de script."""
    return db.query(models.HistoricoPatch).filter(models.HistoricoPatch.perfil_script_id == perfil_script_id).order_by(desc(models.HistoricoPatch.timestamp_aplicacao)).all()

# --- Funções de Serviço para RegistroDrift ---

def create_registro_drift(db: Session, drift_data: schemas.RegistroDriftCreate) -> models.RegistroDrift:
    """Cria um novo registro de drift."""
    db_drift = models.RegistroDrift(**drift_data.model_dump())
    db.add(db_drift)
    db.commit()
    db.refresh(db_drift)
    logger.info(f"Registro de drift do tipo '{db_drift.tipo_drift}' criado para o script ID {db_drift.perfil_script_id}.")
    return db_drift

def get_drifts_nao_resolvidos(db: Session, perfil_script_id: int) -> List[models.RegistroDrift]:
    """Obtém todos os drifts não resolvidos para um dado perfil de script."""
    return db.query(models.RegistroDrift).filter(
        models.RegistroDrift.perfil_script_id == perfil_script_id,
        models.RegistroDrift.resolvido == False
    ).order_by(desc(models.RegistroDrift.detectado_em)).all()

def marcar_drift_como_resolvido(db: Session, drift_id: int) -> Optional[models.RegistroDrift]:
    """Marca um registro de drift específico como resolvido."""
    db_drift = db.query(models.RegistroDrift).filter(models.RegistroDrift.id == drift_id).first()
    if db_drift:
        db_drift.resolvido = True
        db.commit()
        db.refresh(db_drift)
        logger.info(f"Drift ID {drift_id} marcado como resolvido.")
    return db_drift

# --- Funções de Serviço para MetricaAgente ---

def get_metrica_agente_por_nome(db: Session, nome_modelo: str) -> Optional[models.MetricaAgente]:
    """Obtém as métricas de um agente pelo seu nome de modelo."""
    return db.query(models.MetricaAgente).filter(models.MetricaAgente.nome_modelo == nome_modelo).first()

def update_or_create_metrica_agente(db: Session, metrica_data: schemas.MetricaAgenteCreate) -> models.MetricaAgente:
    """
    Atualiza as métricas de um agente se ele existir, ou cria um novo registro se não existir.
    """
    db_metrica = get_metrica_agente_por_nome(db, metrica_data.nome_modelo)
    if db_metrica:
        db_metrica.usos = metrica_data.usos
        db_metrica.score_total = metrica_data.score_total
        db_metrica.sucessos = metrica_data.sucessos
        logger.debug(f"Métricas do agente '{metrica_data.nome_modelo}' atualizadas.")
    else:
        db_metrica = models.MetricaAgente(**metrica_data.model_dump())
        db.add(db_metrica)
        logger.info(f"Novo registro de métrica criado para o agente '{metrica_data.nome_modelo}'.")

    db.commit()
    db.refresh(db_metrica)
    return db_metrica

# --- Funções de Serviço para MissaoTecnica ---

def create_missao_tecnica(db: Session, missao_data: schemas.MissaoTecnicaCreate) -> models.MissaoTecnica:
    """Cria um novo registro de missão técnica."""
    db_missao = models.MissaoTecnica(**missao_data.model_dump())
    db.add(db_missao)
    db.commit()
    db.refresh(db_missao)
    logger.info(f"Nova Missão Técnica (ID: {db_missao.id}) registrada no banco de dados.")
    return db_missao

def finalizar_missao_tecnica(db: Session, missao_id: int, status_final: str, mensagem_final: str, patch_vencedor_id: Optional[int] = None) -> Optional[models.MissaoTecnica]:
    """
    Atualiza uma missão técnica existente com seu status final e outros detalhes de conclusão.
    """
    db_missao = db.query(models.MissaoTecnica).filter(models.MissaoTecnica.id == missao_id).first()
    if db_missao:
        db_missao.finalizada_em = datetime.now()
        db_missao.status_final = status_final
        db_missao.mensagem_final = mensagem_final
        if patch_vencedor_id:
            db_missao.patch_vencedor_id = patch_vencedor_id
        db.commit()
        db.refresh(db_missao)
        logger.info(f"Missão Técnica (ID: {missao_id}) finalizada com status '{status_final}'.")
    return db_missao

def get_missoes_por_status(db: Session, status: str, limit: Optional[int] = None) -> List[models.MissaoTecnica]:
    """
    Obtém uma lista de missões técnicas filtradas por status.

    Args:
        db (Session): A sessão do banco de dados.
        status (str): O status das missões a serem buscadas (ex: 'falha_missao', 'sucesso').
        limit (Optional[int]): O número máximo de resultados a retornar.

    Returns:
        List[models.MissaoTecnica]: Uma lista de objetos MissaoTecnica.
    """
    query = db.query(models.MissaoTecnica).filter(models.MissaoTecnica.status_final == status)
    if limit is not None:
        query = query.limit(limit)
    return query.all()

# --- Funções de Serviço para EntradaAnaliseModel (se você a implementou) ---

def registrar_analise(db: Session, entrada_data: schemas.EntradaAnalise) -> models.EntradaAnaliseModel:
    """
    Registra uma nova entrada de análise de causa raiz no banco de dados.
    """
    # Certifique-se de que schemas.EntradaAnalise corresponde a EntradaAnaliseModel
    db_entrada = models.EntradaAnaliseModel(**entrada_data.model_dump())
    db.add(db_entrada)
    db.commit()
    db.refresh(db_entrada)
    logger.info(f"Análise do modelo '{db_entrada.modelo}' registrada no banco de dados.")
    return db_entrada