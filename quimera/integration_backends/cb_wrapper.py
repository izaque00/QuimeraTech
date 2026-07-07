"""CBMC/ESBMC Wrapper — Bounded Model Checking para C.

Integra bounded model checkers (CBMC, ESBMC) ao pipeline de verificação
do Quimera. Bounded model checking verifica propriedades até um limite
de profundidade (unwinding bound), provando ausência de erros dentro
desse limite.

Diferença Z3 vs CBMC:
    Z3: verificação de propriedades específicas em fórmulas SMT
    CBMC: verificação completa do programa C (todas as paths) até bound K

Uso:
    from quimera.integration_backends.cb_wrapper import CBMCAnalyzer
    
    analyzer = CBMCAnalyzer()
    result = analyzer.verify(
        code=patched_c,
        properties=["assert", "overflow", "pointer"],
        unwind_bound=100
    )
    
    if result.all_passed:
        print(f"✅ Todas as {result.total_properties} propriedades provadas")
    else:
        print(f"❌ {result.failed_count} falhas encontradas")
"""

import logging
import subprocess
import tempfile
import os
import shutil
import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from enum import Enum

from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================

class CBMCPropertyType(Enum):
    """Tipos de propriedades que o CBMC pode verificar."""
    ASSERT = "assert"               # __CPROVER_assert()
    ASSUME = "assume"               # __CPROVER_assume()
    ARRAY_BOUNDS = "array-bounds"   # Acesso fora dos limites
    POINTER = "pointer"             # Ponteiro inválido
    OVERFLOW = "overflow"           # Integer overflow
    DIV_BY_ZERO = "div-by-zero"     # Divisão por zero
    MEMORY_LEAK = "memory-leak"     # Vazamento de memória
    NARROWING = "narrowing"         # Cast com perda de precisão
    UNINITIALIZED = "uninitialized" # Variável não inicializada
    DEAD_CODE = "dead-code"         # Código inalcançável


class CBMCStatus(Enum):
    SUCCESS = "SUCCESS"        # Todas as propriedades provadas
    FAILURE = "FAILURE"        # Uma ou mais propriedades violadas
    ERROR = "ERROR"            # Erro na execução do CBMC
    UNKNOWN = "UNKNOWN"        # Timeout ou inconclusivo
    NOT_INSTALLED = "NOT_INSTALLED"


@dataclass
class CBMCPropertyResult:
    """Resultado de uma propriedade verificada."""
    property_id: str
    description: str
    status: str  # "SUCCESS" ou "FAILURE"
    source_line: int
    counterexample_trace: Optional[str] = None


@dataclass
class CBMCAnalysisResult:
    """Resultado completo da análise CBMC."""
    tool: str  # "cbmc" ou "esbmc"
    status: CBMCStatus
    total_properties: int
    passed_properties: int
    failed_properties: int
    properties: List[CBMCPropertyResult] = field(default_factory=list)
    unwind_bound: int = 0
    analysis_time_ms: float = 0.0
    raw_output: str = ""
    error_message: str = ""
    all_passed: bool = False

    def __post_init__(self):
        self.all_passed = (
            self.status == CBMCStatus.SUCCESS
            and self.failed_properties == 0
            and self.total_properties > 0
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool,
            "status": self.status.value,
            "total_properties": self.total_properties,
            "passed": self.passed_properties,
            "failed": self.failed_properties,
            "all_passed": self.all_passed,
            "unwind_bound": self.unwind_bound,
            "analysis_time_ms": self.analysis_time_ms,
        }


# ============================================================================
# CBMCAnalyzer
# ============================================================================

