"""
Quimera Mark X — LLM Adviser (Mind Enhancement)

Optional LLM layer for the Mind. NOT the core — an adviser that
the Mind consults only when needed:

  - Input is ambiguous → LLM helps disambiguate
  - User wants detailed explanation → LLM generates it
  - Creative refactoring suggestion needed → LLM proposes
  - Complex error translation → LLM explains in human terms

The LLM NEVER executes code, deploys, or modifies files.
All LLM output is validated through the deterministic pipeline (sandbox + H3 verification).

Supports:
  - Local Llama 70B (via Ollama)
  - OpenAI API (GPT-4o, GPT-4o-mini)
  - Anthropic Claude API
  - Groq (fast inference)
  - HuggingFace TGI endpoint
  - Deterministic fallback (when LLM unavailable)

Usage:
    adviser = LLMAdviser(provider="ollama", model="llama3:70b")
    
    # Consult when Mind confidence is LOW
    if thought.confidence == Confidence.LOW:
        suggestion = await adviser.consult(thought, context)
    
    # Generate explanation
    explanation = await adviser.explain(issue, audience="developer")
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("quimera.mind.llm")



class LLMProvider(str, Enum):
    OLLAMA = "ollama"           # Local Llama/Mistral via Ollama
    OPENAI = "openai"          # GPT-4o / GPT-4o-mini
    ANTHROPIC = "anthropic"    # Claude Sonnet
    GROQ = "groq"              # Fast inference
    HUGGINGFACE = "huggingface"  # TGI endpoint
    NONE = "none"              # Deterministic only


@dataclass
class LLMConfig:
    provider: LLMProvider = LLMProvider.NONE
    model: str = ""
    endpoint: str = ""          # For Ollama/HuggingFace
    api_key: Optional[str] = None
    max_tokens: int = 2048
    temperature: float = 0.3
    timeout_seconds: int = 30
    fallback_to_deterministic: bool = True


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    tokens_used: int
    latency_ms: float
    from_cache: bool = False
    error: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════
# LLM Adviser
# ═══════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════
# Multi-Provider Router — loads KEYS from .env, delegates to multi_llm_orchestrator
# ═══════════════════════════════════════════════════════════════════════════

class MultiProviderRouter:
    """Carrega ~11 chaves API do .env e alterna entre provedores automaticamente.
    
    Usa o multi_llm_orchestrator.py (36KB) existente para cada chamada,
    mas com roteamento inteligente de chaves.
    """
    
    PROVIDER_KEY_PREFIXES = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
        "groq": "GROQ_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "together": "TOGETHER_API_KEY",
        "mistral": "MISTRAL_API_KEY",
        "cohere": "COHERE_API_KEY",
        "fireworks": "FIREWORKS_API_KEY",
        "huggingface": "HUGGINGFACE_API_KEY",
    }
    
    FREE_TIER = ["groq", "google", "deepseek", "ollama", "huggingface"]
    
    def __init__(self):
        self.keys: Dict[str, List[str]] = {}
        self._load_all_keys()
    
    def _load_all_keys(self):
        for provider, prefix in self.PROVIDER_KEY_PREFIXES.items():
            for i in range(1, 20):
                key = os.getenv(f"{prefix}_{i}")
                if key and not key.startswith("sk-...") and key.strip():
                    self.keys.setdefault(provider, []).append(key)
        # Ollama local (no key needed)
        ollama_ep = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")
        self.keys["ollama"] = [ollama_ep]
        
        total = sum(len(v) for v in self.keys.values())
        providers = list(self.keys.keys())
        logger.info(f"MultiProviderRouter: {total} keys across {len(providers)} providers: {providers}")
    
    def get_provider_order(self) -> List[str]:
        """Free tier first, then paid."""
        order = []
        for p in self.FREE_TIER + list(self.PROVIDER_KEY_PREFIXES.keys()) + ["ollama"]:
            if p in self.keys and self.keys[p]:
                order.append(p)
        # Deduplicate
        seen = set()
        return [p for p in order if not (p in seen or seen.add(p))]
    
    async def route(self, messages: List[Dict], task_type: str = "advise") -> Dict:
        """Roteia por todos os provedores até um responder."""
        provider_order = self.get_provider_order()
        
        for provider in provider_order:
            for key in self.keys[provider]:
                try:
                    result = await self._call_provider(provider, key, messages)
                    if result:
                        return result
                except Exception:
                    continue
        
        # Fallback: Ollama local
        if "ollama" in self.keys:
            result = await self._call_ollama(self.keys["ollama"][0], messages)
            if result: return result
        
        return {"content": "[Todos provedores esgotados]", "model": "fallback", "usage": {}}
    
    async def _call_provider(self, provider: str, api_key: str, messages: List[Dict]) -> Dict:
        import aiohttp
        
        # OpenAI-compatible endpoints
        endpoints = {
            "openai": ("https://api.openai.com/v1/chat/completions", "gpt-4o-mini"),
            "groq": ("https://api.groq.com/openai/v1/chat/completions", "llama-3.3-70b-versatile"),
            "deepseek": ("https://api.deepseek.com/v1/chat/completions", "deepseek-chat"),
            "together": ("https://api.together.xyz/v1/chat/completions", "mistralai/Mixtral-8x7B-Instruct-v0.1"),
            "fireworks": ("https://api.fireworks.ai/inference/v1/chat/completions", "accounts/fireworks/models/llama-v3p1-70b-instruct"),
            "mistral": ("https://api.mistral.ai/v1/chat/completions", "mistral-large-latest"),
            "cohere": ("https://api.cohere.ai/v1/chat", "command-r-plus"),
        }
        
        if provider in endpoints:
            url, model = endpoints[provider]
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {"model": model, "messages": messages, "temperature": 0.3, "max_tokens": 2048}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {"content": data["choices"][0]["message"]["content"], "model": data.get("model", model), "usage": data.get("usage", {})}
                    elif resp.status == 429:
                        raise RateLimitError(f"429 {provider}")
        
        if provider == "anthropic":
            return await self._call_anthropic(api_key, messages)
        if provider == "google":
            return await self._call_google(api_key, messages)
        if provider == "ollama":
            return await self._call_ollama(api_key, messages)
        
        return None
    
    async def _call_ollama(self, endpoint: str, messages: List[Dict]) -> Dict:
        import aiohttp
        payload = {"model": "qwen3", "messages": messages, "stream": False}
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{endpoint}/api/chat", json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {"content": data["message"]["content"], "model": "ollama", "usage": {"total_tokens": data.get("eval_count", 0)}}
    
    async def _call_anthropic(self, api_key: str, messages: List[Dict]) -> Dict:
        import aiohttp
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
        payload = {"model": "claude-sonnet-4-20250514", "max_tokens": 2048, "messages": messages}
        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {"content": data["content"][0]["text"], "model": data.get("model", "claude"), "usage": data.get("usage", {})}
    
    async def _call_google(self, api_key: str, messages: List[Dict]) -> Dict:
        import aiohttp
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
        contents = [{"parts": [{"text": m["content"]}]} for m in messages if m.get("content")]
        payload = {"contents": contents}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {"content": data["candidates"][0]["content"]["parts"][0]["text"], "model": "gemini", "usage": {}}
    
    def get_stats(self) -> Dict:
        return {
            "providers": {p: len(ks) for p, ks in self.keys.items()},
            "total_keys": sum(len(v) for v in self.keys.values()),
            "free_tier_first": True,
        }

class RateLimitError(Exception):
    pass


class LLMAdviser:
    """Optional LLM layer — adviser, not executor.

    The Mind remains fully operational without this.
    LLM provides natural language understanding for edge cases.
    """

    def __init__(
        self,
        provider: str = "none",
        model: str = "",
        endpoint: str = "http://localhost:11434",
        api_key: Optional[str] = None,
        temperature: float = 0.3,
    ):
        self.config = LLMConfig(
            provider=LLMProvider(provider) if provider != "none" else LLMProvider.NONE,
            model=model,
            endpoint=endpoint,
            api_key=api_key,
            temperature=temperature,
        )
        self._cache: Dict[str, LLMResponse] = {}
        self._total_calls = 0
        self._total_tokens = 0
        self._total_latency = 0.0
        self._available = False

        # Multi-Provider Router — carrega chaves do .env
        self._router = MultiProviderRouter()
        logger.info(f"LLMAdviser: Router enabled — {self._router.get_stats()['total_keys']} keys")
        self._use_router = provider == "auto" or provider == "none"

        if self.config.provider != LLMProvider.NONE:
            logger.info(f"LLMAdviser: {provider}/{model or 'default'} at {endpoint}")
        else:
            logger.info("LLMAdviser: deterministic mode (no LLM)")

    # ── Health Check ────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        """Check if LLM is reachable."""
        if self.config.provider == LLMProvider.NONE:
            self._available = False
            return False

        try:
            # Use Multi-Provider Router (auto-fallback across all .env keys)
            if self._use_router:
                messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
                result = await self._router.route(messages, task_type="advise")
                response = LLMResponse(
                    text=result.get("content", ""),
                    provider=result.get("model", "router"),
                    model=result.get("model", "auto"),
                    tokens_used=result.get("usage", {}).get("total_tokens", 0),
                    latency_ms=0,
                )
            elif self.config.provider == LLMProvider.OLLAMA:
                # Ollama health check
                import urllib.request
                url = f"{self.config.endpoint}/api/tags"
                req = urllib.request.Request(url, headers={"User-Agent": "Quimera/3.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read())
                    models = [m["name"] for m in data.get("models", [])]
                    self._available = any(self.config.model in m for m in models)
                    logger.info(f"LLMAdviser: Ollama available — {len(models)} models")
            else:
                # Simple API ping
                self._available = True
        except Exception as e:
            self._available = False
            logger.warning(f"LLMAdviser: unavailable ({e})")

        return self._available

    # ── Consult ─────────────────────────────────────────────────────────

    async def consult(self, prompt: str, context: Optional[Dict] = None) -> LLMResponse:
        """Consult the LLM for advice. Used when Mind confidence is LOW."""
        if not self._available:
            return LLMResponse(
                text=self._deterministic_fallback(prompt, context),
                provider="deterministic",
                model="none",
                tokens_used=0,
                latency_ms=0,
                error="LLM unavailable — using deterministic fallback",
            )

        # Build system prompt
        system = self._build_system_prompt(context)

        t0 = time.monotonic()
        self._total_calls += 1

        try:
            # Use Multi-Provider Router (auto-fallback across all .env keys)
            if self._use_router:
                messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
                result = await self._router.route(messages, task_type="advise")
                response = LLMResponse(
                    text=result.get("content", ""),
                    provider=result.get("model", "router"),
                    model=result.get("model", "auto"),
                    tokens_used=result.get("usage", {}).get("total_tokens", 0),
                    latency_ms=0,
                )
            elif self.config.provider == LLMProvider.OLLAMA:
                response = await self._call_ollama(system, prompt)
            elif self.config.provider == LLMProvider.OPENAI:
                response = await self._call_openai(system, prompt)
            elif self.config.provider == LLMProvider.ANTHROPIC:
                response = await self._call_anthropic(system, prompt)
            elif self.config.provider == LLMProvider.GROQ:
                response = await self._call_groq(system, prompt)
            else:
                response = LLMResponse(
                    text=self._deterministic_fallback(prompt, context),
                    provider="deterministic",
                    model="none",
                    tokens_used=0,
                    latency_ms=0,
                )
        except Exception as e:
            logger.error(f"LLMAdviser: call failed — {e}")
            response = LLMResponse(
                text=self._deterministic_fallback(prompt, context),
                provider="deterministic",
                model="fallback",
                tokens_used=0,
                latency_ms=0,
                error=str(e)[:200],
            )

        elapsed = (time.monotonic() - t0) * 1000
        response.latency_ms = round(elapsed, 1)
        self._total_latency += elapsed
        self._total_tokens += response.tokens_used

        return response

    # ── Adviser (structured tool selection) ────────────────────────────

    async def advise(self, context: Dict) -> Optional[Dict]:
        """Consult LLM for tool selection advice.
        
        Called by Mind._consult_llm() when deterministic confidence is low.
        Returns structured JSON with tools, confidence, and reasoning.
        The Mind VALIDATES every tool before using it.
        
        Args:
            context: {
                "user_input": str,
                "deterministic_plan": {"intent", "confidence", "tools", "reasoning"},
                "codebase": {"files", "symbols"},
                "pending_issues": [...],
                "available_tools": ["genetic_evolve", "z3_verify_patch", ...],
            }
        
        Returns:
            {"tools": ["genetic_evolve", "sandbox_execute"],
             "confidence": "high",
             "reasoning": "...",
             "expected_outcome": "..."}
            or None if LLM unavailable
        """
        if not self._available:
            return None

        available_tools = context.get("available_tools", [])
        deterministic = context.get("deterministic_plan", {})
        user_input = context.get("user_input", "")
        issues = context.get("pending_issues", [])

        prompt = f"""Problem: {user_input[:500]}

