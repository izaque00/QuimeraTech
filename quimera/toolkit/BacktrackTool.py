# quimera/toolkit/BacktrackTool.py

import time
import os
import shutil
import hashlib
from pathlib import Path
from collections import deque # Para histórico limitado em memória
from typing import Optional, Dict, Any, Callable # Adicionado Callable
import logging

# Importa o módulo de logging personalizado
from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)

class RefinoTrilha:
    """
    Gerencia o histórico de versões de um arquivo para permitir rollback preciso.
    Armazena snapshots do código em pontos críticos de refino.
    """
    def __init__(self, mod_base: str):
        self.modulo_path = Path(mod_base)
        self.historico_dir = Path("cache/backups/refino_trilhas") / self.modulo_path.name # Pasta de backups específica por arquivo
        self.historico_dir.mkdir(parents=True, exist_ok=True) # Garante que o diretório exista
        self.ativo = False # Controle se o rastreamento está ativo
        self.tentativas: deque[Dict[str, Any]] = deque(maxlen=10) # Armazena os últimos 10 snapshots em memória

        # Opcional: Carregar histórico de disco na inicialização (se a Quimera reiniciar)
        # self._carregar_historico_do_disco()

        montar_log(f"RefinoTrilha inicializada para: {self.modulo_path.name}", log_level="INFO")

    def toggle_gravacao(self, estado: bool):
        """
        Ativa ou desativa o rastreamento de mudanças.
        Quando ativado, o estado atual do arquivo é salvo.
        """
        self.ativo = estado
        if self.ativo:
            montar_log(f"Rastreamento de '{self.modulo_path.name}' ativado. Salvando estado inicial.", log_level="INFO")
            self.rastrear() # Grava o estado inicial ao ativar

    def rastrear(self):
        """
        Salva o estado atual do arquivo no histórico.
        Um snapshot é feito no diretório de histórico e uma referência é adicionada ao deque em memória.
        """
        if not self.ativo or not self.modulo_path.exists():
            return

        try:
            current_content = self.modulo_path.read_text(encoding='utf-8', errors='ignore')
            current_hash = hashlib.sha256(current_content.encode('utf-8')).hexdigest()

            # Evita salvar duplicatas sucessivas
            if self.tentativas and self.tentativas[-1]["hash"] == current_hash:
                return

            # Caminho do snapshot no disco
            snapshot_path = self.historico_dir / f"{current_hash}.snap"
            snapshot_path.write_text(current_content, encoding='utf-8')

            self.tentativas.append({
                "timestamp": time.time(),
                "hash": current_hash,
                "path": str(snapshot_path),
                "content_len": len(current_content)
            })
            montar_log(f"[TRILHA] Snapshot de '{self.modulo_path.name}' salvo: {current_hash[:8]}...", log_level="DEBUG")

        except Exception as e:
            montar_log(f"[TRILHA] Falha ao rastrear '{self.modulo_path.name}': {e}", log_level="ERROR")

    def rollback(self, hash_val: Optional[str] = None) -> Optional[str]:
        """
        Reverte o arquivo para uma versão anterior no histórico.
        Prioriza o hash específico, depois a penúltima versão em memória,
        e por último tenta restaurar de um snapshot no disco.
        """
        target_snapshot = None

        if hash_val:
            # Tenta encontrar na memória recente
            for snap in reversed(self.tentativas): # Busca do mais recente para o mais antigo
                if snap["hash"] == hash_val:
                    target_snapshot = snap
                    break

            if not target_snapshot:
                montar_log(f"[ROLLBACK] Snapshot com hash '{hash_val[:8]}...' não encontrado na memória. Tentando disco...", log_level="WARNING")
                # Se não está na memória, tenta buscar no disco diretamente
                snapshot_path_disk = self.historico_dir / f"{hash_val}.snap"
                if snapshot_path_disk.exists():
                    target_snapshot = {"path": str(snapshot_path_disk), "hash": hash_val} # Cria um dict mock para leitura
                    montar_log(f"[ROLLBACK] Recuperado snapshot do disco: {hash_val[:8]}...", log_level="INFO")

        elif len(self.tentativas) >= 2:
            target_snapshot = self.tentativas[-2] # Penúltima versão em memória
            montar_log(f"[ROLLBACK] Revertendo para a penúltima versão em memória.", log_level="INFO")

        else:
            montar_log("[ROLLBACK] Histórico insuficiente para rollback. Mínimo de 2 snapshots necessários.", log_level="WARNING")
            return None

        if not target_snapshot:
            montar_log("[ROLLBACK] Nenhuma versão alvo para rollback encontrada.", log_level="ERROR")
            return None

        try:
            content_to_restore = Path(target_snapshot["path"]).read_text(encoding='utf-8', errors='ignore')
            self.modulo_path.write_text(content_to_restore, encoding='utf-8')

            montar_log(f"[ROLLBACK] '{self.modulo_path.name}' restaurado para hash: {target_snapshot.get('hash', 'N/A')[:8]}...", log_level="INFO")
            return content_to_restore
        except Exception as e:
            montar_log(f"[ROLLBACK] Falha crítica ao restaurar '{self.modulo_path.name}': {e}", log_level="ERROR")
            return None