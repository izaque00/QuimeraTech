#!/usr/bin/env python3
"""
QUIMERA MASTER COORDINATOR
Coordenador mestre que integra todos os sistemas de forma transparente
"""
import os
import sys
import asyncio
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime

# Adiciona o diretório atual ao path
sys.path.append(str(Path(__file__).parent))

# Sistema inteligente de importação e coordenação
try:
    from quimera.quimera_smart_imports import enable_smart_imports, disable_smart_imports, smart_execute
    from quimera.quimera_orchestrator import QuimeraSmartOrchestrator
    from quimera.quimera_hybrid_engine import QuimeraHybridEngine
    SMART_SYSTEMS_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Sistemas inteligentes não encontrados: {e}")
    SMART_SYSTEMS_AVAILABLE = False

# Imports dos módulos clássicos do Quimera
try:
    # DiagnosticoSistemico: módulo pendente de implementação
    # CorretorUnificado: módulo pendente de implementação
    CLASSIC_QUIMERA_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Módulos clássicos Quimera não encontrados: {e}")
    CLASSIC_QUIMERA_AVAILABLE = False

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class QuimeraMasterCoordinator:
    """
    Coordenador mestre que unifica todos os sistemas do Quimera
    """
    
    def __init__(self):
        self.orchestrator = None
        self.hybrid_engine = None
        self.smart_imports_active = False
        
        # Inicializa sistemas inteligentes se disponíveis
        if SMART_SYSTEMS_AVAILABLE:
            self.orchestrator = QuimeraSmartOrchestrator()
            self.hybrid_engine = QuimeraHybridEngine()
        
        # Detecta capacidades do sistema
        self.capabilities = self._detect_capabilities()
    
    def _detect_capabilities(self) -> Dict[str, bool]:
        """Detecta todas as capacidades disponíveis"""
        caps = {
            "classic_quimera": CLASSIC_QUIMERA_AVAILABLE,
            "smart_systems": SMART_SYSTEMS_AVAILABLE,
            "multi_environment": False,
            "hybrid_execution": False,
            "intelligent_imports": False
        }
        
        if SMART_SYSTEMS_AVAILABLE:
            caps["intelligent_imports"] = True
            caps["hybrid_execution"] = True
            
            # Verifica ambientes disponíveis
            if self.orchestrator:
                available_envs = sum(1 for available in self.orchestrator.available_envs.values() if available)
                caps["multi_environment"] = available_envs > 0
        
        return caps
    
    def execute_with_smart_coordination(self, task_type: str, *args, **kwargs) -> Any:
        """
        Executa tarefas com coordenação inteligente automática
        """
        if not SMART_SYSTEMS_AVAILABLE:
            raise RuntimeError("Sistemas inteligentes não disponíveis")
        
        # Ativa importações inteligentes
        enable_smart_imports()
        
        try:
            if task_type == "missao_unica":
                return self._execute_unified_mission(*args, **kwargs)
            
            elif task_type == "hybrid_task":
                return self._execute_hybrid_task(*args, **kwargs)
            
            elif task_type == "smart_analysis":
                return self._execute_smart_analysis(*args, **kwargs)
            
            elif task_type == "auto_detect":
                return self._execute_auto_detect(*args, **kwargs)
            
            else:
                raise ValueError(f"Tipo de tarefa não reconhecido: {task_type}")
        
        finally:
            disable_smart_imports()
    
    def _execute_unified_mission(self, input_text: str, mission_type: str = "auto") -> Dict[str, Any]:
        """Executa missão unificada com detecção automática"""
        
        print("🎯 MISSÃO UNIFICADA QUIMERA")
        print("=" * 60)
        print(f"📝 Input: {len(input_text)} caracteres")
        print(f"🎯 Tipo: {mission_type}")
        
        # Auto-detecta tipo de missão se necessário
        if mission_type == "auto":
            mission_type = self._auto_detect_mission_type(input_text)
            print(f"🧠 Tipo detectado: {mission_type}")
        
        # Executa coordenação
        result = self.orchestrator.execute_smart_mission(f"--{mission_type}", input_text)
        
        # Adiciona metadados
        result["coordination_metadata"] = {
            "smart_imports_used": True,
            "environments_coordinated": len(result.get("environments_used", [])),
            "execution_mode": "unified_mission",
            "auto_detected": mission_type != "auto"
        }
        
        return result
    
    def _execute_hybrid_task(self, task_definition: Dict[str, Any]) -> Dict[str, Any]:
        """Executa tarefa híbrida coordenada"""
        
        print("🔄 TAREFA HÍBRIDA")
        print("=" * 60)
        
        # Valida definição da tarefa
        required_keys = ["name", "steps"]
        if not all(key in task_definition for key in required_keys):
            raise ValueError(f"Definição de tarefa deve conter: {required_keys}")
        
        # Executa no motor híbrido
        result = self.hybrid_engine.execute_hybrid_task(task_definition)
        
        # Adiciona metadados de coordenação
        result["coordination_metadata"] = {
            "execution_mode": "hybrid_task",
            "environments_used": list(set(step["env"] for step in task_definition["steps"])),
            "coordination_successful": result["success"]
        }
        
        return result
    
    def _execute_smart_analysis(self, target: str, analysis_type: str = "comprehensive") -> Dict[str, Any]:
        """Executa análise inteligente de código/texto"""
        
        print("🔍 ANÁLISE INTELIGENTE")
        print("=" * 60)
        
        # Determina se é arquivo ou texto direto
        if os.path.exists(target):
            with open(target, 'r', encoding='utf-8') as f:
                content = f.read()
            analysis_target = "file"
        else:
            content = target
            analysis_target = "text"
        
        # Cria tarefa híbrida para análise
        task = {
            "name": f"smart_analysis_{analysis_type}",
            "steps": [
                {
                    "env": "analysis",
                    "code": f"""
import ast
import re

content = '''{content}'''

# Análise estática
try:
    tree = ast.parse(content)
    is_code = True
    
    functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    imports = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend([alias.name for alias in node.names])
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or '')
    
    static_analysis = {{
        'type': 'python_code',
        'functions': functions,
        'classes': classes,
        'imports': imports,
        'lines': len(content.split('\\n')),
        'complexity_score': len(functions) * 2 + len(classes) * 3
    }}
    
except SyntaxError:
    is_code = False
    words = content.split()
    static_analysis = {{
        'type': 'text',
        'words': len(words),
        'lines': len(content.split('\\n')),
        'characters': len(content),
        'estimated_reading_time': len(words) / 200  # palavras por minuto
    }}
""",
                    "outputs": ["static_analysis", "content"]
                }
            ]
        }
        
        # Adiciona análise semântica se RAG disponível
        if self.orchestrator.available_envs.get("rag", False):
            task["steps"].append({
                "env": "rag",
                "code": """
from sentence_transformers import SentenceTransformer

# Análise semântica
model = SentenceTransformer('all-MiniLM-L6-v2')

# Divide em chunks para análise
if len(content) > 1000:
    chunks = [content[i:i+500] for i in range(0, len(content), 400)]
else:
    chunks = [content]

embeddings = model.encode(chunks)

semantic_analysis = {
    'chunks_count': len(chunks),
    'embedding_dimension': embeddings.shape[1] if len(embeddings.shape) > 1 else len(embeddings),
    'semantic_complexity': float(embeddings.std()) if hasattr(embeddings, 'std') else 0.0
}
""",
                "inputs": ["content"],
                "outputs": ["semantic_analysis"]
            })
        
        # Adiciona insights com LLM se disponível
        if self.orchestrator.available_envs.get("llm", False):
            task["steps"].append({
                "env": "llm",
                "code": """
# Gera insights inteligentes
insights = []

if static_analysis['type'] == 'python_code':
    insights.append(f"Código Python com {len(static_analysis['functions'])} funções")
    
    if static_analysis['complexity_score'] > 10:
        insights.append("Código de alta complexidade - considere refatoração")
    elif static_analysis['complexity_score'] > 5:
        insights.append("Código de complexidade moderada")
    else:
        insights.append("Código simples e direto")
    
    if len(static_analysis['imports']) > 10:
        insights.append("Muitas dependências - pode impactar performance")
    
else:
    insights.append(f"Texto com {static_analysis['words']} palavras")
    
    reading_time = static_analysis.get('estimated_reading_time', 0)
    if reading_time > 10:
        insights.append("Texto longo - considere dividir em seções")
    else:
        insights.append("Texto de tamanho adequado para leitura")

# Adiciona insights semânticos se disponível
if 'semantic_analysis' in globals():
    if semantic_analysis['semantic_complexity'] > 0.5:
        insights.append("Alta diversidade semântica - conteúdo variado")
    else:
        insights.append("Conteúdo semanticamente coeso")

intelligent_summary = {
    'insights': insights,
    'recommendations': [],
    'overall_assessment': 'Análise concluída com sucesso'
}
""",
                "inputs": ["static_analysis"],
                "outputs": ["intelligent_summary"]
            })
        
        # Executa análise híbrida
        result = self.hybrid_engine.execute_hybrid_task(task)
        
        # Consolida resultado
        analysis_result = {
            "target": target,
            "target_type": analysis_target,
            "analysis_type": analysis_type,
            "static_analysis": result["shared_state"].get("static_analysis", {}),
            "semantic_analysis": result["shared_state"].get("semantic_analysis", {}),
            "intelligent_summary": result["shared_state"].get("intelligent_summary", {}),
            "coordination_metadata": {
                "environments_used": [step["env"] for step in task["steps"]],
                "analysis_successful": result["success"]
            }
        }
        
        return analysis_result
    
    def _execute_auto_detect(self, input_data: Any, context: Dict = None) -> Dict[str, Any]:
        """Detecção automática e execução da melhor estratégia"""
        
        print("🧠 DETECÇÃO AUTOMÁTICA")
        print("=" * 60)
        
        # Analisa input para determinar estratégia
        if isinstance(input_data, str):
            if os.path.exists(input_data):
                # É um arquivo
                strategy = "file_analysis"
                return self._execute_smart_analysis(input_data, "comprehensive")
            
            elif len(input_data) > 100 and ("def " in input_data or "class " in input_data):
                # É código Python
                strategy = "code_analysis"
                return self._execute_smart_analysis(input_data, "code_focused")
            
            else:
                # É texto para processamento
                strategy = "text_processing"
                return self._execute_unified_mission(input_data, "missao_unica")
        
        elif isinstance(input_data, dict) and "steps" in input_data:
            # É definição de tarefa híbrida
            strategy = "hybrid_execution"
            return self._execute_hybrid_task(input_data)
        
        else:
            raise ValueError(f"Tipo de input não suportado para auto-detecção: {type(input_data)}")
    
    def _auto_detect_mission_type(self, input_text: str) -> str:
        """Detecta automaticamente o tipo de missão"""
        
        # Análise heurística do input
        if "def " in input_text or "class " in input_text or "import " in input_text:
            return "analise_completa"
        
        elif len(input_text.split()) > 50:
            return "missao_unica"
        
        else:
            return "missao_unica"
    
    def get_system_status(self) -> Dict[str, Any]:
        """Retorna status completo do sistema"""
        
        status = {
            "timestamp": datetime.now().isoformat(),
            "capabilities": self.capabilities,
            "classic_modules": {},
            "smart_systems": {},
            "environments": {},
            "overall_health": "unknown"
        }
        
        # Status dos módulos clássicos
        if CLASSIC_QUIMERA_AVAILABLE:
            classic_modules = [
                ("DiagnosticoSistemico", "quimera.utils.diagnostico_sistemico"),
                ("CorretorUnificado", "quimera.utils.corretor_unificado"),
                ("MemoriaEvolutiva", "quimera.utils.memoria_evolutiva"),
                ("FallbackLLM", "quimera.utils.fallback_llm"),
                ("FeedbackLoop", "quimera.utils.feedback_loop")
            ]
            
            for module_name, module_path in classic_modules:
                try:
                    __import__(module_path)
                    status["classic_modules"][module_name] = "active"
                except Exception as e:
                    status["classic_modules"][module_name] = f"limited: {str(e)[:30]}"
        
        # Status dos sistemas inteligentes
        if SMART_SYSTEMS_AVAILABLE:
            status["smart_systems"] = {
                "orchestrator": "active" if self.orchestrator else "inactive",
                "hybrid_engine": "active" if self.hybrid_engine else "inactive",
                "smart_imports": "available"
            }
            
            # Status dos ambientes
            if self.orchestrator:
                status["environments"] = self.orchestrator.available_envs
        
        # Avaliação geral
        active_capabilities = sum(1 for cap in self.capabilities.values() if cap)
        total_capabilities = len(self.capabilities)
        
        if active_capabilities == total_capabilities:
            status["overall_health"] = "excellent"
        elif active_capabilities >= total_capabilities * 0.7:
            status["overall_health"] = "good"
        elif active_capabilities >= total_capabilities * 0.4:
            status["overall_health"] = "limited"
        else:
            status["overall_health"] = "poor"
        
        return status

