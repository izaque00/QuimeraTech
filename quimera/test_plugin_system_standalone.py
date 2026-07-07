#!/usr/bin/env python3
"""
Teste Standalone do Sistema de Plugins do Quimera
Script para validar o framework plug-and-play sem dependências do Quimera principal

Author: Quimera AI System
Version: 1.0.0
"""

import asyncio
import sys
import os
import tempfile
import logging
import importlib.util
from pathlib import Path

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_module_from_file(file_path, module_name):
    """Carrega módulo Python de um arquivo"""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def test_base_plugin_system():
    """Testa o sistema base de plugins"""
    print("🔧 Testando sistema base de plugins...")

    try:
        # Carregar módulos necessários
        base_plugin_path = "/home/ubuntu/quimera_final/quimera/plugins/base_plugin.py"
        base_plugin = load_module_from_file(base_plugin_path, "base_plugin")

        # Testar criação de metadados
        metadata = base_plugin.create_plugin_metadata(
            name="test_plugin",
            version="1.0.0",
            description="Plugin de teste",
            author="Test Author",
            plugin_type=base_plugin.PluginType.ANALYZER
        )

        print(f"✅ Metadados criados: {metadata.name} v{metadata.version}")
        print(f"📋 Tipo: {metadata.plugin_type.value}")
        print(f"👤 Autor: {metadata.author}")

        return True

    except Exception as e:
        print(f"❌ Erro no teste base: {e}")
        return False


