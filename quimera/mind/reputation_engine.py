"""
Quimera Reputation Engine — Cada agente tem histórico de confiança.
Scores persistem entre execuções e afetam roteamento/planejamento.
"""
import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("quimera.reputation")

# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class AgentScore:
    agent: str
    success_count: int = 0
    failure_count: int = 0
    avg_latency_ms: float = 0.0
    avg_fitness: float = 0.0
    last_used: str = ""
    streak: int = 0          # consecutive successes
    reputation: float = 0.5  # weighted score (0.0 → 1.0)

@dataclass
class ModelScore:
    provider: str
    model: str
    calls: int = 0
    successes: int = 0
    total_tokens: int = 0
    avg_latency_ms: float = 0.0
    reputation: float = 0.5

# ═══════════════════════════════════════════════════════════════════════════

class ReputationEngine:
    """Persistent reputation tracking for agents and LLM models.

    Every action is scored. Scores affect:
    - Agent selection (prefer high-reputation agents)
    - LLM provider routing (prefer reliable + fast models)
    - Auto-healing decisions (skip agents with low reputation)
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.path.expanduser("~"), ".quimera", "reputation.db"
        )
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()
        self._agent_cache: Dict[str, AgentScore] = {}
        self._model_cache: Dict[str, ModelScore] = {}

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)

        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_scores (
                agent TEXT PRIMARY KEY,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                avg_latency_ms REAL DEFAULT 0,
                avg_fitness REAL DEFAULT 0,
                last_used TEXT DEFAULT '',
                streak INTEGER DEFAULT 0,
                reputation REAL DEFAULT 0.5
            )
        """)

        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS model_scores (
                provider TEXT,
                model TEXT,
                calls INTEGER DEFAULT 0,
                successes INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                avg_latency_ms REAL DEFAULT 0,
                reputation REAL DEFAULT 0.5,
                PRIMARY KEY (provider, model)
            )
        """)

        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS action_history (
                id TEXT PRIMARY KEY,
                agent TEXT NOT NULL,
                action TEXT NOT NULL,
                success INTEGER DEFAULT 0,
                fitness REAL DEFAULT 0,
                latency_ms REAL DEFAULT 0,
                model TEXT DEFAULT '',
                provider TEXT DEFAULT '',
                tokens INTEGER DEFAULT 0,
                created_at TEXT DEFAULT ''
            )
        """)

        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_action_agent ON action_history(agent, success)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_action_time ON action_history(created_at)
        """)
        self._conn.commit()

    # ── Record Outcomes ─────────────────────────────────────────────────

    def record_action(self, action_id: str, agent: str, action: str,
                      success: bool, latency_ms: float, fitness: float = 0.0,
                      model: str = "", provider: str = "", tokens: int = 0):
        """Record one action for learning."""
        now = datetime.now(timezone.utc).isoformat()

        # Insert history
        self._conn.execute(
            """INSERT INTO action_history 
               (id, agent, action, success, fitness, latency_ms, model, provider, tokens, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (action_id, agent, action, int(success), fitness, latency_ms,
             model, provider, tokens, now),
        )

        # Update agent score
        cur = self._conn.execute("SELECT * FROM agent_scores WHERE agent = ?", (agent,))
        row = cur.fetchone()

        if row:
            # Update existing
            new_success = row[1] + (1 if success else 0)
            new_failure = row[2] + (0 if success else 1)
            total = new_success + new_failure
            new_avg_latency = (row[3] * (total - 1) + latency_ms) / total
            new_avg_fitness = (row[4] * (total - 1) + fitness) / total
            new_streak = row[6] + 1 if success else 0

            self._conn.execute(
                """UPDATE agent_scores SET 
                   success_count=?, failure_count=?, avg_latency_ms=?, 
                   avg_fitness=?, last_used=?, streak=?, reputation=?
                   WHERE agent=?""",
                (new_success, new_failure, new_avg_latency, new_avg_fitness,
                 now, new_streak,
                 self._calc_reputation(new_success, new_failure, new_avg_latency),
                 agent),
            )
        else:
            rep = self._calc_reputation(1 if success else 0, 0 if success else 1, latency_ms)
            self._conn.execute(
                """INSERT INTO agent_scores VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (agent, 1 if success else 0, 0 if success else 1,
                 latency_ms, fitness, now, 1 if success else 0, rep),
            )

        # Update model score if available
        if provider and model:
            self._update_model_score(provider, model, success, latency_ms, tokens)

        self._conn.commit()

    # ── Query Reputation ────────────────────────────────────────────────

    def get_agent_reputation(self, agent: str) -> AgentScore:
        """Get reputation for a specific agent."""
        if agent in self._agent_cache:
            return self._agent_cache[agent]

        cur = self._conn.execute("SELECT * FROM agent_scores WHERE agent = ?", (agent,))
        row = cur.fetchone()
        if row:
            s = AgentScore(
                agent=row[0], success_count=row[1], failure_count=row[2],
                avg_latency_ms=row[3], avg_fitness=row[4], last_used=row[5],
                streak=row[6], reputation=row[7],
            )
        else:
            s = AgentScore(agent=agent)

        self._agent_cache[agent] = s
        return s

    def get_all_agent_scores(self) -> List[AgentScore]:
        """Get all agent scores, sorted by reputation descending."""
        cur = self._conn.execute(
            "SELECT * FROM agent_scores ORDER BY reputation DESC"
        )
        return [
            AgentScore(
                agent=r[0], success_count=r[1], failure_count=r[2],
                avg_latency_ms=r[3], avg_fitness=r[4], last_used=r[5],
                streak=r[6], reputation=r[7],
            )
            for r in cur.fetchall()
        ]

    def get_best_agents(self, min_reputation: float = 0.4, top_k: int = 5) -> List[str]:
        """Get best agents above reputation threshold."""
        cur = self._conn.execute(
            "SELECT agent FROM agent_scores WHERE reputation >= ? ORDER BY reputation DESC LIMIT ?",
            (min_reputation, top_k),
        )
        return [r[0] for r in cur.fetchall()]

    def get_model_reputation(self, provider: str, model: str) -> ModelScore:
        """Get reputation for a specific model."""
        key = f"{provider}:{model}"
        if key in self._model_cache:
            return self._model_cache[key]

        cur = self._conn.execute(
            "SELECT * FROM model_scores WHERE provider = ? AND model = ?",
            (provider, model),
        )
        row = cur.fetchone()
        if row:
            s = ModelScore(
                provider=row[0], model=row[1], calls=row[2],
                successes=row[3], total_tokens=row[4],
                avg_latency_ms=row[5], reputation=row[6],
            )
        else:
            s = ModelScore(provider=provider, model=model)

        self._model_cache[key] = s
        return s

    def get_best_models(self, min_reputation: float = 0.3) -> List[Dict]:
        """Get best LLM models for routing."""
        cur = self._conn.execute(
            "SELECT provider, model, reputation, avg_latency_ms, successes, calls "
            "FROM model_scores WHERE reputation >= ? ORDER BY reputation DESC",
            (min_reputation,),
        )
        return [
            {"provider": r[0], "model": r[1], "reputation": r[2],
             "avg_latency_ms": r[3], "successes": r[4], "calls": r[5]}
            for r in cur.fetchall()
        ]

    # ── Learning ────────────────────────────────────────────────────────

    def get_recent_actions(self, limit: int = 20) -> List[Dict]:
        """Get recent action history for learning."""
        cur = self._conn.execute(
            "SELECT * FROM action_history ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [
            {"id": r[0], "agent": r[1], "action": r[2], "success": bool(r[3]),
             "fitness": r[4], "latency_ms": r[5], "model": r[6], "provider": r[7],
             "tokens": r[8], "created_at": r[9]}
            for r in cur.fetchall()
        ]

    def get_success_rate(self, agent: Optional[str] = None) -> float:
        """Overall success rate, optionally filtered by agent."""
        if agent:
            cur = self._conn.execute(
                "SELECT AVG(success) FROM action_history WHERE agent = ?",
                (agent,),
            )
        else:
            cur = self._conn.execute("SELECT AVG(success) FROM action_history")
        row = cur.fetchone()
        return row[0] if row[0] is not None else 0.0

    def get_stats(self) -> Dict[str, Any]:
        """Full reputation stats."""
        total = self._conn.execute("SELECT COUNT(*) FROM action_history").fetchone()[0]
        successes = self._conn.execute(
            "SELECT COUNT(*) FROM action_history WHERE success = 1"
        ).fetchone()[0]

        return {
            "total_actions": total,
            "total_successes": successes,
            "overall_success_rate": f"{successes / max(total, 1):.1%}",
            "agents_tracked": self._conn.execute(
                "SELECT COUNT(*) FROM agent_scores"
            ).fetchone()[0],
            "models_tracked": self._conn.execute(
                "SELECT COUNT(*) FROM model_scores"
            ).fetchone()[0],
            "top_agents": [
                {"agent": a.agent, "reputation": f"{a.reputation:.1%}", "streak": a.streak}
                for a in self.get_all_agent_scores()[:5]
            ],
        }

    # ── Internal ────────────────────────────────────────────────────────

    def _update_model_score(self, provider: str, model: str,
                            success: bool, latency_ms: float, tokens: int):
        cur = self._conn.execute(
            "SELECT * FROM model_scores WHERE provider = ? AND model = ?",
            (provider, model),
        )
        row = cur.fetchone()

        if row:
            new_calls = row[2] + 1
            new_successes = row[3] + (1 if success else 0)
            new_avg_latency = (row[5] * row[2] + latency_ms) / new_calls
            new_tokens = row[4] + tokens
            rep = new_successes / new_calls if new_calls > 0 else 0.5

            self._conn.execute(
                """UPDATE model_scores SET 
                   calls=?, successes=?, total_tokens=?, avg_latency_ms=?, reputation=?
                   WHERE provider=? AND model=?""",
                (new_calls, new_successes, new_tokens, new_avg_latency, rep,
                 provider, model),
            )
        else:
            rep = 1.0 if success else 0.0
            self._conn.execute(
                "INSERT INTO model_scores VALUES (?, ?, 1, ?, ?, ?, ?)",
                (provider, model, 1 if success else 0, tokens, latency_ms, rep),
            )

        self._model_cache.pop(f"{provider}:{model}", None)  # Invalidate cache

    @staticmethod
    def _calc_reputation(successes: int, failures: int, avg_latency: float) -> float:
        """Weighted reputation: success rate × latency bonus."""
        total = successes + failures
        if total == 0:
            return 0.5
        rate = successes / total

        # Latency bonus: faster agents get bonus
        latency_factor = max(0.0, min(1.0, 1.0 - (avg_latency / 10000.0)))

        # Combine: 70% success rate + 30% latency factor
        return (rate * 0.7) + (latency_factor * 0.3)

    def reset(self):
        """Reset all reputation data."""
        for t in ("agent_scores", "model_scores", "action_history"):
            self._conn.execute(f"DELETE FROM {t}")
        self._conn.commit()
        self._agent_cache.clear()
        self._model_cache.clear()
