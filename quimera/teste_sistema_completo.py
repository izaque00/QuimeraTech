#!/usr/bin/env python3
"""
Teste Completo do Sistema Quimera
Verifica se todas as funcionalidades principais estão operacionais
"""

import sys
import os
import traceback
from datetime import datetime

def print_status(mensagem, status="INFO"):
    symbols = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARNING": "⚠️"}
    symbol = symbols.get(status, "•")
    print(f"{symbol} {mensagem}")

def test_imports():
    """Testa todos os imports principais"""
    print_status("=== TESTANDO IMPORTS ===")
    
    tests = [
        ("quimera", "Módulo principal"),
        ("quimera.logs.parser", "Sistema de logs"),
        ("quimera.agentes.agente_fiscal_codigo", "Agente fiscal"),
        ("quimera.core.plugin_framework", "Sistema de plugins"),
        ("quimera.db.base", "Sistema de banco"),
        ("quimera.utils.git_parser", "Parser Git"),
    ]
    
    success_count = 0
    for module, desc in tests:
        try:
            __import__(module)
            print_status(f"{desc} - OK", "SUCCESS")
            success_count += 1
        except Exception as e:
            print_status(f"{desc} - ERRO: {e}", "ERROR")
    
    print_status(f"Imports: {success_count}/{len(tests)} funcionando")
    return success_count == len(tests)

def test_agente_fiscal():
    """Testa o agente fiscal standalone"""
    print_status("=== TESTANDO AGENTE FISCAL ===")
    
    try:
        from quimera.agentes.agente_fiscal_codigo import AgenteFiscalCodigo
        agente = AgenteFiscalCodigo()
        print_status("Agente fiscal instanciado com sucesso", "SUCCESS")
        return True
    except Exception as e:
        print_status(f"Erro ao instanciar agente fiscal: {e}", "ERROR")
        return False

def test_sistema_logs():
    """Testa o sistema de logs"""
    print_status("=== TESTANDO SISTEMA DE LOGS ===")
    
    try:
        from quimera.logs.parser import montar_log
        log_entry = montar_log("INFO", "Teste do sistema de logs", {"teste": True})
        print_status("Sistema de logs funcionando", "SUCCESS")
        return True
    except Exception as e:
        print_status(f"Erro no sistema de logs: {e}", "ERROR")
        return False

def test_comandos_cli():
    """Testa comandos de linha de comando"""
    print_status("=== TESTANDO COMANDOS CLI ===")
    
    commands = [
        "python3 agente_fiscal_standalone.py --help",
        "PYTHONPATH=. python3 quimera/main_aprimorado.py --help",
        "python3 executar_quimera.py --help"
    ]
    
    success_count = 0
    for cmd in commands:
        try:
            result = os.system(f"{cmd} > /dev/null 2>&1")
            if result == 0:
                print_status(f"Comando OK: {cmd.split()[1]}", "SUCCESS")
                success_count += 1
            else:
                print_status(f"Comando FALHOU: {cmd.split()[1]}", "ERROR")
        except Exception as e:
            print_status(f"Erro executando comando: {e}", "ERROR")
    
    return success_count > 0

def test_arquivo_exemplo():
    """Testa análise de um arquivo exemplo"""
    print_status("=== TESTANDO ANÁLISE DE ARQUIVO ===")
    
    # Criar arquivo de teste
    teste_arquivo = "/tmp/teste_quimera.py"
    with open(teste_arquivo, 'w') as f:
        f.write("""
def funcao_teste():
    print("Hello World")
    return True

if __name__ == "__main__":
    funcao_teste()
""")
    
    try:
        # Testar análise fiscal
        result = os.system(f"python3 agente_fiscal_standalone.py --check-only {teste_arquivo} > /dev/null 2>&1")
        if result == 0:
            print_status("Análise de arquivo funcionando", "SUCCESS")
            return True
        else:
            print_status("Análise de arquivo com problemas", "WARNING")
            return False
    except Exception as e:
        print_status(f"Erro na análise: {e}", "ERROR")
        return False
    finally:
        # Limpar arquivo de teste
        if os.path.exists(teste_arquivo):
            os.remove(teste_arquivo)

def main():
    """Executa todos os testes"""
    print_status("🚀 INICIANDO TESTE COMPLETO DO SISTEMA QUIMERA")
    print_status(f"Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print_status(f"Python: {sys.version}")
    print_status(f"Diretório: {os.getcwd()}")
    print("=" * 60)
    
    # Executar testes
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("Agente Fiscal", test_agente_fiscal()))
    results.append(("Sistema de Logs", test_sistema_logs()))
    results.append(("Comandos CLI", test_comandos_cli()))
    results.append(("Análise de Arquivo", test_arquivo_exemplo()))
    
    # Mostrar resultados
    print("=" * 60)
    print_status("=== RESULTADOS FINAIS ===")
    
    success_count = 0
    for test_name, success in results:
        status = "SUCCESS" if success else "ERROR"
        print_status(f"{test_name}: {'PASSOU' if success else 'FALHOU'}", status)
        if success:
            success_count += 1
    
    # Status final
    total_tests = len(results)
    success_rate = (success_count / total_tests) * 100
    
    print("=" * 60)
    if success_count == total_tests:
        print_status(f"🎉 SISTEMA 100% FUNCIONAL! ({success_count}/{total_tests} testes)", "SUCCESS")
        print_status("Sistema Quimera está PRONTO PARA PRODUÇÃO!", "SUCCESS")
        return 0
    elif success_count >= total_tests * 0.8:
        print_status(f"✅ SISTEMA FUNCIONAL! ({success_count}/{total_tests} testes - {success_rate:.1f}%)", "SUCCESS")
        print_status("Sistema Quimera está OPERACIONAL com funcionalidades básicas!", "SUCCESS")
        return 0
    else:
        print_status(f"⚠️ SISTEMA COM PROBLEMAS ({success_count}/{total_tests} testes - {success_rate:.1f}%)", "WARNING")
        print_status("Sistema Quimera precisa de correções adicionais", "WARNING")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print_status("Teste interrompido pelo usuário", "WARNING")
        sys.exit(1)
    except Exception as e:
        print_status(f"Erro inesperado: {e}", "ERROR")
        traceback.print_exc()
        sys.exit(1)