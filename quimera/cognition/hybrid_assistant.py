"""
HybridAssistant — IA LOCAL (Qwen 2.5 3B) + Groq API (Llama 3.3 70B) + Orquestrador REAL.

Arquitetura:
  User fala → Local Qwen (rápido, offline) → entende intenção
           → Se falhar: Groq API (inteligente, cloud)
           → Se falhar: heurísticas (fallback)
           → EXECUÇÃO REAL via orquestrador nativo (NUNCA simulada)

Memória persistente via MemoryEngine (LRU cache + histórico de missões).
"""
import os, re, json, sys, urllib.request, urllib.error, logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

logger = logging.getLogger("quimera.hybrid")

# ═══════════════════════════════════════════
# PROVIDERS
# ═══════════════════════════════════════════
PROVIDERS = {
    "groq":       {"prefix": "gsk_",   "env": "GROQ_API_KEY",       "label": "Groq"},
    "openai":     {"prefix": "sk-",    "env": "OPENAI_API_KEY",     "label": "OpenAI"},
    "gemini":     {"prefix": "AIza",   "env": "GEMINI_API_KEY",     "label": "Gemini"},
    "deepseek":   {"prefix": "sk-",    "env": "DEEPSEEK_API_KEY",   "label": "DeepSeek"},
    "anthropic":  {"prefix": "sk-ant-","env": "ANTHROPIC_API_KEY",  "label": "Anthropic"},
    "openrouter": {"prefix": "sk-or-", "env": "OPENROUTER_API_KEY", "label": "OpenRouter"},
}

# ═══════════════════════════════════════════
# NLCommand
# ═══════════════════════════════════════════
@dataclass
class NLCommand:
    action: str
    target: str = ""
    params: Dict = field(default_factory=dict)
    explanation: str = ""

# ═══════════════════════════════════════════
# SYSTEM PROMPT — identidade Quimera
# ═══════════════════════════════════════════
QUIMERA_IDENTITY = """VOCE E O QUIMERA. Sistema Quimera MarkX v5.4 em Termux Android. Voce COMANDO o motor.

FERRAMENTAS REAIS (voce EXECUTA, nao simula):
🔧 pipeline — Pipeline H1-H6 reparo autonomo (orquestrador nativo)
🛡️ audit — Aegis Security Core (analise de vulnerabilidades real)
📊 health — Diagnostico do orquestrador (get_system_status)
🔍 explain — Deep code review com AST parsing
🔎 search — Busca arquivos por nome no projeto
🔑 register_key — Cadastra chaves API

REGRAS:
- "corrige/arruma/repara X" → action=pipeline, target=X
- "audita/seguranca X" → action=audit, target=X
- "como esta/health/sistema" → action=health
- "analisa/explique X" → action=explain, target=X
- "busca/procura X" → action=search, target=X
- "cadastra chave X" → action=register_key
- Nenhuma ferramenta → action=chat
- target = exatamente o que o usuario falou

JSON: {"action":"...","target":"...","params":{},"explanation":"..."}"""

