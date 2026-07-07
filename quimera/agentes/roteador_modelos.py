# quimera/agentes/roteador_modelos.py

import sys
import os
import logging
import json
from quimera.utils.rate_limiter import TokenBucket
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
import asyncio

# --- Importações de Clientes LangChain Reais ---
try:
    from langchain_community.chat_models import ChatOpenAI
except ImportError:
    ChatOpenAI = None  # ChatOpenAI não disponível
from langchain_mistralai.chat_models import ChatMistralAI
try:
    from langchain_groq import ChatGroq
except ImportError:
    ChatGroq = None  # ChatGroq não disponível
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    ChatGoogleGenerativeAI = None  # ChatGoogleGenerativeAI não disponível
try:
    from langchain_cohere import ChatCohere
except ImportError:
    ChatCohere = None  # ChatCohere não disponível
try:
    from langchain_cloudflare import ChatCloudflareWorkersAI
except ImportError:
    ChatCloudflareWorkersAI = None  # ChatCloudflareWorkersAI não disponível
from langchain_together.chat_models import ChatTogether

# --- Importação da SDK da Cerebras (Wrapper) ---
try:
    from cerebras.cloud.sdk import Cerebras, APIError as CerebrasAPIError
    CEREBRAS_SDK_AVAILABLE = True
except ImportError:
    CEREBRAS_SDK_AVAILABLE = False
    logging.getLogger(__name__).warning("SDK da Cerebras não encontrada. Modelos Cerebras não estarão disponíveis.")

from quimera.core.local_model_manager import LocalModelManager
from quimera.logs.parser import montar_log
from quimera.utils.resilience import CircuitBreakerRegistry

logger = logging.getLogger(__name__)

# --- Wrapper para a SDK da Cerebras para compatibilidade com LangChain ---
class CerebrasWrapper:
    """Wrapper para a SDK da Cerebras para torná-la compatível com a interface ainvoke."""
    def __init__(self, api_key: str, model_name: str):
        self.model = model_name
        self.api_key = api_key
        if not CEREBRAS_SDK_AVAILABLE:
            raise RuntimeError("SDK da Cerebras não disponível, impossível criar o wrapper.")
        try:
            self.client = Cerebras(api_key=api_key)
        except Exception as e:
            raise RuntimeError(f"Falha na inicialização do cliente Cerebras para {model_name}: {e}")

    async def ainvoke(self, prompt: str, **kwargs):
        """Implementa a chamada assíncrona para a API da Cerebras."""
        messages = [{"role": "user", "content": prompt}]
        max_tokens = kwargs.get("max_tokens", 2048)
        temperature = kwargs.get("temperature", 0.2)
        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                messages=messages,
                model=self.model,
                stream=False,
                max_tokens=max_tokens,
                temperature=temperature
            )
            full_content = response.choices[0].message.content
            return type('AIMessage', (object,), {'content': full_content, 'response_metadata': {'token_usage': {}}})()
        except CerebrasAPIError as e:
            logger.error(f"Erro de API da Cerebras ({self.model}): {e.status_code} - {e.message}")
            raise e
        except Exception as e:
            logger.error(f"Erro inesperado no CerebrasWrapper ({self.model}): {e}")
            raise e

