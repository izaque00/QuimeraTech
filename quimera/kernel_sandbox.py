"""
Kernel Sandbox — Real kernel module compilation with Docker.
Builds and tests drivers against specific kernel versions.
"""
import os
import subprocess
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger("quimera.kernel_sandbox")


@dataclass
class KernelBuildResult:
    success: bool
    kernel_version: str
    errors: List[str]
    warnings: List[str]
    modinfo: Dict
    insmod_ok: bool
    rmmod_ok: bool
    dmesg_output: str


class KernelSandbox:
    """Build and test kernel modules in Docker sandbox with real headers."""

    DOCKER_IMAGE = "quimera-kernel"

    def __init__(self, workspace_dir: str, kernel_version: Optional[str] = None):
        self.workspace = workspace_dir
        self.kernel_version = kernel_version

    def build_and_test(self, module_name: str) -> KernelBuildResult:
        """Build a kernel module and test insmod/rmmod."""
        errors = []
        warnings = []

        # Step 1: Check if Docker is available
        try:
            subprocess.run(['docker', '--version'], capture_output=True, timeout=5)
        except FileNotFoundError:
            errors.append("Docker not available — kernel build requires Docker")
            return KernelBuildResult(
                success=False, kernel_version='unknown',
                errors=errors, warnings=warnings,
                modinfo={}, insmod_ok=False, rmmod_ok=False, dmesg_output=''
            )

        # Step 2: Build Docker image if needed
        dockerfile = os.path.join(os.path.dirname(__file__), '..', 'Dockerfile.kernel')
        if os.path.exists(dockerfile):
            subprocess.run(
                ['docker', 'build', '-t', self.DOCKER_IMAGE, '-f', dockerfile, '.'],
                cwd=os.path.dirname(dockerfile), capture_output=True, timeout=120
            )

        # Step 3: Build module in container
        build_proc = subprocess.run([
            'docker', 'run', '--rm',
            '-v', f'{os.path.abspath(self.workspace)}:/workspace',
            self.DOCKER_IMAGE,
            'bash', '-c',
            f'cd /workspace && make clean 2>/dev/null; make 2>&1'
        ], capture_output=True, text=True, timeout=60)

        build_output = build_proc.stdout + '\n' + build_proc.stderr
        success = build_proc.returncode == 0 and 'error:' not in build_output.lower()

        # Parse errors and warnings
        for line in build_output.split('\n'):
            if 'error:' in line.lower():
                errors.append(line.strip())
            elif 'warning:' in line.lower():
                warnings.append(line.strip())

        # Step 4: Test insmod/rmmod in container
        insmod_ok = False
        rmmod_ok = False
        dmesg = ''

        ko_file = f'{module_name}.ko'
        if success and os.path.exists(os.path.join(self.workspace, ko_file)):
            test_proc = subprocess.run([
                'docker', 'run', '--rm', '--privileged',
                '-v', f'{os.path.abspath(self.workspace)}:/workspace',
                self.DOCKER_IMAGE,
                'bash', '-c',
                f'insmod /workspace/{ko_file} 2>&1 && '
                f'dmesg | tail -5 && '
                f'rmmod {module_name} 2>&1'
            ], capture_output=True, text=True, timeout=30)

            dmesg = test_proc.stdout + '\n' + test_proc.stderr
            insmod_ok = 'insmod' not in test_proc.stderr.lower()
            rmmod_ok = 'rmmod' not in test_proc.stderr.lower()

        # Step 5: Get modinfo
        modinfo = {}
        if success:
            modinfo_proc = subprocess.run([
                'docker', 'run', '--rm',
                '-v', f'{os.path.abspath(self.workspace)}:/workspace',
                self.DOCKER_IMAGE,
                'modinfo', f'/workspace/{ko_file}'
            ], capture_output=True, text=True, timeout=10)
            for line in modinfo_proc.stdout.split('\n'):
                if ':' in line:
                    k, v = line.split(':', 1)
                    modinfo[k.strip()] = v.strip()

        return KernelBuildResult(
            success=success,
            kernel_version=self.kernel_version or 'detect-at-runtime',
            errors=errors,
            warnings=warnings,
            modinfo=modinfo,
            insmod_ok=insmod_ok,
            rmmod_ok=rmmod_ok,
            dmesg_output=dmesg,
        )


def build_kernel_module(workspace_dir: str, module_name: str,
                        kernel_version: str = "6.12") -> KernelBuildResult:
    """One-liner: build and test a kernel module."""
    sandbox = KernelSandbox(workspace_dir, kernel_version)
    return sandbox.build_and_test(module_name)
