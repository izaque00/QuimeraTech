"""
Mission Interpreter Neural — TheAnd's "Jarvis"

Replaces regex-based intent classifier with a lightweight LLM that:
  1. Understands free-form Portuguese (also English, Spanish)
  2. Extracts mission, project type, actions, and context
  3. Returns structured JSON the Planner + Orchestrator can consume

Architecture:
  User message (free form)
        ↓
  LLM (local 1-8B or cloud fallback)  ← understands intent, NOT code
        ↓
  Structured Mission JSON
        ↓
  Planner.decompose_mission()
        ↓
  Orchestrator pipeline

The LLM does NOT generate code. It only translates natural language → JSON.
"""
import os, json, re
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class MissionIntent:
    """Structured mission extracted from natural language."""
    mission: str = ""          # 'build_project', 'fix_error', 'analyze_code', etc.
    project_type: str = ""     # 'kernel', 'cmake', 'make', 'cargo', 'meson', etc.
    project_path: str = ""     # path to project root
    actions: List[str] = field(default_factory=list)
    error_context: str = ""    # error message or symptom
    compiler: str = ""         # gcc, clang, etc.
    architecture: str = ""     # x86_64, arm64, etc.
    sanitizers: List[str] = field(default_factory=list)  # kasan, ubsan, asan
    model_preference: str = "" # 'free', 'best', 'fastest'
    confidence: float = 0.0


