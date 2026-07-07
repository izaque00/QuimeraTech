# quimera/agentes/agente_kan.py
"""
Agente KAN — Kolmogorov-Arnold Network para aprendizado de padrões de correção.

KANs são redes neurais baseadas no teorema de Kolmogorov-Arnold,
que decompõem funções multivariadas em somas de funções univariadas.
Mais eficientes que MLPs para funções de kernel e padrões de correção.

Este agente implementa uma KAN simplificada em Python puro (sem dep de GPU),
otimizada para aprendizado de padrões de correção de código kernel.

Uso:
    from quimera.agentes.agente_kan import AgenteKAN
    
    kan = AgenteKAN(input_dim=10, hidden_dim=8, output_dim=1)
    kan.treinar(X, y, epochs=100)
    predicao = kan.predizer(novo_padrao)
"""

import logging
import math
import random
from typing import Dict, List, Optional, Tuple

import numpy as np

from quimera.agentes.agente_base import AgenteBase
from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)


class BSplineBasis:
    """Base de B-splines para KAN.
    
    B-splines são usadas como funções de ativação aprendíveis
    no lugar de funções fixas (ReLU, sigmoid).
    """
    
    def __init__(self, num_bases: int = 8, k: int = 3, x_min: float = -1.0, x_max: float = 1.0):
        self.num_bases = num_bases
        self.k = k
        self.x_min = x_min
        self.x_max = x_max
        # Grid uniforme de knots
        self.knots = np.linspace(x_min, x_max, num_bases + k + 1)
    
    def evaluate(self, x: np.ndarray) -> np.ndarray:
        """Avalia bases B-spline para input x."""
        x = np.clip(x, self.x_min, self.x_max)
        n = len(self.knots) - self.k - 1
        result = np.zeros((len(np.atleast_1d(x)), n))
        
        for i in range(n):
            result[:, i] = self._bspline(x, i, self.k)
        
        return result if len(result) > 1 else result[0]
    
    def _bspline(self, x: np.ndarray, i: int, k: int) -> np.ndarray:
        """Recursão de Cox-de Boor para B-spline."""
        if k == 0:
            return ((x >= self.knots[i]) & (x < self.knots[i + 1])).astype(float)
        
        denom1 = self.knots[i + k] - self.knots[i]
        denom2 = self.knots[i + k + 1] - self.knots[i + 1]
        
        term1 = np.zeros_like(x)
        term2 = np.zeros_like(x)
        
        if denom1 != 0:
            term1 = ((x - self.knots[i]) / denom1) * self._bspline(x, i, k - 1)
        if denom2 != 0:
            term2 = ((self.knots[i + k + 1] - x) / denom2) * self._bspline(x, i + 1, k - 1)
        
        return term1 + term2


class KANLayer:
    """Uma camada da Kolmogorov-Arnold Network."""
    
    def __init__(self, in_dim: int, out_dim: int, num_bases: int = 8):
        self.in_dim = in_dim
        self.out_dim = out_dim
        self.num_bases = num_bases
        
        # Para cada par (input, output): uma B-spline com coeficientes aprendíveis
        self.splines = [[BSplineBasis(num_bases) for _ in range(in_dim)] for _ in range(out_dim)]
        self.coeffs = np.random.randn(out_dim, in_dim, num_bases) * 0.1
        self.bias = np.zeros(out_dim)
    
    def forward(self, x: np.ndarray) -> np.ndarray:
        """Forward pass da camada KAN."""
        batch_size = x.shape[0] if len(x.shape) > 1 else 1
        x = np.atleast_2d(x)
        output = np.zeros((x.shape[0], self.out_dim))
        
        for j in range(self.out_dim):
            for i in range(self.in_dim):
                basis_vals = self.splines[j][i].evaluate(x[:, i])
                output[:, j] += np.dot(basis_vals, self.coeffs[j, i])
            output[:, j] += self.bias[j]
        
        return output if batch_size > 1 else output[0]


