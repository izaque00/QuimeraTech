# quimera/utils/kernel_utils.py
import os
import subprocess
import logging
import shutil
from typing import Optional

logger = logging.getLogger("KernelUtils")

# --- Configurações Padrão do Kernel Alvo ---
# Facilmente alteráveis para mirar em outros kernels.
SPECIFIC_KERNEL_REPO_URL = "https://github.com/eun0115/android_kernel_samsung_sm7150"
DEFAULT_CLONE_BRANCH = os.environ.get("QUIMERA_KERNEL_BRANCH", "master")

class KernelUtilsError(Exception):
    """Exceção personalizada para erros em utilitários de kernel."""
    pass

def validar_e_clonar_kernel(kernel_root: str, repo_url: str = SPECIFIC_KERNEL_REPO_URL, branch: str = DEFAULT_CLONE_BRANCH) -> bool:
    """
    Valida o diretório do kernel. Se não for um repo Git válido, clona do zero.
    Garante que o repositório esteja na branch correta.

    Args:
        kernel_root (str): Caminho absoluto para o diretório de destino do kernel.
        repo_url (str): A URL do repositório Git a ser clonado.
        branch (str): A branch a ser usada.

    Returns:
        True se o kernel estiver pronto para uso, False caso contrário.
    """
    try:
        # Cenário 1: O diretório existe e é um repositório Git válido.
        if os.path.isdir(os.path.join(kernel_root, ".git")):
            logger.info(f"Repositório Git encontrado em '{kernel_root}'. Validando branch...")
            return checkout_branch(kernel_root, branch)

        # Cenário 2: O diretório existe, mas não é um repo. Limpar para um clone limpo.
        if os.path.exists(kernel_root):
            logger.warning(f"Diretório '{kernel_root}' existe mas não é um repositório Git. Removendo para um clone limpo.")
            shutil.rmtree(kernel_root)

        # Cenário 3: O diretório não existe. Criar e clonar.
        logger.info(f"Repositório não encontrado. Clonando '{repo_url}' (branch: {branch}) para '{kernel_root}'...")
        os.makedirs(kernel_root, exist_ok=True)

        clone_command = ["git", "clone", "--depth=1", "--branch", branch, repo_url, kernel_root]

        subprocess.run(
            clone_command,
            check=True,
            capture_output=True,
            text=True,
            errors='ignore'
        )
        logger.info("Repositório do kernel clonado com sucesso.")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Falha no comando Git ao validar/clonar kernel: {e.stderr.strip()}")
        return False
    except Exception as e:
        logger.error(f"Erro inesperado ao preparar o kernel: {e}", exc_info=True)
        return False

def checkout_branch(kernel_root: str, branch_name: str) -> bool:
    """
    Garante que o repositório esteja em um branch específico.

    Args:
        kernel_root (str): Caminho para a raiz do repositório.
        branch_name (str): O nome do branch desejado.

    Returns:
        True se o checkout for bem-sucedido, False caso contrário.
    """
    try:
        # Verifica branch atual
        current_branch_cmd = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=kernel_root, capture_output=True, text=True, check=True)
        if current_branch_cmd.stdout.strip() == branch_name:
            logger.info(f"Kernel já está na branch correta: '{branch_name}'.")
            return True

        # Tenta fazer o checkout
        logger.warning(f"Trocando para a branch '{branch_name}'...")
        subprocess.run(["git", "checkout", branch_name], cwd=kernel_root, check=True, capture_output=True, text=True)
        logger.info(f"Checkout para a branch '{branch_name}' realizado com sucesso.")
        return True
    except subprocess.CalledProcessError:
        logger.error(f"Falha ao fazer checkout da branch '{branch_name}'. Verifique se a branch existe no repositório.")
        return False
    except Exception as e:
        logger.error(f"Erro inesperado durante o checkout: {e}", exc_info=True)
        return False

