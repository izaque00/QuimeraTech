"""
ProjectContext v2 — Arquitetura de Consciência Situacional Desacoplada (MetaX v4.1.0)

Evita o "Context Overfitting" e o "Monstro Semântico" separando rigidamente:
  1. FACTS (Fatos determinísticos: compilador, testes, AST, arquivos, logs)
  2. BELIEFS (Crenças, hipóteses, interpretações da IA local e do usuário)
  3. DECISIONS (Decisões tomadas, planos executados, patches gerados)

Introduz também:
  - Versionamento estrito com Snapshots e Branching (v1 -> v2 -> v3)
  - Isolamento de Multi-Contextos (Repair, Security, Performance)
  - Detecção de Context Drift (inflação, contradição e viés acumulado)

Autor: Quimera MarkX — MetaX
"""
import json
import time
import copy
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class ContextType(str, Enum):
    GLOBAL = "global"
    REPAIR = "repair"
    SECURITY = "security"
    PERFORMANCE = "performance"
    EXPLORATION = "exploration"


class ConfidenceLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERIFIED = "verified"  # Apenas após validação física (compilador/testes)


@dataclass
class FactNode:
    """Fato determinístico imutável verificado por telemetria física."""
    key: str
    value: Any
    source: str                 # "compiler", "pytest", "docker", "ast_parser"
    timestamp: str
    verified: bool = True


@dataclass
class BeliefNode:
    """Crença ou hipótese subjetiva formulada por IA ou informada pelo usuário."""
    key: str
    value: Any
    confidence: ConfidenceLevel
    source: str                 # "local_ai", "user_input"
    timestamp: str
    contradicts: List[str] = field(default_factory=list) # Chaves de fatos/crenças que contradizem isso


@dataclass
class DecisionNode:
    """Decisão de engenharia tomada e seu resultado físico."""
    id: str
    action: str                 # "apply_patch", "run_profiler"
    rationale: str              # Por que foi tomada
    timestamp: str
    success: Optional[bool] = None
    metric_impact: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextMetadata:
    version: int = 1
    parent_version: Optional[int] = None
    context_type: ContextType = ContextType.GLOBAL
    created_at: str = ""
    branch_name: str = "main"


