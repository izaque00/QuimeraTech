#!/usr/bin/env python3
"""
Script de configuração do Agente Fiscal de Código
Instala dependências e configura o ambiente para formatação automática
"""

import subprocess
import sys
import os
from pathlib import Path

def executar_comando(comando, descricao):
    """Executa comando e trata erros"""
    print(f"📦 {descricao}...")
    try:
        resultado = subprocess.run(comando, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {descricao} - Sucesso")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {descricao} - Erro: {e.stderr}")
        return False

def verificar_python():
    """Verifica versão do Python"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8+ é necessário")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    return True

def instalar_dependencias():
    """Instala dependências necessárias"""
    dependencias = [
        "black>=23.0.0",
        "autopep8>=2.0.0",
        "isort>=5.10.0",
        "flake8>=6.0.0",
        "pylint>=2.15.0",
        "pre-commit>=3.0.0"
    ]

    print("🚀 Instalando dependências do Agente Fiscal de Código...")

    for dep in dependencias:
        if not executar_comando(f"pip install {dep}", f"Instalando {dep.split('>=')[0]}"):
            return False

    return True

def configurar_editor_vscode():
    """Configura VS Code com formatação automática"""
    vscode_dir = Path.home() / ".vscode"
    if not vscode_dir.exists():
        print("ℹ️  VS Code não detectado, pulando configuração")
        return True

    settings = {
        "python.formatting.provider": "black",
        "python.formatting.blackArgs": ["--line-length=100"],
        "python.linting.enabled": True,
        "python.linting.flake8Enabled": True,
        "python.linting.flake8Args": ["--max-line-length=100"],
        "editor.formatOnSave": True,
        "editor.codeActionsOnSave": {
            "source.organizeImports": True
        },
        "isort.args": ["--profile", "black"]
    }

    try:
        import json
        settings_file = vscode_dir / "settings.json"

        # Ler configurações existentes
        existing_settings = {}
        if settings_file.exists():
            with open(settings_file, 'r') as f:
                existing_settings = json.load(f)

        # Mesclar configurações
        existing_settings.update(settings)

        # Salvar
        with open(settings_file, 'w') as f:
            json.dump(existing_settings, f, indent=2)

        print("✅ VS Code configurado para formatação automática")
        return True
    except Exception as e:
        print(f"⚠️  Erro ao configurar VS Code: {e}")
        return False

def criar_arquivos_configuracao():
    """Cria arquivos de configuração padrão"""

    # pyproject.toml para black e isort
    pyproject_toml = """[tool.black]
line-length = 100
target-version = ['py38', 'py39', 'py310', 'py311']
skip-string-normalization = true
exclude = '''
/(
    \\.git
  | \\.pytest_cache
  | \\.venv
  | __pycache__
  | build
  | dist
)/
'''

[tool.isort]
profile = "black"
line_length = 100
multi_line_output = 3
include_trailing_comma = true
force_grid_wrap = 0
use_parentheses = true
ensure_newline_before_comments = true
known_first_party = ["quimera"]

[tool.pylint]
max-line-length = 100
disable = [
    "missing-docstring",
    "too-few-public-methods",
    "too-many-arguments"
]
"""

    # setup.cfg para flake8
    setup_cfg = """[flake8]
max-line-length = 100
max-complexity = 10
exclude =
    .git,
    __pycache__,
    .pytest_cache,
    .venv,
    build,
    dist
ignore =
    E203,  # whitespace before ':'
    W503,  # line break before binary operator
    E501   # line too long (handled by black)

