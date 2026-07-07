"""
Testes para OrquestradorUnificado
Valida rotas de decisão e integração entre componentes
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.append(str(Path(__file__).parent.parent))

from core.orquestrador_unificado import OrquestradorUnificado
from utils.diagnostico_sistemico import DiagnosticoSistemico
from utils.corretor_unificado import CorretorUnificado, ResultadoCorrecao
from utils.memoria_evolutiva import MemoriaEvolutiva, RegistroReparo
from utils.fallback_llm import FallbackLLMManager, ResultadoLLM


class TestOrquestradorUnificado:
    """Testes do orchestrador principal"""
    
    @pytest.fixture
    def temp_dir(self):
        """Cria diretório temporário para testes"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def mock_config(self):
        """Configuração mock para testes"""
        return {
            'debug': True,
            'timeout_operacao': 10,
            'max_tentativas': 2,
            'usar_cache': False
        }
    
    @pytest.fixture
    def orquestrador(self, temp_dir, mock_config):
        """Cria instância do orquestrador para teste"""
        return OrquestradorUnificado(
            diretorio_projeto=temp_dir,
            config=mock_config
        )
    
    def test_inicializacao_basica(self, orquestrador):
        """Testa inicialização básica do orquestrador"""
        assert orquestrador is not None
        assert orquestrador.diretorio_projeto is not None
        assert orquestrador.config is not None
        assert hasattr(orquestrador, 'diagnostico')
        assert hasattr(orquestrador, 'corretor')
        assert hasattr(orquestrador, 'memoria')
        assert hasattr(orquestrador, 'fallback_llm')
    
    def test_configuracao_padrao(self, temp_dir):
        """Testa se configuração padrão é aplicada corretamente"""
        orq = OrquestradorUnificado(diretorio_projeto=temp_dir)
        
        assert orq.config['debug'] is False
        assert orq.config['timeout_operacao'] == 30
        assert orq.config['max_tentativas'] == 3
        assert orq.config['usar_cache'] is True
    
    @pytest.mark.asyncio
    async def test_executar_diagnostico_basico(self, orquestrador, temp_dir):
        """Testa execução básica de diagnóstico"""
        # Mock do diagnóstico
        with patch.object(orquestrador.diagnostico, 'executar_diagnostico_completo') as mock_diag:
            mock_diag.return_value = {
                'sucesso': True,
                'problemas_encontrados': [],
                'recomendacoes': []
            }
            
            resultado = await orquestrador.executar_diagnostico()
            
            assert resultado['sucesso'] is True
            assert 'problemas_encontrados' in resultado
            assert 'recomendacoes' in resultado
            mock_diag.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_executar_diagnostico_com_problemas(self, orquestrador):
        """Testa diagnóstico quando problemas são encontrados"""
        problemas_mock = [
            'Dependência faltando: numpy',
            'Arquivo corrompido: config.py'
        ]
        
        with patch.object(orquestrador.diagnostico, 'executar_diagnostico_completo') as mock_diag:
            mock_diag.return_value = {
                'sucesso': False,
                'problemas_encontrados': problemas_mock,
                'recomendacoes': ['Instalar numpy', 'Corrigir config.py']
            }
            
            resultado = await orquestrador.executar_diagnostico()
            
            assert resultado['sucesso'] is False
            assert len(resultado['problemas_encontrados']) == 2
            assert 'numpy' in resultado['problemas_encontrados'][0]
    
    @pytest.mark.asyncio
    async def test_executar_missao_reparo_sucesso(self, orquestrador, temp_dir):
        """Testa missão de reparo bem-sucedida"""
        # Cria arquivo de teste
        arquivo_teste = os.path.join(temp_dir, 'test.py')
        with open(arquivo_teste, 'w') as f:
            f.write('print "hello"')  # Sintaxe Python 2 (erro intencional)
        
        # Mock dos componentes
        with patch.object(orquestrador.corretor, 'corrigir_arquivo') as mock_corretor:
            mock_corretor.return_value = ResultadoCorrecao(
                arquivo=arquivo_teste,
                sucesso=True,
                alteracoes_realizadas=['Convertido para Python 3'],
                erros_corrigidos=['SyntaxError'],
                erros_persistentes=[],
                codigo_antes='print "hello"',
                codigo_depois='print("hello")',
                tempo_processamento=0.5,
                metadados={}
            )
            
            with patch.object(orquestrador.memoria, 'registrar_reparo') as mock_memoria:
                mock_memoria.return_value = True
                
                resultado = await orquestrador.executar_missao_reparo(arquivo_teste)
                
                assert resultado['sucesso'] is True
                assert 'resultado_correcao' in resultado
                assert len(resultado['resultado_correcao'].alteracoes_realizadas) > 0
                mock_corretor.assert_called_once_with(arquivo_teste)
                mock_memoria.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_executar_missao_reparo_falha(self, orquestrador, temp_dir):
        """Testa missão de reparo que falha"""
        arquivo_teste = os.path.join(temp_dir, 'broken.py')
        with open(arquivo_teste, 'w') as f:
            f.write('código completamente inválido $$%')
        
        with patch.object(orquestrador.corretor, 'corrigir_arquivo') as mock_corretor:
            mock_corretor.return_value = ResultadoCorrecao(
                arquivo=arquivo_teste,
                sucesso=False,
                alteracoes_realizadas=[],
                erros_corrigidos=[],
                erros_persistentes=['Erro de sintaxe irrecuperável'],
                codigo_antes='código completamente inválido $$%',
                codigo_depois='código completamente inválido $$%',
                tempo_processamento=1.0,
                metadados={}
            )
            
            resultado = await orquestrador.executar_missao_reparo(arquivo_teste)
            
            assert resultado['sucesso'] is False
            assert len(resultado['resultado_correcao'].erros_persistentes) > 0
    
    @pytest.mark.asyncio
    async def test_modo_continuo_com_arquivos(self, orquestrador, temp_dir):
        """Testa modo contínuo com múltiplos arquivos"""
        # Cria arquivos de teste
        arquivos_teste = []
        for i in range(3):
            arquivo = os.path.join(temp_dir, f'test_{i}.py')
            with open(arquivo, 'w') as f:
                f.write(f'print "hello {i}"')  # Sintaxe Python 2
            arquivos_teste.append(arquivo)
        
        resultados_correcao = []
        for arquivo in arquivos_teste:
            resultados_correcao.append(ResultadoCorrecao(
                arquivo=arquivo,
                sucesso=True,
                alteracoes_realizadas=[f'Corrigido {os.path.basename(arquivo)}'],
                erros_corrigidos=['SyntaxError'],
                erros_persistentes=[],
                codigo_antes=f'print "hello {arquivo[-4]}"',
                codigo_depois=f'print("hello {arquivo[-4]}")',
                tempo_processamento=0.3,
                metadados={}
            ))
        
        with patch.object(orquestrador.corretor, 'corrigir_diretorio') as mock_corretor:
            mock_corretor.return_value = resultados_correcao
            
            with patch.object(orquestrador.memoria, 'registrar_reparo') as mock_memoria:
                mock_memoria.return_value = True
                
                resultado = await orquestrador.executar_modo_continuo()
                
                assert resultado['sucesso'] is True
                assert resultado['total_arquivos_processados'] == len(resultados_correcao)
                assert resultado['arquivos_corrigidos'] == len(resultados_correcao)
                assert mock_corretor.called
    
    @pytest.mark.asyncio
    async def test_fallback_llm_integration(self, orquestrador):
        """Testa integração com sistema de fallback LLM"""
        prompt_teste = "Corrija este código Python: print 'hello'"
        
        with patch.object(orquestrador.fallback_llm, 'processar_com_fallback') as mock_llm:
            mock_llm.return_value = ResultadoLLM(
                sucesso=True,
                resposta='print("hello")',
                modelo_usado='gpt-4o',
                tempo_resposta=1.2,
                tokens_usados=50,
                custo_estimado=0.001,
                erro=None,
                tentativas_realizadas=1,
                metadados={'especialidade': 'python'}
            )
            
            resultado = await orquestrador._consultar_llm(prompt_teste, 'python')
            
            assert resultado.sucesso is True
            assert 'print("hello")' in resultado.resposta
            assert resultado.modelo_usado == 'gpt-4o'
            mock_llm.assert_called_once_with(prompt_teste, 'python', '')
    
    def test_salvar_e_carregar_estado(self, orquestrador, temp_dir):
        """Testa persistência de estado"""
        # Modifica estado
        orquestrador.estatisticas['total_reparos'] = 5
        orquestrador.estatisticas['taxa_sucesso'] = 0.8
        
        # Salva estado
        caminho_estado = os.path.join(temp_dir, 'estado_teste.json')
        orquestrador._salvar_estado_persistente(caminho_estado)
        
        # Verifica se arquivo foi criado
        assert os.path.exists(caminho_estado)
        
        # Cria novo orquestrador e carrega estado
        novo_orquestrador = OrquestradorUnificado(diretorio_projeto=temp_dir)
        novo_orquestrador._carregar_estado_persistente(caminho_estado)
        
        # Verifica se estado foi carregado
        assert novo_orquestrador.estatisticas['total_reparos'] == 5
        assert novo_orquestrador.estatisticas['taxa_sucesso'] == 0.8
    
    def test_validacao_arquivo_inexistente(self, orquestrador):
        """Testa validação de arquivo que não existe"""
        arquivo_inexistente = '/caminho/que/nao/existe.py'
        
        with pytest.raises(FileNotFoundError):
            asyncio.run(orquestrador.executar_missao_reparo(arquivo_inexistente))
    
    def test_configuracao_personalizada(self, temp_dir):
        """Testa aplicação de configuração personalizada"""
        config_custom = {
            'debug': True,
            'timeout_operacao': 60,
            'max_tentativas': 5,
            'usar_memoria_evolutiva': True,
            'salvar_backup': False
        }
        
        orq = OrquestradorUnificado(
            diretorio_projeto=temp_dir,
            config=config_custom
        )
        
        assert orq.config['debug'] is True
        assert orq.config['timeout_operacao'] == 60
        assert orq.config['max_tentativas'] == 5
        assert orq.config['usar_memoria_evolutiva'] is True
        assert orq.config['salvar_backup'] is False
    
    @pytest.mark.asyncio
    async def test_timeout_operacao(self, orquestrador, temp_dir):
        """Testa timeout de operações"""
        arquivo_teste = os.path.join(temp_dir, 'test.py')
        with open(arquivo_teste, 'w') as f:
            f.write('print("test")')
        
        # Mock que simula timeout
        with patch.object(orquestrador.corretor, 'corrigir_arquivo') as mock_corretor:
            mock_corretor.side_effect = asyncio.TimeoutError("Operação demorou muito")
            
            resultado = await orquestrador.executar_missao_reparo(arquivo_teste)
            
            assert resultado['sucesso'] is False
            assert 'timeout' in resultado['erro'].lower() or 'demorou' in resultado['erro'].lower()
    
    def test_estatisticas_iniciais(self, orquestrador):
        """Testa se estatísticas são inicializadas corretamente"""
        assert orquestrador.estatisticas['total_reparos'] == 0
        assert orquestrador.estatisticas['reparos_sucesso'] == 0
        assert orquestrador.estatisticas['taxa_sucesso'] == 0.0
        assert orquestrador.estatisticas['tempo_total'] == 0.0
        assert isinstance(orquestrador.estatisticas['historico_operacoes'], list)
    
    @pytest.mark.asyncio
    async def test_memoria_evolutiva_learning(self, orquestrador, temp_dir):
        """Testa aprendizado evolutivo através da memória"""
        arquivo_teste = os.path.join(temp_dir, 'learning_test.py')
        with open(arquivo_teste, 'w') as f:
            f.write('def func():\nprint "hello"')  # Erro de indentação + sintaxe
        
        # Mock dos resultados
        resultado_correcao = ResultadoCorrecao(
            arquivo=arquivo_teste,
            sucesso=True,
            alteracoes_realizadas=['Corrigida indentação', 'Convertido para Python 3'],
            erros_corrigidos=['IndentationError', 'SyntaxError'],
            erros_persistentes=[],
            codigo_antes='def func():\nprint "hello"',
            codigo_depois='def func():\n    print("hello")',
            tempo_processamento=0.8,
            metadados={'complexity': 'medium'}
        )
        
        with patch.object(orquestrador.corretor, 'corrigir_arquivo') as mock_corretor:
            mock_corretor.return_value = resultado_correcao
            
            with patch.object(orquestrador.memoria, 'registrar_reparo') as mock_memoria:
                mock_memoria.return_value = True
                
                # Executa reparo
                resultado = await orquestrador.executar_missao_reparo(arquivo_teste)
                
                # Verifica se aprendizado foi registrado
                assert resultado['sucesso'] is True
                assert mock_memoria.called
                
                # Verifica se registro foi criado corretamente
                args, kwargs = mock_memoria.call_args
                registro = args[0]
                assert registro.sucesso is True
                assert len(registro.erros_corrigidos) == 2
                assert 'IndentationError' in registro.erros_corrigidos


