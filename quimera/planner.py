"""
Planner — Mission decomposition for Quimera.

Receives high-level missions and breaks them into executable steps.
Each step has: command, expected_output, error_handler, next_step.

Example:
  "Compile my Linux kernel with KASAN enabled"
  -> Step 1: git clone / verify source
  -> Step 2: make defconfig
  -> Step 3: enable KASAN in .config
  -> Step 4: make -j$(nproc)
  -> Step 5: handle errors (detect -> search -> patch -> retry)
  -> Step 6: verify build output
"""
import os, uuid, subprocess
from dataclasses import dataclass, field
from typing import List, Dict, Callable, Optional
from enum import Enum


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class MissionStep:
    id: str
    description: str
    command: str = ""
    cwd: str = ""
    expected_output: str = ""
    on_error: str = "retry"  # retry | skip | ask | abort
    max_retries: int = 3
    timeout_seconds: int = 300
    status: StepStatus = StepStatus.PENDING
    output: str = ""
    error: str = ""


@dataclass
class Mission:
    id: str
    description: str
    steps: List[MissionStep] = field(default_factory=list)
    project_type: str = "unknown"
    project_root: str = ""


class Planner:
    """
    Decomposes high-level missions into executable steps.

    Built-in knowledge for common project types:
    - Linux Kernel: Kbuild, .config, make, ARCH, CROSS_COMPILE
    - Android: Soong, Blueprint, Ninja
    - CMake: cmake, ctest
    - Cargo: cargo build, cargo test
    - Meson: meson setup, meson compile
    """

    # ── Complex Mission Templates ──────────────────────
    MISSION_TEMPLATES = {
        'enable_kasan': {
            'description': 'Enable KASAN in kernel config',
            'steps': [
                {'action': 'configure', 'target': 'CONFIG_KASAN=y',
                 'description': 'Enable KASAN in .config'},
                {'action': 'configure', 'target': 'CONFIG_KASAN_INLINE=y',
                 'description': 'Enable KASAN inline mode'},
                {'action': 'rebuild', 'target': 'make -j$(nproc)',
                 'description': 'Rebuild kernel with KASAN'},
                {'action': 'verify', 'target': 'dmesg | grep KASAN',
                 'description': 'Verify KASAN is active'},
            ],
        },
        'enable_kcov': {
            'description': 'Enable KCOV for fuzzing',
            'steps': [
                {'action': 'configure', 'target': 'CONFIG_KCOV=y',
                 'description': 'Enable KCOV in .config'},
                {'action': 'rebuild', 'target': 'make -j$(nproc)',
                 'description': 'Rebuild with KCOV'},
            ],
        },
        'port_driver': {
            'description': 'Port driver to newer kernel API',
            'steps': [
                {'action': 'analyze', 'target': 'API changes',
                 'description': 'Analyze kernel API changes'},
                {'action': 'search', 'target': 'commits+LKML',
                 'description': 'Search for similar ports'},
                {'action': 'patch', 'target': 'driver files',
                 'description': 'Apply API migration patches'},
                {'action': 'build', 'target': 'make -j$(nproc)',
                 'description': 'Build with ported driver'},
                {'action': 'test', 'target': 'insmod',
                 'description': 'Test driver load'},
            ],
        },
        'update_library': {
            'description': 'Update embedded library',
            'steps': [
                {'action': 'fetch', 'target': 'new version',
                 'description': 'Fetch new library version'},
                {'action': 'diff', 'target': 'API changes',
                 'description': 'Diff API changes'},
                {'action': 'patch', 'target': 'callers',
                 'description': 'Patch callers for API changes'},
                {'action': 'build', 'target': 'make',
                 'description': 'Build with updated library'},
                {'action': 'test', 'target': 'test suite',
                 'description': 'Run test suite'},
            ],
        },
    }

    def decompose_mission(self, mission_desc: str):
        """Decompose complex mission into subtasks."""
        mission_lower = mission_desc.lower()
        for tid, tpl in self.MISSION_TEMPLATES.items():
            keywords = tid.split('_')
            if all(k in mission_lower for k in keywords):
                return tpl['steps']
        # Generic decomposition
        actions = []
        if any(w in mission_lower for w in ['compile','build','make']):
            actions.append('build')
        if any(w in mission_lower for w in ['test','run']):
            actions.append('test')
        if any(w in mission_lower for w in ['fix','patch','corrigir']):
            actions.append('fix')
        if any(w in mission_lower for w in ['kasan','kcov','sanitize']):
            actions.append('configure_sanitizer')
        if any(w in mission_lower for w in ['analyze','check','verificar']):
            actions.append('analyze')
        if any(w in mission_lower for w in ['update','atualizar','upgrade','port']):
            actions.append('update')
        if not actions:
            actions = ['analyze', 'build', 'test']
        return [{'action': a, 'target': mission_desc[:80],
                 'description': f'{a}: {mission_desc[:60]}'} for a in actions]

    PROJECT_TEMPLATES = {
        "kernel": {
            "detect": ["Kbuild", "Kconfig", "Makefile"],
            "configure": "make defconfig",
            "build": "make -j$(nproc)",
            "test": "make -j$(nproc) modules",
            "artifact": "arch/{arch}/boot/bzImage",
        },
        "cmake": {
            "detect": ["CMakeLists.txt"],
            "configure": "cmake -B build -DCMAKE_BUILD_TYPE=Release",
            "build": "cmake --build build -j$(nproc)",
            "test": "ctest --test-dir build --output-on-failure",
        },
        "cargo": {
            "detect": ["Cargo.toml"],
            "configure": None,
            "build": "cargo build --release",
            "test": "cargo test",
        },
        "meson": {
            "detect": ["meson.build"],
            "configure": "meson setup build",
            "build": "meson compile -C build",
            "test": "meson test -C build",
        },
        "make": {
            "detect": ["Makefile", "makefile", "GNUmakefile"],
            "configure": None,
            "build": "make -j$(nproc)",
            "test": "make test 2>/dev/null || make check 2>/dev/null || echo no-tests",
        },
        "autotools": {
            "detect": ["configure.ac", "configure"],
            "configure": "./configure",
            "build": "make -j$(nproc)",
            "test": "make check 2>/dev/null || echo no-tests",
        },
    }

    def __init__(self, project_root: str = ""):
        self.project_root = project_root
        self.project_type = "unknown"
        if project_root:
            self._detect_project_type()

    def _detect_project_type(self):
        """Auto-detect project type from files in project_root."""
        if not os.path.isdir(self.project_root): return
        files = set()
        for root, dirs, filenames in os.walk(self.project_root):
            files.update(filenames)
            if len(files) > 100: break

        # Check in priority order: specific -> generic
        priority = ["kernel", "android", "cargo", "meson", "cmake", "autotools", "make"]
        for ptype in priority:
            if ptype not in self.PROJECT_TEMPLATES:
                continue
            config = self.PROJECT_TEMPLATES[ptype]
            markers = config.get("detect", [])
            if ptype == "kernel":
                # Kernel needs MULTIPLE markers, not just any Makefile
                kernel_markers = {"Kbuild", "Kconfig", "arch/"}
                found_kernel = [m for m in markers if m in files]
                dirs_present = any(
                    os.path.isdir(os.path.join(self.project_root, d))
                    for d in ["arch", "kernel", "drivers"]
                )
                if len(found_kernel) >= 2 or (len(found_kernel) >= 1 and dirs_present):
                    self.project_type = ptype
                    return
            else:
                for marker in markers:
                    if marker in files or any(marker.lower() in f.lower() for f in files):
                        self.project_type = ptype
                        return

    def plan(self, mission_desc: str) -> Mission:
        """Decompose a mission into steps based on project type."""
        m = Mission(
            id=str(uuid.uuid4())[:8],
            description=mission_desc,
            project_type=self.project_type,
            project_root=self.project_root,
        )

        pt = self.PROJECT_TEMPLATES.get(
            self.project_type, self.PROJECT_TEMPLATES["make"]
        )
        n = 1

        # Step 1: Verify project exists
        m.steps.append(MissionStep(
            id=f"S{n}",
            description=f"Verify {self.project_type} project",
            command=f"test -d {self.project_root} && echo OK",
            expected_output="OK",
            on_error="abort",
        ))
        n += 1

        # Step 2: Configure (if needed)
        if pt.get("configure"):
            m.steps.append(MissionStep(
                id=f"S{n}",
                description=f"Configure {self.project_type} build",
                command=pt["configure"],
                cwd=self.project_root,
                expected_output="configuration ok",
                on_error="retry",
                max_retries=2,
            ))
            n += 1

        # Step 3: Build
        m.steps.append(MissionStep(
            id=f"S{n}",
            description=f"Build {self.project_type} project",
            command=pt["build"],
            cwd=self.project_root,
            expected_output="build ok",
            on_error="retry",
            max_retries=5,
            timeout_seconds=1800,
        ))
        n += 1

        # Step 4: Test
        m.steps.append(MissionStep(
            id=f"S{n}",
            description=f"Run tests",
            command=pt["test"],
            cwd=self.project_root,
            expected_output="tests pass",
            on_error="skip",
        ))
        n += 1

        # Step 5: Verify artifact (if known)
        artifact = pt.get("artifact", "")
        if artifact:
            m.steps.append(MissionStep(
                id=f"S{n}",
                description=f"Verify: {artifact}",
                command=f"ls -lh {artifact}",
                cwd=self.project_root,
                expected_output="artifact found",
                on_error="ask",
            ))

        return m

    def execute(self, mission: Mission, on_error_callback: Callable = None) -> bool:
        """
        Execute all mission steps. Never gives up on first error.

        When a step fails:
          1. Log the error
          2. Call on_error_callback (can trigger detect -> search -> patch)
          3. Retry up to max_retries
          4. If still failing: skip or abort based on on_error
        """
        for step in mission.steps:
            step.status = StepStatus.RUNNING

            for attempt in range(step.max_retries):
                try:
                    r = subprocess.run(
                        step.command, shell=True,
                        cwd=step.cwd or self.project_root,
                        capture_output=True, text=True,
                        timeout=step.timeout_seconds
                    )
                    step.output = r.stdout + r.stderr

                    if r.returncode == 0:
                        step.status = StepStatus.SUCCESS
                        break
                    else:
                        step.error = r.stderr[:200]
                        if on_error_callback:
                            on_error_callback(step, mission)
                except Exception as e:
                    step.error = str(e)[:200]
                    if on_error_callback:
                        on_error_callback(step, mission)
            else:
                # All retries exhausted
                if step.on_error == "abort":
                    step.status = StepStatus.FAILED
                    return False
                elif step.on_error == "skip":
                    step.status = StepStatus.SKIPPED
                else:
                    step.status = StepStatus.FAILED

        return all(
            s.status in (StepStatus.SUCCESS, StepStatus.SKIPPED)
            for s in mission.steps
        )


if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    planner = Planner(root)
    print(f"Project: {planner.project_type} at {os.path.abspath(root)}")
    mission = planner.plan("Build the project")
    print(f"Mission: {mission.description}")
    print(f"Steps: {len(mission.steps)}")
    for s in mission.steps:
        print(f"  [{s.id}] {s.description}")
        print(f"       cmd: {s.command[:70]}")
