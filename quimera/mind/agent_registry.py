"""
AgentRegistry — Catálogo central de agentes com metadados estendidos.

Fase 6: Enriquecido com especialidades, linguagens, tipos de erro, 
prioridades, capacidades e dependências.
"""
from typing import Any, Dict, List, Optional


# ──── Metadados estendidos (Fase 6) ─────────────────────────────────
_AGENT_METADATA: Dict[str, Dict[str, Any]] = {
    "AgenteFiscalCodigo": {
        "speciality": "Análise estática de código C",
        "languages": ["c"],
        "error_types": ["compilation_error", "syntax_error", "undefined_reference", "type_mismatch"],
        "priority": 90,
        "capabilities": ["static_analysis", "compilation_check", "linting"],
        "dependencies": ["gcc", "pycparser"],
    },
    "AgenteCritico": {
        "speciality": "Avaliação de fitness de patches",
        "languages": ["c", "python"],
        "error_types": ["buffer_overflow", "null_deref", "use_after_free"],
        "priority": 70,
        "capabilities": ["fitness_evaluation", "patch_ranking"],
        "dependencies": [],
    },
    "AgenteGerador": {
        "speciality": "Geração de patches via templates",
        "languages": ["c", "python", "go", "rust"],
        "error_types": ["buffer_overflow", "memory_leak", "format_string", "null_deref"],
        "priority": 75,
        "capabilities": ["template_generation", "patch_synthesis"],
        "dependencies": [],
    },
    "AgenteMestra": {
        "speciality": "Orquestração multi-agente",
        "languages": ["*"],
        "error_types": ["*"],
        "priority": 60,
        "capabilities": ["agent_orchestration", "workflow_coordination"],
        "dependencies": ["AgenteFiscalCodigo", "AgenteGerador", "AgenteCritico"],
    },
    "AgenteAutoCorrecao": {
        "speciality": "Correção automática de erros simples",
        "languages": ["c", "python"],
        "error_types": ["syntax_error", "missing_import", "undefined_variable", "indentation_error"],
        "priority": 85,
        "capabilities": ["auto_fix", "simple_patch"],
        "dependencies": [],
    },
    "AgenteKAN": {
        "speciality": "Kernel Adaptive Networks para patches",
        "languages": ["c", "python"],
        "error_types": ["buffer_overflow", "use_after_free", "race_condition"],
        "priority": 50,
        "capabilities": ["neural_patch", "adaptive_learning"],
        "dependencies": ["torch"],
    },
    "AgenteQuantico": {
        "speciality": "Otimização quântica (simulada)",
        "languages": ["c"],
        "error_types": ["buffer_overflow", "integer_overflow"],
        "priority": 40,
        "capabilities": ["quantum_optimization", "search_optimization"],
        "dependencies": [],
    },
    "AgenteDeConserto": {
        "speciality": "Rollback inteligente + repair",
        "languages": ["c", "python"],
        "error_types": ["all"],
        "priority": 65,
        "capabilities": ["rollback", "incremental_fix"],
        "dependencies": [],
    },
    "AgenteRejoinderRerank": {
        "speciality": "Reordenação de patches por relevância",
        "languages": ["*"],
        "error_types": ["all"],
        "priority": 55,
        "capabilities": ["reranking", "relevance_sorting"],
        "dependencies": [],
    },
    "AgenteRefinadorV3": {
        "speciality": "Refinamento iterativo v3",
        "languages": ["c", "python", "go", "rust"],
        "error_types": ["all"],
        "priority": 80,
        "capabilities": ["iterative_refinement", "multi_pass"],
        "dependencies": ["AgenteCritico"],
    },
    "AgenteRefinadorV4": {
        "speciality": "Refinamento iterativo v4",
        "languages": ["c", "python", "go", "rust"],
        "error_types": ["all"],
        "priority": 82,
        "capabilities": ["iterative_refinement", "multi_pass", "voting"],
        "dependencies": ["AgenteCritico", "AgenteRejoinderRerank"],
    },
    "AgenteBase": {
        "speciality": "Delegação ao GeneticPatchEngine (fallback)",
        "languages": ["*"],
        "error_types": ["all"],
        "priority": 30,
        "capabilities": ["genetic_evolution", "fallback"],
        "dependencies": ["GeneticPatchEngine"],
    },
    "AgenteSintetizador": {
        "speciality": "Síntese de patches de múltiplas fontes",
        "languages": ["*"],
        "error_types": ["all"],
        "priority": 45,
        "capabilities": ["multi_source_synthesis", "merge_patches"],
        "dependencies": [],
    },
    "IRepairAgent": {
        "speciality": "Interface de plugin SDK",
        "languages": ["*"],
        "error_types": ["all"],
        "priority": 20,
        "capabilities": ["plugin_interface", "extensible"],
        "dependencies": [],
    },
    "AgenteEstrategista": {
        "speciality": "Seleção de estratégia por tipo de erro",
        "languages": ["*"],
        "error_types": ["all"],
        "priority": 95,
        "capabilities": ["strategy_selection", "error_classification"],
        "dependencies": [],
    },
    "AgenteHistoriador": {
        "speciality": "Consulta de histórico para soluções similares",
        "languages": ["*"],
        "error_types": ["all"],
        "priority": 50,
        "capabilities": ["history_lookup", "similarity_search"],
        "dependencies": ["MemoryEngine"],
    },
    "AgenteConfiguradorDeKernel": {
        "speciality": "Configuração de kernel para sandbox",
        "languages": ["c"],
        "error_types": ["kernel_panic", "kernel_config"],
        "priority": 35,
        "capabilities": ["kernel_config", "sandbox_setup"],
        "dependencies": ["DockerBackend", "FirejailBackend"],
    },
    "AgenteDeFallback": {
        "speciality": "Fallback quando todos os outros falham",
        "languages": ["*"],
        "error_types": ["all"],
        "priority": 5,
        "capabilities": ["last_resort", "generic_fix"],
        "dependencies": [],
    },
    "PythonAgent": {
        "speciality": "Correção de erros Python",
        "languages": ["python"],
        "error_types": ["ModuleNotFoundError", "ImportError", "SyntaxError", "AttributeError", "TypeError"],
        "priority": 92,
        "capabilities": ["python_fix", "import_resolution"],
        "dependencies": [],
    },
    "GoAgent": {
        "speciality": "Correção de erros Go",
        "languages": ["go"],
        "error_types": ["compilation_error", "undefined_identifier", "type_mismatch"],
        "priority": 78,
        "capabilities": ["go_fix", "go_analysis"],
        "dependencies": ["go"],
    },
    "RustAgent": {
        "speciality": "Correção de erros Rust",
        "languages": ["rust"],
        "error_types": ["compilation_error", "borrow_check", "lifetime_error", "type_mismatch"],
        "priority": 75,
        "capabilities": ["rust_fix", "borrow_analysis"],
        "dependencies": ["rustc", "cargo"],
    },
    "AegisSecurityAgent": {
        "speciality": "AEGIS security scanning",
        "languages": ["c", "python", "go", "rust"],
        "error_types": ["cve", "security_hole", "crypto_weakness"],
        "priority": 88,
        "capabilities": ["security_scan", "cve_detection"],
        "dependencies": ["AEGIS"],
    },
    "AegisQuimeraAgent": {
        "speciality": "AEGIS CVE monitoring + Quimera integrado",
        "languages": ["c", "python"],
        "error_types": ["cve", "vulnerability"],
        "priority": 86,
        "capabilities": ["cve_monitor", "security_audit"],
        "dependencies": ["AEGIS", "CVE_DB"],
    },
    "AgenteKanValidador": {
        "speciality": "Validação formal com KAN",
        "languages": ["c"],
        "error_types": ["buffer_overflow", "use_after_free", "integer_overflow"],
        "priority": 58,
        "capabilities": ["formal_verification", "kan_validation"],
        "dependencies": ["KAN"],
    },
    "AgenteRevisorAssemble": {
        "speciality": "Revisão de assembly gerado",
        "languages": ["c"],
        "error_types": ["assembly_error", "register_mismatch"],
        "priority": 48,
        "capabilities": ["assembly_review", "register_analysis"],
        "dependencies": ["objdump", "gcc"],
    },
    "AgenteCheckLinux": {
        "speciality": "Verificação de compatibilidade Linux",
        "languages": ["c"],
        "error_types": ["kernel_compat", "syscall_error", "abi_mismatch"],
        "priority": 42,
        "capabilities": ["linux_check", "kernel_verify"],
        "dependencies": ["linux-headers"],
    },
    "AgenteAnalistaMult": {
        "speciality": "Análise multidimensional do codebase",
        "languages": ["*"],
        "error_types": ["all"],
        "priority": 52,
        "capabilities": ["multi_dim_analysis", "codebase_search"],
        "dependencies": [],
    },
}


