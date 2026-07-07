#!/usr/bin/env python3
"""
Gerenciador de Ambientes Virtuais Múltiplos para Quimera
Permite usar 100% das funcionalidades sem conflitos de dependência
"""
import os
import sys
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Optional

class QuimeraEnvManager:
    """
    Gerencia múltiplos ambientes virtuais para diferentes funcionalidades
    """
    
    def __init__(self, base_dir: str = "quimera-envs"):
        self.base_dir = Path(base_dir)
        self.current_env = None
        self.env_configs = self._load_env_configs()
        
    def _load_env_configs(self) -> Dict:
        """Configurações dos ambientes especializados"""
        return {
            "core": {
                "description": "Funcionalidades básicas do sistema",
                "requirements": [
                    "python-dotenv", "requests", "aiohttp", "psutil", 
                    "watchdog", "pygments", "click", "tqdm", "pyyaml",
                    "jsonschema", "packaging", "typer", "rich", "colorama",
                    "sqlalchemy", "pydantic", "GitPython"
                ]
            },
            
            "llm": {
                "description": "Large Language Models e IA",
                "requirements": [
                    "openai==1.0.0", "anthropic==0.8.0", "tiktoken==0.5.0",
                    "langchain==0.1.0", "langchain-core==0.1.0",
                    "langchain-openai==0.1.0", "cohere", "transformers",
                    "torch", "accelerate"
                ]
            },
            
            "rag": {
                "description": "Retrieval Augmented Generation",
                "requirements": [
                    "sentence-transformers", "faiss-cpu", "chromadb",
                    "llama-index", "llama-index-embeddings-huggingface",
                    "llama-index-vector-stores-chroma"
                ]
            },
            
            "ui": {
                "description": "Interfaces de usuário",
                "requirements": [
                    "streamlit", "gradio", "plotly", "matplotlib", 
                    "seaborn", "jupyter", "ipython"
                ]
            },
            
            "ml": {
                "description": "Machine Learning e análise de dados",
                "requirements": [
                    "pandas", "numpy>=2.0.0", "scikit-learn", "scipy",
                    "joblib", "pillow", "opencv-python"
                ]
            },
            
            "web": {
                "description": "Web scraping e automação",
                "requirements": [
                    "selenium", "playwright", "scrapy", "beautifulsoup4",
                    "httpx", "python-slugify"
                ]
            },
            
            "security": {
                "description": "Segurança e criptografia",
                "requirements": [
                    "cryptography", "pyjwt", "bcrypt", "bandit"
                ]
            },
            
            "analysis": {
                "description": "Análise e linting de código",
                "requirements": [
                    "pylint", "black", "isort", "flake8", "autopep8",
                    "mypy", "pre-commit"
                ]
            },
            
            "docs": {
                "description": "Processamento de documentos",
                "requirements": [
                    "PyPDF2", "python-docx", "markdown", "textstat"
                ]
            }
        }
    
    def create_env(self, env_name: str) -> bool:
        """Cria um ambiente virtual específico"""
        if env_name not in self.env_configs:
            print(f"❌ Ambiente '{env_name}' não encontrado")
            return False
            
        env_path = self.base_dir / env_name
        env_path.mkdir(parents=True, exist_ok=True)
        
        # Cria o ambiente virtual
        try:
            subprocess.run([
                sys.executable, "-m", "venv", str(env_path)
            ], check=True, capture_output=True)
            
            print(f"✅ Ambiente '{env_name}' criado em {env_path}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Erro ao criar ambiente '{env_name}': {e}")
            return False
    
    def install_requirements(self, env_name: str) -> bool:
        """Instala requirements em um ambiente específico"""
        if env_name not in self.env_configs:
            return False
            
        env_path = self.base_dir / env_name
        pip_path = env_path / "bin" / "pip"
        
        if not pip_path.exists():
            pip_path = env_path / "Scripts" / "pip.exe"  # Windows
            
        if not pip_path.exists():
            print(f"❌ Pip não encontrado para ambiente '{env_name}'")
            return False
        
        requirements = self.env_configs[env_name]["requirements"]
        
        try:
            # Atualiza pip primeiro
            subprocess.run([
                str(pip_path), "install", "--upgrade", "pip"
            ], check=True, capture_output=True)
            
            # Instala requirements
            for req in requirements:
                print(f"📦 Instalando {req} em {env_name}...")
                result = subprocess.run([
                    str(pip_path), "install", req
                ], capture_output=True, text=True)
                
                if result.returncode != 0:
                    print(f"⚠️ Falha ao instalar {req}: {result.stderr}")
                else:
                    print(f"✅ {req} instalado com sucesso")
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Erro durante instalação: {e}")
            return False
    
    def activate_env(self, env_name: str) -> Optional[str]:
        """Retorna o path do Python do ambiente específico"""
        if env_name not in self.env_configs:
            return None
            
        env_path = self.base_dir / env_name
        python_path = env_path / "bin" / "python"
        
        if not python_path.exists():
            python_path = env_path / "Scripts" / "python.exe"  # Windows
            
        if python_path.exists():
            self.current_env = env_name
            return str(python_path)
        
        return None
    
    def run_in_env(self, env_name: str, script: str, *args) -> int:
        """Executa um script no ambiente específico"""
        python_path = self.activate_env(env_name)
        if not python_path:
            print(f"❌ Ambiente '{env_name}' não encontrado")
            return 1
            
        try:
            result = subprocess.run([
                python_path, script, *args
            ])
            return result.returncode
            
        except Exception as e:
            print(f"❌ Erro ao executar em '{env_name}': {e}")
            return 1
    
    def list_envs(self) -> None:
        """Lista todos os ambientes disponíveis"""
        print("🌍 Ambientes Quimera Disponíveis:")
        print("=" * 50)
        
        for env_name, config in self.env_configs.items():
            env_path = self.base_dir / env_name
            status = "✅ Instalado" if env_path.exists() else "⚪ Não instalado"
            
            print(f"📁 {env_name:12} - {config['description']}")
            print(f"   Status: {status}")
            print(f"   Pacotes: {len(config['requirements'])}")
            print()
    
    def setup_all_envs(self) -> None:
        """Configura todos os ambientes automaticamente"""
        print("🚀 Configurando todos os ambientes Quimera...")
        print("=" * 50)
        
        for env_name in self.env_configs.keys():
            print(f"\n🔧 Configurando ambiente '{env_name}'...")
            
            if self.create_env(env_name):
                if self.install_requirements(env_name):
                    print(f"✅ Ambiente '{env_name}' pronto!")
                else:
                    print(f"❌ Falha na instalação do ambiente '{env_name}'")
            else:
                print(f"❌ Falha na criação do ambiente '{env_name}'")
        
        print("\n🎉 Configuração completa!")
        self.list_envs()

def main():
    """Interface CLI do gerenciador"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Gerenciador de Ambientes Quimera")
    parser.add_argument("command", choices=[
        "setup", "list", "create", "install", "run"
    ])
    parser.add_argument("--env", help="Nome do ambiente")
    parser.add_argument("--script", help="Script para executar")
    parser.add_argument("args", nargs="*", help="Argumentos para o script")
    
    args = parser.parse_args()
    manager = QuimeraEnvManager()
    
    if args.command == "setup":
        manager.setup_all_envs()
    elif args.command == "list":
        manager.list_envs()
    elif args.command == "create" and args.env:
        manager.create_env(args.env)
    elif args.command == "install" and args.env:
        manager.install_requirements(args.env)
    elif args.command == "run" and args.env and args.script:
        return manager.run_in_env(args.env, args.script, *args.args)
    else:
        parser.print_help()

if __name__ == "__main__":
    sys.exit(main())