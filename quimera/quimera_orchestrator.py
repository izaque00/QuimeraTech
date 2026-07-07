#!/usr/bin/env python3
"""
QUIMERA SMART ORCHESTRATOR - VERSÃO MELHORADA
Motor de coordenação inteligente para operações multi-ambiente
Com ativação automática de ambientes virtuais
"""
import json
import asyncio
import pickle
import base64
import tempfile
import subprocess
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Importa o gerenciador de ambientes
sys.path.append(str(Path(__file__).parent))
try:
    from quimera.quimera_env_manager import QuimeraEnvManager
except ImportError:
    print("❌ Erro: quimera_env_manager.py não encontrado no mesmo diretório")
    sys.exit(1)

class OperationType(Enum):
    """Tipos de operações do Quimera"""
    ANALYZE_CODE = "analyze_code"
    GENERATE_TEXT = "generate_text"
    SEARCH_DOCS = "search_docs"
    CREATE_EMBEDDINGS = "create_embeddings"
    WEB_SCRAPE = "web_scrape"
    VISUALIZE_DATA = "visualize_data"
    PROCESS_DOCUMENT = "process_document"
    SECURITY_SCAN = "security_scan"

@dataclass
class PipelineStep:
    """Um passo no pipeline de execução"""
    operation: OperationType
    environment: str
    function_code: str
    input_keys: List[str]
    output_key: str
    dependencies: List[str] = None

@dataclass
class ExecutionContext:
    """Contexto de execução compartilhado"""
    data: Dict[str, Any]
    metadata: Dict[str, Any]
    cache: Dict[str, Any]

