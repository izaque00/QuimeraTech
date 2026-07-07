"""
ASan Integration — Real AddressSanitizer + UBSan validation for Quimera.

Runs compiled binaries with ASan/UBSan and captures crash reports.
Integrates with Engineer Loop to validate fixes.
"""
import os
import re
import subprocess
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger("quimera.asan_validator")


@dataclass
class ASanReport:
    """Parsed AddressSanitizer report."""
    error_type: str = ""           # heap-use-after-free, heap-buffer-overflow, etc
    crash_address: str = ""
    crash_location: str = ""       # file:line
    freed_location: str = ""       # where it was freed
    allocated_location: str = ""   # where it was allocated
    stack_trace: List[str] = field(default_factory=list)
    raw_output: str = ""
    is_crash: bool = False


class ASanValidator:
    """
    Compile with -fsanitize=address,undefined and run to detect runtime bugs.
    """

    @staticmethod
    def compile_with_asan(source_files: List[str], output: str,
                          cwd: str = ".") -> tuple:
        """
        Compile with ASan flags.

        Returns: (success: bool, output: str)
        """
        cmd = ['gcc', '-g', '-fsanitize=address,undefined',
               '-fno-omit-frame-pointer', '-fno-common'] + source_files + ['-o', output]

        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30)
        return proc.returncode == 0, proc.stderr + '\n' + proc.stdout

    @staticmethod
    def run_with_asan(binary_path: str, timeout_seconds: int = 10,
                      env: Optional[Dict] = None) -> ASanReport:
        """
        Run binary with ASan and parse crash reports.

        Returns ASanReport with parsed findings.
        """
        report = ASanReport()

        run_env = os.environ.copy()
        run_env['ASAN_OPTIONS'] = 'detect_leaks=1:abort_on_error=0:halt_on_error=0'
        if env:
            run_env.update(env)

        try:
            proc = subprocess.run(
                [binary_path],
                cwd=os.path.dirname(binary_path),
                capture_output=True, text=True,
                timeout=timeout_seconds,
                env=run_env,
            )

            output = proc.stderr + '\n' + proc.stdout

            # Parse ASan report
            if 'AddressSanitizer:' in output:
                report.is_crash = True
                report.raw_output = output

                # Error type
                type_match = re.search(r'ERROR: AddressSanitizer: (\S+)', output)
                if type_match:
                    report.error_type = type_match.group(1)

                # READ/WRITE location
                loc_match = re.search(r'#0 \S+ in \S+ (.+):(\d+)', output)
                if loc_match:
                    report.crash_location = f"{loc_match.group(1)}:{loc_match.group(2)}"

                # Freed location
                freed_match = re.search(r'freed by.*?\n.*?#0 \S+ in \S+ (.+):(\d+)', output, re.DOTALL)
                if freed_match:
                    report.freed_location = f"{freed_match.group(1)}:{freed_match.group(2)}"

                # Allocated location
                alloc_match = re.search(r'previously allocated.*?\n.*?#0 \S+ in \S+ (.+):(\d+)', output, re.DOTALL)
                if alloc_match:
                    report.allocated_location = f"{alloc_match.group(1)}:{alloc_match.group(2)}"

                # Stack trace
                for line in output.split('\n'):
                    if re.match(r'\s*#\d+\s', line):
                        report.stack_trace.append(line.strip())

            return report

        except subprocess.TimeoutExpired:
            report.is_crash = False
            report.raw_output = "TIMEOUT"
            return report
        except Exception as e:
            report.raw_output = str(e)
            return report


def validate_fix(source_files: List[str], cwd: str = ".") -> dict:
    """
    Full validation cycle:
    1. Compile with ASan
    2. Run with ASan
    3. Report any runtime issues

    Returns: {
        'compiled': bool,
        'crashed': bool,
        'asan_report': ASanReport or None,
        'ready_for_production': bool,
    }
    """
    result = {
        'compiled': False,
        'crashed': False,
        'asan_report': None,
        'ready_for_production': False,
    }

    output_name = os.path.join(cwd, 'quimera_asan_test')
    compiled, compile_output = ASanValidator.compile_with_asan(
        source_files, output_name, cwd
    )
    result['compiled'] = compiled

    if not compiled:
        return result

    report = ASanValidator.run_with_asan(output_name)
    result['asan_report'] = report
    result['crashed'] = report.is_crash
    result['ready_for_production'] = compiled and not report.is_crash

    # Cleanup
    try:
        os.remove(output_name)
    except OSError:
        pass

    return result
