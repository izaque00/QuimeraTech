#!/usr/bin/env python3
"""
QUIMERA DYNAMIC IMPORT SYSTEM
Sistema de importação dinâmica que ativa ambientes automaticamente
"""
import sys
import importlib
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, List
import pickle
import base64
import tempfile

class QuimeraDynamicImporter:
    """
    Sistema que intercepta imports e ativa ambientes automaticamente
    """
    
    def __init__(self):
        self.env_mappings = self._create_environment_mappings()
        self.available_envs = self._detect_environments()
        self.cached_modules = {}
        
    def _create_environment_mappings(self) -> Dict[str, str]:
        """Mapeia bibliotecas para seus ambientes específicos"""
        return {
            # LLM Environment
            "openai": "llm",
            "anthropic": "llm", 
            "langchain": "llm",
            "langchain_core": "llm",
            "langchain_openai": "llm",
            "langchain_community": "llm",
            "tiktoken": "llm",
            "transformers": "llm",
            "torch": "llm",
            "cohere": "llm",
            
            # RAG Environment
            "sentence_transformers": "rag",
            "faiss": "rag",
            "chromadb": "rag", 
            "llama_index": "rag",
            "pinecone": "rag",
            
            # ML Environment
            "pandas": "ml",
            "numpy": "ml",
            "scipy": "ml",
            "sklearn": "ml",
            "scikit_learn": "ml",
            "matplotlib": "ml",
            "seaborn": "ml",
            "plotly": "ml",
            "joblib": "ml",
            "pillow": "ml",
            "cv2": "ml",
            "opencv": "ml",
            
            # Web Environment
            "selenium": "web",
            "playwright": "web",
            "scrapy": "web",
            "beautifulsoup4": "web",
            "bs4": "web",
            "httpx": "web",
            
            # UI Environment
            "streamlit": "ui",
            "gradio": "ui",
            "jupyter": "ui",
            "ipython": "ui",
            
            # Analysis Environment
            "pylint": "analysis",
            "black": "analysis",
            "isort": "analysis",
            "flake8": "analysis",
            "mypy": "analysis",
            "bandit": "analysis",
            
            # Security Environment
            "cryptography": "security",
            "jwt": "security",
            "bcrypt": "security",
            
            # Docs Environment
            "PyPDF2": "docs",
            "docx": "docs",
            "markdown": "docs",
            "python_docx": "docs"
        }
    
    def _detect_environments(self) -> Dict[str, bool]:
        """Detecta ambientes disponíveis"""
        envs = {}
        env_base = Path("quimera-envs")
        
        for env_name in ["core", "llm", "rag", "ui", "ml", "web", "security", "analysis", "docs"]:
            envs[env_name] = (env_base / env_name).exists()
        
        return envs
    
    def get_required_env(self, module_name: str) -> Optional[str]:
        """Determina qual ambiente é necessário para um módulo"""
        # Normaliza nome do módulo
        base_module = module_name.split('.')[0]
        return self.env_mappings.get(base_module)
    
    def execute_in_env(self, env_name: str, code: str, module_name: str) -> Any:
        """Executa código para importar módulo em ambiente específico"""
        if not self.available_envs.get(env_name, False):
            raise ImportError(f"Ambiente '{env_name}' não disponível para importar '{module_name}'")
        
        # Cria script de importação
        script_content = f"""
import sys
import pickle
import base64

try:
    # Importa o módulo
    {code}
    
    # Verifica se a importação funcionou
    if '{module_name}' in locals():
        module_obj = locals()['{module_name}']
    elif '{module_name}' in globals():
        module_obj = globals()['{module_name}']
    else:
        # Tenta importar diretamente
        import {module_name}
        module_obj = {module_name}
    
    # Serializa informações do módulo (não o módulo inteiro)
    module_info = {{
        'name': module_obj.__name__,
        'file': getattr(module_obj, '__file__', None),
        'version': getattr(module_obj, '__version__', None),
        'doc': getattr(module_obj, '__doc__', None)[:200] if getattr(module_obj, '__doc__', None) else None
    }}
    
    serialized = base64.b64encode(pickle.dumps(module_info)).decode('utf-8')
    print(f"IMPORT_SUCCESS:{serialized}")
    
except ImportError as e:
    print(f"IMPORT_ERROR:{{str(e)}}")
except Exception as e:
    print(f"GENERAL_ERROR:{{str(e)}}")
"""
        
        # Executa no ambiente
        script_path = Path(f"temp_import_{env_name}_{module_name}.py")
        try:
            with open(script_path, "w") as f:
                f.write(script_content)
            
            # Determina path do Python
            env_path = Path("quimera-envs") / env_name
            python_path = env_path / "bin" / "python"
            
            if not python_path.exists():
                python_path = env_path / "Scripts" / "python.exe"  # Windows
            
            # Executa
            result = subprocess.run([
                str(python_path), str(script_path)
            ], capture_output=True, text=True, timeout=30)
            
            # Processa resultado
            for line in result.stdout.split('\n'):
                if line.startswith("IMPORT_SUCCESS:"):
                    module_info = pickle.loads(base64.b64decode(line[15:]))
                    return module_info
                elif line.startswith("IMPORT_ERROR:"):
                    raise ImportError(f"Falha ao importar {module_name} em {env_name}: {line[13:]}")
                elif line.startswith("GENERAL_ERROR:"):
                    raise RuntimeError(f"Erro geral ao importar {module_name}: {line[14:]}")
            
            # Se chegou aqui, algo deu errado
            raise ImportError(f"Importação de {module_name} não retornou resultado válido")
            
        finally:
            if script_path.exists():
                script_path.unlink()

