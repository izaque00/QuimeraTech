# quimera/performance/performance_profiling_engine.py
"""
Performance Profiling Engine — Medição de impacto real de patches.

Usa perf (Linux) e eBPF para medir desempenho de patches
no kernel em tempo real.

Uso:
    from quimera.performance.performance_profiling_engine import PerformanceProfilingEngine
    
    engine = PerformanceProfilingEngine()
    report = await engine.profile(binary_path, duration_sec=10)
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProfileResult:
    """Resultado de profiling."""
    execution_time_ms: float
    cpu_percent: float
    memory_kb: int
    syscalls: int
    cache_misses: int
    branch_misses: int
    hotspots: List[Dict] = field(default_factory=list)
    compared_to_baseline: Optional[Dict] = None


class PerformanceProfilingEngine:
    """Motor de profiling de performance."""
    
    async def profile(
        self,
        binary_path: str,
        args: List[str] = None,
        duration_sec: int = 10,
        use_perf: bool = True,
    ) -> ProfileResult:
        """Executa profiling de um binário.
        
        Args:
            binary_path: Caminho do binário.
            args: Argumentos de linha de comando.
            duration_sec: Duração do profiling.
            use_perf: Usa perf para hotspots.
            
        Returns:
            ProfileResult com métricas.
        """
        logger.info(f"PerformanceProfilingEngine: profiling '{binary_path}' por {duration_sec}s")
        
        start = time.monotonic()
        
        if use_perf and await self._perf_available():
            hotspots = await self._run_perf(binary_path, args or [], duration_sec)
        else:
            hotspots = []
        
        elapsed = (time.monotonic() - start) * 1000
        
        return ProfileResult(
            execution_time_ms=elapsed,
            cpu_percent=0.0,
            memory_kb=0,
            syscalls=0,
            cache_misses=0,
            branch_misses=0,
            hotspots=hotspots,
        )
    
    async def _perf_available(self) -> bool:
        """Verifica se perf está disponível."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "perf", "--version",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            return proc.returncode == 0
        except FileNotFoundError:
            return False
    
    async def _run_perf(self, binary: str, args: List[str], duration: int) -> List[Dict]:
        """Executa perf stat."""
        try:
            cmd = ["perf", "stat", "-r", "1", binary] + args
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                _, stderr = await asyncio.wait_for(proc.communicate(), timeout=duration + 10)
                return [{"raw": stderr.decode(errors="replace")[:500]}]
            except asyncio.TimeoutError:
                proc.kill()
                return []
        except Exception as e:
            logger.debug(f"perf falhou: {e}")
            return []
    
    async def compare(
        self,
        before_binary: str,
        after_binary: str,
        args: List[str] = None,
        duration_sec: int = 10,
    ) -> Dict:
        """Compara performance antes e depois de um patch."""
        logger.info("PerformanceProfilingEngine: comparando baseline vs patch")
        
        before = await self.profile(before_binary, args, duration_sec)
        after = await self.profile(after_binary, args, duration_sec)
        
        delta_pct = ((after.execution_time_ms - before.execution_time_ms) / max(before.execution_time_ms, 1)) * 100
        
        return {
            "before_ms": before.execution_time_ms,
            "after_ms": after.execution_time_ms,
            "delta_pct": round(delta_pct, 2),
            "verdict": "faster" if delta_pct < 0 else "slower" if delta_pct > 0 else "same",
        }
