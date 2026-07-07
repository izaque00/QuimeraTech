#!/usr/bin/env python3
"""
Teste do Sistema de Plugins do Quimera
Script para validar o framework plug-and-play

Author: Quimera AI System
Version: 1.0.0
"""

import asyncio
import sys
import os
import tempfile
import logging
from pathlib import Path

# Adicionar o diretório do Quimera ao path
sys.path.insert(0, '/home/ubuntu/quimera_final')

from quimera.plugins.plugin_manager import PluginManager
from quimera.plugins.base_plugin import PluginType

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_plugin_discovery():
    """Testa descoberta automática de plugins"""
    print("🔍 Testando descoberta de plugins...")

    plugin_manager = PluginManager(
        plugin_dirs=['/home/ubuntu/quimera_final/quimera/plugins/builtin'],
        auto_discover=True
    )

    discovered = plugin_manager.discover_plugins()
    available_plugins = list(plugin_manager.registry.available_plugins.keys())

    print(f"✅ Plugins descobertos: {len(discovered)}")
    print(f"📋 Plugins disponíveis: {available_plugins}")

    return plugin_manager


async def test_plugin_loading(plugin_manager):
    """Testa carregamento de plugins"""
    print("\n📦 Testando carregamento de plugins...")

    # Tentar carregar plugins built-in
    available_plugins = list(plugin_manager.registry.available_plugins.keys())

    load_results = {}
    for plugin_name in available_plugins:
        try:
            result = plugin_manager.load_plugin(plugin_name)
            load_results[plugin_name] = result
            print(f"{'✅' if result else '❌'} {plugin_name}: {'Carregado' if result else 'Falha'}")
        except Exception as e:
            load_results[plugin_name] = False
            print(f"❌ {plugin_name}: Erro - {e}")

    loaded_plugins = plugin_manager.registry.list_loaded_plugins()
    print(f"\n📊 Plugins carregados com sucesso: {len(loaded_plugins)}")

    return load_results


async def test_enhanced_code_analyzer(plugin_manager):
    """Testa o plugin Enhanced Code Analyzer"""
    print("\n🔬 Testando Enhanced Code Analyzer...")

    # Código Python de exemplo para análise
    test_code = '''
def calculate_fibonacci(n):
    """
    Calcula o n-ésimo número de Fibonacci

    Args:
        n (int): Posição na sequência

    Returns:
        int: Número de Fibonacci
    """
    if n <= 1:
        return n
    return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)

class DataProcessor:
    """Processador de dados com múltiplos métodos"""

    def __init__(self):
        self.data = []

    def add_data(self, item):
        self.data.append(item)

    def process_data(self):
        # Esta função é muito longa e deveria ser refatorada
        result = []
        for item in self.data:
            if isinstance(item, str):
                processed = item.upper()
            elif isinstance(item, int):
                processed = item * 2
            else:
                processed = str(item)
            result.append(processed)
        return result

# Possível problema de segurança
password = "hardcoded_password_123"
'''

    try:
        # Executar análise
        result = await plugin_manager.execute_plugin(
            'enhanced_code_analyzer',
            test_code
        )

        if result.success:
            print("✅ Análise executada com sucesso!")

            data = result.data
            print(f"📊 Issues encontrados: {data.get('total_issues', 0)}")
            print(f"📈 Métricas: {data.get('metrics', {})}")
            print(f"🔧 Fontes utilizadas: {data.get('sources', [])}")

            # Mostrar alguns issues
            issues = data.get('issues', [])
            if issues:
                print("\n🚨 Principais issues:")
                for issue in issues[:3]:
                    print(f"  - {issue.get('severity', 'info').upper()}: {issue.get('message', 'N/A')}")
        else:
            print(f"❌ Falha na análise: {result.error}")

    except Exception as e:
        print(f"❌ Erro no teste: {e}")


