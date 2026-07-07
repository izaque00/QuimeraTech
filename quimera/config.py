# quimera/config.py

import os
import tempfile

"""
Este arquivo centraliza todas as configurações e parâmetros globais para o projeto Quimera.
Ele serve como a única fonte de verdade para configurações, garantindo consistência e
facilitando a manutenção e o ajuste do comportamento do sistema.
"""

# --- Configurações do Ambiente ---
# Define a URL do banco de dados. Pode ser sobrescrita pela variável de ambiente "DATABASE_URL".
# O padrão é um arquivo SQLite local na raiz do projeto.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./quimera_history.db")

# Configurações de conexão para o Redis, usado pelo QuadroNegro.
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

# Caminho para a raiz do código-fonte do kernel.
# Geralmente é definido dinamicamente pelo orquestrador, mas pode ser fixado aqui para testes.
KERNEL_ROOT = os.getenv("KERNEL_ROOT")


# --- Parâmetros da Missão de Reparo ---
# Número máximo de ciclos de tentativa (geração -> síntese -> avaliação) que o orquestrador executará.
MAX_CICLOS_REPARO = 3

# Score mínimo (de 0.0 a 1.0) que um patch deve atingir na fase de avaliação
# para ser considerado "bom o suficiente" para uma tentativa de compilação.
MIN_SCORE_PARA_APLICACAO = 0.75

# Limiar de drift (dissimilaridade vetorial) para o Agente Evolutivo.
# Se o drift de uma nova versão for menor que este valor, a evolução é considerada segura.
EVOLUTOR_DRIFT_THRESHOLD_SEGURO = 0.18

# Limiar de drift para o Agente de Fallback.
# Se o drift de um arquivo exceder este valor, um rollback de emergência é acionado.
FALLBACK_DRIFT_CRITICO = 0.23


# --- Configurações dos Agentes e LLMs ---
# Parâmetros padrão para chamadas aos modelos de linguagem.
# Podem ser sobrescritos por agentes específicos se necessário.
LLM_DEFAULT_TEMPERATURE = 0.2  # Baixa temperatura para respostas mais determinísticas e técnicas.
LLM_DEFAULT_MAX_TOKENS = 2048   # Aumentado para permitir patches mais longos e análises detalhadas.


# --- Nomes de Arquivos e Pastas Padrão ---
# Nome do subdiretório para os artefatos de build do kernel.
QUIMERA_BUILD_DIR_NAME = "quimera_build"

# Prefixo para os arquivos de patch temporários criados durante a execução.
TEMP_PATCH_FILE_PREFIX = "temp_quimera_patch"

# Caminho completo para o diretório de backup do estado inicial do kernel.
INITIAL_KERNEL_BACKUP_DIR = os.environ.get("QUIMERA_BACKUP_DIR", os.path.join(tempfile.gettempdir() if "tempfile" in dir() else "/tmp", "quimera_kernel_initial_sane_state"))


# --- Chaves de Artefatos do Quadro Negro ---
# Usar constantes para chaves evita erros de digitação e centraliza os nomes.
LOG_COMPILACAO_ERRO_KEY = "Log_Compilacao_Erro"
ANALISE_CAUSA_RAIZ_KEY = "Analise_Tecnica_Causa_Raiz"
SOLUCAO_BRUTA_PREFIX = "Solucao_Bruta"
SOLUCAO_SINTETIZADA_KEY = "Solucao_Sintetizada"
MISSAO_TECNICA_KEY = "Missao_Tecnica"
PATCH_VENCEDOR_FINAL_KEY = "Patch_Vencedor_Final"
INITIAL_BACKUP_PATH_KEY = "Initial_Kernel_Backup_Path"