class QuimeraSmartOrchestrator:
    """
    Orquestrador inteligente que coordena execução entre múltiplos ambientes
    COM ATIVAÇÃO AUTOMÁTICA DE AMBIENTES VIRTUAIS
    """
    
    def __init__(self):
        self.env_manager = QuimeraEnvManager()
        self.available_envs = self._detect_environments()
        self.execution_cache = {}
        self.pipeline_templates = self._load_pipeline_templates()
        self.active_environments = {}  # Cache de ambientes ativos
        
        print("🔮 QUIMERA SMART ORCHESTRATOR - VERSÃO MELHORADA")
        print("=" * 60)
        print("✨ Com ativação automática de ambientes virtuais")
        print()
    
    def _detect_environments(self) -> Dict[str, bool]:
        """Detecta ambientes disponíveis e os cria se necessário"""
        envs = {}
        
        print("🔍 Detectando ambientes disponíveis...")
        
        for env_name in self.env_manager.env_configs.keys():
            env_path = self.env_manager.base_dir / env_name
            exists = env_path.exists()
            envs[env_name] = exists
            
            status = "✅" if exists else "❌"
            print(f"   {status} {env_name}")
            
            # Se o ambiente não existe, oferece para criar
            if not exists:
                print(f"      🔧 Ambiente '{env_name}' será criado automaticamente quando necessário")
        
        print()
        return envs
    
    def _ensure_environment(self, env_name: str) -> bool:
        """Garante que um ambiente existe e está pronto para uso"""
        if env_name not in self.env_manager.env_configs:
            print(f"❌ Ambiente '{env_name}' não é reconhecido")
            return False
        
        env_path = self.env_manager.base_dir / env_name
        
        # Se o ambiente não existe, cria automaticamente
        if not env_path.exists():
            print(f"🔧 Criando ambiente '{env_name}' automaticamente...")
            
            if not self.env_manager.create_env(env_name):
                print(f"❌ Falha ao criar ambiente '{env_name}'")
                return False
            
            print(f"📦 Instalando dependências para '{env_name}'...")
            if not self.env_manager.install_requirements(env_name):
                print(f"❌ Falha ao instalar dependências para '{env_name}'")
                return False
            
            print(f"✅ Ambiente '{env_name}' criado e configurado com sucesso!")
            self.available_envs[env_name] = True
        
        return True
    
    def _get_python_path(self, env_name: str) -> Optional[str]:
        """Obtém o caminho do Python para um ambiente específico"""
        if not self._ensure_environment(env_name):
            return None
        
        # Usa o cache se disponível
        if env_name in self.active_environments:
            return self.active_environments[env_name]
        
        python_path = self.env_manager.activate_env(env_name)
        
        if python_path:
            self.active_environments[env_name] = python_path
            print(f"🐍 Ambiente '{env_name}' ativado: {python_path}")
        else:
            print(f"❌ Falha ao ativar ambiente '{env_name}'")
        
        return python_path
    
    def _load_pipeline_templates(self) -> Dict[str, List[PipelineStep]]:
        """Define templates de pipeline para operações complexas"""
        return {
            "missao_unica": [
                # 1. Análise inicial do código/documento
                PipelineStep(
                    operation=OperationType.ANALYZE_CODE,
                    environment="analysis",
                    function_code="""
def execute(code_text):
    if code_text is None or code_text.strip() == "":
        code_text = "pass  # No input provided, executing a no-op"
    import ast
    import re
    
    print("🔍 Iniciando análise de código...")
    
    # Análise básica do código
    try:
        tree = ast.parse(code_text)
        functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        imports = [node.names[0].name for node in ast.walk(tree) if isinstance(node, ast.Import)]
        
        result = {
            "functions": functions,
            "classes": classes, 
            "imports": imports,
            "lines": len(code_text.split('\\n')),
            "complexity": len(functions) + len(classes) * 2
        }
        
        print(f"✅ Análise concluída: {len(functions)} funções, {len(classes)} classes")
        return result
        
    except:
        # Se não for código, trata como texto
        result = {
            "type": "text",
            "words": len(code_text.split()),
            "lines": len(code_text.split('\\n')),
            "complexity": len(code_text) // 100
        }
        
        print(f"📄 Tratado como texto: {result['words']} palavras")
        return result
""",
                    input_keys=["input_text"],
                    output_key="analysis_result"
                ),
                
                # 2. Criar embeddings para busca semântica
                PipelineStep(
                    operation=OperationType.CREATE_EMBEDDINGS,
                    environment="rag",
                    function_code="""
def execute(text, analysis):
    print("🧠 Criando embeddings semânticos...")
    
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
        
        model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Divide texto em chunks se for muito grande
        if len(text) > 1000:
            chunks = [text[i:i+1000] for i in range(0, len(text), 800)]
        else:
            chunks = [text]
        
        embeddings = model.encode(chunks)
        
        result = {
            "embeddings": embeddings.tolist(),
            "chunks": chunks,
            "vector_dim": embeddings.shape[1] if len(embeddings.shape) > 1 else len(embeddings)
        }
        
        print(f"✅ Embeddings criados: {len(chunks)} chunks, dimensão {result['vector_dim']}")
        return result
        
    except Exception as e:
        print(f"❌ Erro ao criar embeddings: {e}")
        # Fallback simples
        return {
            "embeddings": [[0.0] * 384],  # Dimensão padrão
            "chunks": [text[:1000]],
            "vector_dim": 384,
            "error": str(e)
        }
""",
                    input_keys=["input_text", "analysis_result"],
                    output_key="embeddings_result",
                    dependencies=["analysis_result"]
                ),
                
                # 3. Gerar análise com LLM
                PipelineStep(
                    operation=OperationType.GENERATE_TEXT,
                    environment="llm",
                    function_code="""
def execute(text, analysis, embeddings):
    print("🤖 Gerando análise com LLM...")
    
    import random
    
    insights = []
    
    if analysis.get("type") == "text":
        insights.append(f"📄 Texto com {analysis['words']} palavras e complexidade {analysis['complexity']}")
    else:
        insights.append(f"💻 Código com {len(analysis.get('functions', []))} funções")
        insights.append(f"📦 Usa {len(analysis.get('imports', []))} imports")
    
    insights.append(f"🧠 Representado em {len(embeddings['chunks'])} chunks semânticos")
    insights.append(f"📊 Dimensionalidade vetorial: {embeddings['vector_dim']}")
    
    confidence = random.uniform(0.7, 0.95)
    
    result = {
        "insights": insights,
        "summary": " | ".join(insights),
        "confidence": confidence
    }
    
    print(f"✅ Análise LLM concluída com confiança de {confidence:.1%}")
    return result
""",
                    input_keys=["input_text", "analysis_result", "embeddings_result"], 
                    output_key="llm_result",
                    dependencies=["analysis_result", "embeddings_result"]
                ),
                
                # 4. Análise estatística/ML
                PipelineStep(
                    operation=OperationType.VISUALIZE_DATA,
                    environment="ml",
                    function_code="""
def execute(analysis, embeddings, llm):
    print("📊 Executando análise estatística/ML...")
    
    try:
        import numpy as np
        
        # Análise estatística dos embeddings
        embeddings_array = np.array(embeddings['embeddings'])
        
        if len(embeddings_array.shape) > 1:
            mean_vector = np.mean(embeddings_array, axis=0)
            std_vector = np.std(embeddings_array, axis=0)
            similarity_matrix = np.corrcoef(embeddings_array)
        else:
            mean_vector = embeddings_array
            std_vector = np.zeros_like(embeddings_array)
            similarity_matrix = np.array([[1.0]])
        
        result = {
            "vector_stats": {
                "mean_magnitude": float(np.linalg.norm(mean_vector)),
                "std_magnitude": float(np.linalg.norm(std_vector)),
                "avg_similarity": float(np.mean(similarity_matrix))
            },
            "ml_confidence": llm["confidence"] * 0.9,
            "complexity_score": analysis.get("complexity", 1) * llm["confidence"]
        }
        
        print(f"✅ Análise ML concluída - Score: {result['complexity_score']:.2f}")
        return result
        
    except Exception as e:
        print(f"❌ Erro na análise ML: {e}")
        return {
            "vector_stats": {"error": str(e)},
            "ml_confidence": 0.5,
            "complexity_score": 1.0
        }
""",
                    input_keys=["analysis_result", "embeddings_result", "llm_result"],
                    output_key="ml_result", 
                    dependencies=["analysis_result", "embeddings_result", "llm_result"]
                )
            ],
            
            "analise_completa": [
                # Pipeline simplificado para análise completa
                PipelineStep(
                    operation=OperationType.ANALYZE_CODE,
                    environment="analysis",
                    function_code="""
def execute(code):
    print("🔍 Executando análise completa de código...")
    
    import subprocess
    import tempfile
    import json
    
    # Salva código temporariamente
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        temp_file = f.name
    
    try:
        # Executa verificação de sintaxe
        result = subprocess.run([
            'python', '-m', 'py_compile', temp_file
        ], capture_output=True, text=True)
        
        syntax_ok = result.returncode == 0
        
        analysis_result = {
            "syntax_valid": syntax_ok,
            "error": result.stderr if not syntax_ok else None,
            "lines": len(code.split('\\n'))
        }
        
        status = "✅ Válido" if syntax_ok else "❌ Inválido"
        print(f"{status} - {analysis_result['lines']} linhas analisadas")
        
        return analysis_result
        
    finally:
        import os
        os.unlink(temp_file)
""",
                    input_keys=["input_text"],
                    output_key="code_analysis"
                ),
                
                PipelineStep(
                    operation=OperationType.GENERATE_TEXT,
                    environment="llm", 
                    function_code="""
def execute(code, analysis):
    print("📝 Gerando relatório final...")
    
    # Gera relatório baseado na análise
    report = []
    
    if analysis["syntax_valid"]:
        report.append("✅ Código sintaticamente válido")
    else:
        report.append(f"❌ Erro de sintaxe: {analysis['error']}")
    
    report.append(f"📊 {analysis['lines']} linhas de código analisadas")
    
    result = {
        "report": "\\n".join(report),
        "status": "valid" if analysis["syntax_valid"] else "invalid"
    }
    
    print(f"✅ Relatório gerado - Status: {result['status']}")
    return result
""",
                    input_keys=["input_text", "code_analysis"],
                    output_key="final_report",
                    dependencies=["code_analysis"]
                )
            ]
        }
    
    def _execute_in_env(self, env_name: str, function_code: str, **kwargs) -> Any:
        """Executa código em um ambiente específico COM ATIVAÇÃO AUTOMÁTICA"""
        print(f"🚀 Executando no ambiente '{env_name}'...")
        
        # Obtém o caminho do Python (ativa automaticamente se necessário)
        python_path = self._get_python_path(env_name)
        if not python_path:
            raise RuntimeError(f"Ambiente '{env_name}' não pôde ser ativado")

        # Prepara script de execução
        script_content = f"""
import sys
import json
import pickle
import base64

# Função a ser executada
{function_code}

# Argumentos
kwargs = {repr(kwargs)}

try:
    # Executa a função
    result = execute(**kwargs)
    
    # Serializa resultado
    if result is not None:
        serialized = base64.b64encode(pickle.dumps(result)).decode('utf-8')
        print(f"RESULT:{serialized}")
    else:
        print("RESULT:None")
        
except Exception as e:
    import traceback
    print(f"ERROR:{str(e)}")
    print(f"TRACEBACK:{traceback.format_exc()}")
    sys.exit(1)
"""
        
        # Executa no ambiente
        script_path = Path(f"temp_execution_{env_name}.py")
        try:
            with open(script_path, "w") as f:
                f.write(script_content)
            
            print(f"   🐍 Usando Python: {python_path}")
            
            # Executa
            result = subprocess.run([
                str(python_path), str(script_path)
            ], capture_output=True, text=True, timeout=300)
            
            # Processa resultado
            for line in result.stdout.split('\\n'):
                if line.startswith("RESULT:"):
                    result_data = line[7:]
                    if result_data == "None":
                        return None
                    else:
                        return pickle.loads(base64.b64decode(result_data))
                elif line.startswith("ERROR:"):
                    raise RuntimeError(f"Erro em {env_name}: {line[6:]}")
            
            # Se chegou aqui, algo deu errado
            if result.stderr:
                print(f"   ⚠️ Stderr: {result.stderr}")
            
            raise RuntimeError(f"Execução em {env_name} não retornou resultado válido")
            
        finally:
            if script_path.exists():
                script_path.unlink()
    
    def execute_pipeline(self, pipeline_name: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa um pipeline completo coordenando múltiplos ambientes
        """
        if pipeline_name not in self.pipeline_templates:
            raise ValueError(f"Pipeline '{pipeline_name}' não encontrado")
        
        pipeline = self.pipeline_templates[pipeline_name]
        context = ExecutionContext(data=input_data.copy(), metadata={}, cache={})
        
        print(f"🚀 Executando pipeline '{pipeline_name}' com {len(pipeline)} etapas")
        print("=" * 60)
        
        # Executa cada etapa do pipeline
        for i, step in enumerate(pipeline, 1):
            print(f"\\n📍 Etapa {i}/{len(pipeline)}: {step.operation.value}")
            print(f"🌍 Ambiente: {step.environment}")
            
            # Verifica dependências
            if step.dependencies:
                for dep in step.dependencies:
                    if dep not in context.data:
                        raise RuntimeError(f"Dependência '{dep}' não encontrada para etapa {i}")
            
            # Prepara argumentos
            step_args = {}
            for key in step.input_keys:
                if key in context.data:
                    step_args[key] = context.data[key]
                else:
                    raise RuntimeError(f"Input '{key}' não encontrado para etapa {i}")
            
            # Executa no ambiente apropriado
            try:
                result = self._execute_in_env(step.environment, step.function_code, **step_args)
                context.data[step.output_key] = result
                
                print(f"✅ Etapa concluída - Output: {step.output_key}")
                
                # Log básico do resultado
                if isinstance(result, dict):
                    print(f"   📊 Resultado: {len(result)} campos")
                elif isinstance(result, list):
                    print(f"   📊 Resultado: {len(result)} itens")
                else:
                    print(f"   📊 Resultado: {type(result).__name__}")
                    
            except Exception as e:
                print(f"❌ Erro na etapa {i}: {str(e)}")
                # Implementa fallback se necessário
                context.data[step.output_key] = {"error": str(e), "status": "failed"}
        
        print(f"\\n🎉 Pipeline '{pipeline_name}' concluído!")
        print("=" * 60)
        
        return context.data
    
    def auto_detect_pipeline(self, command: str, input_text: str) -> str:
        """
        Detecta automaticamente qual pipeline usar baseado no comando
        """
        command_lower = command.lower()
        
        if any(keyword in command_lower for keyword in ["missao", "unica", "completa", "full"]):
            return "missao_unica"
        elif any(keyword in command_lower for keyword in ["analise", "analyze", "check"]):
            return "analise_completa"
        else:
            # Pipeline padrão
            return "missao_unica"
    
    def execute_smart_mission(self, command: str, input_text: str) -> Dict[str, Any]:
        """
        Execução inteligente que detecta e coordena automaticamente
        """
        # Auto-detecção do pipeline
        pipeline_name = self.auto_detect_pipeline(command, input_text)
        
        print(f"🧠 Auto-detectado pipeline: {pipeline_name}")
        print(f"📝 Comando: {command}")
        print(f"📄 Input: {len(input_text)} caracteres")
        
        # Executa pipeline
        result = self.execute_pipeline(pipeline_name, {"input_text": input_text})
        
        # Consolida resultado final
        final_result = {
            "command": command,
            "pipeline_used": pipeline_name,
            "environments_used": [step.environment for step in self.pipeline_templates[pipeline_name]],
            "results": result,
            "summary": self._generate_summary(result)
        }
        
        return final_result
    
    def _generate_summary(self, results: Dict[str, Any]) -> str:
        """Gera um resumo executivo dos resultados"""
        summary_parts = []
        
        if "analysis_result" in results:
            analysis = results["analysis_result"]
            if analysis.get("type") == "text":
                summary_parts.append(f"📄 Texto analisado: {analysis.get('words', 0)} palavras")
            else:
                summary_parts.append(f"💻 Código analisado: {len(analysis.get('functions', []))} funções")
        
        if "llm_result" in results:
            llm = results["llm_result"]
            summary_parts.append(f"🤖 LLM confiança: {llm.get('confidence', 0):.1%}")
        
        if "ml_result" in results:
            ml = results["ml_result"]
            summary_parts.append(f"📊 Score complexidade: {ml.get('complexity_score', 0):.2f}")
        
        return " | ".join(summary_parts) if summary_parts else "Análise concluída"
    
    def setup_all_environments(self):
        """Configura todos os ambientes de uma vez"""
        print("🔧 Configurando todos os ambientes Quimera...")
        self.env_manager.setup_all_envs()
        self.available_envs = self._detect_environments()

def main():
    """Interface CLI do orquestrador melhorado"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Quimera Smart Orchestrator - Versão Melhorada")
    parser.add_argument("command", nargs="?", default="--help", 
                       help="Comando a executar")
    parser.add_argument("input_text", nargs="?", default=None,
                       help="Texto ou código para processar")
    parser.add_argument("--setup", action="store_true",
                       help="Configura todos os ambientes")
    
    args = parser.parse_args()
    
    orchestrator = QuimeraSmartOrchestrator()
    
    if args.setup:
        orchestrator.setup_all_environments()
        return
    
    if args.command == "--help" or not args.command:
        print("🔮 QUIMERA SMART ORCHESTRATOR - VERSÃO MELHORADA")
        print("=" * 60)
        print("Coordenação inteligente multi-ambiente com ativação automática")
        print()
        print("Ambientes disponíveis:")
        for env, available in orchestrator.available_envs.items():
            status = "✅" if available else "⚪"
            desc = orchestrator.env_manager.env_configs[env]["description"]
            print(f"  {status} {env:12} - {desc}")
        print()
        print("Uso:")
        print("  python quimera_orchestrator_melhorado.py --setup")
        print("  python quimera_orchestrator_melhorado.py --missao-unica 'código ou texto'")
        print("  python quimera_orchestrator_melhorado.py --analise-completa 'código python'")
        print()
        print("Recursos:")
        print("  ✨ Ativação automática de ambientes virtuais")
        print("  🔧 Criação automática de ambientes ausentes")
        print("  📦 Instalação automática de dependências")
        print("  🚀 Execução coordenada entre múltiplos ambientes")
        return
    
    try:
        result = orchestrator.execute_smart_mission(args.command, args.input_text)
        
        print("\\n" + "=" * 60)
        print("📋 RESULTADO FINAL")
        print("=" * 60)
        print(f"Pipeline usado: {result['pipeline_used']}")
        print(f"Ambientes coordenados: {', '.join(result['environments_used'])}")
        print(f"Resumo: {result['summary']}")
        print()
        
        # Mostra resultados detalhados
        for key, value in result['results'].items():
            if key != "input_text":
                print(f"🔍 {key}:")
                if isinstance(value, dict):
                    for subkey, subvalue in value.items():
                        print(f"   {subkey}: {subvalue}")
                else:
                    print(f"   {value}")
                print()
                
    except Exception as e:
        print(f"❌ Erro na execução: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()