async def test_smart_documentation_generator(plugin_manager):
    """Testa o plugin Smart Documentation Generator"""
    print("\n📚 Testando Smart Documentation Generator...")

    # Código Python de exemplo para documentação
    test_code = '''
"""
Módulo de utilidades matemáticas
Contém funções para cálculos básicos
"""

import math

def calculate_area_circle(radius):
    """
    Calcula a área de um círculo

    Args:
        radius (float): Raio do círculo

    Returns:
        float: Área do círculo
    """
    return math.pi * radius ** 2

class Calculator:
    """Calculadora básica com operações matemáticas"""

    def __init__(self):
        """Inicializa a calculadora"""
        self.history = []

    def add(self, a, b):
        """
        Soma dois números

        Args:
            a (float): Primeiro número
            b (float): Segundo número

        Returns:
            float: Resultado da soma
        """
        result = a + b
        self.history.append(f"{a} + {b} = {result}")
        return result

    def multiply(self, a, b):
        """
        Multiplica dois números

        Args:
            a (float): Primeiro número
            b (float): Segundo número

        Returns:
            float: Resultado da multiplicação
        """
        result = a * b
        self.history.append(f"{a} * {b} = {result}")
        return result
'''

    try:
        # Executar geração de documentação
        result = await plugin_manager.execute_plugin(
            'smart_documentation_generator',
            test_code
        )

        if result.success:
            print("✅ Documentação gerada com sucesso!")

            data = result.data
            print(f"📄 Tipo: {data.get('type', 'N/A')}")
            print(f"📊 Exemplos gerados: {len(data.get('examples', []))}")

            # Mostrar parte da documentação
            documentation = data.get('documentation', '')
            if documentation:
                print("\n📝 Prévia da documentação:")
                lines = documentation.split('\n')
                for line in lines[:10]:  # Mostrar primeiras 10 linhas
                    print(f"  {line}")
                if len(lines) > 10:
                    print(f"  ... (mais {len(lines) - 10} linhas)")
        else:
            print(f"❌ Falha na geração: {result.error}")

    except Exception as e:
        print(f"❌ Erro no teste: {e}")


async def test_plugin_execution_by_type(plugin_manager):
    """Testa execução de plugins por tipo"""
    print("\n🎯 Testando execução por tipo de plugin...")

    # Testar plugins do tipo ANALYZER
    analyzer_plugins = plugin_manager.registry.list_plugins_by_type(PluginType.ANALYZER)
    print(f"🔬 Plugins analisadores encontrados: {len(analyzer_plugins)}")

    if analyzer_plugins:
        test_data = "print('Hello, World!')"

        results = await plugin_manager.execute_plugins_by_type(
            PluginType.ANALYZER,
            test_data,
            parallel=True
        )

        print(f"📊 Resultados de análise: {len(results)}")
        for plugin_name, result in results.items():
            status = "✅" if result.success else "❌"
            print(f"  {status} {plugin_name}: {result.success}")

    # Testar plugins do tipo DOCUMENTATION
    doc_plugins = plugin_manager.registry.list_plugins_by_type(PluginType.DOCUMENTATION)
    print(f"\n📚 Plugins de documentação encontrados: {len(doc_plugins)}")

    if doc_plugins:
        test_data = "def hello(): return 'world'"

        results = await plugin_manager.execute_plugins_by_type(
            PluginType.DOCUMENTATION,
            test_data,
            parallel=False  # Sequencial para documentação
        )

        print(f"📊 Resultados de documentação: {len(results)}")
        for plugin_name, result in results.items():
            status = "✅" if result.success else "❌"
            print(f"  {status} {plugin_name}: {result.success}")


async def test_plugin_status_monitoring(plugin_manager):
    """Testa monitoramento de status dos plugins"""
    print("\n📊 Testando monitoramento de status...")

    # Obter status de todos os plugins
    all_status = plugin_manager.get_plugin_status()

    print(f"📋 Status de {len(all_status)} plugins:")
    for status in all_status:
        plugin_name = status.get('name', 'Unknown')
        plugin_status = status.get('status', 'Unknown')
        uptime = status.get('uptime', 0)

        print(f"  📌 {plugin_name}: {plugin_status} (uptime: {uptime:.2f}s)")


async def test_plugin_configuration():
    """Testa configuração personalizada de plugins"""
    print("\n⚙️ Testando configuração personalizada...")

    # Configuração customizada para o Enhanced Code Analyzer
    custom_config = {
        'enable_external_apis': False,  # Desabilitar APIs externas
        'enable_local_analysis': True,
        'enable_quimera_engines': True
    }

    plugin_manager = PluginManager(
        plugin_dirs=['/home/ubuntu/quimera_final/quimera/plugins/builtin'],
        auto_discover=False
    )

    # Carregar plugin com configuração customizada
    success = plugin_manager.load_plugin('enhanced_code_analyzer', custom_config)

    if success:
        print("✅ Plugin carregado com configuração customizada")

        # Testar execução
        test_code = "def test(): pass"
        result = await plugin_manager.execute_plugin('enhanced_code_analyzer', test_code)

        if result.success:
            sources = result.data.get('sources', [])
            print(f"🔧 Fontes utilizadas: {sources}")
            print("✅ Configuração customizada funcionando")
        else:
            print(f"❌ Erro na execução: {result.error}")
    else:
        print("❌ Falha ao carregar plugin com configuração customizada")


