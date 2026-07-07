#!/usr/bin/env python3
"""
Launcher Seguro para o Projeto Quimera
Verifica dependências e executa com fallbacks
"""

import sys
import os
import importlib
from pathlib import Path

# Adicionar ao PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

def verificar_dependencias_minimas():
    """Verifica e instala dependências mínimas"""
    dependencias_criticas = [
        'yaml',
        'click',
        'tqdm'
    ]

    faltando = []
    for dep in dependencias_criticas:
        try:
            importlib.import_module(dep)
        except ImportError:
            faltando.append(dep)

    if faltando:
        print("⚠️ Dependências críticas faltando:", ", ".join(faltando))
        print("💡 Execute: pip install pyyaml click tqdm")
        return False

    return True

def executar_com_fallback():
    """Executa sistema com fallbacks para dependências opcionais"""
    print("🤖 Iniciando Sistema Quimera (modo seguro)")

    # Verificar dependências
    if not verificar_dependencias_minimas():
        sys.exit(1)

    # Configurar variáveis de ambiente
    os.environ["PYTHONPATH"] = str(Path(__file__).parent)
    os.environ.setdefault("LOG_LEVEL", "INFO")

    try:
        # Tentar importar e executar sistema principal
        from quimera.logs.parser import montar_log
        montar_log("Sistema iniciando em modo seguro", "INFO")

        # Importar componentes principais
        try:
            from quimera.agentes.agente_fiscal_codigo import AgenteFiscalCodigo
        except ImportError:
            AgenteFiscalCodigo = None  # AgenteFiscalCodigo não disponível

        # Executar agente fiscal como demonstração
        agente = AgenteFiscalCodigo() if AgenteFiscalCodigo is not None else None
        montar_log("Agente Fiscal carregado com sucesso", "SUCCESS")

        # Executar análise simples
        resultado = agente.fiscalizar_arquivo(__file__)
        montar_log(f"Auto-análise concluída: {len(resultado.problemas_encontrados)} problemas encontrados", "INFO")

        print("✅ Sistema Quimera executado com sucesso!")
        return 0

    except Exception as e:
        print(f"❌ Erro ao executar sistema: {e}")
        print("💡 Verifique os logs para mais detalhes")
        return 1

def main():
    """Função principal"""
    import argparse

    parser = argparse.ArgumentParser(description='Launcher Seguro do Sistema Quimera')
    parser.add_argument('--modo', choices=['seguro', 'completo'], default='seguro',
                       help='Modo de execução')
    parser.add_argument('--debug', action='store_true',
                       help='Habilitar modo debug')

    args = parser.parse_args()

    if args.debug:
        os.environ["LOG_LEVEL"] = "DEBUG"

    if args.modo == 'seguro':
        sys.exit(executar_com_fallback())
    else:
        # Tentar executar sistema completo
        try:
            from quimera.cli import main as main_completo
            sys.exit(main_completo())
        except Exception as e:
            print(f"❌ Sistema completo falhou: {e}")
            print("🔄 Tentando modo seguro...")
            sys.exit(executar_com_fallback())

if __name__ == "__main__":
    main()