"""
Testes para CorretorUnificado
Valida correções sintáticas, imports, dependências e estruturais
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch

import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from utils.corretor_unificado import CorretorUnificado, ResultadoCorrecao, TipoErro


class TestCorretorUnificado:
    """Testes do corretor unificado"""
    
    @pytest.fixture
    def corretor(self):
        """Cria instância do corretor para teste"""
        return CorretorUnificado()
    
    @pytest.fixture
    def temp_file(self):
        """Cria arquivo temporário para testes"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            yield f.name
        os.unlink(f.name)
    
    def test_inicializacao_basica(self, corretor):
        """Testa inicialização básica do corretor"""
        assert corretor is not None
        assert corretor.max_tentativas == 3
        assert corretor.backup_arquivos is True
        assert isinstance(corretor.padroes_correcao, dict)
        assert TipoErro.SINTAXE in corretor.padroes_correcao
    
    def test_configuracao_personalizada(self):
        """Testa corretor com configuração personalizada"""
        config = {
            'max_tentativas': 5,
            'backup_arquivos': False,
            'modo_agressivo': True
        }
        
        corretor = CorretorUnificado(config)
        
        assert corretor.max_tentativas == 5
        assert corretor.backup_arquivos is False
        assert corretor.modo_agressivo is True
    
    def test_correcao_sintaxe_python2_para_3(self, corretor, temp_file):
        """Testa correção de sintaxe Python 2 para Python 3"""
        codigo_python2 = '''
print "hello world"
x = raw_input("Digite algo: ")
print x
'''
        
        with open(temp_file, 'w') as f:
            f.write(codigo_python2)
        
        resultado = corretor.corrigir_arquivo(temp_file)
        
        assert resultado.sucesso is True
        assert len(resultado.alteracoes_realizadas) > 0
        
        # Verifica se código foi atualizado
        with open(temp_file, 'r') as f:
            codigo_corrigido = f.read()
        
        # Deve ter corrigido print statements
        assert 'print(' in codigo_corrigido
        assert 'print "' not in codigo_corrigido
    
    def test_correcao_indentacao(self, corretor, temp_file):
        """Testa correção de problemas de indentação"""
        codigo_mal_indentado = '''
def funcao():
print("hello")
    if True:
print("world")
return True
'''
        
        with open(temp_file, 'w') as f:
            f.write(codigo_mal_indentado)
        
        resultado = corretor.corrigir_arquivo(temp_file)
        
        assert resultado.sucesso is True
        
        # Verifica se indentação foi corrigida
        with open(temp_file, 'r') as f:
            codigo_corrigido = f.read()
        
        linhas = codigo_corrigido.splitlines()
        # Função deve ter indentação correta
        assert any('    print(' in linha for linha in linhas)
    
    def test_correcao_imports_duplicados(self, corretor, temp_file):
        """Testa remoção de imports duplicados"""
        codigo_imports_duplicados = '''
import os
import sys
import os
import json
import sys
from pathlib import Path
import json

def main():
    pass
'''
        
        with open(temp_file, 'w') as f:
            f.write(codigo_imports_duplicados)
        
        resultado = corretor.corrigir_arquivo(temp_file)
        
        assert resultado.sucesso is True
        
        with open(temp_file, 'r') as f:
            codigo_corrigido = f.read()
        
        # Conta ocorrências de imports
        linhas = codigo_corrigido.splitlines()
        import_os_count = sum(1 for linha in linhas if linha.strip() == 'import os')
        import_sys_count = sum(1 for linha in linhas if linha.strip() == 'import sys')
        
        assert import_os_count == 1
        assert import_sys_count == 1
    
    def test_correcao_encoding(self, corretor, temp_file):
        """Testa correção de problemas de encoding"""
        # Código com caracteres problemáticos
        codigo_encoding = 'print("Olá mundo")\n# Comentário com acentuação'
        
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(codigo_encoding)
        
        resultado = corretor.corrigir_arquivo(temp_file)
        
        assert resultado.sucesso is True
        # Deve processar sem erros mesmo com acentos
        assert len(resultado.erros_persistentes) == 0
    
    def test_arquivo_invalido(self, corretor):
        """Testa comportamento com arquivo inválido"""
        arquivo_inexistente = '/caminho/que/nao/existe.py'
        
        resultado = corretor.corrigir_arquivo(arquivo_inexistente)
        
        assert resultado.sucesso is False
        assert len(resultado.erros_persistentes) > 0
        assert 'Erro ao ler arquivo' in resultado.erros_persistentes[0]
    
    def test_codigo_completamente_invalido(self, corretor, temp_file):
        """Testa código que não pode ser corrigido"""
        codigo_invalido = '''
$%@#$%@#$
def $$invalid_syntax%%():
    !!!error!!!
'''
        
        with open(temp_file, 'w') as f:
            f.write(codigo_invalido)
        
        resultado = corretor.corrigir_arquivo(temp_file)
        
        # Pode falhar na validação final
        assert len(resultado.erros_persistentes) > 0
    
    def test_validacao_sintaxe_final(self, corretor, temp_file):
        """Testa validação sintática final"""
        codigo_valido = '''
def hello():
    print("Hello, World!")
    return True

if __name__ == "__main__":
    hello()
'''
        
        with open(temp_file, 'w') as f:
            f.write(codigo_valido)
        
        resultado = corretor.corrigir_arquivo(temp_file)
        
        assert resultado.sucesso is True
        assert len(resultado.erros_persistentes) == 0
    
    def test_backup_arquivo(self, corretor, temp_file):
        """Testa criação de backup"""
        codigo_original = 'print("test")'
        
        with open(temp_file, 'w') as f:
            f.write(codigo_original)
        
        resultado = corretor.corrigir_arquivo(temp_file)
        
        # Verifica se backup foi criado
        backups = [f for f in os.listdir(os.path.dirname(temp_file)) 
                  if f.startswith(os.path.basename(temp_file) + '.backup_')]
        
        assert len(backups) > 0
        
        # Cleanup backup
        for backup in backups:
            os.unlink(os.path.join(os.path.dirname(temp_file), backup))
    
    def test_correcao_diretorio(self, corretor):
        """Testa correção de diretório inteiro"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Cria arquivos Python de teste
            arquivos_teste = []
            for i in range(3):
                arquivo = os.path.join(temp_dir, f'test_{i}.py')
                with open(arquivo, 'w') as f:
                    f.write(f'print "file {i}"')  # Sintaxe Python 2
                arquivos_teste.append(arquivo)
            
            resultados = corretor.corrigir_diretorio(temp_dir)
            
            assert len(resultados) == 3
            assert all(r.sucesso for r in resultados)
            
            # Verifica se todos foram corrigidos
            for arquivo in arquivos_teste:
                with open(arquivo, 'r') as f:
                    conteudo = f.read()
                assert 'print(' in conteudo
    
    def test_relatorio_correcoes(self, corretor, temp_file):
        """Testa geração de relatório de correções"""
        codigo_teste = 'print "hello"'
        
        with open(temp_file, 'w') as f:
            f.write(codigo_teste)
        
        resultado = corretor.corrigir_arquivo(temp_file)
        relatorio = corretor.gerar_relatorio([resultado])
        
        assert 'RELATÓRIO DE CORREÇÕES UNIFICADAS' in relatorio
        assert temp_file in relatorio
        assert 'ESTATÍSTICAS GERAIS' in relatorio
        
        if resultado.sucesso:
            assert 'Sucesso' in relatorio
        else:
            assert 'Erro' in relatorio
    
    def test_padroes_correcao_sintaxe(self, corretor):
        """Testa aplicação de padrões de correção sintática"""
        codigo_com_padroes = '''
x=1+2
if(True):
    print("test");
'''
        
        resultado_etapa = corretor._corrigir_sintaxe_basica(codigo_com_padroes, 'test.py')
        
        assert resultado_etapa['sucesso'] is True
        codigo_corrigido = resultado_etapa['codigo']
        
        # Verifica aplicação de padrões
        assert 'x = 1 + 2' in codigo_corrigido or 'x=1+2' in codigo_corrigido  # Pode ou não aplicar
        assert 'if True:' in codigo_corrigido  # Remove parênteses desnecessários
        assert not codigo_corrigido.endswith(';')  # Remove ponto e vírgula
    
    def test_deteccao_dependencias_faltantes(self, corretor, temp_file):
        """Testa detecção de dependências faltantes"""
        codigo_com_imports = '''
import numpy as np
import pandas as pd
import biblioteca_inexistente
from modulo_nao_existe import funcao

def test():
    return np.array([1, 2, 3])
'''
        
        with open(temp_file, 'w') as f:
            f.write(codigo_com_imports)
        
        resultado = corretor.corrigir_arquivo(temp_file)
        
        # Pode identificar dependências faltantes sem falhar
        assert resultado.sucesso is True or len(resultado.alteracoes_realizadas) > 0
    
    def test_historico_correcoes(self, corretor, temp_file):
        """Testa manutenção do histórico de correções"""
        codigo_teste = 'print("test")'
        
        with open(temp_file, 'w') as f:
            f.write(codigo_teste)
        
        # Executa várias correções
        for _ in range(3):
            corretor.corrigir_arquivo(temp_file)
        
        assert len(corretor.historico_correcoes) == 3
        
        # Verifica estrutura do histórico
        for resultado in corretor.historico_correcoes:
            assert isinstance(resultado, ResultadoCorrecao)
            assert resultado.arquivo == temp_file


class TestTiposErro:
    """Testa categorização de tipos de erro"""
    
    def test_tipos_erro_definidos(self):
        """Verifica se todos os tipos de erro estão definidos"""
        assert hasattr(TipoErro, 'SINTAXE')
        assert hasattr(TipoErro, 'IMPORT')
        assert hasattr(TipoErro, 'DEPENDENCIA')
        assert hasattr(TipoErro, 'INDENTACAO')
        assert hasattr(TipoErro, 'ENCODING')
        assert hasattr(TipoErro, 'ESTRUTURAL')


class TestResultadoCorrecao:
    """Testa estrutura de dados de resultado"""
    
    def test_resultado_correcao_estrutura(self):
        """Testa se ResultadoCorrecao tem todos os campos necessários"""
        resultado = ResultadoCorrecao(
            arquivo='test.py',
            sucesso=True,
            alteracoes_realizadas=['test'],
            erros_corrigidos=['test'],
            erros_persistentes=[],
            codigo_antes='before',
            codigo_depois='after',
            tempo_processamento=1.0,
            metadados={}
        )
        
        assert resultado.arquivo == 'test.py'
        assert resultado.sucesso is True
        assert len(resultado.alteracoes_realizadas) == 1
        assert len(resultado.erros_corrigidos) == 1
        assert len(resultado.erros_persistentes) == 0
        assert resultado.codigo_antes == 'before'
        assert resultado.codigo_depois == 'after'
        assert resultado.tempo_processamento == 1.0
        assert isinstance(resultado.metadados, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])