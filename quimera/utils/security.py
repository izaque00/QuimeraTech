# quimera/utils/security.py
"""
Utilitários de segurança para proteção de dados sensíveis.

Fornece SecretStr para evitar que API keys e tokens sejam
acidentalmente logados ou expostos em tracebacks.
"""

from typing import Any


class SecretStr:
    """Wrapper que protege strings sensíveis contra logging acidental.

    Redacta o valor em __repr__, __str__, e formatação,
    exibindo apenas os últimos 4 caracteres para identificação.

    Uso:
        api_key = SecretStr("sk-abc123xyz")
        print(api_key)  # SecretStr('***xyz')
        str(api_key)    # 'sk-abc123xyz' (apenas via .get())
    """

    def __init__(self, value: str):
        self._value = value

    def get(self) -> str:
        """Retorna o valor original (use apenas para passar ao cliente)."""
        return self._value

    def __repr__(self) -> str:
        if len(self._value) <= 4:
            return "SecretStr('***')"
        return f"SecretStr('***{self._value[-4:]}')"

    def __str__(self) -> str:
        return self.__repr__()

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, SecretStr):
            return self._value == other._value
        return False

    def __hash__(self) -> int:
        return hash(self._value)

    def __bool__(self) -> bool:
        return bool(self._value)


def redact_sensitive(d: dict, keys: set = None) -> dict:
    """Redacta campos sensíveis em um dicionário antes de logging.

    Args:
        d: Dicionário a sanitizar.
        keys: Conjunto de chaves a redactar (default: api_key, token, secret, password).

    Returns:
        Cópia do dicionário com valores sensíveis substituídos por '***'.
    """
    if keys is None:
        keys = {'api_key', 'token', 'secret', 'password', 'key', 'auth'}
    result = {}
    for k, v in d.items():
        if any(s in k.lower() for s in keys):
            result[k] = '***REDACTED***'
        elif isinstance(v, SecretStr):
            result[k] = repr(v)
        else:
            result[k] = v
    return result
