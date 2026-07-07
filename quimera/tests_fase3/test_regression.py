"""
Testes de Regressão — TODOS os bugs corrigidos nas Fases 1 e 2.
Garante que nenhum bug volte.
"""
import sys
import os
import ast
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


class TestRegressionSyntax:
    """Garante que os 3 syntax errors da Fase 1 não voltem."""
    
    SYNTAX_FILES = [
        'quimera/quimera_aegis_integration.py',
        'quimera/agentes/self_healing_loop.py',
        'quimera/api/worker.py',
    ]
    
    @pytest.mark.parametrize("filepath", SYNTAX_FILES)
    def test_no_syntax_error(self, filepath):
        full = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            filepath
        )
        with open(full) as f:
            source = f.read()
        try:
            ast.parse(source)
        except SyntaxError as e:
            pytest.fail(f"SyntaxError em {filepath}: {e}")


class TestRegressionNameErrors:
    """Garante que os 5 NameErrors da Fase 2 não voltem."""
    
    NAME_ERROR_MODULES = [
        'quimera.agentes.agente_transformador',
        'quimera.agentes.agente_evolutivo_de_codigo',
        'quimera.bibliotecario.biblioteca_alexandria',
        'quimera.integration_backends.clarabel_wrapper',
        'quimera.quimera_fiscal',
    ]
    
    @pytest.mark.parametrize("module", NAME_ERROR_MODULES)
    def test_no_name_error(self, module):
        import importlib
        try:
            importlib.import_module(module)
        except NameError as e:
            pytest.fail(f"NameError em {module}: {e}")


class TestRegressionImports:
    """Garante que imports quebrados da Fase 1 não voltem."""
    
    IMPORT_MODULES = [
        'quimera.cli',
        'quimera.pipeline',
        'quimera.orquestrador_aprimorado',
        'quimera.plugins.plugin_manager',
        'quimera.plugins.base_plugin',
        'quimera.utils.patch_utils',
        'quimera.core.orquestrador_unificado',
        'quimera.core.model_router',
        'quimera.mind.agent_registry',
        'quimera.mind.api_router',
        'quimera.db.models',
        'quimera.memory.memory_engine',
        'quimera.sandbox.manager',
    ]
    
    @pytest.mark.parametrize("module", IMPORT_MODULES)
    def test_module_imports(self, module):
        import importlib
        try:
            importlib.import_module(module)
        except Exception as e:
            pytest.fail(f"ImportError em {module}: {e}")


class TestRegressionPipeline:
    """Testes de regressão específicos dos bugs do pipeline."""
    
    @pytest.mark.asyncio
    async def test_pipeline_has_async_trace(self):
        """_async_trace deve existir (corrigido de _execute_with_trace)."""
        from quimera.pipeline import AutonomousPipeline
        
        p = AutonomousPipeline()
        assert hasattr(p, '_async_trace')
        assert not hasattr(p, '_execute_with_trace')
    
    @pytest.mark.asyncio
    async def test_retrieve_solutions_not_awaited(self):
        """retrieve_solutions não deve ser async (bug do await removido)."""
        import inspect
        from quimera.memory.memory_engine import MemoryEngine
        
        engine = MemoryEngine()
        assert not inspect.iscoroutinefunction(engine.retrieve_solutions)


class TestRegressionDB:
    """Testes de regressão dos aliases do banco."""
    
    def test_db_aliases_exist(self):
        from quimera.db.models import (
            PatchHistory, DriftRecord, Artifact, AgentMetric,
        )
        assert PatchHistory is not None
        assert DriftRecord is not None
        assert Artifact is not None
        assert AgentMetric is not None


class TestRegressionRouter:
    """Testes de regressão do router."""
    
    def test_router_has_resilience_methods(self):
        from quimera.core.model_router import ModelRouter, CircuitBreaker
        
        router = ModelRouter()
        assert hasattr(router, 'circuit_breaker')
        assert isinstance(router.circuit_breaker, CircuitBreaker)
        assert router.timeout > 0
        assert router.max_retries > 0
    
    def test_api_router_alias_exists(self):
        from quimera.mind.api_router import APIRouter, APIKeyRouter
        assert APIRouter is APIKeyRouter


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