# Instância global do coordenador
_master_coordinator = QuimeraMasterCoordinator()

def get_coordinator() -> QuimeraMasterCoordinator:
    """Retorna instância do coordenador mestre"""
    return _master_coordinator

def execute_intelligent_task(task_type: str, *args, **kwargs) -> Any:
    """Interface pública para execução de tarefas inteligentes"""
    return _master_coordinator.execute_with_smart_coordination(task_type, *args, **kwargs)

def get_system_capabilities() -> Dict[str, bool]:
    """Retorna capacidades do sistema"""
    return _master_coordinator.capabilities

def is_smart_system_available() -> bool:
    """Verifica se sistema inteligente está disponível"""
    return _master_coordinator.capabilities["smart_systems"]

# ===============================================================
# BACKWARD COMPATIBILITY - Mantém compatibilidade total
# ===============================================================

def main():
    """Função principal com compatibilidade total"""
    
    coordinator = get_coordinator()
    
    if len(sys.argv) < 2:
        print_enhanced_help(coordinator)
        return
    
    comando = sys.argv[1].lower()
    args = sys.argv[2:] if len(sys.argv) > 2 else []
    
    # Comandos clássicos (compatibilidade total)
    if comando in ['--help', '-h', 'help']:
        print_enhanced_help(coordinator)
        
    elif comando == 'diagnostico' and CLASSIC_QUIMERA_AVAILABLE:
        executar_diagnostico_classico(args)
        
    elif comando == 'corrigir' and CLASSIC_QUIMERA_AVAILABLE:
        executar_correcao_classica(args)
        
    elif comando == 'status':
        executar_status_completo(coordinator)
        
    elif comando == 'version':
        print("🔮 Quimera Unified v2.0.0 - Master Coordination Edition")
        
    # Comandos inteligentes (novos)
    elif comando == '--missao-unica' and is_smart_system_available():
        executar_missao_unica(args)
        
    elif comando == '--analise-inteligente' and is_smart_system_available():
        executar_analise_inteligente(args)
        
    elif comando == '--setup-ambientes':
        executar_setup_ambientes()
        
    elif comando == '--auto-detect' and is_smart_system_available():
        executar_auto_detect(args)
        
    else:
        print(f"❌ Comando desconhecido: {comando}")
        print_enhanced_help(coordinator)

