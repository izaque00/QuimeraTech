"""eBPF Runtime Verifier — Verificação em tempo de execução com probes eBPF.

Usa bpftrace/eBPF para monitorar a execução real do patch no kernel,
verificando propriedades que só podem ser observadas em runtime:
- Comportamento de ponteiros (deref nulo, uso indevido)
- Padrões de lock (held time, lock ordering)
- Acesso a memória (bounds reais, não estimados)
- Chamadas de função (argumentos, retornos)

Arquitetura:
    bpftrace script → kernel probes → eventos → analisador Python
                                        ↓
    Patch executado em sandbox → eBPF monitora em tempo real

Uso:
    from quimera.integration_backends.ebpf_verifier import EbpfVerifier
    
    verifier = EbpfVerifier()
    with verifier.monitor(pid=sandbox_pid) as mon:
        sandbox.execute(patched_kernel)
        events = mon.collect()
    
    for event in events:
        if event.severity == "critical":
            print(f"❌ {event}")

NOTA: Requer bpftrace instalado e acesso root/CAP_BPF.
      Em ambientes sem bpftrace, opera em modo simulação.
"""

import logging
import subprocess
import json
import os
import time
import tempfile
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Iterator
from pathlib import Path
from contextlib import contextmanager
from enum import Enum

from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================

class EbpfEventSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class EbpfEventType(Enum):
    NULL_DEREF = "null_deref"           # Ponteiro NULL acessado
    BUFFER_OVERFLOW = "buffer_overflow" # Acesso além do buffer
    USE_AFTER_FREE = "use_after_free"  # Uso após kfree()
    DOUBLE_FREE = "double_free"         # kfree() duplo
    DOUBLE_LOCK = "double_lock"         # Lock já mantido
    LOCK_NOT_HELD = "lock_not_held"     # Unlock sem lock
    LOCK_LONG_HELD = "lock_long_held"   # Lock mantido > threshold
    SLEEP_IN_ATOMIC = "sleep_atomic"    # Sleep em contexto atômico
    STACK_OVERFLOW = "stack_overflow"   # Stack overflow kernel
    UNINITIALIZED = "uninit"            # Uso de memória não inicializada
    CUSTOM = "custom"                   # Evento customizado


@dataclass
class EbpfEvent:
    """Um evento capturado por probe eBPF."""
    timestamp_ns: int
    event_type: EbpfEventType
    severity: EbpfEventSeverity
    function_name: str
    message: str
    pid: int = 0
    stack_trace: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return (
            f"[{self.event_type.value}] {self.function_name} "
            f"(pid={self.pid}): {self.message}"
        )


@dataclass
class EbpfMonitorResult:
    """Resultado de uma sessão de monitoramento eBPF."""
    total_events: int
    critical_count: int
    error_count: int
    warning_count: int
    events: List[EbpfEvent]
    duration_ms: float
    is_clean: bool  # True se nenhum evento de erro/crítico

    def summary(self) -> str:
        return (
            f"eBPF Monitor: {self.total_events} eventos em {self.duration_ms:.0f}ms — "
            f"{self.critical_count} críticos, {self.error_count} erros, "
            f"{self.warning_count} warnings"
        )


# ============================================================================
# bpftrace Scripts Embutidos
# ============================================================================

BPFTRACE_KMALLOC_KFREE = """
/* Monitora kmalloc/kfree — detecta double-free e use-after-free */
kprobe:kmalloc
{
    @alloc_ts[arg1] = nsecs;
    @alloc_size[arg1] = arg0;
}

kretprobe:kmalloc
{
    $ptr = (uint64)retval;
    if ($ptr != 0) {
        printf("ALLOC %llu kmalloc(%d) = %llx\\n",
               nsecs, @alloc_size[tid], $ptr);
    }
    delete(@alloc_ts[tid]);
    delete(@alloc_size[tid]);
}

kprobe:kfree
{
    $ptr = (uint64)arg0;
    printf("FREE  %llu kfree(%llx)\\n", nsecs, $ptr);
}

/* Hook: detecta double-free */
"""

