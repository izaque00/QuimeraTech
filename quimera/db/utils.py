# quimera/db/utils.py

import json
import logging
from typing import Any, Optional, Dict, List

# Configuração do logger para este módulo
logger = logging.getLogger(__name__)

"""
Este módulo fornece funções de utilidade para a camada de banco de dados,
principalmente para lidar com a serialização e desserialização de dados
que serão armazenados em campos de texto (como JSON).
"""

def jsonify_data(data: Any) -> str:
    """
    Converte uma estrutura de dados Python (como dict ou list) em uma string JSON.
    Esta função é usada para armazenar dados complexos em campos de texto no banco de dados.

    Inclui tratamento de erro para objetos não serializáveis.

    Args:
        data (Any): O objeto Python a ser convertido.

    Returns:
        str: Uma representação em string JSON do objeto.
    """
    if data is None:
        return 'null'
    try:
        # `default=str` é um fallback para tipos que o json não conhece, como datetime.
        # Ele tentará converter o objeto para sua representação em string.
        return json.dumps(data, ensure_ascii=False, default=str)
    except (TypeError, ValueError) as e:
        error_message = f"Erro de serialização JSON: {e}. O objeto não pôde ser convertido."
        logger.error(error_message, exc_info=True)
        # Retorna um objeto JSON de erro para que a falha seja registrada no DB.
        return json.dumps({"__serialization_error__": error_message, "__original_data_type__": str(type(data))})

def parse_json_data(json_string: Optional[str]) -> Any:
    """
    Converte uma string JSON de volta para uma estrutura de dados Python.
    Usado ao ler dados de campos de texto do banco de dados.

    Args:
        json_string (Optional[str]): A string JSON a ser parseada.

    Returns:
        Any: A estrutura de dados Python resultante (dict, list, etc.), ou None
             se a string for nula, vazia ou o parsing falhar.
    """
    if not json_string:
        return None
    try:
        return json.loads(json_string)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(
            f"Falha ao parsear string JSON: {e}. "
            f"A string pode não ser um JSON válido ou o tipo de entrada está incorreto. "
            f"String (início): '{json_string[:100]}...'",
            exc_info=True
        )
        # Retorna a string original como fallback se não for um JSON válido,
        # pois pode ser um dado legado ou um simples texto.
        return json_string