"""
Exceções customizadas do sistema Quimera.

Todas as exceções do projeto herdam de QuimeraError, permitindo
captura uniforme de erros específicos do domínio.
"""


class QuimeraError(Exception):
    """Base exception for Quimera."""
    pass


class AgenteError(QuimeraError):
    """Erro relacionado a agentes do sistema."""
    pass


class RoteamentoError(QuimeraError):
    """Erro relacionado ao roteamento de modelos LLM."""
    pass


class AnaliseError(QuimeraError):
    """Erro durante análise de código ou causa raiz."""
    pass


class LLMError(QuimeraError):
    """Erro relacionado a chamadas de LLM."""
    pass


class SegurancaError(QuimeraError):
    """Erro relacionado a violações de segurança."""
    pass
