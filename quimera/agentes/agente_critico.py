import sys
import logging
import json
import subprocess
import os
import re
import tempfile
from typing import Dict, Any, Optional, Tuple
import asyncio

from quimera.quadro_negro import QuadroNegro
try:
    from quimera.agentes.roteador_modelos import RoteadorModelos
except ImportError:
    RoteadorModelos = None  # RoteadorModelos não disponível
from quimera.utils import linter
from quimera import config
from quimera.utils.patch_utils_refactor import PatchValidatorSession, generate_patch_id
try:
    from quimera.core.formal_verification_pipeline import FormalVerificationPipeline
    FORMAL_VERIFICATION_AVAILABLE = True
except ImportError:
    FORMAL_VERIFICATION_AVAILABLE = False
from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)

class AgenteCheckLinux:
    def __init__(self, quadro_negro: QuadroNegro):
        self.quadro_negro = quadro_negro
        self.kernel_root = os.getenv("KERNEL_ROOT")
        if not self.kernel_root:
            montar_log("KERNEL_ROOT não configurado. Validações do AgenteCheckLinux podem ser puladas.", "WARNING")

    def validar_aplicabilidade_patch(self, conteudo_patch: str) -> Dict[str, Any]:
        if not self.kernel_root or not os.path.isdir(self.kernel_root):
            msg = "Validação de aplicabilidade (dry-run) ignorada: KERNEL_ROOT não é um diretório válido."
            montar_log(msg, "WARNING")
            return {"valido": True, "score": 0.5, "log": msg, "motivo": "Ambiente de kernel inválido."}

        if not conteudo_patch or not conteudo_patch.strip():
            return {"valido": False, "score": 0.0, "log": "", "motivo": "Patch vazio ou nulo."}

        patch_path = ""
        try:
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.patch', encoding='utf-8') as tmp:
                tmp.write(conteudo_patch)
                patch_path = tmp.name

            cmd_parts = ["git", "apply", "--check", patch_path]
            result = subprocess.run(cmd_parts, cwd=self.kernel_root, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                return {"valido": True, "score": 1.0, "log": result.stdout, "motivo": "Patch aplicável."}
            else:
                return {"valido": False, "score": 0.0, "log": result.stderr, "motivo": "Patch não aplicável (conflito ou erro)."}
        except subprocess.TimeoutExpired:
            return {"valido": False, "score": 0.0, "log": "Timeout expired", "motivo": "git apply --check demorou demais."}
        except Exception as e:
            montar_log(f"Erro ao executar git apply --check: {e}", "ERROR")
            return {"valido": False, "score": 0.0, "log": str(e), "motivo": "Exceção durante a validação."}
        finally:
            if patch_path and os.path.exists(patch_path):
                os.remove(patch_path)

class AgenteCritico:
    def __init__(self, quadro_negro: QuadroNegro):
        self.quadro_negro = quadro_negro
        self.roteador = RoteadorModelos() if RoteadorModelos is not None else None
        self.checklinux = AgenteCheckLinux(quadro_negro)
        self.kernel_source_path = os.getenv("KERNEL_ROOT")
        # Inicializar pipeline de verificação formal (Horizonte 3)
        if FORMAL_VERIFICATION_AVAILABLE:
            try:
                self.verificador_formal = FormalVerificationPipeline(
                    z3_timeout_ms=5000,
                    cbmc_unwind=100,
                    fail_fast=False,
                )
                status = self.verificador_formal.get_status()
                montar_log(
                    f"AgenteCrítico: Pipeline de verificação formal ativo. "
                    f"Z3={'✅' if status['z3_available'] else '❌'} "
                    f"CBMC={'✅' if status['cbmc_available'] else '❌'} "
                    f"eBPF={'✅' if status['ebpf_available'] else '❌'}",
                    "INFO"
                )
            except Exception as e:
                self.verificador_formal = None
                montar_log(f"AgenteCrítico: Falha ao inicializar verificação formal: {e}", "WARNING")
        else:
            self.verificador_formal = None

        montar_log("AgenteCrítico inicializado.", "INFO")

    async def avaliar_patch(self, conteudo_patch: str, missao_id: Optional[str] = None) -> Dict[str, Any]:
        montar_log("Agente Crítico: Iniciando avaliação completa do patch.", "INFO")
        feedback_final = {"aprovado": False, "score_geral": 0.0, "feedback_detalhado": {}}

        feedback_checklinux = self.checklinux.validar_aplicabilidade_patch(conteudo_patch)
        feedback_final["feedback_detalhado"]["checklinux"] = feedback_checklinux
        if not feedback_checklinux["valido"]:
            feedback_final["motivo_rejeicao"] = f"Falha na validação técnica: {feedback_checklinux['motivo']}"
            montar_log(f"Rejeição na Fase 1 (CheckLinux): {feedback_final['motivo_rejeicao']}", "WARNING")
            return feedback_final

        montar_log("Agente Crítico: Iniciando validação de compilação...", "INFO")
        try:
            with PatchValidatorSession(self.kernel_source_path) as validator:
                resultado_compilacao = validator.validate(conteudo_patch)
        except Exception as e:
            resultado_compilacao = {"sucesso": False, "log": f"Erro crítico na sessão de validação: {e}", "motivo": "erro_sessao_validacao"}
            feedback_final["feedback_detalhado"]["compilacao"] = resultado_compilacao
            feedback_final["motivo_rejeicao"] = "Patch não compilou com sucesso (falha crítica na sessão)."
            montar_log("Rejeição na Fase 2 (Compilação): O patch falhou em compilar.", "WARNING")
            return feedback_final

        feedback_final["feedback_detalhado"]["compilacao"] = resultado_compilacao
        if not resultado_compilacao.get("sucesso"):
            feedback_final["motivo_rejeicao"] = "Patch não compilou com sucesso."
            montar_log("Rejeição na Fase 2 (Compilação): O patch falhou em compilar.", "WARNING")
            return feedback_final

        # ── Fase 2.5: Verificação Formal (Horizonte 3) ──
        if self.verificador_formal is not None:
            montar_log("Agente Crítico: Iniciando verificação formal do patch (Z3 + CBMC + eBPF)...", "INFO")
            try:
                # Obtém código original do Quadro Negro
                artefato_backup = self.quadro_negro.obter_conteudo_artefato(
                    config.INITIAL_BACKUP_PATH_KEY
                )
                codigo_original = ""
                if artefato_backup and isinstance(artefato_backup, str):
                    # Ler o código original do backup
                    from quimera.utils.general import get_code
                    codigo_original = get_code(artefato_backup) or ""

                verdict = self.verificador_formal.verify(
                    original_code=codigo_original,
                    patched_code=conteudo_patch,
                    checks=["buffer_overflow", "use_after_free", "null_dereference", "race_condition"],
                )
                feedback_final["feedback_detalhado"]["verificacao_formal"] = verdict.to_dict()

                if not verdict.certified_safe:
                    montar_log(
                        f"Agente Crítico: Verificação formal encontrou problemas — "
                        f"confiança={verdict.confidence.value}, "
                        f"motores passaram={verdict.engines_passed}/{verdict.engines_executed}",
                        "WARNING"
                    )
                    # Não rejeita automaticamente — isso depende da confiança
                    if verdict.confidence.value in ("low", "none"):
                        feedback_final["feedback_detalhado"]["verificacao_formal"]["acao"] = "rejeitar"
                        feedback_final["motivo_rejeicao"] = (
                            f"Verificação formal falhou: {verdict.confidence.value} confiança. "
                            + "; ".join(verdict.recommendations[:2])
                        )
                        montar_log("Rejeição na Fase 2.5 (Verificação Formal): Confiança insuficiente.", "WARNING")
                        return feedback_final
                    else:
                        # Apenas warning — o LLM pode aprovar apesar dos warnings
                        feedback_final["aviso_verificacao_formal"] = (
                            f"Verificação formal: {verdict.confidence.value} confiança. "
                            + "; ".join(verdict.recommendations[:2])
                        )
                else:
                    montar_log(
                        f"Agente Crítico: ✅ Verificação formal APROVADA com confiança {verdict.confidence.value}",
                        "SUCCESS"
                    )
            except Exception as e:
                montar_log(f"Agente Crítico: Erro na verificação formal: {e}", "ERROR")
                feedback_final["feedback_detalhado"]["verificacao_formal"] = {"erro": str(e)}
        else:
            montar_log("Agente Crítico: Verificação formal indisponível — pulando fase.", "INFO")
            feedback_final["feedback_detalhado"]["verificacao_formal"] = {
                "executada": False,
                "motivo": "Pipeline de verificação formal não inicializado"
            }

        montar_log("Agente Crítico: Iniciando análise de qualidade por LLM...", "INFO")
        feedback_llm = await self._analise_qualitativa_llm(conteudo_patch)
        feedback_final["feedback_detalhado"]["analise_llm"] = feedback_llm

        score_compilacao = 1.0 if resultado_compilacao.get("sucesso") else 0.0
        score_llm = feedback_llm.get("score_confianca", 0.0)
        feedback_final["score_geral"] = (score_compilacao * 0.7) + (score_llm * 0.3)

        if feedback_final["score_geral"] >= config.MIN_SCORE_APROVACAO and feedback_llm.get("aprovado", False):
            feedback_final["aprovado"] = True
            montar_log(f"Agente Crítico: Patch APROVADO com score final {feedback_final['score_geral']:.2f}", "SUCCESS")
        else:
            feedback_final["aprovado"] = False
            feedback_final["motivo_rejeicao"] = feedback_llm.get("justificativa_rejeicao", "Score ou análise do LLM insuficientes para aprovação.")
            montar_log(f"Agente Crítico: Patch REJEITADO com score final {feedback_final['score_geral']:.2f}. Motivo: {feedback_final['motivo_rejeicao']}", "WARNING")

        patch_id = generate_patch_id(conteudo_patch)
        self.quadro_negro.publicar_artefato(f"{config.PATCH_AVALIADO_KEY}_{patch_id}", feedback_final, self.__class__.__name__)
        return feedback_final

    async def _analise_qualitativa_llm(self, conteudo_patch: str) -> Dict[str, Any]:
        agentes = self.roteador.selecionar_agentes_para_tarefa("revisao_patch_critica", 1)
        if not agentes:
            return {"aprovado": False, "justificativa_rejeicao": "Nenhum agente de revisão de patch disponível.", "score_confianca": 0.0}

        agente_revisor = agentes[0]
        prompt = self._criar_prompt_revisao(conteudo_patch)
        try:
            resposta_llm_obj = await agente_revisor["cliente_llm"].ainvoke(prompt)
            resposta_bruta = resposta_llm_obj.content
            json_match = re.search(r"\{.*\}", resposta_bruta, re.DOTALL)
            if json_match:
                analise = json.loads(json_match.group(0))
                return analise
            else:
                raise json.JSONDecodeError("Nenhum objeto JSON encontrado na resposta.", resposta_bruta, 0)
        except Exception as e:
            montar_log(f"Agente Crítico: Falha na análise qualitativa do LLM. Erro: {e}", "ERROR")
            return {"aprovado": False, "score_confianca": 0.0, "justificativa_rejeicao": f"Erro de parsing ou API: {e}", "log_bruto_llm": locals().get("resposta_bruta", "N/A")}

    def _criar_prompt_revisao(self, conteudo_patch: str) -> str:
        return f'''
Você é um revisor de código sênior do kernel Linux. Avalie criticamente o seguinte patch:

### PATCH PROPOSTO:
```diff
{conteudo_patch}
```
### CRITÉRIOS DE AVALIAÇÃO:

- Correção: O patch resolve o problema?
- Segurança: Há riscos (overflows, race conditions etc)?
- Estilo: Está conforme o estilo do kernel?
- Performance: Introduz lentidão ou código desnecessário?
- Efeitos Colaterais: Pode quebrar outras partes?

### FORMATO DE SAÍDA (Exemplo):
{{
  "aprovado": true,
  "score_confianca": 0.92,
  "pontos_positivos": ["Uso correto de locks", "Estilo aderente ao padrão"],
  "problemas_encontrados": ["Comentário ausente em bloco crítico"],
  "sugestoes_melhoria": ["Adicionar comentário explicativo"],
  "justificativa_rejeicao": ""
}}
'''