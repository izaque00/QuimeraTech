# quimera/memory/cross_kernel.py
"""
Cross-Kernel Transfer Learning — Aprendizado entre kernels diferentes.

Transfere conhecimento de reparo entre:
    - Kernel Linux → Android kernel
    - x86_64 → aarch64
    - Versões diferentes do mesmo kernel

Estratégia:
    1. Mapear correspondências de subsistemas entre kernels
    2. Adaptar soluções considerando diferenças de arquitetura
    3. Validar soluções adaptadas em sandbox antes de aplicar

Uso:
    from quimera.memory.cross_kernel import CrossKernelTransfer
    
    xfer = CrossKernelTransfer(source_kernel="linux", target_kernel="android")
    adapted = xfer.adapt_solution(solution, context)
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class KernelProfile:
    """Perfil de um kernel para transfer learning."""
    name: str
    arch: str
    version: str
    subsystems: Set[str] = field(default_factory=set)
    config_options: Dict[str, str] = field(default_factory=dict)
    toolchain: str = "gcc"


# Mapeamentos conhecidos entre kernels
KERNEL_SUBSYSTEM_MAP = {
    "linux": {
        "drivers/net": "drivers/net",
        "drivers/gpu": "drivers/gpu",
        "fs": "fs",
        "mm": "mm",
        "kernel/sched": "kernel/sched",
        "arch/x86": "arch/arm64",
        "arch/arm64": "arch/arm64",
    },
    "android": {
        "drivers/net": "drivers/net",
        "drivers/gpu": "drivers/gpu/drm",
        "fs": "fs",
        "mm": "mm",
        "kernel/sched": "kernel/sched",
        "arch/arm64": "arch/arm64",
    },
}

ARCH_EQUIVALENCES = {
    "x86_64": ["x86_64", "amd64", "x86"],
    "aarch64": ["aarch64", "arm64", "armv8"],
    "arm": ["arm", "armv7", "armv7l"],
    "riscv64": ["riscv64", "riscv"],
}

# Padrões de adaptação de código entre arquiteturas
ARCH_ADAPTATION_RULES = [
    {
        "pattern": "movq",
        "x86_64": "movq %rsi, %rdi",
        "aarch64": "mov x0, x1",
    },
    {
        "pattern": "rdtsc",
        "x86_64": "rdtsc",
        "aarch64": "mrs x0, cntvct_el0",
    },
    {
        "pattern": "__iomem",
        "x86_64": "__iomem *",
        "aarch64": "void __iomem *",
    },
]


class CrossKernelTransfer:
    """Motor de transferência de conhecimento entre kernels.
    
    Permite que soluções de reparo aprendidas em um kernel
    (ex: Linux x86_64) sejam adaptadas para outro
    (ex: Android aarch64).
    """
    
    def __init__(
        self,
        source_kernel: str = "linux",
        target_kernel: str = "android",
        source_arch: str = "x86_64",
        target_arch: str = "aarch64",
    ):
        self.source = KernelProfile(
            name=source_kernel,
            arch=source_arch,
            version="unknown",
        )
        self.target = KernelProfile(
            name=target_kernel,
            arch=target_arch,
            version="unknown",
        )
        self._adaptation_cache: Dict[str, str] = {}
        logger.info(
            f"CrossKernelTransfer: {source_kernel}/{source_arch} → {target_kernel}/{target_arch}"
        )
    
    def map_subsystem(self, source_path: str) -> Optional[str]:
        """Mapeia subsistema do kernel fonte para o alvo.
        
        Args:
            source_path: Caminho do arquivo no kernel fonte.
            
        Returns:
            Caminho equivalente no kernel alvo, ou None.
        """
        source_map = KERNEL_SUBSYSTEM_MAP.get(self.source.name, {})
        target_map = KERNEL_SUBSYSTEM_MAP.get(self.target.name, {})
        
        for src_prefix, src_target in source_map.items():
            if source_path.startswith(src_prefix):
                target_prefix = target_map.get(src_prefix, src_target)
                return source_path.replace(src_prefix, target_prefix, 1)
        
        return None
    
    def are_arches_compatible(self, source_arch: str, target_arch: str) -> bool:
        """Verifica se arquiteturas são compatíveis para transfer."""
        for group in ARCH_EQUIVALENCES.values():
            if source_arch in group and target_arch in group:
                return True
        return False
    
    def adapt_solution(
        self,
        solution_description: str,
        source_context: Dict = None,
        target_context: Dict = None,
    ) -> str:
        """Adapta uma solução do kernel fonte para o alvo.
        
        Args:
            solution_description: Descrição da solução original.
            source_context: Contexto do kernel fonte (paths, configs).
            target_context: Contexto do kernel alvo.
            
        Returns:
            Solução adaptada.
        """
        adapted = solution_description
        
        # 1. Adaptação de caminhos de subsistema
        if source_context and target_context:
            source_path = source_context.get("file_path", "")
            target_path = target_context.get("file_path", "")
            adapted = adapted.replace(source_path, target_path)
        
        # 2. Adaptação de nomes de função específicos de arch
        arch_rules = {
            "x86_64": {"aarch64": {
                "native_read_tsc": "read_cntvct",
                "__arch_irq_stat": "arch_irq_stat",
                "load_gs_index": "",  # não existe em aarch64
            }},
        }
        
        rules = arch_rules.get(self.source.arch, {}).get(self.target.arch, {})
        for old, new in rules.items():
            adapted = adapted.replace(old, new)
        
        # 3. Adaptação de padrões de código
        for rule in ARCH_ADAPTATION_RULES:
            if self.source.arch in rule and self.target.arch in rule:
                adapted = adapted.replace(
                    rule.get(self.source.arch, ""),
                    rule.get(self.target.arch, ""),
                )
        
        # Cache
        cache_key = f"{solution_description[:100]}→{self.target.name}"
        self._adaptation_cache[cache_key] = adapted
        
        logger.debug(
            f"CrossKernelTransfer: solução adaptada "
            f"({self.source.name}/{self.source.arch} → {self.target.name}/{self.target.arch})"
        )
        return adapted
    
    def estimate_transferability(
        self,
        source_error_type: str,
        source_subsystem: str,
    ) -> float:
        """Estima a probabilidade de transferência bem-sucedida.
        
        Returns:
            Score 0-1 de transferibilidade.
        """
        score = 0.5  # baseline
        
        # Mesmo subsistema → +0.3
        target_path = self.map_subsystem(source_subsystem)
        if target_path:
            score += 0.3
        
        # Arquiteturas compatíveis → +0.2
        if self.are_arches_compatible(self.source.arch, self.target.arch):
            score += 0.2
        
        # Erro genérico (não arch-specific) → +0.1
        arch_specific_errors = {"alignment_fault", "tlb_miss", "page_fault_arch"}
        if source_error_type not in arch_specific_errors:
            score += 0.1
        
        return min(score, 1.0)
    
    def get_transfer_report(self) -> Dict:
        """Relatório de transferência."""
        return {
            "source": {
                "kernel": self.source.name,
                "arch": self.source.arch,
            },
            "target": {
                "kernel": self.target.name,
                "arch": self.target.arch,
            },
            "compatible_arch": self.are_arches_compatible(
                self.source.arch, self.target.arch
            ),
            "cached_adaptations": len(self._adaptation_cache),
        }
