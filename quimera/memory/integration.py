"""H2 Memory Pipeline — REAL SQLite + embedding store."""
import asyncio, hashlib, json, logging, os, sqlite3, time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import numpy as np

logger = logging.getLogger("quimera.memory")

@dataclass
class MemoryContext:
    error_type: str = ""; error_description: str = ""; kernel_version: str = ""
    stack_trace: str = ""; source_file: str = ""; function_name: str = ""
    tenant_id: str = "default"; extra: Dict = field(default_factory=dict)

@dataclass
class MemoryEnhancedResult:
    solutions: List[Dict] = field(default_factory=list); total_found: int = 0
    query_time_ms: float = 0.0; source: str = ""

class MemoryPipeline:
    def __init__(self, db_path: str = None, embed_dim: int = 384, auto_record: bool = False):
        self.db_path = db_path or os.path.join(os.path.expanduser("~"), ".quimera", "memory.db")
        self.embed_dim = embed_dim; self._conn = None; self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("""CREATE TABLE IF NOT EXISTS memory_entries(
            id TEXT PRIMARY KEY, error_type TEXT NOT NULL, error_hash TEXT NOT NULL,
            description TEXT, solution TEXT, patch_code TEXT,
            success INTEGER DEFAULT 0, fitness_score REAL DEFAULT 0.0,
            embedding BLOB, kernel_version TEXT DEFAULT '',
            created_at TEXT DEFAULT '', retrieval_count INTEGER DEFAULT 0)""")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_et ON memory_entries(error_type)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_eh ON memory_entries(error_hash)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_sc ON memory_entries(success, fitness_score DESC)")
        self._conn.commit()

    async def retrieve_solutions(self, ctx=None, error_type="", error_description="", top_k=5, min_similarity=0.3):
        t0 = time.monotonic()
        et = ctx.error_type if ctx else error_type; ed = ctx.error_description if ctx else error_description
        eh = self._hash(et, ed)
        cur = self._conn.execute("SELECT * FROM memory_entries WHERE error_hash=? AND success=1 ORDER BY fitness_score DESC LIMIT ?", (eh, top_k))
        rows = list(cur.fetchall())
        if len(rows) < top_k:
            qv = self._embed_vec_text(et, ed)
            similar = self._search(qv, top_k - len(rows), min_similarity)
            rows.extend(similar)
        for r in rows: self._conn.execute("UPDATE memory_entries SET retrieval_count=retrieval_count+1 WHERE id=?", (r[0],))
        self._conn.commit()
        elapsed = (time.monotonic() - t0) * 1000
        sols = [{"id": r[0], "error_type": r[1], "description": r[3], "solution": r[4], "patch_code": r[5], "fitness_score": r[6], "retrieval_count": r[10]} for r in rows[:top_k]]
        return MemoryEnhancedResult(solutions=sols, total_found=len(sols), query_time_ms=round(elapsed, 1), source="sqlite+embedding")

    async def record_outcome(self, mission_id=None, ctx=None, solution_description="", success=False, fitness_score=0.0, patch_code="", error_type="", error_description="", **kw):
        et = ctx.error_type if ctx else error_type; ed = ctx.error_description if ctx else error_description
        eid = mission_id or f"mem-{int(time.time()*1000)}"; eh = self._hash(et, ed)
        emb = self._embed_vec(et, ed, solution_description)
        self._conn.execute("INSERT OR REPLACE INTO memory_entries(id,error_type,error_hash,description,solution,patch_code,success,fitness_score,embedding,kernel_version,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (eid, et, eh, ed, solution_description, patch_code, int(success), fitness_score, emb, ctx.kernel_version if ctx else "", datetime.now(timezone.utc).isoformat()))
        self._conn.commit()

    def _search(self, qv, top_k, min_sim):
        cur = self._conn.execute("SELECT * FROM memory_entries WHERE success=1 AND embedding IS NOT NULL")
        rows = list(cur.fetchall())
        if not rows: return []
        scores = []
        for r in rows:
            try:
                vec = np.frombuffer(r[7], dtype=np.float32)
                sim = np.dot(qv, vec) / (np.linalg.norm(qv) * np.linalg.norm(vec) + 1e-8)
                if sim >= min_sim: scores.append((sim, r))
            except Exception: continue  # non-critical memory operation
        scores.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scores[:top_k]]

    def _embed_vec_text(self, text, dim=384):
        vec = np.zeros(dim, dtype=np.float32)
        for i, ch in enumerate(text.encode()): idx = (i * 7 + ch) % dim; vec[idx] += 1.0
        return vec / (np.linalg.norm(vec) + 1e-8)

    def _embed_vec(self, et, ed, sol):
        return self._embed_vec_text(f"{et}:{ed}=>{sol}").tobytes()

    def _hash(self, et, ed): return hashlib.sha256(f"{et}:{ed}".encode()).hexdigest()[:16]

    async def get_memory_stats(self):
        t = self._conn.execute("SELECT COUNT(*) FROM memory_entries").fetchone()[0]
        s = self._conn.execute("SELECT COUNT(*) FROM memory_entries WHERE success=1").fetchone()[0]
        return {"total_entries": t, "successful_entries": s, "db_path": self.db_path}
