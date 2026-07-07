"""
Testes do Sandbox — Isolamento e segurança.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


class TestSandboxManager:
    """Testes do SandboxManager."""
    
    def test_sandbox_import(self):
        from quimera.sandbox.manager import SandboxManager
        assert SandboxManager is not None
    
    def test_sandbox_instantiation(self):
        from quimera.sandbox.manager import SandboxManager
        
        from quimera.sandbox.backends.docker_backend import DockerBackend
        backend = DockerBackend()
        manager = SandboxManager(backend=backend)
        assert manager is not None
    
    def test_sandbox_backend_docker(self):
        from quimera.sandbox.backends.docker_backend import DockerBackend
        assert DockerBackend is not None
    
    def test_sandbox_backend_firejail(self):
        try:
            from quimera.sandbox.backends.firejail_backend import FirejailBackend
            assert FirejailBackend is not None
        except ImportError:
            pytest.skip("firejail_backend não disponível")
    
    def test_sandbox_safety_patterns(self):
        """Verifica padrões de segurança no código do sandbox."""
        import re
        
        sandbox_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'quimera', 'sandbox'
        )
        
        unsafe_patterns_in_sandbox = 0
        for root, dirs, files in os.walk(sandbox_dir):
            for f in files:
                if f.endswith('.py'):
                    with open(os.path.join(root, f)) as fh:
                        content = fh.read()
                    
                    # subprocess no sandbox é esperado, mas shell=True é perigoso
                    if 'shell=True' in content:
                        unsafe_patterns_in_sandbox += 1
        
        # shell=True não deve aparecer mais que 2x no sandbox
        assert unsafe_patterns_in_sandbox <= 2, \
            f"shell=True encontrado {unsafe_patterns_in_sandbox}x no sandbox"


class TestUtilsControle:
    """Testes do módulo de controle de segurança."""
    
    def test_verificar_padroes_inseguros(self):
        from quimera.utils.controle import verificar_padroes_inseguros
        
        code = "os.system('rm -rf /')"
        results = verificar_padroes_inseguros(code)
        assert len(results) > 0
    
    def test_verificar_codigo_seguro(self):
        from quimera.utils.controle import verificar_padroes_inseguros
        
        code = "int x = 1 + 2;"
        results = verificar_padroes_inseguros(code)
        assert len(results) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
