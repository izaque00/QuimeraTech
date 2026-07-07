"""
Testes para DiagnosticoSistemico
Valida verificações de sistema, dependências e estrutura do projeto
"""

import pytest
import tempfile
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.append(str(Path(__file__).parent.parent.parent))

from utils.diagnostico_sistemico import DiagnosticoSistemico


class TestDiagnosticoSistemico:
    """Testes do diagnóstico sistêmico"""
    
    @pytest.fixture
    def diagnostico(self):
        """Cria instância do diagnóstico para teste"""
        return DiagnosticoSistemico()
    
    @pytest.fixture
    def temp_project(self):
        """Cria projeto temporário para testes"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Cria estrutura básica de projeto
            os.makedirs(os.path.join(temp_dir, 'src'))
            os.makedirs(os.path.join(temp_dir, 'tests'))
            
            # Cria arquivos básicos
            with open(os.path.join(temp_dir, 'requirements.txt'), 'w') as f:
                f.write('requests>=2.0.0\nnumpy>=1.0.0\n')
            
            with open(os.path.join(temp_dir, 'setup.py'), 'w') as f:
                f.write('from setuptools import setup\nsetup(name="test")')
            
            with open(os.path.join(temp_dir, 'src', 'main.py'), 'w') as f:
                f.write('print("Hello World")')
            
            yield temp_dir
    
    def test_inicializacao_basica(self, diagnostico):
        """Testa inicialização básica do diagnóstico"""
        assert diagnostico is not None
        assert hasattr(diagnostico, 'verificar_info_sistema')
        assert hasattr(diagnostico, 'verificar_ambiente_python')
        assert hasattr(diagnostico, 'verificar_dependencias_core')
    
    def test_info_sistema(self, diagnostico):
        """Testa coleta de informações do sistema"""
        info = diagnostico.verificar_info_sistema()
        
        assert 'os' in info
        assert 'python_version' in info
        assert 'architecture' in info
        assert 'cpu_count' in info
        assert 'memory_total' in info
        
        # Verifica tipos
        assert isinstance(info['cpu_count'], int)
        assert isinstance(info['memory_total'], (int, float))
        assert info['cpu_count'] > 0
        assert info['memory_total'] > 0
    
    def test_ambiente_python(self, diagnostico):
        """Testa verificação do ambiente Python"""
        resultado = diagnostico.verificar_ambiente_python()
        
        assert 'python_executable' in resultado
        assert 'python_version' in resultado
        assert 'pip_version' in resultado
        assert 'virtual_env' in resultado
        
        # Python deve estar disponível
        assert os.path.exists(resultado['python_executable'])
        assert len(resultado['python_version']) > 0
    
    def test_dependencias_core(self, diagnostico):
        """Testa verificação de dependências core"""
        resultado = diagnostico.verificar_dependencias_core()
        
        assert 'sucesso' in resultado
        assert 'dependencias_instaladas' in resultado
        assert 'dependencias_faltantes' in resultado
        
        # Verifica estrutura
        assert isinstance(resultado['dependencias_instaladas'], list)
        assert isinstance(resultado['dependencias_faltantes'], list)
    
    def test_dependencias_opcionais(self, diagnostico):
        """Testa verificação de dependências opcionais"""
        resultado = diagnostico.verificar_dependencias_opcionais()
        
        assert 'redis' in resultado
        assert 'numpy' in resultado
        assert 'torch' in resultado
        
        # Cada dependência deve ter status
        for dep, status in resultado.items():
            assert 'disponivel' in status
            assert isinstance(status['disponivel'], bool)
    
    def test_estrutura_projeto_valida(self, diagnostico, temp_project):
        """Testa verificação de estrutura de projeto válida"""
        resultado = diagnostico.verificar_estrutura_projeto(temp_project)
        
        assert 'sucesso' in resultado
        assert 'problemas' in resultado
        assert 'estrutura_encontrada' in resultado
        
        # Deve encontrar estrutura básica
        estrutura = resultado['estrutura_encontrada']
        assert 'requirements.txt' in estrutura
        assert 'setup.py' in estrutura
        assert 'src/' in estrutura
    
    def test_estrutura_projeto_invalida(self, diagnostico):
        """Testa verificação de projeto com estrutura inválida"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Diretório vazio
            resultado = diagnostico.verificar_estrutura_projeto(temp_dir)
            
            assert resultado['sucesso'] is False
            assert len(resultado['problemas']) > 0
    
    def test_arquivos_criticos(self, diagnostico, temp_project):
        """Testa verificação de arquivos críticos"""
        resultado = diagnostico.verificar_arquivos_criticos(temp_project)
        
        assert 'arquivos_encontrados' in resultado
        assert 'arquivos_faltantes' in resultado
        
        # requirements.txt deve estar presente
        assert 'requirements.txt' in resultado['arquivos_encontrados']
    
    def test_sintaxe_python(self, diagnostico, temp_project):
        """Testa verificação de sintaxe dos arquivos Python"""
        resultado = diagnostico.verificar_sintaxe_python(temp_project)
        
        assert 'total_arquivos' in resultado
        assert 'arquivos_validos' in resultado
        assert 'arquivos_com_erro' in resultado
        
        # main.py deve ter sintaxe válida
        assert resultado['total_arquivos'] >= 1
        assert len(resultado['arquivos_com_erro']) == 0
    
    def test_sintaxe_python_com_erro(self, diagnostico):
        """Testa detecção de erro de sintaxe"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Cria arquivo com erro de sintaxe
            arquivo_erro = os.path.join(temp_dir, 'erro.py')
            with open(arquivo_erro, 'w') as f:
                f.write('def funcao(\n    print("erro de sintaxe"')
            
            resultado = diagnostico.verificar_sintaxe_python(temp_dir)
            
            assert len(resultado['arquivos_com_erro']) > 0
            assert 'erro.py' in str(resultado['arquivos_com_erro'])
    
    def test_diagnostico_completo(self, diagnostico, temp_project):
        """Testa execução de diagnóstico completo"""
        resultado = diagnostico.executar_diagnostico_completo(temp_project)
        
        # Verifica seções principais
        assert 'info_sistema' in resultado
        assert 'ambiente_python' in resultado
        assert 'dependencias_core' in resultado
        assert 'dependencias_opcionais' in resultado
        assert 'estrutura_projeto' in resultado
        assert 'arquivos_criticos' in resultado
        assert 'sintaxe_python' in resultado
        
        # Verifica resumo
        assert 'resumo' in resultado
        resumo = resultado['resumo']
        assert 'status_geral' in resumo
        assert 'total_problemas' in resumo
        assert 'recomendacoes' in resumo
    
    def test_salvar_relatorio(self, diagnostico, temp_project):
        """Testa salvamento de relatório"""
        resultado = diagnostico.executar_diagnostico_completo(temp_project)
        
        arquivo_relatorio = os.path.join(temp_project, 'diagnostico_teste.md')
        sucesso = diagnostico.salvar_relatorio(resultado, arquivo_relatorio)
        
        assert sucesso is True
        assert os.path.exists(arquivo_relatorio)
        
        # Verifica conteúdo do relatório
        with open(arquivo_relatorio, 'r', encoding='utf-8') as f:
            conteudo = f.read()
        
        assert '# RELATÓRIO DE DIAGNÓSTICO SISTÊMICO' in conteudo
        assert 'Sistema Operacional' in conteudo
        assert 'Python' in conteudo
    
    def test_verificacao_servicos_externos(self, diagnostico):
        """Testa verificação de serviços externos (se implementada)"""
        # Esta é uma funcionalidade que pode ser expandida
        resultado = diagnostico.verificar_servicos_externos()
        
        assert isinstance(resultado, dict)
        # Pode estar vazio se não houver serviços configurados
    
    @patch('psutil.virtual_memory')
    def test_verificacao_memoria(self, mock_memory, diagnostico):
        """Testa verificação de memória com mock"""
        # Mock da memória
        mock_memory.return_value.total = 8 * 1024 * 1024 * 1024  # 8GB
        mock_memory.return_value.available = 4 * 1024 * 1024 * 1024  # 4GB
        
        info = diagnostico.verificar_info_sistema()
        
        assert info['memory_total'] > 0
        mock_memory.assert_called()
    
    def test_deteccao_problemas_performance(self, diagnostico):
        """Testa detecção de problemas de performance"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Cria muitos arquivos para simular projeto grande
            for i in range(100):
                arquivo = os.path.join(temp_dir, f'file_{i}.py')
                with open(arquivo, 'w') as f:
                    f.write(f'# Arquivo {i}\nprint("test")')
            
            resultado = diagnostico.verificar_sintaxe_python(temp_dir)
            
            # Deve processar todos os arquivos
            assert resultado['total_arquivos'] == 100
    
    def test_verificacao_seguranca_basica(self, diagnostico, temp_project):
        """Testa verificações básicas de segurança"""
        resultado = diagnostico.verificar_seguranca_basica(temp_project)
        
        assert isinstance(resultado, dict)
        assert 'problemas_seguranca' in resultado
        assert isinstance(resultado['problemas_seguranca'], list)
    
    def test_formato_relatorio_markdown(self, diagnostico):
        """Testa formatação do relatório em Markdown"""
        dados_teste = {
            'info_sistema': {'os': 'Linux', 'python_version': '3.8'},
            'resumo': {'status_geral': 'OK', 'total_problemas': 0}
        }
        
        relatorio = diagnostico._formatar_relatorio_markdown(dados_teste)
        
        assert isinstance(relatorio, str)
        assert '# RELATÓRIO DE DIAGNÓSTICO SISTÊMICO' in relatorio
        assert '## Sistema' in relatorio
        assert 'Linux' in relatorio
    
    def test_recomendacoes_automaticas(self, diagnostico):
        """Testa geração de recomendações automáticas"""
        problemas_teste = [
            'Dependência numpy não encontrada',
            'Arquivo requirements.txt faltando',
            'Erro de sintaxe em arquivo.py'
        ]
        
        recomendacoes = diagnostico._gerar_recomendacoes(problemas_teste)
        
        assert isinstance(recomendacoes, list)
        assert len(recomendacoes) > 0
        
        # Deve sugerir instalação de numpy
        assert any('numpy' in rec.lower() for rec in recomendacoes)
    
    def test_tolerancia_falhas(self, diagnostico):
        """Testa tolerância a falhas em verificações"""
        # Testa com diretório que não existe
        resultado = diagnostico.verificar_estrutura_projeto('/diretorio/inexistente')
        
        # Não deve quebrar, deve retornar erro gracioso
        assert 'sucesso' in resultado
        assert resultado['sucesso'] is False
        assert 'problemas' in resultado


class TestDiagnosticoPerformance:
    """Testes de performance do diagnóstico"""
    
    @pytest.fixture
    def diagnostico(self):
        return DiagnosticoSistemico()
    
    def test_performance_projeto_grande(self, diagnostico):
        """Testa performance com projeto grande"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Cria estrutura complexa
            for i in range(10):
                subdir = os.path.join(temp_dir, f'subdir_{i}')
                os.makedirs(subdir)
                
                for j in range(10):
                    arquivo = os.path.join(subdir, f'file_{j}.py')
                    with open(arquivo, 'w') as f:
                        f.write('print("test")\n' * 100)  # Arquivo grande
            
            import time
            inicio = time.time()
            
            resultado = diagnostico.verificar_sintaxe_python(temp_dir)
            
            tempo_execucao = time.time() - inicio
            
            # Deve processar em tempo razoável (< 10 segundos)
            assert tempo_execucao < 10
            assert resultado['total_arquivos'] == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])