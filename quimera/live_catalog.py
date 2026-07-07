"""
Live Catalog — Quimera learns from real executions.

Tracks every patch attempt per model, per CWE, per project type.
Updates model scores based on actual success rates, NOT static benchmarks.

After 500+ executions, the catalog reflects REAL performance,
not marketing claims.
"""
import os, json, time
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class ModelStats:
    model: str
    provider: str
    total_attempts: int = 0
    successes: int = 0
    failures: int = 0
    avg_time_ms: float = 0.0
    total_tokens: int = 0
    # Per-CWE breakdown
    cwe_stats: Dict[str, dict] = field(default_factory=dict)
    # Per-project-type breakdown
    project_stats: Dict[str, dict] = field(default_factory=dict)
    last_used: str = ""
    first_used: str = ""


class LiveCatalog:
    """
    Tracks real-world model performance.

    Reads/writes to logs/live_catalog.json.
    Auto-updates model scores in models.json.
    """

    def __init__(self, project_root: str = ""):
        self.project_root = Path(project_root or os.getcwd())
        self.catalog_path = self.project_root / "logs" / "live_catalog.json"
        self.models_path = Path(__file__).parent / "models.json"

        # Load existing catalog
        self.stats = self._load()

    def record_attempt(self, model: str, provider: str, cwe: str,
                       project_type: str, success: bool,
                       time_ms: float, tokens: int = 0):
        """Record a patch attempt and its outcome."""
        if model not in self.stats:
            self.stats[model] = ModelStats(
                model=model, provider=provider,
                first_used=time.strftime('%Y-%m-%d')
            )

        s = self.stats[model]
        s.total_attempts += 1
        if success:
            s.successes += 1
        else:
            s.failures += 1

        # Running average time
        if s.avg_time_ms == 0:
            s.avg_time_ms = time_ms
        else:
            s.avg_time_ms = s.avg_time_ms * 0.9 + time_ms * 0.1

        s.total_tokens += tokens
        s.last_used = time.strftime('%Y-%m-%d %H:%M')

        # Per-CWE
        if cwe not in s.cwe_stats:
            s.cwe_stats[cwe] = {'success': 0, 'total': 0, 'avg_time_ms': 0}
        s.cwe_stats[cwe]['total'] += 1
        if success:
            s.cwe_stats[cwe]['success'] += 1
        if s.cwe_stats[cwe]['avg_time_ms'] == 0:
            s.cwe_stats[cwe]['avg_time_ms'] = time_ms
        else:
            s.cwe_stats[cwe]['avg_time_ms'] = \
                s.cwe_stats[cwe]['avg_time_ms'] * 0.9 + time_ms * 0.1

        # Per-project-type
        if project_type not in s.project_stats:
            s.project_stats[project_type] = {'success': 0, 'total': 0}
        s.project_stats[project_type]['total'] += 1
        if success:
            s.project_stats[project_type]['success'] += 1

        self._save()

    def get_score(self, model: str, cwe: str = "", project_type: str = "") -> float:
        """
        Get a model's real-world score.

        Weights: 60% overall success rate, 25% CWE-specific, 15% project-specific.
        If no real data, returns 0 (use static catalog score instead).
        """
        if model not in self.stats:
            return 0.0

        s = self.stats[model]
        if s.total_attempts == 0:
            return 0.0

        # Overall rate (60%)
        overall_rate = s.successes / s.total_attempts

        # CWE-specific (25%)
        cwe_rate = 0.5  # neutral if no data
        if cwe and cwe in s.cwe_stats:
            cs = s.cwe_stats[cwe]
            if cs['total'] > 0:
                cwe_rate = cs['success'] / cs['total']

        # Project-specific (15%)
        proj_rate = 0.5
        if project_type and project_type in s.project_stats:
            ps = s.project_stats[project_type]
            if ps['total'] > 0:
                proj_rate = ps['success'] / ps['total']

        return 0.60 * overall_rate + 0.25 * cwe_rate + 0.15 * proj_rate

    def summary(self) -> str:
        """Human-readable summary of all model performance."""
        lines = ["**Catálogo Vivo — Performance Real**\n"]
        lines.append(f"{'Modelo':<25s} {'Tentativas':>10s} {'Sucesso':>8s} "
                     f"{'Tempo':>8s} {'Último uso':<16s}")
        lines.append("-" * 75)

        for model, s in sorted(self.stats.items(),
                               key=lambda x: -x[1].total_attempts):
            rate = f"{s.successes/s.total_attempts:.0%}" if s.total_attempts > 0 else "—"
            time_str = f"{s.avg_time_ms:.0f}ms" if s.avg_time_ms > 0 else "—"
            lines.append(
                f"{model:<25s} {s.total_attempts:>10d} {rate:>8s} "
                f"{time_str:>8s} {s.last_used:<16s}"
            )

        return '\n'.join(lines)

    def sync_to_static_catalog(self):
        """Update models.json with real performance data."""
        if not self.models_path.exists():
            return

        with open(self.models_path) as f:
            catalog = json.load(f)

        for model_id, model_info in catalog.get('models', {}).items():
            if model_id in self.stats:
                s = self.stats[model_id]
                if s.total_attempts >= 5:  # Only update with enough data
                    score = self.get_score(model_id)
                    caps = model_info.get('capabilities', {})
                    # Update code_generation based on real data
                    caps['code_generation'] = min(99, int(score * 100))
                    caps['speed_ms'] = int(s.avg_time_ms) if s.avg_time_ms > 0 else caps.get('speed_ms', 5000)

        # Write updated catalog
        with open(self.models_path, 'w') as f:
            json.dump(catalog, f, indent=2)

    # ── Internal ────────────────────────────────────

    def _load(self) -> Dict:
        if self.catalog_path.exists():
            try:
                with open(self.catalog_path) as f:
                    data = json.load(f)
                result = {}
                for model, sdata in data.items():
                    result[model] = ModelStats(**sdata)
                return result
            except Exception:
                pass
        return {}

    def _save(self):
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        for model, s in self.stats.items():
            data[model] = {
                'model': s.model,
                'provider': s.provider,
                'total_attempts': s.total_attempts,
                'successes': s.successes,
                'failures': s.failures,
                'avg_time_ms': s.avg_time_ms,
                'total_tokens': s.total_tokens,
                'cwe_stats': s.cwe_stats,
                'project_stats': s.project_stats,
                'last_used': s.last_used,
                'first_used': s.first_used,
            }
        with open(self.catalog_path, 'w') as f:
            json.dump(data, f, indent=2)


if __name__ == "__main__":
    # Self-test
    catalog = LiveCatalog()

    # Simulate some executions
    catalog.record_attempt('gpt-oss-120b:free', 'openrouter',
                          'CWE-416', 'make', True, 4500, 1500)
    catalog.record_attempt('gpt-oss-120b:free', 'openrouter',
                          'CWE-416', 'cmake', True, 5200, 2000)
    catalog.record_attempt('gpt-oss-120b:free', 'openrouter',
                          'CWE-476', 'kernel', False, 8000, 3000)
    catalog.record_attempt('mistral-small-latest', 'mistral',
                          'CWE-416', 'make', True, 3000, 800)

    print(catalog.summary())

    print(f"\nScore for gpt-oss-120b:free (CWE-416): {catalog.get_score('gpt-oss-120b:free', 'CWE-416'):.2%}")
    print(f"Score for mistral-small-latest (CWE-416): {catalog.get_score('mistral-small-latest', 'CWE-416'):.2%}")