class RoteadorModelos:
    """
    Classe central para gerenciar, selecionar e instanciar clientes para LLMs,
    implementando Circuit Breaker, controle de taxa e seleção ponderada por custo.
    """
    DEFAULT_CONFIG_PATH = Path("quimera/agentes/agentes_config.json")
    COOLDOWN_MINUTES = 5

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.provedores_ativos, self.provider_keys = self._verificar_provedores_ativos()
        self.AGENTES_DISPONIVEIS = self._carregar_configuracao_agentes()

        self.local_manager = LocalModelManager()

        self.key_counters = {provider: 0 for provider in self.provider_keys}

        # Circuit Breaker unificado via registry
        self._circuit_registry = CircuitBreakerRegistry()
        for p in self.provedores_ativos:
            self._circuit_registry.get_or_create(
                name=f"provedor_{p}",
                failure_threshold=3,
                cooldown_seconds=self.COOLDOWN_MINUTES * 60,
            )

        # Limites de API para controle de taxa (requisições por minuto, tokens por minuto)
        self.provider_limits = {
            "mistral": {"rpm": 500, "tpm": 500000}, "cerebras": {"rpm": 30, "tpm": 60000},
            "together": {"rpm": 60, "tpm": 100000}, "groq": {"rpm": 30, "tpm": 14000},
            "cohere": {"rpm": 100, "tpm": 100000}, "cloudflare": {"rpm": 1000, "tpm": 300000},
            "openai": {"rpm": 500, "tpm": 150000}, "openrouter": {"rpm": 200, "tpm": 400000},
            "gemini": {"rpm": 60, "tpm": 250000}, "fireworks": {"rpm": 60, "tpm": 250000},
        }
        self.provider_usage = {p: {"requests": 0, "tokens": 0, "timestamp": time.time()} for p in self.provider_limits}

        montar_log(f"Provedores de LLM com chaves de API ativas: {list(self.provedores_ativos.keys())}", "INFO")
        montar_log(f"RoteadorModelos carregado com {len(self.AGENTES_DISPONIVEIS)} agentes.", "INFO")

    def _verificar_provedores_ativos(self) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
        """Verifica variáveis de ambiente para encontrar todas as chaves de API disponíveis."""
        mapeamento = {
            "groq": "GROQ_API_KEY", "openrouter": "OPENROUTER_API_KEY", "gemini": "GOOGLE_API_KEY",
            "fireworks": "FIREWORKS_API_KEY", "cohere": "COHERE_API_KEY", "cloudflare": "CLOUDFLARE_API_TOKEN",
            "openai": "OPENAI_API_KEY", "mistral": "MISTRAL_API_KEY", "cerebras": "CEREBRAS_API_KEY",
            "together": "TOGETHER_API_KEY"
        }
        provedores_ativos = {}
        provider_keys = {prov: [] for prov in mapeamento}

        for var, valor in os.environ.items():
            if not valor: continue
            for prov, prefixo in mapeamento.items():
                if var.startswith(prefixo):
                    provedores_ativos[prov] = prefixo
                    provider_keys[prov].append(valor)

        for prov, keys in provider_keys.items():
            if keys:
                montar_log(f"Encontradas {len(keys)} chave(s) para o provedor '{prov}'.", "DEBUG")
        return provedores_ativos, provider_keys

    def _obter_cliente_llm(self, provedor: str, nome_modelo: str) -> Optional[Any]:
        self._llm_rate_limiter.acquire()  # Rate limiting
        """Instancia um cliente de LLM, fazendo round-robin entre as chaves disponíveis."""
        if provedor == "local":
            return self.local_manager.get_client_for_task(nome_modelo)
        if provedor not in self.provedores_ativos: return None

        keys = self.provider_keys.get(provedor)
        if not keys: return None

        # Round-robin de chaves
        key_index = self.key_counters.get(provedor, 0)
        api_key = keys[key_index]
        self.key_counters[provedor] = (key_index + 1) % len(keys)

        params = {"temperature": 0.2, "max_retries": 1}
        try:
            if provedor == "openai":
                return ChatOpenAI(model=nome_modelo, api_key=api_key, **params) if ChatOpenAI is not None else None
            if provedor == "mistral": return ChatMistralAI(model=nome_modelo, api_key=api_key, **params)
            if provedor == "groq": return ChatGroq(model_name=nome_modelo, api_key=api_key, **params)
            if provedor == "openrouter":
                return ChatOpenAI(model=nome_modelo, openai_api_key=api_key, base_url="https://openrouter.ai/api/v1", **params) if ChatOpenAI is not None else None
            if provedor == "gemini": return ChatGoogleGenerativeAI(model=nome_modelo, google_api_key=api_key, convert_system_message_to_human=True, **params)
            if provedor == "fireworks":
                return ChatOpenAI(model=nome_modelo, openai_api_key=api_key, base_url="https://api.fireworks.ai/inference/v1", **params) if ChatOpenAI is not None else None
            if provedor == "cohere": return ChatCohere(model=nome_modelo, cohere_api_key=api_key, **params)
            if provedor == "cloudflare":
                account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
                if not account_id: return None
                return ChatCloudflareWorkersAI(model=nome_modelo, cloudflare_api_token=api_key, account_id=account_id, **params)
            if provedor == "cerebras": return CerebrasWrapper(api_key=api_key, model_name=nome_modelo)
            if provedor == "together": return ChatTogether(model=nome_modelo, api_key=api_key, **params)
        except Exception as e:
            logger.error(f"Erro ao instanciar cliente para '{nome_modelo}' do '{provedor}': {e}", exc_info=True)
            self.reportar_falha_provedor(provedor)
            return None
        return None

    def reportar_falha_provedor(self, nome_provedor: str):
        """Abre o circuito para um provedor que falhou usando o CircuitBreaker unificado."""
        breaker = self._circuit_registry.get(f"provedor_{nome_provedor}")
        if breaker:
            breaker.record_failure()
            montar_log(f"CIRCUIT BREAKER ACIONADO para '{nome_provedor}'.", "CRITICAL")

    def _is_provider_operational(self, nome_provedor: str) -> bool:
        """Verifica se um provedor está ativo e não em cooldown."""
        breaker = self._circuit_registry.get(f"provedor_{nome_provedor}")
        if breaker:
            return breaker.is_operational
        # Fallback para provedores sem circuit breaker registrado
        return nome_provedor in self.provedores_ativos

    def _carregar_configuracao_agentes(self) -> Dict[str, Dict[str, Any]]:
        if not self.config_path.exists(): raise FileNotFoundError(f"Arquivo de configuração de agentes '{self.config_path}' não encontrado.")
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        return {**config_data.get("base_agentes", {}), **config_data.get("agentes_custom", {})}

    def obter_nomes_modelos_para_habilidade(self, habilidade_requerida: str) -> List[str]:
        return [
            nome for nome, config in self.AGENTES_DISPONIVEIS.items()
            if habilidade_requerida in config.get("habilidades", []) and config.get('ativa', False)
        ]

    def selecionar_agentes_para_tarefa(self, habilidade_requerida: str, quantidade: int = 1, nivel_de_investimento: str = "gratuito") -> List[Dict[str, Any]]:
        """Seleciona os melhores agentes operacionais para uma tarefa, considerando habilidade, prioridade, custo e uso atual da API."""
        niveis_custo = {"local":-1, "gratuito": 0, "gratuito_limitado": 1, "baixo": 2, "medio": 3, "alto": 4, "extremo": 5}
        nivel_max_investimento = niveis_custo.get(nivel_de_investimento, 0)

        candidatos = []
        for nome, config in self.AGENTES_DISPONIVEIS.items():
            provedor = config.get("provedor", "desconhecido")
            custo_map = niveis_custo.get(config.get("custo"), 99)

            if (habilidade_requerida in config.get("habilidades", []) and config.get('ativa', False) and
                (provedor == "local" or self._is_provider_operational(provedor)) and
                custo_map <= nivel_max_investimento):

                score_uso = 1.0
                if provedor in self.provider_limits:
                    uso = self.provider_usage[provedor]
                    if time.time() - uso["timestamp"] > 60:
                        uso["requests"] = 0
                        uso["tokens"] = 0
                        uso["timestamp"] = time.time()

                    uso_rpm = uso["requests"] / self.provider_limits[provedor]["rpm"]
                    score_uso = max(0.01, 1.0 - uso_rpm) # Penaliza agentes de APIs quase no limite

                score_final = config.get("prioridade", 0) * score_uso
                candidatos.append({"nome": nome, "provedor": provedor, "score": score_final})

        if not candidatos: return []

        candidatos_ordenados = sorted(candidatos, key=lambda x: x["score"], reverse=True)

        agentes_selecionados = []
        for candidato in candidatos_ordenados:
            if len(agentes_selecionados) >= quantidade: break
            cliente = self._obter_cliente_llm(candidato["provedor"], candidato["nome"])
            if cliente:
                agentes_selecionados.append({"nome": candidato["nome"], "cliente_llm": cliente, "provedor": candidato["provedor"]})

        if agentes_selecionados:
            montar_log(f"Agentes selecionados para '{habilidade_requerida}': {[a['nome'] for a in agentes_selecionados]}", "INFO")
        else:
            montar_log(f"Não foi possível instanciar nenhum cliente funcional para '{habilidade_requerida}'.", "ERROR")

        return agentes_selecionados