# quimera/agentes/refinador_v3/validador_ast.py

import logging
import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional

from quimera.utils.general import get_code
from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)

# Diretório raiz do projeto Quimera (3 níveis acima deste arquivo)
QUIMERA_ROOT_DIR = Path(__file__).parent.parent.parent

# Variáveis globais de controle
TREE_SITTER_AVAILABLE = False
parser: Optional['Parser'] = None

try:
    from tree_sitter import Language, Parser

    # Caminho para a biblioteca compilada da gramática C (deve existir)
    C_LANGUAGE_LIB_PATH = QUIMERA_ROOT_DIR / "build" / "c-grammar.so"

    if not C_LANGUAGE_LIB_PATH.exists():
        raise FileNotFoundError(
            f"Biblioteca da gramática C '{C_LANGUAGE_LIB_PATH}' não encontrada.\n"
            "Execute o script de compilação para gerar a biblioteca."
        )

    # CORRETO para tree_sitter 0.19.0: __init__ precisa do nome da linguagem como segundo argumento
    C_LANGUAGE = Language(str(C_LANGUAGE_LIB_PATH), "c")
    parser = Parser()
    parser.set_language(C_LANGUAGE)
    TREE_SITTER_AVAILABLE = True
    montar_log("Validador AST (Tree-sitter) para C inicializado com sucesso a partir de biblioteca pré-compilada.", "INFO")

except (ImportError, FileNotFoundError) as e:
    montar_log(f"Falha na inicialização do Tree-sitter: {e}. A validação AST será desativada.", "CRITICAL")
except Exception as e:
    montar_log(f"Erro inesperado ao carregar a gramática do Tree-sitter: {e}", "CRITICAL", exc_info=True)


def _apply_patch_in_memory(original_code: str, patch_content: str) -> Optional[str]:
    """
    Aplica um patch a um código fonte em memória usando git apply dentro de um diretório temporário.
    Retorna o código modificado ou None se falhar.
    """
    if not patch_content.strip():
        return original_code
    if not patch_content.endswith('\n'):
        patch_content += '\n'

    with tempfile.TemporaryDirectory(prefix="quimera_ast_val_") as temp_dir:
        try:
            subprocess.run(["git", "init", "-q"], cwd=temp_dir, check=True, capture_output=True)
            temp_file_path = os.path.join(temp_dir, "target_file.c")
            with open(temp_file_path, "w", encoding="utf-8") as f:
                f.write(original_code)
            subprocess.run(["git", "add", "."], cwd=temp_dir, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "initial", "-q"], cwd=temp_dir, check=True, capture_output=True)
            subprocess.run(
                ["git", "apply", "--unidiff-zero", "--inaccurate-eof", "-"],
                cwd=temp_dir,
                input=patch_content.encode("utf-8"),
                check=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            return get_code(temp_file_path)
        except subprocess.CalledProcessError as e:
            montar_log(f"Não foi possível aplicar patch em memória para validação AST. Erro: {e.stderr.strip()}", "WARNING")
            return None
        except Exception as e:
            montar_log(f"Erro inesperado ao aplicar patch em memória: {e}", "ERROR", exc_info=True)
            return None


def validar_patch_ast(patch: str, arquivo_alvo_relativo: str) -> bool:
    """
    Valida sintaxe do código C modificado por um patch, aplicando patch em memória e analisando AST.

    Args:
        patch (str): Conteúdo do patch no formato diff/unified.
        arquivo_alvo_relativo (str): Caminho relativo do arquivo alvo ao KERNEL_ROOT.

    Returns:
        bool: True se o código modificado for sintaticamente válido, False caso contrário.
    """
    if not TREE_SITTER_AVAILABLE or parser is None:
        montar_log("Validação de AST pulada (Tree-sitter indisponível).", "WARNING")
        return True

    kernel_root = os.getenv("KERNEL_ROOT")
    if not kernel_root:
        montar_log("Variável de ambiente KERNEL_ROOT não definida. Pulando validação AST.", "ERROR")
        return False

    caminho_completo_arquivo = os.path.join(kernel_root, arquivo_alvo_relativo)
    if not os.path.exists(caminho_completo_arquivo):
        montar_log(f"Arquivo alvo não encontrado para validação AST: '{caminho_completo_arquivo}'", "ERROR")
        return False

    try:
        codigo_original = get_code(caminho_completo_arquivo)
        codigo_modificado = _apply_patch_in_memory(codigo_original, patch)

        if codigo_modificado is None:
            montar_log("Falha ao aplicar patch em memória. Patch considerado inválido sintaticamente.", "WARNING")
            return False

        tree = parser.parse(bytes(codigo_modificado, "utf-8"))

        # Verifica se há erro sintático na AST
        if tree.root_node.has_error:
            montar_log("Validação AST FALHOU: Patch introduz erro sintático.", "WARNING")
            return False

        montar_log("Validação AST (Tree-sitter) bem-sucedida.", "INFO")
        return True

    except Exception as e:
        montar_log(f"Erro inesperado durante validação AST: {e}", "ERROR", exc_info=True)
        return False