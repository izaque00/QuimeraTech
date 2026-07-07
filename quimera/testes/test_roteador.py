# quimera/testes/test_roteador.py
import pytest
import os
from unittest.mock import MagicMock, patch

# Importações dos seus módulos internos
from quimera.agentes.roteador_modelos import selecionar_agentes_para_tarefa, obter_cliente_llm, AGENTES_DISPONIVEIS

# Configuração de logging para testes
import logging
logger = logging.getLogger("TesteRoteador")
logger.setLevel(logging.INFO) # Nível de log INFO para testes
# Desabilita logs muito verbosos de libs externas durante os testes
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('redis').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)


# --- Fixtures para Testes (configura variáveis de ambiente mock) ---
@pytest.fixture
def mock_env_vars():
    """Configura variáveis de ambiente mock para chaves de API."""
    with patch.dict(os.environ, {
        "HF_API_TOKEN": "mock_hf_token",
        "GROQ_API_KEY": "mock_groq_key",
        "GOOGLE_API_KEY": "mock_google_key",
        "FIREWORKS_API_KEY": "mock_fireworks_key"
    }):
        yield

# --- Testes para selecionar_agentes_para_tarefa ---
def test_selecionar_agentes_para_tarefa_sucesso(mock_env_vars):
    """Testa a seleção de agentes para uma tarefa específica com sucesso."""

    # Mock do AGENTES_DISPONIVEIS para garantir controle no teste
    agentes_mock_data = {
        "Modelo_A": {"provedor": "mock_hf", "habilidades": ["geracao_patch_brainstorm", "analise"], "prioridade": 10},
        "Modelo_B": {"provedor": "mock_groq", "habilidades": ["geracao_patch_elite"], "prioridade": 9},
        "Modelo_C": {"provedor": "mock_google", "habilidades": ["analise"], "prioridade": 11},
        "Modelo_D": {"provedor": "mock_hf", "habilidades": ["nenhuma"], "prioridade": 8},
    }

    with patch('quimera.agentes.roteador_modelos.AGENTES_DISPONIVEIS', agentes_mock_data):
        # Teste 1: Selecionar 1 agente para "analise" (deve ser Modelo_C por prioridade)
        selecao1 = selecionar_agentes_para_tarefa("analise", quantidade=1)
        assert len(selecao1) == 1
        assert selecao1[0] == "Modelo_C"

        # Teste 2: Selecionar 2 agentes para "geracao_patch_brainstorm"
        selecao2 = selecionar_agentes_para_tarefa("geracao_patch_brainstorm", quantidade=2)
        assert len(selecao2) == 1 # Apenas Modelo_A tem essa habilidade
        assert selecao2[0] == "Modelo_A"

        # Teste 3: Selecionar 3 agentes para "analise" (ordem por prioridade)
        selecao3 = selecionar_agentes_para_tarefa("analise", quantidade=3)
        assert len(selecao3) == 2 # Apenas Modelo_A e Modelo_C tem essa habilidade
        assert selecao3[0] == "Modelo_C" # Maior prioridade
        assert selecao3[1] == "Modelo_A"

def test_selecionar_agentes_para_tarefa_sem_candidatos(mock_env_vars):
    """Testa a seleção quando não há candidatos para a tarefa."""
    agentes_mock_data = {
        "Modelo_A": {"provedor": "mock_hf", "habilidades": ["geracao"], "prioridade": 10},
    }
    with patch('quimera.agentes.roteador_modelos.AGENTES_DISPONIVEIS', agentes_mock_data):
        selecao = selecionar_agentes_para_tarefa("analise", quantidade=1)
        assert len(selecao) == 0

def test_selecionar_agentes_para_tarefa_excluidos(mock_env_vars):
    """Testa a seleção excluindo modelos específicos."""
    agentes_mock_data = {
        "Modelo_A": {"provedor": "mock_hf", "habilidades": ["analise"], "prioridade": 10},
        "Modelo_B": {"provedor": "mock_groq", "habilidades": ["analise"], "prioridade": 9},
    }
    with patch('quimera.agentes.roteador_modelos.AGENTES_DISPONIVEIS', agentes_mock_data):
        selecao = selecionar_agentes_para_tarefa("analise", quantidade=2, modelos_excluidos=["Modelo_A"])
        assert len(selecao) == 1
        assert selecao[0] == "Modelo_B"

# --- Testes para obter_cliente_llm ---
def test_obter_cliente_llm_huggingface(mock_env_vars):
    """Testa a obtenção de cliente LLM para Hugging Face Space."""
    with patch('quimera.agentes.roteador_modelos.AGENTES_DISPONIVEIS', {"HF_Model": {"provedor": "huggingface_space", "url_base": "https://mock.hf.space"}}), \
         patch('quimera.agentes.roteador_modelos.ChatOpenAI') as mock_chat_openai: # Mocka ChatOpenAI que é a base do Proxy

        cliente = obter_cliente_llm("HF_Model")

        mock_chat_openai.assert_called_once_with(
            model_name="HF_Model",
            base_url="https://mock.hf.space/v1",
            api_key="mock_hf_token",
            temperature=0.4,
            max_tokens=1024
        )
        assert cliente is not None

def test_obter_cliente_llm_groq(mock_env_vars):
    """Testa a obtenção de cliente LLM para Groq."""
    with patch('quimera.agentes.roteador_modelos.AGENTES_DISPONIVEIS', {"Groq_Model": {"provedor": "groq"}}), \
         patch('quimera.agentes.roteador_modelos.ChatGroq') as mock_chat_groq:

        cliente = obter_cliente_llm("Groq_Model")

        mock_chat_groq.assert_called_once_with(
            model_name="Groq_Model",
            temperature=0.4,
            api_key="mock_groq_key"
        )
        assert cliente is not None

def test_obter_cliente_llm_gemini(mock_env_vars):
    """Testa a obtenção de cliente LLM para Gemini."""
    with patch('quimera.agentes.roteador_modelos.AGENTES_DISPONIVEIS', {"Gemini_Model": {"provedor": "gemini"}}), \
         patch('quimera.agentes.roteador_modelos.ChatGoogleGenerativeAI') as mock_chat_gemini:

        cliente = obter_cliente_llm("Gemini_Model")

        mock_chat_gemini.assert_called_once_with(
            model="Gemini_Model",
            temperature=0.4,
            google_api_key="mock_google_key"
        )
        assert cliente is not None

def test_obter_cliente_llm_inexistente(mock_env_vars):
    """Testa a falha ao obter cliente LLM para um modelo inexistente."""
    with patch('quimera.agentes.roteador_modelos.AGENTES_DISPONIVEIS', {}):
        with pytest.raises(ValueError, match="Agente desconhecido: 'Modelo_Inexistente'"):
            obter_cliente_llm("Modelo_Inexistente")

def test_obter_cliente_llm_provedor_desconhecido(mock_env_vars):
    """Testa a falha ao obter cliente LLM para um provedor desconhecido."""
    with patch('quimera.agentes.roteador_modelos.AGENTES_DISPONIVEIS', {"Bad_Model": {"provedor": "unknown_provider"}}):
        cliente = obter_cliente_llm("Bad_Model")
        assert cliente is None # A função loga erro e retorna None