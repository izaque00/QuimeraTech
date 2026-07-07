"""
Quimera Mark X — Tenant Manager (Horizonte 1)

Multi-tenant isolation, quotas, rate limiting, and billing tier management.

Tiers:
    free        — 2 concurrent, 50/day, c only, 60 req/min
    pro         — 10 concurrent, 500/day, all languages, 300 req/min
    enterprise  — 50 concurrent, unlimited, all languages, custom rate, SSO

Usage:
    tm = TenantManager(redis_client)
    await tm.create_tenant("Acme Corp", tier="pro")
    ok = await tm.check_rate_limit(tenant_id)
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("quimera.tenant")


# ═══════════════════════════════════════════════════════════════════════════
# Tier Definitions
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TierDefinition:
    name: str
    max_concurrent: int
    max_daily: int          # 0 = unlimited
    rate_limit_rpm: int     # Requests per minute
    allowed_languages: List[str]
    features: List[str]
    priority_boost: int     # Added to mission priority
    dedicated_workers: bool
    sso_enabled: bool
    audit_log: bool


TIERS: Dict[str, TierDefinition] = {
    "free": TierDefinition(
        name="Free",
        max_concurrent=2,
        max_daily=50,
        rate_limit_rpm=60,
        allowed_languages=["c"],
        features=["basic_repair", "single_language"],
        priority_boost=0,
        dedicated_workers=False,
        sso_enabled=False,
        audit_log=False,
    ),
    "pro": TierDefinition(
        name="Pro",
        max_concurrent=10,
        max_daily=500,
        rate_limit_rpm=300,
        allowed_languages=["c", "rust", "go", "python"],
        features=["basic_repair", "multi_language", "evolution", "verification", "security"],
        priority_boost=2,
        dedicated_workers=False,
        sso_enabled=False,
        audit_log=True,
    ),
    "enterprise": TierDefinition(
        name="Enterprise",
        max_concurrent=50,
        max_daily=0,  # unlimited
        rate_limit_rpm=1000,
        allowed_languages=["c", "rust", "go", "python", "zig"],
        features=["all"],
        priority_boost=5,
        dedicated_workers=True,
        sso_enabled=True,
        audit_log=True,
    ),
}


# ═══════════════════════════════════════════════════════════════════════════
# Rate Limiter — Token Bucket per Tenant
# ═══════════════════════════════════════════════════════════════════════════

class TokenBucket:
    """Token bucket rate limiter with Redis-backed state."""

    def __init__(self, redis_client=None):
        self.redis = redis_client
        self._local_buckets: Dict[str, Dict[str, Any]] = {}

    async def consume(self, key: str, rate_per_minute: int, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if allowed."""
        now = time.monotonic()

        if self.redis:
            return await self._redis_consume(key, rate_per_minute, tokens)
        else:
            return self._local_consume(key, rate_per_minute, tokens, now)

    def _local_consume(self, key: str, rate: int, tokens: int, now: float) -> bool:
        bucket = self._local_buckets.get(key, {"tokens": float(rate), "last": now})

        # Refill
        elapsed = now - bucket["last"]
        bucket["tokens"] = min(float(rate), bucket["tokens"] + elapsed * (rate / 60.0))
        bucket["last"] = now

        if bucket["tokens"] >= tokens:
            bucket["tokens"] -= tokens
            self._local_buckets[key] = bucket
            return True
        self._local_buckets[key] = bucket
        return False

    async def _redis_consume(self, key: str, rate: int, tokens: int) -> bool:
        rkey = f"quimera:ratelimit:{key}"
        now = time.monotonic()
        data = await self.redis.get(rkey)
        bucket = json.loads(data) if data else {"tokens": float(rate), "last": now}

        elapsed = now - bucket["last"]
        bucket["tokens"] = min(float(rate), bucket["tokens"] + elapsed * (rate / 60.0))
        bucket["last"] = now

        if bucket["tokens"] >= tokens:
            bucket["tokens"] -= tokens
            await self.redis.setex(rkey, 120, json.dumps(bucket))
            return True
        await self.redis.setex(rkey, 120, json.dumps(bucket))
        return False


# ═══════════════════════════════════════════════════════════════════════════
# Tenant Manager
# ═══════════════════════════════════════════════════════════════════════════

