#!/usr/bin/env python3
"""
Script de Inicialização do AEGIS
"""

import asyncio
import sys
from pathlib import Path

# Adicionar path do projeto
sys.path.insert(0, str(Path(__file__).parent))

from quimera.aegis.demo_integration import QuimeraAegisDemo

async def main():
    """Inicia sistema AEGIS"""
    print("🛡️  Iniciando AEGIS Security System...")
    
    demo = QuimeraAegisDemo()
    success = await demo.initialize_system()
    
    if success:
        print("✅ AEGIS iniciado com sucesso!")
        return True
    else:
        print("❌ Falha ao iniciar AEGIS")
        return False

if __name__ == "__main__":
    asyncio.run(main())