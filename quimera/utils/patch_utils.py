"""
Patch Utilities — Geração, aplicação e validação de patches.
"""
import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

logger = logging.getLogger("quimera.patch_utils")

def generate_patch_id(source_code: str, target_arch: str = "aarch64") -> str:
    """Gera um ID único para um patch baseado no código fonte."""
    content_hash = hashlib.sha256(source_code.encode()).hexdigest()[:12]
    return f"patch_{target_arch}_{content_hash}"

def apply_patch_to_kernel(kernel_path: str, patch_content: str) -> Tuple[bool, str]:
    """Aplica um patch a um kernel. Retorna (sucesso, mensagem)."""
    if not os.path.exists(kernel_path):
        return False, f"Kernel path not found: {kernel_path}"
    try:
        with open(kernel_path, 'a') as f:
            f.write(f"\n// PATCH APPLIED: {generate_patch_id(patch_content)}\n")
            f.write(patch_content)
        return True, "Patch applied successfully"
    except Exception as e:
        return False, f"Failed to apply patch: {e}"

def compile_kernel(kernel_path: str, target_arch: str = "aarch64") -> Tuple[bool, str]:
    """Compila um kernel para a arquitetura alvo."""
    logger.info(f"Compiling {kernel_path} for {target_arch}")
    return True, f"Compilation simulated for {target_arch}"

def validate_patch(patch_content: str) -> Dict:
    """Valida um patch contra regras de segurança e estilo."""
    issues = []
    if "rm -rf" in patch_content.lower():
        issues.append("Dangerous command detected")
    if "system(" in patch_content:
        issues.append("System call detected — requires sandbox")
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "patch_id": generate_patch_id(patch_content),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
