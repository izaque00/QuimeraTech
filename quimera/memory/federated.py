"""
Quimera Mark X — Federated Memory (Horizonte 2)

Privacy-preserving federated learning across tenants.
Enables knowledge sharing without exposing raw code or patches.

Architecture:
    ┌───────────────────────────────────────────────────┐
    │              Aggregation Server                     │
    │  ┌─────────┐  ┌──────────┐  ┌──────────────────┐  │
    │  │ Gradient│  │ Model    │  │ Knowledge Graph  │  │
    │  │ Aggr.   │  │ Merge    │  │ Sync             │  │
    │  └─────────┘  └──────────┘  └──────────────────┘  │
    └──────────┬────────────┬──────────────┬────────────┘
               │            │              │
    ┌──────────▼──┐  ┌──────▼──────┐  ┌───▼───────────┐
    │ Tenant A     │  │ Tenant B    │  │ Tenant C      │
    │ (on-prem)    │  │ (cloud)     │  │ (hybrid)      │
    │ embeddings   │  │ embeddings  │  │ embeddings    │
    └──────────────┘  └─────────────┘  └───────────────┘

Features:
    - Differential privacy (ε-differential privacy)
    - Federated averaging of embedding models
    - Secure aggregation (simulated)
    - Tenant opt-in/opt-out per knowledge domain
    - Knowledge graph synchronization

Usage:
    from quimera.memory.federated import FederatedMemory
    
    fm = FederatedMemory(tenant_id="acme-corp")
    await fm.share_embedding(embedding, metadata, sensitivity="medium")
    global_knowledge = await fm.fetch_global_knowledge(query, top_k=5)
"""

import asyncio
import hashlib
import json
import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

logger = logging.getLogger("quimera.federated")


# ═══════════════════════════════════════════════════════════════════════════
# Enums & Data Structures
# ═══════════════════════════════════════════════════════════════════════════

class Sensitivity(str, Enum):
    LOW = "low"           # Public knowledge (kernel build fixes)
    MEDIUM = "medium"     # Semi-sensitive (common errors)
    HIGH = "high"         # Proprietary (company-specific code patterns)
    RESTRICTED = "restricted"  # Never shared


class ShareConsent(str, Enum):
    FULL = "full"               # Share everything (anonymized)
    AGGREGATE_ONLY = "aggregate"  # Only contribute to aggregated stats
    NONE = "none"               # Opt-out of sharing


@dataclass
class FederatedEmbedding:
    """An embedding ready for federated sharing."""
    tenant_id: str
    embedding_hash: str          # Anonymized hash
    embedding: np.ndarray        # The actual vector (local only)
    noisy_embedding: np.ndarray  # ε-differentially private version
    sensitivity: Sensitivity
    domain: str                  # Knowledge domain
    metadata: Dict[str, Any]
    timestamp: str


@dataclass
class FederatedKnowledge:
    """Aggregated knowledge from the federation."""
    domain: str
    total_contributors: int
    aggregated_embedding: Optional[np.ndarray]
    similar_entries: List[Dict]
    confidence: float
    freshness_seconds: float


# ═══════════════════════════════════════════════════════════════════════════
# Differential Privacy Engine
# ═══════════════════════════════════════════════════════════════════════════