class CBMCAnalyzer:
    """Analisador usando CBMC/ESBMC para bounded model checking de código C.

    Suporta CBMC (C Bounded Model Checker) e ESBMC (Efficient SMT-Based
    Bounded Model Checker). Ambos verificam código C completo até uma
    profundidade de desenrolamento (unwind bound).

    Attributes:
        preferred_tool: "cbmc", "esbmc", ou "auto" (tenta ambos).
        default_unwind: Profundidade padrão de desenrolamento.
        timeout_seconds: Timeout para cada verificação.
    """

    # Mapeamento de propriedades para flags CBMC
    _PROPERTY_FLAGS = {
        CBMCPropertyType.ASSERT: None,  # Já habilitado por padrão
        CBMCPropertyType.ARRAY_BOUNDS: "--bounds-check",
        CBMCPropertyType.POINTER: "--pointer-check",
        CBMCPropertyType.OVERFLOW: "--signed-overflow-check --unsigned-overflow-check",
        CBMCPropertyType.DIV_BY_ZERO: "--div-by-zero-check",
        CBMCPropertyType.MEMORY_LEAK: "--memory-leak-check",
        CBMCPropertyType.NARROWING: "--conversion-check",
        CBMCPropertyType.UNINITIALIZED: "--uninitialized-check",
        CBMCPropertyType.DEAD_CODE: None,
    }

    def __init__(
        self,
        preferred_tool: str = "auto",
        default_unwind: int = 100,
        timeout_seconds: int = 60,
        keep_temp_files: bool = False,
    ):
        self.preferred_tool = preferred_tool
        self.default_unwind = default_unwind
        self.timeout_seconds = timeout_seconds
        self.keep_temp_files = keep_temp_files

        # Detectar ferramentas disponíveis
        self._cbmc_path = shutil.which("cbmc")
        self._esbmc_path = shutil.which("esbmc")

        if self._cbmc_path:
            montar_log(f"CBMCAnalyzer: CBMC encontrado em {self._cbmc_path}", "INFO")
        else:
            montar_log("CBMCAnalyzer: CBMC NÃO encontrado no PATH", "WARNING")

        if self._esbmc_path:
            montar_log(f"CBMCAnalyzer: ESBMC encontrado em {self._esbmc_path}", "INFO")
        else:
            montar_log("CBMCAnalyzer: ESBMC NÃO encontrado no PATH", "WARNING")

    # ------------------------------------------------------------------
    # API Principal
    # ------------------------------------------------------------------

    def verify(
        self,
        code: str,
        properties: Optional[List[str]] = None,
        unwind_bound: Optional[int] = None,
        function_name: str = "main",
        extra_cprover_asserts: Optional[List[Tuple[str, str]]] = None,
    ) -> CBMCAnalysisResult:
        """Verifica código C com bounded model checking.

        Args:
            code: Código C a verificar.
            properties: Lista de propriedades a verificar (values de CBMCPropertyType).
            unwind_bound: Profundidade de desenrolamento (default: self.default_unwind).
            function_name: Função de entrada.
            extra_cprover_asserts: Lista de (descrição, condição) para asserts extras.

        Returns:
            CBMCAnalysisResult com resultados.
        """
        import time
        start = time.time()

        tool = self._select_tool()
        if not tool:
            return CBMCAnalysisResult(
                tool="none",
                status=CBMCStatus.NOT_INSTALLED,
                total_properties=0,
                passed_properties=0,
                failed_properties=0,
                error_message="Nem CBMC nem ESBMC encontrados no PATH. Instale: apt install cbmc",
            )

        unwind = unwind_bound or self.default_unwind
        prop_types = self._parse_properties(properties)

        # Gerar arquivo C temporário com CPROVER asserts
        instrumented_code = self._instrument_code(
            code, prop_types, extra_cprover_asserts
        )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".c", delete=not self.keep_temp_files, prefix="quimera_cbmc_"
        ) as tmp:
            tmp.write(instrumented_code)
            tmp.flush()

            try:
                cmd = self._build_command(tool, tmp.name, prop_types, unwind, function_name)
                logger.debug(f"Executando: {' '.join(cmd)}")

                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                )
                output = proc.stdout + proc.stderr
                result = self._parse_output(tool, output, unwind)

            except subprocess.TimeoutExpired:
                result = CBMCAnalysisResult(
                    tool=tool,
                    status=CBMCStatus.UNKNOWN,
                    total_properties=0,
                    passed_properties=0,
                    failed_properties=0,
                    unwind_bound=unwind,
                    error_message=f"Timeout após {self.timeout_seconds}s",
                )
            except Exception as e:
                result = CBMCAnalysisResult(
                    tool=tool,
                    status=CBMCStatus.ERROR,
                    total_properties=0,
                    passed_properties=0,
                    failed_properties=0,
                    unwind_bound=unwind,
                    error_message=str(e),
                )

        result.analysis_time_ms = (time.time() - start) * 1000
        montar_log(
            f"CBMCAnalyzer ({tool}): {result.passed_properties}/{result.total_properties} "
            f"passaram em {result.analysis_time_ms:.0f}ms (bound={unwind})",
            "INFO" if result.all_passed else "WARNING"
        )

        return result

    def verify_patch(
        self,
        original_code: str,
        patched_code: str,
        properties: Optional[List[str]] = None,
        unwind_bound: Optional[int] = None,
    ) -> Dict[str, CBMCAnalysisResult]:
        """Verifica um patch: analisa código original e patcheado.

        Args:
            original_code: Código antes do patch.
            patched_code: Código após o patch.
            properties: Propriedades a verificar.
            unwind_bound: Profundidade de desenrolamento.

        Returns:
            Dict com 'original' e 'patched' resultados.
        """
        results = {}
        for label, code in [("original", original_code), ("patched", patched_code)]:
            try:
                results[label] = self.verify(code, properties, unwind_bound)
            except Exception as e:
                results[label] = CBMCAnalysisResult(
                    tool="error",
                    status=CBMCStatus.ERROR,
                    total_properties=0,
                    passed_properties=0,
                    failed_properties=0,
                    error_message=str(e),
                )

        # Comparar: patch não deve introduzir novas falhas
        if "original" in results and "patched" in results:
            orig_failed = results["original"].failed_properties
            patch_failed = results["patched"].failed_properties
            if patch_failed > orig_failed:
                montar_log(
                    f"CBMCAnalyzer: patch introduziu {patch_failed - orig_failed} "
                    f"novas falhas (de {orig_failed} para {patch_failed})",
                    "WARNING"
                )

        return results

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _select_tool(self) -> Optional[str]:
        """Seleciona a melhor ferramenta disponível."""
        if self.preferred_tool == "cbmc" and self._cbmc_path:
            return "cbmc"
        if self.preferred_tool == "esbmc" and self._esbmc_path:
            return "esbmc"
        if self._cbmc_path:
            return "cbmc"
        return "esbmc" if self._esbmc_path else None

    def _parse_properties(self, properties: Optional[List[str]]) -> List[CBMCPropertyType]:
        """Converte lista de strings para CBMCPropertyType."""
        if not properties:
            return [
                CBMCPropertyType.ASSERT,
                CBMCPropertyType.ARRAY_BOUNDS,
                CBMCPropertyType.POINTER,
                CBMCPropertyType.OVERFLOW,
            ]
        result = []
        for p in properties:
            try:
                result.append(CBMCPropertyType(p))
            except ValueError:
                logger.warning(f"Propriedade CBMC desconhecida: {p}")
        return result

    def _build_command(
        self,
        tool: str,
        filepath: str,
        properties: List[CBMCPropertyType],
        unwind: int,
        function: str,
    ) -> List[str]:
        """Constrói comando CBMC/ESBMC."""
        if tool == "cbmc":
            cmd = [self._cbmc_path, filepath, f"--function", function]
        else:
            cmd = [self._esbmc_path, filepath, f"--function", function]

        cmd.append(f"--unwind {unwind}")
        cmd.append("--unwinding-assertions")

        # Flags de propriedades
        flags_set = set()
        for prop in properties:
            flag = self._PROPERTY_FLAGS.get(prop)
            if flag and flag not in flags_set:
                cmd.extend(flag.split())
                flags_set.add(flag)

        # Output legível por máquina
        cmd.append("--xml-ui")  # Output em XML para parsing
        cmd.append("--no-pretty-names")

        return cmd

    def _instrument_code(
        self,
        code: str,
        properties: List[CBMCPropertyType],
        extra_asserts: Optional[List[Tuple[str, str]]] = None,
    ) -> str:
        """Adiciona CPROVER asserts ao código."""
        preamble = """
/* Quimera CBMC Instrumentation */
#ifdef __CPROVER
#include <assert.h>
#define QUIMERA_ASSERT(cond) __CPROVER_assert(cond, #cond)
#endif
"""
        code = preamble + "\n" + code

        # Adiciona asserts extras no final da função
        if extra_asserts:
            assert_block = "\n// Quimera Extra Assertions\n"
            for desc, cond in extra_asserts:
                assert_block += (
                    f'__CPROVER_assert({cond}, "Quimera: {desc}");\n'
                )
            # Insere antes do último }
            last_brace = code.rfind("}")
            if last_brace > 0:
                code = code[:last_brace] + assert_block + code[last_brace:]

        # Para array-bounds, adiciona __CPROVER_assert em acessos de array
        if CBMCPropertyType.ARRAY_BOUNDS in properties:
            code = self._add_bounds_asserts(code)

        return code

    def _add_bounds_asserts(self, code: str) -> str:
        """Adiciona asserts de bounds em acessos de array."""
        # Padrão: arr[i] → adiciona assert(i >= 0 && i < sizeof(arr))
        # Simplificado: apenas adiciona asserts em acessos de array visíveis
        lines = code.splitlines()
        result_lines = []
        for line in lines:
            # Detecta array[index]
            match = re.search(r'(\w+)\[(\w+)\]', line)
            if match:
                arr, idx = match.group(1), match.group(2)
                # Não adiciona se já tiver assert
                if f"__CPROVER_assert" not in line:
                    indent = line[:len(line) - len(line.lstrip())]
                    result_lines.append(
                        f'{indent}__CPROVER_assert({idx} >= 0 && {idx} < (int)sizeof({arr}), '
                        f'"Quimera: array bounds ({arr}[{idx}])");'
                    )
            result_lines.append(line)
        return "\n".join(result_lines)

    def _parse_output(self, tool: str, output: str, unwind: int) -> CBMCAnalysisResult:
        """Parseia output do CBMC/ESBMC."""
        total = 0
        passed = 0
        failed = 0
        properties_list = []

        # CBMC XML output
        if "VERIFICATION SUCCESSFUL" in output:
            status = CBMCStatus.SUCCESS
        elif "VERIFICATION FAILED" in output:
            status = CBMCStatus.FAILURE
        else:
            # Tentar extrair contagem do texto
            passed_match = re.search(r'(\d+) of (\d+) passed', output)
            if passed_match:
                passed = int(passed_match.group(1))
                total = int(passed_match.group(2))
                failed = total - passed
                status = CBMCStatus.SUCCESS if failed == 0 else CBMCStatus.FAILURE
            else:
                status = CBMCStatus.UNKNOWN

        # Extrair propriedades individuais
        for match in re.finditer(
            r'\[(.+?)\]\s+(.+?)\s*:\s*(SUCCESS|FAILURE)',
            output,
            re.MULTILINE
        ):
            prop_id = match.group(1)
            desc = match.group(2)
            prop_status = match.group(3)
            line_match = re.search(r'line (\d+)', output[match.start():match.start()+200])
            line_num = int(line_match.group(1)) if line_match else 0

            properties_list.append(CBMCPropertyResult(
                property_id=prop_id.strip(),
                description=desc.strip(),
                status=prop_status.strip(),
                source_line=line_num,
            ))

        if properties_list:
            total = len(properties_list)
            passed = sum(1 for p in properties_list if p.status == "SUCCESS")
            failed = total - passed

        return CBMCAnalysisResult(
            tool=tool,
            status=status,
            total_properties=total,
            passed_properties=passed,
            failed_properties=failed,
            properties=properties_list,
            unwind_bound=unwind,
            raw_output=output[:5000],  # Truncar output enorme
        )

    def is_available(self) -> bool:
        """Verifica se pelo menos uma ferramenta está disponível."""
        return bool(self._cbmc_path or self._esbmc_path)

    def get_tool_info(self) -> Dict[str, Any]:
        """Retorna informações sobre as ferramentas instaladas."""
        info = {
            "cbmc_available": bool(self._cbmc_path),
            "cbmc_path": self._cbmc_path,
            "esbmc_available": bool(self._esbmc_path),
            "esbmc_path": self._esbmc_path,
            "preferred_tool": self.preferred_tool,
            "default_unwind": self.default_unwind,
        }
        # Tentar obter versão
        if self._cbmc_path:
            try:
                proc = subprocess.run(
                    [self._cbmc_path, "--version"],
                    capture_output=True, text=True, timeout=5
                )
                info["cbmc_version"] = proc.stdout.strip().split("\n")[0]
            except Exception:
                info["cbmc_version"] = "unknown"
        return info
