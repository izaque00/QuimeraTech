# quimera/utils/linter.py

import logging
import subprocess
import os
import shutil
from typing import Dict, Any

logger = logging.getLogger(__name__)

def run_linter_on_patch(kernel_root: str, patch_content: str) -> Dict[str, Any]:
    """
    Executa uma suíte de linters (checkpatch.pl e sparse) em um patch.
    Combina os resultados para um score de qualidade abrangente.

    Args:
        kernel_root (str): Caminho absoluto para a raiz do repositório do kernel.
        patch_content (str): O conteúdo do patch a ser verificado.

    Returns:
        Um dicionário com um score combinado, e os erros e avisos detalhados de cada linter.
    """
    checkpatch_result = _run_checkpatch(kernel_root, patch_content)
    # A verificação com sparse é mais complexa e geralmente requer o código aplicado.
    # Por agora, estamos usando uma simulação. A implementação real seria um passo futuro.
    sparse_result = _run_sparse(kernel_root, patch_content)

    # Combina os resultados
    total_errors = checkpatch_result.get("errors", []) + sparse_result.get("errors", [])
    total_warnings = checkpatch_result.get("warnings", []) + sparse_result.get("warnings", [])

    # Média ponderada dos scores, dando mais peso aos erros do checkpatch,
    # pois são mais diretos de resolver e indicam problemas de estilo claros.
    final_score = (checkpatch_result.get("score", 0.5) * 0.7) + (sparse_result.get("score", 0.5) * 0.3)

    return {
        "score": round(final_score, 2),
        "errors": total_errors,
        "warnings": total_warnings,
        "checkpatch_log": checkpatch_result.get("log", ""),
        "sparse_log": sparse_result.get("log", "")
    }

def _run_checkpatch(kernel_root: str, patch_content: str) -> dict:
    """Usa o script checkpatch.pl, a ferramenta oficial do kernel Linux, para validar o estilo de um patch."""
    if not kernel_root:
        logger.warning("KERNEL_ROOT não definido, pulando checkpatch.pl.")
        return {"score": 0.5, "warnings": ["KERNEL_ROOT não definido"], "errors": [], "log": "KERNEL_ROOT not set"}

    checkpatch_path = os.path.join(kernel_root, "scripts/checkpatch.pl")

    if not os.path.exists(checkpatch_path):
        logger.warning(f"O script 'checkpatch.pl' não foi encontrado em '{checkpatch_path}'. Pulando verificação de estilo.")
        return {"score": 0.5, "warnings": ["checkpatch.pl não encontrado"], "errors": [], "log": "checkpatch.pl not found"}

    logger.info("Executando verificação de estilo com checkpatch.pl...")

    if not patch_content.endswith('\n'):
        patch_content += '\n'

    try:
        result = subprocess.run(
            [checkpatch_path, "--no-tree", "--strict", "-"],
            input=patch_content.encode('utf-8', errors='ignore'),
            capture_output=True,
            text=True,
            timeout=45
        )

        output = result.stdout

        errors = [line for line in output.splitlines() if line.startswith("ERROR:")]
        warnings = [line for line in output.splitlines() if line.startswith("WARNING:")]

        score = 1.0
        score -= len(errors) * 0.20
        score -= len(warnings) * 0.05

        final_score = max(0.0, score)

        if errors or warnings:
            logger.warning(f"checkpatch.pl encontrou {len(errors)} erro(s) e {len(warnings)} aviso(s). Score de estilo: {final_score:.2f}")
        else:
            logger.info("checkpatch.pl não encontrou problemas de estilo. O patch está limpo.")

        return {
            "score": round(final_score, 2),
            "warnings": warnings,
            "errors": errors,
            "log": output
        }

    except Exception as e:
        logger.error(f"Erro ao executar checkpatch.pl: {e}", exc_info=True)
        return {
            "score": 0.1,
            "warnings": [],
            "errors": [f"Erro crítico na execução do linter: {e}"],
            "log": f"Erro na execução do linter: {e}"
        }

def _run_sparse(kernel_root: str, patch_content: str) -> dict:
    """Executa verificação real com o analisador estático sparse (Linux kernel)."""
    sparse_bin = shutil.which("sparse")
    if not sparse_bin:
        logger.info("sparse não encontrado no PATH — pulando verificação semântica")
        return {"score": 0.5, "warnings": ["sparse não instalado"], "errors": [], "log": "sparse not found in PATH"}

    logger.info("Executando sparse real no kernel...")
    
    import subprocess
    import tempfile
    
    # Write patch to temp file for sparse analysis
    with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False, prefix='quimera_lint_') as tmp:
        tmp.write(patch_content)
        tmp_path = tmp.name
    
    try:
        # Run sparse with all warnings enabled
        result = subprocess.run(
            [sparse_bin, "-Wsparse-all", tmp_path],
            capture_output=True, text=True, timeout=30,
            cwd=kernel_root
        )
        
        warnings = []
        errors = []
        
        for line in result.stderr.split('\n') + result.stdout.split('\n'):
            line = line.strip()
            if not line:
                continue
            if 'error:' in line.lower():
                errors.append(line)
            elif 'warning:' in line.lower():
                warnings.append(line)
        
        score = 1.0
        if errors:
            score = max(0.1, 0.8 - len(errors) * 0.15)
        elif warnings:
            score = max(0.3, 0.9 - len(warnings) * 0.05)
        
        log_output = result.stderr[:2000] if result.stderr else "sparse: no issues found"
        
        return {
            "score": score,
            "warnings": warnings[:20],
            "errors": errors[:20],
            "log": log_output,
        }
    except subprocess.TimeoutExpired:
        logger.warning("sparse timeout after 30s")
        return {"score": 0.3, "warnings": [], "errors": ["sparse timeout"], "log": "timeout"}
    except Exception as e:
        logger.warning(f"sparse execution failed: {e}")
        return {"score": 0.3, "warnings": [], "errors": [str(e)], "log": f"sparse error: {e}"}
    finally:
        try:
            import os as _os
            _os.unlink(tmp_path)
        except Exception:
            pass

# Backward compatibility alias
_run_sparse_mock = _run_sparse
# Backward compatibility alias
check_code_lint = run_linter_on_patch
