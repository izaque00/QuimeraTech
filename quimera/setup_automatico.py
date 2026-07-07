#!/usr/bin/env python3
"""
Setup Automático do Projeto Quimera
Instalador inteligente com dependências testadas e funcionais
"""

import subprocess
import sys
import os
from pathlib import Path
import shutil

def print_status(message, status="INFO"):
    """Imprime mensagem com status colorido"""
    colors = {
        "INFO": "\033[34m",  # Azul
        "SUCCESS": "\033[32m",  # Verde
        "WARNING": "\033[33m",  # Amarelo
        "ERROR": "\033[31m",  # Vermelho
        "RESET": "\033[0m"  # Reset
    }
    
    color = colors.get(status, colors["INFO"])
    reset = colors["RESET"]
    
    icons = {
        "INFO": "ℹ️",
        "SUCCESS": "✅",
        "WARNING": "⚠️",
        "ERROR": "❌"
    }
    
    icon = icons.get(status, "•")
    print(f"{color}{icon} {message}{reset}")

def run_command(command, description, check=True):
    """Executa comando com tratamento de erro"""
    print_status(f"Executando: {description}")
    
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            check=check, 
            capture_output=True, 
            text=True
        )
        
        if result.returncode == 0:
            print_status(f"{description} - Concluído", "SUCCESS")
            return True
        else:
            print_status(f"{description} - Falhou: {result.stderr}", "ERROR")
            return False
            
    except subprocess.CalledProcessError as e:
        print_status(f"{description} - Erro: {e}", "ERROR")
        return False

def check_python_version():
    """Verifica versão do Python"""
    version = sys.version_info
    print_status(f"Python {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print_status("Python 3.8+ é necessário", "ERROR")
        return False
    
    print_status("Versão do Python compatível", "SUCCESS")
    return True

def install_dependencies():
    """Instala dependências funcionais testadas"""
    print_status("=== INSTALAÇÃO DE DEPENDÊNCIAS ===")
    
    # Instalar dependências básicas funcionais
    if not run_command(
        f"{sys.executable} -m pip install -r requirements_funcional.txt",
        "Instalando dependências básicas funcionais"
    ):
        return False
    
    # Instalar dependências ML básicas (testadas)
    print_status("Instalando dependências ML básicas...")
    basic_ml = ["numpy", "scikit-learn", "tree-sitter"]
    
    for dep in basic_ml:
        if not run_command(
            f"{sys.executable} -m pip install {dep}",
            f"Instalando {dep}",
            check=False  # Não parar se uma falhar
        ):
            print_status(f"Falha ao instalar {dep} - continuando...", "WARNING")
    
    return True

def verify_installation():
    """Verifica se a instalação foi bem-sucedida"""
    print_status("=== VERIFICAÇÃO DA INSTALAÇÃO ===")
    
    # Testar imports principais
    test_modules = [
        "yaml",
        "click", 
        "tqdm",
        "black",
        "isort",
        "flake8",
        "psutil",
        "watchdog",
        "loguru",
        "pytest"
    ]
    
    success_count = 0
    
    for module in test_modules:
        try:
            __import__(module)
            print_status(f"{module}: OK", "SUCCESS")
            success_count += 1
        except ImportError:
            print_status(f"{module}: FALHOU", "ERROR")
    
    print_status(f"Módulos testados: {success_count}/{len(test_modules)}")
    
    if success_count >= len(test_modules) * 0.8:  # 80% de sucesso
        print_status("Instalação verificada com sucesso", "SUCCESS")
        return True
    else:
        print_status("Verificação falhou - muitos módulos ausentes", "ERROR")
        return False

def test_quimera_system():
    """Testa o sistema Quimera"""
    print_status("=== TESTE DO SISTEMA QUIMERA ===")
    
    if not Path("main.py").exists():
        print_status("main.py não encontrado - execute no diretório do projeto", "ERROR")
        return False
    
    # Testar comando de status
    if run_command(
        f"{sys.executable} main.py status",
        "Testando comando status do Quimera",
        check=False
    ):
        print_status("Sistema Quimera funcionando!", "SUCCESS")
        return True
    else:
        print_status("Sistema Quimera com problemas", "WARNING")
        return False

def setup_poetry_config():
    """Configura Poetry com pyproject.toml corrigido"""
    print_status("=== CONFIGURAÇÃO POETRY (OPCIONAL) ===")
    
    if shutil.which("poetry"):
        print_status("Poetry encontrado - configurando...")
        
        # Backup do pyproject.toml original
        if Path("pyproject.toml").exists():
            run_command(
                "cp pyproject.toml pyproject_backup.toml",
                "Backup do pyproject.toml original",
                check=False
            )
        
        # Usar versão corrigida
        if Path("pyproject_final.toml").exists():
            run_command(
                "cp pyproject_final.toml pyproject.toml",
                "Aplicando pyproject.toml corrigido",
                check=False
            )
            
            # Verificar configuração
            if run_command(
                "poetry check",
                "Verificando configuração Poetry",
                check=False
            ):
                print_status("Poetry configurado com sucesso", "SUCCESS")
            else:
                print_status("Poetry com avisos (normal)", "WARNING")
        else:
            print_status("pyproject_final.toml não encontrado", "WARNING")
    else:
        print_status("Poetry não instalado - pulando configuração", "INFO")

def main():
    """Função principal do setup"""
    print_status("🚀 SETUP AUTOMÁTICO DO PROJETO QUIMERA")
    print_status("=" * 50)
    
    # Verificar se estamos no diretório correto
    if not Path("quimera").exists() and not Path("main.py").exists():
        print_status("Execute este script no diretório raiz do projeto Quimera", "ERROR")
        sys.exit(1)
    
    # Verificar versão Python
    if not check_python_version():
        sys.exit(1)
    
    # Instalar dependências
    if not install_dependencies():
        print_status("Falha na instalação de dependências", "ERROR")
        sys.exit(1)
    
    # Verificar instalação
    if not verify_installation():
        print_status("Verificação falhou - algumas funcionalidades podem não funcionar", "WARNING")
    
    # Configurar Poetry (opcional)
    setup_poetry_config()
    
    # Testar sistema
    test_quimera_system()
    
    print_status("=" * 50)
    print_status("🎉 SETUP CONCLUÍDO!")
    print_status("=" * 50)
    
    print()
    print_status("PRÓXIMOS PASSOS:")
    print_status("1. Testar: python main.py status")
    print_status("2. Diagnóstico: python main.py diagnostico")
    print_status("3. Ajuda: python main.py --help")
    print()
    print_status("Para dependências adicionais:")
    print_status("• ML/AI: pip install sentence-transformers faiss-cpu")
    print_status("• Interface: pip install gradio streamlit")
    print_status("• Cache: pip install redis")
    print()

if __name__ == "__main__":
    main()