class QuimeraModuleProxy:
    """
    Proxy que simula um módulo mas executa no ambiente correto
    """
    
    def __init__(self, module_name: str, env_name: str, importer: QuimeraDynamicImporter):
        self._module_name = module_name
        self._env_name = env_name 
        self._importer = importer
        self._module_info = None
        
    def _execute_function(self, function_name: str, *args, **kwargs):
        """Executa uma função do módulo no ambiente correto"""
        
        function_code = f"""
def execute_function():
    import {self._module_name}
    
    # Obtém a função
    func = getattr({self._module_name}, '{function_name}')
    
    # Executa com argumentos
    args = {repr(args)}
    kwargs = {repr(kwargs)}
    
    result = func(*args, **kwargs)
    return result
"""
        
        return self._importer.execute_in_env(self._env_name, function_code, "result")
    
    def __getattr__(self, name: str):
        """Intercepta acesso a atributos/funções do módulo"""
        if name.startswith('_'):
            raise AttributeError(f"'{self._module_name}' object has no attribute '{name}'")
        
        # Retorna uma função que executa no ambiente correto
        def proxy_function(*args, **kwargs):
            return self._execute_function(name, *args, **kwargs)
        
        return proxy_function
    
    def __str__(self):
        return f"<QuimeraProxy for {self._module_name} in {self._env_name}>"
    
    def __repr__(self):
        return self.__str__()

class QuimeraSmartImportSystem:
    """
    Sistema de importação inteligente integrado ao Quimera
    """
    
    def __init__(self):
        self.importer = QuimeraDynamicImporter()
        import builtins
        self.original_import = builtins.__import__
        self.active = False
        
    def activate(self):
        """Ativa o sistema de importação inteligente"""
        if not self.active:
            import builtins
            builtins.__import__ = self.smart_import
            self.active = True
            print("🧠 Sistema de importação inteligente ativado")
    
    def deactivate(self):
        """Desativa o sistema de importação inteligente"""
        if self.active:
            import builtins
            builtins.__import__ = self.original_import
            self.active = False
            print("💤 Sistema de importação inteligente desativado")
    
    def smart_import(self, name, globals=None, locals=None, fromlist=(), level=0):
        """Importação inteligente que ativa ambientes automaticamente"""
        
        # Para imports básicos do Python, usa importação normal
        if name in sys.stdlib_module_names or name.startswith('_'):
            return self.original_import(name, globals, locals, fromlist, level)
        
        # Verifica se precisa de ambiente específico
        required_env = self.importer.get_required_env(name)
        
        if required_env and self.importer.available_envs.get(required_env, False):
            print(f"🔄 Ativando ambiente '{required_env}' para importar '{name}'")
            
            # Tenta importar no ambiente específico
            try:
                import_code = f"import {name}"
                module_info = self.importer.execute_in_env(required_env, import_code, name)
                print(f"✅ {name} importado com sucesso do ambiente '{required_env}'")
                
                # Retorna proxy do módulo
                return QuimeraModuleProxy(name, required_env, self.importer)
                
            except Exception as e:
                print(f"⚠️ Falha ao importar {name} do ambiente '{required_env}': {e}")
                # Fallback para importação normal
                
        # Fallback: importação normal
        try:
            return self.original_import(name, globals, locals, fromlist, level)
        except ImportError:
            if required_env:
                raise ImportError(f"Módulo '{name}' requer ambiente '{required_env}' que não está disponível")
            raise

# Instância global do sistema
_smart_import_system = QuimeraSmartImportSystem()

def enable_smart_imports():
    """Ativa importações inteligentes globalmente"""
    _smart_import_system.activate()

def disable_smart_imports():
    """Desativa importações inteligentes globalmente"""
    _smart_import_system.deactivate()

def with_smart_imports(func):
    """Decorator para ativar importações inteligentes em uma função"""
    def wrapper(*args, **kwargs):
        enable_smart_imports()
        try:
            return func(*args, **kwargs)
        finally:
            disable_smart_imports()
    return wrapper

def smart_execute(code_string: str, required_modules: List[str] = None):
    """
    Executa código garantindo que todos os módulos necessários estejam disponíveis
    """
    if required_modules:
        print(f"🎯 Detectando ambientes para: {', '.join(required_modules)}")
        
        # Determina ambientes necessários
        required_envs = set()
        for module in required_modules:
            env = _smart_import_system.importer.get_required_env(module)
            if env:
                required_envs.add(env)
        
        print(f"🌍 Ambientes necessários: {', '.join(required_envs)}")
        
        # Verifica disponibilidade
        missing_envs = [env for env in required_envs if not _smart_import_system.importer.available_envs.get(env)]
        if missing_envs:
            raise RuntimeError(f"Ambientes não disponíveis: {', '.join(missing_envs)}")
    
    # Ativa importações inteligentes
    enable_smart_imports()
    try:
        # Executa o código
        exec(code_string)
    finally:
        disable_smart_imports()

if __name__ == "__main__":
    # Teste do sistema
    print("🧪 Testando sistema de importação inteligente")
    
    enable_smart_imports()
    
    try:
        # Simula imports que seriam interceptados
        print("Testando importação de pandas...")
        # import pandas as pd  # Seria interceptado
        
        print("Testando importação de requests...")
        import requests  # Import normal
        
    except Exception as e:
        print(f"Erro no teste: {e}")
    finally:
        disable_smart_imports()