# quimera/kernel/gestor.py

import os
import shutil
import subprocess
import logging
from typing import Dict, Any, Optional, Tuple, Callable, List
from collections import deque
import time
import threading

from quimera.logs.parser import montar_log
from quimera.aegisNative.secure_stubs import check_in_kernelguard
from quimera.utils.retry import retry

logger = logging.getLogger(__name__)

class GestorKernel:
    """
    Gerencia o estado e a integridade do código-fonte do kernel no sistema.
    Encapsula as operações de compilação, limpeza e validação, com foco em
    otimização e segurança para ambientes de produção.
    """
    def __init__(self, kernel_source_path: str):
        if not kernel_source_path or not os.path.isdir(kernel_source_path):
            raise ValueError(f"Caminho do kernel inválido ou não fornecido: '{kernel_source_path}'")

        self.kernel_source_path = kernel_source_path
        self.build_dir = os.path.join(self.kernel_source_path, "quimera_build")
        os.makedirs(self.build_dir, exist_ok=True)
        self.compilation_cache: deque[str] = deque(maxlen=10) # Cache para logs de compilação

        montar_log(f"GestorKernel inicializado para: {self.kernel_source_path}", "INFO")
        self.validar_mobilidade()

    def validar_mobilidade(self) -> Dict[str, Any]:
        """
        Verifica a adequação do ambiente para operações de kernel, incluindo
        arquitetura, permissões e uma verificação de segurança inicial.
        """
        montar_log("Validando ambiente para operações de kernel...", "INFO")

        if not os.path.isdir(os.path.join(self.kernel_source_path, ".git")):
            montar_log(f"Diretório do kernel inválido: {self.kernel_source_path} não é um repositório Git.", "CRITICAL")
            raise RuntimeError("Diretório do kernel malformado.")

        is_root = os.geteuid() == 0
        if not is_root:
            montar_log("Operando em modo não-root. Permissões podem ser limitadas.", "WARNING")

        uname_machine = os.uname().machine.lower()
        if "aarch64" not in uname_machine and "arm" not in uname_machine:
            montar_log(f"Arquitetura '{uname_machine}' não é ARM/ARM64. Otimizações mobile podem não ser efetivas.", "WARNING")

        # Verifica a sanidade do Makefile principal antes de qualquer operação
        kernel_guard_report = check_in_kernelguard(os.path.join(self.kernel_source_path, "Makefile"))
        if not kernel_guard_report["is_safe"]:
            details = kernel_guard_report.get('details', 'N/A')
            montar_log(f"KernelGuard inicial falhou: {details}. Abortando.", "CRITICAL")
            raise RuntimeError(f"KernelGuard inicial detectou anomalias críticas: {details}")

        montar_log("Validação de ambiente concluída. Ambiente OK.", "INFO")
        return {"status": "ok", "is_root": is_root, "architecture": uname_machine, "initial_security_check": kernel_guard_report}

    def limpar_cache_dinamico(self):
        """Limpa artefatos de compilação antigos no diretório de build de forma robusta."""
        montar_log("Limpando cache dinâmico de compilação...", "INFO")
        if os.path.exists(self.build_dir):
            try:
                shutil.rmtree(self.build_dir)
                os.makedirs(self.build_dir)
                montar_log(f"Diretório de build '{self.build_dir}' limpo com sucesso.", "INFO")
            except OSError as e:
                montar_log(f"Falha ao limpar diretório de build: {e}. Verifique as permissões.", "ERROR")
        else:
            os.makedirs(self.build_dir)

    @retry(max_attempts=3, backoff=2.0)
    def compilar_secure(self, source_code_test_file: str, temp_build_dir: str, otimizacao: str = 'default') -> Tuple[bool, str]:
        """
        Compila um fragmento de código C em um ambiente seguro, usando os caminhos de
        include corretos para os cabeçalhos do kernel e um compilador cross-compile.
        """
        montar_log(f"Compilação segura iniciada com otimização: '{otimizacao}'", "INFO")

        temp_c_file_path = os.path.join(temp_build_dir, "temp_quimera_test.c")
        with open(temp_c_file_path, "w", encoding="utf-8") as f:
            f.write(source_code_test_file)

        cross_compile_prefix = os.getenv("CROSS_COMPILE", "aarch64-linux-gnu-")
        compiler_cmd_str = f"{cross_compile_prefix}gcc"
        compiler_path = shutil.which(compiler_cmd_str)

        if not compiler_path:
            montar_log(f"Compilador '{compiler_cmd_str}' não encontrado no PATH.", "CRITICAL")
            return False, f"Erro: Compilador '{compiler_cmd_str}' não encontrado."

        flags: List[str] = [
            f"-I{self.kernel_source_path}/include",
            f"-I{self.kernel_source_path}/arch/arm64/include",
            f"-I{self.kernel_source_path}/arch/arm64/include/uapi",
            f"-I{self.build_dir}/include",
            "-include", f"{self.kernel_source_path}/include/linux/kconfig.h",
            "-nostdinc",
            "-c",
            "-o", os.path.join(temp_build_dir, "temp_quimera_test.o")
        ]

        if otimizacao == 'mobile_fast':
            flags.extend(["-O3", "-mcpu=cortex-a715", "-mtune=cortex-a715", "-fomit-frame-pointer", "-fPIC", "-Werror"])
            montar_log("Compilação com otimização 'mobile_fast' ativada.", "INFO")

        command = [compiler_path] + flags + [temp_c_file_path]

        try:
            montar_log(f"Executando compilação de teste: {' '.join(command)}", "DEBUG")
            result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=90)

            full_log = result.stdout + "\n" + result.stderr
            self.compilation_cache.append(full_log)

            if result.returncode == 0:
                montar_log("Compilação de teste bem-sucedida.", "INFO")
                return True, full_log
            else:
                montar_log(f"Compilação de teste falhou (Exit Code: {result.returncode}): {full_log.strip()}", "WARNING")
                return False, full_log

        except subprocess.TimeoutExpired:
            montar_log("Compilação de teste excedeu o tempo limite de 90s.", "ERROR")
            return False, "Compilação excedeu o tempo limite."
        except Exception as e:
            montar_log(f"Erro inesperado durante a compilação de teste: {e}", "CRITICAL", exc_info=True)
            return False, f"Erro inesperado: {e}"
        finally:
            if os.path.exists(temp_c_file_path): os.remove(temp_c_file_path)
            temp_obj_path = os.path.join(temp_build_dir, "temp_quimera_test.o")
            if os.path.exists(temp_obj_path): os.remove(temp_obj_path)

    def obter_saude(self) -> Dict[str, Any]:
        """Obtém métricas de saúde do kernel e informações de compilação."""
        return {
            "last_compilation_log_summary": self.compilation_cache[-1][:500] + "..." if self.compilation_cache else "N/A",
            "compilation_cache_size": len(self.compilation_cache),
        }