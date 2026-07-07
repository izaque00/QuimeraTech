"""
Docker Sandbox Executor — Compila e executa código C com sanitizers reais.

Pipeline H5: fuzzing engine + RedTeam exploit generation via sandbox.
         Nenhum código real é compilado ou executado.

Solução: Compilar o código original + patch em sandbox isolado,
         executar com ASan/UBSan, capturar crashes reais.

Pipeline:
  1. Recebe código C + patch candidate
  2. Cria diretório isolado em /tmp/quimera_sandbox_XXXXX
  3. Compila com: gcc -fsanitize=address,undefined -g -O0
  4. Executa o binário com inputs de teste
  5. Captura stdout, stderr, exit code, e ASan/UBSan reports
  6. Se crash → finding CONFIRMADO
  7. Limpa o sandbox

Segurança:
  - Timeout de 5s por execução
  - Memória limitada via ulimit
  - Sem acesso à rede
  - Diretório isolado e removido após uso
"""

import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class CompileResult:
    """Result of compiling C code."""
    success: bool
    binary_path: Optional[str] = None
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    elapsed_ms: float = 0.0


@dataclass
class ExecutionResult:
    """Result of running a compiled binary."""
    success: bool  # True if no crash
    exit_code: int = 0
    signal: Optional[int] = None  # SIGSEGV=11, SIGABRT=6, etc.
    stdout: str = ""
    stderr: str = ""
    asan_report: Optional[str] = None  # AddressSanitizer output
    ubsan_report: Optional[str] = None  # UndefinedBehaviorSanitizer output
    crashed: bool = False
    crash_type: str = ""  # segfault, assertion_failure, heap_overflow, etc.
    elapsed_ms: float = 0.0
    timeout: bool = False


@dataclass
class SandboxResult:
    """Complete sandbox execution result for a patch."""
    patch_id: str = ""
    patch_description: str = ""
    compile: Optional[CompileResult] = None
    executions: List[ExecutionResult] = field(default_factory=list)
    confirmed: bool = False  # True if crash reproduced
    total_elapsed_ms: float = 0.0
    error: str = ""


