"""
Proposal Authority — Quem pode criar propostas de evolução.

Regra fundamental: NEM TODO MÓDULO pode gerar propostas.
Apenas fontes autorizadas e com trilha de auditoria.

Fontes autorizadas:
  1. SISTEMA_B (torneio)  → prioridade ALTA   — baseado em evidência comparativa
  2. ENGINEERING_KB        → prioridade MÉDIA  — baseado em padrões conhecidos
  3. LOCAL_AI              → prioridade BAIXA  — baseado em conversa com usuário
  4. HUMAN                 → prioridade MÁXIMA — usuário solicita diretamente

Fontes BLOQUEADAS:
  - PLANNER     → NUNCA gera proposta (só lê o catálogo)
  - PIPELINE    → NUNCA gera proposta (só executa)
  - DISPATCHER  → NUNCA gera proposta (só roteia)

Cada proposta carrega source + priority para evitar duplicação
e permitir que o Evolution Core priorize conflitos.

Autor: Quimera MarkX — OMinivers
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ProposalSource(str, Enum):
    """Fonte autorizada a gerar propostas."""
    SISTEMA_B = "sistema_b"           # Torneio entre estratégias
    ENGINEERING_KB = "engineering_kb" # Padrões conhecidos de vulnerabilidade
    LOCAL_AI = "local_ai"             # Conversa com usuário
    HUMAN = "human"                   # Usuário solicita diretamente


class ProposalPriority(str, Enum):
    """Prioridade da proposta — determina ordem de processamento."""
    MAXIMUM = "maximum"    # Humano solicitou
    HIGH = "high"          # Sistema B (torneio) com evidência forte
    MEDIUM = "medium"      # EngineeringKB com padrão conhecido
    LOW = "low"            # LocalAI com sugestão conversacional


# Mapeamento: fonte → prioridade padrão
SOURCE_PRIORITY = {
    ProposalSource.HUMAN: ProposalPriority.MAXIMUM,
    ProposalSource.SISTEMA_B: ProposalPriority.HIGH,
    ProposalSource.ENGINEERING_KB: ProposalPriority.MEDIUM,
    ProposalSource.LOCAL_AI: ProposalPriority.LOW,
}


# Fontes BLOQUEADAS — estes módulos NUNCA geram propostas
BLOCKED_SOURCES = {"planner", "pipeline", "dispatcher", "executor", "router"}


@dataclass
class ProposalOrigin:
    """Origem auditável de uma proposta."""
    source: ProposalSource
    priority: ProposalPriority
    evidence_refs: list = field(default_factory=list)  # Referências a dados que motivaram
    context_snapshot: Optional[str] = None              # Snapshot do estado no momento
    
    def is_valid(self) -> bool:
        """True se a fonte está autorizada."""
        return self.source in ProposalSource
    
    def summary(self) -> str:
        return f"[{self.source.value}] priority={self.priority.value}"


class ProposalAuthority:
    """Gatekeeper de autoridade — decide se uma fonte pode criar proposta.
    
    Regras:
      1. Apenas fontes em ProposalSource podem criar
      2. Planner/pipeline/dispatcher NUNCA criam (bloqueados)
      3. Conflitos resolvidos por prioridade
      4. Propostas duplicadas (mesmo target + mesma fonte) são detectadas
    """
    
    def __init__(self):
        self._recent_targets: dict = {}  # target → source → timestamp (evita duplicação)
    
    def authorize(self, source: str, target_file: str = "") -> tuple[bool, Optional[ProposalSource], ProposalPriority]:
        """Verifica se uma fonte está autorizada a criar proposta.
        
        Returns:
            (allowed, source_enum, priority)
        """
        if source in BLOCKED_SOURCES:
            return False, None, ProposalPriority.LOW
        
        try:
            src = ProposalSource(source)
        except ValueError:
            return False, None, ProposalPriority.LOW
        
        priority = SOURCE_PRIORITY.get(src, ProposalPriority.LOW)
        
        # Verificar duplicação: mesma fonte + mesmo target em < 1 hora
        import time
        key = f"{source}:{target_file}"
        last = self._recent_targets.get(key, 0)
        if time.time() - last < 3600:
            return False, src, priority  # Duplicado
        
        self._recent_targets[key] = time.time()
        return True, src, priority
    
    def resolve_conflict(self, proposals: list) -> list:
        """Ordena propostas conflitantes por prioridade."""
        priority_order = {
            ProposalPriority.MAXIMUM: 0,
            ProposalPriority.HIGH: 1,
            ProposalPriority.MEDIUM: 2,
            ProposalPriority.LOW: 3,
        }
        return sorted(proposals, key=lambda p: priority_order.get(p.get("priority", ProposalPriority.LOW), 99))


# Global
proposal_authority = ProposalAuthority()
