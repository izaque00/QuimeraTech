"""
Testes dos Agentes — Registry, base, e agentes individuais.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


class TestAgentRegistry:
    """Testes do AgentRegistry."""
    
    def test_registry_has_agents(self):
        from quimera.mind.agent_registry import AgentRegistry
        
        count = AgentRegistry.count()
        assert count > 0, "AgentRegistry deve ter agentes registrados"
        assert count >= 28, f"Esperado >= 28, tem {count}"
    
    def test_registry_get_handler(self):
        from quimera.mind.agent_registry import AgentRegistry
        
        handler = AgentRegistry.get_handler("AgenteFiscalCodigo")
        assert handler is not None
        assert isinstance(handler, str)
    
    def test_registry_get_handler_unknown(self):
        from quimera.mind.agent_registry import AgentRegistry
        
        handler = AgentRegistry.get_handler("AgenteQueNaoExiste")
        assert handler is None
    
    def test_registry_get_horizon(self):
        from quimera.mind.agent_registry import AgentRegistry
        
        horizon = AgentRegistry.get_horizon("AgenteFiscalCodigo")
        assert horizon == "H4"
    
    def test_registry_list_agents(self):
        from quimera.mind.agent_registry import AgentRegistry
        
        agents = AgentRegistry.list_agents()
        assert isinstance(agents, list)
        assert len(agents) > 0
        
        # Cada agente deve ter os campos esperados
        first = agents[0]
        assert 'name' in first
        assert 'handler' in first
        assert 'horizon' in first
        assert 'description' in first
    
    def test_all_agents_have_valid_horizon(self):
        from quimera.mind.agent_registry import AgentRegistry
        
        agents = AgentRegistry.list_agents()
        for agent in agents:
            horizon = agent['horizon']
            assert horizon in ['H1', 'H2', 'H3', 'H4', 'H5', 'H6', '?'], \
                f"Agente {agent['name']} tem horizon inválido: {horizon}"


class TestAgenteBase:
    """Testes do AgenteBase."""
    
    def test_base_agent_import(self):
        """AgenteBase deve importar (NameError corrigido na Fase 2)."""
        from quimera.agentes.agente_base import AgenteBase
        assert AgenteBase is not None


class TestAgenteFiscal:
    """Testes do AgenteFiscalCodigo."""
    
    def test_agente_fiscal_import(self):
        from quimera.agentes.agente_fiscal_codigo import AgenteFiscalCodigo
        assert AgenteFiscalCodigo is not None


class TestSelfHealing:
    """Testes do SelfHealing loop (syntax bug corrigido na Fase 1)."""
    
    def test_self_healing_import(self):
        """SelfHealingLoop deve importar sem SyntaxError."""
        from quimera.agentes.self_healing_loop import SelfHealingLoop
        assert SelfHealingLoop is not None


class TestAgenteTransformador:
    """Testes do agente_transformador (NameError Pipeline corrigido)."""
    
    def test_transformador_import(self):
        """Deve importar sem NameError (Pipeline com fallback)."""
        from quimera.agentes.agente_transformador import NeuralCodeReconstructor
        assert NeuralCodeReconstructor is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
