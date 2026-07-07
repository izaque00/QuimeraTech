import os
import shutil
import subprocess
import logging
import hashlib
import re
import tempfile
from typing import Dict, List, Optional, Any, Tuple
from contextlib import contextmanager
from datetime import datetime
from dataclasses import dataclass

try:
    from quimera.logs.parser import montar_log
except ImportError:
    def montar_log(msg, level="INFO", context=None):
        return f"[{level}] {msg}"
from quimera.kernel.gestor import GestorKernel

logger = logging.getLogger(__name__)

@dataclass
class ContextoPatch:
    arquivo_alvo: str
    linha_erro: int
    codigo_original: str
    erro_compilacao: str
    analise_causa_raiz: Dict[str, Any]

def extract_target_file_from_patch(patch_content: str) -> Optional[str]:
    """
    Extrai o caminho do arquivo alvo do cabeçalho de um patch no formato unified diff.
    Prioriza a linha '+++' mas usa '---' como fallback para maior robustez.
    """
    if not isinstance(patch_content, str):
        return None

    # Tenta encontrar a linha '+++ b/path/to/file'
    match = re.search(r'^\+\+\+\s+b/(.*)', patch_content, re.MULTILINE)
    if not match:
        # Fallback para a linha '--- a/path/to/file'
        match = re.search(r'^\-\-\-\s+a/(.*)', patch_content, re.MULTILINE)

    if match:
        # O caminho pode conter uma tabulação no final (comum em diffs), que deve ser removida
        path = match.group(1).strip()
        return path.split('\t')[0]

    montar_log("Não foi possível extrair o arquivo alvo do patch.", "WARNING")
    return None

def generate_patch_id(patch_content: str) -> str:
    """Gera um ID único e determinístico para um patch usando SHA256."""
    if not isinstance(patch_content, str):
        patch_content = ""
    return hashlib.sha256(patch_content.encode('utf-8')).hexdigest()

def apply_patch_to_kernel(kernel_root: str, patch_content: str, dry_run: bool = False, reverter: bool = False) -> Tuple[bool, str]:
    """
    Aplica um patch ao código do kernel no diretório especificado usando o comando `patch`.

    Args:
        kernel_root (str): Caminho absoluto para a raiz do repositório do kernel.
        patch_content (str): O conteúdo do patch no formato unified diff.
        dry_run (bool): Se True, apenas simula a aplicação do patch.
        reverter (bool): Se True, tenta reverter o patch.

    Returns:
        Tuple[bool, str]: Sucesso/falha e a saída do comando.
    """
    if not os.path.isdir(kernel_root):
        logger.error(f"[PATCH_UTILS] Diretório do kernel '{kernel_root}' não encontrado para aplicar patch.")
        return False, "Diretório do kernel inválido."

    temp_patch_file = os.path.join("/tmp", f"temp_quimera_patch_{datetime.now().timestamp()}_{os.getpid()}.diff")

    try:
        with open(temp_patch_file, "w", encoding="utf-8") as f:
            f.write(patch_content)

        cmd_parts = ["patch"]
        if reverter:
            cmd_parts.append("-R")
        if dry_run:
            cmd_parts.append("--dry-run")

        cmd_parts.extend(["-p1", "-i", temp_patch_file])
        command = " ".join(cmd_parts)

        log_action = "Simulando aplicação" if dry_run else ("Revertendo" if reverter else "Aplicando")
        logger.info(f"[PATCH_UTILS] {log_action} patch no kernel em '{kernel_root}'...")

        result = subprocess.run(
            command,
            cwd=kernel_root,
            shell=True,
            capture_output=True,
            text=True,
            errors='ignore'
        )

        if result.returncode == 0:
             logger.info(f"[PATCH_UTILS] {log_action} patch: SUCESSO.")
             return True, result.stdout.strip()
        else:
             error_msg = f"[PATCH_UTILS] {log_action} patch: FALHA. Stdout: {result.stdout.strip()} | Stderr: {result.stderr.strip()}"
             logger.error(error_msg)
             return False, error_msg

    except Exception as e:
        error_msg = f"[PATCH_UTILS] Erro inesperado ao {log_action.lower()} patch: {e}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg
    finally:
        if os.path.exists(temp_patch_file):
            os.remove(temp_patch_file)

@contextmanager
def PatchValidatorSession(kernel_root: str) -> 'ValidationSessionManager':
    """
    Gerenciador de contexto para uma sessão de validação de patches.
    Cria um ambiente de teste isolado e o reutiliza para validar múltiplos patches,
    maximizando a performance ao evitar cópias repetitivas do kernel.

    Uso:
        with PatchValidatorSession(kernel_root) as validator:
            resultado_A = validator.validate(patch_A)
            resultado_B = validator.validate(patch_B)
    """
    session = ValidationSessionManager(kernel_root)
    try:
        session.setup()
        yield session
    finally:
        session.teardown()

