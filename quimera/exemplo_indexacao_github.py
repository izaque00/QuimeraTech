#!/usr/bin/env python3
"""
Exemplo Prático: Indexação Automática de Repositórios GitHub com Quimera
Demo de como usar o comando --indexar com URLs do GitHub

Autor: Sistema Quimera
Data: 2025
"""

import os
import subprocess
import sys
from pathlib import Path

def executar_comando(cmd, descricao):
    """Executa um comando e mostra o resultado"""
    print(f"\n🚀 {descricao}")
    print(f"💻 Comando: {cmd}")
    print("="*80)

    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)

        if result.stdout:
            print("📤 Saída:")
            print(result.stdout)

        if result.stderr:
            print("⚠️  Avisos/Erros:")
            print(result.stderr)

        if result.returncode == 0:
            print("✅ Comando executado com sucesso!")
        else:
            print(f"❌ Comando falhou com código: {result.returncode}")

        return result.returncode == 0

    except subprocess.TimeoutExpired:
        print("⏰ Comando demorou mais que 5 minutos - timeout")
        return False
    except Exception as e:
        print(f"💥 Erro inesperado: {e}")
        return False

def main():
    """Função principal com exemplos de indexação"""

    print("🎯 DEMO: INDEXAÇÃO AUTOMÁTICA DE REPOSITÓRIOS GITHUB")
    print("="*80)
    print("Este script demonstra como usar o Quimera para indexar")
    print("repositórios GitHub automaticamente.")
    print()

    # Verificar se estamos no diretório correto
    quimera_dir = Path.cwd()
    main_script = quimera_dir / "quimera" / "main_aprimorado.py"

    if not main_script.exists():
        print("❌ Erro: main_aprimorado.py não encontrado!")
        print(f"   Esperado em: {main_script}")
        print("   Execute este script do diretório raiz do Quimera.")
        sys.exit(1)

    print(f"📁 Diretório do Quimera: {quimera_dir}")
    print(f"✅ Script principal encontrado: {main_script}")
    print()

    # Lista de repositórios para demonstração
    repos_exemplo = [
        {
            "url": "https://github.com/torvalds/linux",
            "descricao": "Kernel Linux Principal (Linus Torvalds)",
            "tamanho": "~500MB",
            "tempo_estimado": "10-15 min"
        },
        {
            "url": "https://github.com/eun0115/android_kernel_samsung_sm7150",
            "descricao": "Kernel Android Samsung SM7150 (seu exemplo)",
            "tamanho": "~200MB",
            "tempo_estimado": "5-10 min"
        },
        {
            "url": "https://github.com/python/cpython",
            "descricao": "Interpretador Python (CPython)",
            "tamanho": "~150MB",
            "tempo_estimado": "5-8 min"
        },
        {
            "url": "https://github.com/microsoft/vscode",
            "descricao": "Visual Studio Code",
            "tamanho": "~300MB",
            "tempo_estimado": "8-12 min"
        }
    ]

    print("📋 REPOSITÓRIOS DISPONÍVEIS PARA INDEXAÇÃO:")
    print()

    for i, repo in enumerate(repos_exemplo, 1):
        print(f"{i}. {repo['descricao']}")
        print(f"   🌐 URL: {repo['url']}")
        print(f"   💾 Tamanho: {repo['tamanho']}")
        print(f"   ⏱️  Tempo estimado: {repo['tempo_estimado']}")
        print()

    # Menu interativo
    print("Escolha uma opção:")
    print("1-4: Indexar repositório específico")
    print("5: Testar comando --help")
    print("6: Exemplo com repositório pequeno (demo)")
    print("0: Sair")

    try:
        escolha = input("\n🎯 Digite sua escolha (0-6): ").strip()

        if escolha == "0":
            print("👋 Saindo...")
            return

        elif escolha == "5":
            # Testar comando --help
            cmd = "PYTHONPATH=. python3 quimera/main_aprimorado.py --help"
            executar_comando(cmd, "Mostrando ajuda do comando --indexar")

        elif escolha == "6":
            # Exemplo com repositório pequeno para demo
            print("\n🎮 DEMO RÁPIDA: Repositório pequeno para teste")
            print("Vamos usar um repositório pequeno para demonstração...")

            demo_url = "https://github.com/octocat/Hello-World"
            cmd = f"PYTHONPATH=. python3 quimera/main_aprimorado.py --indexar {demo_url}"

            confirmar = input(f"Indexar {demo_url}? (s/N): ").strip().lower()
            if confirmar in ['s', 'sim', 'y', 'yes']:
                executar_comando(cmd, f"Indexando repositório demo: {demo_url}")
            else:
                print("❌ Indexação cancelada pelo usuário")
                
        elif escolha in ['1', '2', '3', '4']:
            # Indexar repositório específico
            idx = int(escolha) - 1
            repo = repos_exemplo[idx]
            
            print(f"\n🎯 REPOSITÓRIO SELECIONADO:")
            print(f"📝 Descrição: {repo['descricao']}")
            print(f"🌐 URL: {repo['url']}")
            print(f"💾 Tamanho estimado: {repo['tamanho']}")
            print(f"⏱️ Tempo estimado: {repo['tempo_estimado']}")
            print()
            print("⚠️  ATENÇÃO: Este processo irá:")
            print("   1. Clonar o repositório completo")
            print("   2. Analisar todos os arquivos")
            print("   3. Gerar embeddings de IA")
            print("   4. Criar relacionamentos no banco")
            print()
            
            confirmar = input("🤔 Tem certeza que deseja continuar? (s/N): ").strip().lower()
            
            if confirmar in ['s', 'sim', 'y', 'yes']:
                cmd = f"PYTHONPATH=. python3 quimera/main_aprimorado.py --indexar {repo['url']}"
                sucesso = executar_comando(cmd, f"Indexando: {repo['descricao']}")
                
                if sucesso:
                    print("\n🎉 INDEXAÇÃO COMPLETA!")
                    print("📚 O repositório está agora disponível no Bibliotecário Cognitivo")
                    print("🔍 Você pode fazer consultas sobre o código indexado")
                else:
                    print("\n💥 INDEXAÇÃO FALHOU!")
                    print("🔧 Verifique os logs para mais detalhes")
            else:
                print("❌ Indexação cancelada pelo usuário")
                
        else:
            print("❌ Opção inválida!")
            
    except KeyboardInterrupt:
        print("\n⚠️ Operação cancelada pelo usuário")
    except Exception as e:
        print(f"\n💥 Erro: {e}")
        print("🔧 Verifique a configuração e tente novamente")