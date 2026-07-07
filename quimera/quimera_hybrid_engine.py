#!/usr/bin/env python3
"""
QUIMERA HYBRID EXECUTION ENGINE
Motor de execução híbrida que coordena múltiplos ambientes simultaneamente
"""
import os
import sys
import json
import pickle
import base64
import tempfile
import subprocess
import threading
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from queue import Queue
import time

@dataclass
class HybridTaskResult:
    """Resultado de uma tarefa híbrida"""
    success: bool
    result: Any
    environment: str
    execution_time: float
    error: Optional[str] = None

class QuimeraHybridEngine:
    """
    Motor que executa código necessitando de múltiplas bibliotecas simultaneamente
    """
    
    def __init__(self):
        self.available_envs = self._detect_environments()
        self.env_connections = {}
        self.shared_state = {}
        self.execution_cache = {}
        
    def _detect_environments(self) -> Dict[str, bool]:
        """Detecta ambientes disponíveis"""
        envs = {}
        env_base = Path("quimera-envs")
        
        for env_name in ["core", "llm", "rag", "ui", "ml", "web", "security", "analysis", "docs"]:
            envs[env_name] = (env_base / env_name).exists()
        
        return envs
    
    def create_persistent_connection(self, env_name: str) -> bool:
        """Cria conexão persistente com um ambiente"""
        if env_name in self.env_connections:
            return True
            
        if not self.available_envs.get(env_name, False):
            return False
        
        env_path = Path("quimera-envs") / env_name
        python_path = env_path / "bin" / "python"
        
        if not python_path.exists():
            python_path = env_path / "Scripts" / "python.exe"  # Windows
        
        try:
            # Cria processo persistente
            process = subprocess.Popen([
                str(python_path), "-u", "-c", """
import sys
import json
import pickle
import base64

print("ENV_READY")
sys.stdout.flush()

while True:
    try:
        line = input()
        if line == "EXIT":
            break
            
        command_data = json.loads(line)
        command_type = command_data["type"]
        
        if command_type == "EXEC":
            code = command_data["code"]
            shared_data = command_data.get("shared_data", {})
            
            # Deserializa dados compartilhados
            for key, value in shared_data.items():
                if isinstance(value, str) and value.startswith("PICKLE:"):
                    shared_data[key] = pickle.loads(base64.b64decode(value[7:]))
            
            # Adiciona dados compartilhados ao namespace local
            locals().update(shared_data)
            globals().update(shared_data)
            
            try:
                # Executa código
                result = eval(code) if command_data.get("eval", False) else exec(code)
                
                # Serializa resultado se necessário
                if result is not None:
                    try:
                        serialized = "PICKLE:" + base64.b64encode(pickle.dumps(result)).decode('utf-8')
                        print(json.dumps({"status": "success", "result": serialized}))
                    except:
                        print(json.dumps({"status": "success", "result": str(result)}))
                else:
                    print(json.dumps({"status": "success", "result": None}))
                    
            except Exception as e:
                print(json.dumps({"status": "error", "error": str(e)}))
                
        elif command_type == "IMPORT":
            module = command_data["module"]
            try:
                exec(f"import {module}")
                print(json.dumps({"status": "success", "imported": module}))
            except Exception as e:
                print(json.dumps({"status": "error", "error": str(e)}))
        
        sys.stdout.flush()
        
    except EOFError:
        break
    except Exception as e:
        print(json.dumps({"status": "error", "error": str(e)}))
        sys.stdout.flush()
"""
            ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
               text=True, bufsize=1)
            
            # Aguarda sinal de pronto
            ready_signal = process.stdout.readline().strip()
            if ready_signal == "ENV_READY":
                self.env_connections[env_name] = process
                print(f"✅ Conexão persistente criada: {env_name}")
                return True
            else:
                process.terminate()
                return False
                
        except Exception as e:
            print(f"❌ Erro ao criar conexão com {env_name}: {e}")
            return False
    
    def close_connections(self):
        """Fecha todas as conexões persistentes"""
        for env_name, process in self.env_connections.items():
            try:
                process.stdin.write("EXIT\n")
                process.stdin.flush()
                process.wait(timeout=5)
            except:
                process.terminate()
        
        self.env_connections.clear()
        print("🔌 Todas as conexões fechadas")
    
    def execute_in_env_persistent(self, env_name: str, code: str, shared_data: Dict = None, eval_mode: bool = False) -> HybridTaskResult:
        """Executa código em ambiente com conexão persistente"""
        start_time = time.time()
        
        if env_name not in self.env_connections:
            if not self.create_persistent_connection(env_name):
                return HybridTaskResult(
                    success=False,
                    result=None,
                    environment=env_name,
                    execution_time=time.time() - start_time,
                    error=f"Ambiente {env_name} não disponível"
                )
        
        process = self.env_connections[env_name]
        
        # Prepara dados compartilhados
        processed_shared_data = {}
        if shared_data:
            for key, value in shared_data.items():
                try:
                    # Tenta serializar objetos complexos
                    json.dumps(value)
                    processed_shared_data[key] = value
                except:
                    # Se não conseguir, usa pickle
                    serialized = "PICKLE:" + base64.b64encode(pickle.dumps(value)).decode('utf-8')
                    processed_shared_data[key] = serialized
        
        # Prepara comando
        command = {
            "type": "EXEC",
            "code": code,
            "shared_data": processed_shared_data,
            "eval": eval_mode
        }
        
        try:
            # Envia comando
            process.stdin.write(json.dumps(command) + "\n")
            process.stdin.flush()
            
            # Lê resposta
            response_line = process.stdout.readline()
            if not response_line:
                raise RuntimeError("Processo terminou inesperadamente")
            
            response = json.loads(response_line.strip())
            
            execution_time = time.time() - start_time
            
            if response["status"] == "success":
                result = response["result"]
                
                # Deserializa se necessário
                if isinstance(result, str) and result.startswith("PICKLE:"):
                    result = pickle.loads(base64.b64decode(result[7:]))
                
                return HybridTaskResult(
                    success=True,
                    result=result,
                    environment=env_name,
                    execution_time=execution_time
                )
            else:
                return HybridTaskResult(
                    success=False,
                    result=None,
                    environment=env_name,
                    execution_time=execution_time,
                    error=response["error"]
                )
                
        except Exception as e:
            return HybridTaskResult(
                success=False,
                result=None,
                environment=env_name,
                execution_time=time.time() - start_time,
                error=str(e)
            )
    
    def execute_hybrid_task(self, task_definition: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa tarefa híbrida que coordena múltiplos ambientes
        
        task_definition = {
            "name": "nome_da_tarefa",
            "steps": [
                {
                    "env": "ml",
                    "code": "import pandas as pd; data = pd.DataFrame({'x': [1,2,3]})",
                    "outputs": ["data"]
                },
                {
                    "env": "llm", 
                    "code": "summary = f'Dataset has {len(data)} rows'",
                    "inputs": ["data"],
                    "outputs": ["summary"]
                }
            ]
        }
        """
        print(f"🚀 EXECUTANDO TAREFA HÍBRIDA: {task_definition['name']}")
        print("=" * 60)
        
        steps = task_definition["steps"]
        shared_state = {}
        results = {}
        
        for i, step in enumerate(steps, 1):
            env_name = step["env"]
            code = step["code"]
            inputs = step.get("inputs", [])
            outputs = step.get("outputs", [])
            
            print(f"\n📍 ETAPA {i}/{len(steps)}: {env_name}")
            print(f"🔧 Código: {code[:50]}..." if len(code) > 50 else f"🔧 Código: {code}")
            
            # Prepara dados de entrada
            step_inputs = {}
            for input_var in inputs:
                if input_var in shared_state:
                    step_inputs[input_var] = shared_state[input_var]
                else:
                    print(f"⚠️ Variável '{input_var}' não encontrada no estado compartilhado")
            
            # Executa no ambiente
            result = self.execute_in_env_persistent(env_name, code, step_inputs)
            
            if result.success:
                print(f"✅ Executado em {result.execution_time:.2f}s")
                
                # Extrai outputs do código executado
                for output_var in outputs:
                    extraction_code = f"globals().get('{output_var}', locals().get('{output_var}'))"
                    extract_result = self.execute_in_env_persistent(env_name, extraction_code, eval_mode=True)
                    
                    if extract_result.success and extract_result.result is not None:
                        shared_state[output_var] = extract_result.result
                        print(f"   📤 Extraído: {output_var}")
                
                results[f"step_{i}"] = {
                    "success": True,
                    "environment": env_name,
                    "execution_time": result.execution_time,
                    "outputs_extracted": outputs
                }
            else:
                print(f"❌ Falha: {result.error}")
                results[f"step_{i}"] = {
                    "success": False,
                    "environment": env_name,
                    "error": result.error
                }
                # Para a execução em caso de erro
                break
        
        print(f"\n🎉 TAREFA HÍBRIDA CONCLUÍDA!")
        print("=" * 60)
        
        return {
            "task_name": task_definition["name"],
            "steps_executed": len(results),
            "total_steps": len(steps),
            "shared_state": shared_state,
            "step_results": results,
            "success": all(r["success"] for r in results.values())
        }
    
    def create_hybrid_function(self, function_definition: Dict[str, Any]) -> callable:
        """
        Cria função híbrida que pode usar bibliotecas de múltiplos ambientes
        
        function_definition = {
            "name": "analyze_and_visualize",
            "environments": ["ml", "llm"],
            "code": '''
def hybrid_function(data_file):
    # No ambiente ML
    import pandas as pd
    import matplotlib.pyplot as plt
    
    data = pd.read_csv(data_file)
    stats = data.describe()
    
    # No ambiente LLM (simulado)
    summary = f"Dados analisados: {len(data)} registros, {len(data.columns)} colunas"
    
    return {"stats": stats, "summary": summary}
'''
        }
        """
        
        def hybrid_wrapper(*args, **kwargs):
            # Cria tarefa híbrida dinamicamente
            task = {
                "name": function_definition["name"],
                "steps": []
            }
            
            # Processa código para diferentes ambientes
            # (Implementação simplificada - em produção seria mais sofisticada)
            for env in function_definition["environments"]:
                step = {
                    "env": env,
                    "code": function_definition["code"],
                    "inputs": list(kwargs.keys()),
                    "outputs": ["result"]
                }
                task["steps"].append(step)
            
            # Executa
            result = self.execute_hybrid_task(task)
            return result["shared_state"].get("result")
        
        return hybrid_wrapper

def demonstrate_hybrid_execution():
    """Demonstra execução híbrida"""
    
    print("🧪 DEMONSTRAÇÃO: EXECUÇÃO HÍBRIDA")
    print("=" * 60)
    
    engine = QuimeraHybridEngine()
    
    # Exemplo 1: Análise que usa ML + LLM
    print("\n🔹 EXEMPLO 1: Análise de dados com ML + LLM")
    
    task_ml_llm = {
        "name": "analise_dados_inteligente",
        "steps": [
            {
                "env": "ml",
                "code": """
import pandas as pd
import numpy as np

# Cria dataset exemplo
data = pd.DataFrame({
    'vendas': np.random.randint(100, 1000, 30),
    'mes': range(1, 31)
})

# Análise estatística
media_vendas = data['vendas'].mean()
desvio_vendas = data['vendas'].std()
tendencia = 'crescente' if data['vendas'].iloc[-1] > data['vendas'].iloc[0] else 'decrescente'

stats_summary = {
    'media': media_vendas,
    'desvio': desvio_vendas,
    'tendencia': tendencia,
    'total_registros': len(data)
}
""",
                "outputs": ["stats_summary", "data"]
            },
            {
                "env": "llm",
                "code": """
# Gera insights usando dados do ML
insights = []

if stats_summary['media'] > 500:
    insights.append("Vendas estão acima da média histórica")
else:
    insights.append("Vendas abaixo da média, requer atenção")

if stats_summary['desvio'] > 200:
    insights.append("Alta variabilidade nas vendas - mercado instável")
else:
    insights.append("Vendas consistentes - mercado estável")

insights.append(f"Tendência {stats_summary['tendencia']} identificada")

relatorio_inteligente = {
    'resumo_executivo': f"Análise de {stats_summary['total_registros']} registros",
    'insights': insights,
    'recomendacoes': ["Revisar estratégia de vendas", "Monitorar concorrência"]
}
""",
                "inputs": ["stats_summary"],
                "outputs": ["relatorio_inteligente"]
            }
        ]
    }
    
    try:
        result = engine.execute_hybrid_task(task_ml_llm)
        
        print(f"✅ Tarefa executada: {result['success']}")
        print(f"📊 Etapas: {result['steps_executed']}/{result['total_steps']}")
        
        if "relatorio_inteligente" in result["shared_state"]:
            relatorio = result["shared_state"]["relatorio_inteligente"]
            print(f"📋 Relatório: {relatorio}")
            
    except Exception as e:
        print(f"❌ Erro na demonstração: {e}")
    
    # Exemplo 2: Web scraping + Análise
    print("\n🔹 EXEMPLO 2: Web scraping + Análise de sentimento")
    
    task_web_llm = {
        "name": "scraping_com_analise",
        "steps": [
            {
                "env": "web",
                "code": """
import requests
from bs4 import BeautifulSoup

# Simula scraping (sem fazer requisição real)
textos_extraidos = [
    "Produto excelente, muito satisfeito com a compra",
    "Qualidade duvidosa, não recomendo",
    "Entrega rápida e produto conforme anunciado",
    "Preço muito alto para o que oferece"
]

metadados_scraping = {
    'fonte': 'reviews_simulados',
    'total_textos': len(textos_extraidos),
    'data_coleta': '2024-01-15'
}
""",
                "outputs": ["textos_extraidos", "metadados_scraping"]
            },
            {
                "env": "llm",
                "code": """
# Análise de sentimento dos textos
sentimentos = []
for texto in textos_extraidos:
    if any(word in texto.lower() for word in ['excelente', 'satisfeito', 'rápida', 'conforme']):
        sentimento = 'positivo'
    elif any(word in texto.lower() for word in ['duvidosa', 'não recomendo', 'muito alto']):
        sentimento = 'negativo'
    else:
        sentimento = 'neutro'
    
    sentimentos.append(sentimento)

# Consolidação
analise_sentimento = {
    'sentimentos': sentimentos,
    'positivos': sentimentos.count('positivo'),
    'negativos': sentimentos.count('negativo'),
    'neutros': sentimentos.count('neutro'),
    'score_geral': (sentimentos.count('positivo') - sentimentos.count('negativo')) / len(sentimentos)
}
""",
                "inputs": ["textos_extraidos"],
                "outputs": ["analise_sentimento"]
            }
        ]
    }
    
    try:
        result = engine.execute_hybrid_task(task_web_llm)
        
        print(f"✅ Tarefa executada: {result['success']}")
        
        if "analise_sentimento" in result["shared_state"]:
            analise = result["shared_state"]["analise_sentimento"]
            print(f"😊 Positivos: {analise['positivos']}")
            print(f"😞 Negativos: {analise['negativos']}")
            print(f"📊 Score: {analise['score_geral']:.2f}")
            
    except Exception as e:
        print(f"❌ Erro na demonstração: {e}")
    
    # Fecha conexões
    engine.close_connections()

def main():
    """Interface principal"""
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demonstrate_hybrid_execution()
    else:
        print("🔮 QUIMERA HYBRID EXECUTION ENGINE")
        print("=" * 50)
        print("Motor de execução híbrida - coordena múltiplos ambientes")
        print()
        print("Execute:")
        print("  python quimera_hybrid_engine.py --demo")
        print()
        print("Para ver demonstração de execução híbrida!")

if __name__ == "__main__":
    main()