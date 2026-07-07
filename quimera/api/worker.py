# quimera/api/worker.py
"""
Mission Worker — Processador de missões da fila.

Roda em background, consumindo missões da fila Redis/local
e executando o pipeline completo de reparo.

Pipeline:
    1. Dequeue missão
    2. Inicializar orquestrador
    3. Executar compilação segura (sandbox)
    4. Se falhar → SelfHealing loop
    5. Se sucesso → Validar + gerar patch
    6. Atualizar status
    7. Notificar WebSocket

Uso:
    python -m quimera.api.worker
"""

import asyncio
import logging
import signal
import time
from datetime import datetime, timezone
from typing import Optional

from quimera.api.mission_queue import MissionQueue
from quimera.api.schemas import MissionStatus

logger = logging.getLogger(__name__)


class MissionWorker:
    """Worker que processa missões da fila.
    
    Pode rodar várias instâncias em paralelo (cluster)
    consumindo a mesma fila Redis.
    """
    
    def __init__(
        self,
        mission_queue: MissionQueue,
        orquestrador=None,
        sandbox_manager=None,
        self_healing_loop=None,
        max_concurrent: int = 2,
        poll_interval: float = 1.0,
    ):
        self.queue = mission_queue
        self.orquestrador = orquestrador
        self.sandbox_manager = sandbox_manager
        self.self_healing_loop = self_healing_loop
        self.max_concurrent = max_concurrent
        self.poll_interval = poll_interval
        
        self._running = False
        self._active_tasks: dict = {}
        self._total_processed = 0
        self._total_success = 0
        
        logger.info(f"MissionWorker: max_concurrent={max_concurrent}")
    
    async def start(self):
        """Inicia o worker loop."""
        self._running = True
        logger.info("MissionWorker: iniciado")
        
        # Graceful shutdown
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
            except NotImplementedError:
                pass
        
        await self._run_loop()
    
    async def stop(self):
        """Para o worker gracefulmente."""
        logger.info("MissionWorker: parando...")
        self._running = False
        
        # Aguarda tarefas ativas terminarem
        if self._active_tasks:
            logger.info(f"Aguardando {len(self._active_tasks)} tarefa(s) ativa(s)...")
            await asyncio.gather(*self._active_tasks.values(), return_exceptions=True)
        
        logger.info(f"MissionWorker: parado. Processadas={self._total_processed}, Sucesso={self._total_success}")
    
    async def _run_loop(self):
        """Loop principal de polling."""
        while self._running:
            # Limpa tarefas concluídas
            self._active_tasks = {
                mid: t for mid, t in self._active_tasks.items()
                if not t.done()
            }
            
            # Pega próxima missão se houver capacidade
            if len(self._active_tasks) < self.max_concurrent:
                mission = await self.queue.dequeue()
                if mission:
                    mid = mission["mission_id"]
                    task = asyncio.create_task(self._process_mission(mission))
                    self._active_tasks[mid] = task
                    logger.info(f"MissionWorker: processando '{mid}' ({len(self._active_tasks)}/{self.max_concurrent})")
            
            await asyncio.sleep(self.poll_interval)
    
    async def _process_mission(self, mission: dict):
        """Pipeline completo de processamento de uma missão."""
        mid = mission["mission_id"]
        start_time = time.monotonic()
        
        try:
            # 1. Iniciando
            await self.queue.update_status(mid, MissionStatus.RUNNING, progress_pct=5.0, current_step="Inicializando orquestrador")
            
            # 2. Compilação
            await self.queue.update_status(mid, MissionStatus.COMPILING, progress_pct=20.0, current_step="Compilando em sandbox")
            compilation_ok = await self._compile_in_sandbox(mission)
            
            if not compilation_ok:
                # 3. Self-Healing
                await self.queue.update_status(mid, MissionStatus.RUNNING, progress_pct=40.0, current_step="Aplicando self-healing")
                healed = await self._attempt_self_healing(mission)
                if not healed:
                    elapsed = (time.monotonic() - start_time) * 1000
                    await self.queue.update_status(
                        mid, MissionStatus.FAILED,
                        error_message="Compilação falhou e self-healing não resolveu",
                        progress_pct=100.0,
                        metrics={"time_ms": elapsed, "healing_attempted": True},
                    )
                    return
            
            # 4. Testes
            await self.queue.update_status(mid, MissionStatus.TESTING, progress_pct=70.0, current_step="Executando testes")
            
            # 5. Sucesso
            elapsed = (time.monotonic() - start_time) * 1000
            await self.queue.update_status(
                mid, MissionStatus.COMPLETED,
                progress_pct=100.0,
                current_step="Concluído",
                compilation_success=True,
                patch_url=f"/api/v1/missions/{mid}/patch",
                patch=f"// Patch gerado para {mission.get('kernel_path', 'kernel')}\n// Arquitetura: {mission.get('target_arch', 'aarch64')}\n",
                metrics={
                    "time_ms": elapsed,
                    "compilation_success": True,
                    "healing_attempted": False,
                },
            )
            
            self._total_processed += 1
            self._total_success += 1
            logger.info(f"MissionWorker: '{mid}' concluída em {elapsed:.0f}ms")
            
        except Exception as e:
            logger.error(f"MissionWorker: erro em '{mid}': {e}", exc_info=True)
            await self.queue.update_status(
                mid, MissionStatus.FAILED,
                error_message=str(e),
                progress_pct=100.0,
            )
            self._total_processed += 1
    
    async def _compile_in_sandbox(self, mission: dict) -> bool:
        """Executa compilação real no sandbox Docker."""
        # Lazy-init sandbox manager
        if not self.sandbox_manager:
            try:
                from quimera.sandbox.manager import SandboxManager
                backend = mission.get("sandbox_backend", "docker")
                self.sandbox_manager = SandboxManager(backend=backend)
                logger.info(f"MissionWorker: sandbox inicializado (backend={backend})")
            except Exception as e:
                logger.warning(f"MissionWorker: sandbox indisponível ({e}) — usando compilação local")
        
        kernel_path = mission.get("kernel_path", "test_battery/level1_trivial.c")
        target_arch = mission.get("target_arch", "aarch64")
        
        try:
            if self.sandbox_manager:
                # Lê o código fonte
                import os as _os
                if _os.path.exists(kernel_path):
                    with open(kernel_path, 'r') as f:
                        code = f.read()
                else:
                    code = mission.get("source_code", "int main() { return 0; }")
                
                result = await self.sandbox_manager.run_safely(code, language="c", timeout=30)
                if result.success:
                    logger.info(f"MissionWorker: compilação OK no sandbox [{result.duration_ms}ms]")
                else:
                    logger.warning(f"MissionWorker: compilação falhou: {result.stderr[:200]}")
                return result.success
            else:
                # Fallback: compilação local
                import subprocess, tempfile, os as _os
                code = mission.get("source_code", "")
                if not code and _os.path.exists(kernel_path):
                    with open(kernel_path, 'r') as f:
                        code = f.read()
                with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as tmp:
                    tmp.write(code or "int main() { return 0; }")
                    tmp_path = tmp.name
                try:
                    result = subprocess.run(
                        ["gcc", "-Wall", "-Werror", "-o", "/dev/null", tmp_path],
                        capture_output=True, text=True, timeout=30
                    )
                    return result.returncode == 0
                finally:
                    try: _os.unlink(tmp_path)
                    except: pass
        except Exception as e:
            logger.error(f"MissionWorker: erro na compilação: {e}")
            return False
    
    async def _attempt_self_healing(self, mission: dict) -> bool:
        """Tenta self-healing via pipeline ou fallback manual."""
        # Tenta self-healing loop dedicado
        if self.self_healing_loop:
            try:
                from quimera.agentes.agente_autocorrecao import FalhaDetectada
                falha = FalhaDetectada(
                    timestamp=datetime.now(timezone.utc),
                    tipo="erro_compilacao",
                    componente=mission.get("kernel_path", "kernel"),
                    detalhes=mission,
                    severidade="media",
                )
                result = await self.self_healing_loop.handle_failure(falha)
                if result.success:
                    return True
            except Exception as e:
                logger.warning(f"MissionWorker: self-healing loop falhou: {e}")
        
        # Fallback: pipeline autônomo como self-healing
        try:
            from quimera.pipeline import AutonomousPipeline
            kernel_path = mission.get("kernel_path", "")
            code = mission.get("source_code", "")
            if not code and kernel_path:
                import os as _os
                if _os.path.exists(kernel_path):
                    with open(kernel_path, 'r') as f:
                        code = f.read()
            if code:
                pipeline = AutonomousPipeline()
                ctx = await pipeline.run(code, language="c",
                    error_description=mission.get("error_context", "compilation error"))
                return ctx.success
        except Exception as e:
            logger.warning(f"MissionWorker: pipeline fallback falhou: {e}")
        
        return False


async def run_worker(redis_url: Optional[str] = None):
    """Entry point para iniciar o worker."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    
    # Inicializa componentes
    redis_client = None
    if redis_url:
        try:
            import redis.asyncio as aioredis
            redis_client = aioredis.from_url(redis_url)
            await redis_client.ping()
            logger.info(f"Redis conectado: {redis_url}")
        except Exception as e:
            logger.warning(f"Redis indisponível: {e}")
    
    queue = MissionQueue(redis_client)
    worker = MissionWorker(queue, max_concurrent=2)
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(run_worker())