class TenantManager:
    """Multi-tenant management with quotas and rate limiting."""

    def __init__(self, redis_client=None):
        self.redis = redis_client
        self._use_redis = redis_client is not None
        self._tenants: Dict[str, Dict[str, Any]] = {}
        self._daily_counters: Dict[str, Dict[str, Any]] = {}  # tenant_id → {count, date}
        self.rate_limiter = TokenBucket(redis_client)
        self._active_missions: Dict[str, int] = {}  # tenant_id → active count

    # ── Tenant CRUD ────────────────────────────────────────────────────

    async def create_tenant(
        self, name: str, tier: str = "free",
        tenant_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> str:
        """Create a new tenant."""
        if tier not in TIERS:
            raise ValueError(f"Invalid tier: {tier}. Available: {list(TIERS.keys())}")

        tid = tenant_id or f"tenant-{uuid.uuid4().hex[:8]}"
        td = TIERS[tier]

        tenant_data = {
            "tenant_id": tid,
            "name": name,
            "tier": tier,
            "max_concurrent": td.max_concurrent,
            "max_daily": td.max_daily,
            "rate_limit_rpm": td.rate_limit_rpm,
            "allowed_languages": td.allowed_languages,
            "features": td.features,
            "priority_boost": td.priority_boost,
            "dedicated_workers": td.dedicated_workers,
            "sso_enabled": td.sso_enabled,
            "audit_log": td.audit_log,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "active",
            "metadata": metadata or {},
        }

        if self._use_redis:
            key = f"quimera:tenant:{tid}"
            await self.redis.hset(key, mapping=tenant_data)
            await self.redis.sadd("quimera:tenants", tid)
        else:
            self._tenants[tid] = tenant_data

        logger.info(f"Tenant created: {tid} ({name}, {tier})")
        return tid

    async def get_tenant(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        if self._use_redis:
            key = f"quimera:tenant:{tenant_id}"
            data = await self.redis.hgetall(key)
            return dict(data) if data else None
        return self._tenants.get(tenant_id)

    async def update_tier(self, tenant_id: str, new_tier: str):
        if new_tier not in TIERS:
            raise ValueError(f"Invalid tier: {new_tier}")
        td = TIERS[new_tier]
        updates = {
            "tier": new_tier,
            "max_concurrent": td.max_concurrent,
            "max_daily": td.max_daily,
            "rate_limit_rpm": td.rate_limit_rpm,
            "allowed_languages": td.allowed_languages,
            "features": td.features,
            "priority_boost": td.priority_boost,
            "dedicated_workers": td.dedicated_workers,
            "sso_enabled": td.sso_enabled,
            "audit_log": td.audit_log,
        }
        if self._use_redis:
            key = f"quimera:tenant:{tenant_id}"
            await self.redis.hset(key, mapping=updates)
        elif tenant_id in self._tenants:
            self._tenants[tenant_id].update(updates)
        logger.info(f"Tenant {tenant_id} upgraded to {new_tier}")

    async def delete_tenant(self, tenant_id: str):
        if self._use_redis:
            await self.redis.delete(f"quimera:tenant:{tenant_id}")
            await self.redis.srem("quimera:tenants", tenant_id)
        else:
            self._tenants.pop(tenant_id, None)
        logger.info(f"Tenant deleted: {tenant_id}")

    # ── Quota Checks ───────────────────────────────────────────────────

    async def check_concurrent_limit(self, tenant_id: str) -> Tuple[bool, str]:
        """Check if tenant can accept another concurrent mission."""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return False, "Tenant not found"

        if tenant.get("status") != "active":
            return False, "Tenant suspended"

        active = self._active_missions.get(tenant_id, 0)
        max_concurrent = tenant.get("max_concurrent", 2)

        if active >= max_concurrent:
            return False, f"Concurrent limit reached ({active}/{max_concurrent})"

        return True, "ok"

    async def check_daily_limit(self, tenant_id: str) -> Tuple[bool, str]:
        """Check daily mission quota."""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return False, "Tenant not found"

        max_daily = tenant.get("max_daily", 50)
        if max_daily == 0:  # unlimited
            return True, "ok"

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        counter = self._daily_counters.get(tenant_id, {"count": 0, "date": today})

        if counter["date"] != today:
            counter = {"count": 0, "date": today}

        if counter["count"] >= max_daily:
            return False, f"Daily limit reached ({counter['count']}/{max_daily})"

        return True, "ok"

    async def check_rate_limit(self, tenant_id: str) -> Tuple[bool, str]:
        """Check request rate limit."""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return False, "Tenant not found"

        rate = tenant.get("rate_limit_rpm", 60)
        allowed = await self.rate_limiter.consume(f"tenant:{tenant_id}", rate)
        if not allowed:
            return False, f"Rate limit exceeded ({rate}/min)"
        return True, "ok"

    async def check_language_allowed(self, tenant_id: str, language: str) -> Tuple[bool, str]:
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return False, "Tenant not found"

        allowed = tenant.get("allowed_languages", ["c"])
        if language not in allowed:
            return False, f"Language '{language}' not allowed. Allowed: {allowed}"
        return True, "ok"

    async def can_submit_mission(self, tenant_id: str, language: str = "c") -> Tuple[bool, str]:
        """Run all checks before accepting a mission."""
        # Check tenant exists
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return False, "Tenant not found"
        if tenant.get("status") != "active":
            return False, "Tenant suspended"

        checks = [
            ("concurrent", await self.check_concurrent_limit(tenant_id)),
            ("daily", await self.check_daily_limit(tenant_id)),
            ("rate", await self.check_rate_limit(tenant_id)),
            ("language", await self.check_language_allowed(tenant_id, language)),
        ]

        for check_name, (ok, msg) in checks:
            if not ok:
                return False, f"[{check_name}] {msg}"

        return True, "ok"

    # ── Mission Tracking ────────────────────────────────────────────────

    async def mission_started(self, tenant_id: str):
        """Called when a mission starts for a tenant."""
        self._active_missions[tenant_id] = self._active_missions.get(tenant_id, 0) + 1

        # Increment daily counter
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        counter = self._daily_counters.get(tenant_id, {"count": 0, "date": today})
        if counter["date"] != today:
            counter = {"count": 0, "date": today}
        counter["count"] += 1
        self._daily_counters[tenant_id] = counter

        if self._use_redis:
            await self.redis.hincrby(f"quimera:tenant:{tenant_id}:daily", today, 1)

    async def mission_completed(self, tenant_id: str):
        """Called when a mission completes."""
        self._active_missions[tenant_id] = max(0, self._active_missions.get(tenant_id, 1) - 1)

    async def get_tenant_usage(self, tenant_id: str) -> Dict[str, Any]:
        tenant = await self.get_tenant(tenant_id)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        counter = self._daily_counters.get(tenant_id, {"count": 0, "date": today})
        daily = counter["count"] if counter["date"] == today else 0

        return {
            "tenant_id": tenant_id,
            "tier": tenant.get("tier", "free") if tenant else "free",
            "active_missions": self._active_missions.get(tenant_id, 0),
            "max_concurrent": tenant.get("max_concurrent", 2) if tenant else 2,
            "daily_missions": daily,
            "max_daily": tenant.get("max_daily", 50) if tenant else 50,
            "max_daily_str": "unlimited" if (tenant and tenant.get("max_daily") == 0) else str(tenant.get("max_daily", 50)) if tenant else "50",
        }

    # ── Tenant Info ─────────────────────────────────────────────────────

    async def list_tenants(self) -> List[Dict[str, Any]]:
        if self._use_redis:
            tids = await self.redis.smembers("quimera:tenants")
            tenants = []
            for tid in (tids or []):
                data = await self.redis.hgetall(f"quimera:tenant:{tid}")
                if data:
                    tenants.append(dict(data))
            return tenants
        return list(self._tenants.values())

    async def get_cluster_tenant_stats(self) -> Dict[str, Any]:
        tenants = await self.list_tenants()
        by_tier = {}
        total_active = 0
        for t in tenants:
            tier = t.get("tier", "free")
            if tier not in by_tier:
                by_tier[tier] = 0
            by_tier[tier] += 1
            total_active += self._active_missions.get(t["tenant_id"], 0)

        return {
            "total_tenants": len(tenants),
            "by_tier": by_tier,
            "total_active_missions": total_active,
        }
