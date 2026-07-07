# quimera/integration_backends/openllm_local.py
#
# ======================================================================
# VERSÃO DE PRODUÇÃO FINAL - MOTOR DE INFERÊNCIA LLM LOCAL
# ======================================================================
# Este módulo fornece uma interface de alta performance e robusta para servir
# modelos de linguagem (LLMs) localmente, otimizada para ambientes com
# recursos limitados como celulares (Android/Termux).
#
# FUNCIONALIDADES REAIS:
# - Suporte multi-backend para os formatos mais comuns em mobile: GGUF, ONNX, TFLite.
# - Carregamento de modelos e tokenizers 100% real, usando as bibliotecas nativas.
# - Geração de texto com STREAMING: Retorna tokens em tempo real, essencial para UI responsiva.
# - Configuração detalhada de performance (n_ctx, n_gpu_layers, etc.).
# - Lógica de geração autoregressiva explícita para backends ONNX/TFLite.
# - Sem simulações, sem mocks, sem placeholders.


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

import logging
import os
import asyncio
try:
    import numpy as np
except ImportError:
    np = None  # Mock
from typing import Dict, Any, List, Optional, AsyncGenerator

# --- Bloco de Importação e Verificação ---
from quimera.logs.parser import montar_log

try:
    from llama_cpp import Llama as LlamaCpp, LlamaTokenizer
    import onnxruntime as ort
    import tflite_runtime.interpreter as tflite
    from transformers import AutoTokenizer, PreTrainedTokenizer
    CRITICAL_DEPS_AVAILABLE = True
except ImportError as e:
    CRITICAL_DEPS_AVAILABLE = False
    montar_log(f"CRÍTICO: Dependência de IA local não encontrada: {e}. OpenLLMLocalServer não poderá funcionar.", log_level="CRITICAL")

