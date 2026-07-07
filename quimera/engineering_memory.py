"""
Engineering Memory — historical record of every decision the Quimera made.

Records for every fix attempt:
  • Error → Solution → Commit used → Model → Time → Compiler → Architecture → Result

This is NOT just Patch Memory (which stores patches).
This stores the FULL CONTEXT of each decision:
  - What was the project?
  - What compiler/version?
  - What knowledge sources helped?
  - Which model generated the patch?
  - How long did it take?
  - Was the patch accepted?
  - What validators passed/failed?

After months of use, this becomes an invaluable training dataset
for improving the CandidateGenerator and KnowledgeBroker.
"""
import os, json, time, uuid
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class EngineeringRecord:
    """One complete fix attempt record."""
    id: str = ""
    timestamp: str = ""
    project: str = ""
    project_type: str = ""  # kernel, cmake, make, etc.
    compiler: str = ""
    compiler_version: str = ""
    architecture: str = ""
    cwe: str = ""
    error_description: str = ""
    file_path: str = ""
    line_number: int = 0

    # Knowledge phase
    knowledge_sources_used: List[str] = field(default_factory=list)
    knowledge_results_count: int = 0

    # Generation phase
    model_used: str = ""
    provider_used: str = ""
    candidates_generated: int = 0
    approaches_tried: List[str] = field(default_factory=list)

    # Validation phase
    best_approach: str = ""
    compiled: bool = False
    build_passed: bool = False
    tests_passed: bool = False
    asan_clean: bool = False
    ubsan_clean: bool = False

    # Outcome
    patch_accepted: bool = False
    patch_code: str = ""
    total_time_ms: float = 0.0
    retry_count: int = 0
    final_result: str = ""  # "success", "failed", "partial"


class EngineeringMemory:
    """
    Complete historical memory of all Quimera decisions.

    Usage:
        mem = EngineeringMemory()
        mem.record(
            project="linux-kernel", cwe="CWE-416",
            model="gpt-oss-120b:free", compiled=True,
            asan_clean=True, patch_accepted=True,
            ...
        )
        # Later: query by project, CWE, compiler, architecture
        records = mem.query(project="linux-kernel", cwe="CWE-416")
    """

    def __init__(self, project_root: str = ""):
        self.project_root = Path(project_root or os.getcwd())
        self.memory_path = self.project_root / "logs" / "engineering_memory.jsonl"

    def record(self, **kwargs) -> str:
        """Record an engineering decision. Returns the record ID."""
        record = EngineeringRecord(
            id=str(uuid.uuid4())[:8],
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            **{k: v for k, v in kwargs.items()
               if k in EngineeringRecord.__dataclass_fields__}
        )

        # Append to JSONL
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.memory_path, 'a') as f:
            f.write(json.dumps(asdict(record)) + '\n')

        return record.id

    def query(self, project: str = "", cwe: str = "",
              compiler: str = "", architecture: str = "",
              accepted_only: bool = False,
              limit: int = 20) -> List[EngineeringRecord]:
        """
        Query engineering memory with filters.

        Examples:
            mem.query(cwe="CWE-416", accepted_only=True)
            mem.query(project="linux-kernel", compiler="gcc")
            mem.query(architecture="x86_64")
        """
        if not self.memory_path.exists():
            return []

        results = []
        with open(self.memory_path) as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if project and project.lower() not in data.get("project", "").lower():
                        continue
                    if cwe and cwe not in data.get("cwe", ""):
                        continue
                    if compiler and compiler.lower() not in data.get("compiler", "").lower():
                        continue
                    if architecture and architecture not in data.get("architecture", ""):
                        continue
                    if accepted_only and not data.get("patch_accepted", False):
                        continue
                    results.append(EngineeringRecord(**data))
                except Exception:
                    pass

                if len(results) >= limit:
                    break

        return results

    def stats(self) -> Dict:
        """Aggregate statistics from engineering memory."""
        if not self.memory_path.exists():
            return {"total_records": 0}

        records = []
        with open(self.memory_path) as f:
            for line in f:
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass

        if not records:
            return {"total_records": 0}

        accepted = sum(1 for r in records if r.get("patch_accepted"))
        cwes = {}
        models = {}
        projects = {}
        total_time = 0

        for r in records:
            cwe = r.get("cwe", "unknown")
            cwes[cwe] = cwes.get(cwe, 0) + 1

            model = r.get("model_used", "unknown")
            if model not in models:
                models[model] = {"total": 0, "accepted": 0}
            models[model]["total"] += 1
            if r.get("patch_accepted"):
                models[model]["accepted"] += 1

            proj = r.get("project", "unknown")
            projects[proj] = projects.get(proj, 0) + 1

            total_time += r.get("total_time_ms", 0)

        return {
            "total_records": len(records),
            "accepted": accepted,
            "acceptance_rate": f"{accepted/len(records):.0%}",
            "total_time_ms": total_time,
            "avg_time_ms": total_time / len(records),
            "cwes": dict(sorted(cwes.items(), key=lambda x: -x[1])[:10]),
            "models": {k: {**v, "rate": f"{v['accepted']/v['total']:.0%}"}
                       for k, v in models.items()},
            "projects": dict(sorted(projects.items(), key=lambda x: -x[1])[:10]),
        }

    def find_best_approach(self, cwe: str, project_type: str = "") -> Optional[Dict]:
        """
        Find the most successful approach for a given CWE + project type.

        Returns the approach with highest acceptance rate.
        """
        records = self.query(cwe=cwe, accepted_only=True)
        if not records:
            return None

        approaches = {}
        for r in records:
            approach = r.best_approach
            if not approach:
                continue
            if approach not in approaches:
                approaches[approach] = {"total": 0, "accepted": 0}
            approaches[approach]["total"] += 1
            approaches[approach]["accepted"] += 1  # all records are accepted

        if not approaches:
            return None

        best = max(approaches.items(), key=lambda x: x[1]["total"])
        return {"approach": best[0], "times_used": best[1]["total"]}

    def summary(self) -> str:
        """Human-readable summary."""
        s = self.stats()
        lines = ["**Engineering Memory**\n"]
        lines.append(f"Total records: {s.get('total_records', 0)}")
        lines.append(f"Accepted: {s.get('accepted', 0)} ({s.get('acceptance_rate', '0%')})")
        lines.append(f"Avg time: {s.get('avg_time_ms', 0):.0f}ms")

        lines.append("\nTop CWEs:")
        for cwe, count in s.get("cwes", {}).items():
            lines.append(f"  {cwe}: {count}")

        lines.append("\nModel performance:")
        for model, data in s.get("models", {}).items():
            lines.append(f"  {model}: {data['accepted']}/{data['total']} ({data['rate']})")

        return '\n'.join(lines)


