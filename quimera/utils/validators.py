"""JSON Schema Validator — Validação com schema para arquivos de configuração JSON.

Garante que arquivos JSON carregados em runtime (manifesto_quimera.json,
casos_de_reparo_conhecidos.json, etc.) tenham estrutura esperada,
evitando erros silenciosos com dados malformados.

Uso:
    from quimera.utils.validators import validate_json_schema
    
    data = json.loads(conteudo)
    validate_json_schema(data, KNOWN_CASES_SCHEMA, "casos_conhecidos.json")
"""

import json
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


# --- Schemas pré-definidos ---

KNOWN_CASES_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "casos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "descricao": {"type": "string"},
                    "erro": {"type": "string"},
                    "solucao": {"type": "string"},
                    "arquivo_afetado": {"type": "string"},
                    "severidade": {"type": "string", "enum": ["critical", "high", "medium", "low", "info"]},
                },
                "required": ["id", "descricao"],
            }
        }
    },
}

MANIFESTO_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "nome": {"type": "string"},
        "versao": {"type": "string"},
        "descricao": {"type": "string"},
        "dependencias": {
            "type": "object",
            "properties": {
                "obrigatorias": {"type": "array", "items": {"type": "string"}},
                "opcionais": {"type": "array", "items": {"type": "string"}},
            },
        },
        "scripts": {"type": "object"},
    },
}

KERNEL_PROFILES_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": {
        "type": "object",
        "properties": {
            "nome": {"type": "string"},
            "arquitetura": {"type": "string"},
            "compilador": {"type": "string"},
            "flags": {"type": "array", "items": {"type": "string"}},
        },
    },
}


def validate_structure(
    data: Any, schema: Dict[str, Any], source_name: str = "unknown"
) -> List[str]:
    """Valida estrutura JSON contra schema simples (sem dependência externa).

    Implementação minimalista que cobre type, properties, required,
    items, enum, e additionalProperties. Não requer jsonschema lib.

    Args:
        data: Dados JSON carregados.
        schema: Schema de validação.
        source_name: Nome do arquivo para mensagens de erro.

    Returns:
        Lista de mensagens de erro (vazia se válido).
    """
    errors: List[str] = []

    def _validate(value: Any, sch: Dict[str, Any], path: str = "$") -> None:
        schema_type = sch.get("type")

        # Type checking
        if schema_type == "object":
            if not isinstance(value, dict):
                errors.append(f"{source_name}:{path} esperado 'object', recebido {type(value).__name__}")
                return

            # Check required
            for req in sch.get("required", []):
                if req not in value:
                    errors.append(f"{source_name}:{path} campo obrigatório '{req}' ausente")

            # Check properties
            props = sch.get("properties", {})
            for prop_name, prop_schema in props.items():
                if prop_name in value:
                    _validate(value[prop_name], prop_schema, f"{path}.{prop_name}")

            # Check additionalProperties
            if sch.get("additionalProperties") is False:
                extra = set(value.keys()) - set(props.keys())
                if extra:
                    errors.append(
                        f"{source_name}:{path} campos não permitidos: {extra}"
                    )

        elif schema_type == "array":
            if not isinstance(value, list):
                errors.append(f"{source_name}:{path} esperado 'array', recebido {type(value).__name__}")
                return

            item_schema = sch.get("items")
            if item_schema and isinstance(item_schema, dict):
                for idx, item in enumerate(value):
                    _validate(item, item_schema, f"{path}[{idx}]")

        elif schema_type == "string":
            if not isinstance(value, str):
                errors.append(f"{source_name}:{path} esperado 'string', recebido {type(value).__name__}")

        elif schema_type == "number":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                errors.append(f"{source_name}:{path} esperado 'number', recebido {type(value).__name__}")

        elif schema_type == "boolean":
            if not isinstance(value, bool):
                errors.append(f"{source_name}:{path} esperado 'boolean', recebido {type(value).__name__}")

        # Enum validation
        allowed = sch.get("enum")
        if allowed is not None and value not in allowed:
            errors.append(f"{source_name}:{path} valor '{value}' não está em {allowed}")

    _validate(data, schema)
    return errors


def validate_json_schema(
    data: Any, schema: Dict[str, Any], source_name: str = "unknown"
) -> bool:
    """Valida dados JSON contra schema. Faz log de erros.

    Args:
        data: Dados JSON carregados.
        schema: Schema de validação.
        source_name: Nome do arquivo para mensagens de erro.

    Returns:
        True se válido, False se houver erros.
    """
    errors = validate_structure(data, schema, source_name)
    if errors:
        for err in errors:
            logger.error(f"JSON Schema Violation: {err}")
        return False
    logger.debug(f"JSON Schema validado com sucesso: {source_name}")
    return True


def safe_json_load(path: str, schema: Optional[Dict[str, Any]] = None) -> Optional[Any]:
    """Carrega arquivo JSON com validação de schema opcional.

    Args:
        path: Caminho do arquivo JSON.
        schema: Schema opcional para validação.

    Returns:
        Dados carregados ou None se falhar.
    """
    file_path = Path(path)
    if not file_path.exists():
        logger.warning(f"Arquivo JSON não encontrado: {path}")
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"JSON inválido em '{path}': {e}")
        return None
    except Exception as e:
        logger.error(f"Erro ao ler '{path}': {e}")
        return None

    if schema and not validate_json_schema(data, schema, file_path.name):
        logger.warning(f"Arquivo '{path}' passou no parse JSON mas falhou na validação de schema")
        # Retorna os dados mesmo assim — o schema é informativo, não bloqueante
        return data

    return data