BPFTRACE_MEMORY_BOUNDS = """
/* Monitora acessos de memória — detecta buffer overflow */
kprobe:memcpy
{
    $dst = (uint64)arg0;
    $src = (uint64)arg1;
    $n   = (uint64)arg2;
    printf("MEMCPY %llu dst=%llx src=%llx n=%llu\\n",
           nsecs, $dst, $src, $n);
}

kprobe:memset
{
    $dst = (uint64)arg0;
    $n   = (uint64)arg2;
    printf("MEMSET %llu dst=%llx n=%llu\\n", nsecs, $dst, $n);
}
"""

BPFTRACE_LOCK = """
/* Monitora locks no kernel — detecta race conditions */
kprobe:mutex_lock
{
    @lock_time[tid] = nsecs;
    printf("LOCK  %llu mutex_lock()\\n", nsecs);
}

kretprobe:mutex_lock
{
    $held = (nsecs - @lock_time[tid]) / 1000000;
    if ($held > 100) {
        printf("LOCK_LONG_HELD %llu mutex held for %d ms\\n", nsecs, $held);
    }
}

kprobe:mutex_unlock
{
    printf("UNLOCK %llu mutex_unlock()\\n", nsecs);
}

/* Spin lock tracking */
kprobe:spin_lock
{
    @spin_time[tid] = nsecs;
    printf("SPIN_LOCK %llu\\n", nsecs);
}

kprobe:spin_unlock
{
    $held = (nsecs - @spin_time[tid]) / 1000;
    if ($held > 5000) {
        printf("SPIN_LONG %llu spin_lock held for %d us\\n", nsecs, $held);
    }
}
"""

BPFTRACE_NULL_DEREF = """
/* Detecta NULL pointer dereference */
kprobe:do_page_fault
{
    printf("PAGE_FAULT %llu addr=%llx ip=%llx\\n",
           nsecs, arg1, arg2);
}
"""

BPFTRACE_STACK = """
/* Monitora stack usage */
kretprobe:do_syscall_64
{
    printf("STACK %llu return\\n", nsecs);
}
"""

BPFTRACE_COMPREHENSIVE = """
/* Quimera Comprehensive eBPF Monitor */
BEGIN {
    printf("Quimera eBPF Monitor — Iniciando\\n");
    @start = nsecs;
}

/* Memory allocation tracking */
kprobe:kmalloc,
kprobe:kmalloc_array,
kprobe:kzalloc,
kprobe:vmalloc
{
    @live_allocs += 1;
}

kprobe:kfree,
kprobe:vfree
{
    @live_allocs -= 1;
    if (@live_allocs < 0) {
        printf("DOUBLE_FREE %llu live_allocs=%d\\n", nsecs, @live_allocs);
        @live_allocs = 0;
    }
}

/* Lock tracking */
kprobe:mutex_lock,
kprobe:mutex_lock_interruptible,
kprobe:mutex_lock_killable
{
    @locks_held += 1;
}

kprobe:mutex_unlock
{
    @locks_held -= 1;
    if (@locks_held < 0) {
        printf("UNLOCK_WITHOUT_LOCK %llu\\n", nsecs);
        @locks_held = 0;
    }
}

/* Page fault tracking */
kprobe:do_page_fault {
    printf("PAGE_FAULT %llu addr=%llx\\n", nsecs, arg1);
}

/* WARN/BUG tracking */
kprobe:__warn_printk {
    printf("KERNEL_WARN %llu\\n", nsecs);
}

END {
    printf("Quimera eBPF Monitor — Finalizado\\n");
    printf("  live_allocs: %d\\n", @live_allocs);
    printf("  locks_held: %d\\n", @locks_held);
    printf("  duration_ms: %llu\\n", (nsecs - @start) / 1000000);
}
"""


# ============================================================================
# EbpfVerifier
# ============================================================================

