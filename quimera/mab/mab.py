# quimera/mab/mab.py

# Verificações de dependências adicionadas automaticamente
def verificar_dependencia(nome_modulo, funcionalidade="essa funcionalidade"):
    """Verifica se uma dependência está disponível"""
    try:
        __import__(nome_modulo)
        return True
    except ImportError:
        print(f"⚠️  {nome_modulo} não instalado - {funcionalidade} não disponível")
        return False

import logging
_logger = logging.getLogger(__name__)


def _unavailable_feature(feature_name: str, *args, **kwargs):
    """Loga warning quando funcionalidade não está disponível por falta de dependências."""
    _logger.warning(f"Funcionalidade '{feature_name}' indisponível — dependência não instalada")
    return None

try:
    import numpy as np
except ImportError:
    np = None  # Mock
    import math  # Fallback para operações matemáticas
import logging
from typing import List, Dict, Any

# Configuração do logger para este módulo
logger = logging.getLogger(__name__)

class MultiArmedBandit:
    """
    Implementação do algoritmo Multi-Armed Bandit (MAB) usando a estratégia
    Upper Confidence Bound (UCB1) para a seleção otimizada de agentes de IA.

    Esta classe gerencia um conjunto de "braços" (agentes), balanceando a
    exploração (tentar agentes menos conhecidos) e a explotação (usar agentes
    com histórico de sucesso) para maximizar a recompensa ao longo do tempo.
    A classe opera em memória e não tem dependências diretas com o banco de dados,
    recebendo e expondo métricas através de sua interface pública.
    """

    def __init__(self, agentes: List[str]):
        """
        Inicializa o MAB com uma lista de agentes disponíveis.

        Args:
            agentes (List[str]): Uma lista de nomes únicos que identificam cada agente (braço).
        """
        if not agentes:
            raise ValueError("A lista de agentes não pode ser vazia.")

        self.agentes = list(set(agentes)) # Garante que os agentes sejam únicos
        self.metricas: Dict[str, Dict[str, Any]] = {
            agente: {"usos": 0, "score_total": 0.0, "sucessos": 0}
            for agente in self.agentes
        }
        self.total_rodadas_selecao = 0
        logger.info(f"Multi-Armed Bandit inicializado com {len(self.agentes)} agentes: {self.agentes}")

    def adicionar_agente(self, nome_agente: str):
        """Adiciona um novo agente (braço) ao MAB, se ele ainda não existir."""
        if nome_agente not in self.metricas:
            self.agentes.append(nome_agente)
            self.metricas[nome_agente] = {"usos": 0, "score_total": 0.0, "sucessos": 0}
            logger.info(f"Novo agente '{nome_agente}' adicionado ao MAB.")

    def selecionar_agentes_para_rodada(self, quantidade: int = 1) -> List[str]:
        """
        Seleciona o(s) agente(s) mais promissor(es) para a próxima rodada usando o UCB1.

        Args:
            quantidade (int): O número de agentes a serem selecionados.

        Returns:
            List[str]: Uma lista com os nomes dos agentes selecionados, ordenados pelo score UCB.
        """
        self.total_rodadas_selecao += 1

        # Prioriza a exploração inicial de agentes que nunca foram usados.
        agentes_nao_usados = [a for a in self.agentes if self.metricas[a]["usos"] == 0]
        if agentes_nao_usados:
            if np is not None:
                np.random.shuffle(agentes_nao_usados)
            else:
                import random
                random.shuffle(agentes_nao_usados)
            selecionados = agentes_nao_usados
        else:
            selecionados = []

        # Para os agentes já usados, calcula o score UCB.
        scores_ucb = []
        for agente in self.agentes:
            if self.metricas[agente]["usos"] > 0:
                # Termo de Explotação: Recompensa média observada até agora.
                recompensa_media = self.metricas[agente]["score_total"] / self.metricas[agente]["usos"]

                # Termo de Exploração: Aumenta a incerteza para agentes menos usados.
                if np is not None:
                    termo_exploracao = np.sqrt((2 * np.log(self.total_rodadas_selecao)) / self.metricas[agente]["usos"])
                else:
                    termo_exploracao = math.sqrt((2 * math.log(self.total_rodadas_selecao)) / self.metricas[agente]["usos"])

                ucb_score = recompensa_media + termo_exploracao
                scores_ucb.append((ucb_score, agente))

        # Ordena os agentes pelo maior score UCB e adiciona à lista de selecionados.
        agentes_ordenados_por_ucb = sorted(scores_ucb, key=lambda x: x[0], reverse=True)
        for _, nome_agente in agentes_ordenados_por_ucb:
            if nome_agente not in selecionados:
                selecionados.append(nome_agente)

        # Retorna a quantidade solicitada.
        resultado_final = selecionados[:quantidade]
        logger.info(f"[MAB] Rodada {self.total_rodadas_selecao}: Agentes selecionados: {resultado_final}")
        return resultado_final

    def registrar_resultado(self, nome_agente: str, recompensa: float, sucesso: bool):
        """
        Atualiza as métricas de um agente com o resultado de sua última ação.

        Args:
            nome_agente (str): O nome do agente a ser atualizado.
            recompensa (float): O score de recompensa (0.0 a 1.0) recebido.
            sucesso (bool): True se a ação resultou em um sucesso final (ex: compilação correta).
        """
        if nome_agente not in self.metricas:
            logger.warning(f"[MAB] Tentativa de registrar resultado para agente desconhecido '{nome_agente}'. Ignorando.")
            return

        self.metricas[nome_agente]["usos"] += 1
        self.metricas[nome_agente]["score_total"] += recompensa
        if sucesso:
            self.metricas[nome_agente]["sucessos"] += 1

        logger.debug(f"[MAB] Resultado registrado para '{nome_agente}': Recompensa={recompensa}, Sucesso={sucesso}. Novas métricas: {self.metricas[nome_agente]}")

    def registrar_resultado_rodada(self, nomes_agentes: List[str], recompensa: float, sucesso: bool):
        """Aplica o mesmo resultado a um grupo de agentes que participaram de uma rodada."""
        for nome_agente in nomes_agentes:
            self.registrar_resultado(nome_agente, recompensa, sucesso)

    def obter_metricas(self) -> Dict[str, Dict[str, Any]]:
        """Retorna o estado atual de todas as métricas dos agentes para persistência."""
        return self.metricas

    def atualizar_metrica_existente(self, nome_agente: str, usos: int, score_total: float, sucessos: int):
        """
        Carrega métricas preexistentes (geralmente do banco de dados) para um agente,
        permitindo que o MAB continue de onde parou.
        """
        if nome_agente in self.metricas:
            self.metricas[nome_agente] = {
                "usos": usos,
                "score_total": score_total,
                "sucessos": sucessos
            }
            # Garante que o contador de rodadas seja consistente com os dados carregados.
            if usos > self.total_rodadas_selecao:
                self.total_rodadas_selecao = usos
            logger.info(f"Métricas pré-existentes carregadas para o agente '{nome_agente}'.")