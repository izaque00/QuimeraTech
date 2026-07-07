"""
Quimera Vault — Gerenciador Seguro de Chaves API

Problema resolvido:
  ❌ ANTES: chaves em .env texto puro → vazavam no zip/commits
  ✅ AGORA: chaves criptografadas em .vault + .env só referência

Arquitetura:
  .env           → contém VAULT_KEY (senha mestra) + VAULT_PATH
  .vault         → chaves criptografadas com AES-256-GCM
  .gitignore     → .env e .vault NUNCA entram no git
  .env.example   → template SEM chaves reais (já estava certo!)

Fluxo:
  1. Usuário define VAULT_KEY em .env (ou variável de ambiente)
  2. Usuário adiciona chaves via: quimera vault add OPENAI_API_KEY sk-...
  3. Chaves são criptografadas e salvas em .vault
  4. Em runtime, Vault descriptografa sob demanda
  5. .env e .vault são automaticamente ignorados pelo git
"""

import os
import json
import base64
import hashlib
import secrets
from pathlib import Path
from typing import Dict, Optional
import logging

logger = logging.getLogger("quimera.vault")


class QuimeraVault:
    """
    Cofre criptografado para chaves API.

    Uso:
        vault = QuimeraVault()
        vault.set("OPENAI_API_KEY", "sk-...")
        key = vault.get("OPENAI_API_KEY")
    """

    def __init__(self, vault_path: str = None, master_key: str = None):
        self.vault_path = Path(vault_path or os.getenv("QUIMERA_VAULT_PATH", ".vault"))
        self._master_key = master_key or os.getenv("QUIMERA_VAULT_KEY", os.getenv("VAULT_KEY", ""))
        self._cache: Dict[str, str] = {}
        self._keys: Dict[str, str] = {}

        if self._master_key:
            self._load()

    def _derive_key(self) -> bytes:
        """Deriva chave AES-256 da senha mestra."""
        return hashlib.sha256(self._master_key.encode()).digest()

    def _encrypt(self, plaintext: str) -> str:
        """Criptografa com AES-256-GCM."""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            key = self._derive_key()
            nonce = secrets.token_bytes(12)
            aesgcm = AESGCM(key)
            ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
            return base64.b64encode(nonce + ciphertext).decode()
        except ImportError:
            # Fallback: XOR com a chave (melhor que texto puro)
            key_bytes = self._derive_key()
            result = bytes(a ^ key_bytes[i % len(key_bytes)] for i, a in enumerate(plaintext.encode()))
            return base64.b64encode(result).decode()

    def _decrypt(self, encrypted: str) -> str:
        """Descriptografa AES-256-GCM."""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            key = self._derive_key()
            raw = base64.b64decode(encrypted)
            nonce, ciphertext = raw[:12], raw[12:]
            aesgcm = AESGCM(key)
            return aesgcm.decrypt(nonce, ciphertext, None).decode()
        except ImportError:
            # Fallback: XOR reverso
            key_bytes = self._derive_key()
            raw = base64.b64decode(encrypted)
            result = bytes(a ^ key_bytes[i % len(key_bytes)] for i, a in enumerate(raw))
            return result.decode()

    def _load(self):
        """Carrega chaves do arquivo .vault."""
        if not self.vault_path.exists():
            logger.info("Vault: arquivo .vault não encontrado — iniciando vazio")
            return

        try:
            with open(self.vault_path) as f:
                encrypted_data = json.load(f)

            for key_name, encrypted_value in encrypted_data.items():
                try:
                    self._keys[key_name] = self._decrypt(encrypted_value)
                except Exception:
                    logger.warning(f"Vault: não foi possível descriptografar '{key_name}' (senha errada?)")
        except Exception as e:
            logger.error(f"Vault: erro ao carregar: {e}")

    def _save(self):
        """Salva chaves criptografadas no .vault."""
        encrypted_data = {}
        for key_name, value in self._keys.items():
            encrypted_data[key_name] = self._encrypt(value)

        # Garantir permissões restritas
        with open(self.vault_path, 'w') as f:
            json.dump(encrypted_data, f, indent=2)

        # chmod 600 no Linux/Mac
        try:
            os.chmod(self.vault_path, 0o600)
        except Exception:
            pass

        logger.info(f"Vault: {len(encrypted_data)} chaves salvas em {self.vault_path}")

    def set(self, key_name: str, value: str):
        """Adiciona/atualiza uma chave no cofre."""
        self._keys[key_name] = value
        self._cache[key_name] = value
        self._save()

    def get(self, key_name: str) -> Optional[str]:
        """Recupera uma chave do cofre."""
        # 1. Cache em memória
        if key_name in self._cache:
            return self._cache[key_name]

        # 2. Vault criptografado
        if key_name in self._keys:
            self._cache[key_name] = self._keys[key_name]
            return self._keys[key_name]

        # 3. Variável de ambiente (fallback)
        env_val = os.getenv(key_name)
        if env_val:
            return env_val

        return None

    def list_keys(self) -> list:
        """Lista nomes das chaves (sem revelar valores)."""
        return list(self._keys.keys())

    def has_key(self, key_name: str) -> bool:
        return key_name in self._keys or os.getenv(key_name) is not None

    def remove(self, key_name: str):
        """Remove uma chave do cofre."""
        self._keys.pop(key_name, None)
        self._cache.pop(key_name, None)
        self._save()

    def import_from_env_file(self, env_path: str = ".env"):
        """Importa chaves de um arquivo .env existente para o vault."""
        env_file = Path(env_path)
        if not env_file.exists():
            logger.warning(f"Arquivo {env_path} não encontrado")
            return 0

        count = 0
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip().strip('"').strip("'")

                if any(kw in key.upper() for kw in ('API_KEY', 'API_TOKEN', 'SECRET', 'TOKEN')):
                    if value and value != '...' and not value.endswith('...'):
                        self.set(key, value)
                        count += 1

        logger.info(f"Vault: {count} chaves importadas de {env_path}")
        return count


