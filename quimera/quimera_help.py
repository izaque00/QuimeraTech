#!/usr/bin/env python3
"""
🤖 SISTEMA DE HELP INTERATIVO DO QUIMERA v3.0.0
Guia completo com todos os comandos, exemplos e funcionalidades
"""

import sys
import os
from pathlib import Path

class QuimeraHelp:
    def __init__(self):
        self.version = "3.0.0"
        self.comandos = {
            "principais": {
                "unified-mission": {
                    "desc": "Executa uma missão unificada coordenando todos os orquestradores",
                    "uso": "python3 main_unificado.py unified-mission --target [alvo] --objective [objetivo]",
                    "exemplo": "python3 main_unificado.py unified-mission --target ./meu_projeto --objective 'analisar e corrigir código'"
                },
                "setup": {
                    "desc": "Configura e inicializa todos os ambientes virtuais e dependências",
                    "uso": "python3 main_unificado.py setup",
                    "exemplo": "python3 main_unificado.py setup"
                },
                "list-orchestrators": {
                    "desc": "Lista todos os orquestradores internos disponíveis e suas capacidades",
                    "uso": "python3 main_unificado.py list-orchestrators",
                    "exemplo": "python3 main_unificado.py list-orchestrators"
                }
            },
            "analise": {
                "diagnostico-integrated": {
                    "desc": "Executa diagnóstico sistêmico completo do Quimera",
                    "uso": "python3 main_unificado.py diagnostico-integrated [--deep] [--output arquivo]",
                    "exemplo": "python3 main_unificado.py diagnostico-integrated --deep --output diagnostico.json"
                },
                "analise-codigo-integrated": {
                    "desc": "Análise completa de código Python",
                    "uso": "python3 main_unificado.py analise-codigo-integrated --path [caminho] [--format json]",
                    "exemplo": "python3 main_unificado.py analise-codigo-integrated --path ./src --format json"
                },
                "status-integrated": {
                    "desc": "Exibe status completo do sistema",
                    "uso": "python3 main_unificado.py status-integrated [--verbose]",
                    "exemplo": "python3 main_unificado.py status-integrated --verbose"
                }
            },
            "correcao": {
                "corrigir-integrated": {
                    "desc": "Corrige arquivos Python automaticamente",
                    "uso": "python3 main_unificado.py corrigir-integrated --arquivo [arquivo] [--backup]",
                    "exemplo": "python3 main_unificado.py corrigir-integrated --arquivo meu_script.py --backup"
                },
                "missao-unica-aprimorado": {
                    "desc": "Executa uma única missão de diagnóstico e reparo",
                    "uso": "python3 main_unificado.py missao-unica-aprimorado --target [alvo] [--repair-mode auto]",
                    "exemplo": "python3 main_unificado.py missao-unica-aprimorado --target ./projeto --repair-mode auto"
                }
            },
            "ia": {
                "gerar-texto-integrated": {
                    "desc": "Gera texto usando LLM",
                    "uso": "python3 main_unificado.py gerar-texto-integrated --prompt '[prompt]' [--model gpt-4]",
                    "exemplo": "python3 main_unificado.py gerar-texto-integrated --prompt 'Explique machine learning' --model gpt-4"
                },
                "buscar-docs-integrated": {
                    "desc": "Busca semântica em documentos",
                    "uso": "python3 main_unificado.py buscar-docs-integrated --query '[consulta]' [--limit 10]",
                    "exemplo": "python3 main_unificado.py buscar-docs-integrated --query 'como usar pandas' --limit 5"
                }
            },
            "fiscal": {
                "agente-fiscal": {
                    "desc": "Fiscalização completa de código Python",
                    "uso": "python3 agente_fiscal_standalone.py [diretório] [opções]",
                    "exemplo": "python3 agente_fiscal_standalone.py ./src --output relatorio.json --check-only"
                }
            }
        }
        
        self.fluxos = {
            "primeiro_uso": [
                "python3 main_unificado.py setup",
                "python3 main_unificado.py status-integrated",
                "python3 main_unificado.py list-orchestrators"
            ],
            "analise_projeto": [
                "python3 main_unificado.py diagnostico-completo-aprimorado --components all",
                "python3 main_unificado.py analise-codigo-integrated --path ./src --format json",
                "python3 agente_fiscal_standalone.py ./src --output relatorio.json"
            ],
            "correcao": [
                "python3 main_unificado.py corrigir-integrated --arquivo problema.py --backup",
                "python3 main_unificado.py unified-mission --target ./projeto --objective 'otimizar código'"
            ]
        }

    def exibir_banner(self):
        print(f"""
🤖 ═══════════════════════════════════════════════════════════════
   SISTEMA QUIMERA v{self.version} - HELP INTERATIVO
   Sistema Ultra-Avançado de Análise e Correção de Código
═══════════════════════════════════════════════════════════════
""")

    def exibir_menu_principal(self):
        print("""
📋 MENU PRINCIPAL:
═════════════════

1. 🚀 Comandos Principais
2. 🔍 Análise e Diagnóstico  
3. 🛠️  Correção e Reparo
4. 🤖 IA e LLM
5. 👮 Agente Fiscal
6. 📚 Fluxos de Trabalho
7. ⚡ Início Rápido
8. 🆘 Ajuda Específica
9. 🚪 Sair

""")

    def exibir_categoria(self, categoria):
        if categoria not in self.comandos:
            print(f"❌ Categoria '{categoria}' não encontrada!")
            return
            
        print(f"\n🔧 COMANDOS - {categoria.upper()}")
        print("═" * 50)
        
        for cmd, info in self.comandos[categoria].items():
            print(f"\n📌 {cmd}")
            print(f"   📝 {info['desc']}")
            print(f"   💻 {info['uso']}")
            print(f"   🌟 Exemplo: {info['exemplo']}")

    def exibir_fluxos(self):
        print(f"\n📚 FLUXOS DE TRABALHO RECOMENDADOS")
        print("═" * 50)
        
        for nome, comandos in self.fluxos.items():
            print(f"\n🎯 {nome.replace('_', ' ').title()}:")
            for i, cmd in enumerate(comandos, 1):
                print(f"   {i}. {cmd}")

    def exibir_inicio_rapido(self):
        print(f"""
⚡ INÍCIO RÁPIDO
═══════════════

🔧 1. CONFIGURAÇÃO INICIAL:
   python3 main_unificado.py setup

🔍 2. VERIFICAR STATUS:
   python3 main_unificado.py status-integrated

📊 3. ANALISAR PROJETO:
   python3 main_unificado.py analise-codigo-integrated --path ./seu_projeto

👮 4. FISCALIZAR CÓDIGO:
   python3 agente_fiscal_standalone.py ./seu_projeto

🛠️  5. CORRIGIR PROBLEMAS:
   python3 main_unificado.py corrigir-integrated --arquivo arquivo.py

🚀 6. MISSÃO COMPLETA:
   python3 main_unificado.py unified-mission --target ./projeto --objective "analisar e otimizar"

""")

    def buscar_comando(self, termo):
        print(f"\n🔍 BUSCANDO: '{termo}'")
        print("═" * 30)
        
        encontrados = []
        for categoria, comandos in self.comandos.items():
            for cmd, info in comandos.items():
                if termo.lower() in cmd.lower() or termo.lower() in info['desc'].lower():
                    encontrados.append((categoria, cmd, info))
        
        if encontrados:
            for categoria, cmd, info in encontrados:
                print(f"\n📌 {cmd} ({categoria})")
                print(f"   📝 {info['desc']}")
                print(f"   🌟 {info['exemplo']}")
        else:
            print(f"❌ Nenhum comando encontrado para '{termo}'")

    def executar(self):
        self.exibir_banner()
        
        while True:
            self.exibir_menu_principal()
            
            try:
                escolha = input("👉 Escolha uma opção (1-9): ").strip()
                
                if escolha == '1':
                    self.exibir_categoria('principais')
                elif escolha == '2':
                    self.exibir_categoria('analise')
                elif escolha == '3':
                    self.exibir_categoria('correcao')
                elif escolha == '4':
                    self.exibir_categoria('ia')
                elif escolha == '5':
                    self.exibir_categoria('fiscal')
                elif escolha == '6':
                    self.exibir_fluxos()
                elif escolha == '7':
                    self.exibir_inicio_rapido()
                elif escolha == '8':
                    termo = input("🔍 Digite o termo para buscar: ").strip()
                    if termo:
                        self.buscar_comando(termo)
                elif escolha == '9':
                    print("\n👋 Obrigado por usar o Quimera! Até logo!")
                    break
                else:
                    print("❌ Opção inválida! Escolha entre 1-9.")
                
                input("\n⏸️  Pressione ENTER para continuar...")
                
            except KeyboardInterrupt:
                print("\n\n👋 Saindo... Até logo!")
                break
            except Exception as e:
                print(f"❌ Erro: {e}")

if __name__ == "__main__":
    help_system = QuimeraHelp()
    
    # Se passou argumentos, busca diretamente
    if len(sys.argv) > 1:
        termo = " ".join(sys.argv[1:])
        help_system.exibir_banner()
        help_system.buscar_comando(termo)
    else:
        # Executa modo interativo
        help_system.executar()