class TestIntegracaoComponentes:
    """Testa integração entre diferentes componentes"""
    
    @pytest.fixture
    def sistema_completo(self, tmp_path):
        """Setup de sistema completo para testes de integração"""
        return OrquestradorUnificado(diretorio_projeto=str(tmp_path))
    
    @pytest.mark.asyncio
    async def test_pipeline_completo_reparo(self, sistema_completo, tmp_path):
        """Testa pipeline completo: diagnóstico -> reparo -> memória"""
        # Cria arquivo com problemas
        arquivo_problema = tmp_path / "problema.py"
        arquivo_problema.write_text("""
import os
import sys

def funcao_mal_escrita(  ):
    x=1+1
    print x
    return x
""")
        
        # Mock dos componentes para simular pipeline
        with patch.multiple(
            sistema_completo,
            diagnostico=Mock(),
            corretor=Mock(), 
            memoria=Mock(),
            fallback_llm=Mock()
        ):
            # Configura mocks
            sistema_completo.diagnostico.executar_diagnostico_completo.return_value = {
                'sucesso': False,
                'problemas_encontrados': ['SyntaxError na linha 7'],
                'recomendacoes': ['Corrigir sintaxe Python 2 para 3']
            }
            
            sistema_completo.corretor.corrigir_arquivo.return_value = ResultadoCorrecao(
                arquivo=str(arquivo_problema),
                sucesso=True,
                alteracoes_realizadas=['Corrigida sintaxe print', 'Formatação melhorada'],
                erros_corrigidos=['SyntaxError'],
                erros_persistentes=[],
                codigo_antes=arquivo_problema.read_text(),
                codigo_depois="import os\nimport sys\n\ndef funcao_mal_escrita():\n    x = 1 + 1\n    print(x)\n    return x\n",
                tempo_processamento=1.5,
                metadados={'tipo': 'syntax_fix'}
            )
            
            sistema_completo.memoria.registrar_reparo.return_value = True
            
            # Executa pipeline
            diag_result = await sistema_completo.executar_diagnostico()
            repair_result = await sistema_completo.executar_missao_reparo(str(arquivo_problema))
            
            # Verificações
            assert diag_result['sucesso'] is False
            assert len(diag_result['problemas_encontrados']) > 0
            
            assert repair_result['sucesso'] is True
            assert len(repair_result['resultado_correcao'].alteracoes_realizadas) > 0
            
            # Verifica chamadas
            sistema_completo.diagnostico.executar_diagnostico_completo.assert_called_once()
            sistema_completo.corretor.corrigir_arquivo.assert_called_once()
            sistema_completo.memoria.registrar_reparo.assert_called_once()


# Configuração de pytest para testes async
@pytest.fixture(scope="session")
def event_loop():
    """Cria event loop para testes assíncronos"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    # Permite execução direta dos testes
    pytest.main([__file__, "-v"])