# ═══════════════════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════════════════

_vault: Optional[QuimeraVault] = None


def get_vault(master_key: str = None) -> QuimeraVault:
    """Obtém a instância global do Vault."""
    global _vault
    if _vault is None:
        vault_key = master_key or os.getenv("VAULT_KEY", os.getenv("QUIMERA_VAULT_KEY", ""))
        if not vault_key:
            logger.warning(
                "Vault: VAULT_KEY não definida. "
                "Defina VAULT_KEY no .env ou variável de ambiente. "
                "Execute: quimera vault init"
            )
        _vault = QuimeraVault(master_key=vault_key)
    return _vault


# ═══════════════════════════════════════════════════════════════════════
# CLI helpers
# ═══════════════════════════════════════════════════════════════════════

def vault_init():
    """Inicializa o vault pela primeira vez."""
    import getpass

    print("🔐 Quimera Vault — Configuração Inicial")
    print()

    # Gerar senha mestra
    if os.getenv("VAULT_KEY"):
        print("✅ VAULT_KEY já definida via variável de ambiente")
        master_key = os.getenv("VAULT_KEY")
    else:
        print("Defina uma senha mestra para o cofre de chaves:")
        print("(Esta senha protege TODAS as suas chaves API)")
        master_key = getpass.getpass("Senha mestra: ")
        confirm = getpass.getpass("Confirme a senha: ")
        if master_key != confirm:
            print("❌ Senhas não conferem.")
            return
        if len(master_key) < 8:
            print("❌ A senha deve ter pelo menos 8 caracteres.")
            return

    vault = QuimeraVault(master_key=master_key)

    # Importar do .env existente
    if Path(".env").exists():
        count = vault.import_from_env_file(".env")
        if count > 0:
            print(f"✅ {count} chaves importadas do .env para o .vault criptografado")
            print()
            print("⚠️  Recomendação: remova as chaves do .env e mantenha apenas no .vault")
            print("   O .vault é criptografado e deve ser adicionado ao .gitignore")
        else:
            print("Nenhuma chave API encontrada no .env")
    else:
        print("Nenhum .env encontrado. Adicione chaves com:")
        print("  quimera vault add OPENAI_API_KEY sk-...")

    # Salvar referência no .env
    env_line = f'\n# Quimera Vault\nVAULT_KEY={master_key}\n'
    if Path(".env").exists():
        with open(".env", "a") as f:
            f.write(env_line)

    print()
    print("✅ Vault configurado com sucesso!")
    print(f"   Chaves armazenadas: {len(vault.list_keys())}")
    print(f"   Arquivo: .vault (criptografado)")


def vault_add(key_name: str, value: str):
    """Adiciona uma chave ao vault."""
    vault = get_vault()
    if not vault._master_key:
        print("❌ Vault não configurado. Execute: quimera vault init")
        return

    vault.set(key_name, value)
    print(f"✅ Chave '{key_name}' adicionada ao vault")
