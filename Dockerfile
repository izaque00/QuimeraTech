# syntax=docker/dockerfile:1
# ─── Quimera MarkX — Dockerfile v4.0.0 (MetaX) ───
# 
# Ambiente de execução completo com todas as dependências.
# 
# Build:
#   docker build -t quimera-markx .
# 
# Run:
#   docker run -v $(pwd):/workspace quimera-markx repair /workspace
#   docker run -it quimera-markx assist "Meu projeto não compila"
#   docker run -p 8000:8000 quimera-markx serve
#
# Development:
#   docker run -it -v $(pwd):/workspace quimera-markx bash

FROM python:3.13-slim

LABEL org.opencontainers.image.title="Quimera MarkX"
LABEL org.opencontainers.image.description="Agente Cognitivo de Engenharia de Software — MetaX v4.0.0"
LABEL org.opencontainers.image.version="4.0.0"

# ── System dependencies ──
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    clang \
    cmake \
    # For sandbox
    firejail \
    # For fuzzing (optional)
    afl++ \
    # Clean
    && rm -rf /var/lib/apt/lists/*

# ── Workdir ──
WORKDIR /quimera

# ── Python dependencies ──
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir \
    # Web API
    uvicorn[standard] fastapi \
    # LLM (optional, for cognition layer)
    # ollama langchain langchain-community \
    # Notebooks
    # jupyter \
    # Development
    pytest pytest-asyncio pytest-cov pytest-benchmark \
    black ruff mypy

# ── Quimera source ──
COPY . .

# ── Install Quimera ──
RUN pip install -e . 2>/dev/null || echo "Package installed via PYTHONPATH"

# ── Environment ──
ENV PYTHONPATH=/quimera
ENV QUIMERA_HOME=/quimera
ENV QUIMERA_ENV=production

# ── Entrypoint ──
ENTRYPOINT ["python3", "-m", "quimera.cli"]

# Default: help
CMD ["--help"]