class ValidationSessionManager:
    """Classe interna que gerencia o estado e as operações da sessão de validação."""
    def __init__(self, kernel_root: str):
        self.kernel_root = kernel_root
        self.tmp_dir_obj = None
        self.validation_path = None
        self.gestor_temp = None

    def setup(self):
        """
        Prepara o ambiente de validação: copia o kernel e inicializa o git.
        """
        montar_log("Iniciando sessão de validação: preparando ambiente de teste...", "INFO")
        try:
            self.tmp_dir_obj = tempfile.TemporaryDirectory(prefix="quimera-session-")
            self.validation_path = os.path.join(self.tmp_dir_obj.name, "linux-kernel-validation")

            montar_log(f"Criando cópia de validação do kernel em: {self.validation_path}", "DEBUG")
            shutil.copytree(self.kernel_root, self.validation_path, symlinks=True, ignore=shutil.ignore_patterns('.git'))

            # Inicializa um repositório git para aplicar e reverter patches de forma atômica
            subprocess.run(["git", "-c", "init.defaultBranch=main", "init"], cwd=self.validation_path, check=True, capture_output=True, text=True)
            subprocess.run(["git", "add", "."], cwd=self.validation_path, check=True, capture_output=True, text=True)
            subprocess.run(["git", "commit", "--no-verify", "-m", "Initial state for validation"], cwd=self.validation_path, check=True, capture_output=True, text=True)

            self.gestor_temp = GestorKernel(kernel_source_path=self.validation_path)
            montar_log("Ambiente de validação pronto para testes.", "SUCCESS")
        except Exception as e:
            montar_log(f"Falha crítica ao preparar ambiente de validação: {e}", "CRITICAL", exc_info=True)
            self.teardown() # Garante a limpeza em caso de falha na configuração
            raise

    def validate(self, patch_content: str, timeout: int = 600) -> Dict[str, Any]:
        """
        Valida um único patch dentro da sessão ativa.
        Retorna o resultado da compilação e reverte o estado do ambiente.
        """
        if not self.validation_path:
            raise RuntimeError("A sessão de validação não foi iniciada corretamente. Use dentro de um bloco 'with'.")
        if not patch_content or not patch_content.strip():
            return {"sucesso": False, "log": "Conteúdo do patch está vazio.", "motivo": "patch_vazio"}

        patch_path = os.path.join(self.tmp_dir_obj.name, "proposta.patch")

        try:
            # Escreve o patch em um arquivo
            with open(patch_path, "w", encoding="utf-8") as f:
                f.write(patch_content)

            # Aplica o patch
            apply_result = subprocess.run(
                ["git", "apply", "--reject", "--whitespace=fix", patch_path],
                cwd=self.validation_path, capture_output=True, text=True, timeout=60
            )

            if apply_result.returncode != 0:
                return {"sucesso": False, "log": f"Falha ao aplicar o patch:\n{apply_result.stderr}", "motivo": "falha_aplicacao_patch"}

            # Tenta compilar
            montar_log("Iniciando compilação de validação para o patch...", "INFO")
            resultado_compilacao = self.gestor_temp.compilar_kernel(timeout=timeout)
            return resultado_compilacao

        except Exception as e:
            msg = f"Erro inesperado durante a validação do patch: {e}"
            montar_log(msg, "ERROR", exc_info=True)
            return {"sucesso": False, "log": msg, "motivo": "erro_inesperado"}
        finally:
            # REVERTE O ESTADO: Garante que a árvore de fontes esteja limpa para o próximo patch
            montar_log("Revertendo estado do ambiente de validação para o commit inicial...", "DEBUG")
            try:
                subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=self.validation_path, check=True, capture_output=True, text=True)
            except Exception as git_error:
                montar_log(f"Falha ao reverter o ambiente de validação: {git_error}", "ERROR")

            if os.path.exists(patch_path):
                os.remove(patch_path)

    def teardown(self):
        """
        Limpa o ambiente de validação.
        """
        montar_log("Finalizando sessão de validação e limpando recursos.", "INFO")
        if self.tmp_dir_obj:
            try:
                self.tmp_dir_obj.cleanup()
            except Exception as e:
                montar_log(f"Erro ao limpar diretório temporário {self.tmp_dir_obj.name}: {e}", "ERROR")

# Função wrapper para manter a compatibilidade com o código que pode chamar a função diretamente
# Esta abordagem é menos eficiente para múltiplos patches, mas funciona para um único.
def validar_compilacao_kernel_com_patch(kernel_root: str, patch_content: str, timeout: int = 600) -> Dict[str, Any]:
    """
    Função de validação que executa uma única validação em um ambiente temporário.
    É menos eficiente para múltiplos patches, mas é autocontida.
    """
    montar_log("Usando função de validação de patch única (menos eficiente). Use a sessão para múltiplos patches.", "WARNING")
    with PatchValidatorSession(kernel_root) as session:
        return session.validate(patch_content, timeout)

def diff_analysis(code_diff: str) -> Dict[str, List[str]]:
    """
    Realiza o parsing básico de um patch no formato unified diff.
    """
    parsed_lines = {"added": [], "removed": [], "context": [], "all_lines": []}
    if not isinstance(code_diff, str):
        return parsed_lines

    raw_diff_content = code_diff
    match = re.search(r"```(?:diff)?\n(.*?)```", code_diff, re.DOTALL)
    if match:
        raw_diff_content = match.group(1).strip()

    lines = raw_diff_content.splitlines()
    for line in lines:
        parsed_lines["all_lines"].append(line)
        if line.startswith('+') and not line.startswith('+++'):
            parsed_lines["added"].append(line[1:])
        elif line.startswith('-') and not line.startswith('---'):
            parsed_lines["removed"].append(line[1:])
        elif line.startswith(' '):
            parsed_lines["context"].append(line[1:])

    return parsed_lines