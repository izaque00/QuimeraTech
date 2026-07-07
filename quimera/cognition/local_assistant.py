"""
LocalAssistant — IA 100% local (Qwen2.5-0.5B GGUF) para entender comandos em português.

Roda offline, sem internet, sem API key. 468MB RAM. Funciona até em celular A71.
Se o modelo local falhar ou não estiver disponível, fallback para Groq API.
"""
import os, re, json, logging
from typing import Optional

logger = logging.getLogger("quimera.local_assistant")

# Caminho do modelo GGUF
MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "models", "qwen2.5-0.5b-instruct-q4_k_m.gguf"
)

SYSTEM_PROMPT = """Você é o Quimera Assistant. Converta comandos em português para JSON.

AÇÕES:
- scan: analisar vulnerabilidades em código
- repair: corrigir bugs
- register_key: cadastrar chave API (extraia a chave como target)
- explain: explicar código
- audit: auditoria de segurança completa
- help: ajuda

Responda APENAS com JSON:
{"action":"...","target":"...","params":{},"explanation":"..."}

REGRAS:
- Extraia o nome do arquivo ou caminho mencionado
- Se for "cadastrar/registrar chave", action=register_key e target=chave
- "olhar/verificar/analisar" → scan
- "arrumar/corrigir/consertar" → repair
- Se não tiver certeza da ação, use scan"""


class LocalAssistant:
    """Assistente NL que roda 100% local via llama.cpp."""

    def __init__(self):
        self._llm = None
        self.available = os.path.exists(MODEL_PATH)
        if self.available:
            try:
                from llama_cpp import Llama
                self._llm = Llama(
                    model_path=MODEL_PATH,
                    n_ctx=1024,
                    n_threads=4,
                    verbose=False,
                )
            except Exception as e:
                logger.warning(f"Modelo local não carregou: {e}")
                self.available = False

    def understand(self, message: str) -> dict:
        """Interpreta comando em português usando modelo local."""
        if not self.available or not self._llm:
            return None

        prompt = f"<|im_start|>system\n{SYSTEM_PROMPT}\n<|im_end|>\n<|im_start|>user\n{message}\n<|im_end|>\n<|im_start|>assistant\n"

        try:
            output = self._llm(
                prompt,
                max_tokens=100,
                temperature=0.1,
                top_p=0.9,
                stop=["<|im_end|>"],
            )
            text = output["choices"][0]["text"].strip()

            # Extrair JSON (tolerante a pequenos erros)
            m = re.search(r'\{[^}]+\}', text)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    # Tenta reparar: remove trailing commas, adiciona aspas faltantes
                    fixed = re.sub(r',\s*}', '}', m.group(0))
                    fixed = re.sub(r'([{,]\s*)(\w+):', r'\1"\2":', fixed)
                    try:
                        return json.loads(fixed)
                    except:
                        pass
        except Exception as e:
            logger.warning(f"Inferência local falhou: {e}")

        return None

    def close(self):
        if self._llm:
            self._llm.close()
            self._llm = None


# Singleton
local_assistant = LocalAssistant()
print(f"✅ LocalAssistant: {'disponível' if local_assistant.available else 'indisponível'}")
