# quimera/utils/general.py
import os
import re
from datetime import datetime
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("GeneralUtils")
# Não inicializa logging.basicConfig aqui.

# --- Funções de Segurança ---

def mask_sensitive_data(text: str) -> str:
    """Mask API keys and sensitive data in logs."""
    if not isinstance(text, str):
        text = str(text)
    text = re.sub(r'sk-[a-zA-Z0-9]{20,}', 'sk-***REDACTED***', text)
    text = re.sub(r'Bearer\s+[a-zA-Z0-9\-_]+', 'Bearer ***REDACTED***', text)
    text = re.sub(r'api[_-]?key\s*[:=]\s*[\'"]?[a-zA-Z0-9_\-]{10,}', 'api_key=***REDACTED***', text, flags=re.IGNORECASE)
    text = re.sub(r'x-api-key\s*:\s*[\'"]?[a-zA-Z0-9_\-]{10,}', 'x-api-key: ***REDACTED***', text, flags=re.IGNORECASE)
    return text


# --- Funções Auxiliares Gerais ---

def format_async_error(error: Exception) -> str:
    """
    Formata uma exceção assíncrona para registro em log.

    Args:
        error (Exception): A exceção a ser formatada.

    Returns:
        str: String formatada da exceção.
    """
    return f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Erro Assíncrono: {type(error).__name__}: {str(error)}"

# Funções para leitura/escrita de código (usadas em vários agentes e utilitários)
def get_code(file_path: str) -> str:
    """Lê o conteúdo de um arquivo de código."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Arquivo não encontrado: {file_path}")
        raise
    except Exception as e:
        logger.error(f"Erro ao ler arquivo {file_path}: {e}", exc_info=True)
        raise

def write_code(file_path: str, code_content: str):
    """Escreve o conteúdo em um arquivo de código."""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code_content)
        logger.debug(f"Código salvo em: {file_path}")
    except Exception as e:
        logger.error(f"Erro ao escrever código no arquivo {file_path}: {e}", exc_info=True)
        raise