Deterministic plan:
- Intent: {deterministic.get('intent', 'unknown')}
- Confidence: {deterministic.get('confidence', 'unknown')}
- Tools selected: {deterministic.get('tools', [])}
- Reasoning: {deterministic.get('reasoning', '')[:200]}

Detected issues: {json.dumps(issues[:3])}

Available tools (H1-H6):
{json.dumps(available_tools)}"""

        system = f"""{self._build_system_prompt(None)}

You are advising the QuimeraMind on which tools to use for a given problem.
Respond ONLY with a JSON object:
{{
  "tools": ["tool_name_1", "tool_name_2"],
  "confidence": "high|medium|low|uncertain",
  "reasoning": "brief explanation of why these tools",
  "expected_outcome": "what should happen after execution"
}}

Rules:
1. ONLY suggest tools from the "Available tools" list
2. Max 3 tools
3. If you're unsure, set confidence to "low"
4. Never suggest tools that don't exist"""

        t0 = time.monotonic()
        self._total_calls += 1

        try:
            if self.config.provider == LLMProvider.OLLAMA:
                response = await self._call_ollama(system, prompt, json_mode=True)
            elif self.config.provider == LLMProvider.OPENAI:
                response = await self._call_openai(system, prompt, json_mode=True)
            else:
                response = LLMResponse(
                    text=json.dumps({"tools": [], "confidence": "low", "reasoning": "No LLM available"}),
                    provider="deterministic", model="none", tokens_used=0, latency_ms=0,
                )

            elapsed = (time.monotonic() - t0) * 1000
            self._total_latency += elapsed
            self._total_tokens += response.tokens_used

            # Parse JSON from response
            text = response.text.strip()
            # Handle markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            try:
                result = json.loads(text)
                # Validate structure
                if "tools" not in result or not isinstance(result["tools"], list):
                    logger.warning("LLMAdviser: invalid response structure — missing 'tools'")
                    return None
                return result
            except json.JSONDecodeError:
                logger.warning(f"LLMAdviser: failed to parse JSON from LLM response")
                return None

        except Exception as e:
            logger.warning(f"LLMAdviser: advise() failed — {e}")
            return None

    # ── Specialized Queries ─────────────────────────────────────────────

    async def explain_issue(self, issue: Dict, audience: str = "developer") -> LLMResponse:
        """Explain a detected issue in human language."""
        prompt = f"""Explain this code issue to a {audience}:

Issue Type: {issue.get('type', 'unknown')}
Severity: {issue.get('severity', 'unknown')}
File: {issue.get('file_path', 'unknown')}
Line: {issue.get('line_number', '?')}
Description: {issue.get('description', 'No description')}

Explain:
1. What is the problem? (in simple terms)
2. Why is it dangerous? (impact)
3. How would you fix it? (concrete steps)
4. How to prevent it in the future?

Keep it concise and actionable."""
        return await self.consult(prompt)

    async def suggest_refactoring(self, code: str, language: str = "c") -> LLMResponse:
        """Suggest creative refactoring options."""
        prompt = f"""Suggest refactoring improvements for this {language} code.
Focus on safety, readability, and performance. Be specific.

```{language}
{code[:3000]}
```

Provide 2-3 concrete suggestions with code examples."""
        return await self.consult(prompt)

    async def translate_error(self, error_output: str) -> LLMResponse:
        """Translate compiler/runtime error into human explanation."""
        prompt = f"""Translate this error message into a clear, actionable explanation:

```
{error_output[:2000]}
```

Explain:
1. What went wrong?
2. Where exactly is the problem?
3. What's the most likely fix?
4. Is this a common pattern? (if so, what's the standard solution?)"""
        return await self.consult(prompt)

    async def generate_report(self, stats: Dict) -> LLMResponse:
        """Generate a human-readable report from mind stats."""
        prompt = f"""Generate a concise system health report from these metrics:

{json.dumps(stats, indent=2, default=str)[:3000]}

Create a brief executive summary (2-3 sentences) followed by:
- Critical issues (if any)
- Recommendations
- Overall health assessment"""
        return await self.consult(prompt)

    # ── Backend Implementations ─────────────────────────────────────────

    async def _call_ollama(self, system: str, prompt: str, json_mode: bool = False) -> LLMResponse:
        """Call Ollama API."""
        try:
            import urllib.request
            payload = json.dumps({
                "model": self.config.model,
                "system": system,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.config.temperature,
                    "num_predict": self.config.max_tokens,
                },
            }).encode()
            req = urllib.request.Request(
                f"{self.config.endpoint}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "Quimera/3.0"},
            )
            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
                data = json.loads(resp.read())
                return LLMResponse(
                    text=data.get("response", ""),
                    provider="ollama",
                    model=self.config.model,
                    tokens_used=data.get("eval_count", 0),
                    latency_ms=0,
                )
        except Exception as e:
            raise RuntimeError(f"Ollama call failed: {e}")

    async def _call_openai(self, system: str, prompt: str) -> LLMResponse:
        """Call OpenAI API."""
        try:
            import urllib.request
            payload = json.dumps({
                "model": self.config.model or "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
            }).encode()
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.config.api_key}",
                    "User-Agent": "Quimera/3.0",
                },
            )
            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
                data = json.loads(resp.read())
                choice = data["choices"][0]
                return LLMResponse(
                    text=choice["message"]["content"],
                    provider="openai",
                    model=data.get("model", "unknown"),
                    tokens_used=data.get("usage", {}).get("total_tokens", 0),
                    latency_ms=0,
                )
        except Exception as e:
            raise RuntimeError(f"OpenAI call failed: {e}")

    async def _call_anthropic(self, system: str, prompt: str) -> LLMResponse:
        """Call Anthropic API."""
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY_1"))
            response = await asyncio.to_thread(
                client.messages.create,
                model=self.config.model or "claude-sonnet-4-20250514",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            return LLMResponse(
                text=response.content[0].text, provider="anthropic",
                model=response.model,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                latency_ms=0,
            )
        except Exception as e:
            logger.warning(f"Anthropic call failed, using fallback: {e}")
            return LLMResponse(
                text=self._deterministic_fallback(prompt, None),
                provider="anthropic", model="fallback",
                tokens_used=0, latency_ms=0,
            )

    async def _call_groq(self, system: str, prompt: str) -> LLMResponse:
        """Call Groq API (OpenAI-compatible, fast inference)."""
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            logger.warning("GROQ_API_KEY not set, using fallback")
            return LLMResponse(
                text=self._deterministic_fallback(prompt, None),
                provider="groq", model="fallback",
                tokens_used=0, latency_ms=0,
            )
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "Quimera/3.0",
            }
            body = json.dumps({
                "model": self.config.model or "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": self.config.max_tokens or 2048,
                "temperature": self.config.temperature or 0.2,
            }).encode("utf-8")
            req = urllib.request.Request(url, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
                data = json.loads(resp.read())
                choice = data["choices"][0]
                return LLMResponse(
                    text=choice["message"]["content"],
                    provider="groq",
                    model=data.get("model", "llama-3.3-70b-versatile"),
                    tokens_used=data.get("usage", {}).get("total_tokens", 0),
                    latency_ms=0,
                )
        except Exception as e:
            logger.warning(f"Groq call failed, using fallback: {e}")
            return LLMResponse(
                text=self._deterministic_fallback(prompt, None),
                provider="groq", model="fallback",
                tokens_used=0, latency_ms=0,
            )

    # ── Deterministic Fallback ──────────────────────────────────────────

    def _deterministic_fallback(self, prompt: str, context: Optional[Dict]) -> str:
        """Generate response without LLM — using heuristics and templates."""
        prompt_lower = prompt.lower()

        if "explain" in prompt_lower and "issue" in prompt_lower:
            return self._template_explain_issue(context or {})
        elif "refactor" in prompt_lower:
            return self._template_refactoring()
        elif "error" in prompt_lower and "translate" in prompt_lower:
            return self._template_error_translation()
        elif "report" in prompt_lower:
            return self._template_report()
        else:
            return self._template_general(prompt)

    def _template_explain_issue(self, ctx: Dict) -> str:
        t = ctx.get("type", "unknown")
        desc = ctx.get("description", "No details")
        return (
            f"Issue: {t}\n"
            f"Description: {desc}\n"
            f"This was detected by the Quimera SelfAwareness system.\n"
            f"Recommendation: Run genetic evolution (H4) with formal verification (H3) to auto-fix.\n"
            f"Use 'mind.process(\"fix {t}\")' to attempt autonomous repair."
        )

    def _template_refactoring(self) -> str:
        return (
            "Refactoring suggestions (deterministic):\n"
            "1. Replace unsafe functions (strcpy→strncpy, sprintf→snprintf)\n"
            "2. Add NULL checks before pointer dereferences\n"
            "3. Use bounded loops with explicit size limits\n"
            "Run 'genetic_evolve' for automated optimization."
        )

    def _template_error_translation(self) -> str:
        return "Error translation: Use 'mind.process(\"explain this error: ...\")' with the full error output for analysis."

    def _template_report(self) -> str:
        return "System report: Run 'mind.process(\"status\")' for a comprehensive health check across all 6 horizons."

    def _template_general(self, prompt: str) -> str:
        return (
            f"QuimeraMind analyzed: '{prompt[:100]}...'\n"
            f"The Mind operates deterministically across H1-H6.\n"
            f"For complex natural language tasks, connect an LLM via LLMAdviser.\n"
            f"Available actions: repair, analyze, secure, optimize, deploy, status."
        )

    # ── Prompt Building ─────────────────────────────────────────────────

    def _build_system_prompt(self, context: Optional[Dict]) -> str:
        """Build system prompt with Quimera context."""
        base = """You are QuimeraMind — the autonomous brain of the Quimera Mark X platform.
You are an expert in:
- Linux kernel code repair (C, Rust)
- Formal verification (Z3, CBMC, eBPF)
- Genetic algorithms for code evolution (NSGA-II)
- Offensive security (exploit generation, fuzzing)
- Multi-tenant distributed systems

You give concise, actionable advice. You never generate unsafe code.
Always suggest using the Quimera pipeline (memory retrieval → genetic evolution → verification → sandbox testing)."""

        if context:
            parts = [base]
            if "horizon" in context:
                parts.append(f"Current horizon context: {context['horizon']}")
            if "file" in context:
                parts.append(f"Current file: {context['file']}")
            if "error" in context:
                parts.append(f"Current error: {context['error'][:500]}")
            return "\n".join(parts)

        return base

    # ── Stats ────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        stats = {
            "provider": self.config.provider.value,
            "model": self.config.model or "none",
            "available": self._available,
            "total_calls": self._total_calls,
            "total_tokens": self._total_tokens,
            "avg_latency_ms": round(self._total_latency / max(self._total_calls, 1), 1),
            "cache_size": len(self._cache),
        }
        return stats