class MissionInterpreter:
    """
    Neural interpreter: natural language → structured mission.

    Uses a small LLM (local or cloud) to understand free-form text
    and extract mission parameters. Falls back to keyword-based extraction
    if no LLM is available.

    The LLM prompt is engineered for intent extraction ONLY —
    not code generation, not reasoning, not patching.
    """

    SYSTEM_PROMPT = """You are a mission interpreter for TheAnd, an autonomous software engineering platform.

Your ONLY job: extract structured mission parameters from natural language text.
Return a JSON object with these fields:
{
  "mission": "build_project" | "fix_error" | "analyze_code" | "enable_sanitizer" | 
             "register_api_key" | "select_model" | "port_driver" | "update_library" |
             "custom_command" | "explain_error",
  "project_type": "kernel" | "cmake" | "make" | "cargo" | "meson" | "bazel" | "unknown",
  "project_path": "path if mentioned, else empty string",
  "actions": ["list", "of", "actions"],
  "error_context": "error message or symptom if user mentions a problem",
  "compiler": "gcc" | "clang" | "msvc" | "",
  "architecture": "x86_64" | "arm64" | "riscv" | "",
  "sanitizers": ["kasan", "ubsan", "asan"] if mentioned,
  "model_preference": "free" | "best" | "fastest" | "",
  "confidence": 0.0-1.0
}

RULES:
- If user mentions "KASAN", "kernel", "bootloop", "panico", "panic" → mission="enable_sanitizer" or "fix_error"
- If user mentions "compilar", "compile", "build", "make" → mission="build_project"
- If user mentions "erro", "error", "falha", "segfault", "crash" → mission="fix_error"
- If user mentions "chave", "key", "api", "token" → mission="register_api_key"
- If user mentions "melhor modelo", "best model" → mission="select_model"
- If user mentions "atualizar", "update", "upgrade", "port" → mission="update_library"
- If the message contains an API key (sk-or-v1..., sk-ant..., etc.) → extract it
- Be conservative: confidence=0.9+ if clear, 0.5-0.7 if ambiguous
- Return ONLY the JSON object, no other text."""

    # ── Fallback keyword extraction (no LLM needed) ────
    KEYWORD_MISSIONS = {
        'build_project': [
            r'(?:compil|build|make)\w*\s+(?:o\s+)?(?:projeto|project|kernel|codigo|code)',
            r'(?:compil|build|make)\s+(?:kernel|linux|projeto)',
            r'build\s+(?:the\s+)?(?:kernel|project|code)',
            r'(?:compila|builda)\s+(?:isso|esse|este|ate|até)\s+(?:funcionar|dar\s+certo)',
            r'quero\s+(?:compilar|buildar|fazer\s+build)\s+(?:o\s+)?(?:kernel|projeto|codigo)',
        ],
        'fix_error': [
            r'(?:corrig|consert|arrum|fix|repair)\w*\s+(?:erro|error|bug|falha|problema)',
            r'(?:meu|my|o)\s+(?:codigo|code|kernel|projeto)\s+(?:esta|está|ta|is)\s+(?:dando|com|with)\s+(?:erro|error|bug)',
            r'(?:segfault|segmentation\s+fault|bootloop|panico|panic|crash|travou|travando)',
            r'(?:nao|não|not)\s+(?:compila|compiling|builda|building)',
            r'parou\s+de\s+(?:compilar|funcionar)',
            r'(?:resolve|resolva|corrige|fix)\s+(?:esse|este|o)\s+(?:erro|problema|bug)',
            r'(?:kernel|driver|modulo)\s+(?:esta|deu|entrou)\s+(?:em|no)\s+(?:panico|panic|bootloop)',
        ],
        'analyze_code': [
            r'(?:analis|analyz|analis)\w*\s+(?:codigo|code|kernel|projeto|project)',
            r'(?:scan|escanear|verificar)\s+(?:codigo|code|vulnerab)',
            r'quero\s+(?:analisar|entender|ver)\s+(?:o\s+)?(?:codigo|code)',
        ],
        'enable_sanitizer': [
            r'(?:ativ|enable|lig|turn\s+on)\w*\s+(?:kasan|ubsan|asan|sanitizer)',
            r'(?:kasan|ubsan|asan|kcov)\s+(?:no|em|no|on|in)\s+(?:kernel|meu|my)',
            r'quero\s+(?:ativar|compilar\s+com)\s+(?:kasan|ubsan|asan)',
        ],
        'register_api_key': [
            r'(?:cadastr|registr|adicionar|register|add).*?(?:chave|key|api)',
            r'(?:sk-or-v1|sk-ant|sk-proj|AIza|gsk_|fw_|hf_)[\w\-]{12,}',
        ],
        'select_model': [
            r'(?:melhor|best|ideal|recomend)\s+(?:modelo|model|ia|llm)',
            r'qual\s+(?:modelo|ia|llm)\s+(?:usar|escolher|para)',
        ],
        'update_library': [
            r'(?:atualiz|updat|upgrad)\w*\s+(?:biblioteca|library|lib|driver)',
            r'port\w*\s+(?:driver|library|lib)',
        ],
        'explain_error': [
            r'(?:explica|explain|entender|understand)\w*\s+(?:erro|error|isso|this)',
            r'o\s+que\s+(?:significa|é|e)\s+(?:esse|este|o)\s+(?:erro|error)',
        ],
        'analyze_code': [
            r'(?:analis|analyz|analis)\w*\s+(?:codigo|code|kernel|projeto|project)',
            r'(?:scan|escanear|verificar)\s+(?:codigo|code|vulnerab)',
            r'quero\s+(?:analisar|entender|ver)\s+(?:o\s+)?(?:codigo|code)',
            r'(?:analis|analyz)\w*\s+(?:esse|este|o)\s+(?:zip|arquivo|projeto|driver|kernel)',
            r'(?:analis|analyz)\w*\s+(?:inteiro|todo|completo)',
        ],
    }

    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm
        self._llm = None

    def _get_llm(self):
        """Lazy-load LLM interface."""
        if self._llm is None:
            try:
                from quimera.candidate_generator import LLMInterface
                self._llm = LLMInterface()
            except Exception:
                self._llm = False
        return self._llm if self._llm is not False else None

    def interpret(self, user_message: str) -> MissionIntent:
        """
        Interpret free-form natural language into a structured mission.

        Args:
            user_message: "Meu kernel deu bootloop depois do KASAN"

        Returns:
            MissionIntent with mission, project_type, actions, etc.
        """
        msg = user_message.strip()

        # Try neural interpretation first
        if self.use_llm:
            result = self._interpret_neural(msg)
            if result and result.confidence >= 0.5:
                return result

        # Fallback: keyword-based extraction
        return self._interpret_keywords(msg)

    def _interpret_neural(self, msg: str) -> Optional[MissionIntent]:
        """Use LLM to interpret the message."""
        llm = self._get_llm()
        if not llm:
            return None

        try:
            prompt = f"User message: {msg}\n\nExtract the mission:"
            response = llm.generate(
                system=self.SYSTEM_PROMPT,
                prompt=prompt,
                max_tokens=300,
                temperature=0.1  # low temp for structured output
            )

            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                return MissionIntent(
                    mission=data.get('mission', ''),
                    project_type=data.get('project_type', ''),
                    project_path=data.get('project_path', ''),
                    actions=data.get('actions', []),
                    error_context=data.get('error_context', ''),
                    compiler=data.get('compiler', ''),
                    architecture=data.get('architecture', ''),
                    sanitizers=data.get('sanitizers', []),
                    model_preference=data.get('model_preference', ''),
                    confidence=data.get('confidence', 0.5),
                )
        except Exception:
            pass

        return None

    def _interpret_keywords(self, msg: str) -> MissionIntent:
        """Keyword-based fallback interpretation."""
        msg_lower = msg.lower()

        # Detect mission type
        best_mission = 'custom_command'
        best_confidence = 0.0

        for mission, patterns in self.KEYWORD_MISSIONS.items():
            for pattern in patterns:
                if re.search(pattern, msg_lower):
                    confidence = 0.7 if len(pattern) > 20 else 0.5
                    if confidence > best_confidence:
                        best_mission = mission
                        best_confidence = confidence

        # Detect project type
        project_type = 'unknown'
        if any(w in msg_lower for w in ['kernel', 'linux', 'kbuild', 'kconfig', 'kasan', 'ubsan', 'kcov']):
            project_type = 'kernel'
        elif any(w in msg_lower for w in ['driver', 'modulo', 'módulo', 'pci', 'usb', 'i2c', 'spi']):
            project_type = 'kernel'
        elif any(w in msg_lower for w in ['cmake', 'cmakelists']):
            project_type = 'cmake'
        elif 'makefile' in msg_lower or 'make' in msg_lower:
            project_type = 'make'
        elif 'cargo' in msg_lower:
            project_type = 'cargo'
        elif 'meson' in msg_lower:
            project_type = 'meson'

        # Detect sanitizers
        sanitizers = []
        for san in ['kasan', 'ubsan', 'asan', 'kcov']:
            if san in msg_lower:
                sanitizers.append(san)

        # Detect compiler
        compiler = ''
        if 'clang' in msg_lower:
            compiler = 'clang'
        elif 'gcc' in msg_lower:
            compiler = 'gcc'

        # Detect architecture
        arch = ''
        for a in ['x86_64', 'arm64', 'aarch64', 'riscv', 'arm']:
            if a in msg_lower:
                arch = a
                break

        # Detect model preference
        model_pref = ''
        if 'gratuito' in msg_lower or 'gratis' in msg_lower or 'free' in msg_lower:
            model_pref = 'free'
        elif 'melhor' in msg_lower or 'best' in msg_lower:
            model_pref = 'best'
        elif 'rapido' in msg_lower or 'rápido' in msg_lower or 'fastest' in msg_lower:
            model_pref = 'fastest'

        # Build actions
        actions = []
        if best_mission == 'enable_sanitizer':
            actions = ['configure_sanitizer', 'build', 'verify']
        elif best_mission == 'build_project':
            actions = ['analyze', 'build', 'test']
        elif best_mission == 'fix_error':
            actions = ['detect', 'research', 'patch', 'validate', 'build']
        elif best_mission == 'analyze_code':
            actions = ['scan', 'report']
        elif best_mission == 'register_api_key':
            actions = ['register_key']
        elif best_mission == 'select_model':
            actions = ['list_models', 'recommend']
        elif best_mission == 'update_library':
            actions = ['fetch', 'diff', 'patch', 'build', 'test']
        elif best_mission == 'explain_error':
            actions = ['research', 'explain']

        # Extract error context
        error_ctx = ''
        err_match = re.search(r'(?:erro|error|segfault|panic|crash|falha)[:\s]*(.{10,100})', msg_lower)
        if err_match:
            error_ctx = err_match.group(1).strip()

        return MissionIntent(
            mission=best_mission,
            project_type=project_type,
            actions=actions,
            error_context=error_ctx,
            compiler=compiler,
            architecture=arch,
            sanitizers=sanitizers,
            model_preference=model_pref,
            confidence=best_confidence,
        )


