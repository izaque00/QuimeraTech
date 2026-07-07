"""Resolution States for Quimera findings."""
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
import time

class ResolutionState(Enum):
    RESOLVED = "resolved"
    CANDIDATE_FIX = "candidate_fix"
    NEEDS_INVESTIGATION = "needs_investigation"
    UNKNOWN = "unknown"
    @property
    def emoji(self):
        return {"resolved":"🟢","candidate_fix":"🟡","needs_investigation":"🟠","unknown":"🔴"}.get(self.value,"")

@dataclass
class Resolution:
    state: ResolutionState = ResolutionState.UNKNOWN
    resolved_at: Optional[float] = None
    attempts: int = 0
    hypotheses_tried: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    
    def transition(self, new_state, note=""):
        valid = {
            ResolutionState.UNKNOWN: [ResolutionState.CANDIDATE_FIX, ResolutionState.NEEDS_INVESTIGATION],
            ResolutionState.NEEDS_INVESTIGATION: [ResolutionState.CANDIDATE_FIX, ResolutionState.UNKNOWN],
            ResolutionState.CANDIDATE_FIX: [ResolutionState.RESOLVED, ResolutionState.NEEDS_INVESTIGATION, ResolutionState.UNKNOWN],
            ResolutionState.RESOLVED: [],
        }
        if new_state not in valid.get(self.state, []):
            raise ValueError(f"Invalid: {self.state.value} -> {new_state.value}")
        self.state = new_state
        if new_state == ResolutionState.RESOLVED: self.resolved_at = time.time()
        if note: self.notes.append(f"[{self.state.emoji}] {note}")
    
    def record_attempt(self, hid, passed):
        self.attempts += 1
        self.hypotheses_tried.append({"id":hid,"passed":passed,"ts":time.time()})
    
    @property
    def is_terminal(self): return self.state == ResolutionState.RESOLVED
    @property
    def needs_human(self): return self.state in (ResolutionState.UNKNOWN, ResolutionState.NEEDS_INVESTIGATION)
    
    def summary(self):
        lines = [f"{self.state.emoji} {self.state.value.upper()} ({self.attempts} attempts)"]
        for n in self.notes[-3:]: lines.append(f"  {n}")
        return "\n".join(lines)

def classify_finding(evidence):
    if evidence.total_occurrences == 0: return ResolutionState.UNKNOWN
    rr = evidence.risky_occurrences / evidence.total_occurrences
    ur = (evidence.uncertain + evidence.context_dependent) / evidence.total_occurrences
    if rr > 0.3: return ResolutionState.CANDIDATE_FIX
    if ur > 0.5: return ResolutionState.NEEDS_INVESTIGATION
    if evidence.safe_occurrences > 0.8 * evidence.total_occurrences: return ResolutionState.RESOLVED
    return ResolutionState.UNKNOWN
