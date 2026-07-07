# quimera/api/mission_queue.py
"""
Fila de missões usando Redis (pub/sub + listas).

Coordena missões entre múltiplas instâncias Quimera.
Usa Redis para:
  - Fila de missões pendentes (LPUSH/RPOP)
  - Status de missão em hash (HSET/HGET)
  - Pub/Sub para notificações em tempo real

Uso:
    from quimera.api.mission_queue import MissionQueue
    
    queue = MissionQueue(redis_client)
    mission_id = await queue.enqueue(mission_data)
    status = await queue.get_status(mission_id)
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from quimera.api.schemas import MissionStatus

logger = logging.getLogger(__name__)

# Prefixos de chave Redis
KEY_PREFIX = "quimera:"
QUEUE_KEY = KEY_PREFIX + "mission_queue"
STATUS_KEY = KEY_PREFIX + "mission:{}"      # mission:{id}
RESULT_KEY = KEY_PREFIX + "mission:{}:result"
CHANNEL_KEY = KEY_PREFIX + "mission:{}:updates"


class MissionQueue:
    """Fila de missões distribuída via Redis."""
    
    def __init__(self, redis_client=None):
        self.redis = redis_client
        self._local_queue: List[str] = []
        self._local_status: Dict[str, Dict] = {}
        self._use_redis = redis_client is not None
        if self._use_redis:
            logger.info("MissionQueue: usando Redis para fila distribuída")
        else:
            logger.info("MissionQueue: usando fila local (modo single-instance)")
    
    async def enqueue(self, mission_data: Dict[str, Any]) -> str:
        """Enfileira uma nova missão.
        
        Args:
            mission_data: Dados da missão (MissionCreate como dict).
            
        Returns:
            mission_id único.
        """
        mission_id = f"qm-{uuid.uuid4().hex[:12]}"
        
        payload = {
            "mission_id": mission_id,
            "status": MissionStatus.QUEUED.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "progress_pct": 0.0,
            **mission_data,
        }
        
        if self._use_redis:
            await self._redis_enqueue(mission_id, payload)
        else:
            self._local_queue.append(mission_id)
            self._local_status[mission_id] = payload
        
        logger.info(f"MissionQueue: missão '{mission_id}' enfileirada")
        return mission_id
    
    async def dequeue(self) -> Optional[Dict[str, Any]]:
        """Remove e retorna a próxima missão da fila."""
        if self._use_redis:
            return await self._redis_dequeue()
        elif self._local_queue:
            mission_id = self._local_queue.pop(0)
            return self._local_status.get(mission_id)
        return None
    
    async def update_status(
        self,
        mission_id: str,
        status: MissionStatus,
        progress_pct: float = 0.0,
        current_step: Optional[str] = None,
        error_message: Optional[str] = None,
        **kwargs,
    ):
        """Atualiza status de uma missão."""
        update = {
            "status": status.value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "progress_pct": progress_pct,
        }
        if current_step:
            update["current_step"] = current_step
        if error_message:
            update["error_message"] = error_message
        update.update(kwargs)
        
        if self._use_redis:
            await self._redis_update_status(mission_id, update)
        elif mission_id in self._local_status:
            self._local_status[mission_id].update(update)
    
    async def get_status(self, mission_id: str) -> Optional[Dict[str, Any]]:
        """Obtém status de uma missão."""
        if self._use_redis:
            return await self._redis_get_status(mission_id)
        return self._local_status.get(mission_id)
    
    async def get_queue_size(self) -> int:
        """Tamanho da fila."""
        if self._use_redis:
            return await self._redis_queue_size()
        return len(self._local_queue)
    
    async def list_active(self) -> List[Dict[str, Any]]:
        """Lista missões ativas (não completadas/falhas)."""
        if self._use_redis:
            return await self._redis_list_active()
        return [
            m for m in self._local_status.values()
            if m["status"] not in (MissionStatus.COMPLETED.value, MissionStatus.FAILED.value, MissionStatus.CANCELLED.value)
        ]
    
    # --- Redis implementations ---
    
    async def _redis_enqueue(self, mission_id: str, payload: Dict):
        await self.redis.set(STATUS_KEY.format(mission_id), json.dumps(payload))
        await self.redis.lpush(QUEUE_KEY, mission_id)
    
    async def _redis_dequeue(self) -> Optional[Dict]:
        mid = await self.redis.rpop(QUEUE_KEY)
        if mid:
            data = await self.redis.get(STATUS_KEY.format(mid.decode() if isinstance(mid, bytes) else mid))
            return json.loads(data) if data else None
        return None
    
    async def _redis_update_status(self, mission_id: str, update: Dict):
        key = STATUS_KEY.format(mission_id)
        current = await self.redis.get(key)
        if current:
            data = json.loads(current)
            data.update(update)
            await self.redis.set(key, json.dumps(data))
    
    async def _redis_get_status(self, mission_id: str) -> Optional[Dict]:
        data = await self.redis.get(STATUS_KEY.format(mission_id))
        return json.loads(data) if data else None
    
    async def _redis_queue_size(self) -> int:
        return await self.redis.llen(QUEUE_KEY) or 0
    
    async def _redis_list_active(self) -> List[Dict]:
        keys = await self.redis.keys(STATUS_KEY.format("*"))
        result = []
        for k in keys:
            data = await self.redis.get(k)
            if data:
                d = json.loads(data)
                if d.get("status") not in ("completed", "failed", "cancelled"):
                    result.append(d)
        return result
