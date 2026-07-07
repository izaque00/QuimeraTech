"""Log Parser — Funcao centralizada de logging do Quimera.

Usada por todos os modulos para logging padronizado.
"""

import logging

logger = logging.getLogger(__name__)


def montar_log(msg: str, log_level: str = "INFO", exc_info: bool = False):
    """Funcao de logging centralizada.

    Args:
        msg: Mensagem de log.
        log_level: Nivel (INFO, WARNING, ERROR, CRITICAL, DEBUG, SUCCESS).
        exc_info: Se True, inclui traceback.
    """
    level = log_level.upper()
    if level == "ERROR":
        logger.error(msg, exc_info=exc_info)
    elif level == "WARNING":
        logger.warning(msg)
    elif level == "CRITICAL":
        logger.critical(msg, exc_info=exc_info)
    elif level == "DEBUG":
        logger.debug(msg)
    elif level == "SUCCESS":
        logger.info(f"[SUCCESS] {msg}")
    else:
        logger.info(msg)
