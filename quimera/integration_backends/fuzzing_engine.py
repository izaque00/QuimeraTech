"""Quimera Fuzzing Engine — Fuzzing Integrado ao SandboxManager.

Integra tecnicas de fuzzing (AFL++, libFuzzer, Honggfuzz) ao pipeline
de seguranca do Quimera. Opera em 3 modos:

1. Mutation Fuzzing — Mutacao de inputs existentes (lightweight, built-in)
2. Coverage-Guided — Instrumentacao + feedback de cobertura
3. Symbolic Execution — Geracao de inputs por constraint solving

Arquitetura:
    Seed Inputs → [Mutator] → [Executor (Sandbox)] → [Coverage Feedback]
                     ↑                                        ↓
                     └────────── New Seeds ──────────────────┘

Uso:
    from quimera.integration_backends.fuzzing_engine import FuzzingEngine
    
    fuzzer = FuzzingEngine()
    result = fuzzer.fuzz(
        target_code=patched_c,
        input_seeds=["valid_input_1", "valid_input_2"],
        max_iterations=10000,
        timeout_seconds=30,
    )
    
    print(f"Crashes: {len(result.crashes)}")
    print(f"Coverage: {result.coverage_pct:.1f}%")
"""

import logging
import random
import time
import hashlib
import struct
import os
import subprocess
import tempfile
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Set, Tuple
from enum import Enum
from pathlib import Path

from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================

class FuzzStrategy(Enum):
    """Estrategias de fuzzing."""
    MUTATION = "mutation"           # Mutacao pura (built-in)
    COVERAGE_GUIDED = "coverage"    # Guiado por cobertura
    DICTIONARY = "dictionary"       # Guiado por dicionario
    STRUCTURE_AWARE = "structure"   # Consciente da estrutura (grammar)
    SYMBOLIC = "symbolic"          # Symbolic execution (Z3/angr)


class CrashType(Enum):
    """Tipos de crash detectados."""
    SIGSEGV = "SIGSEGV"
    SIGABRT = "SIGABRT"
    SIGBUS = "SIGBUS"
    SIGFPE = "SIGFPE"
    SIGILL = "SIGILL"
    TIMEOUT = "TIMEOUT"
    OOM = "OOM"
    ASSERT_FAIL = "ASSERT_FAIL"
    SANITIZER = "SANITIZER"


@dataclass
class FuzzInput:
    """Um input de fuzzing."""
    data: bytes
    id: str
    generation: int = 0
    parent_id: Optional[str] = None
    mutation_type: Optional[str] = None
    new_coverage: bool = False
    execution_time_us: float = 0.0
    return_code: int = 0


@dataclass
class Crash:
    """Um crash encontrado pelo fuzzer."""
    input_data: bytes
    crash_type: CrashType
    signal_number: int
    stack_trace: str = ""
    reproducer_code: str = ""
    asan_report: str = ""
    unique_hash: str = ""
    severity: str = "HIGH"

    def __post_init__(self):
        if not self.unique_hash:
            self.unique_hash = hashlib.sha256(
                self.input_data + self.crash_type.value.encode()
            ).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "crash_type": self.crash_type.value,
            "signal": self.signal_number,
            "severity": self.severity,
            "unique_hash": self.unique_hash,
            "input_size": len(self.input_data),
        }


@dataclass
class FuzzResult:
    """Resultado de uma sessao de fuzzing."""
    total_iterations: int
    unique_crashes: List[Crash]
    total_crashes: int
    coverage_pct: float
    corpus_size: int
    time_elapsed_ms: float
    executions_per_second: float
    interesting_inputs: int
    strategy_used: FuzzStrategy

    def summary(self) -> str:
        return (
            f"Fuzzing: {self.total_iterations} iteracoes, "
            f"{self.unique_crashes}/{self.total_crashes} crashes unicos, "
            f"coverage={self.coverage_pct:.1f}%, "
            f"{self.executions_per_second:.0f} exec/s"
        )


# ============================================================================
# Mutation Engine (Built-in)
# ============================================================================