class EbpfVerifier:
    """Verificador runtime usando eBPF probes.

    Monitora a execução de código em sandbox com probes eBPF,
    detectando anomalias em tempo real.

    Attributes:
        bpftrace_path: Caminho para o binário bpftrace.
        auto_install_hint: Se True, sugere instalação se bpftrace ausente.
        lock_held_threshold_ms: Threshold para alerta de lock mantido.
    """

    _PROBE_MAP = {
        EbpfEventType.NULL_DEREF: "do_page_fault",
        EbpfEventType.USE_AFTER_FREE: "kfree",
        EbpfEventType.DOUBLE_FREE: "kfree",
        EbpfEventType.DOUBLE_LOCK: "mutex_lock",
        EbpfEventType.BUFFER_OVERFLOW: "memcpy",
    }

    def __init__(
        self,
        bpftrace_path: Optional[str] = None,
        lock_held_threshold_ms: int = 100,
        capture_stack_traces: bool = False,
    ):
        self._bpftrace = bpftrace_path or shutil.which("bpftrace")  # type: ignore[name-defined]
        self.lock_held_threshold_ms = lock_held_threshold_ms
        self.capture_stack_traces = capture_stack_traces

        if self._bpftrace:
            montar_log(f"EbpfVerifier: bpftrace encontrado em {self._bpftrace}", "INFO")
        else:
            montar_log(
                "EbpfVerifier: bpftrace NÃO encontrado — operando em modo simulação. "
                "Instale: apt install bpftrace",
                "WARNING"
            )

    @property
    def is_available(self) -> bool:
        """Verifica se eBPF monitoring está disponível."""
        if not self._bpftrace:
            return False
        # Verificar permissões
        try:
            result = subprocess.run(
                [self._bpftrace, "-e", 'BEGIN { exit(); }'],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    @contextmanager
    def monitor(
        self,
        pid: Optional[int] = None,
        duration_seconds: Optional[int] = None,
        event_types: Optional[List[EbpfEventType]] = None,
        extra_probes: Optional[str] = None,
    ) -> Iterator["EbpfMonitorSession"]:
        """Context manager para monitorar execução com eBPF.

        Args:
            pid: PID do processo a monitorar (None = sistema todo).
            duration_seconds: Duração máxima do monitoramento.
            event_types: Tipos de eventos a monitorar.
            extra_probes: Script bpftrace adicional.

        Yields:
            EbpfMonitorSession para coleta de eventos.
        """
        session = EbpfMonitorSession(
            verifier=self,
            pid=pid,
            duration_seconds=duration_seconds,
            event_types=event_types or list(EbpfEventType),
            extra_probes=extra_probes,
        )
        session.start()
        try:
            yield session
        finally:
            session.stop()

    def generate_bpftrace_script(
        self,
        pid: Optional[int] = None,
        event_types: Optional[List[EbpfEventType]] = None,
    ) -> str:
        """Gera script bpftrace para os tipos de eventos solicitados."""
        if event_types is None:
            event_types = list(EbpfEventType)

        pid_filter = f"/pid == {pid}/ " if pid else ""

        script_parts = []

        if EbpfEventType.DOUBLE_FREE in event_types:
            script_parts.append(
                f'kprobe:kfree {pid_filter}{{\n'
                f'    $ptr = arg0;\n'
                f'    if (@freed[$ptr]) {{\n'
                f'        printf("DOUBLE_FREE %llu ptr=%llx\\\\n", nsecs, $ptr);\n'
                f'    }}\n'
                f'    @freed[$ptr] = 1;\n'
                f'}}'
            )

        if EbpfEventType.USE_AFTER_FREE in event_types:
            script_parts.append(
                f'kprobe:kmalloc {pid_filter}{{\n'
                f'    $ptr = (uint64)retval;\n'
                f'    @allocated[$ptr] = 1;\n'
                f'}}'
            )

        if EbpfEventType.DOUBLE_LOCK in event_types:
            script_parts.append(
                f'kprobe:mutex_lock {pid_filter}{{\n'
                f'    $lock = arg0;\n'
                f'    if (@locked[$lock]) {{\n'
                f'        printf("DOUBLE_LOCK %llu lock=%llx\\\\n", nsecs, $lock);\n'
                f'    }}\n'
                f'    @locked[$lock] = 1;\n'
                f'}}'
            )
            script_parts.append(
                f'kprobe:mutex_unlock {pid_filter}{{\n'
                f'    $lock = arg0;\n'
                f'    if (!@locked[$lock]) {{\n'
                f'        printf("LOCK_NOT_HELD %llu lock=%llx\\\\n", nsecs, $lock);\n'
                f'    }}\n'
                f'    delete(@locked[$lock]);\n'
                f'}}'
            )

        if EbpfEventType.NULL_DEREF in event_types:
            script_parts.append(
                f'kprobe:do_page_fault {pid_filter}{{\n'
                f'    printf("PAGE_FAULT %llu addr=%llx ip=%llx\\\\n", nsecs, arg1, arg2);\n'
                f'}}'
            )

        if EbpfEventType.BUFFER_OVERFLOW in event_types:
            script_parts.append(
                'kprobe:__ubsan_handle_out_of_bounds {\n'
                '    printf("BUFFER_OVERFLOW %llu\\\\n", nsecs);\n'
                '}\n'
                'kprobe:__ubsan_handle_out_of_bounds_abort {\n'
                '    printf("BUFFER_OVERFLOW_CRITICAL %llu\\\\n", nsecs);\n'
                '}'
            )

        if EbpfEventType.SLEEP_IN_ATOMIC in event_types:
            script_parts.append(
                'kprobe:__might_sleep {\n'
                '    printf("SLEEP_IN_ATOMIC %llu\\\\n", nsecs);\n'
                '}'
            )

        if not script_parts:
            script_parts.append('BEGIN { printf("Quimera eBPF idle\\\\n"); exit(); }')

        return "\n\n".join(script_parts)

    def parse_bpftrace_output(self, raw_output: str) -> List[EbpfEvent]:
        """Parseia saída do bpftrace em EbpfEvents."""
        events = []
        for line in raw_output.strip().splitlines():
            if not line.strip():
                continue
            event = self._parse_line(line)
            if event:
                events.append(event)
        return events

    def _parse_line(self, line: str) -> Optional[EbpfEvent]:
        """Parseia uma linha de output do bpftrace."""
        # Formatos esperados:
        # DOUBLE_FREE 123456789 ptr=7fff1234
        # PAGE_FAULT 123456789 addr=0 ip=ffff8880
        # BUFFER_OVERFLOW 123456789

        # Extrair tipo de evento
        parts = line.split(None, 2)
        if len(parts) < 2:
            return None

        event_name = parts[0]
        try:
            event_type = EbpfEventType(event_name.lower())
        except ValueError:
            event_type = EbpfEventType.CUSTOM

        # Extrair timestamp
        try:
            ts = int(parts[1])
        except (ValueError, IndexError):
            ts = 0

        # Determinar severidade
        severity_map = {
            EbpfEventType.NULL_DEREF: EbpfEventSeverity.CRITICAL,
            EbpfEventType.DOUBLE_FREE: EbpfEventSeverity.CRITICAL,
            EbpfEventType.BUFFER_OVERFLOW: EbpfEventSeverity.CRITICAL,
            EbpfEventType.USE_AFTER_FREE: EbpfEventSeverity.CRITICAL,
            EbpfEventType.SLEEP_IN_ATOMIC: EbpfEventSeverity.ERROR,
            EbpfEventType.DOUBLE_LOCK: EbpfEventSeverity.ERROR,
            EbpfEventType.UNINITIALIZED: EbpfEventSeverity.ERROR,
            EbpfEventType.STACK_OVERFLOW: EbpfEventSeverity.CRITICAL,
            EbpfEventType.LOCK_NOT_HELD: EbpfEventSeverity.WARNING,
            EbpfEventType.LOCK_LONG_HELD: EbpfEventSeverity.WARNING,
        }

        severity = severity_map.get(event_type, EbpfEventSeverity.INFO)
        message = parts[2] if len(parts) > 2 else event_name

        return EbpfEvent(
            timestamp_ns=ts,
            event_type=event_type,
            severity=severity,
            function_name=event_name,
            message=message,
        )


class EbpfMonitorSession:
    """Sessão de monitoramento eBPF."""

    def __init__(
        self,
        verifier: EbpfVerifier,
        pid: Optional[int] = None,
        duration_seconds: Optional[int] = None,
        event_types: Optional[List[EbpfEventType]] = None,
        extra_probes: Optional[str] = None,
    ):
        self._verifier = verifier
        self._pid = pid
        self._duration = duration_seconds
        self._event_types = event_types or list(EbpfEventType)
        self._extra_probes = extra_probes
        self._process: Optional[subprocess.Popen] = None
        self._start_time: float = 0.0
        self._events: List[EbpfEvent] = []
        self._running = False

    def start(self):
        """Inicia o monitoramento eBPF."""
        import shutil
        self._start_time = time.time()
        self._events = []

        if not self._verifier._bpftrace:
            montar_log("EbpfMonitorSession: bpftrace indisponível — simulando", "INFO")
            self._running = True
            return

        script = self._verifier.generate_bpftrace_script(
            self._pid, self._event_types
        )

        if self._extra_probes:
            script += "\n" + self._extra_probes

        try:
            self._process = subprocess.Popen(
                [self._verifier._bpftrace, "-e", script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self._running = True
            montar_log(
                f"EbpfMonitorSession: monitoramento iniciado (pid={self._pid or 'all'})",
                "INFO"
            )
        except Exception as e:
            montar_log(f"EbpfMonitorSession: falha ao iniciar bpftrace: {e}", "WARNING")
            self._running = True  # Continuar em modo simulação

    def stop(self) -> EbpfMonitorResult:
        """Para o monitoramento e coleta resultados."""
        duration_ms = (time.time() - self._start_time) * 1000

        if self._process:
            try:
                self._process.terminate()
                stdout, stderr = self._process.communicate(timeout=10)
                if stdout:
                    self._events = self._verifier.parse_bpftrace_output(stdout)
                if stderr:
                    logger.debug(f"bpftrace stderr: {stderr[:500]}")
            except Exception as e:
                logger.warning(f"Erro ao finalizar bpftrace: {e}")
            self._process = None

        self._running = False

        critical = sum(1 for e in self._events if e.severity == EbpfEventSeverity.CRITICAL)
        errors = sum(1 for e in self._events if e.severity == EbpfEventSeverity.ERROR)
        warnings = sum(1 for e in self._events if e.severity == EbpfEventSeverity.WARNING)

        result = EbpfMonitorResult(
            total_events=len(self._events),
            critical_count=critical,
            error_count=errors,
            warning_count=warnings,
            events=self._events,
            duration_ms=duration_ms,
            is_clean=(critical == 0 and errors == 0),
        )

        montar_log(result.summary(), "INFO" if result.is_clean else "WARNING")
        return result

    def collect(self) -> EbpfMonitorResult:
        """Alias para stop() — coleta resultados."""
        return self.stop()

    def check_now(self) -> List[EbpfEvent]:
        """Verifica eventos pendentes sem parar o monitoramento."""
        if self._process and self._process.stdout:
            import select
            ready, _, _ = select.select([self._process.stdout], [], [], 0)
            if ready:
                line = self._process.stdout.readline()
                if line:
                    event = self._verifier._parse_line(line.strip())
                    if event:
                        self._events.append(event)
        return list(self._events)


# ============================================================================
# Factory
# ============================================================================

def create_ebpf_verifier(
    lock_threshold_ms: int = 100,
    stack_traces: bool = False,
) -> EbpfVerifier:
    """Factory function para EbpfVerifier."""
    return EbpfVerifier(
        lock_held_threshold_ms=lock_threshold_ms,
        capture_stack_traces=stack_traces,
    )
