# quimera/testes/test_agente.py
import asyncio
import pytest
import os
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch # Para simular comportamentos assíncronos

# Importações dos seus módulos internos
from quimera.agentes.agente_analista import EngenheiroDebug
from quimera.agentes.agente_gerador import AgenteGerador
from quimera.agentes.agente_critico import AgenteCritico
from quimera.quadro_negro import QuadroNegro
from quimera.agentes.roteador_modelos import selecionar_agentes_para_tarefa, obter_cliente_llm # Mockar essas funções
from quimera.utils.general import write_code, get_code
from quimera.utils.kernel_utils import create_kernel_backup, restore_kernel_state # Para gerenciar estado do kernel para testes

# Configuração de logging para testes
import logging
logger = logging.getLogger("TesteAgente")
logger.setLevel(logging.INFO) # Nível de log INFO para testes
# Desabilita logs muito verbosos de libs externas durante os testes
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('redis').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)


# --- Fixtures para Testes ---
@pytest.fixture
def quadro_negro_limpo():
    """Fixture que retorna uma instância limpa do Quadro Negro para cada teste."""
    qn = QuadroNegro()
    qn.limpar_quadro() # Garante que o quadro está vazio
    return qn

@pytest.fixture
def mock_llm_cliente():
    """Fixture que retorna um mock assíncrono para o cliente LLM."""
    mock = AsyncMock()
    mock.invoke.return_value.content = "Análise mock da causa raiz." # Padrão para Analista
    return mock

@pytest.fixture
def mock_roteador_modelos(mock_llm_cliente):
    """Fixture que simula as funções de roteamento de modelos."""
    with patch('quimera.agentes.roteador_modelos.selecionar_agentes_para_tarefa') as mock_selecionar, \
         patch('quimera.agentes.roteador_modelos.obter_cliente_llm') as mock_obter_cliente:

        mock_selecionar.return_value = ["mock_modelo_llm"] # Retorna um modelo mock
        mock_obter_cliente.return_value = mock_llm_cliente # Retorna o cliente mock

        yield # Permite que o teste execute
        # Limpeza após o teste (opcional, pois mocks são isolados por padrão)

@pytest.fixture
def kernel_test_env(tmp_path):
    """
    Cria um ambiente de kernel simulado para testes, incluindo um diretório de kernel e um de build.
    `tmp_path` é uma fixture do pytest para diretórios temporários.
    """
    test_kernel_root = tmp_path / "test_kernel"
    test_build_dir = test_kernel_root / "quimera_build"

    # Cria a estrutura mínima de um repositório Git e um Makefile
    test_kernel_root.mkdir()
    (test_kernel_root / ".git").mkdir()
    (test_kernel_root / "Makefile").write_text("all:\n\t@echo 'Kernel make done.'")

    # Mock de um arquivo de código para análise
    (test_kernel_root / "drivers" / "char").mkdir(parents=True)
    (test_kernel_root / "drivers" / "char" / "my_driver.c").write_text("int main() { /* mock code */ return 0; }")

    test_build_dir.mkdir()

    # Define KERNEL_ROOT no ambiente para os utilitários
    os.environ["KERNEL_ROOT"] = str(test_kernel_root)

    yield str(test_kernel_root), str(test_build_dir)

    # Limpeza é feita automaticamente pelo tmp_path, mas pode ser explícita
    # shutil.rmtree(test_kernel_root)


# --- Testes para Agente Analista (EngenheiroDebug) ---
@pytest.mark.asyncio
async def test_engenheiro_debug_executar_analise(quadro_negro_limpo, mock_roteador_modelos):
    """Testa a execução do Agente Analista (EngenheiroDebug)."""
    agente_analista = EngenheiroDebug(quadro_negro_limpo)

    log_erro_mock = "Erro de compilação: undefined reference to 'func_teste' na linha 123."

    # Configura o mock LLM para retornar um JSON válido
    mock_roteador_modelos[1].invoke.return_value.content = json.dumps({
        "causa_raiz": "Referência indefinida a func_teste.",
        "modulo_afetado": "arquivo.c",
        "implicacoes_secundarias": ["linkagem", "bibliotecas"],
        "estrategia_correcao": "Adicionar biblioteca ou implementar func_teste.",
        "historico_problemas_semelhantes": "N/A"
    })

    resultado = await agente_analista.executar_analise(log_erro_mock)

    assert resultado["confiavel"] is True
    assert "causa_raiz" in resultado["resultado"]

    artefato = quadro_negro_limpo.obter_artefato("analise_tecnica_causa_raiz")
    assert artefato is not None
    assert artefato["conteudo"]["causa_raiz"] == "Referência indefinida a func_teste."

