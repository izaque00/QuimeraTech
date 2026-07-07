"""
Quimera Vault CLI — Comandos de gerenciamento de chaves.

Uso:
    quimera vault init              # Configurar vault pela primeira vez
    quimera vault add KEY value     # Adicionar chave
    quimera vault list              # Listar chaves (sem valores)
    quimera vault remove KEY        # Remover chave
    quimera vault import .env       # Importar chaves do .env existente
"""

import os
import sys
from pathlib import Path

# Adiciona raiz do projeto ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def cmd_vault(args):
    """Gerencia o cofre de chaves criptografado."""
    from quimera.vault import get_vault, vault_init, vault_add

    if not hasattr(args, 'vault_action'):
        print("Uso: quimera vault <init|add|list|remove|import>")
        return

    action = args.vault_action

    if action == 'init':
        vault_init()

    elif action == 'add':
        if not hasattr(args, 'key_name') or not hasattr(args, 'key_value'):
            print("Uso: quimera vault add <NOME> <VALOR>")
            return
        vault_add(args.key_name, args.key_value)

    elif action == 'list':
        vault = get_vault()
        keys = vault.list_keys()
        if keys:
            print(f"🔐 {len(keys)} chaves no vault:")
            for k in sorted(keys):
                print(f"   • {k}")
        else:
            print("🔐 Nenhuma chave no vault.")
            print("   Adicione com: quimera vault add OPENAI_API_KEY sk-...")

    elif action == 'remove':
        if not hasattr(args, 'key_name'):
            print("Uso: quimera vault remove <NOME>")
            return
        vault = get_vault()
        vault.remove(args.key_name)
        print(f"✅ Chave '{args.key_name}' removida")

    elif action == 'import':
        vault = get_vault()
        if not vault._master_key:
            print("❌ Vault não configurado. Execute: quimera vault init")
            return
        env_path = getattr(args, 'file', '.env')
        count = vault.import_from_env_file(env_path)
        print(f"✅ {count} chaves importadas de {env_path}")

def main():
    import argparse
    p = argparse.ArgumentParser(prog="quimera-vault")
    sp = p.add_subparsers(dest="vault_action")

    sp.add_parser("init", help="Configurar vault")
    add_p = sp.add_parser("add", help="Adicionar chave")
    add_p.add_argument("key_name")
    add_p.add_argument("key_value", nargs="?")
    sp.add_parser("list", help="Listar chaves")
    rm_p = sp.add_parser("remove", help="Remover chave")
    rm_p.add_argument("key_name")
    imp_p = sp.add_parser("import", help="Importar do .env")
    imp_p.add_argument("file", nargs="?", default=".env")

    args = p.parse_args()
    cmd_vault(args)

if __name__ == "__main__":
    main()