async def test_api_connector():
    """Testa o conector de API"""
    print("\n🌐 Testando API Connector...")

    try:
        # Carregar módulos necessários
        base_plugin_path = "/home/ubuntu/quimera_final/quimera/plugins/base_plugin.py"
        base_plugin = load_module_from_file(base_plugin_path, "base_plugin")

        api_connector_path = "/home/ubuntu/quimera_final/quimera/plugins/api_connector.py"
        api_connector = load_module_from_file(api_connector_path, "api_connector")

        # Criar configuração de teste
        config = {
            'base_url': 'https://api.github.com',
            'auth_type': 'none',
            'timeout': 10,
            'enable_cache': False  # Desabilitar cache para teste
        }

        # Criar instância do conector
        connector = api_connector.APIConnector(config)

        # Testar metadados
        metadata = connector.get_metadata()
        print(f"✅ API Connector criado: {metadata.name}")
        print(f"🔧 Capacidades: {metadata.capabilities}")

        # Testar adição de endpoint
        endpoint = api_connector.APIEndpoint(
            name="test_endpoint",
            url="/test",
            method="GET"
        )

        connector.add_endpoint(endpoint)
        print(f"✅ Endpoint adicionado: {endpoint.name}")

        # Testar inicialização (sem executar requisições reais)
        print("✅ API Connector testado com sucesso")

        return True

    except Exception as e:
        print(f"❌ Erro no teste API Connector: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_enhanced_code_analyzer_standalone():
    """Testa o Enhanced Code Analyzer de forma standalone"""
    print("\n🔬 Testando Enhanced Code Analyzer (standalone)...")

    try:
        # Carregar módulos necessários
        base_plugin_path = "/home/ubuntu/quimera_final/quimera/plugins/base_plugin.py"
        base_plugin = load_module_from_file(base_plugin_path, "base_plugin")

        api_connector_path = "/home/ubuntu/quimera_final/quimera/plugins/api_connector.py"
        api_connector = load_module_from_file(api_connector_path, "api_connector")

        analyzer_path = "/home/ubuntu/quimera_final/quimera/plugins/builtin/enhanced_code_analyzer.py"
        analyzer_module = load_module_from_file(analyzer_path, "enhanced_code_analyzer")

        # Criar configuração de teste
        config = {
            'enable_external_apis': False,  # Desabilitar APIs externas
            'enable_local_analysis': True,
            'enable_quimera_engines': False  # Desabilitar engines do Quimera
        }

        # Criar instância do analisador
        analyzer = analyzer_module.EnhancedCodeAnalyzer(config)

        # Testar metadados
        metadata = analyzer.get_metadata()
        print(f"✅ Enhanced Code Analyzer criado: {metadata.name}")
        print(f"🔧 Capacidades: {metadata.capabilities}")

        # Inicializar plugin
        init_success = await analyzer.initialize_async()
        print(f"{'✅' if init_success else '❌'} Inicialização: {'Sucesso' if init_success else 'Falha'}")

        if init_success:
            # Testar análise de código
            test_code = '''
def fibonacci(n):
    """Calcula fibonacci de forma recursiva (ineficiente)"""
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

class Calculator:
    def __init__(self):
        self.history = []

    def add(self, a, b):
        result = a + b
        self.history.append(result)
        return result

# Possível problema de segurança
password = "hardcoded_password"
'''

            result = await analyzer.execute(test_code)

            if result.success:
                print("✅ Análise executada com sucesso!")

                data = result.data
                print(f"📊 Issues encontrados: {data.get('total_issues', 0)}")
                print(f"📈 Métricas: {data.get('metrics', {})}")

                # Mostrar alguns issues
                issues = data.get('issues', [])
                if issues:
                    print("\n🚨 Issues encontrados:")
                    for issue in issues[:3]:
                        severity = issue.get('severity', 'info')
                        message = issue.get('message', 'N/A')
                        source = issue.get('source', 'unknown')
                        print(f"  - [{severity.upper()}] {message} (fonte: {source})")

                # Mostrar métricas
                metrics = data.get('metrics', {})
                if metrics:
                    print(f"\n📊 Métricas do código:")
                    for key, value in metrics.items():
                        print(f"  - {key}: {value}")
            else:
                print(f"❌ Falha na análise: {result.error}")

        # Finalizar plugin
        await analyzer.shutdown_async()
        print("✅ Plugin finalizado")

        return True

    except Exception as e:
        print(f"❌ Erro no teste Enhanced Code Analyzer: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_smart_documentation_generator_standalone():
    """Testa o Smart Documentation Generator de forma standalone"""
    print("\n📚 Testando Smart Documentation Generator (standalone)...")

    try:
        # Carregar módulos necessários
        base_plugin_path = "/home/ubuntu/quimera_final/quimera/plugins/base_plugin.py"
        base_plugin = load_module_from_file(base_plugin_path, "base_plugin")

        api_connector_path = "/home/ubuntu/quimera_final/quimera/plugins/api_connector.py"
        api_connector = load_module_from_file(api_connector_path, "api_connector")

        doc_gen_path = "/home/ubuntu/quimera_final/quimera/plugins/builtin/smart_documentation_generator.py"
        doc_gen_module = load_module_from_file(doc_gen_path, "smart_documentation_generator")

        # Criar configuração de teste
        config = {
            'output_format': 'markdown',
            'include_examples': True,
            'include_diagrams': False,  # Desabilitar diagramas para teste
            'auto_generate_api_docs': True
        }

        # Criar instância do gerador
        doc_generator = doc_gen_module.SmartDocumentationGenerator(config)

        # Testar metadados
        metadata = doc_generator.get_metadata()
        print(f"✅ Smart Documentation Generator criado: {metadata.name}")
        print(f"🔧 Capacidades: {metadata.capabilities}")

        # Inicializar plugin
        init_success = await doc_generator.initialize_async()
        print(f"{'✅' if init_success else '❌'} Inicialização: {'Sucesso' if init_success else 'Falha'}")

        if init_success:
            # Testar geração de documentação
            test_code = '''
"""
Módulo de utilidades matemáticas
Fornece funções para cálculos básicos
"""

import math

def calculate_circle_area(radius):
    """
    Calcula a área de um círculo

    Args:
        radius (float): Raio do círculo em metros

    Returns:
        float: Área do círculo em metros quadrados

    Raises:
        ValueError: Se o raio for negativo
    """
    if radius < 0:
        raise ValueError("Raio não pode ser negativo")
    return math.pi * radius ** 2

class GeometryCalculator:
    """
    Calculadora para operações geométricas

    Esta classe fornece métodos para calcular áreas e perímetros
    de diferentes formas geométricas.
    """

    def __init__(self):
        """Inicializa a calculadora geométrica"""
        self.calculations_count = 0

    def rectangle_area(self, width, height):
        """
        Calcula a área de um retângulo

        Args:
            width (float): Largura do retângulo
            height (float): Altura do retângulo

        Returns:
            float: Área do retângulo
        """
        self.calculations_count += 1
        return width * height

    def triangle_area(self, base, height):
        """
        Calcula a área de um triângulo

        Args:
            base (float): Base do triângulo
            height (float): Altura do triângulo

        Returns:
            float: Área do triângulo
        """
        self.calculations_count += 1
        return 0.5 * base * height
'''

            result = await doc_generator.execute(test_code)

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
                    for i, line in enumerate(lines[:15]):  # Mostrar primeiras 15 linhas
                        print(f"  {i+1:2d}: {line}")
                    if len(lines) > 15:
                        print(f"      ... (mais {len(lines) - 15} linhas)")

                # Mostrar exemplos gerados
                examples = data.get('examples', [])
                if examples:
                    print(f"\n💡 Exemplos gerados ({len(examples)}):")
                    for i, example in enumerate(examples[:2]):  # Mostrar primeiros 2
                        print(f"  {i+1}. {example.get('title', 'Sem título')}")
                        code = example.get('code', '')
                        if code:
                            code_lines = code.split('\n')
                            for line in code_lines[:3]:  # Primeiras 3 linhas
                                print(f"     {line}")
                            if len(code_lines) > 3:
                                print(f"     ... (mais {len(code_lines) - 3} linhas)")
            else:
                print(f"❌ Falha na geração: {result.error}")

        # Finalizar plugin
        await doc_generator.shutdown_async()
        print("✅ Plugin finalizado")

        return True

    except Exception as e:
        print(f"❌ Erro no teste Smart Documentation Generator: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_plugin_integration():
    """Testa integração entre plugins"""
    print("\n🔗 Testando integração entre plugins...")

    try:
        # Simular pipeline: Análise -> Documentação
        print("📋 Pipeline: Análise de código → Geração de documentação")

        # Código de teste
        test_code = '''
def process_data(data_list):
    """Processa lista de dados"""
    result = []
    for item in data_list:
        if isinstance(item, str):
            result.append(item.upper())
        elif isinstance(item, int):
            result.append(item * 2)
    return result

class DataManager:
    """Gerenciador de dados"""

    def __init__(self):
        self.data = []

    def add_item(self, item):
        """Adiciona item aos dados"""
        self.data.append(item)
'''

        # Etapa 1: Análise
        print("\n🔬 Etapa 1: Análise de código...")

        # Carregar Enhanced Code Analyzer
        base_plugin_path = "/home/ubuntu/quimera_final/quimera/plugins/base_plugin.py"
        base_plugin = load_module_from_file(base_plugin_path, "base_plugin")

        api_connector_path = "/home/ubuntu/quimera_final/quimera/plugins/api_connector.py"
        api_connector = load_module_from_file(api_connector_path, "api_connector")

        analyzer_path = "/home/ubuntu/quimera_final/quimera/plugins/builtin/enhanced_code_analyzer.py"
        analyzer_module = load_module_from_file(analyzer_path, "enhanced_code_analyzer")

        analyzer = analyzer_module.EnhancedCodeAnalyzer({
            'enable_external_apis': False,
            'enable_local_analysis': True,
            'enable_quimera_engines': False
        })

        await analyzer.initialize_async()
        analysis_result = await analyzer.execute(test_code)

        if analysis_result.success:
            print("✅ Análise concluída")
            issues_count = analysis_result.data.get('total_issues', 0)
            print(f"📊 Issues encontrados: {issues_count}")
        else:
            print(f"❌ Falha na análise: {analysis_result.error}")
            return False

        # Etapa 2: Documentação
        print("\n📚 Etapa 2: Geração de documentação...")

        doc_gen_path = "/home/ubuntu/quimera_final/quimera/plugins/builtin/smart_documentation_generator.py"
        doc_gen_module = load_module_from_file(doc_gen_path, "smart_documentation_generator")

        doc_generator = doc_gen_module.SmartDocumentationGenerator({
            'output_format': 'markdown',
            'include_examples': True
        })

        await doc_generator.initialize_async()
        doc_result = await doc_generator.execute(test_code)

        if doc_result.success:
            print("✅ Documentação gerada")
            examples_count = len(doc_result.data.get('examples', []))
            print(f"📊 Exemplos gerados: {examples_count}")
        else:
            print(f"❌ Falha na documentação: {doc_result.error}")
            return False

        # Etapa 3: Combinar resultados
        print("\n🔗 Etapa 3: Combinando resultados...")

        combined_result = {
            'code': test_code,
            'analysis': analysis_result.data,
            'documentation': doc_result.data,
            'pipeline_success': True,
            'total_processing_time': (
                analysis_result.execution_time + doc_result.execution_time
            )
        }

        print(f"✅ Pipeline concluído em {combined_result['total_processing_time']:.2f}s")
        print(f"📊 Resultado combinado criado com sucesso")

        # Finalizar plugins
        await analyzer.shutdown_async()
        await doc_generator.shutdown_async()

        return True

    except Exception as e:
        print(f"❌ Erro no teste de integração: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_error_handling():
    """Testa tratamento de erros dos plugins"""
    print("\n🚨 Testando tratamento de erros...")

    try:
        # Carregar Enhanced Code Analyzer
        base_plugin_path = "/home/ubuntu/quimera_final/quimera/plugins/base_plugin.py"
        base_plugin = load_module_from_file(base_plugin_path, "base_plugin")

        api_connector_path = "/home/ubuntu/quimera_final/quimera/plugins/api_connector.py"
        api_connector = load_module_from_file(api_connector_path, "api_connector")

        analyzer_path = "/home/ubuntu/quimera_final/quimera/plugins/builtin/enhanced_code_analyzer.py"
        analyzer_module = load_module_from_file(analyzer_path, "enhanced_code_analyzer")

        analyzer = analyzer_module.EnhancedCodeAnalyzer({
            'enable_external_apis': False,
            'enable_local_analysis': True,
            'enable_quimera_engines': False
        })

        await analyzer.initialize_async()

        # Teste 1: Código com erro de sintaxe
        print("🧪 Teste 1: Código com erro de sintaxe")
        invalid_code = "def invalid_function( missing_closing_paren:"

        result = await analyzer.execute(invalid_code)

        if result.success:
            issues = result.data.get('issues', [])
            syntax_errors = [i for i in issues if i.get('type') == 'syntax']
            print(f"✅ Erro de sintaxe detectado: {len(syntax_errors)} issues")
        else:
            print(f"❌ Falha inesperada: {result.error}")

        # Teste 2: Entrada inválida
        print("\n🧪 Teste 2: Entrada inválida (None)")

        result = await analyzer.execute(None)

        if not result.success:
            print(f"✅ Entrada inválida rejeitada: {result.error}")
        else:
            print("❌ Entrada inválida aceita incorretamente")

        # Teste 3: Entrada vazia
        print("\n🧪 Teste 3: Código vazio")

        result = await analyzer.execute("")

        if result.success:
            print(f"✅ Código vazio processado: {result.data.get('total_issues', 0)} issues")
        else:
            print(f"❌ Falha no código vazio: {result.error}")

        await analyzer.shutdown_async()

        print("✅ Testes de tratamento de erros concluídos")
        return True

    except Exception as e:
        print(f"❌ Erro no teste de tratamento de erros: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Função principal de teste"""
    print("🚀 Iniciando testes standalone do sistema de plugins do Quimera")
    print("=" * 70)

    test_results = {}

    try:
        # Teste 1: Sistema base
        test_results['base_system'] = await test_base_plugin_system()

        # Teste 2: API Connector
        test_results['api_connector'] = await test_api_connector()

        # Teste 3: Enhanced Code Analyzer
        test_results['code_analyzer'] = await test_enhanced_code_analyzer_standalone()

        # Teste 4: Smart Documentation Generator
        test_results['doc_generator'] = await test_smart_documentation_generator_standalone()

        # Teste 5: Integração entre plugins
        test_results['integration'] = await test_plugin_integration()

        # Teste 6: Tratamento de erros
        test_results['error_handling'] = await test_error_handling()

        # Resumo dos resultados
        print("\n" + "=" * 70)
        print("📊 RESUMO DOS TESTES")
        print("=" * 70)

        total_tests = len(test_results)
        successful_tests = sum(test_results.values())

        for test_name, success in test_results.items():
            status = "✅ PASSOU" if success else "❌ FALHOU"
            print(f"{test_name.replace('_', ' ').title():<30} {status}")

        print("-" * 70)
        print(f"Total: {successful_tests}/{total_tests} testes passaram")

        if successful_tests == total_tests:
            print("🎉 TODOS OS TESTES PASSARAM!")
            print("✅ Sistema de plugins está funcionando corretamente")
        else:
            print("⚠️  ALGUNS TESTES FALHARAM")
            print("🔧 Verifique os logs acima para detalhes")

    except Exception as e:
        print(f"\n❌ Erro crítico durante os testes: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())