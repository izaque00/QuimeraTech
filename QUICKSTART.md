# Quimera MarkX — Quickstart

## Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) + Docker Compose
- 1 chave de API LLM ([Groq é grátis](https://console.groq.com))

## 5 minutos para produção

```bash
# 1. Configurar chave LLM
echo "GROQ_API_KEY=gsk_seu_token" >> .env

# 2. Subir API + Workers + Redis
docker-compose up -d

# 3. Verificar
curl http://localhost:8000/api/v1/health
# → {"status":"healthy","version":"3.0.0","agents_loaded":16}

# 4. Dashboard
open http://localhost:8000/dashboard

# 5. Primeira missão
curl -X POST http://localhost:8000/api/v1/missions \
  -H "Content-Type: application/json" \
  -d '{"kernel_path":"test_battery/level1_trivial.c","target_arch":"aarch64"}'
```

## Modos de uso

### CLI (linha de comando)
```bash
docker run -v $(pwd):/workspace quimera repair /workspace/meu_driver.c
docker run -it quimera audit /workspace/ --cve --red-team
docker run quimera explain /workspace/ --detail=all
```

### API REST
```bash
POST   /api/v1/missions          # Criar missão
GET    /api/v1/missions/{id}     # Status da missão
GET    /api/v1/missions/{id}/patch  # Download do patch
GET    /api/v1/health            # Health check
GET    /metrics                  # Prometheus metrics
GET    /dashboard                # Dashboard HTML
```

### Python SDK
```python
from quimera.pipeline import AutonomousPipeline
import asyncio

pipeline = AutonomousPipeline()
ctx = asyncio.run(pipeline.run("""
    int main() { 
        char buf[10]; 
        strcpy(buf, "overflow"); 
        return 0; 
    }
""", language="c", error_description="CWE-121"))

print(f"Fitness: {ctx.fitness_score:.3f}")
print(f"Patches: {len(ctx.evolved_patches)}")
print(f"Stages: {ctx.stages_completed}")
```

## Stack de monitoring

```bash
# Subir com Prometheus + Grafana
docker-compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d

# Grafana: http://localhost:3000 (admin/admin)
# Prometheus: http://localhost:9090
```

## Testes

```bash
# Test battery completa (6 níveis)
PYTHONPATH=. python quimera/scripts/run_test_battery.py

# Unit tests
make test

# Lint
make lint
```

## Arquitetura (H1→H6)

```
Mission → H1:ACCEPT (roteamento)
       → H2:RETRIEVE (memória de patches anteriores)
       → H3:VERIFY (análise estática de segurança)
       → H4:EVOLVE (NSGA-II genético, 30 gerações)
       → H5:ATTACK (RedTeam + Fuzzing 10K iters)
       → H6:OUTPUT (patch multi-linguagem)
       → H2_rec:RECORD (persistência para ML futuro)
```

## Solução de problemas

| Problema | Solução |
|----------|---------|
| `GROQ_API_KEY` não setada | https://console.groq.com → criar chave gratuita |
| Docker build falha | `docker system prune -a && docker-compose build --no-cache` |
| Redis não conecta | `docker-compose down -v && docker-compose up -d` |
| Pipeline lento sem GPU | Usar Groq (inferência rápida gratuita) |