class AgenteKAN(AgenteBase):
    """Agente baseado em Kolmogorov-Arnold Network.
    
    Aprende padrões de correção de código kernel usando KAN,
    que é mais eficiente que MLP para funções com estrutura
    composicional (como correções de código).
    
    Attributes:
        input_dim: Dimensão do vetor de features de entrada.
        hidden_dim: Dimensão da camada oculta.
        output_dim: Dimensão da saída.
        learning_rate: Taxa de aprendizado.
    """
    
    def __init__(
        self,
        input_dim: int = 10,
        hidden_dim: int = 8,
        output_dim: int = 1,
        learning_rate: float = 0.01,
        nome: str = "AgenteKAN",
    ):
        super().__init__(nome=nome)
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim
        self.lr = learning_rate
        
        # Arquitetura: 2 camadas KAN
        self.layer1 = KANLayer(input_dim, hidden_dim)
        self.layer2 = KANLayer(hidden_dim, output_dim)
        
        self._trained = False
        self._loss_history: List[float] = []
        logger.info(f"AgenteKAN: {input_dim}→{hidden_dim}→{output_dim}, lr={learning_rate}")
    
    def forward(self, x: np.ndarray) -> np.ndarray:
        """Forward pass completo."""
        h = self.layer1.forward(x)
        h = np.tanh(h)  # Não-linearidade entre camadas
        return self.layer2.forward(h)
    
    def treinar(
        self,
        X: np.ndarray,
        y: np.ndarray,
        epochs: int = 100,
        batch_size: int = 16,
        verbose: bool = True,
    ) -> List[float]:
        """Treina a KAN nos dados fornecidos.
        
        Args:
            X: Features de entrada (n_amostras, input_dim).
            y: Targets (n_amostras, output_dim).
            epochs: Número de épocas.
            batch_size: Tamanho do batch.
            verbose: Se True, loga progresso.
            
        Returns:
            Histórico de loss.
        """
        n = len(X)
        self._loss_history = []
        
        for epoch in range(epochs):
            # Shuffle
            indices = np.random.permutation(n)
            epoch_loss = 0.0
            
            for start in range(0, n, batch_size):
                batch_idx = indices[start:start + batch_size]
                X_batch = X[batch_idx]
                y_batch = y[batch_idx]
                
                # Forward
                y_pred = np.array([self.forward(x) for x in X_batch])
                
                # MSE Loss
                loss = np.mean((y_pred - y_batch) ** 2)
                epoch_loss += loss
                
                # Gradiente simples (aproximação numérica)
                grad = 2 * (y_pred - y_batch) / len(X_batch)
                
                # Atualiza coeficientes da layer2 (simplificado)
                for j in range(self.output_dim):
                    for i in range(self.hidden_dim):
                        self.layer2.coeffs[j, i] -= self.lr * np.mean(grad[:, j]) * 0.1
            
            avg_loss = epoch_loss / max(n // batch_size, 1)
            self._loss_history.append(avg_loss)
            
            if verbose and (epoch + 1) % (epochs // 5) == 0:
                montar_log(f"AgenteKAN: época {epoch+1}/{epochs}, loss={avg_loss:.6f}", "INFO")
        
        self._trained = True
        montar_log(f"AgenteKAN: treinamento concluído — loss final={self._loss_history[-1]:.6f}", "INFO")
        return self._loss_history
    
    def predizer(self, x: np.ndarray) -> np.ndarray:
        """Prediz para novos dados."""
        if not self._trained:
            logger.warning("AgenteKAN: predizendo sem treinamento")
        return self.forward(np.atleast_1d(x))
    
    def avaliar(self, X: np.ndarray, y: np.ndarray) -> Dict[str, float]:
        """Avalia a KAN em dados de teste."""
        y_pred = np.array([self.predizer(x) for x in X])
        mse = np.mean((y_pred.flatten() - y.flatten()) ** 2)
        mae = np.mean(np.abs(y_pred.flatten() - y.flatten()))
        return {"mse": float(mse), "mae": float(mae)}
    
    def extrair_padroes(self, X: np.ndarray, threshold: float = 0.5) -> List[Dict]:
        """Extrai padrões aprendidos pela KAN.
        
        Analisa quais features têm maior influência nas predições.
        """
        if not self._trained:
            return []
        
        importances = []
        for i in range(self.input_dim):
            # Perturba feature i e mede mudança na predição
            x_base = np.zeros(self.input_dim)
            x_perturbed = x_base.copy()
            x_perturbed[i] = 1.0
            
            pred_base = self.predizer(x_base)
            pred_pert = self.predizer(x_perturbed)
            
            importance = float(np.abs(pred_pert - pred_base))
            importances.append({
                "feature_index": i,
                "importance": importance,
                "significant": importance > threshold,
            })
        
        importances.sort(key=lambda x: x["importance"], reverse=True)
        return importances
    
    def obter_relatorio(self) -> Dict:
        """Relatório da KAN."""
        return {
            "nome": self.nome,
            "arquitetura": f"{self.input_dim}→{self.hidden_dim}→{self.output_dim}",
            "trained": self._trained,
            "loss_final": self._loss_history[-1] if self._loss_history else None,
            "parametros": self.input_dim * self.hidden_dim * 8 + self.hidden_dim * self.output_dim * 8,
        }
