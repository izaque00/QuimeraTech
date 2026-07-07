# quimera/testes/test_patch.py
import pytest
import os
import shutil
import subprocess
from pathlib import Path

# Importações dos seus módulos internos
from quimera.utils.patch_utils import diff_analysis, generate_patch_id, apply_patch_to_kernel, compile_kernel
from quimera.utils.general import write_code, get_code # Para utilitários de leitura/escrita
from quimera.utils.kernel_utils import create_kernel_backup, restore_kernel_state # Para gerenciar estado do kernel para testes

# Configuração de logging para testes
import logging
logger = logging.getLogger("TestePatch")
logger.setLevel(logging.INFO) # Nível de log INFO para testes
# Desabilita logs muito verbosos de libs externas durante os testes
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('redis').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)


# --- Fixtures para Testes ---
@pytest.fixture
def kernel_test_env(tmp_path):
    """
    Cria um ambiente de kernel simulado para testes, com um diretório de kernel e um de build,
    e um arquivo inicial para ser patchado.
    `tmp_path` é uma fixture do pytest para diretórios temporários.
    """
    test_kernel_root = tmp_path / "test_kernel"
    test_build_dir = test_kernel_root / "quimera_build"

    # Cria a estrutura mínima de um repositório Git
    test_kernel_root.mkdir()
    (test_kernel_root / ".git").mkdir()

    # Cria um Makefile mínimo para simular a compilação
    (test_kernel_root / "Makefile").write_text("all:\n\t@echo 'Kernel make done.'\n\t@exit 0")

    # Cria um arquivo de código para ser patchado
    test_source_dir = test_kernel_root / "drivers" / "char"
    test_source_dir.mkdir(parents=True)
    test_file_path = test_source_dir / "my_driver.c"
    test_file_path.write_text("/* Original code */\nint main() { return 0; }")

    test_build_dir.mkdir()

    # Define KERNEL_ROOT no ambiente para os utilitários
    os.environ["KERNEL_ROOT"] = str(test_kernel_root)

    yield str(test_kernel_root), str(test_build_dir), str(test_file_path)

    # A limpeza é feita automaticamente pelo tmp_path

# --- Testes para diff_analysis ---
def test_diff_analysis_basic():
    """Testa a análise de um diff básico."""
    diff_content = """--- a/old_file.py
+++ b/new_file.py
@@ -1,2 +1,3 @@
-linha1
+nova_linha1
+nova_linha2
"""
    result = diff_analysis(diff_content)
    assert "nova_linha1" in result["added"]
    assert "linha1" in result["removed"]
    assert len(result["context"]) == 0
    assert len(result["all_lines"]) == 5

# --- Testes para generate_patch_id ---
def test_generate_patch_id_unique():
    """Testa se IDs de patches são únicos para conteúdos diferentes."""
    id1 = generate_patch_id("patch content 1")
    id2 = generate_patch_id("patch content 2")
    id3 = generate_patch_id("patch content 1")

    assert len(id1) == 64 # SHA256 padrão
    assert id1 != id2
    assert id1 == id3

def test_generate_patch_id_empty():
    """Testa o ID de patch para conteúdo vazio ou nulo."""
    assert generate_patch_id("") == "empty_patch"
    assert generate_patch_id("   ") == "empty_patch"
    assert generate_patch_id(None) == "empty_patch"

# --- Testes para apply_patch_to_kernel ---
@pytest.mark.asyncio
async def test_apply_patch_dry_run_success(kernel_test_env):
    """Testa a simulação de aplicação de patch bem-sucedida."""
    kernel_root, _, test_file_path = kernel_test_env

    patch_content = """--- a/drivers/char/my_driver.c
+++ b/drivers/char/my_driver.c
@@ -1,2 +1,3 @@
 /* Original code */
 int main() { return 0; }
+void new_feature() {}
"""
    success, output = apply_patch_to_kernel(kernel_root, patch_content, dry_run=True)

    assert success is True
    assert "Patch applied." in output # Ou mensagem similar de sucesso dry-run
    # Verifica que o arquivo original não foi alterado
    assert get_code(test_file_path) == "/* Original code */\nint main() { return 0; }"

