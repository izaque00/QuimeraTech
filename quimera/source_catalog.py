"""
Source Catalog — learns which knowledge sources are most useful.

Tracks real outcomes per source (Patch Memory, StackOverflow, GitHub, CVE, etc.)
and re-ranks sources based on actual success rates.

After 1000+ executions, the Quimera queries sources in optimal order,
not the hardcoded L1→L7 order.
"""
import os, json, time
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class SourceStats:
    source: str
    times_queried: int = 0
    times_useful: int = 0
    patches_from_this_source: int = 0
    patches_accepted: int = 0
    avg_confidence_when_useful: float = 0.0
    last_useful: str = ""


class SourceCatalog:
    """
    Tracks per-source effectiveness.

    Usage:
        catalog = SourceCatalog()
        catalog.record_query("stackoverflow", useful=True, patches=1, accepted=1, conf=0.65)
        catalog.record_query("github_issues", useful=False)

        # Get optimal search order
        order = catalog.optimal_order()
        # → ["patch_memory", "engineering_kb", "github_commits", "man_pages", ...]
    """

    def __init__(self, project_root: str = ""):
        self.project_root = Path(project_root or os.getcwd())
        self.path = self.project_root / "logs" / "source_catalog.json"
        self.stats = self._load()

    def record_query(self, source: str, useful: bool,
                     patches: int = 0, accepted: int = 0,
                     confidence: float = 0.0):
        """Record that a source was queried and whether it produced useful results."""
        if source not in self.stats:
            self.stats[source] = SourceStats(source=source)

        s = self.stats[source]
        s.times_queried += 1
        if useful:
            s.times_useful += 1
            s.last_useful = time.strftime("%Y-%m-%d %H:%M")
        s.patches_from_this_source += patches
        s.patches_accepted += accepted
        if confidence > 0:
            if s.avg_confidence_when_useful == 0:
                s.avg_confidence_when_useful = confidence
            else:
                s.avg_confidence_when_useful = (
                    s.avg_confidence_when_useful * 0.9 + confidence * 0.1
                )

        self._save()

    def usefulness_rate(self, source: str) -> float:
        """Return usefulness rate for a source (0.0-1.0)."""
        if source not in self.stats:
            return 0.5  # unknown => neutral
        s = self.stats[source]
        if s.times_queried == 0:
            return 0.5
        # Rate with Laplace smoothing (avoid 0% for new sources)
        return (s.times_useful + 1) / (s.times_queried + 2)

    def acceptance_rate(self, source: str) -> float:
        """Return patch acceptance rate for patches from this source."""
        if source not in self.stats:
            return 0.0
        s = self.stats[source]
        if s.patches_from_this_source == 0:
            return 0.0
        return s.patches_accepted / s.patches_from_this_source

    def optimal_order(self) -> List[str]:
        """
        Return sources in optimal query order based on real performance.

        Score = usefulness_rate * 0.6 + acceptance_rate * 0.4
        Sources with insufficient data retain neutral position.
        """
        scored = []
        for source in self.stats:
            s = self.stats[source]
            if s.times_queried < 3:
                scored.append((source, 0.5))  # insufficient data
            else:
                score = (self.usefulness_rate(source) * 0.6 +
                         self.acceptance_rate(source) * 0.4)
                scored.append((source, score))

        scored.sort(key=lambda x: -x[1])
        return [s[0] for s in scored]

    def summary(self) -> str:
        """Human-readable summary of source performance."""
        lines = ["**Source Catalog — Real Performance**\n"]
        lines.append(f"{'Source':<22s} {'Queries':>7s} {'Useful':>7s} "
                     f"{'Rate':>6s} {'Patches':>8s} {'Accepted':>8s}")
        lines.append("-" * 70)

        for source, s in sorted(self.stats.items(),
                                key=lambda x: -self.usefulness_rate(x[0])):
            rate = self.usefulness_rate(source)
            acc = self.acceptance_rate(source)
            lines.append(
                f"{source:<22s} {s.times_queried:>7d} {s.times_useful:>7d} "
                f"{rate:>5.0%} {s.patches_from_this_source:>8d} "
                f"{s.patches_accepted:>8d} ({acc:.0%})"
            )
        return '\n'.join(lines)

    # ── Internal ────────────────────────────────────

    def _load(self) -> Dict:
        if self.path.exists():
            try:
                with open(self.path) as f:
                    data = json.load(f)
                return {k: SourceStats(**v) for k, v in data.items()}
            except Exception:
                pass
        return {}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {k: {
            'source': s.source, 'times_queried': s.times_queried,
            'times_useful': s.times_useful, 'patches_from_this_source': s.patches_from_this_source,
            'patches_accepted': s.patches_accepted,
            'avg_confidence_when_useful': s.avg_confidence_when_useful,
            'last_useful': s.last_useful,
        } for k, s in self.stats.items()}
        with open(self.path, 'w') as f:
            json.dump(data, f, indent=2)


if __name__ == "__main__":
    catalog = SourceCatalog()
    # Simulate real data
    catalog.record_query("patch_memory", True, patches=3, accepted=3, confidence=0.92)
    catalog.record_query("engineering_kb", True, patches=2, accepted=2, confidence=0.78)
    catalog.record_query("github_commits", True, patches=5, accepted=4, confidence=0.72)
    catalog.record_query("man_pages", True, patches=1, accepted=0, confidence=0.50)
    catalog.record_query("stackoverflow", False)
    catalog.record_query("stackoverflow", True, patches=1, accepted=1, confidence=0.55)
    catalog.record_query("cve_database", False)
    catalog.record_query("llm", True, patches=2, accepted=1, confidence=0.40)
    catalog.record_query("llm", False)
    print(catalog.summary())
    print(f"\nOptimal order: {catalog.optimal_order()}")
