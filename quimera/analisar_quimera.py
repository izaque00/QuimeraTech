#!/usr/bin/env python3
"""
Script de Análise Rápida do Quimera
Executa análise completa do projeto
"""

import asyncio
import sys
import argparse
from pathlib import Path

# Adicionar diretório atual ao path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from agente_fiscal_hibrido import analisar_projeto_hibrido, ConfiguracaoHibrida
    
    async def main():
        parser = argparse.ArgumentParser(description="Análise do Projeto Quimera")
        parser.add_argument("--ia", action="store_true", help="Usar IA para sugestões")
        parser.add_argument("--corrigir", action="store_true", help="Corrigir automaticamente")
        parser.add_argument("--verbose", action="store_true", help="Modo verboso")
        
        args = parser.parse_args()
        
        config = ConfiguracaoHibrida(
            usar_ia_para_correcoes=args.ia,
            corrigir_automaticamente=args.corrigir,
            modo_verboso=args.verbose
        )
        
        print("🔍 Iniciando análise do Quimera...")
        resultado = await analisar_projeto_hibrido(".", config)
        
        print(f"\n{'='*50}")
        print(f"RESULTADO DA ANÁLISE")
        print(f"{'='*50}")
        print(f"Agente usado: {resultado.agente_usado}")
        print(f"Sucesso: {'✅' if resultado.sucesso else '❌'}")
        print(f"Arquivos verificados: {resultado.arquivos_verificados}")
        print(f"Problemas encontrados: {len(resultado.problemas_encontrados)}")
        print(f"Problemas corrigidos: {len(resultado.problemas_corrigidos)}")
        print(f"Tempo: {resultado.tempo_execucao:.2f}s")
        
        # Mostrar problemas por severidade
        severidades = {}
        for problema in resultado.problemas_encontrados:
            sev = problema.get("severidade", "unknown")
            severidades[sev] = severidades.get(sev, 0) + 1
        
        if severidades:
            print("\nProblemas por severidade:")
            for sev, count in severidades.items():
                print(f"  {sev}: {count}")
    
    if __name__ == "__main__":
        asyncio.run(main())
        
except ImportError:
    print("❌ Agente fiscal híbrido não disponível")
    print("Execute: python integrar_agente_fiscal.py")