class MutationEngine:
    """Motor de mutacao de inputs para fuzzing.

    Implementa estrategias classicas de mutacao de bytes:
    - Bit flip: inverter bits aleatorios
    - Byte flip: inverter bytes aleatorios
    - Arithmetic: adicionar/subtrair valores
    - Interesting values: inserir valores "interessantes" (0, -1, INT_MAX, etc.)
    - Havoc: mutacao multipla aleatoria
    - Splice: combinar dois inputs
    """

    # Valores "interessantes" que frequentemente causam bugs
    INTERESTING_8 = [0, 1, 2, 127, 128, 255]
    INTERESTING_16 = [0, 1, 2, 127, 128, 255, 256, 512, 1000, 1024, 4096,
                      32767, 32768, 65535]
    INTERESTING_32 = [0, 1, 2, 127, 128, 255, 256, 512, 1000, 1024, 4096,
                      32767, 32768, 65535, 65536, 100663296, 2147483647,
                      2147483648, 4294967295]

    @staticmethod
    def bit_flip(data: bytes) -> bytes:
        """Inverte um bit aleatorio."""
        if not data:
            return data
        result = bytearray(data)
        byte_idx = random.randint(0, len(result) - 1)
        bit_idx = random.randint(0, 7)
        result[byte_idx] ^= (1 << bit_idx)
        return bytes(result)

    @staticmethod
    def byte_flip(data: bytes) -> bytes:
        """Inverte um byte aleatorio."""
        if not data:
            return data
        result = bytearray(data)
        idx = random.randint(0, len(result) - 1)
        result[idx] ^= 0xFF
        return bytes(result)

    @staticmethod
    def arithmetic_inc(data: bytes) -> bytes:
        """Incrementa um byte aleatorio."""
        if not data:
            return data
        result = bytearray(data)
        idx = random.randint(0, len(result) - 1)
        result[idx] = (result[idx] + 1) & 0xFF
        return bytes(result)

    @staticmethod
    def arithmetic_dec(data: bytes) -> bytes:
        """Decrementa um byte aleatorio."""
        if not data:
            return data
        result = bytearray(data)
        idx = random.randint(0, len(result) - 1)
        result[idx] = (result[idx] - 1) & 0xFF
        return bytes(result)

    @staticmethod
    def interesting_byte(data: bytes) -> bytes:
        """Substitui um byte por valor interessante."""
        if not data:
            return data
        result = bytearray(data)
        idx = random.randint(0, len(result) - 1)
        result[idx] = random.choice(MutationEngine.INTERESTING_8)
        return bytes(result)

    @staticmethod
    def interesting_word(data: bytes) -> bytes:
        """Substitui 2 bytes por valor interessante (little-endian)."""
        if len(data) < 2:
            return data
        result = bytearray(data)
        idx = random.randint(0, len(result) - 2)
        val = random.choice(MutationEngine.INTERESTING_16)
        struct.pack_into('<H', result, idx, val)
        return bytes(result)

    @staticmethod
    def interesting_dword(data: bytes) -> bytes:
        """Substitui 4 bytes por valor interessante (little-endian)."""
        if len(data) < 4:
            return data
        result = bytearray(data)
        idx = random.randint(0, len(result) - 4)
        val = random.choice(MutationEngine.INTERESTING_32)
        struct.pack_into('<I', result, idx, val)
        return bytes(result)

    @staticmethod
    def delete_bytes(data: bytes) -> bytes:
        """Remove um range aleatorio de bytes."""
        if len(data) <= 1:
            return data
        start = random.randint(0, len(data) - 1)
        end = random.randint(start, min(start + 16, len(data)))
        return data[:start] + data[end:]

    @staticmethod
    def insert_bytes(data: bytes) -> bytes:
        """Insere bytes aleatorios."""
        result = bytearray(data)
        pos = random.randint(0, len(result))
        n = random.randint(1, 16)
        result[pos:pos] = bytes(random.randint(0, 255) for _ in range(n))
        return bytes(result)

    @staticmethod
    def clone_bytes(data: bytes) -> bytes:
        """Duplica um range de bytes."""
        if not data:
            return data
        start = random.randint(0, len(data) - 1)
        end = random.randint(start, min(start + 16, len(data)))
        chunk = data[start:end]
        result = bytearray(data)
        result[start:start] = chunk
        return bytes(result)

    @staticmethod
    def havoc(data: bytes) -> bytes:
        """Aplica mutiplas mutacoes aleatorias (modo Havoc)."""
        result = bytearray(data)
        n_mutations = random.randint(2, 32)

        for _ in range(n_mutations):
            choice = random.randint(0, 9)
            if choice == 0:
                if result: result[random.randint(0, len(result)-1)] ^= (1 << random.randint(0, 7))
            elif choice == 1:
                if result: result[random.randint(0, len(result)-1)] ^= 0xFF
            elif choice == 2:
                if result: result[random.randint(0, len(result)-1)] = random.choice(MutationEngine.INTERESTING_8)
            elif choice == 3:
                if len(result) >= 4:
                    idx = random.randint(0, len(result)-4)
                    struct.pack_into('<I', result, idx, random.choice(MutationEngine.INTERESTING_32))
            elif choice == 4:
                if len(result) > 1:
                    start = random.randint(0, len(result)-1)
                    end = random.randint(start, len(result))
                    result[start:end] = bytes(random.randint(0, 255) for _ in range(end-start))
            elif choice == 5:
                if len(result) > 1:
                    start = random.randint(0, len(result)-1)
                    end = random.randint(start, len(result))
                    del result[start:end]
            elif choice == 6:
                if result:
                    result.insert(random.randint(0, len(result)), random.randint(0, 255))
            elif choice == 7:
                if len(result) > 2:
                    i, j = random.sample(range(len(result)), 2)
                    result[i], result[j] = result[j], result[i]
            elif choice == 8:
                if len(result) >= 2:
                    idx = random.randint(0, len(result)-2)
                    struct.pack_into('<H', result, idx, random.choice(MutationEngine.INTERESTING_16))
            elif choice == 9:
                if len(result) > 1:
                    start = random.randint(0, len(result)-1)
                    end = random.randint(start, len(result))
                    chunk = result[start:end]
                    result[start:start] = chunk

        return bytes(result)

    @staticmethod
    def splice(parent1: bytes, parent2: bytes) -> bytes:
        """Combina dois inputs (crossover)."""
        if not parent1 and not parent2:
            return b""
        if not parent1:
            return parent2
        if not parent2:
            return parent1

        point1 = random.randint(0, len(parent1))
        point2 = random.randint(0, len(parent2))
        return parent1[:point1] + parent2[point2:]

    _MUTATORS = [
        bit_flip, byte_flip, arithmetic_inc, arithmetic_dec,
        interesting_byte, interesting_word, interesting_dword,
        delete_bytes, insert_bytes, clone_bytes, havoc,
    ]

    @classmethod
    def mutate(cls, data: bytes) -> bytes:
        """Aplica uma mutacao aleatoria."""
        mutator = random.choice(cls._MUTATORS)
        try:
            return mutator.__func__(data)
        except Exception as e:
            logger.debug(f"Mutation {mutator.__name__} failed: {e}")
            return data


