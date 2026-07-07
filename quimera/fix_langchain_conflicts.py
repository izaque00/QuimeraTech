#!/usr/bin/env python3
"""
Script para corrigir conflitos de versão do LangChain no pyproject.toml
"""
import re

# Versões conhecidas por serem compatíveis
LANGCHAIN_COMPATIBLE_VERSIONS = {
    "langchain": "0.3.0",
    "langchain-core": "0.3.0", 
    "langchain-community": "0.3.0",
    "langchain-openai": "0.2.0",
    "langchain-groq": "0.2.0",
    "langchain-google-genai": "2.0.0",
    "langchain-cohere": "0.3.0",
    "langchain-cloudflare": "0.1.0",
    "langchain-mistralai": "0.2.0",
    "langchain-together": "0.2.0",
    "tiktoken": "0.8.0"
}

def fix_pyproject_toml():
    """Corrige o pyproject.toml com versões compatíveis"""
    with open("pyproject.toml", "r", encoding="utf-8") as f:
        content = f.read()
    
    # Backup
    with open("pyproject_before_langchain_fix.toml", "w", encoding="utf-8") as f:
        f.write(content)
    
    # Aplica as correções
    for package, version in LANGCHAIN_COMPATIBLE_VERSIONS.items():
        # Procura pela linha do pacote e substitui a versão
        pattern = rf'^({re.escape(package)}\s*=\s*{{version\s*=\s*)"[^"]*"'
        replacement = rf'\1"^{version}"'
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        
        # Para dependências simples
        pattern = rf'^({re.escape(package)}\s*=\s*)"[^"]*"'
        replacement = rf'\1"^{version}"'
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    
    # Salva o arquivo corrigido
    with open("pyproject.toml", "w", encoding="utf-8") as f:
        f.write(content)
    
    print("✅ pyproject.toml corrigido com versões compatíveis do LangChain")

if __name__ == "__main__":
    fix_pyproject_toml()