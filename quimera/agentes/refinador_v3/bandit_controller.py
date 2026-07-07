# quimera/agentes/refinador_v3/bandit_controller.py

import random
import logging
import json
from pathlib import Path
from typing import List, Callable, Any, Dict

from quimera.agentes.refinador_v3.config_refinador import EPSILON
from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)

class BanditController:
    """
    Implementação de produção do Multi-Armed Bandit (MAB) usando a estratégia
    Epsilon-Greedy para selecionar dinamicamente a heurística de mutação mais eficaz.
    Esta classe gerencia o estado das heurísticas (braços), incluindo seus scores
    e contagens de uso, e permite persistir e carregar esse estado.
    """
    def __init__(self, heuristicas: List[Callable]):
        """
        Inicializa o controlador do bandit.

        Args:
            heuristicas (List[Callable]): Uma lista inicial de funções de heurística.
        """
        if not heuristicas:
            raise ValueError("A lista de heurísticas não pode ser vazia.")

        self.heuristicas = heuristicas
        # Dicionários para armazenar o valor estimado (Q) e a contagem (N) para cada braço
        self.q_values: Dict[str, float] = {h.__name__: 0.0 for h in heuristicas}
        self.n_counts: Dict[str, int] = {h.__name__: 0 for h in heuristicas}
        montar_log(f"BanditController inicializado com {len(heuristicas)} heurísticas.", "INFO")

    def escolher(self) -> Callable:
        """
        Escolhe uma heurística usando a estratégia Epsilon-Greedy.

        Com probabilidade (epsilon), escolhe uma heurística aleatória (exploração).
        Com probabilidade (1 - epsilon), escolhe a melhor heurística conhecida (explotação).
        """
        # Se alguma heurística nunca foi usada, força a exploração dela primeiro
        nao_usadas = [h for h in self.heuristicas if self.n_counts.get(h.__name__, 0) == 0]
        if nao_usadas:
            escolhida = random.choice(nao_usadas)
            montar_log(f"Bandit [EXPLORAÇÃO INICIAL]: Escolheu heurística não utilizada '{escolhida.__name__}'.", "DEBUG")
            return escolhida

        # Estratégia Epsilon-Greedy
        if random.random() < EPSILON:
            escolhida = random.choice(self.heuristicas)
            montar_log(f"Bandit [EXPLORAÇÃO ALEATÓRIA (ε)]: Escolheu heuristicamente '{escolhida.__name__}'.", "DEBUG")
            return escolhida
        else:
            # Encontra o nome da heurística com o maior Q-value
            best_heuristica_name = max(self.q_values, key=self.q_values.get)
            for h in self.heuristicas:
                if h.__name__ == best_heuristica_name:
                    montar_log(f"Bandit [EXPLOTAÇÃO]: Escolheu a melhor heurística conhecida '{h.__name__}' com Q-value {self.q_values[best_heuristica_name]:.3f}.", "DEBUG")
                    return h

        # Fallback (não deve ser alcançado em operação normal)
        return random.choice(self.heuristicas)

    def registrar_resultado(self, heuristica: Callable, recompensa: float):
        """
        Registra o resultado (recompensa) de uma heurística, atualizando seu Q-value
        usando a fórmula de média incremental.

        Args:
            heuristica (Callable): A função de heurística que foi usada.
            recompensa (float): O score (recompensa) obtido, geralmente entre 0.0 e 1.0.
        """
        name = heuristica.__name__
        if name not in self.q_values:
            montar_log(f"Heurística '{name}' não estava registrada. Adicionando dinamicamente.", "WARNING")
            self.adicionar_heuristica(heuristica)

        # Atualiza a contagem de usos
        self.n_counts[name] += 1
        n = self.n_counts[name]

        # Atualiza o Q-value usando a média incremental para eficiência e estabilidade numérica.
        # Fórmula: Novo_Q = Q_antigo + (Recompensa_Atual - Q_antigo) / N
        current_q = self.q_values[name]
        new_q = current_q + (recompensa - current_q) / n
        self.q_values[name] = new_q

        montar_log(f"Bandit: Resultado para '{name}' registrado. Recompensa: {recompensa:.2f}. Novo Q-value: {new_q:.3f} (N={n}).", "INFO")

    def adicionar_heuristica(self, heuristica: Callable):
        """Adiciona uma nova heurística ao MAB em tempo de execução."""
        name = heuristica.__name__
        if name not in self.q_values:
            self.heuristicas.append(heuristica)
            self.q_values[name] = 0.0
            self.n_counts[name] = 0
            montar_log(f"Bandit: Nova heurística '{name}' adicionada dinamicamente.", "INFO")

    def salvar_estado(self, caminho_arquivo: str):
        """Salva o estado atual (Q-values e contagens) em um arquivo JSON."""
        estado = {
            "q_values": self.q_values,
            "n_counts": self.n_counts
        }
        try:
            with open(caminho_arquivo, 'w', encoding='utf-8') as f:
                json.dump(estado, f, indent=4)
            montar_log(f"Estado do Bandit salvo com sucesso em '{caminho_arquivo}'.", "INFO")
        except Exception as e:
            montar_log(f"Falha ao salvar estado do Bandit: {e}", "ERROR", exc_info=True)

    def carregar_estado(self, caminho_arquivo: str):
        """Carrega um estado salvo (Q-values e contagens) de um arquivo JSON."""
        try:
            if Path(caminho_arquivo).exists():
                with open(caminho_arquivo, 'r', encoding='utf-8') as f:
                    estado = json.load(f)
                self.q_values = estado.get("q_values", self.q_values)
                self.n_counts = estado.get("n_counts", self.n_counts)
                montar_log(f"Estado do Bandit carregado com sucesso de '{caminho_arquivo}'.", "INFO")
        except (json.JSONDecodeError, KeyError) as e:
            montar_log(f"Falha ao carregar estado do Bandit de '{caminho_arquivo}'. O arquivo pode estar corrompido ou malformado. {e}", "ERROR")
        except Exception as e:
            montar_log(f"Erro inesperado ao carregar estado do Bandit: {e}", "ERROR", exc_info=True)