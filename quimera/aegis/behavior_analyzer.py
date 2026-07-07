"""
AEGIS Behavior Analyzer - Analisador Comportamental Avançado
===========================================================
"""

import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from quimera.logs.parser import montar_log


@dataclass
class ExecutionMetrics:
    """Métricas de execução de um componente"""
    total_operations: int = 0
    last_operation_time: Optional[datetime] = None
    average_response_time: float = 0.0
    error_count: int = 0
    success_count: int = 0


class BehaviorAnalyzer:
    """
    Analisador comportamental avançado para o sistema AEGIS
    
    Funcionalidades:
    - Monitoramento de padrões de execução
    - Detecção de anomalias em tempo real
    - Análise de uso de recursos
    - Aprendizado de padrões normais
    """
    
    def __init__(self):
        self._lock = threading.RLock()
        self._initialized = False
        self._learning_mode = True
        self._analysis_active = False
        
        # Armazenamento de dados comportamentais
        self._execution_metrics = {}      # component_id -> ExecutionMetrics
        self._anomaly_history = {}        # anomaly_id -> details
        
        # Buffers de dados em tempo real
        self._execution_buffer = defaultdict(lambda: deque(maxlen=1000))
        self._resource_buffer = defaultdict(lambda: deque(maxlen=1000))
        
        # Configurações de análise
        self.config = {
            'learning_period_hours': 24,
            'analysis_interval_seconds': 10,
            'anomaly_threshold': 2.0,  # Desvios padrão
            'minimum_samples': 50,
            'realtime_analysis': True
        }
        
        # Métricas globais
        self.metrics = {
            'components_analyzed': 0,
            'anomalies_detected': 0,
            'patterns_learned': 0,
            'total_operations_monitored': 0
        }
    
    def initialize(self) -> bool:
        """Inicializa o analisador comportamental"""
        try:
            with self._lock:
                if self._initialized:
                    return True
                
                self._initialized = True
                
                montar_log("AEGIS Behavior Analyzer inicializado", "INFO")
                return True
                
        except Exception as e:
            montar_log(f"Erro ao inicializar analisador comportamental: {e}", "ERROR")
            return False
    
    def register_component(self, component: Any, component_id: str,
                          monitoring_config: Dict[str, Any] = None) -> bool:
        """
        Registra componente para análise comportamental
        
        Args:
            component: Componente a ser monitorado
            component_id: ID único do componente
            monitoring_config: Configurações específicas de monitoramento
        
        Returns:
            True se registrado com sucesso
        """
        try:
            with self._lock:
                # Criar métricas de execução
                self._execution_metrics[component_id] = ExecutionMetrics()
                
                self.metrics['components_analyzed'] += 1
                
                montar_log(f"Componente {component_id} registrado para análise comportamental", "INFO")
                return True
                
        except Exception as e:
            montar_log(f"Erro ao registrar componente {component_id}: {e}", "ERROR")
            return False
    
    def record_operation(self, component_id: str, operation: str, data: Dict[str, Any]) -> bool:
        """Registra uma operação para análise comportamental"""
        try:
            timestamp = datetime.now()
            
            # Registra no buffer de execução
            self._execution_buffer[component_id].append({
                'timestamp': timestamp,
                'operation': operation,
                'data': data
            })
            
            # Atualiza métricas
            if component_id in self._execution_metrics:
                self._execution_metrics[component_id].total_operations += 1
                self._execution_metrics[component_id].last_operation_time = timestamp
            
            self.metrics['total_operations_monitored'] += 1
            
            # Analisa em tempo real se configurado
            if self.config.get('realtime_analysis', True):
                self._analyze_operation_realtime(component_id, operation, data)
            
            return True
            
        except Exception as e:
            montar_log(f"Erro ao registrar operação {operation} para {component_id}: {e}", "ERROR")
            return False
    
    def _analyze_operation_realtime(self, component_id: str, operation: str, data: Dict[str, Any]):
        """Analisa operação em tempo real para anomalias"""
        try:
            operations_count = len(self._execution_buffer[component_id])
            
            if operations_count > 10:  # Threshold mínimo
                recent_operations = list(self._execution_buffer[component_id])[-10:]
                operation_types = [op['operation'] for op in recent_operations]
                
                # Detecta operações repetitivas suspeitas
                if operation_types.count(operation) > 7:  # 70% de repetição
                    self._record_anomaly(component_id, "repetitive_operations", {
                        "operation": operation,
                        "frequency": operation_types.count(operation)
                    })
        
        except Exception as e:
            montar_log(f"Erro na análise em tempo real: {e}", "ERROR")
    
    def _record_anomaly(self, component_id: str, anomaly_type: str, details: Dict[str, Any]):
        """Registra uma anomalia detectada"""
        try:
            anomaly_id = f"{component_id}_{anomaly_type}_{datetime.now().timestamp()}"
            
            self._anomaly_history[anomaly_id] = {
                'component_id': component_id,
                'type': anomaly_type,
                'details': details,
                'timestamp': datetime.now(),
                'resolved': False
            }
            
            self.metrics['anomalies_detected'] += 1
            
            montar_log(f"⚠️ Anomalia detectada em {component_id}: {anomaly_type}", "WARNING")
            
        except Exception as e:
            montar_log(f"Erro ao registrar anomalia: {e}", "ERROR")
    
    def analyze_agent_behavior(self, agent_id: str) -> Dict[str, Any]:
        """Analisa comportamento de um agente específico"""
        try:
            if agent_id not in self._execution_metrics:
                return {
                    "anomaly_detected": False,
                    "reason": "Agent not registered"
                }
            
            # Análise básica
            metrics = self._execution_metrics[agent_id]
            operations_buffer = self._execution_buffer[agent_id]
            
            # Verifica padrões anômalos simples
            anomalies = []
            
            # Verifica se há muitas operações em pouco tempo
            if len(operations_buffer) > 100:
                recent_ops = list(operations_buffer)[-50:]
                time_span = (recent_ops[-1]['timestamp'] - recent_ops[0]['timestamp']).total_seconds()
                
                if time_span < 10:  # 50 operações em menos de 10 segundos
                    anomalies.append("high_frequency_operations")
            
            return {
                "anomaly_detected": len(anomalies) > 0,
                "anomalies": anomalies,
                "total_operations": metrics.total_operations,
                "analysis_timestamp": datetime.now()
            }
            
        except Exception as e:
            montar_log(f"Erro na análise de comportamento: {e}", "ERROR")
            return {
                "anomaly_detected": False,
                "reason": f"Analysis error: {e}"
            }
    
    def get_analysis_status(self) -> Dict[str, Any]:
        """Retorna status da análise comportamental"""
        return {
            "initialized": self._initialized,
            "learning_mode": self._learning_mode,
            "analysis_active": self._analysis_active,
            "components_monitored": len(self._execution_metrics),
            "total_operations": self.metrics['total_operations_monitored'],
            "anomalies_detected": self.metrics['anomalies_detected']
        }
    
    def start_analysis(self):
        """Inicia análise em tempo real"""
        try:
            self._analysis_active = True
            montar_log("Análise comportamental ativada", "INFO")
            
        except Exception as e:
            montar_log(f"Erro ao iniciar análise: {e}", "ERROR")
    
    def stop_analysis(self):
        """Para análise em tempo real"""
        self._analysis_active = False
        montar_log("Análise comportamental desativada", "INFO")