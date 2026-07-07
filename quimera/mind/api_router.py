"""
Quimera Mark X — API Key Router + Multi-Provider Fallback

Sistema de roteamento inteligente para ~11 chaves de API.
O Mind usa este módulo para nunca ficar sem IA, alternando
entre provedores conforme disponibilidade.

Funcionalidades:
- Carrega chaves do .env
- Roteamento round-robin com pesos dinâmicos
- Rate-limit tracking por chave
- Fallback automático (groq → deepseek → openai → anthropic → ollama)
- Cooldown de chaves que falham
- Tier gratuito prioritário (groq, google, deepseek)
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("quimera.router")


class ProviderStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    RATE_LIMITED = "rate_limited"
    DOWN = "down"
    COOLDOWN = "cooldown"


@dataclass
class KeyState:
    key: str
    provider: str
    index: int
    status: ProviderStatus = ProviderStatus.HEALTHY
    requests_this_minute: int = 0
    total_requests: int = 0
    total_failures: int = 0
    last_request_at: float = 0.0
    last_failure_at: float = 0.0
    cooldown_until: float = 0.0
    avg_latency_ms: float = 0.0

    @property
    def available(self) -> bool:
        if self.status == ProviderStatus.DOWN:
            return False
        if self.status == ProviderStatus.COOLDOWN and time.time() < self.cooldown_until:
            return False
        return True


@dataclass
class RouterConfig:
    max_rpm_per_key: int = 50
    timeout_seconds: int = 30
    max_retries_per_key: int = 3
    key_cooldown_seconds: int = 60
    free_tier_first: bool = True
    priority_order: List[str] = field(default_factory=list)
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300


class ModelSpec:
    PROVIDER_MODELS = {
        "openai": ["gpt-4o-mini", "gpt-4o", "o4-mini"],
        "anthropic": ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022"],
        "google": ["gemini-2.0-flash", "gemini-2.5-pro"],
        "groq": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"],
        "deepseek": ["deepseek-chat", "deepseek-reasoner"],
        "together": ["mistralai/Mixtral-8x7B-Instruct-v0.1"],
        "mistral": ["mistral-large-latest", "mistral-small-latest"],
        "cohere": ["command-r-plus", "command-r"],
        "fireworks": ["accounts/fireworks/models/llama-v3p1-70b-instruct"],
        "huggingface": ["meta-llama/Llama-3.3-70B-Instruct"],
        "ollama": ["qwen3", "llama3:70b"],
    }

    FREE_TIER_PROVIDERS = ["groq", "google", "deepseek", "ollama"]

    COST_PER_1M = {
        "openai": (0.15, 0.60),       # gpt-4o-mini
        "anthropic": (3.00, 15.00),
        "google": (0.00, 0.00),        # Free tier
        "groq": (0.00, 0.00),
        "deepseek": (0.14, 0.28),
        "together": (0.90, 0.90),
        "mistral": (0.00, 0.00),       # Free tier
        "cohere": (0.00, 0.00),        # Free tier
        "fireworks": (0.90, 0.90),
        "huggingface": (0.00, 0.00),
        "ollama": (0.00, 0.00),
    }


class RateLimitError(Exception):
    pass


class APIKeyRouter:
    """
    Roteador inteligente de chaves API.

    Uso:
        router = APIKeyRouter()
        response = await router.route(
            messages=[{"role": "user", "content": "explique buffer overflow"}],
            task_type="explain"
        )
    """

    def __init__(self, config: Optional[RouterConfig] = None):
        self.config = config or RouterConfig()
        self.keys: Dict[str, List[KeyState]] = defaultdict(list)
        self._cache: Dict[str, Tuple[float, Any]] = {}
        self._current_index: Dict[str, int] = defaultdict(int)
        self._total_cost_usd: float = 0.0
        self._load_keys()

    def _load_keys(self):
        env_prefixes = {
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

        for provider, prefix in env_prefixes.items():
            for i in range(1, 20):
                key_name = f"{prefix}_{i}"
                key_value = os.getenv(key_name)
                if key_value and not key_value.startswith("sk-...") and key_value:
                    ks = KeyState(key=key_value, provider=provider, index=i)
                    self.keys[provider].append(ks)

        # Ollama sempre disponível como fallback
        self.keys["ollama"].append(KeyState(
            key=os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434"),
            provider="ollama", index=0
        ))

        total_keys = sum(len(v) for v in self.keys.values())
        providers = [p for p, ks in self.keys.items() if ks]
        logger.info(f"APIKeyRouter: {total_keys} keys across {len(providers)} providers: {providers}")

    def get_provider_order(self) -> List[str]:
        if self.config.priority_order:
            order = [p for p in self.config.priority_order if self.keys.get(p)]
        else:
            order = [p for p in self.keys if self.keys.get(p)]

        if self.config.free_tier_first:
            free = [p for p in order if p in ModelSpec.FREE_TIER_PROVIDERS]
            paid = [p for p in order if p not in ModelSpec.FREE_TIER_PROVIDERS]
            order = free + paid

        return [p for p in order if self.keys.get(p)]

    async def route(
        self,
        messages: List[Dict],
        task_type: str = "general",
        prefer_provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        cache_key = self._cache_key(messages, task_type)
        if self.config.cache_enabled and cache_key in self._cache:
            cached_at, cached_response = self._cache[cache_key]
            if time.time() - cached_at < self.config.cache_ttl_seconds:
                return cached_response

        provider_order = self.get_provider_order()
        if prefer_provider and prefer_provider in provider_order:
            provider_order.remove(prefer_provider)
            provider_order.insert(0, prefer_provider)

        last_error = None
        for provider in provider_order:
            try:
                result = await self._try_provider(provider, messages, task_type)
                if result:
                    if self.config.cache_enabled:
                        self._cache[cache_key] = (time.time(), result)
                    return result
            except Exception as e:
                last_error = str(e)
                logger.warning(f"  {provider}: {e[:100]}")

        # Last resort: deterministic fallback
        return {
            "content": f"[Deterministic] All providers exhausted. Last error: {last_error}",
            "model": "deterministic",
            "usage": {"total_tokens": 0},
            "estimated_cost": 0.0,
        }

    async def _try_provider(
        self, provider: str, messages: List[Dict], task_type: str
    ) -> Optional[Dict]:
        pkeys = self.keys.get(provider, [])
        if not pkeys:
            return None

        available = [k for k in pkeys if k.available]
        if not available:
            logger.debug(f"  {provider}: all {len(pkeys)} keys exhausted")
            return None

        start_idx = self._current_index[provider] % len(available)
        for offset in range(len(available)):
            idx = (start_idx + offset) % len(available)
            ks = available[idx]

            if ks.requests_this_minute >= self.config.max_rpm_per_key:
                continue

            try:
                t0 = time.monotonic()
                result = await self._call_api(provider, ks.key, messages)
                elapsed = (time.monotonic() - t0) * 1000

                ks.requests_this_minute += 1
                ks.total_requests += 1
                ks.last_request_at = time.time()
                ks.avg_latency_ms = (ks.avg_latency_ms * (ks.total_requests - 1) + elapsed) / ks.total_requests
                ks.status = ProviderStatus.HEALTHY

                self._current_index[provider] = idx + 1
                self._total_cost_usd += self._estimate_cost(provider, result.get("usage", {}))

                return result

            except RateLimitError:
                ks.status = ProviderStatus.RATE_LIMITED
                ks.cooldown_until = time.time() + self.config.key_cooldown_seconds
                logger.warning(f"  {provider}#{ks.index}: rate limited")

            except Exception as e:
                ks.total_failures += 1
                ks.last_failure_at = time.time()
                if ks.total_failures >= self.config.max_retries_per_key:
                    ks.status = ProviderStatus.COOLDOWN
                    ks.cooldown_until = time.time() + self.config.key_cooldown_seconds * 3
                logger.warning(f"  {provider}#{ks.index}: {e}")

        return None

    async def _call_api(self, provider: str, api_key: str, messages: List[Dict]) -> Dict:
        try:
            import aiohttp
        except ImportError:
            return {"content": f"[aiohttp not installed]", "model": "error", "usage": {}}

        if provider == "ollama":
            return await self._call_ollama(api_key, messages)

        # OpenAI-compatible (works for OpenAI, Groq, DeepSeek, Together, Fireworks)
        urls = {
            "openai": "https://api.openai.com/v1/chat/completions",
            "groq": "https://api.groq.com/openai/v1/chat/completions",
            "deepseek": "https://api.deepseek.com/v1/chat/completions",
            "together": "https://api.together.xyz/v1/chat/completions",
            "fireworks": "https://api.fireworks.ai/inference/v1/chat/completions",
            "mistral": "https://api.mistral.ai/v1/chat/completions",
        }

        if provider in urls:
            model = ModelSpec.PROVIDER_MODELS.get(provider, ["default"])[0]
            return await self._call_openai_compat(api_key, urls[provider], messages, model)

        if provider == "anthropic":
            return await self._call_anthropic(api_key, messages)
        if provider == "google":
            return await self._call_google(api_key, messages)

        raise ValueError(f"Unknown provider: {provider}")

    async def _call_openai_compat(self, api_key: str, base_url: str, messages: List[Dict], model: str) -> Dict:
        import aiohttp
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": model, "messages": messages, "temperature": 0.3, "max_tokens": 2048}

        timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(base_url, json=payload, headers=headers) as resp:
                if resp.status == 429:
                    raise RateLimitError("429")
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(f"HTTP {resp.status}: {body[:200]}")
                data = await resp.json()
                return {
                    "content": data["choices"][0]["message"]["content"],
                    "model": data.get("model", model),
                    "usage": data.get("usage", {}),
                    "estimated_cost": self._estimate_cost(provider="openai", usage=data.get("usage", {})),
                }

    async def _call_ollama(self, endpoint: str, messages: List[Dict]) -> Dict:
        import aiohttp
        payload = {"model": "qwen3", "messages": messages, "stream": False}
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{endpoint}/api/chat", json=payload, timeout=self.config.timeout_seconds) as resp:
                data = await resp.json()
                return {
                    "content": data["message"]["content"],
                    "model": data.get("model", "ollama"),
                    "usage": {"total_tokens": data.get("eval_count", 0)},
                    "estimated_cost": 0.0,
                }

    async def _call_anthropic(self, api_key: str, messages: List[Dict]) -> Dict:
        import aiohttp
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
        payload = {"model": "claude-sonnet-4-20250514", "max_tokens": 2048, "messages": messages}
        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers,
                                    timeout=self.config.timeout_seconds) as resp:
                if resp.status == 429:
                    raise RateLimitError("429")
                data = await resp.json()
                return {
                    "content": data["content"][0]["text"],
                    "model": data.get("model", "claude"),
                    "usage": data.get("usage", {}),
                    "estimated_cost": 0.0,
                }

    async def _call_google(self, api_key: str, messages: List[Dict]) -> Dict:
        import aiohttp
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
        contents = [{"parts": [{"text": m["content"]}]} for m in messages if m.get("content")]
        payload = {"contents": contents}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=self.config.timeout_seconds) as resp:
                data = await resp.json()
                return {
                    "content": data["candidates"][0]["content"]["parts"][0]["text"],
                    "model": "gemini",
                    "usage": {},
                    "estimated_cost": 0.0,
                }

    def _cache_key(self, messages: List[Dict], task_type: str) -> str:
        raw = json.dumps(messages, sort_keys=True) + task_type
        return hashlib.sha256(raw.encode()).hexdigest()

    def _estimate_cost(self, provider: str, usage: Dict) -> float:
        costs = ModelSpec.COST_PER_1M.get(provider, (0, 0))
        prompt_tokens = usage.get("prompt_tokens", 0) / 1_000_000
        completion_tokens = usage.get("completion_tokens", 0) / 1_000_000
        return prompt_tokens * costs[0] + completion_tokens * costs[1]

    def get_stats(self) -> Dict:
        stats = {"total_cost_usd": round(self._total_cost_usd, 6), "providers": {}}
        for provider, pkeys in self.keys.items():
            if not pkeys:
                continue
            alive = sum(1 for k in pkeys if k.available)
            total_req = sum(k.total_requests for k in pkeys)
            stats["providers"][provider] = {
                "keys_total": len(pkeys),
                "keys_alive": alive,
                "total_requests": total_req,
                "avg_latency_ms": round(sum(k.avg_latency_ms for k in pkeys) / max(len(pkeys), 1), 1),
            }
        return stats

    def reset_minute_counters(self):
        for pkeys in self.keys.values():
            for ks in pkeys:
                ks.requests_this_minute = 0


__all__ = ["APIKeyRouter", "RouterConfig", "KeyState", "ProviderStatus", "ModelSpec", "RateLimitError"]

APIRouter = APIKeyRouter
