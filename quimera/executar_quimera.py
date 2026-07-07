#!/usr/bin/env python3
"""Launcher básico do Quimera"""
import sys
import os
from pathlib import Path

# Configurar PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))
os.environ["PYTHONPATH"] = str(Path(__file__).parent)

def main():
    try:
        print("🤖 Iniciando Sistema Quimera...")

        # Tentar importar logs
        from quimera.logs.parser import montar_log
        montar_log("Sistema iniciado", "INFO")

        # Tentar importar agente fiscal
        try:
            from quimera.agentes.agente_fiscal_codigo import AgenteFiscalCodigo
            montar_log("Agente Fiscal carregado", "SUCCESS")
        except ImportError:
            AgenteFiscalCodigo = None  # AgenteFiscalCodigo não disponível
            montar_log("Agente Fiscal não disponível", "WARNING")

        print("✅ Sistema carregado com sucesso!")
        print("💡 Para usar: if AgenteFiscalCodigo is not None:")
        print("     AgenteFiscalCodigo().fiscalizar_arquivo('arquivo.py')")

        return 0

    except Exception as e:
        print(f"❌ Erro: {e}")
        print("💡 Verifique se todas as dependências estão instaladas")
        return 1

if __name__ == "__main__":
    sys.exit(main())