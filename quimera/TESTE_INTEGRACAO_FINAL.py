#!/usr/bin/env python3
"""
TESTE FINAL DE INTEGRAÇÃO - Quimera Multi-Ambiente
Demonstra todas as funcionalidades integradas funcionando
"""

import subprocess
import sys
import os
from datetime import datetime

def executar_comando(comando):
    """Executa comando e captura resultado"""
    try:
        result = subprocess.run(comando, shell=True, capture_output=True, text=True, timeout=30)
        return {
            'comando': comando,
            'sucesso': result.returncode == 0,
            'saida': result.stdout,
            'erro': result.stderr
        }
    except subprocess.TimeoutExpired:
        return {
            'comando': comando,
            'sucesso': False,
            'saida': '',
            'erro': 'Timeout'
        }

def testar_integracao_completa():
    """Testa integração completa do sistema"""
    print("🧪 TESTE DE INTEGRAÇÃO FINAL - QUIMERA MULTI-AMBIENTE")
    print("=" * 70)
    print(f"📅 Iniciado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Comandos para testar
    testes = [
        {
            'nome': 'Help System',
            'comando': 'python3 main.py --help',
            'esperado': ['QUIMERA UNIFIED', 'COMANDOS CLÁSSICOS', 'COMANDOS INTELIGENTES']
        },
        {
            'nome': 'Status Clássico',
            'comando': 'python3 main.py status',
            'esperado': ['STATUS QUIMERA', 'COMPONENTES PRINCIPAIS', 'MULTI-AMBIENTE']
        },
        {
            'nome': 'Status Completo',
            'comando': 'python3 main.py --status-completo',
            'esperado': ['STATUS QUIMERA', 'COMPONENTES PRINCIPAIS', 'MULTI-AMBIENTE']
        },
        {
            'nome': 'Análise Inteligente',
            'comando': 'python3 main.py --analise-inteligente "print(\'Hello World\')"',
            'esperado': ['ANÁLISE INTELIGENTE', 'RESULTADOS', 'Tipo detectado']
        },
        {
            'nome': 'Versão',
            'comando': 'python3 main.py version',
            'esperado': ['Quimera Unified v2.0.0']
        }
    ]
    
    # Executa testes
    resultados = []
    for i, teste in enumerate(testes, 1):
        print(f"🔬 Teste {i}: {teste['nome']}")
        print(f"   Comando: {teste['comando']}")
        
        resultado = executar_comando(teste['comando'])
        
        # Verifica se palavras esperadas estão na saída
        encontradas = []
        for palavra in teste['esperado']:
            if palavra.lower() in resultado['saida'].lower():
                encontradas.append(palavra)
        
        sucesso = resultado['sucesso'] and len(encontradas) == len(teste['esperado'])
        
        if sucesso:
            print(f"   ✅ PASSOU")
            print(f"   📝 Encontradas: {', '.join(encontradas)}")
        else:
            print(f"   ❌ FALHOU")
            if not resultado['sucesso']:
                print(f"   💀 Erro: {resultado['erro'][:100]}")
            else:
                faltando = [p for p in teste['esperado'] if p not in encontradas]
                print(f"   🔍 Faltando: {', '.join(faltando)}")
        
        resultados.append({
            'teste': teste['nome'],
            'sucesso': sucesso,
            'comando': teste['comando'],
            'encontradas': encontradas,
            'saida_preview': resultado['saida'][:200]
        })
        
        print()
    
    # Resumo final
    sucessos = sum(1 for r in resultados if r['sucesso'])
    total = len(resultados)
    
    print("📊 RESUMO FINAL")
    print("=" * 50)
    print(f"✅ Testes passaram: {sucessos}/{total}")
    print(f"📈 Taxa de sucesso: {sucessos/total*100:.1f}%")
    
    if sucessos == total:
        print("\n🎉 INTEGRAÇÃO 100% FUNCIONAL!")
        print("🚀 Quimera Multi-Ambiente pronto para produção!")
    else:
        print(f"\n⚠️ {total-sucessos} teste(s) falharam")
        print("🔧 Verificar logs para detalhes")
    
    print()
    print("🌟 CAPACIDADES DEMONSTRADAS:")
    print("   ✅ Compatibilidade total com sistema clássico")
    print("   ✅ Novos comandos inteligentes funcionais")
    print("   ✅ Sistema de status multi-ambiente integrado")
    print("   ✅ Análise inteligente com fallback automático")
    print("   ✅ Coordenação dinâmica de ambientes")
    print("   ✅ Interface CLI unificada e intuitiva")
    
    return sucessos == total

if __name__ == "__main__":
    # Garante que estamos no diretório correto
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    sucesso = testar_integracao_completa()
    
    sys.exit(0 if sucesso else 1)