# ──── Registry (mantido do original) ─────────────────────────────────
class AgentRegistry:
    """Catálogo de agentes com registro e busca por capacidades."""
    
    REGISTRY = {
        "AgenteFiscalCodigo":  {"handler": "quimera.agentes.agente_fiscal_codigo", "horizon": "H4", "description": "Análise fiscal de código C — detecta erros de compilação e estilo"},
        "AgenteCritico":       {"handler": "quimera.agentes.agente_critico", "horizon": "H4", "description": "Avalia criticamente patches gerados — fitness function humana"},
        "AgenteGerador":       {"handler": "quimera.agentes.agente_gerador", "horizon": "H4", "description": "Gera patches candidatos via templates"},
        "AgenteMestra":        {"handler": "quimera.agentes.agente_mestra", "horizon": "H4", "description": "Coordena múltiplos agentes de reparo — orquestração interna"},
        "AgenteEstrategista":  {"handler": "quimera.agentes.agente_estrategista", "horizon": "H2", "description": "Define estratégia de reparo baseada em histórico"},
        "AgenteHistoriador":   {"handler": "quimera.agentes.agente_historico", "horizon": "H2", "description": "Consulta histórico de soluções passadas"},
        "AgenteAutoCorrecao":  {"handler": "quimera.agentes.agente_autocorrecao", "horizon": "H4", "description": "Correção automática de erros simples"},
        "AgenteKAN":           {"handler": "quimera.agentes.agente_kan", "horizon": "H4", "description": "Kernel Adaptive Networks para patches"},
        "AgenteQuantico":      {"handler": "quimera.agentes.agente_quantico", "horizon": "H4", "description": "Otimização quântica de patches"},
        "AgenteConfiguradorDeKernel": {"handler": "quimera.agentes.agente_configurador", "horizon": "H1", "description": "Configura kernel para teste em sandbox"},
        "AgenteDeConserto":    {"handler": "quimera.agentes.agente_gestao_rollback", "horizon": "H4", "description": "Conserta erros usando rollback inteligente"},
        "AgenteDeFallback":    {"handler": "quimera.agentes.agente_fallback", "horizon": "H1", "description": "Fallback quando outros agentes falham"},
        "AgenteRejoinderRerank": {"handler": "quimera.agentes.agente_votoaste", "horizon": "H4", "description": "Reordena patches por relevância"},
        "AgenteKanValidador":  {"handler": "quimera.agentes.agente_kan_validador", "horizon": "H3", "description": "Valida patches com KAN + verificação formal"},
        "AgenteRevisorAssemble": {"handler": "quimera.agentes.agente_revisor_assembly", "horizon": "H3", "description": "Revisa assembly gerado por patches"},
        "AgenteRefinadorV3":   {"handler": "quimera.agentes.agente_transformador", "horizon": "H4", "description": "Refinamento iterativo de patches v3"},
        "AgenteRefinadorV4":   {"handler": "quimera.agentes.agente_evolutivo_de_codigo", "horizon": "H4", "description": "Refinamento iterativo de patches v4"},
        "AgenteCheckLinux":    {"handler": "quimera.agentes.agente_check_linux", "horizon": "H1", "description": "Verifica compatibilidade com Linux"},
        "GoAgent":             {"handler": "quimera.plugins.go_agent", "horizon": "H6", "description": "Agente especializado em Go"},
        "PythonAgent":         {"handler": "quimera.plugins.python_agent", "horizon": "H6", "description": "Agente especializado em Python"},
        "RustAgent":           {"handler": "quimera.plugins.rust_agent", "horizon": "H6", "description": "Agente especializado em Rust"},
        "AegisSecurityAgent":  {"handler": "quimera.aegis.aegis_security", "horizon": "H5", "description": "AEGIS security scanning"},
        "AegisQuimeraAgent":   {"handler": "quimera.quimera_aegis_integration", "horizon": "H5", "description": "AEGIS CVE monitoring"},
        "AgenteBase":          {"handler": "quimera.agentes.agente_base", "horizon": "H4", "description": "Classe base para todos os agentes — delega ao engine de evolução"},
        "AgenteAnalistaMult":  {"handler": "quimera.agentes.agente_analista", "horizon": "H2", "description": "Analista multidimensional — busca no codebase"},
        "AgenteSintetizador":  {"handler": "quimera.agentes.agente_sintetizador", "horizon": "H4", "description": "Sintetiza patches de múltiplas IAs"},
        "IRepairAgent":        {"handler": "quimera.plugins.plugin_sdk", "horizon": "H4", "description": "Interface de reparo — plugin SDK"},
        "MyRustAgent":         {"handler": "quimera.plugins.rust_custom", "horizon": "H6", "description": "Agente Rust customizado via plugin SDK"},
    }
    
    @classmethod
    def count(cls) -> int:
        return len(cls.REGISTRY)
    
    @classmethod
    def list_agents(cls) -> List[Dict]:
        return [
            {"name": name, "handler": info["handler"], "horizon": info["horizon"], 
             "description": info["description"]}
            for name, info in cls.REGISTRY.items()
        ]
    
    @classmethod
    def get_handler(cls, name: str) -> Optional[str]:
        entry = cls.REGISTRY.get(name)
        return entry["handler"] if entry else None
    
    @classmethod
    def get_horizon(cls, name: str) -> Optional[str]:
        entry = cls.REGISTRY.get(name)
        return entry["horizon"] if entry else None
    
    # ──── Métodos estendidos (Fase 6) ─────────────────────────────
    
    @classmethod
    def get_metadata(cls, agent_name: str) -> Optional[Dict[str, Any]]:
        """Retorna metadados estendidos do agente."""
        return _AGENT_METADATA.get(agent_name)
    
    @classmethod
    def find_by_error_type(cls, error_type: str, language: Optional[str] = None) -> List[str]:
        """Encontra agentes capazes de resolver um tipo de erro, ordenados por prioridade."""
        candidates = []
        for name, meta in _AGENT_METADATA.items():
            types = meta.get("error_types", [])
            if error_type in types or "all" in types or "*" in types:
                langs = meta.get("languages", [])
                if language is None or language in langs or "*" in langs:
                    candidates.append((name, meta.get("priority", 0)))
        candidates.sort(key=lambda x: -x[1])
        return [name for name, _ in candidates]
    
    @classmethod
    def find_by_capability(cls, capability: str) -> List[str]:
        """Encontra agentes com uma capacidade específica."""
        return [name for name, meta in _AGENT_METADATA.items()
                if capability in meta.get("capabilities", [])]
    
    @classmethod
    def find_by_language(cls, language: str) -> List[str]:
        """Encontra agentes especializados em uma linguagem."""
        return [name for name, meta in _AGENT_METADATA.items()
                if language in meta.get("languages", []) or "*" in meta.get("languages", [])]
    
    @classmethod
    def get_all_metadata(cls) -> Dict[str, Dict[str, Any]]:
        """Retorna todos os metadados estendidos."""
        return dict(_AGENT_METADATA)
