"""
Testes do Banco de Dados — Models, aliases e conexão.
Cobre os aliases de compatibilidade (PatchHistory, DriftRecord, etc).
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


class TestDBModels:
    """Testes dos models e aliases de compatibilidade."""
    
    def test_all_models_import(self):
        """Todos os models devem importar sem erro."""
        from quimera.db.models import (
            ScriptProfile, HistoricoPatch, RegistroDrift,
            MetricaAgente, MissaoTecnica, EntradaAnaliseModel,
        )
        assert ScriptProfile is not None
        assert HistoricoPatch is not None
        assert RegistroDrift is not None
        assert MetricaAgente is not None
    
    def test_compatibility_aliases(self):
        """BUG FIX: Aliases PatchHistory, DriftRecord, etc devem existir."""
        from quimera.db.models import (
            PatchHistory, DriftRecord, Artifact, AgentMetric,
        )
        from quimera.db.models import HistoricoPatch, RegistroDrift, EntradaAnaliseModel, MetricaAgente
        
        # Aliases devem apontar para as classes corretas
        assert PatchHistory is HistoricoPatch
        assert DriftRecord is RegistroDrift
        assert Artifact is EntradaAnaliseModel
        assert AgentMetric is MetricaAgente
    
    def test_base_import(self):
        """Base, get_db, init_db devem importar."""
        from quimera.db.base import Base, get_db, init_db
        
        assert Base is not None
        assert get_db is not None
        assert init_db is not None
    
    def test_schemas_import(self):
        """Schemas devem importar."""
        from quimera.db import schemas
        assert schemas is not None
    
    def test_service_import(self):
        """Service deve importar."""
        from quimera.db import service
        assert service is not None


class TestDBInit:
    """Testes de inicialização do banco."""
    
    def test_init_db_creates_tables(self):
        """init_db deve criar tabelas sem erro."""
        import tempfile
        import os
        
        # Usar banco temporário
        old_db = os.environ.get('QUIMERA_DB_URL', '')
        os.environ['QUIMERA_DB_URL'] = 'sqlite:///:memory:'
        
        try:
            from quimera.db.base import init_db
            init_db()
        finally:
            if old_db:
                os.environ['QUIMERA_DB_URL'] = old_db
    
    def test_get_db_returns_session(self):
        """get_db deve retornar um context manager."""
        from quimera.db.base import get_db
        
        db = get_db()
        assert db is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
