# quimera/core/local_model_manager.py


# Verificações de dependências adicionadas automaticamente
def verificar_dependencia(nome_modulo, funcionalidade="essa funcionalidade"):
    """Verifica se uma dependência está disponível"""
    try:
        __import__(nome_modulo)
        return True
    except ImportError:
        print(f"⚠️  {nome_modulo} não instalado - {funcionalidade} não disponível")
        return False

import logging
_logger = logging.getLogger(__name__)


def _unavailable_feature(feature_name: str, *args, **kwargs):
    """Loga warning quando funcionalidade não está disponível por falta de dependências."""
    _logger.warning(f"Funcionalidade '{feature_name}' indisponível — dependência não instalada")
    return None

import os
import logging
import json
import requests
try:
    import numpy as np
except ImportError:
    np = None  # Mock
from typing import Any, Dict, Optional, List
from pathlib import Path

# --- Bloco de Importação e Verificação de Dependências Opcionais ---
try:
    from llama_cpp import Llama
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False
    logging.getLogger(__name__).warning("llama-cpp-python não encontrado. Modelos GGUF não estarão disponíveis.")

try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False
    logging.getLogger(__name__).warning("onnxruntime não encontrado. Modelos ONNX não estarão disponíveis.")

try:
    from transformers import AutoTokenizer, PreTrainedTokenizer
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logging.getLogger(__name__).warning("transformers não encontrado. Tokenizers para modelos ONNX não funcionarão.")

logger = logging.getLogger(__name__)

class LocalModelManager:
    """
    Gerencia o ciclo de vida (download, carregamento, acesso) de múltiplos
    modelos de linguagem locais (GGUF, ONNX, etc.).
    Implementado como um Singleton para garantir uma única instância em todo o sistema.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LocalModelManager, cls).__new__(cls)
            cls._instance.config_path = Path("quimera/configs/internal.mobile/config.json")
            cls._instance.config = cls._instance._load_config()
            cls._instance.models_config = cls._instance.config.get("modelos_locais", [])
            cls._instance.loaded_models: Dict[str, Any] = {}
            cls._instance.loaded_tokenizers: Dict[str, Any] = {}
            logger.info("LocalModelManager inicializado como Singleton.")
        return cls._instance

    def _load_config(self) -> Dict[str, Any]:
        """Carrega o arquivo de configuração dos modelos locais."""
        if not self.config_path.exists():
            logger.error(f"Arquivo de configuração de modelos locais não encontrado em '{self.config_path}'.")
            return {}
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _download_model_if_missing(self, model_info: Dict[str, str]):
        """Baixa um modelo se o arquivo não existir localmente."""
        dest_path = Path(model_info["caminho"])
        if dest_path.exists() and dest_path.stat().st_size > 0:
            return

        url = model_info.get("url_fallback")
        if not url:
            logger.warning(f"Modelo '{model_info['nome']}' não encontrado em '{dest_path}' e sem URL de fallback.")
            return

        logger.info(f"Baixando modelo '{model_info['nome']}' de {url}...")
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with requests.get(url, stream=True, timeout=600) as r:
                r.raise_for_status()
                with open(dest_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            logger.info(f"Modelo '{model_info['nome']}' baixado com sucesso.")
        except Exception as e:
            logger.error(f"Falha no download do modelo '{model_info['nome']}': {e}", exc_info=True)

    def _get_tokenizer(self, model_info: Dict[str, str]) -> Optional[Any]:
        """Carrega e cacheia um tokenizer."""
        tokenizer_name = model_info.get("tokenizer_path") or self.config.get("tokenizer_path_padrao")
        if not tokenizer_name:
            logger.error(f"Nenhum tokenizer especificado para o modelo '{model_info['nome']}'.")
            return None

        if tokenizer_name in self.loaded_tokenizers:
            return self.loaded_tokenizers[tokenizer_name]

        if not TRANSFORMERS_AVAILABLE:
            return None

        logger.info(f"Carregando tokenizer '{tokenizer_name}'...")
        try:
            tokenizer = AutoTokenizer.from_pretrained(tokenizer_name, trust_remote_code=True)
            self.loaded_tokenizers[tokenizer_name] = tokenizer
            return tokenizer
        except Exception as e:
            logger.error(f"Falha ao carregar tokenizer '{tokenizer_name}': {e}", exc_info=True)
            return None

    def _load_gguf_model(self, model_info: Dict[str, str]) -> Optional[Any]:
        """Carrega um modelo GGUF."""
        if not LLAMA_CPP_AVAILABLE: return None
        self._download_model_if_missing(model_info)
        model_path = Path(model_info["caminho"])
        if not model_path.exists(): return None
        try:
            logger.info(f"Carregando modelo GGUF '{model_info['nome']}'...")
            llm = Llama(model_path=str(model_path), n_ctx=2048, n_gpu_layers=0, verbose=False)
            logger.info(f"Modelo '{model_info['nome']}' carregado na memória.")
            return llm
        except Exception as e:
            logger.error(f"Erro ao carregar modelo GGUF '{model_info['nome']}': {e}", exc_info=True)
            return None

    def _load_onnx_model(self, model_info: Dict[str, str]) -> Optional[Any]:
        """Carrega um modelo ONNX e seu tokenizer."""
        if not ONNX_AVAILABLE: return None
        self._download_model_if_missing(model_info)
        model_path = Path(model_info["caminho"])
        if not model_path.exists(): return None

        tokenizer = self._get_tokenizer(model_info)
        if not tokenizer: return None

        try:
            logger.info(f"Carregando modelo ONNX '{model_info['nome']}'...")
            session = ort.InferenceSession(str(model_path), providers=['CPUExecutionProvider'])
            logger.info(f"Modelo '{model_info['nome']}' carregado na memória.")
            return {"session": session, "tokenizer": tokenizer}
        except Exception as e:
            logger.error(f"Erro ao carregar modelo ONNX '{model_info['nome']}': {e}", exc_info=True)
            return None

    def get_client_for_task(self, habilidade: str) -> Optional[Any]:
        """
        Encontra e carrega (se ainda não estiver carregado) o primeiro modelo
        local que possui a habilidade especificada.
        """
        for model_info in self.models_config:
            if habilidade in model_info.get("habilidades", []):
                model_name = model_info["nome"]
                if model_name in self.loaded_models:
                    return self.loaded_models[model_name]

                loaded_model = None
                if model_info["tipo"] == "gguf":
                    loaded_model = self._load_gguf_model(model_info)
                elif model_info["tipo"] == "onnx":
                    loaded_model = self._load_onnx_model(model_info)

                if loaded_model:
                    self.loaded_models[model_name] = loaded_model
                    return loaded_model

        logger.debug(f"Nenhum modelo local encontrado para a habilidade '{habilidade}'.")
        return None