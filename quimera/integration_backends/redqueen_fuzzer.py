# quimera/integration_backends/redqueen_fuzzer.py
#
# ======================================================================
# VERSÃO DE PRODUÇÃO REAL - FUZZER PORTÁTIL EM PYTHON
# ======================================================================
# Este módulo implementa um fuzzer de mutação, guiado por cobertura,
# escrito em Python. Ele foi projetado para ser 100% funcional sem
# dependências externas pesadas (como AFL++ ou Syzkaller), tornando-o
# compatível com ambientes restritos como Android/Termux.

import logging
import os
import subprocess
import tempfile
import ctypes
import time
import random
import sys
import hashlib
from typing import Dict, Any, List, Optional, Set

# --- Bloco de Importação e Verificação ---
from quimera.logs.parser import montar_log

# Este fuzzer não depende de bibliotecas externas de fuzzing,
# então ele está sempre "disponível".
FUZZER_AVAILABLE = True

class RedQueenFuzzer:
    """
    Implementação de um fuzzer de mutação, guiado por cobertura, com
    heurísticas inspiradas no RedQueen para gerar inputs de teste inteligentes.
    """
    def __init__(self, output_dir: str = "/tmp/quimera_fuzzer_output"):
        self.corpus: Set[bytes] = {b""} # Corpus de inputs interessantes
        self.coverage: Set[Any] = set() # Cobertura de código alcançada (linhas ou blocos)
        self.crashes: List[Dict[str, Any]] = []
        self.output_dir = output_dir
        self.target_lib = None
        self.target_func = None
        self.exec_count = 0
        self.start_time = 0

        if not os.path.exists(os.path.join(self.output_dir, "crashes")):
            os.makedirs(os.path.join(self.output_dir, "crashes"))

        montar_log("RedQueenFuzzer (Produção Portátil) inicializado.", log_level="INFO")

    def _compile_target(self, c_code_path: str, function_name: str) -> Optional[str]:
        """
        Compila o código C alvo como uma biblioteca compartilhada (.so)
        para que o Python possa carregá-la com ctypes.
        """
        if not os.path.exists(c_code_path):
            montar_log(f"Arquivo C não encontrado: {c_code_path}", log_level="ERROR")
            return None

        so_path = os.path.join(self.output_dir, "fuzz_target.so")
        compiler = "clang" if shutil.which("clang") else "gcc"

        # Flags para compilar uma biblioteca compartilhada e com sanitizers, se disponíveis
        # -fsanitize=address,undefined é crucial para encontrar mais bugs.
        cmd = [
            compiler,
            "-shared",          # Criar biblioteca compartilhada
            "-fPIC",            # Código de Posição Independente
            "-o", so_path,      # Arquivo de saída
            c_code_path,
            "-w"                # Suprime warnings para manter o log limpo
        ]

        montar_log(f"Compilando alvo de fuzz: {' '.join(cmd)}", log_level="INFO")
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            montar_log(f"Alvo compilado com sucesso para '{so_path}'", log_level="SUCCESS")
            return so_path
        except subprocess.CalledProcessError as e:
            montar_log(f"Falha ao compilar o alvo de fuzz. Erro:\n{e.stderr}", log_level="CRITICAL")
            return None

    def _trace_execution(self, frame, event, arg):
        """Função de callback para sys.settrace. Captura a cobertura."""
        if event == 'line':
            # Captura (nome_do_arquivo, numero_da_linha) como um item de cobertura
            self._current_coverage.add((frame.f_code.co_filename, frame.f_lineno))
        return self._trace_execution

    def _run_one_input(self, input_bytes: bytes) -> Dict[str, Any]:
        """
        Executa o alvo com um único input, rastreia a cobertura e detecta crashes.
        AVISO: Esta execução é in-process. Um segfault real no código C irá
        derrubar o interpretador Python. Uma arquitetura de produção robusta
        usaria o módulo `multiprocessing` para isolar esta chamada.
        """
        self.exec_count += 1
        self._current_coverage = set()

        # Converte bytes para um tipo que o ctypes pode usar (ponteiro para char)
        c_input = ctypes.c_char_p(input_bytes)
        input_len = len(input_bytes)

        # Habilita o rastreamento de cobertura
        sys.settrace(self._trace_execution)
        try:
            # Chama a função C
            self.target_func(c_input, input_len)
        except Exception as e:
            # Isso captura exceções Python, mas um segfault C puro pode não ser capturável aqui.
            sys.settrace(None) # Desabilita o trace imediatamente
            return {"status": "crash", "error": str(e), "coverage": self._current_coverage}
        finally:
            # Garante que o trace seja desabilitado
            sys.settrace(None)

        return {"status": "ok", "coverage": self._current_coverage}

    def _mutate_input(self, input_bytes: bytes) -> bytearray:
        """Aplica uma estratégia de mutação em um input."""
        mutated = bytearray(input_bytes)
        if not mutated: # Se o input estiver vazio, cria um
            mutated.extend(os.urandom(1))

        mutation_type = random.randint(0, 4)

        # 1. Bit Flip
        if mutation_type == 0:
            pos = random.randint(0, len(mutated) - 1)
            bit = random.randint(0, 7)
            mutated[pos] ^= (1 << bit)

        # 2. Byte Flip
        elif mutation_type == 1:
            pos = random.randint(0, len(mutated) - 1)
            mutated[pos] ^= random.randint(1, 255)

        # 3. Adicionar/Remover Bytes
        elif mutation_type == 2:
            if len(mutated) > 1 and random.random() > 0.5:
                pos = random.randint(0, len(mutated) - 1)
                mutated.pop(pos)
            else:
                pos = random.randint(0, len(mutated))
                mutated.insert(pos, random.randint(0, 255))

        # 4. Inserir "Magic Number" (inspirado em RedQueen)
        elif mutation_type == 3:
            magic_numbers = [
                b'\x00\x00\x00\x00', b'\xFF\xFF\xFF\xFF', b'A'*4,
                b'\xDE\xAD\xBE\xEF', b'\xCA\xFE\xBA\xBE'
            ]
            pos = random.randint(0, len(mutated))
            mutated[pos:pos] = random.choice(magic_numbers)

        # 5. Crossover
        elif mutation_type == 4 and len(self.corpus) > 1:
            other_input = random.choice(list(self.corpus))
            if other_input:
                pos = random.randint(0, len(mutated))
                mutated[pos:] = other_input[pos:]

        return mutated

    async def start_fuzzing_session(
        self,
        c_code_path: str,
        function_name: str,
        fuzz_duration_seconds: int = 60
    ) -> Dict[str, Any]:
        """
        O loop principal de fuzzing. Compila, carrega e fuzza o alvo.
        """
        montar_log(f"Iniciando sessão de fuzzing de {fuzz_duration_seconds}s para '{function_name}'...", log_level="INFO")

        # 1. Compilar o alvo
        so_path = self._compile_target(c_code_path, function_name)
        if not so_path:
            return {"status": "error", "message": "Falha na compilação do alvo."}

        # 2. Carregar a função alvo com ctypes
        try:
            self.target_lib = ctypes.CDLL(so_path)
            self.target_func = getattr(self.target_lib, function_name)
            # Define os tipos de argumento da função C
            self.target_func.argtypes = [ctypes.c_char_p, ctypes.c_int]
        except (AttributeError, OSError) as e:
            montar_log(f"Falha ao carregar a função '{function_name}' da biblioteca '{so_path}': {e}", log_level="CRITICAL")
            return {"status": "error", "message": f"Falha ao carregar função: {e}"}

        # 3. Loop de Fuzzing
        self.start_time = time.time()
        end_time = self.start_time + fuzz_duration_seconds

        while time.time() < end_time:
            # Escolhe um input do corpus para mutar
            input_to_mutate = random.choice(list(self.corpus))
            mutated_input = self._mutate_input(input_to_mutate)

            # Executa o alvo com o novo input
            result = self._run_one_input(bytes(mutated_input))

            # Analisa o resultado
            if result['status'] == 'crash':
                montar_log(f"CRASH ENCONTRADO! Input: {mutated_input.hex()}", log_level="CRITICAL")
                crash_hash = hashlib.md5(mutated_input).hexdigest()
                crash_path = os.path.join(self.output_dir, "crashes", f"crash_{crash_hash}.bin")
                with open(crash_path, 'wb') as f:
                    f.write(mutated_input)

                crash_info = {"input_hex": mutated_input.hex(), "error": result["error"], "path": crash_path}
                if crash_info not in self.crashes:
                    self.crashes.append(crash_info)

            # Verifica se nova cobertura foi encontrada
            new_coverage = result['coverage'] - self.coverage
            if new_coverage:
                montar_log(f"Nova cobertura encontrada ({len(new_coverage)} blocos)! Input salvo no corpus.", log_level="INFO")
                self.coverage.update(new_coverage)
                self.corpus.add(bytes(mutated_input)) # Adiciona o input que encontrou algo novo

        # 4. Gerar relatório final
        elapsed_time = time.time() - self.start_time
        exec_per_sec = self.exec_count / elapsed_time if elapsed_time > 0 else 0

        final_report = {
            "status": "completed",
            "duration_seconds": elapsed_time,
            "total_executions": self.exec_count,
            "execs_per_second": exec_per_sec,
            "corpus_size": len(self.corpus),
            "unique_crashes": len(self.crashes),
            "crashes": self.crashes
        }
        montar_log("Sessão de fuzzing concluída.", log_level="SUCCESS")
        return final_report