def print_enhanced_help(coordinator: QuimeraMasterCoordinator):
    """Ajuda melhorada que mostra todas as capacidades"""
    
    print("""
🔮 QUIMERA UNIFIED - Master Coordination System

COMANDOS CLÁSSICOS (Compatibilidade Total):""")
    
    if coordinator.capabilities["classic_quimera"]:
        print("""    diagnostico         Diagnóstico sistêmico
    corrigir <arquivo>  Correção de arquivos
    status              Status do sistema
    version             Versão do Quimera""")
    else:
        print("    ❌ Módulos clássicos não disponíveis")
    
    print("""
COMANDOS INTELIGENTES (Novos):""")
    
    if coordinator.capabilities["smart_systems"]:
        print("""    --missao-unica <input>      Coordenação automática multi-ambiente
    --analise-inteligente <alvo> Análise híbrida de código/texto
    --auto-detect <input>       Detecção automática + execução
    --setup-ambientes           Configura ambientes automaticamente""")
    else:
        print("    ❌ Sistemas inteligentes não disponíveis")
    
    print(f"""
CAPACIDADES ATIVAS:""")
    
    for capability, active in coordinator.capabilities.items():
        status = "✅" if active else "❌"
        print(f"    {capability:<20} {status}")
    
    print(f"""
AMBIENTES DISPONÍVEIS:""")
    
    if coordinator.orchestrator:
        for env, available in coordinator.orchestrator.available_envs.items():
            status = "✅" if available else "❌"
            print(f"    {env:<12} {status}")
    else:
        print("    ❌ Sistema de ambientes não inicializado")

