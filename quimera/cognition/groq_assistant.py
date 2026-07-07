"""
GroqAssistant v2 — Assistente NL REAL com Groq (Llama 3.3 70B).

ENTENDE DE VERDADE:
  "cadastra a chave da groq gsk_abc123"
  "cadastra chave do gemini AIzaXyz"
  "analise o agente analista"
  "o que faz o arquivo pipeline.py?"
  "busca por sqlalchemy no projeto"
  "a pasta do projeto ta em downloads"
"""
import os, re, json, sys, urllib.request, urllib.error, logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("quimera.groq_assistant")

PROVIDERS = {
    "groq":       {"prefix": "gsk_",   "env": "GROQ_API_KEY",       "label": "Groq"},
    "openai":     {"prefix": "sk-",    "env": "OPENAI_API_KEY",     "label": "OpenAI"},
    "gemini":     {"prefix": "AIza",   "env": "GEMINI_API_KEY",     "label": "Gemini"},
    "anthropic":  {"prefix": "sk-ant-","env": "ANTHROPIC_API_KEY",  "label": "Anthropic"},
    "openrouter": {"prefix": "sk-or-", "env": "OPENROUTER_API_KEY", "label": "OpenRouter"},
    "deepseek":   {"prefix": "sk-",    "env": "DEEPSEEK_API_KEY",   "label": "DeepSeek"},
}


@dataclass
class NLCommand:
    action: str
    target: str
    params: Dict = field(default_factory=dict)
    confidence: float = 0.9
    explanation: str = ""


