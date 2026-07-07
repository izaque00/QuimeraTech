import logging
import re
import asyncio
import json
from typing import List, Optional, Dict, Any

# Importações de componentes do sistema Quimera
from quimera.quadro_negro import QuadroNegro
try:
    from quimera.agentes.roteador_modelos import RoteadorModelos
except ImportError:
    RoteadorModelos = None  # RoteadorModelos não disponível
from quimera import config

# Importações do sistema AEGIS de segurança avançada
try:
    from quimera.aegis.aegis_core import AegisCore, AegisMode
    from quimera.aegis.defensive_tokens import DefensiveTokenManager, SecurityLevel
    from quimera.aegis.dual_llm_pattern import DualLLMSecurityPattern, SecurityContext
    from quimera.aegis.validation_pipeline import ValidationPipeline
except ImportError:
    AegisCore = None
    AegisMode = None
    DefensiveTokenManager = None
    SecurityLevel = None
    DualLLMSecurityPattern = None
    SecurityContext = None
    ValidationPipeline = None

# Configuração do logger para este módulo
logger = logging.getLogger(__name__)

class AgenteMestra:
    """
    Agente Mestra, a autoridade final no processo de reparo.
    É responsável pelo julgamento final e consenso entre os patches candidatos,
    selecionando a solução mais robusta e confiável para ser aplicada.
    """

    def __init__(self, quadro_negro: QuadroNegro, enable_aegis: bool = True):
        """
        Inicializa a AgenteMestra com proteção avançada AEGIS.

        Args:
            quadro_negro (QuadroNegro): A instância do Quadro Negro para comunicação.
            enable_aegis (bool): Se deve ativar proteção AEGIS avançada.
        """
        self.quadro_negro = quadro_negro
        self.roteador = RoteadorModelos() if RoteadorModelos is not None else None
        
        # Inicializar sistema AEGIS de segurança avançada
        self.aegis_core = None
        self.defensive_tokens = None
        self.dual_llm_security = None
        self.validation_pipeline = None
        
        if enable_aegis and AegisCore is not None:
            try:
                # Inicializar núcleo AEGIS em modo avançado
                self.aegis_core = AegisCore(mode=AegisMode.ADVANCED)
                
                # Registrar este agente para proteção
                self.aegis_core.register_agent(self)
                
                # Inicializar componentes de segurança específicos
                if DefensiveTokenManager:
                    self.defensive_tokens = DefensiveTokenManager()
                    
                if DualLLMSecurityPattern:
                    self.dual_llm_security = DualLLMSecurityPattern()
                    
                if ValidationPipeline:
                    self.validation_pipeline = ValidationPipeline()
                
                # Ativar AEGIS
                if self.aegis_core.initialize():
                    logger.info("🛑️ AgenteMestra protegida pelo sistema AEGIS avançado")
                else:
                    logger.warning("⚠️ AEGIS não pôde ser inicializado - executando sem proteção avançada")
                    
            except Exception as e:
                logger.warning(f"⚠️ Erro ao inicializar AEGIS: {e} - executando sem proteção avançada")
                self.aegis_core = None
        else:
            logger.info("🚫 AgenteMestra executando sem proteção AEGIS")

        # Inicializar LLM com roteador de modelos
        if self.roteador:
            agentes_selecionados = self.roteador.selecionar_agentes_para_tarefa(
                habilidade_requerida="votacao_final_consenso",
                quantidade=1
            )
            if not agentes_selecionados:
                raise ValueError("AgenteMestra não pôde ser inicializada: Nenhum modelo disponível para 'votacao_final_consenso'.")

            agente_principal = agentes_selecionados[0]
            self.llm_cliente = agente_principal["cliente_llm"]
            self.nome_modelo = agente_principal["nome"]
        else:
            # Fallback se não houver roteador
            self.llm_cliente = None
            self.nome_modelo = "fallback_model"
            logger.warning("⚠️ Roteador de modelos não disponível - AgenteMestra em modo limitado")

        logger.info(f"🎆 AgenteMestra inicializada com sucesso. Modelo: '{self.nome_modelo}', AEGIS: {'Ativo' if self.aegis_core else 'Inativo'}")

    def _criar_prompt_julgamento(self, patches_candidatos: List[Dict[str, Any]], analise_causa_raiz: str, log_erro: str) -> str:
        """Cria um prompt detalhado e protegido para o julgamento final."""
        candidatos_str = ""
        for i, candidato in enumerate(patches_candidatos):
            candidatos_str += f"""
---
**CANDIDATO {i + 1}**
*   **Agente(s) Gerador(es):** {candidato.get('agentes_geradores', 'N/A')}
*   **Score de Avaliação (Crítico):** {candidato.get('score_critico', 'N/A')}
*   **Comentário do Crítico:** {candidato.get('comentario_critico', 'N/A')}

**Conteúdo do Patch:**
```diff
{candidato['patch_content']}
```"""

        # Prompt base
        base_prompt = f"""
Você é a Agente Mestra, a autoridade final e a Engenheira de Qualidade de Software mais experiente do kernel Linux. Sua tarefa é realizar o julgamento final entre os patches candidatos.

Contexto do Problema Original:
Análise da Causa Raiz: {analise_causa_raiz}
Log de Erro: {log_erro}

Patches Candidatos para Julgamento:
{candidatos_str}

Sua Missão de Julgamento:
1. Analise o Contexto Completo: Considere o problema original, a análise do especialista e a avaliação prévia de cada patch.
2. Compare as Soluções: Avalie qual patch oferece a solução mais elegante, segura, eficiente e robusta. Qual deles tem menos probabilidade de introduzir efeitos colaterais?
3. Faça a Escolha Final: Selecione UM e apenas UM patch como o vencedor.
4. Justifique sua Decisão: Forneça uma justificativa clara e técnica para sua escolha.

Formato da Resposta:
Sua resposta DEVE ser um objeto JSON com as seguintes chaves:
{{
    "indice_vencedor": "O número (integer) do patch vencedor (começando em 1).",
    "justificativa_da_escolha": "Uma explicação detalhada e técnica do porquê este patch é superior aos outros."
}}
"""
        
        # Aplicar proteção AEGIS se disponível
        if self.defensive_tokens:
            try:
                # Aplicar tokens defensivos para proteção contra injeção de prompt
                protected_prompt = self.defensive_tokens.apply_defensive_protection(
                    base_prompt,
                    SecurityLevel.HIGH,
                    context={"operation": "patch_judgment", "agent": "AgenteMestra"}
                )
                logger.debug("🛑️ Prompt protegido com tokens defensivos AEGIS")
                return protected_prompt
            except Exception as e:
                logger.warning(f"⚠️ Erro ao aplicar proteção defensiva: {e} - usando prompt base")
        
        return base_prompt

    async def _validar_patches_aegis(self, patches_candidatos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Valida patches usando pipeline AEGIS antes do julgamento."""
        if not self.validation_pipeline:
            return patches_candidatos
        
        try:
            patches_validados = []
            for i, patch in enumerate(patches_candidatos):
                logger.debug(f"🔍 AEGIS validando patch candidato {i+1}...")
                
                # Validar conteúdo do patch
                validation_result = await self.validation_pipeline.validate_code_async(
                    patch.get('patch_content', ''),
                    context={"patch_index": i, "source": "patch_candidate"}
                )
                
                if validation_result.get('is_safe', True):
                    patches_validados.append(patch)
                    logger.debug(f"✅ Patch {i+1} aprovado na validação AEGIS")
                else:
                    logger.warning(f"⚠️ Patch {i+1} rejeitado pelo AEGIS: {validation_result.get('reason', 'Falha de segurança')}")
            
            logger.info(f"🛑️ AEGIS: {len(patches_validados)}/{len(patches_candidatos)} patches aprovados na validação")
            return patches_validados
            
        except Exception as e:
            logger.error(f"❌ Erro na validação AEGIS: {e} - prosseguindo sem validação")
            return patches_candidatos
    
    async def _executar_dual_llm_judgment(self, prompt: str) -> str:
        """Executa julgamento usando padrão Dual LLM para maior segurança."""
        if not self.dual_llm_security or not self.llm_cliente:
            # Fallback para LLM único
            resposta = await self.llm_cliente.ainvoke(prompt)
            return resposta.content.strip()
        
        try:
            # Usar padrão Dual LLM para isolar processamento de decisão
            resultado = await self.dual_llm_security.execute_secure_operation(
                operation_name="patch_judgment",
                untrusted_data=prompt,
                privileged_action=lambda p: self.llm_cliente.ainvoke(p),
                security_context=SecurityContext.MONITORED
            )
            
            logger.debug("🔐 Julgamento executado com padrão Dual LLM AEGIS")
            return resultado.get('result', {}).get('content', '')
            
        except Exception as e:
            logger.warning(f"⚠️ Erro no Dual LLM: {e} - usando LLM único")
            # Fallback
            resposta = await self.llm_cliente.ainvoke(prompt)
            return resposta.content.strip()
    
    async def executar_julgamento_final(self, patches_candidatos: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Realiza o julgamento final entre uma lista de patches candidatos para escolher o melhor.

        Args:
            patches_candidatos (List[Dict[str, Any]]): Uma lista de dicionários, onde cada um
                contém 'patch_content' e outros metadados de avaliação.

        Returns:
            Optional[Dict[str, Any]]: O dicionário do patch vencedor, ou None se nenhum for escolhido.
        """
        if not patches_candidatos:
            logger.warning("Nenhum patch candidato fornecido para julgamento. Nenhuma ação tomada.")
            return None

        if len(patches_candidatos) == 1:
            logger.info("Apenas um patch candidato. Selecionado por padrão.")
            return patches_candidatos[0]

        logger.info(f"🏆 Iniciando julgamento final AEGIS entre {len(patches_candidatos)} patches candidatos com modelo '{self.nome_modelo}'...")
        
        # Validar patches com sistema AEGIS antes do julgamento
        patches_candidatos = await self._validar_patches_aegis(patches_candidatos)
        
        if not patches_candidatos:
            logger.error("❌ Todos os patches foram rejeitados pela validação AEGIS")
            return None
        elif len(patches_candidatos) == 1:
            logger.info("🎆 Apenas um patch passou na validação AEGIS - selecionado automaticamente")
            return patches_candidatos[0]

        # Obter contexto da missão do Quadro Negro
        analise_causa_raiz = self.quadro_negro.obter_conteudo_do_artefato(config.ANALISE_CAUSA_RAIZ_KEY) or "Análise não disponível."
        log_erro = self.quadro_negro.obter_conteudo_do_artefato(config.LOG_COMPILACAO_ERRO_KEY) or "Log de erro não disponível."

        prompt = self._criar_prompt_julgamento(patches_candidatos, json.dumps(analise_causa_raiz), log_erro)

        try:
            # Usar sistema Dual LLM para maior segurança
            voto_raw = await self._executar_dual_llm_judgment(prompt)

            logger.info(f"Veredito recebido da Agente Mestra (LLM): '{voto_raw}'")

            # Extrair JSON da resposta
            json_match = re.search(r"```json\n(.*?)\n```", voto_raw, re.DOTALL)
            json_str = json_match.group(1).strip() if json_match else voto_raw

            decisao = json.loads(json_str)
            indice_escolhido = int(decisao.get("indice_vencedor", 0)) - 1

            if 0 <= indice_escolhido < len(patches_candidatos):
                patch_vencedor = patches_candidatos[indice_escolhido]
                logger.info(f"🏆 Voto final da Mestra AEGIS: CANDIDATO {indice_escolhido + 1} selecionado.")
                
                # Monitoramento AEGIS da decisão
                if self.aegis_core:
                    try:
                        self.aegis_core.monitor_agent_behavior(
                            agent_name=self.__class__.__name__,
                            operation="patch_judgment_decision",
                            data={
                                "selected_patch_index": indice_escolhido,
                                "total_candidates": len(patches_candidatos),
                                "justification": decisao.get("justificativa_da_escolha", "N/A")[:200]  # Limitar tamanho
                            }
                        )
                    except Exception as e:
                        logger.warning(f"⚠️ Erro no monitoramento AEGIS: {e}")

                # Publica a decisão no Quadro Negro com informações AEGIS
                decisao_final = {
                    "patch_vencedor": patch_vencedor,
                    "justificativa": decisao.get("justificativa_da_escolha", "N/A"),
                    "voto_llm_bruto": voto_raw,
                    "aegis_protection": {
                        "enabled": self.aegis_core is not None,
                        "defensive_tokens": self.defensive_tokens is not None,
                        "dual_llm": self.dual_llm_security is not None,
                        "validation_pipeline": self.validation_pipeline is not None
                    }
                }
                
                self.quadro_negro.publicar_artefato(
                    "decisao_final_mestra",
                    decisao_final,
                    autor=self.__class__.__name__
                )
                
                return patch_vencedor
            else:
                raise ValueError(f"Índice de vencedor inválido: {indice_escolhido + 1}")

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"Falha ao processar o julgamento final da LLM: {e}. Resposta: {voto_raw}. Usando o primeiro patch como fallback.")
            # Como fallback seguro, retorna o primeiro candidato em caso de erro de parsing.
            return patches_candidatos[0]
        except Exception as e:
            logger.error(f"❌ Erro inesperado no julgamento final: {e}", exc_info=True)
            return patches_candidatos[0]
    
    def get_aegis_status(self) -> Dict[str, Any]:
        """Retorna status detalhado do sistema AEGIS."""
        if not self.aegis_core:
            return {
                "aegis_enabled": False,
                "status": "AEGIS não inicializado",
                "components": {}
            }
        
        try:
            aegis_status = self.aegis_core.get_system_status()
            return {
                "aegis_enabled": True,
                "status": "AEGIS ativo e monitorando",
                "protection_level": aegis_status.get("protection_level", "DESCONHECIDO"),
                "components": {
                    "defensive_tokens": self.defensive_tokens is not None,
                    "dual_llm_security": self.dual_llm_security is not None,
                    "validation_pipeline": self.validation_pipeline is not None
                },
                "metrics": aegis_status.get("metrics", {}),
                "advanced_systems": aegis_status.get("advanced_systems", {})
            }
        except Exception as e:
            return {
                "aegis_enabled": True,
                "status": f"AEGIS com erro: {e}",
                "components": {
                    "defensive_tokens": self.defensive_tokens is not None,
                    "dual_llm_security": self.dual_llm_security is not None,
                    "validation_pipeline": self.validation_pipeline is not None
                }
            }

    # --- Função conceitual mantida do estudo original ---
    async def processo_refactor(self, ficha_path: str) -> Dict[str, Any]:
        """
        (Função Conceitual) Orquestra um processo de refatoração de ponta a ponta
        para um arquivo específico, demonstrando o poder de decisão da Mestra.

        Args:
            ficha_path (str): Caminho para o arquivo a ser refatorado.

        Returns:
            Dict[str, Any]: O resultado do processo de refatoração.
        """
        logger.info(f"🛠️ [Processo Refactor AEGIS] Iniciando refatoração protegida para: {ficha_path}")
        
        # Log do status AEGIS
        aegis_status = self.get_aegis_status()
        logger.info(f"🛑️ Status AEGIS: {aegis_status['status']}")

        # Gerar patches via pipeline real com fallback
        patches_simulados = []
        try:
            from quimera.pipeline import AutonomousPipeline
            import asyncio as _asyncio
            pipeline = AutonomousPipeline()
            # Read target file for context
            try:
                with open(ficha_path, 'r') as _f:
                    source_code = _f.read()
            except Exception:
                source_code = "// kernel module source"
            result = await pipeline.run(source_code, language="c")
            if hasattr(result, 'evolved_patches') and result.evolved_patches:
                for i, patch in enumerate(result.evolved_patches[:3]):
                    patches_simulados.append({
                        'patch_content': patch,
                        'agentes_geradores': [f'h4_genetic_{i}'],
                        'score_critico': 0.7 + (i * 0.1),
                        'comentario_critico': f'Pipeline-generated candidate {i+1}'
                    })
        except Exception:
            logger.debug("Real pipeline unavailable — using template fallback")
        
        # Fallback: template-based candidates
        if not patches_simulados:
            patches_simulados = [
                {
                    'patch_content': f"// Auto-generated patch for {ficha_path}\n// H1-H4 pipeline candidate A",
                    'agentes_geradores': ['pipeline_H1_H4'],
                    'score_critico': 0.75,
                    'comentario_critico': 'Pipeline candidate — LLM unavailable, template applied.'
                }
            ]

        # 2. Executar julgamento final
        patch_vencedor_info = await self.executar_julgamento_final(patches_simulados)

        if patch_vencedor_info:
            logger.info(f"🏆 [Processo Refactor AEGIS] Patch vencedor selecionado. Aplicando ao arquivo (simulação)...")
            # Em um cenário real, aqui você aplica o patch ao arquivo
            # e registra no banco de dados.
            return {
                "status": "refatorado_com_sucesso", 
                "file": ficha_path, 
                "patch_aplicado": patch_vencedor_info,
                "aegis_status": aegis_status
            }
        else:
            logger.warning(f"⚠️ [Processo Refactor AEGIS] Nenhum patch aprovado para {ficha_path}")
            return {
                "status": "refatoracao_falhou", 
                "file": ficha_path, 
                "motivo": "Nenhum patch aprovado no julgamento final.",
                "aegis_status": aegis_status
            }