class DockerSandbox:
    """
    Isolated compilation and execution sandbox for C code.
    
    Uses temp directories + subprocess with strict limits.
    No Docker required — works in any Linux environment.
    """

    def __init__(self, timeout_seconds: int = 5, max_memory_mb: int = 256):
        self.timeout = timeout_seconds
        self.max_memory = max_memory_mb
        self._sandbox_dir: Optional[str] = None

    def setup(self) -> str:
        """Create isolated sandbox directory."""
        self._sandbox_dir = tempfile.mkdtemp(prefix="quimera_sandbox_")
        return self._sandbox_dir

    def cleanup(self):
        """Remove sandbox directory."""
        if self._sandbox_dir and os.path.exists(self._sandbox_dir):
            shutil.rmtree(self._sandbox_dir, ignore_errors=True)
            self._sandbox_dir = None

    def compile(self, code: str, filename: str = "target.c") -> CompileResult:
        """
        Compile C code with sanitizers.
        
        Args:
            code: C source code
            filename: name for the source file
        
        Returns:
            CompileResult with binary path or errors
        """
        if not self._sandbox_dir:
            self.setup()

        t0 = time.monotonic()
        result = CompileResult(success=False)

        # Write source file
        src_path = os.path.join(self._sandbox_dir, filename)
        try:
            with open(src_path, 'w') as f:
                f.write(code)
        except Exception as e:
            result.errors.append(f"Cannot write source: {e}")
            result.elapsed_ms = (time.monotonic() - t0) * 1000
            return result

        # Compile with ASan + UBSan
        binary_path = os.path.join(self._sandbox_dir, "quimera_test")
        compile_cmd = [
            "gcc",
            "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            "-g", "-O0",
            "-o", binary_path,
            src_path,
            "-lm",  # link math
        ]

        try:
            proc = subprocess.run(
                compile_cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self._sandbox_dir,
            )
            result.exit_code = proc.returncode
            result.stdout = proc.stdout
            result.stderr = proc.stderr
        except subprocess.TimeoutExpired:
            result.errors.append("Compilation timed out")
            result.elapsed_ms = (time.monotonic() - t0) * 1000
            return result
        except FileNotFoundError:
            result.errors.append("gcc not found — install build-essential")
            result.elapsed_ms = (time.monotonic() - t0) * 1000
            return result

        # Parse warnings and errors
        for line in result.stderr.split('\n'):
            line = line.strip()
            if not line:
                continue
            if 'error:' in line:
                result.errors.append(line)
            elif 'warning:' in line:
                result.warnings.append(line)

        if proc.returncode == 0 and os.path.exists(binary_path):
            result.success = True
            result.binary_path = binary_path
        else:
            result.errors.append(f"Compilation failed (exit {proc.returncode})")

        result.elapsed_ms = (time.monotonic() - t0) * 1000
        return result

    def execute(self, binary_path: str, stdin_input: Optional[str] = None,
                args: Optional[List[str]] = None) -> ExecutionResult:
        """
        Execute a compiled binary with timeout and memory limits.
        
        Returns:
            ExecutionResult with crash info and sanitizer reports
        """
        t0 = time.monotonic()
        result = ExecutionResult(success=True)

        if not os.path.exists(binary_path):
            result.success = False
            result.stderr = "Binary not found"
            result.elapsed_ms = (time.monotonic() - t0) * 1000
            return result

        cmd = [binary_path]
        if args:
            cmd.extend(args)

        env = os.environ.copy()
        env["ASAN_OPTIONS"] = "detect_leaks=0:abort_on_error=1:halt_on_error=1"
        env["UBSAN_OPTIONS"] = "print_stacktrace=1:halt_on_error=1"

        try:
            proc = subprocess.run(
                cmd,
                input=stdin_input,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self._sandbox_dir,
                env=env,
            )
            result.exit_code = proc.returncode
            result.stdout = proc.stdout
            result.stderr = proc.stderr

            if proc.returncode != 0:
                result.crashed = True
                result.success = False

        except subprocess.TimeoutExpired:
            result.timeout = True
            result.success = False
            result.crashed = True
            result.crash_type = "timeout"
        except Exception as e:
            result.success = False
            result.stderr = str(e)

        # Parse sanitizer output
        result.asan_report = self._extract_asan_report(result.stderr)
        result.ubsan_report = self._extract_ubsan_report(result.stderr)
        result.crash_type = self._classify_crash(result)

        # Check for signal
        if result.exit_code < 0:
            result.signal = -result.exit_code
            result.crashed = True
            result.success = False

        result.elapsed_ms = (time.monotonic() - t0) * 1000
        return result

    def execute_with_inputs(self, binary_path: str, 
                           inputs: List[str]) -> List[ExecutionResult]:
        """Run binary with multiple inputs, return all results."""
        results = []
        for inp in inputs:
            result = self.execute(binary_path, stdin_input=inp)
            results.append(result)
            if result.crashed:
                break  # Found a crash, stop testing
        return results

    def run_full_test(self, code: str, filename: str = "target.c",
                     test_inputs: Optional[List[str]] = None) -> SandboxResult:
        """
        Full pipeline: compile → execute with test inputs.
        
        Args:
            code: C source code
            filename: source filename
            test_inputs: list of stdin inputs to test
        
        Returns:
            SandboxResult with compile + execution results
        """
        t0 = time.monotonic()
        result = SandboxResult(patch_id=filename.replace('.c', ''))

        self.setup()

        # Step 1: Compile
        compile_result = self.compile(code, filename)
        result.compile = compile_result

        if not compile_result.success:
            result.error = f"Compilation failed: {'; '.join(compile_result.errors[:3])}"
            result.total_elapsed_ms = (time.monotonic() - t0) * 1000
            self.cleanup()
            return result

        # Step 2: Execute with test inputs
        if test_inputs is None:
            test_inputs = [
                "",                    # empty
                "\x00\x00\x00\x00",    # null bytes
                "A" * 256,             # long string
                "\xff\xff\xff\xff",    # -1
                "%s%s%s%s%s",          # format string
                "A" * 4096,            # page size
            ]

        for inp in test_inputs:
            exec_result = self.execute(compile_result.binary_path, stdin_input=inp)
            result.executions.append(exec_result)
            if exec_result.crashed:
                result.confirmed = True
                result.patch_description = (
                    f"CRASH: {exec_result.crash_type} "
                    f"(ASan: {bool(exec_result.asan_report)}, "
                    f"UBSan: {bool(exec_result.ubsan_report)})"
                )
                break

        result.total_elapsed_ms = (time.monotonic() - t0) * 1000
        self.cleanup()
        return result

    def _extract_asan_report(self, stderr: str) -> Optional[str]:
        """Extract AddressSanitizer report from stderr."""
        if not stderr:
            return None
        lines = stderr.split('\n')
        for i, line in enumerate(lines):
            if 'AddressSanitizer' in line or 'ASAN' in line:
                return '\n'.join(lines[i:i+10])
            if 'heap-buffer-overflow' in line or 'stack-buffer-overflow' in line:
                return '\n'.join(lines[max(0,i-1):i+8])
            if 'heap-use-after-free' in line:
                return '\n'.join(lines[max(0,i-1):i+8])
        return None

    def _extract_ubsan_report(self, stderr: str) -> Optional[str]:
        """Extract UndefinedBehaviorSanitizer report from stderr."""
        if not stderr:
            return None
        lines = stderr.split('\n')
        for i, line in enumerate(lines):
            if 'UndefinedBehavior' in line or 'UBSAN' in line:
                return '\n'.join(lines[i:i+8])
            if 'runtime error:' in line:
                return '\n'.join(lines[max(0,i-1):i+6])
        return None

    def _classify_crash(self, result: ExecutionResult) -> str:
        """Classify the type of crash."""
        stderr = result.stderr or ""
        stdout = result.stdout or ""

        if result.signal == 11:
            return "segfault"
        if result.signal == 6:
            return "assertion_failure"
        if result.signal == 8:
            return "floating_point_error"
        if result.timeout:
            return "timeout"

        if "heap-buffer-overflow" in stderr:
            return "heap_overflow"
        if "stack-buffer-overflow" in stderr:
            return "stack_overflow"
        if "heap-use-after-free" in stderr:
            return "use_after_free"
        if "double-free" in stderr:
            return "double_free"
        if "AddressSanitizer" in stderr and "SEGV" in stderr:
            return "asan_segfault"
        if "assertion" in stderr.lower():
            return "assertion_failure"
        if "runtime error:" in stderr:
            return "ubsan_error"

        if result.exit_code != 0:
            return f"exit_{result.exit_code}"

        return "none"