[tool:pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
addopts = -v --tb=short
"""

    try:
        with open("pyproject.toml", "w") as f:
            f.write(pyproject_toml)
        print("✅ pyproject.toml criado")

        with open("setup.cfg", "w") as f:
            f.write(setup_cfg)
        print("✅ setup.cfg criado")

        return True
    except Exception as e:
        print(f"❌ Erro ao criar arquivos de configuração: {e}")
        return False

def configurar_pre_commit():
    """Configura pre-commit hooks"""
    if not executar_comando("pre-commit --version", "Verificando pre-commit"):
        return False

    precommit_config = """.pre-commit-config.yaml já foi criado pelo agente"""

    if not os.path.exists(".pre-commit-config.yaml"):
        config = """repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        args: [--line-length=100]

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
        args: [--profile=black]

  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        args: [--max-line-length=100, --max-complexity=10]

  - repo: local
    hooks:
      - id: quimera-fiscal
        name: Quimera Code Inspector
        entry: python -m quimera.agentes.agente_fiscal_codigo --check-only
        language: system
        files: \\.py$
        pass_filenames: false
        args: [.]
"""

        try:
            with open(".pre-commit-config.yaml", "w") as f:
                f.write(config)
            print("✅ .pre-commit-config.yaml criado")
        except Exception as e:
            print(f"❌ Erro ao criar .pre-commit-config.yaml: {e}")
            return False

    # Instalar hooks
    return executar_comando("pre-commit install", "Instalando pre-commit hooks")

def criar_scripts_uteis():
    """Cria scripts úteis para desenvolvimento"""

    # Script para verificar código
    check_script = """#!/bin/bash
# Script para verificar qualidade do código

echo "🔍 Verificando qualidade do código Quimera..."

echo "📝 Verificando sintaxe..."
find . -name "*.py" -exec python -m py_compile {} \\;

echo "🎨 Verificando formatação com black..."
black --check --diff .

echo "📚 Verificando imports com isort..."
isort --check-only --diff .

echo "📊 Verificando PEP8 com flake8..."
flake8 .

echo "🤖 Executando Agente Fiscal de Código..."
python -m quimera.agentes.agente_fiscal_codigo --check-only .

echo "✅ Verificação completa!"
"""

    # Script para formatar código
    format_script = """#!/bin/bash
# Script para formatar código automaticamente

echo "🎨 Formatando código Quimera..."

echo "📚 Organizando imports..."
isort .

echo "🖤 Formatando com black..."
black .

echo "🤖 Executando Agente Fiscal de Código..."
python -m quimera.agentes.agente_fiscal_codigo .

echo "✅ Formatação completa!"
"""

    try:
        with open("scripts/check_code.sh", "w") as f:
            f.write(check_script)
        os.chmod("scripts/check_code.sh", 0o755)

        with open("scripts/format_code.sh", "w") as f:
            f.write(format_script)
        os.chmod("scripts/format_code.sh", 0o755)

        print("✅ Scripts criados em scripts/")
        return True
    except Exception as e:
        print(f"❌ Erro ao criar scripts: {e}")
        return False

def main():
    """Função principal de configuração"""
    print("🚀 Configurando Agente Fiscal de Código do Quimera")
    print("=" * 50)

    # Verificar Python
    if not verificar_python():
        sys.exit(1)

    # Criar diretório scripts se não existir
    os.makedirs("scripts", exist_ok=True)

    # Executar configurações
    etapas = [
        (instalar_dependencias, "Instalação de dependências"),
        (criar_arquivos_configuracao, "Criação de arquivos de configuração"),
        (configurar_editor_vscode, "Configuração do VS Code"),
        (configurar_pre_commit, "Configuração do pre-commit"),
        (criar_scripts_uteis, "Criação de scripts úteis")
    ]

    sucesso = 0
    for funcao, descricao in etapas:
        print(f"\n🔧 {descricao}...")
        if funcao():
            sucesso += 1
        else:
            print(f"⚠️  Falha em: {descricao}")

    print("\n" + "=" * 50)
    print(f"📊 Configuração completa: {sucesso}/{len(etapas)} etapas realizadas")

    if sucesso == len(etapas):
        print("\n🎉 Agente Fiscal de Código configurado com sucesso!")
        print("\n📖 Como usar:")
        print("  • Verificar código: python -m quimera.agentes.agente_fiscal_codigo --check-only .")
        print("  • Formatar código: python -m quimera.agentes.agente_fiscal_codigo .")
        print("  • Script rápido: ./scripts/check_code.sh")
        print("  • Formatação rápida: ./scripts/format_code.sh")
        print("\n🚀 Pre-commit hooks instalados - formatação automática em cada commit!")
    else:
        print("\n⚠️  Algumas configurações falharam. Verifique os erros acima.")
        sys.exit(1)

if __name__ == "__main__":
    main()