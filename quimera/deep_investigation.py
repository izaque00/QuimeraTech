"""Deep Investigation Mode — activated when UNKNOWN."""
import time
from dataclasses import dataclass, field
from enum import Enum

class InvestigationStatus(Enum):
    COLLECTING="collecting"; CONSULTING="consulting"; VALIDATING="validating"
    EXHAUSTED="exhausted"; PARTIAL="partial"; DOSSIER_READY="dossier_ready"

@dataclass
class InvestigationDossier:
    error_description: str = ""
    context: dict = field(default_factory=dict)
    hypotheses_generated: int = 0
    hypotheses_tested: int = 0
    hypotheses_passed: int = 0
    root_causes: list = field(default_factory=list)
    failed: list = field(default_factory=list)
    recommendations: list = field(default_factory=list)
    status: InvestigationStatus = InvestigationStatus.COLLECTING
    
    def to_markdown(self):
        lines = ["# Deep Investigation Report","",f"**Status:** {self.status.value}",f"**Error:** {self.error_description[:200]}"]
        if self.root_causes:
            lines+=["","## Root Cause Candidates"]
            for rc in self.root_causes[:5]: lines.append(f"- {rc}")
        if self.failed:
            lines+=["","## Failed Attempts"]
            for f in self.failed[-5:]: lines.append(f"- {f}")
        if self.status==InvestigationStatus.EXHAUSTED:
            lines+=["","> All hypotheses exhausted. Human investigation required."]
        if self.recommendations:
            lines+=["","## Recommendations"]
            for r in self.recommendations: lines.append(f"- {r}")
        return "\n".join(lines)

class DeepInvestigation:
    MAX_HYPOTHESES = 12
    def __init__(self, sandbox=False, llm=False):
        self.sandbox=sandbox; self.llm=llm; self.dossier=None
    
    def investigate(self, error_ctx, code="", env=None):
        d = InvestigationDossier(error_description=str(error_ctx),
            context={"env":env or {},"code":code[:500],"ts":time.time()})
        d.status=InvestigationStatus.CONSULTING
        hyps=self._consult(error_ctx,code,env)
        d.hypotheses_generated=len(hyps)
        if self.sandbox:
            d.status=InvestigationStatus.VALIDATING
            for h in hyps:
                d.hypotheses_tested+=1
                if self._validate(h,code):
                    d.hypotheses_passed+=1; d.root_causes.append(h)
                else: d.failed.append(f"Failed: {h.get('desc','')[:100]}")
        if d.hypotheses_passed>0:
            d.status=InvestigationStatus.PARTIAL
            d.recommendations.append("Promote passing hypotheses to CANDIDATE_FIX")
        else:
            d.status=InvestigationStatus.EXHAUSTED
            d.recommendations.append("No automated fix found. Manual investigation required.")
        d.status=InvestigationStatus.DOSSIER_READY
        self.dossier=d; return d
    
    def _consult(self,ctx,code,env): return []
    def _validate(self,hyp,code): return False
    
    def admit_unknown(self):
        if not self.dossier: return "No investigation."
        return f"Investigation exhausted: {self.dossier.hypotheses_tested} hypotheses tested, none passed. Dossier ready."