def setup_toolchain() -> bool:
    """
    Instala pré-requisitos de compilação para o kernel em sistemas Debian/Ubuntu.
    AVISO: Requer privilégios de sudo. Ideal para ambientes de setup, não runtime.
    """
    logger.info("Configurando toolchain de compilação (apt). Pode exigir senha de sudo.")
    try:
        packages = "build-essential flex bison libssl-dev dwarves libelf-dev clang lld crossbuild-essential-arm64"
        # Usar `sudo -n` para evitar prompt de senha e falhar graciosamente se não tiver privilégios
        cmd = f"sudo -n apt-get update && sudo -n apt-get install -y {packages}"

        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True, errors='ignore')
        logger.info(f"Toolchain configurada com sucesso. Log: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Falha ao instalar toolchain: {e.stderr.strip()}")
        logger.error("Verifique se você tem permissões sudo (sem senha) e se os pacotes são válidos para sua distro.")
        return False
    except Exception as e:
        logger.error(f"Erro inesperado ao configurar toolchain: {e}", exc_info=True)
        return False

def criar_backup_kernel(kernel_root: str, backup_path: str) -> bool:
    """
    Cria um backup limpo do estado atual do kernel, ignorando artefatos de build e .git.

    Args:
        kernel_root (str): Caminho absoluto para a raiz do kernel.
        backup_path (str): Caminho absoluto para o diretório de backup.

    Returns:
        True se o backup foi bem-sucedido, False caso contrário.
    """
    if not os.path.isdir(kernel_root):
        logger.error(f"Diretório do kernel '{kernel_root}' não encontrado para backup.")
        return False

    try:
        logger.info(f"Criando backup de '{kernel_root}' para '{backup_path}'...")
        if os.path.exists(backup_path):
            shutil.rmtree(backup_path)

        ignore_patterns = shutil.ignore_patterns(
            '.git', '__pycache__', '*_build', 'out', '*.o', '*.ko', '*.mod.c', '*.cmd'
        )
        shutil.copytree(kernel_root, backup_path, ignore=ignore_patterns, dirs_exist_ok=True)
        logger.info(f"Backup do kernel criado com sucesso em '{backup_path}'.")
        return True
    except Exception as e:
        logger.error(f"Falha ao criar backup do kernel: {e}", exc_info=True)
        return False

def restaurar_backup_kernel(backup_path: str, kernel_root: str) -> bool:
    """
    Restaura o estado do kernel a partir de um backup, garantindo um estado limpo.

    Args:
        backup_path (str): Caminho para o diretório de backup.
        kernel_root (str): Caminho para o diretório do kernel a ser restaurado.

    Returns:
        True se a restauração foi bem-sucedida, False caso contrário.
    """
    if not os.path.isdir(backup_path):
        logger.error(f"Diretório de backup '{backup_path}' não encontrado.")
        return False

    try:
        logger.info(f"Restaurando kernel em '{kernel_root}' a partir de '{backup_path}'...")

        # Preserva o diretório .git se ele existir, para não precisar clonar tudo de novo
        git_dir = os.path.join(kernel_root, '.git')
        temp_git_dir = None
        if os.path.exists(git_dir):
            temp_git_dir = backup_path + '_gittemp'
            shutil.move(git_dir, temp_git_dir)

        # Limpa o diretório do kernel e restaura do backup
        if os.path.exists(kernel_root):
            shutil.rmtree(kernel_root)

        shutil.copytree(backup_path, kernel_root)

        # Restaura o diretório .git
        if temp_git_dir:
            shutil.move(temp_git_dir, git_dir)

        logger.info("Estado do kernel restaurado com sucesso.")
        return True
    except Exception as e:
        logger.error(f"Falha ao restaurar o estado do kernel: {e}", exc_info=True)
        return False

def validar_repositorio_clonado(caminho_repo: str) -> bool:
    """
    Verifica se o repositório do kernel está corretamente clonado.
    Critérios básicos: o caminho existe e possui um arquivo Android.mk ou Makefile.
    """
    import os
    if not os.path.isdir(caminho_repo):
        return False
    arquivos_esperados = ['Android.mk', 'Makefile']
    return any(os.path.isfile(os.path.join(caminho_repo, arq)) for arq in arquivos_esperados)