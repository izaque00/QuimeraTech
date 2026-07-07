"""
LLM Config — Auto-detect and configure LLM providers.

Finally doing what was promised: actual LLM integration.
Uses your existing API keys from vault/env for real AI-powered analysis.

Providers supported:
  - OpenRouter (free tier: Mistral Small, Gemma, Llama)
  - OpenAI (GPT-4o, GPT-4o-mini)
  - Anthropic (Claude)
  - Ollama (local, free, private)

Key storage: vault.py (AES-256-GCM encrypted) or env vars.
"""

import os
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger("quimera.llm_config")


@dataclass
class LLMProvider:
    """One configured LLM provider."""
    name: str
    provider: str  # openrouter, openai, anthropic, ollama
    model: str
    api_key: str = ""
    api_base: str = ""
    max_tokens: int = 4096
    temperature: float = 0.1
    timeout_seconds: int = 60
    is_free: bool = False
    priority: int = 0  # 0 = highest priority


@dataclass
class LLMConfig:
    """
    Auto-detects and configures all available LLM providers.
    
    Priority order:
    1. Ollama (local, free, private) — if running
    2. OpenRouter free models (Mistral Small, Gemma) — if API key
    3. OpenAI/Anthropic (paid, best quality) — if API key
    """
    
    providers: List[LLMProvider] = field(default_factory=list)
    default_provider: str = "openrouter"
    default_model: str = "mistralai/mistral-small-3.1-24b-instruct"
    vault_path: str = ".vault"
    
    def __post_init__(self):
        self._detect_providers()
    
    def _detect_providers(self):
        """Auto-detect all available LLM providers from env/vault."""
        
        # 1. Ollama (local)
        if self._check_ollama():
            self.providers.append(LLMProvider(
                name="ollama-local",
                provider="ollama",
                model="codellama:13b",
                api_base="http://localhost:11434",
                is_free=True,
                priority=0,
            ))
            logger.info("LLM: Ollama local detected")
        
        # 2. OpenRouter (free tier)
        or_key = self._get_key("OPENROUTER_API_KEY") or self._get_key("OR_KEY")
        if or_key:
            self.providers.append(LLMProvider(
                name="openrouter-free",
                provider="openrouter",
                model="mistralai/mistral-small-3.1-24b-instruct",
                api_key=or_key,
                api_base="https://openrouter.ai/api/v1",
                is_free=True,
                priority=1,
            ))
            self.providers.append(LLMProvider(
                name="openrouter-gemma",
                provider="openrouter",
                model="google/gemma-3-27b-it:free",
                api_key=or_key,
                api_base="https://openrouter.ai/api/v1",
                is_free=True,
                priority=2,
            ))
            logger.info("LLM: OpenRouter configured (free models)")
        
        # 3. OpenAI
        oai_key = self._get_key("OPENAI_API_KEY")
        if oai_key:
            self.providers.append(LLMProvider(
                name="openai-gpt4o-mini",
                provider="openai",
                model="gpt-4o-mini",
                api_key=oai_key,
                is_free=False,
                priority=10,
            ))
            logger.info("LLM: OpenAI configured")
        
        # 4. Anthropic
        anthropic_key = self._get_key("ANTHROPIC_API_KEY")
        if anthropic_key:
            self.providers.append(LLMProvider(
                name="anthropic-claude",
                provider="anthropic",
                model="claude-3-haiku-20240307",
                api_key=anthropic_key,
                is_free=False,
                priority=10,
            ))
            logger.info("LLM: Anthropic configured")
        
        if not self.providers:
            logger.warning(
                "LLM: No providers detected. Set env vars or use vault. "
                "Free OpenRouter key: https://openrouter.ai/keys"
            )
    
    def get_best_provider(self) -> Optional[LLMProvider]:
        """Get the best available provider (free prioritized)."""
        if not self.providers:
            return None
        # Sort by priority (free first)
        sorted_providers = sorted(self.providers, key=lambda p: p.priority)
        return sorted_providers[0]
    
    def get_provider_by_name(self, name: str) -> Optional[LLMProvider]:
        """Get a specific provider by name."""
        for p in self.providers:
            if p.name == name:
                return p
        return None
    
    def _check_ollama(self) -> bool:
        """Check if Ollama is running locally."""
        try:
            import urllib.request
            req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
            urllib.request.urlopen(req, timeout=2)
            return True
        except Exception:
            return False
    
    def _get_key(self, key_name: str) -> Optional[str]:
        """
        Get API key from:
        1. Environment variable
        2. Encrypted vault (.vault)
        3. .env file
        """
        # 1. Env var
        val = os.environ.get(key_name)
        if val:
            return val
        
        # 2. Vault
        try:
            from quimera.vault import get_vault
            vault = get_vault()
            if vault:
                val = vault.get(key_name.lower())
                if val:
                    return val
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"Vault read error: {e}")
        
        # 3. .env file
        try:
            with open(".env") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith(f"{key_name}="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        except FileNotFoundError:
            pass
        
        return None
    
    def status(self) -> Dict:
        """Return status of all configured providers."""
        return {
            "total_providers": len(self.providers),
            "free_providers": sum(1 for p in self.providers if p.is_free),
            "providers": [
                {
                    "name": p.name,
                    "model": p.model,
                    "free": p.is_free,
                    "priority": p.priority,
                }
                for p in self.providers
            ],
        }