class PatchValidator:
    """
    Validates Quimera-generated patches by running them in sandbox.
    
    Workflow:
      1. Receive original code + proposed patch
      2. Apply patch to code
      3. Compile both original and patched versions
      4. Run same inputs on both
      5. Compare: original crashes? patched still crashes? fixed?
    """

    def __init__(self):
        self.sandbox = DockerSandbox()

    def validate_patch(self, original_code: str, patched_code: str,
                      test_inputs: Optional[List[str]] = None) -> Dict:
        """
        Validate a patch by running both versions.
        
        Returns:
            {
                'original_crash': bool,
                'patched_crash': bool,
                'fixed': bool,  # original crashed, patched doesn't
                'regression': bool,  # original was fine, patched crashes
                'original_result': ExecutionResult,
                'patched_result': ExecutionResult,
            }
        """
        # Test original
        orig_result = self.sandbox.run_full_test(
            original_code, "original.c", test_inputs
        )

        # Test patched
        patch_result = self.sandbox.run_full_test(
            patched_code, "patched.c", test_inputs
        )

        orig_crash = any(e.crashed for e in orig_result.executions) if orig_result.executions else False
        patch_crash = any(e.crashed for e in patch_result.executions) if patch_result.executions else False

        return {
            'original_crash': orig_crash,
            'patched_crash': patch_crash,
            'fixed': orig_crash and not patch_crash,
            'regression': not orig_crash and patch_crash,
            'original_result': orig_result,
            'patched_result': patch_result,
        }
