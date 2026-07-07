"""
AEGIS Security Core - Sistema de Segurança Ultra-Avançado para Quimera
=====================================================================

O AEGIS é um órgão de segurança especializado que protege todo o sistema Quimera
com técnicas avançadas de detecção, prevenção e resposta a ameaças.
"""

__version__ = "1.0.0"
__author__ = "AEGIS Security Team"

# Importações principais
try:
    from .aegis_core import AegisCore
    from .malware_detector import MalwareDetector
    from .integrity_monitor import IntegrityMonitor
    from .behavior_analyzer import BehaviorAnalyzer
    from .crypto_engine import CryptoEngine
    from .aegis_agent import AegisSecurityAgent
    from .aegis_plugin import AegisSecurityPlugin
    from .aegis_dashboard import AegisDashboard
    
    AEGIS_AVAILABLE = True
    
except ImportError as e:
    # Em caso de dependências faltantes
    AEGIS_AVAILABLE = False
    import logging
    logging.warning(f"AEGIS Security Core com funcionalidades limitadas: {e}")

__all__ = [
    'AegisCore',
    'MalwareDetector', 
    'IntegrityMonitor',
    'BehaviorAnalyzer',
    'CryptoEngine',
    'AegisSecurityAgent',
    'AegisSecurityPlugin',
    'AegisDashboard',
    'AEGIS_AVAILABLE'
]