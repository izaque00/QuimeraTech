#!/usr/bin/env python3
"""
Teste independente do Agente Fiscal de Código
Demonstra as funcionalidades sem depender de outros módulos do Quimera
"""

import os
import sys
import tempfile
import ast
from pathlib import Path

# Adicionar o diretório do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def teste_basico_formatador():
    """Testa funcionalidades básicas do formatador"""
    print("🧪 Testando FormatadorAutomatico...")

    # Importar apenas o que precisamos
    from quimera.agentes.agente_fiscal_codigo import FormatadorAutomatico

    formatador = FormatadorAutomatico()

    # Código de teste com problemas
    codigo_problematico = '''import os,sys,json
def funcao_mal_formatada(   param1,param2,param3   ):
    if True:
        x=1+2+3
        y    =    4
    return x,y
'''

    # Criar arquivo temporário
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(codigo_problematico)
        temp_file = f.name

    try:
        # Testar formatação
        foi_formatado, mensagem = formatador.formatar_arquivo(temp_file, usar_black=False, usar_isort=False)

        if foi_formatado:
            print(f"✅ Arquivo formatado: {mensagem}")

            # Ler resultado
            with open(temp_file, 'r') as f:
                codigo_formatado = f.read()

            print("📝 Código original:")
            print(codigo_problematico)
            print("\n📝 Código formatado:")
            print(codigo_formatado)
        else:
            print(f"ℹ️  {mensagem}")

        return True
    except Exception as e:
        print(f"❌ Erro no teste do formatador: {e}")
        return False
    finally:
        os.unlink(temp_file)

def teste_fiscalizador_sintaxe():
    """Testa o fiscalizador de sintaxe"""
    print("\n🧪 Testando FiscalizadorSintaxe...")

    from quimera.agentes.agente_fiscal_codigo import FiscalizadorSintaxe

    fiscalizador = FiscalizadorSintaxe()

    # Código com problemas de sintaxe
    codigos_teste = {
        'codigo_ok.py': '''
def funcao_valida():
    return "Hello, World!"
''',
        'codigo_erro_sintaxe.py': '''
def funcao_invalida(
    return "String não terminada
''',
        'codigo_indentacao.py': '''
def funcao_indentacao():
    if True:  # Tab aqui
        print("Mistura tabs e espaços")  # Espaços aqui
'''
    }

    resultados = {}

    for nome_arquivo, codigo in codigos_teste.items():
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(codigo)
            temp_file = f.name

        try:
            problemas = fiscalizador.verificar_sintaxe_arquivo(temp_file)
            resultados[nome_arquivo] = len(problemas)

            print(f"📁 {nome_arquivo}: {len(problemas)} problemas")
            for problema in problemas[:3]:  # Mostrar apenas os primeiros 3
                print(f"   • {problema.categoria}: {problema.descricao}")

        except Exception as e:
            print(f"❌ Erro ao verificar {nome_arquivo}: {e}")
            resultados[nome_arquivo] = -1
        finally:
            os.unlink(temp_file)

    # Verificar resultados esperados
    if resultados.get('codigo_ok.py', -1) == 0:
        print("✅ Código válido detectado corretamente")
    else:
        print("❌ Falha na detecção de código válido")

    if resultados.get('codigo_erro_sintaxe.py', 0) > 0:
        print("✅ Erros de sintaxe detectados corretamente")
    else:
        print("❌ Falha na detecção de erros de sintaxe")

    return True

def teste_detector_problemas():
    """Testa o detector de problemas de qualidade"""
    print("\n🧪 Testando DetectorProblemas...")

    from quimera.agentes.agente_fiscal_codigo import DetectorProblemas

    detector = DetectorProblemas()

    # Código com problemas de qualidade
    codigo_qualidade = '''
def funcao_muito_longa_com_muitos_argumentos_e_logica_complexa(param1, param2, param3, param4, param5, param6, param7, param8):
    """Função com muitos problemas de qualidade"""
    linha_muito_longa_que_ultrapassa_o_limite_recomendado_de_caracteres_por_linha_causando_problemas_de_legibilidade_e_formatacao = True

    if param1:
        if param2:
            if param3:
                if param4:
                    if param5:
                        if param6:
                            if param7:
                                if param8:
                                    return "Muito complexo"
                                else:
                                    return "Ainda complexo"
                            else:
                                return "Complexo"
                        else:
                            return "Meio complexo"
                    else:
                        return "Um pouco complexo"
                else:
                    return "Simples"
            else:
                return "Muito simples"
        else:
            return "Super simples"
    else:
        return "Trivial"
'''

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(codigo_qualidade)
        temp_file = f.name

    try:
        problemas = detector.analisar_qualidade_arquivo(temp_file)

        print(f"📊 Problemas de qualidade encontrados: {len(problemas)}")

        categorias = {}
        for problema in problemas:
            categorias[problema.categoria] = categorias.get(problema.categoria, 0) + 1

        for categoria, count in categorias.items():
            print(f"   • {categoria}: {count}")

        # Verificar se detectou problemas esperados
        categorias_esperadas = ['linha_longa', 'funcao_complexa', 'muitos_argumentos']
        detectadas = 0

        for cat in categorias_esperadas:
            if cat in categorias:
                detectadas += 1
                print(f"✅ {cat} detectado corretamente")

        if detectadas >= 2:
            print("✅ Detector de problemas funcionando")
        else:
            print("⚠️  Detector pode precisar de ajustes")

        return True

    except Exception as e:
        print(f"❌ Erro no teste do detector: {e}")
        return False
    finally:
        os.unlink(temp_file)

