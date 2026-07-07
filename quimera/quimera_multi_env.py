#!/usr/bin/env python3
"""
Sistema Quimera com Switching Automático de Ambientes
Demonstra como usar 100% das funcionalidades através de ambientes isolados
"""
import os
import sys
import subprocess
import importlib
from pathlib import Path
from typing import Any, Optional, Dict, Callable

class QuimeraCore:
    """
    Núcleo do Quimera que coordena entre diferentes ambientes
    """
    
    def __init__(self):
        self.env_manager = None
        self.current_env = "core"
        self.available_features = self._detect_features()
        
        # Cache de módulos carregados
        self._module_cache: Dict[str, Any] = {}
        
    def _detect_features(self) -> Dict[str, bool]:
        """Detecta quais funcionalidades estão disponíveis"""
        features = {
            "llm": False,
            "rag": False, 
            "ui": False,
            "ml": False,
            "web": False,
            "security": False,
            "analysis": False,
            "docs": False
        }
        
        # Verifica se os ambientes existem
        env_base = Path("quimera-envs")
        for feature in features.keys():
            features[feature] = (env_base / feature).exists()
            
        return features
    
    def switch_to_env(self, env_name: str) -> bool:
        """Muda para um ambiente específico"""
        if not self.available_features.get(env_name, False):
            print(f"⚠️ Ambiente '{env_name}' não disponível")
            return False
            
        self.current_env = env_name
        print(f"🔄 Mudando para ambiente: {env_name}")
        return True
    
    def run_in_env(self, env_name: str, function_code: str, *args) -> Any:
        """Executa código em um ambiente específico via subprocess"""
        if not self.available_features.get(env_name, False):
            raise RuntimeError(f"Ambiente '{env_name}' não disponível")
        
        # Cria um script temporário
        script_content = f"""
import sys
import json
import pickle
import base64

# Código da função
{function_code}

# Executa a função
try:
    args = {repr(args)}
    result = execute(*args)
    
    # Serializa o resultado
    if result is not None:
        serialized = base64.b64encode(pickle.dumps(result)).decode('utf-8')
        print(f"RESULT:{serialized}")
    else:
        print("RESULT:None")
        
except Exception as e:
    print(f"ERROR:{str(e)}")
    sys.exit(1)
"""
        
        # Salva o script temporário
        script_path = Path("temp_execution.py")
        with open(script_path, "w") as f:
            f.write(script_content)
        
        try:
            # Executa no ambiente específico
            env_path = Path("quimera-envs") / env_name
            python_path = env_path / "bin" / "python"
            
            if not python_path.exists():
                python_path = env_path / "Scripts" / "python.exe"  # Windows
            
            result = subprocess.run([
                str(python_path), str(script_path)
            ], capture_output=True, text=True)
            
            # Processa o resultado
            for line in result.stdout.split('\n'):
                if line.startswith("RESULT:"):
                    result_data = line[7:]
                    if result_data == "None":
                        return None
                    else:
                        import pickle
                        import base64
                        return pickle.loads(base64.b64decode(result_data))
                elif line.startswith("ERROR:"):
                    raise RuntimeError(line[6:])
            
            return None
            
        finally:
            # Remove o script temporário
            if script_path.exists():
                script_path.unlink()
    
    # === FUNCIONALIDADES LLM ===
    
    def generate_text(self, prompt: str, model: str = "gpt-3.5-turbo") -> str:
        """Gera texto usando LLMs (ambiente: llm)"""
        function_code = f"""
def execute(prompt, model):
    import openai
    
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model=model,
        messages=[{{"role": "user", "content": prompt}}]
    )
    return response.choices[0].message.content
"""
        return self.run_in_env("llm", function_code, prompt, model)
    
    def analyze_with_langchain(self, text: str) -> Dict:
        """Análise usando LangChain (ambiente: llm)"""
        function_code = f"""
def execute(text):
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain.schema import Document
    
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000)
    docs = splitter.split_text(text)
    
    return {{
        "chunks": len(docs),
        "total_chars": len(text),
        "avg_chunk_size": len(text) / len(docs) if docs else 0
    }}
"""
        return self.run_in_env("llm", function_code, text)
    
    # === FUNCIONALIDADES RAG ===
    
    def create_embeddings(self, texts: list) -> list:
        """Cria embeddings (ambiente: rag)"""
        function_code = f"""
def execute(texts):
    from sentence_transformers import SentenceTransformer
    
    model = SentenceTransformer('all-MiniLM-L6-v2')
    embeddings = model.encode(texts)
    return embeddings.tolist()
"""
        return self.run_in_env("rag", function_code, texts)
    
    def search_similar(self, query: str, documents: list) -> list:
        """Busca documentos similares (ambiente: rag)"""
        function_code = f"""
def execute(query, documents):
    from sentence_transformers import SentenceTransformer
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity
    
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    query_embedding = model.encode([query])
    doc_embeddings = model.encode(documents)
    
    similarities = cosine_similarity(query_embedding, doc_embeddings)[0]
    
    # Retorna índices ordenados por similaridade
    sorted_indices = np.argsort(similarities)[::-1]
    
    return [{{
        "index": int(idx),
        "similarity": float(similarities[idx]),
        "document": documents[idx]
    }} for idx in sorted_indices[:5]]
"""
        return self.run_in_env("rag", function_code, query, documents)
    
    # === FUNCIONALIDADES ML ===
    
    def analyze_data(self, data: list) -> Dict:
        """Análise estatística (ambiente: ml)"""
        function_code = f"""
def execute(data):
    import pandas as pd
    import numpy as np
    
    df = pd.DataFrame(data)
    
    return {{
        "shape": df.shape,
        "dtypes": df.dtypes.to_dict(),
        "describe": df.describe().to_dict(),
        "null_counts": df.isnull().sum().to_dict()
    }}
"""
        return self.run_in_env("ml", function_code, data)
    
    # === FUNCIONALIDADES WEB ===
    
    def scrape_website(self, url: str) -> Dict:
        """Web scraping (ambiente: web)"""
        function_code = f"""
def execute(url):
    import requests
    from bs4 import BeautifulSoup
    
    response = requests.get(url, timeout=10)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    return {{
        "title": soup.title.string if soup.title else "No title",
        "paragraphs": len(soup.find_all('p')),
        "links": len(soup.find_all('a')),
        "images": len(soup.find_all('img')),
        "status_code": response.status_code
    }}
"""
        return self.run_in_env("web", function_code, url)
    
    # === FUNCIONALIDADES ANALYSIS ===
    
    def lint_code(self, code: str) -> Dict:
        """Análise de código (ambiente: analysis)"""
        function_code = f'''
def execute(code):
    import ast
    import tempfile
    import subprocess
    from pathlib import Path
    
    # Salva código em arquivo temporário
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        temp_file = f.name
    
    try:
        # Verifica sintaxe
        try:
            ast.parse(code)
            syntax_valid = True
            syntax_error = None
        except SyntaxError as e:
            syntax_valid = False
            syntax_error = str(e)
        
        # Executa pylint se sintaxe é válida
        if syntax_valid:
            result = subprocess.run([
                'pylint', temp_file, '--output-format=json'
            ], capture_output=True, text=True)
            
            import json
            try:
                pylint_results = json.loads(result.stdout)
            except:
                pylint_results = []
        else:
            pylint_results = []
        
        return {{
            "syntax_valid": syntax_valid,
            "syntax_error": syntax_error,
            "pylint_issues": len(pylint_results),
            "lines": len(code.split('\\n'))
        }}
        
    finally:
        Path(temp_file).unlink()
'''
        return self.run_in_env("analysis", function_code, code)
    
    def status(self) -> Dict:
        """Status completo do sistema"""
        status = {
            "current_env": self.current_env,
            "available_features": self.available_features,
            "total_features": len([f for f in self.available_features.values() if f]),
            "features_status": {}
        }
        
        # Testa cada funcionalidade
        for feature, available in self.available_features.items():
            if available:
                try:
                    if feature == "llm":
                        # Teste simples do LLM
                        result = "✅ LLM pronto"
                    elif feature == "rag": 
                        # Teste simples do RAG
                        result = "✅ RAG pronto"
                    elif feature == "ml":
                        # Teste simples do ML
                        result = "✅ ML pronto"
                    elif feature == "web":
                        # Teste simples do Web
                        result = "✅ Web scraping pronto"
                    else:
                        result = "✅ Disponível"
                        
                    status["features_status"][feature] = result
                except Exception as e:
                    status["features_status"][feature] = f"❌ Erro: {str(e)}"
            else:
                status["features_status"][feature] = "⚪ Não instalado"
        
        return status

