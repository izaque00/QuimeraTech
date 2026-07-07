# quimera/api/task_runner.py
"""
Task Runner — Executor assíncrono de tarefas do Quimera.

Sistema leve de fila de tarefas (sem dependência de Celery)
para orquestração de missões em cluster.

Suporta:
  - Execução concorrente com Semaphore
  - Retry automático com backoff
  - Prioridade de missões
  - Health check de workers

Uso:
    from quimera.api.task_runner import TaskRunner
    
    runner = TaskRunner(max_workers=4)
    runner.start()
    result = await runner.submit(mission_data)
"""

import asyncio
import heapq
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    LOW = 0
    NORMAL = 5
    HIGH = 8
    URGENT = 10


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass(order=True)
class PrioritizedTask:
    """Tarefa com prioridade para heap."""
    priority: int
    created_at: float = field(compare=False)
    task_id: str = field(compare=False)
    data: Dict[str, Any] = field(compare=False)


@dataclass
class TaskResult:
    """Resultado de uma tarefa."""
    task_id: str
    status: TaskStatus
    result: Any = None
    error: Optional[str] = None
    attempts: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time_ms: float = 0.0


class TaskRunner:
    """Executor de tarefas com fila de prioridade.
    
    Alternativa leve ao Celery para orquestração interna.
    """
    
    def __init__(
        self,
        max_workers: int = 4,
        max_retries: int = 3,
        retry_delay: float = 5.0,
        task_timeout: float = 300.0,
    ):
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.task_timeout = task_timeout
        
        self._queue: List[PrioritizedTask] = []
        self._results: Dict[str, TaskResult] = {}
        self._active: Dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(max_workers)
        self._running = False
        self._handler: Optional[Callable] = None
        
        logger.info(f"TaskRunner: max_workers={max_workers}, max_retries={max_retries}")
    
    def register_handler(self, handler: Callable[[Dict], Any]):
        """Registra função que processa cada tarefa."""
        self._handler = handler
    
    async def submit(
        self,
        data: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> str:
        """Submete uma tarefa à fila.
        
        Args:
            data: Dados da tarefa.
            priority: Prioridade (TaskPriority).
            
        Returns:
            task_id.
        """
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        
        task = PrioritizedTask(
            priority=-priority.value,  # heapq é min-heap
            created_at=time.time(),
            task_id=task_id,
            data={"task_id": task_id, **data},
        )
        
        heapq.heappush(self._queue, task)
        self._results[task_id] = TaskResult(task_id=task_id, status=TaskStatus.PENDING)
        
        logger.debug(f"TaskRunner: '{task_id}' enfileirada (priority={priority.name})")
        return task_id
    
    async def start(self):
        """Inicia o processamento de tarefas."""
        self._running = True
        logger.info("TaskRunner: iniciado")
        
        poll_task = asyncio.create_task(self._poll_loop())
        await poll_task
    
    async def stop(self):
        """Para o runner."""
        self._running = False
        logger.info(f"TaskRunner: parando ({len(self._active)} ativas)...")
        
        if self._active:
            await asyncio.gather(*self._active.values(), return_exceptions=True)
        
        total = len(self._results)
        success = sum(1 for r in self._results.values() if r.status == TaskStatus.COMPLETED)
        logger.info(f"TaskRunner: parado — {success}/{total} sucesso")
    
    async def _poll_loop(self):
        """Loop de polling da fila."""
        while self._running:
            if self._queue and len(self._active) < self.max_workers:
                task = heapq.heappop(self._queue)
                coro = self._execute_task(task)
                self._active[task.task_id] = asyncio.create_task(coro)
            
            # Limpa tarefas concluídas
            self._active = {tid: t for tid, t in self._active.items() if not t.done()}
            
            await asyncio.sleep(0.1)
    
    async def _execute_task(self, task: PrioritizedTask):
        """Executa uma tarefa com retry."""
        result = self._results[task.task_id]
        result.started_at = datetime.now(timezone.utc)
        start = time.monotonic()
        
        for attempt in range(self.max_retries + 1):
            result.attempts = attempt + 1
            self._results[task.task_id].status = TaskStatus.RUNNING if attempt == 0 else TaskStatus.RETRYING
            
            try:
                if self._handler:
                    output = await asyncio.wait_for(
                        self._execute_handler(task.data),
                        timeout=self.task_timeout,
                    )
                else:
                    output = {"status": "ok", "note": "no handler registered"}
                
                elapsed = (time.monotonic() - start) * 1000
                result.status = TaskStatus.COMPLETED
                result.result = output
                result.completed_at = datetime.now(timezone.utc)
                result.execution_time_ms = elapsed
                logger.info(f"TaskRunner: '{task.task_id}' concluída ({elapsed:.0f}ms, attempt {attempt+1})")
                return
                
            except asyncio.TimeoutError:
                logger.warning(f"TaskRunner: '{task.task_id}' timeout ({self.task_timeout}s)")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    result.status = TaskStatus.FAILED
                    result.error = f"Timeout após {self.max_retries + 1} tentativas"
                    
            except Exception as e:
                logger.warning(f"TaskRunner: '{task.task_id}' erro (attempt {attempt+1}): {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    result.status = TaskStatus.FAILED
                    result.error = str(e)
        
        result.completed_at = datetime.now(timezone.utc)
        result.execution_time_ms = (time.monotonic() - start) * 1000
    
    async def _execute_handler(self, data: Dict) -> Any:
        """Executa o handler (pode ser sobrescrito)."""
        if asyncio.iscoroutinefunction(self._handler):
            return await self._handler(data)
        return self._handler(data)
    
    def get_result(self, task_id: str) -> Optional[TaskResult]:
        """Obtém resultado de uma tarefa."""
        return self._results.get(task_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Estatísticas do runner."""
        total = len(self._results)
        return {
            "queue_size": len(self._queue),
            "active_tasks": len(self._active),
            "total_processed": total,
            "completed": sum(1 for r in self._results.values() if r.status == TaskStatus.COMPLETED),
            "failed": sum(1 for r in self._results.values() if r.status == TaskStatus.FAILED),
            "pending": sum(1 for r in self._results.values() if r.status == TaskStatus.PENDING),
        }