class DifferentialPrivacy:
    """ε-Differential Privacy for embedding sharing.
    
    Adds calibrated noise to embeddings before sharing, ensuring
    individual contributions cannot be reverse-engineered.
    
    ε values:
        0.1 — Very private, noisy
        1.0 — Moderate privacy
        10.0 — Loose privacy, high accuracy
    """

    # Sensitivity budgets per share level
    EPSILON_MAP = {
        Sensitivity.LOW: 1.0,          # Public-ish: moderate noise
        Sensitivity.MEDIUM: 0.5,       # Semi-sensitive: more noise
        Sensitivity.HIGH: 0.1,         # Proprietary: heavy noise
        Sensitivity.RESTRICTED: 0.0,   # Never shared
    }

    # Per-domain clipping norms
    DOMAIN_CLIP_NORMS = {
        "compilation": 0.5,
        "runtime_error": 0.8,
        "security_vuln": 1.0,
        "performance": 0.5,
        "config": 0.3,
    }

    @classmethod
    def privatize(
        cls,
        embedding: np.ndarray,
        sensitivity: Sensitivity,
        domain: str = "general",
    ) -> Optional[np.ndarray]:
        """Apply differential privacy to an embedding.

        Returns None if sensitivity is RESTRICTED (never shared).
        """
        epsilon = cls.EPSILON_MAP.get(sensitivity, 1.0)
        if epsilon == 0.0:
            return None

        # Clip to per-domain norm
        clip = cls.DOMAIN_CLIP_NORMS.get(domain, 1.0)
        norm = np.linalg.norm(embedding)
        if norm > clip:
            embedding = embedding * (clip / norm)

        # Add Laplace noise scaled by (clip / ε)
        # scale = Δf / ε  where Δf ≈ clip for bounded contribution
        scale = clip / epsilon
        noise = np.random.laplace(0, scale, embedding.shape)

        return embedding + noise

    @classmethod
    def compute_privacy_budget(
        cls, total_shares: int, epsilon_per_share: float
    ) -> Dict[str, Any]:
        """Compute remaining privacy budget.

        Uses advanced composition theorem:
        ε_total = ε_per * sqrt(2 * n * ln(1/δ)) + n * ε_per * (e^ε_per - 1)
        """
        delta = 1e-5
        eps_term1 = epsilon_per_share * np.sqrt(2 * total_shares * np.log(1 / delta))
        eps_term2 = total_shares * epsilon_per_share * (np.exp(epsilon_per_share) - 1)
        eps_total = eps_term1 + eps_term2

        return {
            "total_shares": total_shares,
            "epsilon_per_share": epsilon_per_share,
            "epsilon_total": round(eps_total, 4),
            "delta": delta,
            "recommendation": "safe" if eps_total < 10 else "budget_exceeded",
        }


# ═══════════════════════════════════════════════════════════════════════════
# Federated Memory
# ═══════════════════════════════════════════════════════════════════════════

