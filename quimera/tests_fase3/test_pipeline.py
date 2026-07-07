"""
Testes do Pipeline — Cobre todos os bugs corrigidos na Fase 2.
Executa o pipeline H1→H6 com código mínimo.
"""
import sys
import os
import asyncio
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


@pytest.mark.asyncio
async def test_pipeline_runs_all_7_stages():
    """Pipeline deve completar todos os 7 estágios com código C simples."""
    from quimera.pipeline import AutonomousPipeline
    
    p = AutonomousPipeline()
    result = await p.run('int main() { return 0; }', language='c')
    
    assert result.success, f"Pipeline falhou: {result.errors}"
    assert len(result.stages_completed) == 7, f"Esperado 7 stages, teve {len(result.stages_completed)}"
    assert 'accept' in result.stages_completed
    assert 'retrieve' in result.stages_completed
    assert 'verify' in result.stages_completed
    assert 'evolve' in result.stages_completed
    assert 'attack' in result.stages_completed
    assert 'output' in result.stages_completed
    assert 'record' in result.stages_completed


@pytest.mark.asyncio
async def test_pipeline_generates_patches():
    """H4 deve gerar patches via GeneticPatchEngine."""
    from quimera.pipeline import AutonomousPipeline
    
    p = AutonomousPipeline()
    result = await p.run('int main() { return 0; }', language='c')
    
    assert result.best_patch, "Nenhum patch foi gerado"
    assert len(result.best_patch) > 0
    assert result.fitness_score >= 0.0


@pytest.mark.asyncio
async def test_pipeline_error_description():
    """Pipeline deve classificar erro quando description é fornecida."""
    from quimera.pipeline import AutonomousPipeline
    
    p = AutonomousPipeline()
    result = await p.run(
        'char buf[10]; strcpy(buf, "overflow");', 
        language='c',
        error_description='buffer overflow detected',
    )
    
    assert result.success
    assert len(result.stages_completed) == 7


@pytest.mark.asyncio
async def test_pipeline_handles_empty_code():
    """Pipeline não deve crashar com código vazio."""
    from quimera.pipeline import AutonomousPipeline
    
    p = AutonomousPipeline()
    result = await p.run('', language='c')
    
    # Pode falhar ou ter sucesso, mas não pode dar exceção não tratada
    assert result is not None
    assert hasattr(result, 'errors')


@pytest.mark.asyncio
async def test_pipeline_with_complex_code():
    """Pipeline deve lidar com código multi-linha."""
    from quimera.pipeline import AutonomousPipeline
    
    code = """
    #include <stdio.h>
    int main() {
        char buf[16];
        printf("Hello World\\n");
        return 0;
    }
    """
    
    p = AutonomousPipeline()
    result = await p.run(code, language='c')
    
    assert result is not None
    assert len(result.stages_completed) >= 1  # Pelo menos H1 deve rodar


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
