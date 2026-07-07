# quimera/agentes/agente_quantico.py
"""
Agente Quântico — Exploração de espaço de soluções via Simulated Annealing.

Inspirado em conceitos de computação quântica (superposição + colapso),
o agente gera múltiplos patches em paralelo e seleciona o melhor
via annealing simulado com função de fitness.

Uso:
    from quimera.agentes.agente_quantico import AgenteQuantico
    
    agente = AgenteQuantico(temperatura_inicial=1.0, taxa_resfriamento=0.95)
    melhor_patch = await agente.explorar(codigo_problema, restricoes)
"""

import asyncio
import logging
import math
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from quimera.agentes.agente_base import AgenteBase
from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)


@dataclass
class EstadoQuantico:
    """Representa um estado no espaço de busca (uma solução candidata)."""
    id: str
    codigo: str
    fitness: float = 0.0
    metadados: Dict[str, Any] = field(default_factory=dict)
    geracao: int = 0
    pai: Optional[str] = None


class AgenteQuantico(AgenteBase):
    """Agente de exploração quântica do espaço de soluções.
    
    Baseado em Simulated Annealing com paralelismo:
    1. SUPERPOSIÇÃO: gera N patches candidatos em paralelo
    2. AVALIAÇÃO: calcula fitness de cada candidato
    3. COLAPSO: seleciona o melhor, mas permite explorar
       soluções piores com probabilidade ~T (temperatura)
    4. RESFRIAMENTO: reduz T gradualmente
    """
    
    def __init__(
        self,
        temperatura_inicial: float = 1.0,
        temperatura_minima: float = 0.001,
        taxa_resfriamento: float = 0.95,
        iteracoes_por_temperatura: int = 5,
        max_candidatos_paralelos: int = 8,
        nome: str = "AgenteQuantico",
    ):
        super().__init__(nome=nome)
        self.T = temperatura_inicial
        self.T_min = temperatura_minima
        self.alpha = taxa_resfriamento
        self.iter_por_T = iteracoes_por_temperatura
        self.max_paralelos = max_candidatos_paralelos
        
        self._historico: List[EstadoQuantico] = []
        self._melhor_estado: Optional[EstadoQuantico] = None
        self._geracao_atual = 0
        logger.info(
            f"AgenteQuantico: T0={temperatura_inicial}, alpha={taxa_resfriamento}, "
            f"max_paralelos={max_candidatos_paralelos}"
        )
    
    async def explorar(
        self,
        codigo_base: str,
        fitness_fn: Callable[[str], float],
        gerador_fn: Callable[[str], List[str]],
        max_iteracoes: int = 100,
    ) -> EstadoQuantico:
        """Explora o espaço de soluções via Simulated Annealing.
        
        Args:
            codigo_base: Código fonte inicial.
            fitness_fn: Função que avalia qualidade (0-1, maior = melhor).
            gerador_fn: Função que gera variantes a partir de um código.
            max_iteracoes: Número máximo de iterações.
            
        Returns:
            Melhor estado encontrado.
        """
        montar_log(
            f"AgenteQuantico: iniciando exploração (T={self.T:.3f}, max_iter={max_iteracoes})",
            "INFO"
        )
        
        # Estado inicial
        estado_atual = EstadoQuantico(
            id=f"q{self._geracao_atual}",
            codigo=codigo_base,
            fitness=fitness_fn(codigo_base),
            geracao=self._geracao_atual,
        )
        self._historico.append(estado_atual)
        self._melhor_estado = estado_atual
        
        iteracao = 0
        while self.T > self.T_min and iteracao < max_iteracoes:
            for _ in range(self.iter_por_T):
                self._geracao_atual += 1
                iteracao += 1
                
                if iteracao >= max_iteracoes:
                    break
                
                # SUPERPOSIÇÃO: gerar múltiplos candidatos
                candidatos = gerador_fn(estado_atual.codigo)
                candidatos = candidatos[:self.max_paralelos]
                
                # AVALIAÇÃO em paralelo
                estados = []
                for i, cod in enumerate(candidatos):
                    fit = fitness_fn(cod)
                    estados.append(EstadoQuantico(
                        id=f"q{self._geracao_atual}_{i}",
                        codigo=cod,
                        fitness=fit,
                        geracao=self._geracao_atual,
                        pai=estado_atual.id,
                    ))
                
                if not estados:
                    continue
                
                # COLAPSO: selecionar próximo estado
                # Estratégia: pegar melhor, mas com probabilidade de aceitar pior
                estados.sort(key=lambda e: e.fitness, reverse=True)
                melhor_candidato = estados[0]
                
                delta = melhor_candidato.fitness - estado_atual.fitness
                
                if delta > 0 or random.random() < math.exp(delta / max(self.T, 1e-9)):
                    # Aceita o novo estado
                    estado_atual = melhor_candidato
                    self._historico.append(estado_atual)
                    
                    if estado_atual.fitness > self._melhor_estado.fitness:
                        self._melhor_estado = estado_atual
                        montar_log(
                            f"AgenteQuantico: novo melhor! fitness={estado_atual.fitness:.4f} "
                            f"(iter={iteracao}, T={self.T:.4f})",
                            "INFO"
                        )
            
            # RESFRIAMENTO
            self.T *= self.alpha
        
        montar_log(
            f"AgenteQuantico: exploração concluída — "
            f"melhor fitness={self._melhor_estado.fitness:.4f} "
            f"em {iteracao} iterações",
            "INFO"
        )
        return self._melhor_estado
    
    def obter_historico_fitness(self) -> List[float]:
        """Retorna histórico de fitness para análise de convergência."""
        return [e.fitness for e in self._historico]
    
    def obter_relatorio(self) -> Dict[str, Any]:
        """Relatório da exploração quântica."""
        return {
            "nome": self.nome,
            "temperatura_final": self.T,
            "geracoes": self._geracao_atual,
            "total_estados": len(self._historico),
            "melhor_fitness": self._melhor_estado.fitness if self._melhor_estado else 0,
            "convergencia": self.obter_historico_fitness()[-20:] if self._historico else [],
        }