@pytest.mark.asyncio
async def test_engenheiro_debug_busca_correlatas(quadro_negro_limpo, mock_roteador_modelos, kernel_test_env):
    """Testa a função de busca correlata com ambiente de kernel mockado."""
    agente_analista = EngenheiroDebug(quadro_negro_limpo)

    kernel_root, _ = kernel_test_env

    # Mock do subprocess.run para git log (evita chamada real ao Git)
    with patch('subprocess.run') as mock_sub_run:
        mock_sub_run.return_value = MagicMock(
            returncode=0,
            stdout="commit abcdef123\nAutor: Teste\n\nCommit de teste.\n",
            stderr=""
        )

        buscas = agente_analista._buscas_correlatas("drivers/char/my_driver.c", kernel_root)

        assert len(buscas) > 0
        assert "Commit de teste." in buscas[0]

        # Verifica se o subprocess.run foi chamado com os argumentos corretos
        mock_sub_run.assert_called_once()
        assert "git -C" in mock_sub_run.call_args[0][0]
        assert "log -p --max-count=5" in mock_sub_run.call_args[0][0]
        assert "drivers/char/my_driver.c" in mock_sub_run.call_args[0][0]


# --- Testes para Agente Gerador ---
@pytest.mark.asyncio
async def test_agente_gerador_executar_geracao(quadro_negro_limpo, mock_roteador_modelos):
    """Testa a execução do Agente Gerador."""
    agente_gerador = AgenteGerador(quadro_negro_limpo, nome_modelo="mock_modelo_gerador")

    # Publica artefatos que o gerador precisa
    quadro_negro_limpo.criar_artefato(
        "analise_tecnica_causa_raiz",
        {"causa_raiz": "Erro XYZ", "modulo_afetado": "foo.c", "estrategia_correcao": "patchar"},
        "EngenheiroDebug"
    )
    quadro_negro_limpo.criar_artefato("Log_Compilacao_Erro", "Log de erro aqui.", "Sistema")

    # Configura o mock LLM para retornar um patch
    mock_roteador_modelos[1].invoke.return_value.content = "```diff\n--- a/foo.c\n+++ b/foo.c\n@@ -1 +1,2 @@\n+novo_codigo()\n```"

    patch_gerado = await agente_gerador.executar_geracao()

    assert patch_gerado is not None
    assert "novo_codigo()" in patch_gerado

    artefato_patch = quadro_negro_limpo.obter_artefato("solucao_bruta_mock_modelo_gerador")
    assert artefato_patch is not None
    assert "novo_codigo()" in artefato_patch["conteudo"]


# --- Testes para Agente Critico ---
@pytest.mark.asyncio
async def test_agente_critico_executar_analise_llm(quadro_negro_limpo, mock_roteador_modelos):
    """Testa a análise de lógica do Agente Crítico via LLM."""
    agente_critico = AgenteCritico(quadro_negro_limpo)

    # Configura o mock LLM para retornar um JSON de avaliação
    mock_roteador_modelos[1].invoke.return_value.content = json.dumps({
        "score": 0.9,
        "ponto_fraco": "N/A",
        "recomenda_correcao": "Usar async/await em I/O.",
        "justificativa_detalhada": "Código limpo e eficiente."
    })

    patch_mock = "print('Hello')"
    resultado_analise = await agente_critico.executar_analise_llm(patch_mock)

    assert resultado_analise["score"] == 0.9
    assert resultado_analise["ponto_fraco"] == "N/A"