# ── Backward compatibility ─────────────────────────────
# NaturalConfig now wraps MissionInterpreter + LLMConfig

class NaturalConfig:
    """
    High-level NL interface: interprets user messages and
    routes to either MissionInterpreter (for missions) or
    LLMConfig (for API key management).
    """

    def __init__(self):
        self.interpreter = MissionInterpreter()
        from quimera.llm_config import LLMConfig
        self.config = LLMConfig()

    def process(self, user_message: str) -> 'NLResponse':
        """
        Process a natural language message.

        Returns NLResponse with structured result.
        """
        # First, check if it's an API key registration
        api_key = self._extract_api_key(user_message)
        if api_key:
            return self._handle_api_key(user_message, api_key)

        # Check if it's a model query
        msg_lower = user_message.lower()
        api_patterns = [
            r'(?:mostr|list|ver|exibir|show)\w*\s+(?:meus\s+)?(?:modelos?|provedores?)',
            r'(?:qual|que)\s+(?:modelo|ia)\s+(?:e|é)\s+(?:melhor|bom|boa)',
            r'(?:test|verific)\w*\s+(?:conex|connection)',
        ]
        for p in api_patterns:
            if re.search(p, msg_lower):
                return self._handle_api_command(user_message)

        # Otherwise, interpret as a mission
        intent = self.interpreter.interpret(user_message)

        # Build response
        actions_str = ' → '.join(intent.actions) if intent.actions else 'analisar'
        emoji = {'build_project': '🔨', 'fix_error': '🔧', 'enable_sanitizer': '🛡️',
                 'analyze_code': '🔍', 'register_api_key': '🔑', 'select_model': '🤖',
                 'update_library': '📦', 'explain_error': '💡', 'custom_command': '⚡'}

        return NLResponse(
            success=True,
            action=intent.mission,
            message=(
                f"{emoji.get(intent.mission, '▶️')} **Missão: {intent.mission}**\n\n"
                f"📁 Projeto: {intent.project_type or 'auto-detectar'}\n"
                f"🔧 Ações: {actions_str}\n"
                f"{'🛡️ Sanitizers: ' + ', '.join(intent.sanitizers).upper() if intent.sanitizers else ''}"
                f"{chr(10) + '⚠️ Erro: ' + intent.error_context if intent.error_context else ''}"
                f"{chr(10) + '🔌 Compiler: ' + intent.compiler if intent.compiler else ''}"
                f"{chr(10) + '💻 Arch: ' + intent.architecture if intent.architecture else ''}"
                f"\n\n🎯 Confiança: {intent.confidence:.0%}"
            ),
            data={
                'mission': intent.mission,
                'project_type': intent.project_type,
                'actions': intent.actions,
                'sanitizers': intent.sanitizers,
                'confidence': intent.confidence,
            }
        )

    def _extract_api_key(self, text: str) -> Optional[str]:
        patterns = [
            r'(sk-or-v1[a-zA-Z0-9\-]{12,})',
            r'(sk-ant[a-zA-Z0-9\-]{12,})',
            r'(sk-proj[a-zA-Z0-9\-]{12,})',
            r'(gsk_[a-zA-Z0-9]{12,})',
            r'(AIza[A-Za-z0-9\-_]{30,})',
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                return m.group(1)
        return None

    def _handle_api_key(self, msg: str, key: str) -> 'NLResponse':
        provider = self._detect_provider(key)
        if provider in self.config.providers:
            ok, detail = self.config.register_key(provider, key)
            return NLResponse(
                success=ok, action='register_api_key',
                message=f"{'✅' if ok else '❌'} {detail}"
            )
        return NLResponse(
            success=False, action='register_api_key',
            message=f"Chave detectada mas provedor **{provider}** não suportado."
        )

    def _detect_provider(self, key: str) -> str:
        if key.startswith('sk-or-v1'): return 'openrouter'
        if key.startswith('sk-ant'): return 'anthropic'
        if key.startswith('sk-proj'): return 'openai'
        if key.startswith('gsk_'): return 'groq'
        if key.startswith('AIza'): return 'google'
        return 'openrouter'

    def _handle_api_command(self, msg: str) -> 'NLResponse':
        status = self.config.list_keys()
        lines = ["**Provedores configurados:**\n"]
        for s in status:
            icon = "✅" if s.configured and s.tested else "❌"
            lines.append(f"{icon} **{s.name}**: {s.models_available} modelos")
        return NLResponse(
            success=True, action='list_models',
            message='\n'.join(lines)
        )


@dataclass
class NLResponse:
    success: bool
    message: str
    action: str = ""
    data: Dict = None
