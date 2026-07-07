# quimera/agentes/agente_configurador.py
import sys
import logging
import os
import shutil
import asyncio
import subprocess
import re
from pathlib import Path
from typing import Dict, Any, Optional, List

from quimera.quadro_negro import QuadroNegro
from quimera.ferramentas.device_scanner import DeviceScanner, DeviceConnectionError
from quimera.kernel.gestor import GestorKernel # Importado para type hinting, não usado na lógica direta
from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)

class AgenteConfiguradorDeKernel:
    """
    Agente especialista em analisar um dispositivo de destino, extrair sua
    configuração de kernel e aplicar uma configuração enriquecida e validada
    ao ambiente de compilação. Interage com o usuário em caso de ambiguidade.
    """

    def __init__(self, quadro_negro: QuadroNegro):
        self.quadro_negro = quadro_negro
        self.kernel_root = os.getenv("KERNEL_ROOT")
        if not self.kernel_root:
            raise ValueError("AgenteConfiguradorDeKernel: KERNEL_ROOT não está definido.")

        self.build_dir = os.path.join(self.kernel_root, "quimera_build")
        self.config_dir = Path("quimera/dados/configs_temporarias")
        self.config_dir.mkdir(parents=True, exist_ok=True)

        montar_log("AgenteConfiguradorDeKernel inicializado.", "INFO")

    async def _fase1_escanear_dispositivo(self) -> Optional[str]:
        """Fase 1: Conecta-se ao dispositivo alvo via ADB e extrai a configuração do kernel."""
        montar_log("[Fase 1] Iniciando escaneamento do dispositivo alvo via ADB...", "INFO")
        try:
            device_target = os.getenv("ADB_DEVICE_TARGET")
            scanner = DeviceScanner(device_target=device_target)

            caminho_config_extraido = await asyncio.to_thread(
                scanner.extract_kernel_config,
                output_dir=str(self.config_dir)
            )

            if not caminho_config_extraido:
                montar_log("[Fase 1] Falha ao extrair a configuração do dispositivo.", "WARNING")
                return None

            montar_log(f"[Fase 1] Configuração do dispositivo extraída com sucesso para: {caminho_config_extraido}", "SUCCESS")
            return caminho_config_extraido

        except (RuntimeError, DeviceConnectionError) as e:
            montar_log(f"[Fase 1] Erro de conexão ADB: {e}. O dispositivo pode não estar conectado.", "WARNING")
            return None

    def _descobrir_defconfig_fallback(self) -> Optional[str]:
        """
        Escaneia o diretório de configurações e retorna o caminho do defconfig
        mais provável, interagindo com o usuário se houver ambiguidade.
        """
        configs_dir = os.path.join(self.kernel_root, "arch/arm64/configs")
        if not os.path.isdir(configs_dir):
            montar_log(f"Diretório de configs '{configs_dir}' não encontrado. Impossível descobrir defconfig.", "ERROR")
            return None

        # Palavras-chave priorizadas para busca no nome do arquivo defconfig
        # A ordem importa: 'vendor' e 'qgki' são mais específicos.
        keywords = ["vendor", "qgki", "a71", "sm7150", "defconfig"]
        candidatos = []

        for filename in os.listdir(configs_dir):
            if "_defconfig" in filename:
                score = 0
                fn_lower = filename.lower()
                for i, keyword in enumerate(keywords):
                    if keyword in fn_lower:
                        score += len(keywords) - i # Mais pontos para keywords no início

                # Aceita apenas candidatos que tenham pelo menos uma palavra-chave relevante
                if score > 0:
                    candidatos.append({"path": os.path.join(configs_dir, filename), "score": score})

        if not candidatos:
            montar_log(f"Nenhum arquivo defconfig com palavras-chave relevantes encontrado em '{configs_dir}'.", "WARNING")
            return None

        # Ordena os candidatos do melhor para o pior score
        candidatos.sort(key=lambda x: x["score"], reverse=True)

        # Lógica de desempate e interação com o usuário
        # Mostra até 5 opções para não sobrecarregar
        if len(candidatos) > 1 and (candidatos[0]["score"] - candidatos[1]["score"] <= 1):
            print("\n--- [QUIMERA] Intervenção Necessária: Múltiplos defconfigs encontrados ---")
            print("Selecione o defconfig base para a compilação ou use o padrão (melhor candidato):")
            for i, cand in enumerate(candidatos[:5]):
                print(f"  {i + 1}: {os.path.basename(cand['path'])} (Score: {cand['score']})")
            print("  0: Usar o melhor candidato automaticamente (default)")

            try:
                escolha = input(f"Sua escolha (0-{min(len(candidatos), 5)}) [padrão: 0]: ")
                indice = int(escolha.strip())
                if 1 <= indice <= min(len(candidatos), 5):
                    montar_log(f"Usuário escolheu defconfig: {os.path.basename(candidatos[indice - 1]['path'])}", "INFO")
                    return candidatos[indice - 1]["path"]
            except ValueError:
                montar_log("Entrada inválida. Usando o melhor candidato automaticamente.", "WARNING")
            except IndexError:
                montar_log("Escolha fora do alcance. Usando o melhor candidato automaticamente.", "WARNING")

        melhor_candidato_path = candidatos[0]["path"]
        montar_log(f"defconfig de fallback descoberto heuristicamente e selecionado: '{os.path.basename(melhor_candidato_path)}'", "INFO")
        return melhor_candidato_path

    def _fase2_enriquecer_configuracao(self, config_base_path: str, configs_adicionais_path: List[str]) -> Optional[str]:
        """Fase 2: Usa a configuração base e a enriche com módulos adicionais."""
        montar_log("[Fase 2] Iniciando enriquecimento de configuração...", "INFO")
        config_final_path = os.path.join(self.build_dir, ".config")

        try:
            # Garante que o diretório de build esteja limpo
            if os.path.exists(self.build_dir): shutil.rmtree(self.build_dir)
            os.makedirs(self.build_dir)

            # Define CROSS_COMPILE e CROSS_COMPILE_COMPAT para os comandos make
            cross_compile = os.getenv('CROSS_COMPILE', 'aarch64-linux-gnu-')
            cross_compile_compat = os.getenv('CROSS_COMPILE_COMPAT', 'arm-linux-gnueabihf-')

            # CÓPIA DO AMBIENTE ATUAL e adição de variáveis para o make
            env_vars = os.environ.copy()
            env_vars['ARCH'] = 'arm64'
            env_vars['CROSS_COMPILE'] = cross_compile
            env_vars['CROSS_COMPILE_COMPAT'] = cross_compile_compat

            make_cmd_base_args = [
                "make", f"O={self.build_dir}" # O argumento -O é para o make
            ]

            # Aplica a configuração base: se for um defconfig, usa 'make defconfig'; se for um .config, copia
            if os.path.basename(config_base_path).endswith("_defconfig"):
                montar_log(f"Aplicando defconfig '{os.path.basename(config_base_path)}'...", "INFO")
                subprocess.run(make_cmd_base_args + [os.path.basename(config_base_path)], cwd=self.kernel_root, check=True, capture_output=True, env=env_vars)
            elif os.path.exists(config_base_path): # Já é um .config
                montar_log(f"Copiando .config base de '{config_base_path}'...", "INFO")
                shutil.copyfile(config_base_path, config_final_path)
            else:
                montar_log(f"Caminho de configuração base inválido ou não encontrado: '{config_base_path}'.", "CRITICAL")
                return None

            # Mescla configurações adicionais (ex: para pentest ou depuração)
            script_config_path = os.path.join(self.kernel_root, "scripts/config")
            if not os.path.exists(script_config_path):
                montar_log(f"Script 'scripts/config' não encontrado em '{script_config_path}'.", "WARNING")
            else:
                for config_file in configs_adicionais_path:
                    if not config_file or not os.path.exists(config_file): continue
                    montar_log(f"Mesclando configurações de: {os.path.basename(config_file)}", "INFO")
                    with open(config_file, 'r') as f:
                        for line in f:
                            match = re.match(r"^\s*(CONFIG_[A-Z0-9_]+)=([ym])", line.strip())
                            if match:
                                config_name, value = match.group(1), match.group(2)
                                action = "--enable" if value == 'y' else "--module"
                                subprocess.run([script_config_path, "--file", config_final_path, action, config_name], check=True, capture_output=True, env=env_vars)

            # Executa make olddefconfig para resolver dependências
            montar_log("Executando 'make olddefconfig' para resolver dependências...", "INFO")
            subprocess.run(make_cmd_base_args + ["olddefconfig"], cwd=self.kernel_root, check=True, capture_output=True, env=env_vars)
            montar_log(f"[Fase 2] Enriquecimento concluído. .config final em '{config_final_path}'.", "SUCCESS")
            return config_final_path
        except Exception as e:
            error_details = e.stderr.decode(errors='ignore') if hasattr(e, 'stderr') else str(e)
            montar_log(f"[Fase 2] Falha durante o enriquecimento da configuração: {error_details}", "ERROR", exc_info=True)
            return None

    async def _fase3_validar_configuracao(self) -> bool:
        """
        Valida a configuração executando 'make modules_prepare'. Este comando
        gera autoconf.h e todos os cabeçalhos necessários, validando o .config.
        """
        montar_log("[Fase 3] Validando .config com 'make modules_prepare'...", "INFO")
        try:
            cross_compile = os.getenv('CROSS_COMPILE', 'aarch64-linux-gnu-')
            # CORREÇÃO APLICADA AQUI: O valor padrão correto para compatibilidade de 32 bits.
            cross_compile_compat = os.getenv('CROSS_COMPILE_COMPAT', 'arm-linux-gnueabihf-')

            env_vars = os.environ.copy()
            env_vars['ARCH'] = 'arm64'
            env_vars['CROSS_COMPILE'] = cross_compile
            env_vars['CROSS_COMPILE_COMPAT'] = cross_compile_compat

            # CORREÇÃO APLICADA AQUI: Aspas adicionadas para robustez
            make_cmd_str = (
                f"make O='{self.build_dir}' ARCH=arm64 "
                f"CROSS_COMPILE='{cross_compile}' "
                f"CROSS_COMPILE_COMPAT='{cross_compile_compat}' "
                "modules_prepare -j$(nproc)"
            )

            process = await asyncio.create_subprocess_shell(
                make_cmd_str,
                cwd=self.kernel_root,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env_vars
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)

            if process.returncode == 0:
                montar_log("[Fase 3] Validação bem-sucedida! 'modules_prepare' concluído.", "SUCCESS")
                return True
            else:
                montar_log("[Fase 3] Validação falhou! 'modules_prepare' retornou erro.", "ERROR")
                montar_log(f"Log de erro da validação:\n{stderr.decode(errors='ignore')[-1500:]}", "DEBUG")
                return False
        except asyncio.TimeoutError:
            montar_log("[Fase 3] Validação excedeu o tempo limite.", "ERROR")
            return False
        except Exception as e:
            montar_log(f"[Fase 3] Erro inesperado durante a validação: {e}", "CRITICAL", exc_info=True)
            return False

    async def executar_missao_configuracao(self) -> bool:
        """Orquestra o fluxo completo de configuração e validação do kernel."""
        montar_log("--- INICIANDO MISSÃO DE CONFIGURAÇÃO DE KERNEL ---", "INFO")

        config_base_path = await self._fase1_escanear_dispositivo()

        if not config_base_path:
            montar_log("Não foi possível extrair .config do dispositivo. Tentando descobrir defconfig de fallback...", "WARNING")
            config_base_path = self._descobrir_defconfig_fallback()

            if not config_base_path:
                montar_log("FALLBACK FALHOU: Nenhum defconfig pôde ser encontrado. Missão de configuração abortada.", "CRITICAL")
                return False

        configs_adicionais = [os.path.join("quimera/dados/configs_adicionais", "pentest.config")]

        caminho_config_final = self._fase2_enriquecer_configuracao(config_base_path, configs_adicionais)
        if not caminho_config_final: return False

        if not await self._fase3_validar_configuracao(): return False

        montar_log("--- MISSÃO DE CONFIGURAÇÃO DE KERNEL CONCLUÍDA COM SUCESSO ---", "SUCCESS")
        self.quadro_negro.publicar_artefato(
            "ConfiguracaoDeKernelOtimizada",
            {"caminho_config_final": caminho_config_final, "status": "Validada e Pronta"},
            autor=self.__class__.__name__
        )
        return True