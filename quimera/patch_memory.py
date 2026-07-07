"""
Patch Memory — Learning loop for successful fixes.

When Engineer Loop applies a fix that passes validation, we store:
  - The error pattern (e.g., "return string from int function")
  - The fix applied (e.g., "change int to const char*")
  - The confidence score

Next time the same pattern appears, we skip LLM and apply directly.
"""
import json
import os
import hashlib
from dataclasses import dataclass
from typing import List, Optional

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "patch_memory.json")


@dataclass
class PatchMemoryEntry:
    pattern: str
    fix_type: str
    fix_template: str
    confidence: float
    success_count: int = 0
    total_attempts: int = 0


class PatchMemory:
    """Learning loop: remembers what worked and reapplies."""

    def __init__(self):
        self.entries: List[PatchMemoryEntry] = []
        self._load()

    def _load(self):
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE) as f:
                    data = json.load(f)
                for d in data:
                    self.entries.append(PatchMemoryEntry(**d))
            except Exception:
                pass

    def _save(self):
        with open(MEMORY_FILE, 'w') as f:
            json.dump([e.__dict__ for e in self.entries], f, indent=2)

    def find_match(self, error_message: str) -> Optional[PatchMemoryEntry]:
        for entry in self.entries:
            if self._pattern_matches(entry.pattern, error_message):
                return entry
        return None

    def learn(self, error_message: str, fix_type: str,
              fix_template: str, success: bool):
        existing = self.find_match(error_message)
        if existing:
            existing.total_attempts += 1
            if success:
                existing.success_count += 1
            existing.confidence = existing.success_count / existing.total_attempts
        else:
            entry = PatchMemoryEntry(
                pattern=error_message,
                fix_type=fix_type,
                fix_template=fix_template,
                confidence=1.0 if success else 0.5,
                success_count=1 if success else 0,
                total_attempts=1,
            )
            self.entries.append(entry)
        self._save()

    def _pattern_matches(self, stored: str, error: str) -> bool:
        import re
        s = set(re.sub(r'[^a-z ]', ' ', stored.lower()).split())
        e = set(re.sub(r'[^a-z ]', ' ', error.lower()).split())
        return len(s & e) >= 3