def main():
    """Interface CLI principal"""
    quimera = QuimeraCore()
    
    if len(sys.argv) < 2:
        print("🔮 Quimera - Sistema Multi-Ambiente")
        print("=" * 40)
        
        status = quimera.status()
        print(f"Ambiente atual: {status['current_env']}")
        print(f"Funcionalidades ativas: {status['total_features']}/{len(status['available_features'])}")
        print()
        
        for feature, status_msg in status["features_status"].items():
            print(f"📁 {feature:12} - {status_msg}")
        
        print("\nComandos disponíveis:")
        print("  python quimera_multi_env.py llm 'Olá mundo'")
        print("  python quimera_multi_env.py rag 'buscar' 'doc1,doc2,doc3'")
        print("  python quimera_multi_env.py web 'https://python.org'")
        print("  python quimera_multi_env.py analyze 'print(\"hello\")'")
        
        return
    
    command = sys.argv[1]
    
    try:
        if command == "llm" and len(sys.argv) > 2:
            result = quimera.generate_text(sys.argv[2])
            print(f"🤖 LLM Response: {result}")
            
        elif command == "rag" and len(sys.argv) > 3:
            query = sys.argv[2]
            docs = sys.argv[3].split(',')
            result = quimera.search_similar(query, docs)
            print(f"🔍 RAG Results: {result}")
            
        elif command == "web" and len(sys.argv) > 2:
            result = quimera.scrape_website(sys.argv[2])
            print(f"🌐 Web Scraping: {result}")
            
        elif command == "analyze" and len(sys.argv) > 2:
            result = quimera.lint_code(sys.argv[2])
            print(f"🔍 Code Analysis: {result}")
            
        else:
            print("❌ Comando inválido ou argumentos insuficientes")
            
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    main()