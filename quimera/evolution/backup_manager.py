"""
Backup Manager — Rollback de 30 dias para toda evolução.

Princípio: NADA é excluído. Tudo que é substituído vai para backup.

Cada backup:
  - Armazena o conteúdo original antes da modificação
  - Tem TTL de 30 dias (após isso, expira automaticamente)
  - Permite rollback instantâneo com um comando
  - Registra quem fez a mudança, quando e por quê

O backup é feito NO MOMENTO do deploy — não depois.
Se o deploy falhar, o backup garante rollback atômico.

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
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("quimera.evolution.backup")


@dataclass
class BackupRecord:
    """Registro de backup de 30 dias."""
    id: str = field(default_factory=lambda: f"BAK-{uuid.uuid4().hex[:8]}")
    file_path: str = ""                        # Arquivo original
    backup_path: str = ""                      # Caminho do backup
    original_content: str = ""                 # Conteúdo original salvo
    file_size: int = 0
    reason: str = ""                           # Por que o backup foi feito
    proposal_id: Optional[str] = None          # Proposta relacionada
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str = ""                       # +30 dias
    restored: bool = False
    restored_at: Optional[str] = None
    
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > datetime.fromisoformat(self.expires_at)


class BackupManager:
    """Gerencia backups de 30 dias com rollback instantâneo.
    
    Regras:
      - Todo deploy gera backup automático
      - Backup expira em 30 dias (pode ser renovado)
      - Rollback restaura o conteúdo original
      - Backups são armazenados em logs/backups/
    """
    
    BACKUP_TTL_DAYS = 30
    
    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root)
        self.backup_dir = self.workspace_root / "logs" / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        self._records: Dict[str, BackupRecord] = {}
        self._load_index()
        self._clean_expired()
    
    def _index_path(self) -> Path:
        return self.backup_dir / "backup_index.json"
    
    def _load_index(self):
        """Carrega índice de backups."""
        idx = self._index_path()
        if idx.exists():
            try:
                data = json.loads(idx.read_text())
                for item in data:
                    bak = BackupRecord(**item)
                    self._records[bak.id] = bak
            except Exception as e:
                logger.warning(f"Failed to load backup index: {e}")
    
    def _save_index(self):
        """Salva índice de backups."""
        data = [asdict(r) for r in self._records.values()]
        self._index_path().write_text(json.dumps(data, indent=2, default=str))
    
    def _clean_expired(self):
        """Remove backups expirados (> 30 dias)."""
        expired = []
        for bid, rec in self._records.items():
            if rec.is_expired():
                expired.append(bid)
                # Remover arquivo físico
                if rec.backup_path and os.path.exists(rec.backup_path):
                    os.remove(rec.backup_path)
                    logger.info(f"🗑️  Expired backup removed: {rec.id} ({rec.file_path})")
        
        for bid in expired:
            del self._records[bid]
        
        if expired:
            self._save_index()
    
    def create_backup(
        self,
        file_path: str,
        reason: str = "",
        proposal_id: Optional[str] = None,
    ) -> Optional[str]:
        """Cria backup de um arquivo antes de modificá-lo.
        
        Args:
            file_path: Caminho do arquivo a ser backupeado
            reason: Motivo do backup
            proposal_id: ID da proposta que motivou o backup
            
        Returns:
            backup_id ou None se o arquivo não existe
        """
        fp = Path(file_path)
        if not fp.exists():
            logger.warning(f"Cannot backup nonexistent file: {file_path}")
            return None
        
        # Ler conteúdo original
        original = fp.read_text(errors='ignore')
        file_size = fp.stat().st_size
        
        # Criar diretório de backup
        backup_id = f"BAK-{uuid.uuid4().hex[:8]}"
        backup_path = self.backup_dir / f"{backup_id}_{fp.name}"
        
        # Copiar arquivo
        shutil.copy2(file_path, backup_path)
        
        # Registrar
        record = BackupRecord(
            id=backup_id,
            file_path=str(fp.absolute()),
            backup_path=str(backup_path.absolute()),
            original_content=original,
            file_size=file_size,
            reason=reason,
            proposal_id=proposal_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            expires_at=(datetime.now(timezone.utc) + timedelta(days=self.BACKUP_TTL_DAYS)).isoformat(),
        )
        
        self._records[backup_id] = record
        self._save_index()
        
        logger.info(f"💾 Backup created: {backup_id} — {fp.name} ({file_size} bytes) — expires in {self.BACKUP_TTL_DAYS}d")
        return backup_id
    
    def restore_backup(self, backup_id: str) -> bool:
        """Restaura um backup (rollback).
        
        Args:
            backup_id: ID do backup a restaurar
            
        Returns:
            True se restaurado com sucesso
        """
        if backup_id not in self._records:
            logger.error(f"Backup {backup_id} not found")
            return False
        
        record = self._records[backup_id]
        
        if record.is_expired():
            logger.error(f"Backup {backup_id} expired at {record.expires_at}")
            return False
        
        if not record.backup_path or not os.path.exists(record.backup_path):
            logger.error(f"Backup file missing: {record.backup_path}")
            return False
        
        try:
            # Restaurar conteúdo
            target = Path(record.file_path)
            backup_content = Path(record.backup_path).read_text(errors='ignore')
            target.write_text(backup_content)
            
            record.restored = True
            record.restored_at = datetime.now(timezone.utc).isoformat()
            self._save_index()
            
            logger.info(f"↩️  Backup restored: {backup_id} → {record.file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore backup {backup_id}: {e}")
            return False
    
    def get_active_backups(self) -> List[BackupRecord]:
        """Retorna backups ativos (não expirados)."""
        self._clean_expired()
        return [r for r in self._records.values() if not r.is_expired()]
    
    def get_backups_for_file(self, file_path: str) -> List[BackupRecord]:
        """Retorna backups para um arquivo específico."""
        fp = str(Path(file_path).absolute())
        return [r for r in self._records.values() if r.file_path == fp and not r.is_expired()]
    
    def renew_backup(self, backup_id: str, extra_days: int = 30) -> bool:
        """Renova TTL de um backup."""
        if backup_id not in self._records:
            return False
        
        record = self._records[backup_id]
        record.expires_at = (datetime.now(timezone.utc) + timedelta(days=extra_days)).isoformat()
        self._save_index()
        logger.info(f"🔄 Backup {backup_id} renewed for {extra_days} more days")
        return True
    
    def get_stats(self) -> Dict:
        """Estatísticas do BackupManager."""
        active = self.get_active_backups()
        return {
            "total_backups": len(self._records),
            "active_backups": len(active),
            "expired_backups": len(self._records) - len(active),
            "restored_backups": len([r for r in self._records.values() if r.restored]),
            "total_size_bytes": sum(r.file_size for r in self._records.values()),
            "oldest_backup": min((r.created_at for r in active), default="N/A"),
            "ttl_days": self.BACKUP_TTL_DAYS,
        }


# Global
backup_manager = BackupManager()