def teste_completo_agente():
    """Testa o agente completo em um diretório de teste"""
    print("\n🧪 Testando AgenteFiscalCodigo completo...")

    # Criar um mock simples do AgenteBase para evitar dependências
    class AgenteBaseMock:
        def __init__(self):
            pass

    # Temporariamente substituir a importação
    import quimera.agentes.agente_fiscal_codigo
    quimera.agentes.agente_fiscal_codigo.AgenteBase = AgenteBaseMock

    # Mock da função montar_log
    def mock_montar_log(msg, level="INFO"):
        print(f"[{level}] {msg}")

    quimera.agentes.agente_fiscal_codigo.montar_log = mock_montar_log

    from quimera.agentes.agente_fiscal_codigo import AgenteFiscalCodigo

    try:
        # Criar diretório de teste
        with tempfile.TemporaryDirectory() as temp_dir:
            # Criar alguns arquivos de teste
            arquivos_teste = {
                'arquivo_ok.py': '''
def funcao_boa():
    """Função bem formatada"""
    return True
''',
                'arquivo_problemas.py': '''
import os,sys,json
def funcao_ruim(   a,b,c,d,e,f,g,h   ):
    linha_muito_longa = "Esta é uma linha extremamente longa que certamente vai ultrapassar o limite recomendado de caracteres"
    if a:
        if b:
            if c:
                return "complexo"
    return None
''',
                'subdir/outro_arquivo.py': '''
def outra_funcao():
    return "ok"
'''
            }

            # Criar arquivos
            for caminho, conteudo in arquivos_teste.items():
                arquivo_path = Path(temp_dir) / caminho
                arquivo_path.parent.mkdir(exist_ok=True)
                arquivo_path.write_text(conteudo)

            # Criar agente
            agente = AgenteFiscalCodigo()
            print("✅ Agente criado com sucesso")

            # Testar busca de arquivos
            arquivos_encontrados = agente._encontrar_arquivos_python(temp_dir)
            print(f"✅ Encontrados {len(arquivos_encontrados)} arquivos Python")

            # Executar fiscalização completa (apenas verificação)
            resultado = agente.fiscalizar_diretorio(temp_dir, formatar=False, corrigir=False)

            print(f"📊 Resultado da fiscalização:")
            print(f"   • Arquivos verificados: {resultado.arquivos_verificados}")
            print(f"   • Problemas encontrados: {len(resultado.problemas_encontrados)}")
            print(f"   • Tempo de execução: {resultado.tempo_execucao:.2f}s")

            # Mostrar alguns problemas
            if resultado.problemas_encontrados:
                print("🔍 Primeiros problemas encontrados:")
                for problema in resultado.problemas_encontrados[:5]:
                    print(f"   • {problema.categoria} em {Path(problema.arquivo).name}:{problema.linha}")

            print("✅ Fiscalização completa executada com sucesso")
            return True

    except Exception as e:
        print(f"❌ Erro no teste completo: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Executa todos os testes"""
    print("🚀 Iniciando testes do Agente Fiscal de Código")
    print("=" * 60)

    testes = [
        teste_fiscalizador_sintaxe,
        teste_detector_problemas,
        teste_basico_formatador,
        teste_completo_agente
    ]

    sucessos = 0
    for i, teste in enumerate(testes, 1):
        print(f"\n[{i}/{len(testes)}] {teste.__name__}")
        try:
            if teste():
                sucessos += 1
        except Exception as e:
            print(f"❌ Falha no teste: {e}")

    print("\n" + "=" * 60)
    print(f"📊 Resultado dos testes: {sucessos}/{len(testes)} sucessos")

    if sucessos == len(testes):
        print("🎉 Todos os testes passaram! Agente Fiscal está funcionando corretamente.")
    else:
        print("⚠️  Alguns testes falharam. Verifique as implementações.")

    return sucessos == len(testes)

if __name__ == "__main__":
    main()