async def test_error_handling(plugin_manager):
    """Testa tratamento de erros"""
    print("\n🚨 Testando tratamento de erros...")

    # Teste 1: Plugin inexistente
    result = await plugin_manager.execute_plugin('plugin_inexistente', 'test')
    print(f"Plugin inexistente: {'✅' if not result.success else '❌'}")

    # Teste 2: Dados inválidos
    if 'enhanced_code_analyzer' in plugin_manager.registry.loaded_plugins:
        result = await plugin_manager.execute_plugin('enhanced_code_analyzer', None)
        print(f"Dados inválidos: {'✅' if not result.success else '❌'}")

    # Teste 3: Código com erro de sintaxe
    if 'enhanced_code_analyzer' in plugin_manager.registry.loaded_plugins:
        invalid_code = "def invalid_syntax( missing_closing_paren:"
        result = await plugin_manager.execute_plugin('enhanced_code_analyzer', invalid_code)
        print(f"Código inválido: {'✅' if result.success else '❌'} (deve lidar com erro)")


async def test_performance():
    """Testa performance do sistema de plugins"""
    print("\n⚡ Testando performance...")

    plugin_manager = PluginManager(
        plugin_dirs=['/home/ubuntu/quimera_final/quimera/plugins/builtin'],
        auto_discover=True
    )

    # Carregar todos os plugins
    import time
    start_time = time.time()

    load_results = plugin_manager.load_all_plugins()

    load_time = time.time() - start_time
    successful_loads = sum(load_results.values())

    print(f"⏱️ Tempo de carregamento: {load_time:.2f}s")
    print(f"📊 Plugins carregados: {successful_loads}/{len(load_results)}")

    # Teste de execução paralela
    if successful_loads > 0:
        test_code = "def performance_test(): return 'fast'"

        start_time = time.time()

        # Executar múltiplas análises em paralelo
        tasks = []
        for i in range(5):
            if 'enhanced_code_analyzer' in plugin_manager.registry.loaded_plugins:
                task = plugin_manager.execute_plugin('enhanced_code_analyzer', test_code)
                tasks.append(task)

        if tasks:
            results = await asyncio.gather(*tasks)
            execution_time = time.time() - start_time

            successful_executions = sum(1 for r in results if r.success)
            print(f"⚡ Execução paralela: {execution_time:.2f}s para {len(tasks)} tarefas")
            print(f"✅ Sucessos: {successful_executions}/{len(tasks)}")


async def main():
    """Função principal de teste"""
    print("🚀 Iniciando testes do sistema de plugins do Quimera")
    print("=" * 60)

    try:
        # Teste 1: Descoberta de plugins
        plugin_manager = await test_plugin_discovery()

        # Teste 2: Carregamento de plugins
        load_results = await test_plugin_loading(plugin_manager)

        # Teste 3: Enhanced Code Analyzer
        if 'enhanced_code_analyzer' in plugin_manager.registry.loaded_plugins:
            await test_enhanced_code_analyzer(plugin_manager)

        # Teste 4: Smart Documentation Generator
        if 'smart_documentation_generator' in plugin_manager.registry.loaded_plugins:
            await test_smart_documentation_generator(plugin_manager)

        # Teste 5: Execução por tipo
        await test_plugin_execution_by_type(plugin_manager)

        # Teste 6: Monitoramento de status
        await test_plugin_status_monitoring(plugin_manager)

        # Teste 7: Configuração personalizada
        await test_plugin_configuration()

        # Teste 8: Tratamento de erros
        await test_error_handling(plugin_manager)

        # Teste 9: Performance
        await test_performance()

        print("\n" + "=" * 60)
        print("🎉 Testes concluídos!")

        # Finalizar plugin manager
        plugin_manager.shutdown()

    except Exception as e:
        print(f"\n❌ Erro durante os testes: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())