# quimera/testes/test_apis.py

import requests
import os
import json
import logging
from typing import List

# Configuração do logger para este módulo de teste
logging.basicConfig(level=logging.INFO, format='[API TESTER | %(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# --- Configuração dos Testes de API ---

# Token da Hugging Face. É altamente recomendado usar uma variável de ambiente.
# Para executar, defina a variável: export HF_TOKEN="hf_xxxxxxxx"
HF_API_TOKEN = os.getenv("HF_TOKEN")

# URL do seu Gradio Space (se você estiver testando o app_gradio.py implantado)
# Substitua pela URL real do seu Space.
GRADIO_SPACE_URL = "https://huggingface.co/spaces/Izaque00/Izaqe/api/predict/"

# Lista de modelos gratuitos e populares para testar na API de Inferência da Hugging Face.
# Esta lista pode ser expandida com outros modelos de interesse.
MODELS_TO_TEST_INFERENCE_API = [
    "mistralai/Mistral-7B-Instruct-v0.2",
    "HuggingFaceH4/zephyr-7b-beta",
    "google/gemma-7b-it",
    "meta-llama/Meta-Llama-3-8B-Instruct",
    "bigcode/starcoder2-3b",
    "openchat/openchat-3.5-0106",
]

def testar_api_gradio_space(prompt: str, modelo: str = "phi"):
    """
    Testa a API de um Gradio Space implantado.
    Esta função foi adaptada de 'consulta_ia.py'.

    Args:
        prompt (str): O prompt a ser enviado para o modelo.
        modelo (str): O nome amigável do modelo a ser usado no Gradio Space.
    """
    logger.info(f"Testando Gradio Space em: {GRADIO_SPACE_URL}")
    logger.info(f"  -> Prompt: '{prompt}'")
    logger.info(f"  -> Modelo: '{modelo}'")

    try:
        response = requests.post(
            GRADIO_SPACE_URL,
            json={"data": [prompt, modelo]},
            timeout=60  # Timeout de 60 segundos
        )
        response.raise_for_status()  # Levanta um erro para status HTTP 4xx/5xx

        logger.info(f"Resposta recebida (Status: {response.status_code})")
        print("--- Resposta do Gradio Space ---")
        print(json.dumps(response.json(), indent=2))
        print("---------------------------------")

    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao conectar com a API do Gradio Space: {e}")
    except Exception as e:
        logger.error(f"Ocorreu um erro inesperado: {e}")


def testar_api_inferencia_hf(model_id: str, prompt: str = "Explique o que é a Teoria da Relatividade em 3 frases."):
    """
    Testa um modelo específico usando a API de Inferência da Hugging Face.
    Esta função foi adaptada de 'f.py'.

    Args:
        model_id (str): O identificador completo do modelo (ex: 'mistralai/Mistral-7B-Instruct-v0.2').
        prompt (str): O prompt a ser enviado para o modelo.

    Returns:
        str: O status do teste ('✅ ON', '🕒 EM FILA', '❌ OFF', etc.).
    """
    if not HF_API_TOKEN:
        return "🔒 TOKEN AUSENTE"

    api_url = f"https://api-inference.huggingface.co/models/{model_id}"
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
    payload = {"inputs": prompt}

    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            return "✅ ON"
        elif response.status_code == 503:
            # Modelo está carregando, o que é um bom sinal
            return "🕒 EM FILA (Carregando...)"
        elif response.status_code == 403:
            return "🔒 BLOQUEADO (Acesso restrito)"
        elif response.status_code == 422:
             return "🔄 NECESSITA PROMPT DE CHAT"
        else:
            return f"❌ OFF (Código: {response.status_code})"
    except requests.exceptions.Timeout:
        return "⌛ TIMEOUT"
    except requests.exceptions.RequestException:
        return "🔌 ERRO DE CONEXÃO"


if __name__ == "__main__":
    # --- Teste 1: Consulta ao Gradio Space ---
    logger.info("\n--- INICIANDO TESTE DA API DO GRADIO SPACE ---")
    prompt_gradio = "O que é um kernel monolítico?"
    modelo_gradio = "StarCoder2-3B (Correção)" # Modelo que deve estar no seu app_gradio.py
    testar_api_gradio_space(prompt_gradio, modelo_gradio)

    # --- Teste 2: Verificação de status dos modelos na API de Inferência ---
    logger.info("\n--- INICIANDO TESTE DE STATUS DA API DE INFERÊNCIA HF ---")
    if not HF_API_TOKEN:
        logger.warning("A variável de ambiente 'HF_TOKEN' não está definida.")
        logger.warning("Os testes da API de Inferência serão pulados. Exporte seu token para executar.")
    else:
        for model in MODELS_TO_TEST_INFERENCE_API:
            status = testar_api_inferencia_hf(model_id=model)
            # Imprime o resultado formatado
            print(f"{model:<40} -> {status}")