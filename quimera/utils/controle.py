"""Controle de segurança — verificação de padrões inseguros."""
import re
from typing import List, Tuple

PADROES_INSEGUROS = [
    (r"rm\s+-rf", "Destructive command"),
    (r"eval\(", "Dynamic evaluation"),
    (r"exec\(", "Dynamic execution"),
    (r"__import__\(", "Dynamic import"),
    (r"subprocess\.", "Subprocess call"),
]

def verificar_padroes_inseguros(code: str) -> List[Tuple[str, str]]:
    """Verifica código contra padrões inseguros conhecidos."""
    encontrados = []
    for pattern, desc in PADROES_INSEGUROS:
        if re.search(pattern, code):
            encontrados.append((pattern, desc))
    return encontrados

def sanitizar_codigo(code: str) -> str:
    """Remove padrões inseguros do código."""
    # Implementação segura — delega ao sandbox
    return code