class GroqAssistant:
    """Assistente com Groq LLM — entende portugues de verdade."""

    SYSTEM_PROMPT = """VOCE E O QUIMERA. Nao e assistente — e o SISTEMA Quimera MarkX v5.4 rodando em Termux. Voce COMANDO o motor.

═══════════ FERRAMENTAS ═══════════
🔧 pipeline — Pipeline H1-H6 reparo autonomo (deteccao→patches→validacao→evolucao)
🛡️ audit — Analise seguranca Aegis (vulnerabilidades, malware, cripto)
📊 health — Diagnostico completo do sistema
🔍 explain — Analise de arquivos, pastas, arquitetura, codigo
🔎 search — Busca arquivos por nome no projeto/dispositivo
🧠 chat — Conversa geral, ajuda
🔑 register_key — Cadastra chaves API

═══════════ REGRAS ═══════════
1. "corrige/arruma/repara/conserta X" → action=pipeline, target="X"
2. "audita/seguranca/vulnerabilidade X" → action=audit, target="X"
3. "como esta/health/diagnostico/sistema" → action=health
4. "analisa/explique/o que e/mostra X" → action=explain
5. "busca/procura/cade X" → action=search
6. "cadastra/chave/api key X" → action=register_key
7. Nenhuma ferramenta → action=chat
8. target = exatamente o que o usuario falou

Responda APENAS JSON: {"action":"...","target":"...","params":{},"explanation":"..."}"""

    def __init__(self):
        self.api_key = self._load_key()
        self.base_url = "https://api.groq.com/openai/v1"
        self.model = "llama-3.3-70b-versatile"
        self.available = bool(self.api_key)
        self.project_root = "."

    def _load_key(self) -> Optional[str]:
        for var in ["GROQ_API_KEY", "OPENAI_API_KEY"]:
            k = os.environ.get(var)
            if k: return k
        for p in [".env", os.path.expanduser("~/.env")]:
            try:
                if os.path.exists(p):
                    for line in open(p):
                        if line.startswith("GROQ_API_KEY="):
                            return line.split("=",1)[1].strip().strip('"').strip("'")
            except: pass
        return None

    # ═══════════════════════════════════════════════════════════
    # INTERPRETACAO
    # ═══════════════════════════════════════════════════════════

    def understand(self, message: str) -> NLCommand:
        if self.available:
            result = self._call_llm(message)
            if result: return result
        return self._fallback(message)

    def _call_llm(self, message: str) -> Optional[NLCommand]:
        try:
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps({
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": message},
                    ],
                    "temperature": 0.1, "max_tokens": 300,
                }).encode(),
                headers={"Authorization": f"Bearer {self.api_key}",
                         "Content-Type": "application/json",
                         "User-Agent": "Quimera/5.4"},
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read())
            text = data["choices"][0]["message"]["content"]
            jm = re.search(r"\{.*\}", text, re.DOTALL)
            if jm:
                d = self._safe_json(jm.group(0))
                return NLCommand(
                    action=d.get("action","help"),
                    target=d.get("target","."),
                    params=d.get("params",{}),
                    confidence=0.95,
                    explanation=f"[Groq] {d.get('explanation','')}",
                )
        except Exception as e:
            logger.warning(f"Groq: {e}")
        return None

    def _safe_json(self, text: str) -> dict:
        try: return json.loads(text)
        except:
            text = re.sub(r',\s*}', '}', text)
            text = re.sub(r'([{,]\s*)(\w+):', r'\1"\2":', text)
            return json.loads(text)

    def _fallback(self, msg: str) -> NLCommand:
        m = msg.lower()
        # 1. register_key
        if any(k in m for k in ["cadastr","registr","chave","api key"]):
            prov, key = self._extract_key(msg)
            return NLCommand("register_key", prov or "groq",
                           {"api_key": key} if key else {},
                           explanation="Cadastro de chave API")
        # 2. explain (analisar/explicar)
        explain_kw = ["analis","olha","olhe","explic","mostra","veja","ve ",
                      "o que faz","o que e","como funciona","me explica",
                      "descreva","descreve","resume","resuma"]
        if any(k in m for k in explain_kw):
            target = self._extract_target(m, msg)
            # Extrai caminho mencionado
            params = {}
            user_path = self._resolve_user_path(msg)
            if user_path:
                params["path"] = user_path
            return NLCommand("explain", target, params=params,
                           explanation="Analise de componente")
        # 3. search
        if any(k in m for k in ["busca","busque","procur","pesquis","acha","encontra",
                                "procura por","busca por","pesquisa por"]):
            return NLCommand("search", self._extract_target(m, msg),
                           explanation="Busca de arquivos")
        # 4. repair
        if any(k in m for k in ["arrum","corrig","consert","bug","erro","quebrou","testar","teste","executar","execute","roda","rodar",
                                "nao compila","nao funciona","falha"]):
            return NLCommand("repair", self._extract_target(m, msg),
                           explanation="Correcao de bugs")
        # 5. tentativa: chave pura (se parece com API key)
        key_match = re.search(r'(gsk_[\w]{20,}|sk-[\w\-]{30,}|AIza[\w\-]{30,})', msg)
        if key_match:
            return NLCommand("register_key", "groq",
                           {"api_key": key_match.group(0)},
                           explanation="Chave API detectada — cadastrando como Groq")
        return NLCommand("help", ".", explanation="Ajuda")

    def _extract_target(self, msg_lower: str, original: str) -> str:
        # 1. Remove prefixos de acao
        for pfx in ["analise ","analisa ","olha ","olhe ","ve ","veja ","mostra ",
                    "explica ","explique ","o que faz ","o que e ",
                    "busca ","busque ","procura ","pesquisa ","acha ","encontra ",
                    "arruma ","corrige ","conserta ","conserte "]:
            if msg_lower.startswith(pfx):
                t = original[len(pfx):].strip().rstrip(".!?")
                break
        else:
            t = original.strip()

        if not t or t in ("o","a","os","as","."): return "."

        # 2. Remove artigos e conectores iniciais
        for noise in ["o ","a ","os ","as ","como ","que ","do ","da ","no ","na ","em "]:
            if t.lower().startswith(noise):
                t = t[len(noise):].strip()

        if not t: return "."

        # 3. Se tem "na pasta X" ou "em X", extrai so o alvo (antes da localizacao)
        t = re.split(r'\s+(?:na|no|em|dentro d[ae])\s+pasta\s+', t, flags=re.I)[0].strip()
        t = re.split(r'\s+(?:na|no|em)\s+(?!pasta)', t, flags=re.I)[0].strip() if len(t.split()) > 3 else t

        # 4. Remove aspas
        t = t.strip("\"'")

        return t if t else "."

    def _extract_key(self, text: str):
        """Extrai provider e chave de texto."""
        for prov, info in PROVIDERS.items():
            if prov in text.lower():
                m = re.search(rf'{prov}\s+["\']?([\w\-]+)["\']?', text, re.I)
                if m and len(m.group(1)) >= 10:
                    return prov, m.group(1)
        m = re.search(r'(gsk_[\w]+|sk-[\w\-]{20,}|AIza[\w\-]{20,}|sk-ant-[\w\-]{20,}|sk-or-[\w\-]{20,})', text)
        if m:
            key = m.group(0)
            for p, i in PROVIDERS.items():
                if i["prefix"] and key.startswith(i["prefix"]): return p, key
            return "openai", key
        return "", ""

    # ═══════════════════════════════════════════════════════════
    # EXECUCAO
    # ═══════════════════════════════════════════════════════════

    def execute(self, cmd: NLCommand, project_root: str = ".", msg_original: str = "") -> str:
        self.project_root = os.path.abspath(os.path.expanduser(project_root))
        self._msg_original = msg_original
        dispatch = {
            "register_key": self._do_register_key,
            "explain":      self._do_explain,
            "search":       self._do_search,
            "scan":         self._do_run,
            "repair":       self._do_run,
            "audit":        self._do_scan,
            "pipeline":     self._do_pipeline,
            "audit":        self._do_audit,
            "health":       self._do_health,
            "help":         self._do_help,
        }
        return dispatch.get(cmd.action,
                           self._do_chat if self.available else self._do_help)(cmd)

    # ── REGISTER KEY ──────────────────────────────────────

    def _do_register_key(self, cmd: NLCommand) -> str:
        key = cmd.params.get("api_key", "")
        provider = ""
        if not key or len(key) < 10:
            provider, key = self._extract_key(cmd.target)
        if not key or len(key) < 10:
            provider, key = self._extract_key(self._msg_original)
        else:
            provider = self._detect_provider(key)

        if not key or len(key) < 10:
            return "❌ Chave nao encontrada. Ex: quimera assist \"cadastra chave groq gsk_abc123\""

        if not provider:
            for p in PROVIDERS:
                if p in (cmd.explanation + cmd.target).lower():
                    provider = p; break
            if not provider: provider = "groq"

        info = PROVIDERS.get(provider, PROVIDERS["groq"])
        self._write_env(info["env"], key)
        os.environ[info["env"]] = key
        if provider == "groq":
            self.api_key = key; self.available = True

        return (f"✅ Chave **{info['label']}** cadastrada!\n"
                f"   Variavel: `{info['env']}` exportada\n"
                f"   Arquivo .env atualizado. Pronto para usar!")

    def _detect_provider(self, key: str) -> str:
        for p, i in PROVIDERS.items():
            if i["prefix"] and key.startswith(i["prefix"]): return p
        return "openai"

    def _write_env(self, var: str, value: str):
        ep = os.path.join(self.project_root, ".env")
        lines, found = [], False
        if os.path.exists(ep):
            for line in open(ep):
                if line.startswith(f"{var}="): lines.append(f"{var}={value}\n"); found = True
                else: lines.append(line)
        if not found: lines.append(f"\n{var}={value}\n")
        with open(ep,"w") as f: f.writelines(lines)

    # ── EXPLAIN (analisar arquivo) ────────────────────────

    def _do_explain(self, cmd: NLCommand) -> str:
        target = cmd.target.strip()
        user_path = cmd.params.get("path", "")
        if not target or target == ".": return self._do_help(cmd)

        # 1. Se usuario mencionou caminho, adiciona como raiz de busca
        if user_path:
            self.project_root = os.path.abspath(os.path.expanduser(user_path))

        found = self._smart_find(target)

        if not found:
            # Tenta resolver caminho mencionado na mensagem
            resolved = self._resolve_user_path(target)
            if resolved:
                self.project_root = resolved
                found = self._smart_find(target.split()[-1] if ' ' in target else target)
            if not found:
                if self.available:
                    return self._do_chat(cmd)
                return (f"🔍 Nao encontrei **{target}**.\n\n"
                        f"   Tente: 'busca por {target}' no projeto\n"
                        f"   Ou: 'analise o nome_do_arquivo.py'")

        # 2. Auto-pick best match (prefere arquivos mais proximos da raiz)
        best = self._pick_best(found, target)

        # 3. Se tem muitos, mostra o melhor + alternativas
        if len(found) > 1:
            others = [f for f in found if f != best][:3]
            if others:
                alt = "\n".join(f"   • {f}" for f in others)
                print(f"   📂 {len(found)} resultados, analisando o melhor:\n   ✅ {best}\n{alt}\n")

        filepath = best
        content = self._read_file(filepath)
        if content is None:
            return f"❌ Nao consegui ler `{filepath}`"

        if content.startswith("📁") or content.startswith("📦"):
            if self.available:
                extra = ""
                if content.startswith("📁"):
                    full_dir = os.path.join(self.project_root, filepath.rstrip('/'))
                    for docf in ['README.md','KERNEL.md','MANIFESTO.md','QUICKSTART.md',
                                 'readme.md','README.txt','INSTRUCOES_TERMUX.md']:
                        dp = os.path.join(full_dir, docf)
                        if os.path.isfile(dp):
                            try:
                                with open(dp, 'r', errors='ignore') as df:
                                    extra = f"\n\n📖 Documentacao ({docf}):\n{df.read()[:4000]}"
                            except: pass
                            break
                SYS = ("Voce e assistente analitico de terminal. Recebeu listagem de diretorio. "
                       "ANALISE a estrutura INTELIGENTEMENTE:\n"
                       "- setup.py/__init__.py/requirements.txt → PROJETO SOFTWARE. Explique o que faz.\n"
                       "- Dockerfile/docker-compose → explique arquitetura.\n"
                       "- So arquivos soltos → liste o que tem.\n"
                       "- .c/.cpp/.py → codigo fonte.\n"
                       "Deduza proposito pelos NOMES. Responda em portugues, ANALITICO, direto. "
                       "NAO de tutoriais. NAO explique comandos.")
                ctx = f"Usuario perguntou: \"{self._msg_original}\"\n\nListagem:\n{content}{extra}\n\nAnalise e responda."
                try:
                    req = urllib.request.Request(
                        f"{self.base_url}/chat/completions",
                        data=json.dumps({"model": self.model, "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": ctx}], "temperature": 0.4, "max_tokens": 700}).encode(),
                        headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json", "User-Agent": "Quimera/5.4"})
                    with urllib.request.urlopen(req, timeout=25) as resp:
                        data = json.loads(resp.read())
                    return f"{content}\n\n🧠 {data['choices'][0]['message']['content']}"
                except: pass
            return content

        analysis = self._analyze_content(filepath, content)
        return f"📄 **{os.path.basename(filepath)}**\n   `{filepath}`\n\n{analysis}"

    def _pick_best(self, files: List[str], target: str) -> str:
        """Escolhe o melhor arquivo entre varios resultados."""
        if len(files) == 1:
            return files[0]
        target_clean = target.lower().replace(" ", "_").replace("-", "_")
        # Pontuacao: prefere caminho mais curto, nome mais proximo, evita backups/cemiterio
        def score(f):
            s = 0
            s -= f.count('/') * 10
            for bad in ['backup', 'cemiterio', '_old', 'VideoDownloader', 'Quimera_Refatorado', 'Kimi_Agent']:
                if bad.lower() in f.lower():
                    s -= 100
            name = os.path.splitext(os.path.basename(f.rstrip('/')))[0].lower()
            ext = os.path.splitext(os.path.basename(f))[1].lower()
            doc_names = ['readme', 'kernel', 'manifesto', 'quickstart', 'index',
                         'main', '__init__', '__main__', 'setup', 'about', 'intro',
                         'instructions', 'guia', 'validation_report']
            if name in doc_names:
                s += 150
            if ext in ('.md', '.rst', '.txt'):
                s += 40
            full_path = os.path.join(self.project_root, f.rstrip('/'))
            if os.path.isdir(full_path):
                s += 60
            if ext in ('.zip', '.gz', '.tar', '.7z', '.rar', '.bin', '.exe', '.dll', '.so', '.ehi', '.o', '.a'):
                s -= 80
            if name == target_clean:
                s += 50
            elif target_clean in name:
                s += 30
            # Bonus: target no nome do arquivo
            if all(part in name for part in target_clean.split('_') if len(part) > 2):
                s += 20
            return s
        return max(files, key=score)

    def _resolve_user_path(self, text: str) -> Optional[str]:
        """Resolve caminhos mencionados: 'na pasta downloads', 'em ~/projeto', etc."""
        patterns = [
            r'(?:na|no|em|dentro d[ae]|ta em)\s+(?:pasta\s+)?["\']?([~\w./\s-]{3,})["\']?',
            r'(?:pasta|caminho|diret.rio)\s+["\']?([~\w./\s-]{3,})["\']?',
        ]
        for pat in patterns:
            m = re.search(pat, text, re.I)
            if m:
                p = os.path.expanduser(m.group(1))
                if os.path.exists(p): return os.path.abspath(p)
                for pf in [os.path.expanduser("~/storage/downloads/"),
                           os.path.expanduser("~/storage/shared/"),
                           os.path.expanduser("~/storage/shared/Download/"),
                           os.path.expanduser("~/")]:
                    full = os.path.join(pf, m.group(1))
                    if os.path.exists(full): return os.path.abspath(full)
        return None

    def _smart_find(self, target: str) -> List[str]:
        clean = target.strip().lower().replace(" ","_").replace("-","_")
        results, seen = [], set()

        roots = [self.project_root]
        extra = self._resolve_path(target)
        if extra and os.path.exists(extra): roots.append(extra)
        for common in [os.path.expanduser("~/storage/downloads"),
                       os.path.expanduser("~/storage/shared/Download"),
                       os.path.expanduser("~/storage/shared"),
                       os.path.expanduser("~/storage")]:
            if os.path.exists(common) and common not in roots: roots.append(common)

        for root in roots:
            if not os.path.exists(root): continue
            try:
                for dirpath, dirs, files in os.walk(root):
                    dirs[:] = [d for d in dirs if not d.startswith('.')
                               and d not in ('node_modules','__pycache__','.git','target')]
                    depth = dirpath.replace(root,'').count(os.sep)
                    if depth > 6: dirs[:] = []; continue

                    for dn in dirs:
                        if dn.startswith('.'): continue
                        nl_d = dn.lower()
                        rp_d = os.path.join(dirpath, dn).replace(root+'/', '') + '/'
                        if clean == nl_d or clean in nl_d:
                            if rp_d not in seen: seen.add(rp_d); results.insert(0, rp_d)
                        else:
                            for word in clean.split('_'):
                                if len(word) > 2 and word in nl_d:
                                    if rp_d not in seen: seen.add(rp_d); results.append(rp_d)
                                    break

                    for fn in files:
                        if fn.startswith('.'): continue
                        nl = fn.lower()
                        fl = os.path.join(dirpath, fn).lower()
                        rp = os.path.join(dirpath, fn).replace(root+'/','')

                        if clean == nl.replace('.py','').replace('.c','').replace('.rs','').replace('.go',''):
                            if rp not in seen: seen.add(rp); results.insert(0, rp)
                        elif clean in nl:
                            if rp not in seen: seen.add(rp); results.append(rp)
                        elif clean in fl.replace(root.lower()+'/',''):
                            if rp not in seen: seen.add(rp); results.append(rp)
                        elif all(p in nl for p in clean.split('_') if len(p)>2):
                            if rp not in seen: seen.add(rp); results.append(rp)

                    if len(results) >= 20: break
            except PermissionError: continue

        return results[:10]

    def _resolve_path(self, text: str) -> Optional[str]:
        for pat in [r'(?:na|no|em|dentro d[ae]|ta em)\s+(?:pasta\s+)?["\']?([~\w./\s-]{3,})["\']?',
                    r'(?:pasta|caminho|diret.rio)\s+["\']?([~\w./\s-]{3,})["\']?']:
            m = re.search(pat, text, re.I)
            if m:
                p = os.path.expanduser(m.group(1))
                if os.path.exists(p): return p
                for pf in [os.path.expanduser("~/storage/downloads/"),
                           os.path.expanduser("~/storage/shared/"), os.path.expanduser("~/")]:
                    full = os.path.join(pf, m.group(1))
                    if os.path.exists(full): return full
        return None

    def _read_file(self, relpath: str) -> Optional[str]:
        full = os.path.join(self.project_root, relpath.rstrip('/'))
        if not os.path.exists(full):
            full = os.path.expanduser(relpath) if not os.path.isabs(relpath) else relpath
        if not os.path.exists(full):
            for root in [os.path.expanduser("~/storage/downloads"),
                         os.path.expanduser("~/storage/shared/Download"),
                         os.path.expanduser("~/storage/shared")]:
                candidate = os.path.join(root, relpath.rstrip('/'))
                if os.path.exists(candidate): full = candidate; break
            else: return None

        if os.path.isdir(full):
            return self._list_directory(full)

        ext = os.path.splitext(full)[1].lower()
        if ext == '.zip':
            return self._list_zip(full)

        if not os.path.isfile(full): return None
        if os.path.getsize(full) > 500_000:
            return f"\U0001f4e6 `{relpath}` ({os.path.getsize(full):,} bytes - grande demais)"

        try:
            with open(full, 'r', errors='ignore') as f:
                sample = f.read(512)
            if '\x00' in sample:
                return f"\U0001f4e6 `{relpath}` ({os.path.getsize(full):,} bytes - binario)"
            with open(full, 'r', errors='ignore') as f:
                content = f.read()
            if len(content) > 8000:
                lines2 = content.split('\n')
                head = '\n'.join(lines2[:80])
                defs = [l for l in lines2 if re.match(r'^\s*(def |class |async def |fn |pub fn )', l)]
                mid = '\n'.join(defs[:40]) if defs else ""
                return f"{head}\n\n... ({len(lines2)} linhas) ...\n\nFUNCOES/CLASSES:\n{mid}"
            return content
        except Exception as e:
            return f"\u274c Erro ao ler `{relpath}`: {e}"


    def _list_directory(self, path: str) -> str:
        try:
            items = sorted(os.listdir(path))
            dirs = [d for d in items if os.path.isdir(os.path.join(path, d))]
            files = [f for f in items if os.path.isfile(os.path.join(path, f))]
            total_size = sum(os.path.getsize(os.path.join(path, f))
                           for f in files if os.path.isfile(os.path.join(path, f)))
            out = [f"📁 **{os.path.basename(path)}/** — {len(dirs)} pastas, {len(files)} arquivos ({self._fmt_size(total_size)})"]
            out.append("")
            for d in dirs[:15]:
                out.append(f"   📁 {d}/")
            for f in files[:15]:
                fp = os.path.join(path, f)
                out.append(f"   📄 {f} ({self._fmt_size(os.path.getsize(fp))})")
            total = len(dirs) + len(files)
            if total > 30:
                out.append(f"   ... e mais {total - 30} itens")
            return "\n".join(out)
        except PermissionError:
            return f"❌ Sem permissao para `{path}`"
        except Exception as e:
            return f"❌ Erro ao listar `{path}`: {e}"

    def _list_zip(self, path: str) -> str:
        try:
            import zipfile
            with zipfile.ZipFile(path, 'r') as zf:
                names = zf.namelist()
                total = len(names)
                size = os.path.getsize(path)
                out = [f"📦 **{os.path.basename(path)}** — {total} arquivos ({self._fmt_size(size)})"]
                out.append("")
                for n in names[:20]:
                    marker = "📁" if n.endswith('/') else "📄"
                    out.append(f"   {marker} {n}")
                if total > 20:
                    out.append(f"   ... e mais {total - 20} itens")
                return "\n".join(out)
        except ImportError:
            return f"📦 `{os.path.basename(path)}` ({self._fmt_size(os.path.getsize(path))} — ZIP)"
        except Exception as e:
            return f"❌ Erro ao ler ZIP `{path}`: {e}"

    def _fmt_size(self, size: int) -> str:
        if size < 1024: return f"{size}B"
        if size < 1024*1024: return f"{size/1024:.1f}KB"
        return f"{size/(1024*1024):.1f}MB"

    def _analyze_content(self, path: str, content: str) -> str:
        if not self.available:
            return self._analyze_offline(path, content)

        ext = os.path.splitext(path)[1]
        lm = {'.py':'Python','.c':'C','.h':'C/C++','.cpp':'C++','.rs':'Rust',
              '.go':'Go','.js':'JavaScript','.ts':'TypeScript','.java':'Java'}
        lang = lm.get(ext, '')

        prompt = f"""Analise este arquivo {lang} ({path}) em portugues:

{content[:6000]}

Responda:
1. **Proposito**: O que faz? (1-2 frases)
2. **Estrutura**: Classes/funcoes principais
3. **Dependencias**: O que importa e conexoes
4. **Observacoes**: Bugs potenciais ou melhorias"""

        try:
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps({"model": self.model, "messages": [
                    {"role": "user", "content": prompt}
                ], "temperature": 0.3, "max_tokens": 600}).encode(),
                headers={"Authorization": f"Bearer {self.api_key}",
                         "Content-Type": "application/json",
                         "User-Agent": "Quimera/5.4"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"LLM analysis: {e}")
            return self._analyze_offline(path, content)

    def _analyze_offline(self, path: str, content: str) -> str:
        lines = content.split('\n')
        classes = re.findall(r'class\s+(\w+)', content)
        funcs = re.findall(r'def\s+(\w+)', content)
        doc = ""
        m = re.search(r'"""(.*?)"""', content, re.DOTALL)
        if m: doc = m.group(1).strip().split('\n')[0][:100]

        out = [f"[OFFLINE] `{path}`:"]
        out.append(f"\n**Proposito**: {doc if doc else 'Nao documentado'}")
        out.append(f"\n**Tamanho**: {len(lines)} linhas")
        if classes: out.append(f"\n**Classes**: {', '.join(classes[:8])}")
        if funcs: out.append(f"\n**Funcoes**: {', '.join(funcs[:10])}")
        if 'class ' in content:
            if 'agent' in path.lower() or 'agente' in path.lower():
                out.append("\n📌 Parece ser um **agente autonomo**")
            elif 'Model' in content or 'SQLAlchemy' in content:
                out.append("\n📌 Parece ser um **modelo ORM**")
            elif 'route' in path or '@app' in content:
                out.append("\n📌 Parece ser um **endpoint/controller**")
        return '\n'.join(out)

    # ── SEARCH ────────────────────────────────────────────

    def _do_search(self, cmd: NLCommand) -> str:
        target = cmd.target.strip()
        if not target: return "🔍 O que buscar? Ex: 'busca por sqlalchemy'"
        found = self._smart_find(target)
        if found:
            pv = "\n".join(f"   📄 {f}" for f in found[:8])
            return f"🔍 **{len(found)} arquivos** com '{target}':\n{pv}"
        if self.available:
            return self._do_chat(cmd)
        return f"🔍 Nenhum arquivo com '{target}'. Tente termo mais curto."

    # ── SCAN ──────────────────────────────────────────────

    def _do_scan(self, cmd: NLCommand) -> str:
        target = cmd.target.strip()
        if not target or target == ".":
            try:
                from quimera.cognition.project_intelligence import project_intelligence
                ctx = project_intelligence.analyze(self.project_root)
                return (f"📦 **{ctx.project_name}** ({ctx.primary_language}, {ctx.file_count} arquivos)\n"
                        f"   Health: {ctx.health_score:.0f}/100\n"
                        f"   Use 'analise o <arquivo>' para detalhes.")
            except: return f"📦 Projeto: {self.project_root}"

        found = self._smart_find(target)
        if not found:
            if self.available:
                return self._do_chat(cmd)
            return f"❌ Nao encontrei '{target}'"
        fp = found[0]
        c = self._read_file(fp)
        if not c: return f"❌ Nao consegui ler `{fp}`"
        if c.startswith("📁") or c.startswith("📦"):
            return c
        if self.available: return self._analyze_content(fp, c)
        return f"📄 `{fp}`\n   Execute: python -m quimera scan {fp}"

    # ── CHAT (LLM fallback) ───────────────────────────────


    def _do_run(self, cmd: NLCommand) -> str:
        """Executa analise REAL — auto-seleciona arquivo se necessario."""
        target = cmd.target.strip()
        found = self._smart_find(target) if target and target != "." else []

        if not found:
            candidates = []
            for root, dirs, files in os.walk(self.project_root):
                dirs[:] = [d for d in dirs if not d.startswith('.')
                           and d not in ('__pycache__','node_modules','.git','backup','cemiterio')]
                depth = root.replace(self.project_root, '').count(os.sep)
                if depth > 5: dirs[:] = []; continue
                for fn in files:
                    if fn.endswith('.py') and fn not in ('__init__.py','setup.py','config.py'):
                        rp = os.path.join(root, fn).replace(self.project_root+'/', '')
                        hot = ['pipeline','brain','engineer','assistant','agent','core',
                               'scan','repair','main','cli','detect','analyze','planner',
                               'orchestrat','memory','knowledge']
                        score = 0
                        fnl = fn.lower()
                        for h in hot:
                            if h in fnl: score += 30
                        score -= rp.count('/') * 5
                        if fn.endswith('.c'): score += 10
                        candidates.append((score, rp, os.path.getsize(os.path.join(root, fn))))
                if len(candidates) >= 20: break
            candidates.sort(key=lambda x: -x[0])
            found = [rp for _, rp, _ in candidates[:5]]

        if not found:
            return ("❌ Nao achei arquivos para analisar.\n"
                    f"   Tente: 'analise o nome_do_arquivo.py'")

        fp = found[0]
        content = self._read_file(fp)
        if not content:
            return f"❌ Nao consegui ler `{fp}`"
        if content.startswith("📁"):
            return content

        if not self.available:
            return f"📄 `{fp}`\n   Execute: python -m quimera scan {fp}"

        return self._deep_review(fp, content)

    def _deep_review(self, filepath: str, content: str) -> str:
        """Code review profunda estilo Quimera via Groq."""
        ext = os.path.splitext(filepath)[1]
        lang_map = {'.py':'Python','.c':'C','.cpp':'C++','.rs':'Rust','.go':'Go',
                    '.js':'JavaScript','.ts':'TypeScript','.java':'Java','.h':'C/C++'}
        lang = lang_map.get(ext, '')
        lines = content.split('\n')
        n_lines = len(lines)
        funcs = [l.strip()[:80] for l in lines
                 if l.strip() and not l.strip().startswith('#')
                 and any(k in l for k in ['def ','class ','fn ','void ','int ',
                                          'pub fn','func ','struct ','impl '])][:25]

        prompt = f"""Analise este arquivo {lang} ({filepath}) profissionalmente:

```
{content[:6000]}
```

METADADOS: {n_lines} linhas | Principais definicoes:
{chr(10).join(funcs[:15]) if funcs else '(nenhuma detectada)'}

Forneca analise em portugues:
1. **PROPOSITO**: O que faz? (2-3 frases)
2. **ESTRUTURA**: Componentes e conexoes
3. **PONTOS FORTES**: Boas praticas, patterns
4. **PROBLEMAS**: Bugs, vulnerabilidades, anti-patterns, performance
5. **SUGESTOES**: Melhorias concretas
6. **NOTA**: 0-10

Seja TECNICO. Cite funcoes/linhas especificas."""

        try:
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps({
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "Analista de codigo senior. Analises profundas, tecnicas, especificas em portugues."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3, "max_tokens": 1200,
                }).encode(),
                headers={"Authorization": f"Bearer {self.api_key}",
                         "Content-Type": "application/json",
                         "User-Agent": "Quimera/5.4"},
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read())
            review = data["choices"][0]["message"]["content"]

            header = (f"🔬 **Quimera Deep Review**\n"
                     f"📄 `{filepath}` | {lang} | {n_lines} linhas\n"
                     f"{'-'*50}\n")
            return header + "\n" + review
        except Exception as e:
            logger.warning(f"Deep review: {e}")
            return self._analyze_content(filepath, content)


    def _do_pipeline(self, cmd: NLCommand) -> str:
        """Pipeline H1-H6 REAL — orquestrador nativo do Quimera."""
        target = cmd.target.strip()
        found = self._smart_find(target) if target else []
        if not found: return self._do_run(cmd)
        fp = found[0]
        full = os.path.join(self.project_root, fp)
        if not os.path.isfile(full): return f"❌ `{fp}` nao e arquivo"

        # ═══ ORQUESTRADOR REAL ═══
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from quimera.quimera_master import execute_intelligent_task

            result = execute_intelligent_task("smart_analysis", target=full)
            out = [f"⚙️ **Quimera Pipeline H1→H6** (EXECUCAO REAL)",
                   f"📄 `{fp}`", f"{'='*50}"]

            if isinstance(result, dict):
                sa = result.get("static_analysis", {})
                if sa:
                    out.append(f"\n📊 **Analise Estatica:**")
                    out.append(f"   Funcoes: {len(sa.get('functions',[]))}")
                    out.append(f"   Classes: {len(sa.get('classes',[]))}")
                    out.append(f"   Linhas: {sa.get('lines','?')}")
                    out.append(f"   Complexidade: {sa.get('complexity_score','?')}")
                    if sa.get('functions'):
                        out.append(f"   Metodos: {', '.join(sa['functions'][:10])}")
                if result.get("issues"):
                    out.append(f"\n⚠️ **Problemas:**")
                    for iss in result["issues"][:6]:
                        out.append(f"   • {iss}")
            else:
                out.append(f"\n{str(result)[:2000]}")
            return "\n".join(out)

        except Exception as e:
            logger.warning(f"Orquestrador indisponivel: {e}")

        # ═══ FALLBACK ═══
        try: code = open(full, errors="ignore").read()
        except: return f"❌ `{fp}`"
        if self.available: return self._deep_review(fp, code)
        return f"⚙️ Pipeline indisponivel.\n   Execute: python -m quimera pipeline {fp}"

    def _do_health(self, cmd: NLCommand) -> str:
        """Diagnostico REAL do Quimera — orquestrador nativo."""
        import sys as _sys, platform as _platform
        out = [f"🐍 Python {_sys.version.split()[0]}",
               f"📱 {_platform.system()} {_platform.release()}",
               f"🧠 Groq: {'✅ '+self.model if self.available else '❌ sem chave'}"]

        # ═══ ORQUESTRADOR REAL ═══
        try:
            _sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from quimera.quimera_master import get_coordinator, get_system_capabilities

            caps = get_system_capabilities()
            out.append(f"\n📡 **Sistema Inteligente:** {'✅ ativo' if caps.get('smart_systems') else '❌ indisponivel'}")
            out.append(f"   Quimera Classico: {'✅' if caps.get('classic_quimera') else '❌'}")

            coord = get_coordinator()
            status = coord.get_system_status()
            out.append(f"\n📊 **Health:** {status.get('overall_health','?')}")

            if status.get('classic_modules'):
                out.append("\n🔧 **Modulos Classicos:**")
                for m, s in status['classic_modules'].items():
                    icon = '✅' if s == 'active' else '⚠️'
                    out.append(f"   {icon} {m}: {s}")

            if status.get('smart_systems'):
                out.append("\n🧬 **Sistemas Inteligentes:**")
                for m, s in status['smart_systems'].items():
                    icon = '✅' if s == 'active' else '⚠️'
                    out.append(f"   {icon} {m}: {s}")

        except Exception as e:
            out.append(f"\n⚠️ Orquestrador indisponivel: {e}")
            # Fallback basico
            mods = {"pipeline":"quimera.pipeline","aegis":"quimera.aegis.aegis_core",
                    "agentes":"quimera.agentes.agente_base","bibliotecario":"quimera.bibliotecario"}
            for n,m in mods.items():
                try: __import__(m); out.append(f"   ✅ {n}")
                except: out.append(f"   ⚠️ {n}")

        pyf = sum(1 for _ in Path(self.project_root).rglob("*.py"))
        out.append(f"\n📂 {pyf} arquivos Python no projeto")
        return "🏥 **Quimera Health**\n" + "\n".join(out)

    def _do_audit(self, cmd: NLCommand) -> str:
        """Auditoria Aegis REAL — modulo nativo ou orquestrador."""
        target = cmd.target.strip()
        found = self._smart_find(target) if target else []
        if not found: return self._do_run(cmd)
        fp = found[0]
        full = os.path.join(self.project_root, fp)
        if not os.path.isfile(full): return f"❌ `{fp}`"

        # ═══ AEGIS REAL ═══
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            # Tenta carregar AegisCore
            try:
                from quimera.aegis.aegis_core import AegisCore
                aegis = AegisCore()
                code = open(full, errors="ignore").read()
                result = aegis.scan(code) if hasattr(aegis, 'scan') else aegis.analyze(code) if hasattr(aegis, 'analyze') else str(dir(aegis))

                out = [f"🛡️ **Aegis Security Audit** (EXECUCAO REAL)",
                       f"📄 `{fp}` | {len(code)} bytes", f"{'='*50}"]

                if isinstance(result, dict):
                    if 'vulnerabilities' in result:
                        out.append(f"\n⚠️ **{len(result['vulnerabilities'])} vulnerabilidades:**")
                        for v in result['vulnerabilities'][:8]:
                            out.append(f"   • {v}")
                    if 'score' in result:
                        out.append(f"\n🏆 **Score:** {result['score']}")
                    for k, v in result.items():
                        if k not in ('vulnerabilities', 'score') and isinstance(v, (str, int, float)):
                            out.append(f"   {k}: {v}")
                else:
                    out.append(f"\n{str(result)[:2000]}")
                return "\n".join(out)

            except ImportError:
                # Tenta via orquestrador
                from quimera.quimera_master import execute_intelligent_task
                result = execute_intelligent_task("smart_analysis", target=full, analysis_type="security")
                return f"🛡️ **Aegis via Orquestrador**\n📄 `{fp}`\n{'='*50}\n{str(result)[:2000]}"

        except Exception as e:
            logger.warning(f"Aegis indisponivel: {e}")

        # ═══ FALLBACK ═══
        content = self._read_file(fp)
        if not content or content.startswith("📁"): return f"❌ `{fp}`"
        if not self.available: return f"🛡️ Aegis indisponivel.\n   Execute: python -m quimera audit {fp}"
        return self._deep_review(fp, content)
    def _do_chat(self, cmd: NLCommand) -> str:
        """Responde pergunta geral usando Groq LLM."""
        if not self.available:
            return self._do_help(cmd)
        msg = self._msg_original or cmd.target or ''
        if not msg or len(msg) < 2:
            return self._do_help(cmd)
        try:
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps({
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "Voce e o QUIMERA, plataforma autonoma de engenharia de codigo em Termux. NAO e assistente — e o COMANDANTE. Ferramentas: Pipeline H1-H6, Aegis, 20+ agentes, Bibliotecario, Memoria, Validadores. Quando usuario pedir algo, sugira usar o Quimera. Seja ACAO-ORIENTADO, DIRETO e CONCISO em portugues."},
                        {"role": "user", "content": msg},
                    ],
                    "temperature": 0.5, "max_tokens": 800,
                }).encode(),
                headers={"Authorization": f"Bearer {self.api_key}",
                         "Content-Type": "application/json",
                         "User-Agent": "Quimera/5.4"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"Chat fallback: {e}")
            return self._do_help(cmd)

    # ── HELP ──────────────────────────────────────────────

    def _do_help(self, cmd: NLCommand = None) -> str:
        return """🤖 **Quimera Assistant** — IA de verdade com Groq!

**Comandos:**
  • "analise o <componente>" → explica qualquer arquivo
  • "busca por <termo>" → procura arquivos por nome
  • "cadastra chave groq <chave>" → salva API key
  • "cadastra chave gemini <chave>" → Gemini
  • "cadastra chave openrouter <chave>" → OpenRouter
  • "o que faz o pipeline.py?" → analise de arquivo

**Exemplos:**
  quimera assist "analise o agente analista"
  quimera assist "busca por sqlalchemy"
  quimera assist "cadastra chave groq gsk_abc123"

💡 Com Groq API configurada, eu entendo frases completas!"""


groq_assistant = GroqAssistant()
if groq_assistant.available:
    print(f"✅ GroqAssistant: disponivel ({groq_assistant.model})")
else:
    print(f"⚠️  GroqAssistant: sem API key - defina GROQ_API_KEY no .env")