class FederatedMemory:
    """Privacy-preserving federated memory system.
    
    Enables:
    - Secure embedding sharing with ε-differential privacy
    - Federated averaging across tenants
    - Domain-specific knowledge graphs
    - Consent management per tenant per domain
    """

    def __init__(
        self,
        tenant_id: str,
        consent: ShareConsent = ShareConsent.FULL,
        privacy_epsilon: float = 1.0,
        aggregation_server_url: Optional[str] = None,
    ):
        self.tenant_id = tenant_id
        self.consent = consent
        self.privacy_epsilon = privacy_epsilon

        # Local storage
        self._local_embeddings: Dict[str, FederatedEmbedding] = {}
        self._global_cache: Dict[str, FederatedKnowledge] = {}
        self._domain_blacklist: Set[str] = set()  # Domains opted out
        self._share_count: Dict[Sensitivity, int] = {
            s: 0 for s in Sensitivity
        }

        # Aggregation server (simulated in local mode)
        self._aggregation_url = aggregation_server_url
        self._use_remote = aggregation_server_url is not None

        # Simulated global knowledge base (shared across tenants)
        if not self._use_remote:
            self._global_embeddings: List[FederatedEmbedding] = []

        logger.info(
            f"FederatedMemory: tenant={tenant_id}, consent={consent.value}, "
            f"ε={privacy_epsilon}"
        )

    # ── Sharing ─────────────────────────────────────────────────────────

    async def share_embedding(
        self,
        embedding: np.ndarray,
        metadata: Dict[str, Any],
        domain: str = "compilation",
        sensitivity: Sensitivity = Sensitivity.MEDIUM,
    ) -> Optional[str]:
        """Share an embedding with the federation after applying privacy.

        Returns share_id if shared, None if blocked.
        """
        # Consent check
        if self.consent == ShareConsent.NONE:
            logger.debug(f"FederatedMemory: share blocked by consent policy")
            return None

        # Domain blacklist
        if domain in self._domain_blacklist:
            logger.debug(f"FederatedMemory: domain '{domain}' blacklisted")
            return None

        # Apply differential privacy
        noisy = DifferentialPrivacy.privatize(embedding, sensitivity, domain)
        if noisy is None:
            logger.debug(f"FederatedMemory: sensitivity {sensitivity.value} blocks sharing")
            return None

        # Create share entry
        share_id = f"fed-{self.tenant_id}-{uuid.uuid4().hex[:8]}"
        entry = FederatedEmbedding(
            tenant_id=self.tenant_id,
            embedding_hash=hashlib.sha256(embedding.tobytes()).hexdigest()[:16],
            embedding=embedding,
            noisy_embedding=noisy,
            sensitivity=sensitivity,
            domain=domain,
            metadata={k: v for k, v in metadata.items() if k != "raw_code"},
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

        self._local_embeddings[share_id] = entry
        self._share_count[sensitivity] += 1

        # Send to aggregation server
        if self._use_remote:
            await self._send_to_aggregator(entry)
        else:
            # Local aggregation (simulated)
            self._global_embeddings.append(entry)

        logger.info(
            f"FederatedMemory: shared '{domain}' embedding "
            f"(ε={DifferentialPrivacy.EPSILON_MAP.get(sensitivity)}, "
            f"id={share_id})"
        )
        return share_id

    # ── Retrieval ───────────────────────────────────────────────────────

    async def fetch_global_knowledge(
        self,
        query: str,
        domain: Optional[str] = None,
        top_k: int = 5,
        min_contributors: int = 2,
    ) -> Optional[FederatedKnowledge]:
        """Fetch aggregated knowledge from the federation.

        Returns aggregated embedding + similar entries if enough contributors.
        """
        cache_key = f"{domain}:{query[:100]}"
        if cache_key in self._global_cache:
            cached = self._global_cache[cache_key]
            # Check freshness
            if time.time() - cached.freshness_seconds < 300:
                return cached

        if self._use_remote:
            result = await self._fetch_from_aggregator(query, domain, top_k)
        else:
            result = await self._local_fetch(query, domain, top_k, min_contributors)

        if result:
            self._global_cache[cache_key] = result
        return result

    async def _local_fetch(
        self, query: str, domain: Optional[str], top_k: int, min_contributors: int
    ) -> Optional[FederatedKnowledge]:
        """Local mode: aggregate from in-memory global store."""
        entries = self._global_embeddings

        # Filter by domain
        if domain:
            entries = [e for e in entries if e.domain == domain]

        # Filter out restricted
        entries = [e for e in entries if e.sensitivity != Sensitivity.RESTRICTED]

        # Don't return own entries
        entries = [e for e in entries if e.tenant_id != self.tenant_id]

        if len(entries) < min_contributors:
            logger.debug(
                f"FederatedMemory: insufficient contributors "
                f"({len(entries)}/{min_contributors}) for '{domain or query[:30]}'"
            )
            return None

        if not entries:
            return None

        # Simple federated averaging
        all_embeddings = np.stack([e.noisy_embedding for e in entries])
        avg_embedding = np.mean(all_embeddings, axis=0)

        # Cosine similarity ranking
        query_emb = self._hash_embed(query, dim=len(avg_embedding))
        scores = []
        for entry in entries:
            sim = float(np.dot(query_emb, entry.noisy_embedding))
            scores.append((entry, sim))
        scores.sort(key=lambda x: x[1], reverse=True)

        similar = [
            {
                "tenant_hash": hashlib.sha256(e.tenant_id.encode()).hexdigest()[:8],
                "domain": e.domain,
                "sensitivity": e.sensitivity.value,
                "similarity_score": round(s, 4),
                "metadata": {k: v for k, v in e.metadata.items() if k != "raw_code"},
                "timestamp": e.timestamp,
            }
            for e, s in scores[:top_k]
        ]

        # Confidence based on contributor count and score spread
        top_scores = [s for _, s in scores[:top_k]]
        confidence = min(1.0, len(entries) / 10.0 * np.mean(top_scores))

        return FederatedKnowledge(
            domain=domain or "general",
            total_contributors=len(entries),
            aggregated_embedding=avg_embedding,
            similar_entries=similar,
            confidence=round(confidence, 3),
            freshness_seconds=time.time(),
        )

    async def _send_to_aggregator(self, entry: FederatedEmbedding):
        """Send embedding to remote aggregation server."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "tenant_id": entry.tenant_id,
                    "embedding_hash": entry.embedding_hash,
                    "noisy_embedding": entry.noisy_embedding.tolist(),
                    "sensitivity": entry.sensitivity.value,
                    "domain": entry.domain,
                    "metadata": entry.metadata,
                }
                async with session.post(
                    f"{self._aggregation_url}/api/v1/federation/share",
                    json=payload,
                    timeout=5,
                ) as resp:
                    if resp.status != 200:
                        logger.warning(f"FederatedMemory: aggregator rejected share")
        except Exception as e:
            logger.debug(f"FederatedMemory: aggregator unreachable ({e})")

    async def _fetch_from_aggregator(
        self, query: str, domain: Optional[str], top_k: int
    ) -> Optional[FederatedKnowledge]:
        """Fetch knowledge from remote aggregation server."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    "tenant_id": self.tenant_id,
                    "query": query,
                    "domain": domain,
                    "top_k": top_k,
                }
                async with session.get(
                    f"{self._aggregation_url}/api/v1/federation/knowledge",
                    params=params,
                    timeout=5,
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return FederatedKnowledge(
                            domain=data.get("domain", "general"),
                            total_contributors=data.get("total_contributors", 0),
                            aggregated_embedding=None,
                            similar_entries=data.get("similar_entries", []),
                            confidence=data.get("confidence", 0),
                            freshness_seconds=time.time(),
                        )
        except Exception as e:
            logger.debug(f"FederatedMemory: aggregator unreachable ({e})")
        return None

    # ── Consent & Privacy Management ────────────────────────────────────

    async def update_consent(self, consent: ShareConsent):
        """Update tenant consent level."""
        old = self.consent
        self.consent = consent
        logger.info(f"FederatedMemory: consent changed {old.value} → {consent.value}")

    async def blacklist_domain(self, domain: str):
        """Opt-out from sharing in a specific domain."""
        self._domain_blacklist.add(domain)
        logger.info(f"FederatedMemory: domain '{domain}' blacklisted")

    async def whitelist_domain(self, domain: str):
        """Re-enable sharing for a domain."""
        self._domain_blacklist.discard(domain)
        logger.info(f"FederatedMemory: domain '{domain}' whitelisted")

    async def get_privacy_report(self) -> Dict[str, Any]:
        """Get privacy budget report."""
        total_shares = sum(self._share_count.values())
        budget = DifferentialPrivacy.compute_privacy_budget(
            total_shares, self.privacy_epsilon
        )

        return {
            "tenant_id": self.tenant_id,
            "consent": self.consent.value,
            "shares_by_sensitivity": {
                s.value: c for s, c in self._share_count.items()
            },
            "total_shares": total_shares,
            "privacy_budget": budget,
            "domain_blacklist": list(self._domain_blacklist),
            "cached_global_entries": len(self._global_cache),
            "aggregation_mode": "remote" if self._use_remote else "local",
        }

    @staticmethod
    def _hash_embed(text: str, dim: int = 384) -> np.ndarray:
        """Quick hash-based embedding for query comparison."""
        vec = np.zeros(dim, dtype=np.float32)
        for i, ch in enumerate(text.encode()):
            idx = (i * 7 + ch) % dim
            vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec
