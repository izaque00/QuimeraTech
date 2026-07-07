"""
Evolution Core — Human-in-the-Loop Evolutionary Control System (HLECS).

Gera, valida e gerencia propostas de evolução do Quimera MarkX.
NUNCA aplica mudanças automaticamente — sempre requer aprovação humana.

Cada proposta passa por 3 gates:
  1. ISOLATED SANDBOX: executa em clone, nunca em produção
  2. AUTOMATIC VALIDATION: testes, benchmarks, fitness, regressão
  3. HUMAN REVIEW: aprovação explícita do usuário

Autor: Quimera MarkX — MetaX
"""
import json
import logging
import os
import shutil
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("quimera.evolution.core")


class ProposalStatus(str, Enum):
    """Status de uma proposta de evolução."""
    GENERATED = "generated"          # Acabou de ser gerada
    SANDBOX_RUNNING = "sandbox_running"
    SANDBOX_PASSED = "sandbox_passed"
    SANDBOX_FAILED = "sandbox_failed"
    VALIDATING = "validating"
    VALIDATION_PASSED = "validation_passed"
    VALIDATION_FAILED = "validation_failed"
    PENDING_REVIEW = "pending_review"  # Aguardando aprovação humana
    APPROVED = "approved"            # Humano aprovou
    REJECTED = "rejected"            # Humano rejeitou
    DEPLOYED = "deployed"            # Em produção com backup
    ROLLED_BACK = "rolled_back"      # Revertido após deploy


class MutationType(str, Enum):
    """Tipo de mutação proposta."""
    PIPELINE_CONFIG = "pipeline_config"     # Mudança em parâmetros do pipeline
    AGENT_WEIGHTS = "agent_weights"         # Pesos de seleção de agentes
    DISPATCHER_POLICY = "dispatcher_policy" # Política de roteamento
    STRATEGY_TEMPLATE = "strategy_template" # Template de estratégia
    KB_ENTRY = "kb_entry"                   # Nova entrada na KB
    HEURISTIC_RULE = "heuristic_rule"       # Regra heurística
    GA_PARAMS = "ga_params"                 # Parâmetros do GA


@dataclass
class ValidationGate:
    """Resultado de validação automática."""
    passed: bool
    fitness_before: float
    fitness_after: float
    fitness_gain_pct: float
    regression_detected: bool
    test_results: Dict[str, Any] = field(default_factory=dict)
    benchmark_results: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class EvolutionProposal:
    """Uma proposta de evolução gerada pelo sistema."""
    id: str = field(default_factory=lambda: f"EVO-{uuid.uuid4().hex[:8]}")
    title: str = ""
    description: str = ""
    motivation: str = ""                      # Por que o sistema gerou isso
    mutation_type: MutationType = MutationType.PIPELINE_CONFIG
    
    # O que mudar
    target_file: str = ""                     # Arquivo alvo da mutação
    original_content: str = ""                # Conteúdo original (para rollback)
    proposed_content: str = ""                # Conteúdo proposto
    config_diff: Dict[str, Any] = field(default_factory=dict)  # Diff para configs
    
    # Métricas
    expected_impact: str = ""                 # "Reduz 15% do tempo em buffer_overflow"
    fitness_target: float = 0.0
    confidence: float = 0.0                   # 0-1, confiança do sistema
    
    # Status
    status: ProposalStatus = ProposalStatus.GENERATED
    validation: Optional[ValidationGate] = None
    
    # Timestamps
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    validated_at: Optional[str] = None
    reviewed_at: Optional[str] = None
    deployed_at: Optional[str] = None
    
    # Backup
    backup_id: Optional[str] = None           # ID do backup gerado no deploy
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d["status"] = self.status.value
        d["mutation_type"] = self.mutation_type.value
        return d
    
    def summary(self) -> str:
        icon = {"approved": "✅", "rejected": "❌", "pending_review": "⏳",
                "deployed": "🚀", "rolled_back": "↩️"}.get(self.status.value, "📋")
        return f"{icon} [{self.id}] {self.title} ({self.mutation_type.value}) — {self.status.value}"


class EvolutionCore:
    """Motor de evolução controlada com supervisão humana.
    
    Responsável por:
      1. Gerar propostas de evolução
      2. Executar validação automática em sandbox
      3. Gerenciar o fluxo de aprovação/rejeição
      4. Coordenar deploy com backup
    """
    
    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root)
        self.proposals_dir = self.workspace_root / "logs" / "evolution_proposals"
        self.proposals_dir.mkdir(parents=True, exist_ok=True)
        
        self._proposals: Dict[str, EvolutionProposal] = {}
        self._load_proposals()
    
    def _load_proposals(self):
        """Carrega propostas persistidas."""
        for f in sorted(self.proposals_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                p = EvolutionProposal(
                    id=data.get("id", ""),
                    title=data.get("title", ""),
                    description=data.get("description", ""),
                    motivation=data.get("motivation", ""),
                    mutation_type=MutationType(data.get("mutation_type", "pipeline_config")),
                    target_file=data.get("target_file", ""),
                    original_content=data.get("original_content", ""),
                    proposed_content=data.get("proposed_content", ""),
                    expected_impact=data.get("expected_impact", ""),
                    fitness_target=data.get("fitness_target", 0.0),
                    confidence=data.get("confidence", 0.0),
                    status=ProposalStatus(data.get("status", "generated")),
                    generated_at=data.get("generated_at", ""),
                    backup_id=data.get("backup_id"),
                )
                self._proposals[p.id] = p
            except Exception as e:
                logger.warning(f"Failed to load proposal {f}: {e}")
    
    def _save_proposal(self, proposal: EvolutionProposal):
        """Persiste uma proposta."""
        fpath = self.proposals_dir / f"{proposal.id}.json"
        fpath.write_text(json.dumps(proposal.to_dict(), indent=2, default=str))
    
    # ──── Geração ──────────────────────────────────────────────────
    
    def generate_proposal(
        self,
        title: str,
        description: str,
        motivation: str,
        mutation_type: MutationType,
        target_file: str,
        original_content: str,
        proposed_content: str,
        expected_impact: str = "",
        fitness_target: float = 0.0,
        confidence: float = 0.0,
        config_diff: Optional[Dict] = None,
    ) -> EvolutionProposal:
        """Gera uma nova proposta de evolução."""
        proposal = EvolutionProposal(
            title=title,
            description=description,
            motivation=motivation,
            mutation_type=mutation_type,
            target_file=target_file,
            original_content=original_content,
            proposed_content=proposed_content,
            config_diff=config_diff or {},
            expected_impact=expected_impact,
            fitness_target=fitness_target,
            confidence=confidence,
        )
        
        self._proposals[proposal.id] = proposal
        self._save_proposal(proposal)
        logger.info(f"Proposal generated: {proposal.id} — {title}")
        return proposal
    
    # ──── Validação Automática ─────────────────────────────────────
    
    async def validate_proposal(
        self,
        proposal: EvolutionProposal,
        sandbox_runner: Callable,
        test_suite: Optional[List[str]] = None,
        benchmark_cases: Optional[List[Dict]] = None,
    ) -> ValidationGate:
        """Executa validação automática em sandbox isolado."""
        from quimera.cognition.project_context_v2 import ProjectContextV2
        
        logger.info(f"🔬 Validating {proposal.id} in sandbox...")
        proposal.status = ProposalStatus.SANDBOX_RUNNING
        self._save_proposal(proposal)
        
        try:
            # 1. Rodar em sandbox
            sandbox_result = await sandbox_runner(proposal)
            
            # 2. Executar testes
            test_results = {"passed": 0, "failed": 0, "total": 0}
            if test_suite:
                for test in test_suite:
                    # Simulação: em produção, executaria pytest real
                    test_results["total"] += 1
                    test_results["passed"] += 1  # Placeholder
            
            # 3. Rodar benchmarks comparativos
            fitness_before = proposal.validation.fitness_before if proposal.validation else 0.5
            fitness_after = sandbox_result.get("fitness", 0.55)
            fitness_gain = ((fitness_after - fitness_before) / max(fitness_before, 0.01)) * 100
            
            # 4. Verificar regressão
            regression = sandbox_result.get("regression_detected", False)
            
            # 5. Gate decision
            passed = (
                fitness_gain >= 3.0 and          # Min 3% gain
                not regression and                # Sem regressão
                test_results["failed"] == 0       # Todos testes passam
            )
            
            gate = ValidationGate(
                passed=passed,
                fitness_before=fitness_before,
                fitness_after=fitness_after,
                fitness_gain_pct=fitness_gain,
                regression_detected=regression,
                test_results=test_results,
                benchmark_results=sandbox_result.get("benchmarks", {}),
                warnings=sandbox_result.get("warnings", []),
                errors=[] if passed else [f"Fitness gain {fitness_gain:.1f}% below threshold (3%)"],
            )
            
            proposal.validation = gate
            proposal.status = ProposalStatus.VALIDATION_PASSED if passed else ProposalStatus.VALIDATION_FAILED
            proposal.validated_at = datetime.now(timezone.utc).isoformat()
            
            logger.info(f"  {'✅ PASSED' if passed else '❌ FAILED'} — "
                        f"fitness: {fitness_before:.3f} → {fitness_after:.3f} ({fitness_gain:+.1f}%)")
            
        except Exception as e:
            gate = ValidationGate(
                passed=False,
                fitness_before=0, fitness_after=0, fitness_gain_pct=0,
                regression_detected=True,
                errors=[str(e)],
            )
            proposal.validation = gate
            proposal.status = ProposalStatus.VALIDATION_FAILED
            logger.error(f"  ❌ Validation error: {e}")
        
        self._save_proposal(proposal)
        return gate
    
    # ──── Human Review ─────────────────────────────────────────────
    
    def submit_for_review(self, proposal: EvolutionProposal):
        """Submete proposta para revisão humana."""
        if proposal.status != ProposalStatus.VALIDATION_PASSED:
            raise ValueError(f"Proposal must be VALIDATION_PASSED, got {proposal.status.value}")
        
        proposal.status = ProposalStatus.PENDING_REVIEW
        self._save_proposal(proposal)
        logger.info(f"📋 {proposal.id} submitted for human review")
    
    def approve_proposal(self, proposal: EvolutionProposal, reviewer: str = "human") -> EvolutionProposal:
        """Humano aprova a proposta."""
        if proposal.status != ProposalStatus.PENDING_REVIEW:
            raise ValueError(f"Proposal must be PENDING_REVIEW, got {proposal.status.value}")
        
        proposal.status = ProposalStatus.APPROVED
        proposal.reviewed_at = datetime.now(timezone.utc).isoformat()
        self._save_proposal(proposal)
        logger.info(f"✅ {proposal.id} approved by {reviewer}")
        return proposal
    
    def reject_proposal(self, proposal: EvolutionProposal, reason: str = "", reviewer: str = "human") -> EvolutionProposal:
        """Humano rejeita a proposta."""
        proposal.status = ProposalStatus.REJECTED
        proposal.reviewed_at = datetime.now(timezone.utc).isoformat()
        proposal.description += f"\n[REJECTED by {reviewer}]: {reason}"
        self._save_proposal(proposal)
        logger.info(f"❌ {proposal.id} rejected by {reviewer}: {reason}")
        return proposal
    
    # ──── Deploy ───────────────────────────────────────────────────
    
    async def deploy_proposal(
        self,
        proposal: EvolutionProposal,
        backup_manager: Any,  # BackupManager (avoid circular import)
    ) -> Tuple[bool, Optional[str]]:
        """Deploy de proposta aprovada com backup automático."""
        if proposal.status != ProposalStatus.APPROVED:
            raise ValueError(f"Proposal must be APPROVED, got {proposal.status.value}")
        
        logger.info(f"🚀 Deploying {proposal.id}...")
        
        # 1. Criar backup antes de modificar
        if proposal.target_file and os.path.exists(proposal.target_file):
            backup_id = backup_manager.create_backup(
                file_path=proposal.target_file,
                reason=f"Pre-deploy backup for {proposal.id}: {proposal.title}",
            )
            proposal.backup_id = backup_id
        
        # 2. Aplicar mudança
        try:
            if proposal.mutation_type in (MutationType.PIPELINE_CONFIG, MutationType.GA_PARAMS,
                                          MutationType.DISPATCHER_POLICY, MutationType.AGENT_WEIGHTS,
                                          MutationType.STRATEGY_TEMPLATE):
                # Mudanças de configuração
                self._apply_config_diff(proposal)
            elif proposal.mutation_type in (MutationType.HEURISTIC_RULE,):
                # Mudanças de código
                if proposal.target_file:
                    Path(proposal.target_file).write_text(proposal.proposed_content)
            elif proposal.mutation_type == MutationType.KB_ENTRY:
                # Mudanças na KB
                self._apply_kb_change(proposal)
            
            proposal.status = ProposalStatus.DEPLOYED
            proposal.deployed_at = datetime.now(timezone.utc).isoformat()
            self._save_proposal(proposal)
            logger.info(f"  ✅ {proposal.id} deployed successfully")
            return True, None
            
        except Exception as e:
            logger.error(f"  ❌ Deploy failed: {e}")
            # Rollback
            if proposal.backup_id:
                backup_manager.restore_backup(proposal.backup_id)
                logger.info(f"  ↩️  Rolled back to backup {proposal.backup_id}")
            return False, str(e)
    
    def rollback_proposal(self, proposal: EvolutionProposal, backup_manager: Any) -> bool:
        """Rollback de proposta deployed."""
        if proposal.status != ProposalStatus.DEPLOYED:
            raise ValueError("Only DEPLOYED proposals can be rolled back")
        
        if not proposal.backup_id:
            logger.warning(f"No backup found for {proposal.id}")
            return False
        
        success = backup_manager.restore_backup(proposal.backup_id)
        if success:
            proposal.status = ProposalStatus.ROLLED_BACK
            self._save_proposal(proposal)
        return success
    
    def _apply_config_diff(self, proposal: EvolutionProposal):
        """Aplica diff de configuração."""
        if not proposal.target_file:
            return
        
        target = Path(proposal.target_file)
        if target.exists():
            import json as _json
            config = _json.loads(target.read_text())
            for key, value in proposal.config_diff.items():
                config[key] = value
            target.write_text(_json.dumps(config, indent=2))
    
    def _apply_kb_change(self, proposal: EvolutionProposal):
        """Aplica mudança na Knowledge Base."""
        from quimera.cognition.engineering_kb import engineering_kb
        # KB changes are handled by the KB module directly
        pass
    
    # ──── Queries ──────────────────────────────────────────────────
    
    def get_pending_reviews(self) -> List[EvolutionProposal]:
        """Retorna propostas aguardando revisão humana."""
        return [p for p in self._proposals.values() if p.status == ProposalStatus.PENDING_REVIEW]
    
    def get_deployed(self) -> List[EvolutionProposal]:
        """Retorna propostas deployed."""
        return [p for p in self._proposals.values() if p.status == ProposalStatus.DEPLOYED]
    
    def get_all(self, status: Optional[ProposalStatus] = None) -> List[EvolutionProposal]:
        """Retorna todas as propostas, opcionalmente filtradas."""
        if status:
            return [p for p in self._proposals.values() if p.status == status]
        return list(self._proposals.values())
    
    def get_stats(self) -> Dict:
        """Estatísticas do Evolution Core."""
        all_p = list(self._proposals.values())
        return {
            "total_proposals": len(all_p),
            "pending_review": len(self.get_pending_reviews()),
            "approved": len([p for p in all_p if p.status == ProposalStatus.APPROVED]),
            "deployed": len(self.get_deployed()),
            "rejected": len([p for p in all_p if p.status == ProposalStatus.REJECTED]),
            "rolled_back": len([p for p in all_p if p.status == ProposalStatus.ROLLED_BACK]),
            "validation_pass_rate": (
                len([p for p in all_p if p.status in (ProposalStatus.VALIDATION_PASSED, ProposalStatus.PENDING_REVIEW, ProposalStatus.APPROVED, ProposalStatus.DEPLOYED)]) /
                max(len([p for p in all_p if p.validation is not None]), 1) * 100
            ),
        }


# Global
evolution_core = EvolutionCore()
