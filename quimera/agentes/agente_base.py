# quimera/agentes/agente_base.py

import logging
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Optional
import time

from quimera.quadro_negro import QuadroNegro
from quimera.core.vector_manager import VectorManager
from quimera.mab.mab import MultiArmedBandit
from quimera.logs.parser import montar_log
from quimera.utils.resilience import CircuitBreakerRegistry
from datetime import datetime

# Configuração do logger para a base dos agentes
logger = logging.getLogger(__name__)

# Constantes para o Circuit Breaker
FAILURE_THRESHOLD = 3  # Número de falhas consecutivas antes de abrir o circuito
COOLDOWN_PERIOD = 300  # Segundos (5 minutos) para o agente ficar em cooldown

# Lock global para operações de I/O em drift_history (evita race conditions)
_drift_io_lock = threading.Lock()

class AgenteBase(ABC):
    """
    Classe base abstrata e de produção para todos os agentes do sistema Quimera.

    Fornece uma infraestrutura robusta e compartilhada para:
    - Identificação e registro unificado.
    - Gestão de estado e saúde (operacional, degradado, em cooldown).
    - Análise de conformidade e "drift" de código contra um histórico de falhas.
    - Mecanismos de resiliência como Circuit Breaker.
    - Interface para interação com o sistema Multi-Armed Bandit (MAB).
    - Persistência de falhas para análise post-mortem.
    """

    def __init__(self, id_registro: str, nome_compativel: str, quadro_negro: QuadroNegro, mab_instance: MultiArmedBandit):
        self.id_registro = id_registro
        self.nome_compativel = nome_compativel
        self.quadro_negro = quadro_negro
        self.mab = mab_instance
        self.vector_manager = VectorManager()

        # Circuit Breaker unificado via registry
        self._circuit_breaker = CircuitBreakerRegistry().get_or_create(
            name=f"agente_{id_registro}",
            failure_threshold=FAILURE_THRESHOLD,
            cooldown_seconds=COOLDOWN_PERIOD,
        )

        # Estado de Saúde (mantido para compatibilidade)
        self._status: str = "operacional"  # 'operacional', 'degradado', 'cooldown'
        self._health_score: float = 1.0  # Score de 0.0 a 1.0
        self._consecutive_failures: int = 0
        self._cooldown_until: float = 0.0

        # Histórico de falhas em memória para esta instância
        self.falhas_rego: List[Path] = []
        self._drift_history_dir = Path("quimera/_DriftHistory")
        self._drift_history_dir.mkdir(parents=True, exist_ok=True)

        montar_log(f"Agente '{self.id_registro}' (Tipo: {self.__class__.__name__}) inicializado.", "INFO")

    @property
    def is_operational(self) -> bool:
        """Verifica se o agente está operacional e não em cooldown."""
        return self._circuit_breaker.is_operational

    def _register_failure(self, motivo: str):
        """Registra uma falha, atualiza o estado e potencialmente abre o circuito."""
        self._consecutive_failures += 1
        self._health_score = max(0.0, self._health_score - 0.25)
        montar_log(f"Agente '{self.id_registro}' registrou falha. Motivo: {motivo}. Falhas consecutivas: {self._consecutive_failures}", "WARNING")

        opened = self._circuit_breaker.record_failure()
        if opened:
            self._status = 'cooldown'
            self._cooldown_until = time.time() + COOLDOWN_PERIOD

    def _register_success(self):
        """Registra um sucesso, resetando o contador de falhas e melhorando a saúde."""
        self._consecutive_failures = 0
        self._health_score = min(1.0, self._health_score + 0.1)
        if self._status == 'degradado':
            self._status = 'operacional'
        self._circuit_breaker.record_success()

    def _reset_circuit_breaker(self):
        """Reseta o circuit breaker após o período de cooldown."""
        self._status = 'operacional'
        self._consecutive_failures = 0
        self._cooldown_until = 0.0
        CircuitBreakerRegistry().reset(f"agente_{self.id_registro}")
        montar_log(f"CIRCUIT BREAKER FECHADO para o agente '{self.id_registro}'. Agente está operacional novamente.", "INFO")

    def _conformidade_banida(self, codigo_proposto: str) -> Dict[str, Any]:
        """
        Verifica um trecho de código contra um histórico de vetores de falha.
        Se o código proposto for muito similar a algo que já falhou, ele é vetado.
        Esta é a implementação real da análise de "drift perigoso".
        """
        # Busca soluções de erro na memória vetorial que sejam similares ao log de erro atual
        log_erro_atual = self.quadro_negro.obter_conteudo_artefato("Log_Compilacao_Erro")
        if not log_erro_atual:
            return {"veto": False, "motivo": "Nenhum log de erro atual para comparação."}

        patches_de_falha_conhecidos = self.vector_manager.buscar_solucoes_por_similaridade_de_erro(log_erro_atual, top_k=5)

        vetor_proposto = self.vector_manager.as_full_vector(codigo_proposto)

        for patch_falho in patches_de_falha_conhecidos:
            vetor_falho = self.vector_manager.as_full_vector(patch_falho)
            # Drift é uma medida de dissimilaridade. Um drift baixo significa alta similaridade.
            drift = self.vector_manager.get_drift(vetor_proposto, vetor_falho)

            # Se o patch proposto for >90% similar a um patch que já falhou para um erro similar...
            if drift < 0.10:
                motivo = f"Drift perigoso detectado ({drift:.4f}). Proposta é muito similar a uma solução falha conhecida."
                montar_log(f"[CONFORMIDADE] {motivo}", "CRITICAL")
                self._gravar_falha(codigo_proposto, tipo="drift_perigoso")
                return {"veto": True, "motivo": motivo, "drift": drift}

        return {"veto": False, "motivo": "Nenhum drift perigoso detectado."}

    def _gravar_falha(self, code: str, tipo: str = "default") -> str:
        """
        Registra um patch ou código que falhou em um arquivo de log específico para análise posterior.
        Usa lock para evitar race conditions em operações de I/O concorrentes.
        """
        with _drift_io_lock:
            file_idx = len([f for f in self._drift_history_dir.iterdir() if f.name.startswith(f"drift_{tipo}_")])
            drift_file_path = self._drift_history_dir / f"drift_{tipo}_{file_idx+1}.log"

            try:
                with open(drift_file_path, "w", encoding="utf-8") as f:
                    f.write(f"# --- Falha do Agente: {self.id_registro} ---\n")
                    f.write(f"# --- Tipo de Falha: {tipo} ---\n")
                    f.write(f"# --- Timestamp: {datetime.now().isoformat()} ---\n\n")
                    f.write(code)

                self.falhas_rego.append(drift_file_path)
                self._penalizar_agente_no_mab(recompensa=0.1, sucesso=False) # Penaliza o agente no MAB
                return str(drift_file_path)

            except Exception as e:
                montar_log(f"Erro ao gravar log de falha em '{drift_file_path}': {e}", "ERROR")
                return ""

    def _penalizar_agente_no_mab(self, recompensa: float, sucesso: bool):
        """Registra o resultado (penalidade/recompensa) da ação do agente no MAB."""
        if self.mab:
            self.mab.registrar_resultado(self.id_registro, recompensa, sucesso)
        else:
            logger.warning("Instância do MAB não disponível para registrar resultado.")

    @abstractmethod
    def update_trigger(self, *args, **kwargs) -> Any:
        """
        Método principal de execução do agente. Cada subclasse deve implementar
        sua lógica de negócio aqui. O retorno pode ser qualquer tipo de dado relevante.
        """
        pass

    @abstractmethod
    def version_on_sa(self, *args, **kwargs) -> bool:
        """
        Protocolo de "salvação". Define se uma versão de código gerada por
        este agente é considerada segura o suficiente para ser persistida ou
        promovida, mesmo que não seja a solução final. Retorna True se for segura.
        """
        pass

    def _register_with_registry(self):
        """Registra este agente no AgentRegistry central."""
        try:
            from quimera.mind.agent_registry import AgentRegistry
            name = self.__class__.__name__
            if name not in AgentRegistry.REGISTRY:
                AgentRegistry.REGISTRY[name] = {
                    "handler": "genetic_evolve",
                    "horizon": "H4",
                    "description": f"Agent: {name}",
                }
        except ImportError:
            pass