def executar_diagnostico_classico(args):
    """Executa diagnóstico clássico"""
    print("🔍 Executando Diagnóstico Sistêmico Clássico")
    
    try:
        diretorio = args[0] if args else "."
        
        async def run_diagnostic():
            diagnostico = DiagnosticoSistemico()
            resultado = await diagnostico.executar_diagnostico_completo()
            return resultado
        
        resultado = asyncio.run(run_diagnostic())
        
        print("\n📊 RESULTADOS:")
        status = resultado.get('status', 'desconhecido')
        if status == 'ok':
            print("✅ Sistema em ordem!")
        elif status == 'aviso':
            print("⚠️ Sistema com avisos")
        else:
            print("❌ Sistema com problemas")
        
        print("✅ Diagnóstico concluído!")
        
    except Exception as e:
        print(f"❌ Erro no diagnóstico: {e}")

def executar_correcao_classica(args):
    """Executa correção clássica"""
    if not args:
        print("❌ Especifique um arquivo ou diretório para corrigir")
        return
    
    arquivo = args[0]
    print(f"🔧 Corrigindo: {arquivo}")
    
    try:
        if not os.path.exists(arquivo):
            print(f"❌ Arquivo não encontrado: {arquivo}")
            return
        
        corretor = CorretorUnificado()
        
        if os.path.isdir(arquivo):
            resultados = corretor.corrigir_diretorio(arquivo)
            total = len(resultados)
            sucessos = sum(1 for r in resultados if r.sucesso)
            print(f"Total: {total}, Sucessos: {sucessos}")
        else:
            resultado = corretor.corrigir_arquivo(arquivo)
            if resultado.sucesso:
                print("✅ Correção bem-sucedida")
            else:
                print("❌ Correção falhou")
        
        print("✅ Correção concluída!")
        
    except Exception as e:
        print(f"❌ Erro na correção: {e}")