if __name__ == "__main__":
    mem = EngineeringMemory()

    # Simulate building a memory
    mem.record(
        project="linux-kernel", project_type="kernel",
        compiler="gcc", compiler_version="13.2", architecture="x86_64",
        cwe="CWE-416", error_description="use-after-free in scheduler",
        file_path="kernel/sched/core.c", line_number=4242,
        knowledge_sources_used=["patch_memory", "github_commits", "man_pages"],
        knowledge_results_count=5,
        model_used="gpt-oss-120b:free", provider_used="openrouter",
        candidates_generated=12, approaches_tried=["null_after_free", "goto_cleanup"],
        best_approach="null_after_free",
        compiled=True, build_passed=True, tests_passed=True,
        asan_clean=True, ubsan_clean=True,
        patch_accepted=True,
        patch_code="free(sched);\nsched = NULL;",
        total_time_ms=4500, retry_count=1, final_result="success",
    )

    mem.record(
        project="linux-kernel", project_type="kernel",
        compiler="gcc", compiler_version="13.2", architecture="arm64",
        cwe="CWE-416", error_description="use-after-free in mm subsystem",
        file_path="mm/slab.c", line_number=842,
        knowledge_sources_used=["patch_memory", "cve_database"],
        knowledge_results_count=3,
        model_used="gpt-oss-120b:free", provider_used="openrouter",
        candidates_generated=8, approaches_tried=["null_after_free"],
        best_approach="null_after_free",
        compiled=True, build_passed=True, tests_passed=True,
        asan_clean=True, ubsan_clean=True,
        patch_accepted=True,
        patch_code="free(slab);\nslab = NULL;",
        total_time_ms=3200, retry_count=0, final_result="success",
    )

    mem.record(
        project="openssl", project_type="make",
        compiler="clang", compiler_version="18", architecture="x86_64",
        cwe="CWE-476", error_description="NULL dereference in TLS",
        file_path="ssl/tls.c", line_number=150,
        knowledge_sources_used=["stackoverflow", "llm"],
        knowledge_results_count=2,
        model_used="mistral-small-latest", provider_used="mistral",
        candidates_generated=5, approaches_tried=["null_guard"],
        best_approach="null_guard",
        compiled=True, build_passed=True, tests_passed=False,
        asan_clean=False, ubsan_clean=True,
        patch_accepted=False,
        patch_code="if (!ctx) return ERR;",
        total_time_ms=8000, retry_count=2, final_result="failed",
    )

    print(mem.summary())

    print(f"\nBest approach for CWE-416 in kernel:")
    best = mem.find_best_approach("CWE-416")
    if best:
        print(f"  {best['approach']} — used {best['times_used']} times successfully")

    print(f"\nQuery: CWE-416, accepted only:")
    recs = mem.query(cwe="CWE-416", accepted_only=True)
    for r in recs:
        print(f"  {r.id}: {r.project} — {r.best_approach} — {r.total_time_ms:.0f}ms")