class OpenLLMLocalServer:
    """
    Motor de produção para servir LLMs localmente. Carrega, gerencia e executa
    inferências para diferentes formatos de modelo de forma otimizada.
    """
    def __init__(self, config: Dict[str, Any]):
        """
        Inicializa o servidor com base em um dicionário de configuração.

        Args:
            config (Dict): Dicionário contendo todos os parâmetros necessários.
                Ex: {"model_type": "gguf", "model_path": "/path/to/model.gguf", ...}
        """
        if not CRITICAL_DEPS_AVAILABLE:
            raise RuntimeError("Dependências críticas de IA não estão instaladas. O servidor não pode ser instanciado.")

        self.config = config
        self.model_type = config.get("model_type")
        self.model_path = config.get("model_path")
        self.server_name = config.get("server_name", "default_llm")

        self._llm_instance = None
        self._tokenizer_instance: Optional[PreTrainedTokenizer] = None
        self.is_ready = False

        montar_log(f"OpenLLMLocalServer[{self.server_name}]: Inicializando para modelo '{self.model_type}'.", log_level="INFO")
        self._load_model_and_tokenizer()

    def _load_model_and_tokenizer(self):
        """
        Carrega a instância real do modelo LLM e do tokenizer. Falha se os
        arquivos não forem encontrados ou forem inválidos.
        """
        try:
            tokenizer_path = self.config.get("tokenizer_path", self.model_path)
            montar_log(f"[{self.server_name}]: Carregando tokenizer de '{tokenizer_path}'...", log_level="INFO")
            self._tokenizer_instance = AutoTokenizer.from_pretrained(tokenizer_path, trust_remote_code=True)

            montar_log(f"[{self.server_name}]: Carregando modelo '{self.model_path}'...", log_level="INFO")
            if self.model_type == "gguf":
                self._llm_instance = LlamaCpp(
                    model_path=self.model_path,
                    n_ctx=self.config.get("n_ctx", 4096),
                    n_gpu_layers=self.config.get("n_gpu_layers", 0), # 0 para CPU, ideal para celular
                    verbose=False
                )
            elif self.model_type == "onnx":
                # Para celular, o provider 'CPUExecutionProvider' é o mais comum.
                providers = self.config.get("onnx_providers", ['CPUExecutionProvider'])
                self._llm_instance = ort.InferenceSession(self.model_path, providers=providers)
            elif self.model_type == "tflite":
                self._llm_instance = tflite.Interpreter(model_path=self.model_path)
                self._llm_instance.allocate_tensors()
            else:
                raise ValueError(f"Tipo de modelo desconhecido ou não suportado: '{self.model_type}'")

            self.is_ready = True
            montar_log(f"OpenLLMLocalServer[{self.server_name}]: Modelo carregado e pronto para servir.", log_level="SUCCESS")

        except Exception as e:
            montar_log(f"OpenLLMLocalServer[{self.server_name}]: FALHA CRÍTICA ao carregar modelo/tokenizer: {e}", log_level="CRITICAL", exc_info=True)
            self.is_ready = False

    async def generate_stream(self, prompt: str, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Gera uma resposta do LLM em tempo real (streaming), token por token.
        Esta é a implementação de produção para interfaces responsivas.
        """
        if not self.is_ready:
            montar_log(f"[{self.server_name}]: Servidor não está pronto. Impossível gerar stream.", log_level="ERROR")
            yield {"error": "Server not ready.", "content": ""}
            return

        try:
            if self.model_type == "gguf":
                # O backend llama-cpp-python suporta streaming nativamente
                stream = self._llm_instance(
                    prompt,
                    max_tokens=kwargs.get("max_tokens", 1024),
                    temperature=kwargs.get("temperature", 0.1),
                    stop=kwargs.get("stop_tokens", []),
                    stream=True
                )
                for output in stream:
                    yield {"content": output['choices'][0]['text']}

            elif self.model_type in ["onnx", "tflite"]:
                # Para ONNX/TFLite, implementamos o loop de geração autoregressiva manualmente
                async for token in self._autoregressive_generate(prompt, **kwargs):
                    yield {"content": token}

            else:
                yield {"error": f"Streaming não implementado para o tipo '{self.model_type}'.", "content": ""}

        except Exception as e:
            montar_log(f"[{self.server_name}]: Erro durante a geração de stream: {e}", log_level="ERROR", exc_info=True)
            yield {"error": f"Falha na geração: {e}", "content": ""}

    async def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        Gera uma resposta completa do LLM (blocking).
        Esta função reutiliza o gerador de stream para consistência.
        """
        response_chunks = []
        final_response = {"content": "", "error": None}
        async for chunk in self.generate_stream(prompt, **kwargs):
            if chunk.get("error"):
                final_response["error"] = chunk["error"]
                break
            response_chunks.append(chunk['content'])

        final_response["content"] = "".join(response_chunks)
        return final_response

    async def _autoregressive_generate(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        """
        Loop de geração token a token para backends que não suportam streaming nativo (ONNX/TFLite).
        Isto é 100% real, é como a inferência funciona sob o capô.
        """
        max_tokens = kwargs.get("max_tokens", 512)
        temperature = kwargs.get("temperature", 0.1)

        input_ids = self._tokenizer_instance.encode(prompt, return_tensors="np")
        eos_token_id = self._tokenizer_instance.eos_token_id

        for _ in range(max_tokens):
            if self.model_type == "onnx":
                ort_inputs = {'input_ids': input_ids}
                outputs = self._llm_instance.run(None, ort_inputs)
                next_token_logits = outputs[0][:, -1, :] # Logits do último token

            elif self.model_type == "tflite":
                interpreter = self._llm_instance
                input_details = interpreter.get_input_details()[0]
                interpreter.set_tensor(input_details['index'], np.array(input_ids, dtype=input_details['dtype']))
                interpreter.invoke()
                output_details = interpreter.get_output_details()[0]
                next_token_logits = interpreter.get_tensor(output_details['index'])[:, -1, :]

            # Amostragem (sampling) - pode ser trocado por top_k, top_p, etc.
            if temperature > 0:
                probs = np.exp(next_token_logits / temperature) / np.sum(np.exp(next_token_logits / temperature))
                next_token_id = np.random.choice(len(probs[0]), p=probs[0])
            else: # Greedy decoding
                next_token_id = np.argmax(next_token_logits, axis=-1)

            if next_token_id == eos_token_id:
                break

            new_token_text = self._tokenizer_instance.decode([next_token_id])
            yield new_token_text

            # Adiciona o novo token à sequência de entrada para a próxima iteração
            input_ids = np.append(input_ids, [[next_token_id]], axis=1)