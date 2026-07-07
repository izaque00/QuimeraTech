# quimera/utils/refactor_utils.py
import ast
import hashlib
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional
from quimera.utils.general import get_code, write_code # Utilitários para ler/escrever código

# Não importa VectorScoreManager ou db.service aqui para evitar importações circulares
# Assumimos que o QuadroNegro ou um serviço central fará a interface com o DB/VectorStore
logger = logging.getLogger("RefactorUtils")
# Não inicializa logging.basicConfig aqui.

def rollback_best_version(file_to_rollback: str, force: bool = False, deep_fallback: bool = False) -> Optional[str]:
    """
    Busca e aplica a versão mais segura e consistente de um arquivo para rollback.
    Prioriza histórico de backups e, se `force=True`, tenta um fallback mais profundo.

    Args:
        file_to_rollback (str): Caminho completo do arquivo a ser revertido.
        force (bool): Se True, tenta um rollback mais agressivo (ex: último backup conhecido, mesmo que antigo).
        deep_fallback (bool): Se True, busca por backups com base no histórico vetorial de sucesso.

    Returns:
        Optional[str]: O conteúdo do código revertido com sucesso, ou None se falhar.
    """
    logger.info(f"Iniciando rollback para o arquivo: {file_to_rollback}")

    # Prioridade 1: Último backup temporário (.bak)
    backup_temp_path = f"{file_to_rollback}.bak"
    if os.path.exists(backup_temp_path):
        try:
            content_bak = get_code(backup_temp_path)
            logger.info(f"Rollback para o último backup temporário ({backup_temp_path}) executado com sucesso.")
            write_code(file_to_rollback, content_bak) # Aplica o backup
            return content_bak
        except Exception as e:
            logger.warning(f"Falha ao usar backup temporário {backup_temp_path}: {e}. Tentando outras opções.", exc_info=True)

    # Prioridade 2: Rollback baseado no histórico vetorial ou de banco de dados
    if deep_fallback:
        logger.info("Tentando rollback profundo baseado em histórico vetorial/DB...")
        # Esta lógica deve interagir com o VectorManager ou o DB para buscar a "melhor" versão histórica.
        # Exemplo conceitual (precisa da lógica real do VectorStore e DB)
        try:
            # from quimera.db.base import SessionLocal # Usaria se fosse acessar o DB aqui
            # from quimera.db.service import get_script_profile_by_hash # Exemplo
            # from quimera.utils.vector_manager import VectorManager # Exemplo
            # session = SessionLocal()
            # script_profile = get_script_profile_by_hash(session, generate_code_hash_for_path(file_to_rollback))
            # if script_profile and script_profile.vetores_historicos:
            #    # Lógica para encontrar o vetor mais "são" e seu código associado
            #    pass
            logger.warning("Funcionalidade de rollback profundo (vetorial/DB) é conceitual e precisa de implementação real.")
            # Por agora, simula que não encontrou um rollback profundo
        except Exception as e:
            logger.error(f"Erro no rollback profundo: {e}", exc_info=True)

    # Prioridade 3: Rollback forçado (se solicitado) para o estado anterior do Git (se aplicável)
    if force:
        logger.info("Forçando rollback para a última versão Git do arquivo...")
        try:
            # Assume que o Orquestrador já definiu KERNEL_ROOT no ambiente.
            kernel_root = os.getenv("KERNEL_ROOT")
            if not kernel_root:
                raise ValueError("KERNEL_ROOT não definido para rollback Git.")

            # Comando Git para obter a última versão do arquivo antes das mudanças locais
            result = subprocess.run(
                ["git", "checkout", "HEAD", "--", file_to_rollback],
                cwd=kernel_root, # Executa no diretório do kernel
                capture_output=True, text=True, check=True, errors='ignore'
            )
            content_git = get_code(file_to_rollback) # Lê o arquivo após o checkout
            logger.info(f"Rollback forçado via Git para {file_to_rollback} executado com sucesso.")
            return content_git
        except subprocess.CalledProcessError as e:
            logger.error(f"Falha ao forçar rollback via Git para {file_to_rollback}: {e.stderr.strip()}", exc_info=True)
        except Exception as e:
            logger.error(f"Erro inesperado no rollback forçado via Git: {e}", exc_info=True)

    logger.error(f"Falha ao executar rollback para {file_to_rollback}. Nenhuma versão segura encontrada.")
    return None # Retorna None se nenhum rollback for bem-sucedido

def generate_code_hash_for_path(path: str) -> str:
    """Gera o hash SHA256 do conteúdo de um arquivo."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            code = f.read()
        return hashlib.sha256(code.encode('utf-8')).hexdigest()[:64]
    except FileNotFoundError:
        logger.warning(f"Arquivo não encontrado para gerar hash: {path}. Retornando hash do caminho.")
        return hashlib.sha256(path.encode('utf-8')).hexdigest()[:64]
    except Exception as e:
        logger.error(f"Erro ao gerar hash para {path}: {e}", exc_info=True)
        return hashlib.sha256(path.encode('utf-8')).hexdigest()[:64] # Retorna hash do caminho em caso de erro