@pytest.mark.asyncio
async def test_agente_critico_validar_aplicabilidade_patch(quadro_negro_limpo, kernel_test_env):
    """Testa a validação de aplicabilidade de patch (dry-run)."""
    agente_critico = AgenteCheckLinux(quadro_negro_limpo)
    kernel_root, _ = kernel_test_env

    # Simula um arquivo para o patch ser aplicado (no diretório temporário do kernel)
    (Path(kernel_root) / "test_file.c").write_text("int main() { return 0; }")

    patch_conteudo_valido = "--- a/test_file.c\n+++ b/test_file.c\n@@ -1 +1,2 @@\n int main() { return 0; }\n+void new_func() {}"

    # Mock do subprocess.run para patch --dry-run
    with patch('subprocess.run') as mock_sub_run:
        # Configura o mock para simular um patch que aplica com sucesso
        mock_sub_run.return_value = MagicMock(returncode=0, stdout="Patch applied.", stderr="")

        resultado = agente_critico.validar_aplicabilidade_patch(patch_conteudo_valido)

        assert resultado["valido"] is True
        assert resultado["score"] == 1.0

        # Testar um patch que falha (simulando um erro no subprocess)
        mock_sub_run.return_value = MagicMock(returncode=1, stdout="", stderr="Patch failed.")
        resultado_falha = agente_critico.validar_aplicabilidade_patch("patch_invalido_qualquer")
        assert resultado_falha["valido"] is False
        assert resultado_falha["score"] == 0.2

@pytest.mark.asyncio
async def test_agente_critico_analise_estilo_e_seguranca_mock(quadro_negro_limpo, kernel_test_env):
    """Testa a análise de estilo e segurança (mockada)."""
    agente_critico = AgenteCheckLinux(quadro_negro_limpo)
    kernel_root, _ = kernel_test_env

    # Cria um arquivo mock para o linter.py poder ler
    test_file_path = Path(kernel_root) / "mock_code_for_lint.py"
    test_file_path.write_text("def my_func():\n    x=1 # Bad style\n    print('Hello')\n")

    patch_conteudo_mock = "print('Hello world')"
    resultado = agente_critico.analise_estilo_e_seguranca_mock(patch_conteudo_mock, str(test_file_path))

    assert resultado["score"] >= 0.0 # O score deve ser calculado (não mais fixo)
    assert "Simulado" in resultado["justificativa_simulada"]

# --- Testes para Agente Sintetizador ---
@pytest.mark.asyncio
async def test_agente_sintetizador_mesclar_solucoes(quadro_negro_limpo, mock_roteador_modelos):
    """Testa a fusão de soluções pelo Agente Sintetizador."""
    agente_sintetizador = AstMergeEngine(quadro_negro_limpo)

    patches_brutos_mock = {
        "modelo1": "--- a/file.c\n+++ b/file.c\n@@ -1 +1,2 @@\n+// Patch 1",
        "modelo2": "--- a/file.c\n+++ b/file.c\n@@ -1 +1,2 @@\n+// Patch 2",
    }

    # Configura o mock LLM para retornar uma solução sintetizada
    mock_roteador_modelos[1].invoke.return_value.content = "```diff\n--- a/file.c\n+++ b/file.c\n@@ -1 +1,2 @@\n+// Patch Sintetizado Final\n```"

    solucao_final = await agente_sintetizador.mesclar_solucoes(patches_brutos_mock)

    assert solucao_final is not None
    assert "Patch Sintetizado Final" in solucao_final

# --- Testes para Agente Mestra ---
@pytest.mark.asyncio
async def test_agente_mestra_executar_julgamento_final(quadro_negro_limpo, mock_roteador_modelos):
    """Testa o julgamento final do Agente Mestra."""
    agente_mestra = AgenteMestra(quadro_negro_limpo)

    patches_campeoes_mock = [
        "--- patch1 ---",
        "--- patch2 ---",
        "--- patch3 ---"
    ]

    # Configura o mock LLM para votar no PATCH 2
    mock_roteador_modelos[1].invoke.return_value.content = "PATCH 2"

    vencedor = await agente_mestra.executar_julgamento_final(patches_campeoes_mock)

    assert vencedor == "--- patch2 ---"