@dataclass
class ProjectContextV2:
    """ProjectContext desacoplado com tripartição semântica e branching."""
    # Metadados de versionamento
    meta: ContextMetadata = field(default_factory=ContextMetadata)
    
    # Identidade básica (Fatos raiz)
    project_name: str = ""
    project_path: str = ""
    
    # 🧠 Tripartição da Consciência
    facts: Dict[str, FactNode] = field(default_factory=dict)       # Realidade telemetrada
    beliefs: Dict[str, BeliefNode] = field(default_factory=dict)   # Hipóteses e intenções
    decisions: List[DecisionNode] = field(default_factory=list)    # Ações e impactos
    
    # Histórico de Branches/Snapshots
    lineage: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_fact(self, key: str, value: Any, source: str):
        """Registra um fato imutável."""
        self.facts[key] = FactNode(
            key=key,
            value=value,
            source=source,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            verified=True
        )
        # Ao adicionar um fato, recalcula se há contradições nas crenças existentes
        self._resolve_contradictions()

    def add_belief(self, key: str, value: Any, confidence: ConfidenceLevel, source: str):
        """Adiciona uma hipótese subjetiva."""
        self.beliefs[key] = BeliefNode(
            key=key,
            value=value,
            confidence=confidence,
            source=source,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )
        self._resolve_contradictions()

    def record_decision(self, action: str, rationale: str, success: Optional[bool] = None, impact: Optional[Dict] = None) -> str:
        """Registra uma decisão macro."""
        dec_id = f"DEC-{len(self.decisions) + 1:03d}"
        self.decisions.append(DecisionNode(
            id=dec_id,
            action=action,
            rationale=rationale,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            success=success,
            metric_impact=impact or {}
        ))
        return dec_id

    def fork(self, context_type: ContextType, branch_name: str) -> 'ProjectContextV2':
        """Cria um branch isolado do contexto (ex: de Global para Repair)."""
        new_ctx = copy.deepcopy(self)
        new_ctx.meta.parent_version = self.meta.version
        new_ctx.meta.version = 1
        new_ctx.meta.context_type = context_type
        new_ctx.meta.branch_name = branch_name
        new_ctx.meta.created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        
        # Limpar decisões e crenças específicas do branch anterior para evitar vazamento
        if context_type != ContextType.GLOBAL:
            new_ctx.beliefs = {k: v for k, v in self.beliefs.items() if v.confidence == ConfidenceLevel.VERIFIED}
            new_ctx.decisions = []
            
        # Registrar linhagem
        new_ctx.lineage.append({
            "parent_version": self.meta.version,
            "branch": branch_name,
            "forked_at": new_ctx.meta.created_at
        })
        return new_ctx

    def merge_back(self, source_branch: 'ProjectContextV2'):
        """Mescla fatos e decisões verificadas de volta para o contexto principal."""
        # Apenas mescla fatos verificados e decisões de sucesso
        for k, fact in source_branch.facts.items():
            if fact.verified:
                self.add_fact(k, fact.value, f"merge:{source_branch.meta.branch_name}")
        
        for dec in source_branch.decisions:
            if dec.success:
                self.decisions.append(dec)
                
        self.meta.version += 1
        self._resolve_contradictions()

    def _resolve_contradictions(self):
        """Monitor de Consistência Interna — detecta se crenças contradizem os fatos."""
        for b_key, belief in self.beliefs.items():
            # Exemplo de contradição clássica: Crença de "está lento" vs Fato de "latency_ms < 50ms"
            if b_key == "is_slow" and "latency_ms" in self.facts:
                lat = self.facts["latency_ms"].value
                if lat < 50 and belief.value is True:
                    if "latency_ms" not in belief.contradicts:
                        belief.contradicts.append("latency_ms")
                        belief.confidence = ConfidenceLevel.LOW
            
            # Outro: Crença de "erro de importação" vs Fato de "pytest_passed = True"
            if b_key == "has_import_error" and "pytest_passed" in self.facts:
                if self.facts["pytest_passed"].value is True:
                    if "pytest_passed" not in belief.contradicts:
                        belief.contradicts.append("pytest_passed")
                        belief.confidence = ConfidenceLevel.LOW

    def check_drift(self) -> Dict[str, Any]:
        """Context Drift Monitor: Verifica se o contexto está inflado, contraditório ou enviesado."""
        inflated = len(self.facts) + len(self.beliefs) > 100
        contradictions = [b_key for b_key, b in self.beliefs.items() if b.contradicts]
        
        # Viés acumulado: muitas decisões falhas seguidas sem resetar crenças
        failed_decisions = sum(1 for d in self.decisions if d.success is False)
        biased = failed_decisions >= 3
        
        drift_score = 0
        if inflated: drift_score += 30
        if contradictions: drift_score += len(contradictions) * 15
        if biased: drift_score += 40
        
        return {
            "drift_score": min(drift_score, 100),
            "inflated": inflated,
            "contradictions": contradictions,
            "biased": biased,
            "recommendation": "Sugerido purgar crenças de baixa confiança e re-executar telemetria física" if drift_score > 50 else "Contexto estável e saudável"
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "meta": asdict(self.meta),
            "project_name": self.project_name,
            "project_path": self.project_path,
            "facts": {k: asdict(v) for k, v in self.facts.items()},
            "beliefs": {k: asdict(v) for k, v in self.beliefs.items()},
            "decisions": [asdict(d) for d in self.decisions],
            "drift": self.check_drift(),
        }

    def summary(self) -> str:
        d = self.check_drift()
        lines = [
            f"🧠 ProjectContextV2 [{self.meta.context_type.value.upper()}] (v{self.meta.version} - branch: {self.meta.branch_name})",
            f"   Fatos verificados (facts): {len(self.facts)}",
            f"   Crenças/Hipóteses (beliefs): {len(self.beliefs)} ({len(d['contradictions'])} contradições)",
            f"   Decisões registradas: {len(self.decisions)}",
            f"   Context Drift Score: {d['drift_score']}/100 ({d['recommendation']})"
        ]
        return "\n".join(lines)
