#!/usr/bin/env python3
"""
Script de Setup Corrigido para o Projeto Quimera
"""

import subprocess
import sys
import os
from pathlib import Path

def instalar_dependencias():
    """Instala dependências corrigidas"""
    print("🔧 Instalando dependências corrigidas...")

    try:
        # Usar o requirements corrigido
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", "requirements_corrigido.txt"
        ])
        print("✅ Dependências instaladas com sucesso!")
    except subprocess.CalledProcessError:
        print("❌ Erro ao instalar dependências")
        return False

    return True

def verificar_instalacao():
    """Verifica se a instalação foi bem-sucedida"""
    print("🔍 Verificando instalação...")

    modulos_testar = [
        'tree_sitter',
        'black',
        'isort',
        'flake8',
        'aiohttp',
        'pyyaml'
    ]

    for modulo in modulos_testar:
        try:
            __import__(modulo)
            print(f"✅ {modulo}: OK")
        except ImportError:
            print(f"❌ {modulo}: ERRO")
            return False

    return True

def main():
    """Função principal"""
    print("🚀 Setup do Projeto Quimera - Versão Corrigida")
    print("=" * 50)

    # Verificar se estamos no diretório correto
    if not Path("quimera").exists():
        print("❌ Execute este script no diretório raiz do projeto Quimera")
        sys.exit(1)

    # Instalar dependências
    if not instalar_dependencias():
        sys.exit(1)

    # Verificar instalação
    if not verificar_instalacao():
        print("⚠️ Algumas dependências podem não ter sido instaladas corretamente")
        print("💡 Tente executar: pip install -r requirements_corrigido.txt")
        sys.exit(1)

    print("🎉 Setup concluído com sucesso!")
    print("💡 Agora você pode executar: python quimera/main_aprimorado.py")

if __name__ == "__main__":
    main()