# ═══════════════════════════════════════════
# HybridAssistant
# ═══════════════════════════════════════════
class HybridAssistant:
    """Assistente híbrido: LOCAL primeiro → Groq fallback → heurísticas."""

    def __init__(self):
        # ── Knowledge Base (carrega SEMPRE, independente de modelo) ──
        self._kb = None
        self._kb_prompt = ""
        self._load_knowledge_base()

        # ── Local LLM ──
        self._local = None
        self.local_available = False
        self._init_local()

        # ── Groq API ──
        self.api_key = self._load_key()
        self.base_url = "https://api.groq.com/openai/v1"
        self.model = "llama-3.3-70b-versatile"
        self.groq_available = bool(self.api_key)

        # ── Projeto ──
        self.project_root = "."

        # ── Memória persistente ──
        self._memory = None
        self._init_memory()

        # ── Modo atual ──
        self.mode = "local" if self.local_available else ("groq" if self.groq_available else "heuristic")

    # ═══════════════ LOCAL LLM ═══════════════

    def _init_local(self):
        """Inicializa o modelo local Qwen 2.5 3B."""
        model_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "models", "qwen2.5-3b-instruct-q4_k_m.gguf"
        )
        if not os.path.exists(model_path):
            logger.info("Modelo 3B nao encontrado. Rode: bash setup_model.sh")
            return

        try:
            from llama_cpp import Llama
            self._local = Llama(
                model_path=model_path,
                n_ctx=2048,
                n_threads=6,
                verbose=False,
            )
            self.local_available = True
            logger.info("✅ Modelo local Qwen 2.5 3B carregado")
        except ImportError:
            logger.warning("llama-cpp-python nao instalado. Use: pip install llama-cpp-python")
        except Exception as e:
            logger.warning(f"Modelo local falhou: {e}")

    def _understand_local(self, msg: str) -> Optional[NLCommand]:
        """Interpreta comando usando modelo local."""
        if not self._local: return None

        # Usa system prompt enriquecido com knowledge base
        sp = self._kb_prompt if self._kb_prompt else QUIMERA_IDENTITY
        rag = self._rag_context(msg)
        if rag:
            sp += f"\n\nCONHECIMENTO RELEVANTE DO QUIMERA:\n{rag}"

        prompt = f"<|im_start|>system\n{sp}\n<|im_end|>\n<|im_start|>user\n{msg}\n<|im_end|>\n<|im_start|>assistant\n"
        try:
            output = self._local(prompt, max_tokens=200, temperature=0.1, top_p=0.9, stop=["<|im_end|>"])
            text = output["choices"][0]["text"].strip()
            m = re.search(r'\{[^}]+\}', text)
            if m:
                try: data = json.loads(m.group(0))
                except:
                    fixed = re.sub(r',\s*}', '}', m.group(0))
                    fixed = re.sub(r'([{,]\s*)(\w+):', r'\1"\2":', fixed)
                    try: data = json.loads(fixed)
                    except: return None
                return NLCommand(
                    action=data.get("action", "chat"),
                    target=data.get("target", ""),
                    params=data.get("params", {}),
                    explanation=data.get("explanation", "local")
                )
        except Exception as e:
            logger.warning(f"Local: {e}")
        return None

    # ═══════════════ GROQ API ═══════════════

    def _load_key(self) -> Optional[str]:
        for var in ["GROQ_API_KEY", "OPENAI_API_KEY"]:
            k = os.environ.get(var)
            if k: return k
        for p in [".env", os.path.expanduser("~/.env")]:
            if os.path.exists(p):
                for line in open(p):
                    if "GROQ_API_KEY" in line or "OPENAI_API_KEY" in line:
                        v = line.strip().split("=", 1)[-1].strip().strip('"').strip("'")
                        if v and len(v) > 10: return v
        return None

    def _understand_groq(self, msg: str) -> Optional[NLCommand]:
        """Interpreta comando usando Groq API."""
        if not self.groq_available: return None

        try:
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps({
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": QUIMERA_IDENTITY},
                        {"role": "user", "content": f"{self._rag_context(msg)}\n\nUsuario: {msg}" if self._rag_context(msg) else msg},
                    ],
                    "temperature": 0.1, "max_tokens": 150,
                }).encode(),
                headers={"Authorization": f"Bearer {self.api_key}",
                         "Content-Type": "application/json",
                         "User-Agent": "Quimera/5.4"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            text = data["choices"][0]["message"]["content"].strip()

            m = re.search(r'\{[^}]+\}', text)
            if m:
                try: d = json.loads(m.group(0))
                except: return None
                return NLCommand(
                    action=d.get("action", "chat"),
                    target=d.get("target", ""),
                    params=d.get("params", {}),
                    explanation=d.get("explanation", "groq")
                )
        except Exception as e:
            logger.warning(f"Groq: {e}")
        return None

    # ═══════════════ HEURÍSTICAS ═══════════════

    def _understand_fallback(self, msg: str) -> NLCommand:
        """Fallback heurístico — sem IA, só regex."""
        m = msg.lower().strip()

        # ═══ PERGUNTA TÉCNICA? → chat (RAG vai responder) ═══
        question_starters = ("qual", "como", "oque", "porque", "quem", "onde", "quando",
                            "explique", "descreva", "me diga", "me fale", "se eu",
                            "o que", "pra que", "para que", "existe", "tem como",
                            "eh possivel", "é possivel", "voce pode", "você pode")
        if (m.endswith('?') or m.startswith(question_starters) or
            any(m.startswith(q) for q in question_starters)):
            return NLCommand("chat", msg, explanation="Pergunta → RAG")

        # Chave API
        if any(k in m for k in ["cadastr","registr","chave","api key"]):
            prov, key = self._extract_key(msg)
            return NLCommand("register_key", prov or "groq",
                           {"api_key": key} if key else {},
                           explanation="Chave API")

        # Pipeline/repair
        if any(k in m for k in ["corrig","arrum","consert","repar","pipeline",
                                "testar","teste","executar","execute","roda","rodar"]):
            return NLCommand("pipeline", self._extract_target(m, msg),
                           explanation="Pipeline H1-H6")

        # Audit
        if any(k in m for k in ["audit","seguranc","vulnerab","aegis"]):
            return NLCommand("audit", self._extract_target(m, msg),
                           explanation="Auditoria Aegis")

        # Health
        if any(k in m for k in ["health","diagnost","status","sistema","como ta",
                                "como esta"]):
            return NLCommand("health", ".", explanation="Health check")

        # Search
        if any(k in m for k in ["busca","busque","procur","pesquis","acha",
                                "encontra","cade","onde"]):
            return NLCommand("search", self._extract_target(m, msg),
                           explanation="Busca de arquivos")

        # Explain
        if any(k in m for k in ["analis","expliqu","explique","explique","olhe",
                                "olha","ve","veja","mostra","fale","explica"]):
            return NLCommand("explain", self._extract_target(m, msg),
                           explanation="Analise de codigo")

        # Chat
        return NLCommand("chat", msg, explanation="Conversa")

    def _extract_target(self, msg_lower: str, original: str) -> str:
        """Extrai alvo do comando."""
        # Remove prefixos
        for pfx in ["analise o ","analisa o ","olhe o ","veja o ","mostra o ",
                     "busca por ","procura por ","corrige o ","arruma o ",
                     "audita o ","testa o ","execute o ","roda o ",
                     "me fale sobre ","me explica ","o que e ","o que faz ",
                     "explique ","analise ","analisa ","olhe ","veja ",
                     "busca ","procura ","corrige ","arruma ","audita ",
                     "testa ","execute ","roda "]:
            if original.lower().startswith(pfx):
                return original[len(pfx):].strip()
        # Pega ultima palavra significativa
        words = original.strip().split()
        for w in reversed(words):
            if len(w) > 2 and w.lower() not in ('o','a','os','as','do','da','de',
                'em','no','na','um','uma','que','pra','pro','com','sem','por',
                'sobre','para','me','te','se','nos','voce','aí','la','aqui',
                'isso','disso','nisto','faz','fazer','pode','quero','vamos',
                'testar','teste','rodar','executar','ver','olhar'):
                return w
        return "."

    def _extract_key(self, text: str):
        """Extrai provider e chave API do texto."""
        for prov, info in PROVIDERS.items():
            if prov in text.lower():
                m = re.search(rf'{info["prefix"]}[A-Za-z0-9_-]+', text)
                if m: return prov, m.group(0)
        m = re.search(r'(gsk_|sk-|AIza|sk-ant-|sk-or-)[A-Za-z0-9_-]+', text)
        if m:
            key = m.group(0)
            for prov, info in PROVIDERS.items():
                if key.startswith(info["prefix"]): return prov, key
        return None, None

    # ═══════════════ INTERFACE PÚBLICA ═══════════════

    def understand(self, message: str) -> NLCommand:
        """Interpreta mensagem: local → Groq → heurísticas."""
        # 1. Local (rápido, offline)
        if self.local_available:
            result = self._understand_local(message)
            if result and result.action != "chat":
                self.mode = "local"
                return result

        # 2. Groq API (inteligente, cloud)
        if self.groq_available:
            result = self._understand_groq(message)
            if result:
                self.mode = "groq"
                return result

        # 3. Heurísticas (fallback)
        self.mode = "heuristic"
        return self._understand_fallback(message)

    # ═══════════════ MEMÓRIA ═══════════════

    def _load_knowledge_base(self) -> Optional[Dict]:
        """Carrega base de conhecimento do Quimera."""
        print("   📚 KB...", end=" ", flush=True)
        kb_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "quimera_knowledge.json"
        )
        if not os.path.exists(kb_path):
            # Tenta gerar
            try:
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                from quimera.cognition.knowledge_indexer import QuimeraKnowledgeIndexer
                root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                indexer = QuimeraKnowledgeIndexer(root)
                data = indexer.build()
                # Extrai system prompt
                sp = indexer.generate_system_prompt()
                print(f"✅ gerada")
                return {"data": data, "system_prompt": sp, "indexer": indexer}
            except Exception as e:
                print(f"❌ {e}")
                logger.warning(f"KB generation: {e}")
                return None

        try:
            with open(kb_path) as f:
                data = json.load(f)
            # Reconstrói indexer
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from quimera.cognition.knowledge_indexer import QuimeraKnowledgeIndexer
            root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            indexer = QuimeraKnowledgeIndexer(root)
            indexer.modules = {}  # lazy
            indexer.global_index = data.get("global_index", {})
            sp_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quimera_system_prompt.txt")
            if os.path.exists(sp_path):
                with open(sp_path) as f2:
                    sp = f2.read()
            else:
                sp = ""
            total = len(data.get("modules", {}))
            print(f"✅ {total} modulos")
            return {"data": data, "system_prompt": sp, "indexer": indexer}
        except Exception as e:
            print(f"❌ {e}")
            logger.warning(f"KB load: {e}")
        return None

    def _rag_context(self, query: str) -> str:
        """Busca contexto relevante do Quimera para a query."""
        if not hasattr(self, '_kb') or not self._kb:
            return ""

        # Via indexer
        if self._kb.get("indexer"):
            try:
                result = self._kb["indexer"].generate_rag_context(query, 2500)
                if result: return result
            except: pass

        # Via JSON direto
        data = self._kb.get("data", {})
        if data:
            try:
                words = [w for w in query.lower().split() if len(w) > 2]
                results = []
                gidx = data.get("global_index", {})
                for cls_name, entries in gidx.get("classes", {}).items():
                    if any(w in cls_name.lower() for w in words):
                        for e in entries[:2]:
                            results.append(f"🔵 {e['name']} em {e['module']}: {e.get('doc','')}")
                for fn_name, entries in gidx.get("functions", {}).items():
                    if any(w in fn_name for w in words):
                        for e in entries[:2]:
                            results.append(f"🟢 {e['name']}() em {e['module']}: {e.get('doc','')}")
                for mod_path, info in list(data.get("modules", {}).items())[:5]:
                    if any(w in mod_path.lower().replace('/',' ') for w in words):
                        results.append(f"📁 {mod_path}: {info.get('docstring','')[:100]}")
                if results:
                    return "\n".join(results[:15])
            except: pass

        return ""

    def _init_memory(self):
        """Inicializa memória persistente."""
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from quimera.memory.memory_engine import MemoryEngine
            db_path = os.path.join(self.project_root, "quimera_memory.db")
            self._memory = MemoryEngine(persistence_path=db_path)
            logger.info("✅ Memoria persistente ativada")
        except Exception as e:
            logger.warning(f"Memoria indisponivel: {e}")

    def remember(self, user_msg: str, response: str, action: str = ""):
        """Registra interação na memória."""
        if self._memory:
            try:
                self._memory.record_mission({
                    "timestamp": datetime.now().isoformat(),
                    "user": user_msg[:500],
                    "response": response[:500],
                    "action": action,
                    "mode": self.mode,
                })
            except: pass

    def recall(self, query: str = "", limit: int = 5) -> List[Dict]:
        """Recupera histórico da memória."""
        if self._memory:
            try:
                return self._memory.retrieve_solutions(query, limit)
            except: pass
        return []

    # ═══════════════ TOOLS: EXECUÇÃO REAL ═══════════════

    def execute(self, cmd: NLCommand, message: str = "") -> str:
        """Executa comando usando ferramentas REAIS do Quimera."""
        dispatch = {
            "register_key": self._exec_register_key,
            "explain":      self._exec_explain,
            "search":       self._exec_search,
            "pipeline":     self._exec_pipeline,
            "audit":        self._exec_audit,
            "health":       self._exec_health,
            "chat":         self._exec_chat,
        }
        handler = dispatch.get(cmd.action, self._exec_chat)
        result = handler(cmd, message)
        self.remember(message, result, cmd.action)
        return result

    # ═══════════════ HANDLERS ═══════════════

    def _exec_register_key(self, cmd: NLCommand, msg: str = "") -> str:
        provider = cmd.target or "groq"
        key = cmd.params.get("api_key", "")
        if not key:
            _, key = self._extract_key(msg)
        if not key:
            return "❌ Chave nao encontrada. Ex: cadastrar chave groq gsk_abc123"
        info = PROVIDERS.get(provider, PROVIDERS["groq"])
        os.environ[info["env"]] = key
        with open(".env", "a") as f:
            f.write(f'\n{info["env"]}={key}\n')
        self.api_key = key
        self.groq_available = True
        return f"✅ Chave **{info['label']}** cadastrada!\n   Variável: `{info['env']}` exportada"

    def _exec_explain(self, cmd: NLCommand, msg: str = "") -> str:
        target = cmd.target.strip()
        if not target or target == ".":
            target = "quimera"
        found = self._smart_find(target)
        if not found:
            return self._exec_chat(cmd, msg)
        fp = found[0]
        content = self._read_file(fp)
        if not content: return f"❌ `{fp}`"
        if content.startswith("📁"):
            return self._analyze_directory(fp, msg)
        return self._deep_review(fp, content)

    def _exec_search(self, cmd: NLCommand, msg: str = "") -> str:
        target = cmd.target.strip()
        found = self._smart_find(target) if target else []
        if not found:
            return f"❌ Nao encontrei '{target}'"
        return "📂 **Resultados:**\n" + "\n".join(f"   • {f}" for f in found[:15])

    def _exec_pipeline(self, cmd: NLCommand, msg: str = "") -> str:
        """Pipeline REAL via orquestrador nativo."""
        target = cmd.target.strip()
        found = self._smart_find(target) if target else []
        if not found:
            # Pergunta técnica sobre o Quimera? → chat com RAG
            return self._exec_chat(cmd, msg)

        fp = found[0]
        full = os.path.join(self.project_root, fp)
        if not os.path.isfile(full):
            return f"❌ `{fp}` nao e arquivo"

        # ═══ ORQUESTRADOR REAL ═══
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from quimera.quimera_master import execute_intelligent_task
            result = execute_intelligent_task("smart_analysis", target=full)

            out = [f"⚙️ **Pipeline H1→H6** (ORQUESTRADOR REAL)",
                   f"📄 `{fp}`", f"{'='*50}"]

            if isinstance(result, dict):
                sa = result.get("static_analysis", {})
                if sa:
                    out.append(f"\n📊 **Analise Estatica:**")
                    out.append(f"   Funcoes: {len(sa.get('functions',[]))}")
                    out.append(f"   Classes: {len(sa.get('classes',[]))}")
                    out.append(f"   Complexidade: {sa.get('complexity_score','?')}")
            else:
                out.append(f"\n{str(result)[:2000]}")
            return "\n".join(out)
        except Exception as e:
            logger.warning(f"Orquestrador: {e}")

        # Fallback: deep review
        try: code = open(full, errors="ignore").read()
        except: return f"❌ `{fp}`"
        return self._deep_review(fp, code)

    def _exec_audit(self, cmd: NLCommand, msg: str = "") -> str:
        """Auditoria Aegis REAL."""
        target = cmd.target.strip()
        found = self._smart_find(target) if target else []
        if not found:
            # Pergunta técnica sobre o Quimera? → chat com RAG
            return self._exec_chat(cmd, msg)

        fp = found[0]
        full = os.path.join(self.project_root, fp)
        if not os.path.isfile(full): return f"❌ `{fp}`"

        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from quimera.aegis.aegis_core import AegisCore
            aegis = AegisCore()
            code = open(full, errors="ignore").read()
            result = aegis.scan(code) if hasattr(aegis, 'scan') else aegis.analyze(code) if hasattr(aegis, 'analyze') else None

            if result:
                out = [f"🛡️ **Aegis Audit** (EXECUCAO REAL)", f"📄 `{fp}`", f"{'='*50}"]
                if isinstance(result, dict):
                    for k, v in result.items():
                        if isinstance(v, list):
                            out.append(f"\n⚠️ **{k}:** {len(v)} encontrados")
                        else:
                            out.append(f"   {k}: {v}")
                else:
                    out.append(str(result)[:2000])
                return "\n".join(out)
        except Exception as e:
            logger.warning(f"Aegis: {e}")

        content = self._read_file(fp)
        if content: return self._deep_review(fp, content)
        return f"❌ `{fp}`"

    def _exec_health(self, cmd: NLCommand, msg: str = "") -> str:
        """Health check REAL via orquestrador."""
        import platform as _platform
        out = [f"🐍 Python {sys.version.split()[0]}",
               f"📱 {_platform.system()} {_platform.release()}",
               f"🧠 IA: {'✅ local' if self.local_available else '✅ Groq' if self.groq_available else '⚠️ heuristicas'}",
               f"💾 Memoria: {'✅ ativa' if self._memory else '❌ indisponivel'}"]

        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from quimera.quimera_master import get_coordinator, get_system_capabilities
            caps = get_system_capabilities()
            out.append(f"\n📡 **Sistema Inteligente:** {'✅' if caps.get('smart_systems') else '❌'}")
            out.append(f"   Quimera Classico: {'✅' if caps.get('classic_quimera') else '❌'}")

            coord = get_coordinator()
            status = coord.get_system_status()
            out.append(f"\n📊 **Health:** {status.get('overall_health','?')}")
        except Exception as e:
            out.append(f"\n⚠️ Orquestrador: {e}")

        pyf = sum(1 for _ in Path(self.project_root).rglob("*.py"))
        out.append(f"\n📂 {pyf} arquivos Python")
        return "🏥 **Quimera Health**\n" + "\n".join(out)

    def _exec_chat(self, cmd: NLCommand, msg: str = "") -> str:
        """Chat: Local LLM → Groq API → RAG direto (NUNCA sem resposta)."""
        user_msg = msg or cmd.target or "ajuda"

        # ═══ RAG: busca conhecimento relevante ═══
        rag = self._rag_context(user_msg)

        # ═══ 1. LOCAL LLM (Qwen 3B) ═══
        if self.local_available and self._local:
            try:
                sp = self._kb_prompt if self._kb_prompt else "Voce e o Quimera. Responda em portugues."
                if rag:
                    sp += f"\n\nCONHECIMENTO DO QUIMERA:\n{rag}"
                prompt = f"<|im_start|>system\n{sp}\n<|im_end|>\n<|im_start|>user\n{user_msg}\n<|im_end|>\n<|im_start|>assistant\n"
                result = self._local(prompt, max_tokens=500, temperature=0.5, stop=["<|im_end|>"])
                text = result["choices"][0]["text"].strip()
                if text and len(text) > 10:
                    return f"🧠 [IA Local 3B]\n{text}"
            except Exception as e:
                logger.warning(f"Local chat: {e}")

        # ═══ 2. GROQ API ═══
        if self.groq_available:
            try:
                req = urllib.request.Request(
                    f"{self.base_url}/chat/completions",
                    data=json.dumps({
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": "Voce e o QUIMERA, plataforma autonoma de engenharia de codigo. Ferramentas: Pipeline H1-H6, Aegis, 20+ agentes, Bibliotecario, Memoria. Responda em portugues, CONCISO e TECNICO."},
                            {"role": "user", "content": f"{rag}\n\nUsuario: {user_msg}" if rag else user_msg},
                        ],
                        "temperature": 0.5, "max_tokens": 800,
                    }).encode(),
                    headers={"Authorization": f"Bearer {self.api_key}",
                             "Content-Type": "application/json", "User-Agent": "Quimera/5.4"},
                )
                with urllib.request.urlopen(req, timeout=25) as resp:
                    data = json.loads(resp.read())
                text = data["choices"][0]["message"]["content"]
                return f"☁️ [Groq]\n{text}"
            except Exception as e:
                logger.warning(f"Groq chat: {e}")

        # ═══ 3. RAG DIRETO — responde SEM LLM ═══
        if rag:
            return (f"📚 **Knowledge Base** (offline — sem LLM)\n"
                    f"{'='*50}\n"
                    f"🔍 {user_msg}\n\n"
                    f"{rag}\n\n"
                    f"💡 pip install llama-cpp-python para IA local 3B")

        # ═══ 4. Último recurso: tenta KB carregada ═══
        if self._kb and self._kb.get("data"):
            meta = self._kb["data"].get("metadata", {})
            mods = list(self._kb["data"].get("modules", {}).keys())[:20]
            return (f"📚 **Quimera Knowledge Base** carregada\n"
                    f"{'='*50}\n"
                    f"   Módulos: {meta.get('total_modules','?')}\n"
                    f"   Funções: {meta.get('total_functions','?')}\n"
                    f"   Classes: {meta.get('total_classes','?')}\n"
                    f"   Linhas: {meta.get('total_lines','?')}\n\n"
                    f"🔍 Tente:\n" + "\n".join(f"   • {m}" for m in mods[:10]) +
                    f"\n\n💡 pip install llama-cpp-python para respostas IA")

        return self._help()

    def _help(self) -> str:
        return """🤖 **Quimera MarkX v5.4** — Comandos:

⚙️  pipeline  — Pipeline H1-H6 (corrigir/analisar código)
🛡️  audit     — Aegis Security (auditar vulnerabilidades)
📊  health    — Diagnóstico do sistema
🔍  explain   — Explicar arquivos/código/pastas
🔎  search    — Buscar arquivos por nome
💬  chat      — Conversa livre com IA
🔑  register  — Cadastrar chave API

💡 Tente: "corrige o brain.py", "como ta o sistema", "audita seguranca"
"""

    # ═══════════════ UTILITÁRIOS ═══════════════

    def _smart_find(self, target: str) -> List[str]:
        """Busca arquivo/pasta inteligente."""
        if not target or target == ".": return []
        results = []
        clean = target.lower().replace(" ", "_").replace("-", "_")
        roots = [self.project_root,
                 os.path.expanduser("~/storage/downloads"),
                 os.path.expanduser("~/storage/shared/Download"),
                 os.path.expanduser("~/storage/shared"),
                 os.path.expanduser("~/storage")]
        for root in roots:
            if not os.path.isdir(root): continue
            for dirpath, dirs, files in os.walk(root):
                dirs[:] = [d for d in dirs if not d.startswith('.')][:10]
                for fn in files[:50]:
                    nl = fn.lower()
                    rp = os.path.join(dirpath, fn).replace(root+'/', '')
                    if clean == nl or clean in nl or clean == nl.split('.')[0]:
                        if rp not in results: results.append(rp)
                    elif clean.replace('_','') in nl.replace('_','').replace('-',''):
                        if rp not in results: results.append(rp)
        return sorted(results, key=lambda x: len(x))[:10]

    def _read_file(self, relpath: str) -> Optional[str]:
        """Lê arquivo ou lista diretório/ZIP."""
        full = os.path.join(self.project_root, relpath.rstrip('/'))
        if not os.path.exists(full):
            for root in [os.path.expanduser("~/storage/downloads"),
                         os.path.expanduser("~/storage/shared/Download"),
                         os.path.expanduser("~/storage/shared")]:
                c = os.path.join(root, relpath.rstrip('/'))
                if os.path.exists(c): full = c; break
            else: return None

        if os.path.isdir(full): return self._list_dir(full)
        if full.endswith('.zip'): return self._list_zip(full)
        if not os.path.isfile(full): return None
        if os.path.getsize(full) > 500_000:
            return f"📦 `{relpath}` ({os.path.getsize(full):,} bytes)"
        try:
            with open(full, 'r', errors='ignore') as f:
                sample = f.read(512)
            if '\x00' in sample: return f"📦 `{relpath}` (binario)"
            with open(full, 'r', errors='ignore') as f:
                return f.read()
        except: return None

    def _list_dir(self, path: str) -> str:
        try:
            items = sorted(os.listdir(path))
            dirs = [d for d in items if os.path.isdir(os.path.join(path, d))]
            files = [f for f in items if os.path.isfile(os.path.join(path, f))]
            total = sum(os.path.getsize(os.path.join(path, f)) for f in files)
            out = [f"📁 **{os.path.basename(path)}/** — {len(dirs)} pastas, {len(files)} arquivos ({self._fmt_size(total)})"]
            for d in dirs[:12]: out.append(f"   📁 {d}/")
            for fl in files[:12]:
                sz = self._fmt_size(os.path.getsize(os.path.join(path, fl)))
                out.append(f"   📄 {fl} ({sz})")
            return "\n".join(out)
        except: return f"📁 {os.path.basename(path)}/"

    def _list_zip(self, path: str) -> str:
        try:
            import zipfile
            with zipfile.ZipFile(path, 'r') as zf:
                names = zf.namelist()
                out = [f"📦 **{os.path.basename(path)}** — {len(names)} itens"]
                for n in names[:15]:
                    out.append(f"   {'📁' if n.endswith('/') else '📄'} {n}")
                return "\n".join(out)
        except: return f"📦 {os.path.basename(path)}"

    def _fmt_size(self, size: int) -> str:
        if size < 1024: return f"{size}B"
        if size < 1024*1024: return f"{size/1024:.1f}KB"
        return f"{size/(1024*1024):.1f}MB"

    def _analyze_directory(self, fp: str, msg: str) -> str:
        """Análise de diretório com LLM."""
        content = self._read_file(fp)
        if not content: return f"❌ `{fp}`"
        if not self.groq_available: return content

        # Tenta ler documentação do diretório
        extra = ""
        full_dir = os.path.join(self.project_root, fp.rstrip('/'))
        for docf in ['README.md','KERNEL.md','MANIFESTO.md']:
            dp = os.path.join(full_dir, docf)
            if os.path.isfile(dp):
                try:
                    with open(dp, 'r', errors='ignore') as df:
                        extra = f"\n\n📖 {docf}:\n{df.read()[:3000]}"
                except: pass
                break

        try:
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps({
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "Analista Quimera. Analise estruturas de diretorio. Deduza o proposito pelos nomes. Seja ANALITICO em portugues."},
                        {"role": "user", "content": f"Usuario perguntou: {msg}\n\nListagem:\n{content}{extra}\n\nAnalise."},
                    ],
                    "temperature": 0.4, "max_tokens": 700,
                }).encode(),
                headers={"Authorization": f"Bearer {self.api_key}",
                         "Content-Type": "application/json", "User-Agent": "Quimera/5.4"},
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = json.loads(resp.read())
            return f"{content}\n\n🧠 {data['choices'][0]['message']['content']}"
        except: pass
        return content

    def _deep_review(self, fp: str, content: str) -> str:
        """Code review profunda via Groq."""
        if not self.groq_available or not content or content.startswith("📁") or content.startswith("📦"):
            return f"📄 `{fp}`"

        ext = os.path.splitext(fp)[1]
        lang_map = {'.py':'Python','.c':'C','.cpp':'C++','.rs':'Rust','.go':'Go',
                    '.js':'JavaScript','.ts':'TypeScript','.java':'Java','.h':'C/C++'}
        lang = lang_map.get(ext, '')
        lines = content.split('\n')
        funcs = [l.strip()[:80] for l in lines if l.strip() and not l.strip().startswith('#')
                 and any(k in l for k in ['def ','class ','fn ','void ','int ','pub fn','func ','struct '])][:20]

        prompt = f"""Analise profissional em portugues ({lang}, {fp}):

```
{content[:6000]}
```

{len(lines)} linhas | {', '.join(funcs[:10]) if funcs else 'sem funcoes detectadas'}

1. PROPOSITO 2. ESTRUTURA 3. PONTOS FORTES 4. PROBLEMAS 5. SUGESTOES 6. NOTA 0-10
TECNICO. Cite funcoes/linhas."""

        try:
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps({
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "Analista de codigo senior Quimera. Tecnico, especifico, portugues."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3, "max_tokens": 1200,
                }).encode(),
                headers={"Authorization": f"Bearer {self.api_key}",
                         "Content-Type": "application/json", "User-Agent": "Quimera/5.4"},
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read())
            review = data["choices"][0]["message"]["content"]
            return f"🔬 **Deep Review**\n📄 `{fp}` | {lang} | {len(lines)} linhas\n{'-'*50}\n{review}"
        except: pass
        return f"📄 `{fp}` ({len(lines)} linhas)"

    def close(self):
        if self._local and hasattr(self._local, 'close'):
            self._local.close()

# Singleton
hybrid_assistant = HybridAssistant()
