"""Environment configuration."""
import os

class EnvConfig:
    """Configuração de ambiente."""
    env = os.getenv("QUIMERA_ENV", "development")
    debug = os.getenv("QUIMERA_DEBUG", "false").lower() == "true"