@pytest.mark.asyncio
async def test_apply_patch_real_success(kernel_test_env):
    """Testa a aplicação real de patch bem-sucedida."""
    kernel_root, _, test_file_path = kernel_test_env

    patch_content = """--- a/drivers/char/my_driver.c
+++ b/drivers/char/my_driver.c
@@ -1,2 +1,3 @@
 /* Original code */
 int main() { return 0; }
+void new_feature() {}
"""
    success, output = apply_patch_to_kernel(kernel_root, patch_content, dry_run=False)

    assert success is True
    assert "Patching file drivers/char/my_driver.c" in output # Mensagem de sucesso real
    # Verifica que o arquivo foi realmente alterado
    assert get_code(test_file_path) == "/* Original code */\nint main() { return 0; }\nvoid new_feature() {}\n"

@pytest.mark.asyncio
async def test_apply_patch_revert(kernel_test_env):
    """Testa a reversão de um patch."""
    kernel_root, _, test_file_path = kernel_test_env

    # Primeiro, aplica o patch
    patch_content = """--- a/drivers/char/my_driver.c
+++ b/drivers/char/my_driver.c
@@ -1,2 +1,3 @@
 /* Original code */
 int main() { return 0; }
+void new_feature() {}
"""
    apply_patch_to_kernel(kernel_root, patch_content, dry_run=False)

    # Agora, reverte
    success, output = apply_patch_to_kernel(kernel_root, patch_content, reverter=True)

    assert success is True
    assert "Reversed (or previously applied) patch" in output # Ou mensagem similar de reversão
    assert get_code(test_file_path) == "/* Original code */\nint main() { return 0; }" # Volta ao original

@pytest.mark.asyncio
async def test_apply_patch_failure(kernel_test_env):
    """Testa a falha na aplicação de patch (ex: arquivo já modificado)."""
    kernel_root, _, test_file_path = kernel_test_env

    # Modifica o arquivo para criar um conflito
    write_code(test_file_path, "/* Conflict code */\nint main() { return 1; }")

    patch_content = """--- a/drivers/char/my_driver.c
+++ b/drivers/char/my_driver.c
@@ -1,2 +1,3 @@
 /* Original code */
 int main() { return 0; }
+void new_feature() {}
"""
    success, output = apply_patch_to_kernel(kernel_root, patch_content, dry_run=False)

    assert success is False
    assert "Hunk #1 FAILED" in output # Mensagem típica de conflito

# --- Testes para compile_kernel ---
@pytest.mark.asyncio
async def test_compile_kernel_success(kernel_test_env):
    """Testa a compilação de kernel bem-sucedida."""
    kernel_root, build_dir, _ = kernel_test_env

    # Mock do subprocess.run para 'make'
    with patch('subprocess.run') as mock_sub_run:
        # Simula a chamada de make defconfig primeiro
        mock_sub_run.side_effect = [
            MagicMock(returncode=0, stdout="Configured defconfig.", stderr=""), # make defconfig
            MagicMock(returncode=0, stdout="Kernel make done.", stderr="")      # make compile
        ]

        success, log = compile_kernel(kernel_root, build_dir)

        assert success is True
        assert "Kernel make done." in log
        assert "Configured defconfig." in log
        assert (Path(build_dir) / ".config").exists() # Verifica se o arquivo de config foi "criado"

@pytest.mark.asyncio
async def test_compile_kernel_failure(kernel_test_env):
    """Testa a falha na compilação do kernel."""
    kernel_root, build_dir, _ = kernel_test_env

    with patch('subprocess.run') as mock_sub_run:
        # Simula a falha de compilação
        mock_sub_run.side_effect = [
            MagicMock(returncode=0, stdout="Configured defconfig.", stderr=""), # make defconfig
            MagicMock(returncode=1, stdout="", stderr="Compilation Error: missing header.") # make compile
        ]

        success, log = compile_kernel(kernel_root, build_dir)

        assert success is False
        assert "Compilation Error: missing header." in log