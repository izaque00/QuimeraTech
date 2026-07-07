# quimera/api/__init__.py
"""
API REST do Quimera — Expõe o sistema como serviço HTTP.

FastAPI com endpoints para submissão de missões, acompanhamento
em tempo real, e download de patches.

Rotas principais:
    POST   /api/v1/missions          — Submeter nova missão
    GET    /api/v1/missions/{id}     — Status da missão
    GET    /api/v1/missions/{id}/patch — Download do patch
    GET    /api/v1/health            — Health check
    GET    /api/v1/agents            — Listar agentes ativos
    GET    /api/v1/metrics           — Métricas do sistema
    WS     /api/v1/missions/{id}/ws — Acompanhamento em tempo real
"""

from quimera.api.server import create_app

__all__ = ["create_app"]