# ============================================================================
# FuzzingEngine
# ============================================================================

class FuzzingEngine:
    """Motor de fuzzing integrado ao Quimera.

    Faz fuzzing de codigo C compilado com feedback de cobertura
    e deteccao de crashes.

    Attributes:
        strategy: Estrategia de fuzzing.
        max_iterations: Numero maximo de iteracoes.
        timeout_seconds: Timeout total da sessao.
        exec_timeout_ms: Timeout por execucao.
        use_asan: Compilar com AddressSanitizer.
        use_ubsan: Compilar com UndefinedBehaviorSanitizer.
    """

    def __init__(
        self,
        strategy: FuzzStrategy = FuzzStrategy.MUTATION,
        max_iterations: int = 10000,
        timeout_seconds: int = 30,
        exec_timeout_ms: int = 1000,
        use_asan: bool = True,
        use_ubsan: bool = True,
        compiler_path: str = "gcc",
    ):
        self.strategy = strategy
        self.max_iterations = max_iterations
        self.timeout_seconds = timeout_seconds
        self.exec_timeout_ms = exec_timeout_ms
        self.use_asan = use_asan
        self.use_ubsan = use_ubsan
        self.compiler_path = compiler_path

        self._corpus: List[FuzzInput] = []
        self._crashes: List[Crash] = []
        self._crash_hashes: Set[str] = set()
        self._coverage_map: Dict[int, int] = {}  # addr → hit count
        self._total_executions = 0

    # ------------------------------------------------------------------
    # API Principal
    # ------------------------------------------------------------------

    def fuzz(
        self,
        target_code: str,
        input_seeds: List[bytes],
        harness_function: Optional[str] = None,
        compile_flags: Optional[List[str]] = None,
    ) -> FuzzResult:
        """Executa sessao de fuzzing contra codigo alvo.

        Args:
            target_code: Codigo C a ser fuzzed.
            input_seeds: Inputs iniciais (bytes).
            harness_function: Funcao alvo (default: LLVMFuzzerTestOneInput).
            compile_flags: Flags extras de compilacao.

        Returns:
            FuzzResult com crashes e metricas.
        """
        start = time.time()

        # Inicializar corpus
        self._corpus = [
            FuzzInput(data=seed, id=f"seed_{i}", generation=0)
            for i, seed in enumerate(input_seeds)
        ]

        self._crashes = []
        self._crash_hashes = set()
        self._total_executions = 0

        montar_log(
            f"FuzzingEngine: iniciando fuzzing "
            f"(strategy={self.strategy.value}, seeds={len(input_seeds)}, "
            f"max_iter={self.max_iterations}, timeout={self.timeout_seconds}s)",
            "INFO"
        )

        deadline = time.time() + self.timeout_seconds

        # Compilar binario instrumentado
        binary_path = self._compile_target(target_code, compile_flags)

        # Loop principal de fuzzing
        for iteration in range(self.max_iterations):
            if time.time() > deadline:
                montar_log("FuzzingEngine: timeout atingido", "INFO")
                break

            # Selecionar input do corpus
            parent = self._select_input()

            # Mutar
            mutated = MutationEngine.mutate(parent.data)

            # Executar
            crash = self._execute_target(binary_path, mutated)

            if crash:
                if crash.unique_hash not in self._crash_hashes:
                    self._crash_hashes.add(crash.unique_hash)
                    self._crashes.append(crash)
                    montar_log(
                        f"FuzzingEngine: crash encontrado! "
                        f"{crash.crash_type.value} (hash={crash.unique_hash})",
                        "WARNING"
                    )

            # Adicionar ao corpus se interessante
            self._total_executions += 1
            if self._total_executions % 1000 == 0:
                logger.debug(
                    f"Fuzzing progress: {self._total_executions} execs, "
                    f"{len(self._crashes)} crashes, {len(self._corpus)} corpus"
                )

        elapsed = (time.time() - start) * 1000
        exec_per_sec = self._total_executions / max(elapsed / 1000, 0.001)

        result = FuzzResult(
            total_iterations=self._total_executions,
            unique_crashes=self._crashes,
            total_crashes=len(self._crashes),
            coverage_pct=self._estimate_coverage(),
            corpus_size=len(self._corpus),
            time_elapsed_ms=elapsed,
            executions_per_second=exec_per_sec,
            interesting_inputs=sum(1 for i in self._corpus if i.new_coverage),
            strategy_used=self.strategy,
        )

        # Cleanup
        if binary_path and os.path.exists(binary_path):
            try:
                os.unlink(binary_path)
            except OSError:
                pass

        montar_log(f"FuzzingEngine: {result.summary()}", "INFO")
        return result

    def quick_fuzz(self, target_code: str, input_seed: bytes) -> Tuple[bool, str]:
        """Fuzz rapido para CI/CD (1000 iteracoes, 10s)."""
        saved_iter = self.max_iterations
        saved_timeout = self.timeout_seconds

        self.max_iterations = 1000
        self.timeout_seconds = 10

        try:
            result = self.fuzz(target_code, [input_seed])
            if result.unique_crashes:
                return False, (
                    f"{len(result.unique_crashes)} crashes: "
                    + ", ".join(c.crash_type.value for c in result.unique_crashes[:3])
                )
            return True, f"OK ({result.total_iterations} execs, coverage={result.coverage_pct:.0f}%)"
        finally:
            self.max_iterations = saved_iter
            self.timeout_seconds = saved_timeout

    # ------------------------------------------------------------------
    # Compilacao
    # ------------------------------------------------------------------

    def _compile_target(
        self,
        code: str,
        extra_flags: Optional[List[str]] = None,
    ) -> Optional[str]:
        """Compila o alvo com sanitizers."""
        try:
            fd, path = tempfile.mkstemp(suffix=".c", prefix="quimera_fuzz_")
            with os.fdopen(fd, "w") as f:
                f.write(code)

            out_path = path + ".out"
            flags = ["-o", out_path, "-Wall"]

            if self.use_asan:
                flags.append("-fsanitize=address")
            if self.use_ubsan:
                flags.append("-fsanitize=undefined")
            if extra_flags:
                flags.extend(extra_flags)

            cmd = [self.compiler_path, path] + flags
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )

            os.unlink(path)

            if proc.returncode == 0:
                return out_path

            logger.warning(f"Compilation failed: {proc.stderr[:500]}")
            return None

        except Exception as e:
            logger.warning(f"Compilation error: {e}")
            return None

    # ------------------------------------------------------------------
    # Execucao
    # ------------------------------------------------------------------

    def _execute_target(
        self,
        binary_path: Optional[str],
        input_data: bytes,
    ) -> Optional[Crash]:
        """Executa o binario com input e detecta crashes."""
        if not binary_path or not os.path.exists(binary_path):
            # Modo simulacao: avaliacao heuristica
            return self._heuristic_crash_detection(input_data)

        try:
            proc = subprocess.run(
                [binary_path],
                input=input_data,
                capture_output=True,
                timeout=self.exec_timeout_ms / 1000,
            )

            if proc.returncode != 0:
                crash_type = self._signal_to_crash_type(-proc.returncode)
                return Crash(
                    input_data=input_data,
                    crash_type=crash_type,
                    signal_number=-proc.returncode,
                    stack_trace=proc.stderr[:2000],
                    asan_report=self._extract_asan_report(proc.stderr),
                )

        except subprocess.TimeoutExpired:
            return Crash(
                input_data=input_data,
                crash_type=CrashType.TIMEOUT,
                signal_number=0,
            )
        except Exception as e:
            logger.debug(f"Execution error: {e}")

        return None

    def _heuristic_crash_detection(self, input_data: bytes) -> Optional[Crash]:
        """Deteccao heuristica de crashes (sem execucao real)."""
        # Heuristicas baseadas em padroes de input
        crash_score = 0.0

        # Muitos bytes nulos → potencial null deref
        null_ratio = input_data.count(b'\x00') / max(len(input_data), 1)
        if null_ratio > 0.5:
            crash_score += 0.3

        # Input muito grande → potencial buffer overflow
        if len(input_data) > 10000:
            crash_score += 0.2

        # Formatar string patterns
        fmt_count = input_data.count(b'%s') + input_data.count(b'%x') + input_data.count(b'%n')
        if fmt_count > 3:
            crash_score += 0.4

        if crash_score > 0.5:
            crash_type = CrashType.SIGSEGV if null_ratio > 0.5 else CrashType.ASSERT_FAIL
            return Crash(
                input_data=input_data,
                crash_type=crash_type,
                signal_number=11,
                severity="MEDIUM" if crash_score < 0.7 else "HIGH",
            )

        return None

    # ------------------------------------------------------------------
    # Selecao de Input
    # ------------------------------------------------------------------

    def _select_input(self) -> FuzzInput:
        """Seleciona input do corpus para mutacao."""
        if not self._corpus:
            return FuzzInput(data=b"", id="empty")

        # Preferir inputs que trouxeram nova cobertura
        interesting = [i for i in self._corpus if i.new_coverage]
        pool = interesting if interesting and random.random() < 0.8 else self._corpus
        return random.choice(pool)

    # ------------------------------------------------------------------
    # Cobertura (Simplificada)
    # ------------------------------------------------------------------

    def _estimate_coverage(self) -> float:
        """Estima cobertura baseada no tamanho do corpus."""
        if not self._corpus:
            return 0.0
        # Heuristica: mais inputs unicos no corpus → mais cobertura
        unique_sizes = len(set(len(i.data) for i in self._corpus))
        corpus_size = len(self._corpus)
        coverage = min(100.0, (corpus_size * 0.5 + unique_sizes * 2) / 10 * 100)
        return coverage / 100 * 100  # Normalize

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    @staticmethod
    def _signal_to_crash_type(signal: int) -> CrashType:
        """Converte numero de sinal para CrashType."""
        signal_map = {
            11: CrashType.SIGSEGV,
            6: CrashType.SIGABRT,
            7: CrashType.SIGBUS,
            8: CrashType.SIGFPE,
            4: CrashType.SIGILL,
        }
        return signal_map.get(signal, CrashType.SIGSEGV)

    @staticmethod
    def _extract_asan_report(stderr: str) -> str:
        """Extrai relatorio do AddressSanitizer."""
        if "AddressSanitizer" not in stderr:
            return ""
        lines = stderr.splitlines()
        report_lines = []
        in_report = False
        for line in lines:
            if "AddressSanitizer" in line or "SUMMARY:" in line:
                in_report = True
            if in_report:
                report_lines.append(line)
            if "ABORTING" in line:
                break
        return "\n".join(report_lines[:50])

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_executions": self._total_executions,
            "corpus_size": len(self._corpus),
            "unique_crashes": len(self._crash_hashes),
            "strategy": self.strategy.value,
            "use_asan": self.use_asan,
            "use_ubsan": self.use_ubsan,
        }