def executar_status_completo(coordinator):
    """Status completo do sistema"""
    status = coordinator.get_system_status()
    
    print("📊 STATUS QUIMERA UNIFIED")
    print("=" * 60)
    
    print(f"\n🏥 SAÚDE GERAL: {status['overall_health'].upper()}")
    
    print(f"\n🔧 MÓDULOS CLÁSSICOS:")
    for module, status_info in status["classic_modules"].items():
        icon = "✅" if status_info == "active" else "⚠️"
        print(f"    {icon} {module}: {status_info}")
    
    print(f"\n🧠 SISTEMAS INTELIGENTES:")
    for system, status_info in status["smart_systems"].items():
        icon = "✅" if status_info == "active" else "❌"
        print(f"    {icon} {system}: {status_info}")
    
    print(f"\n🌍 AMBIENTES:")
    for env, available in status["environments"].items():
        icon = "✅" if available else "❌"
        print(f"    {icon} {env}")
    
    print(f"\n📅 Verificado em: {status['timestamp']}")

def executar_missao_unica(args):
    """Executa missão única inteligente"""
    if not args:
        print("❌ Especifique input para missão única")
        return
    
    input_text = " ".join(args)
    
    try:
        result = execute_intelligent_task("missao_unica", input_text)
        
        print("🎉 MISSÃO CONCLUÍDA!")
        print(f"Pipeline: {result.get('pipeline_used', 'N/A')}")
        print(f"Ambientes: {', '.join(result.get('environments_used', []))}")
        
    except Exception as e:
        print(f"❌ Erro na missão: {e}")

def executar_analise_inteligente(args):
    """Executa análise inteligente"""
    if not args:
        print("❌ Especifique alvo para análise")
        return
    
    target = args[0]
    
    try:
        result = execute_intelligent_task("smart_analysis", target)
        
        print("🔍 ANÁLISE CONCLUÍDA!")
        print(f"Tipo: {result.get('target_type', 'N/A')}")
        print(f"Ambientes usados: {len(result.get('coordination_metadata', {}).get('environments_used', []))}")
        
    except Exception as e:
        print(f"❌ Erro na análise: {e}")

def executar_setup_ambientes():
    """Configura ambientes automaticamente"""
    print("🚀 Configurando ambientes...")
    
    try:
        from quimera.quimera_env_manager import QuimeraEnvManager
        manager = QuimeraEnvManager()
        manager.setup_all_envs()
        print("✅ Ambientes configurados!")
        
    except ImportError:
        print("❌ Gerenciador de ambientes não encontrado")
    except Exception as e:
        print(f"❌ Erro na configuração: {e}")

def executar_auto_detect(args):
    """Executa detecção automática"""
    if not args:
        print("❌ Especifique input para auto-detecção")
        return
    
    input_data = " ".join(args)
    
    try:
        result = execute_intelligent_task("auto_detect", input_data)
        print("🧠 AUTO-DETECÇÃO CONCLUÍDA!")
        print(f"Resultado: {type(result).__name__}")
        
    except Exception as e:
        print(f"❌ Erro na auto-detecção: {e}")

if __name__ == "__main__":
    main()