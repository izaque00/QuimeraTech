#!/usr/bin/env python3
"""
Script para verificar versões compatíveis dos pacotes LangChain
"""
import requests
import json
from packaging.version import Version, parse

def get_package_info(package_name):
    """Obtém informações do pacote do PyPI"""
    try:
        url = f"https://pypi.org/pypi/{package_name}/json"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Erro ao buscar {package_name}: {e}")
    return None

def get_latest_version(package_name):
    """Obtém a versão mais recente de um pacote"""
    info = get_package_info(package_name)
    if info:
        return info["info"]["version"]
    return None

def get_dependencies(package_name, version=None):
    """Obtém as dependências de um pacote específico"""
    info = get_package_info(package_name)
    if not info:
        return []
    
    if version:
        # Busca uma versão específica
        if version in info.get("releases", {}):
            releases = info["releases"][version]
        else:
            return []
    else:
        # Usa a versão mais recente
        version = info["info"]["version"]
        releases = info["releases"].get(version, [])
    
    # Pega as dependências do primeiro wheel/sdist disponível
    for release in releases:
        if release.get("requires_dist"):
            return release["requires_dist"]
    
    return []

# Pacotes que queremos verificar
packages = [
    "langchain",
    "langchain-core", 
    "langchain-openai",
    "langchain-cloudflare",
    "langchain-together",
    "tiktoken"
]

print("=== Verificando versões mais recentes ===")
versions = {}
for package in packages:
    latest = get_latest_version(package)
    versions[package] = latest
    print(f"{package}: {latest}")

print("\n=== Verificando dependências ===")
for package in packages:
    if versions[package]:
        deps = get_dependencies(package, versions[package])
        print(f"\n{package} {versions[package]} requer:")
        for dep in deps or []:
            if any(x in dep.lower() for x in ["langchain", "tiktoken"]):
                print(f"  - {dep}")