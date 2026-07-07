# quimera/agentes/agente_gestao_rollback.py
import sys
import asyncio
import logging
import os
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# Importações de componentes do sistema Quimera
from quimera.quadro_negro import QuadroNegro
from quimera.db.base import get_db
from quimera.db import service as db_service, schemas
from quimera.utils.general import get_code, write_code
from quimera.utils.refactor_utils import generate_code_hash_for_path
from quimera.utils.retry import retry
from quimera.utils.file_lock import FileLock

logger = logging.getLogger(__name__)

class AgenteDeConserto:
    """
    Agente responsável pela gestão de rollback e pela restauração do código-fonte
    a um estado estável conhecido. Atua como a rede de segurança do sistema,
    intervindo quando uma operação falha ou introduz um risco inaceitável.
    """

    def __init__(self, quadro_negro: QuadroNegro):
        """
        Inicializa o AgenteDeConserto.

        Args:
            quadro_negro (QuadroNegro): A instância do Quadro Negro para comunicação.
        """
        self.quadro_negro = quadro_negro
        self.kernel_root = os.getenv("KERNEL_ROOT")
        if not self.kernel_root:
            raise ValueError("AgenteDeConserto: KERNEL_ROOT não está definido no ambiente.")
        logger.info("AgenteDeConserto (Gestão de Rollback) inicializado.")

    def _tentar_rollback_de_backup_local(self, caminho_arquivo: str) -> Optional[str]:
        """Tenta reverter para um backup local imediato (arquivo.bak)."""
        backup_path = f"{caminho_arquivo}.bak"
        if os.path.exists(backup_path):
            try:
                logger.info(f"Encontrado backup local em '{backup_path}'. Restaurando...")
                conteudo_backup = get_code(backup_path)
                write_code(caminho_arquivo, conteudo_backup)
                os.remove(backup_path) # Remove o backup após o uso bem-sucedido
                return conteudo_backup
            except Exception as e:
                logger.error(f"Falha ao restaurar do backup local '{backup_path}': {e}", exc_info=True)
        return None

    @retry(max_attempts=2, backoff=1.0)
    def _tentar_rollback_via_git(self, caminho_arquivo: str) -> Optional[str]:
        """Tenta reverter o arquivo para o estado do último commit usando Git."""
        try:
            logger.info(f"Tentando reverter '{caminho_arquivo}' para o estado do HEAD do Git...")
            # Usa o caminho relativo ao root do kernel para o comando git
            caminho_relativo = os.path.relpath(caminho_arquivo, self.kernel_root)

            # Remove o index.lock
            git_lock_path = os.path.join(self.kernel_root, '.git', 'index.lock')
            if os.path.exists(git_lock_path):
                logger.warning(f"Arquivo de lock do Git encontrado em '{git_lock_path}'. Usando FileLock para remoção segura.")
                try:
                    with FileLock(git_lock_path, timeout=5):
                        if os.path.exists(git_lock_path):
                            os.remove(git_lock_path)
                except (TimeoutError, Exception) as e:
                    logger.error(f"Falha ao remover arquivo de lock do Git '{git_lock_path}': {e}")

            cmd = ["git", "checkout", "HEAD", "--", caminho_relativo]
            subprocess.run(
                cmd,
                cwd=self.kernel_root,
                capture_output=True,
                check=True, # Levanta exceção em caso de erro
                timeout=60 # Timeout aumentado
            )
            logger.info(f"Rollback via Git para '{caminho_arquivo}' bem-sucedido.")
            return get_code(caminho_arquivo)
        except subprocess.TimeoutExpired:
            logger.error(f"Comando de rollback do Git para '{caminho_arquivo}' excedeu o timeout de 60 segundos.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Falha no comando de rollback do Git: {e.stderr.decode(errors='ignore').strip()}")
        except Exception as e:
            logger.error(f"Erro inesperado durante o rollback via Git: {e}", exc_info=True)
        return None

    def _tentar_rollback_completo_via_git(self) -> bool:
        """Tenta reverter TODOS os arquivos modificados no repositório para o estado do último commit."""
        try:
            logger.info("Tentando reverter TODOS os arquivos modificados para o estado do HEAD do Git...")

            git_lock_path = os.path.join(self.kernel_root, '.git', 'index.lock')
            if os.path.exists(git_lock_path):
                logger.warning(f"Arquivo de lock do Git encontrado em '{git_lock_path}'. Usando FileLock para remoção segura.")
                try:
                    with FileLock(git_lock_path, timeout=5):
                        if os.path.exists(git_lock_path):
                            os.remove(git_lock_path)
                except (TimeoutError, Exception) as e:
                    logger.error(f"Falha ao remover arquivo de lock do Git '{git_lock_path}': {e}. Tentando prosseguir.")

            cmd = ["git", "checkout", "HEAD", "--", "."] # Checkout de tudo a partir do diretório atual
            subprocess.run(
                cmd,
                cwd=self.kernel_root,
                capture_output=True,
                check=True,
                timeout=120 # Timeout maior para um checkout completo
            )
            logger.info("Rollback completo do repositório via Git bem-sucedido.")
            return True
        except subprocess.TimeoutExpired:
             logger.error("Comando de rollback completo do Git excedeu o timeout de 120 segundos.")
        except Exception as e:
            logger.error(f"Erro inesperado durante o rollback completo via Git: {e}", exc_info=True)
            return False


    async def executar_rollback_arquivo(self, caminho_arquivo: str, motivo: str) -> bool:
        """
        Executa um rollback em um arquivo ou diretório específico usando uma hierarquia de estratégias
        e registra o evento no banco de dados.

        Args:
            caminho_arquivo (str): Caminho completo do arquivo ou diretório a ser revertido.
            motivo (str): A razão pela qual o rollback foi acionado.

        Returns:
            bool: True se o rollback foi bem-sucedido, False caso contrário.
        """
        logger.warning(f"ROLLBACK ACIONADO para o caminho '{caminho_arquivo}'. Motivo: {motivo}")

        codigo_restaurado = None
        # Verifica se o caminho é um diretório (sugere um rollback geral)
        if os.path.isdir(caminho_arquivo):
             logger.info("Caminho é um diretório, tentando rollback completo do repositório.")
             sucesso_rollback = await asyncio.to_thread(self._tentar_rollback_completo_via_git)
             if sucesso_rollback:
                 codigo_restaurado = "Estado do repositório restaurado via Git." # Placeholder para indicar sucesso
        else:
            codigo_restaurado = self._tentar_rollback_de_backup_local(caminho_arquivo)
            if not codigo_restaurado:
                codigo_restaurado = self._tentar_rollback_via_git(caminho_arquivo)

        if not codigo_restaurado:
            logger.critical(f"FALHA CRÍTICA DE ROLLBACK: Não foi possível restaurar o caminho '{caminho_arquivo}'. O estado do arquivo pode estar inconsistente.")
            return False

        # Se o rollback foi bem-sucedido, registra o evento no banco de dados.
        with get_db() as db:
            try:
                # Se for um rollback de diretório, o 'perfil' pode não ser aplicável ou pode ser para o diretório raiz.
                # Para simplificar, só registraremos o patch se o rollback foi em um arquivo específico.
                if os.path.isfile(caminho_arquivo):
                    perfil = db_service.get_or_create_script_profile(db, schemas.ScriptProfileCreate(
                        caminho_arquivo=caminho_arquivo,
                        hash_atual=generate_code_hash_for_path(caminho_arquivo)
                    ))

                    patch_id_rollback = f"rollback_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                    patch_data = schemas.HistoricoPatchCreate(
                        patch_id=patch_id_rollback,
                        perfil_script_id=perfil.id,
                        conteudo_patch=f"ROLLBACK para o estado anterior. Motivo: {motivo}",
                        status="revertido",
                        agente_criador=self.__class__.__name__,
                        comentario=f"O arquivo {os.path.basename(caminho_arquivo)} foi revertido para uma versão estável conhecida."
                    )
                    db_service.create_historico_patch(db, patch_data)
                    logger.info(f"Evento de rollback para '{caminho_arquivo}' registrado com sucesso no banco de dados.")
                else:
                    logger.info(f"Rollback de diretório/repositório para '{caminho_arquivo}' concluído. Não registrando patch individual no DB.")

            except Exception as e:
                logger.error(f"Erro ao registrar o evento de rollback no banco de dados: {e}", exc_info=True)

        self.quadro_negro.publicar_artefato(
            f"rollback_executado:{os.path.basename(caminho_arquivo)}",
            {"caminho": caminho_arquivo, "motivo": motivo},
            autor=self.__class__.__name__
        )
        return True