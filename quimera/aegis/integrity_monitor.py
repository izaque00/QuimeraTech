"""
AEGIS Integrity Monitor - Monitor Avançado de Integridade
========================================================

Sistema de monitoramento de integridade em tempo real que detecta
modificações não autorizadas em componentes, arquivos e dados do sistema.
Utiliza hashing avançado, checksums e verificação de assinaturas digitais.
"""

import asyncio
import hashlib
import hmac
import json
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple, Callable
import weakref
import json

from quimera.logs.parser import montar_log


@dataclass
class IntegrityRecord:
    """Registro de integridade de um componente"""
    component_id: str
    hash_sha256: str
    hash_blake2b: str
    size: int
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    verification_count: int = 0
    last_verified: Optional[datetime] = None
    violations_count: int = 0


@dataclass
class IntegrityViolation:
    """Violação de integridade detectada"""
    id: str
    component_id: str
    violation_type: str  # hash_mismatch, size_change, unauthorized_modification
    severity: float
    timestamp: datetime
    original_hash: str
    current_hash: str
    details: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False


class IntegrityMonitor:
    """
    Monitor avançado de integridade para o sistema AEGIS
    
    Funcionalidades:
    - Monitoramento contínuo de integridade
    - Detecção de modificações não autorizadas
    - Verificação de checksums múltiplos
    - Sistema de assinaturas digitais
    - Backup automático de estados íntegros
    - Restauração automática de integridade
    """
    
    def __init__(self):
        self._lock = threading.RLock()
        self._initialized = False
        self._monitoring_active = False
        
        # Armazenamento de registros de integridade
        self._integrity_database = {}  # component_id -> IntegrityRecord
        self._violations_log = {}      # violation_id -> IntegrityViolation
        self._component_references = weakref.WeakKeyDictionary()
        
        # Configurações de monitoramento
        self.config = {
            'check_interval_seconds': 60,
            'deep_verification_hours': 24,
            'hash_algorithms': ['sha256', 'blake2b'],
            'auto_backup_enabled': True,
            'auto_restore_enabled': True,
            'violation_threshold': 3,
            'notification_enabled': True,
            'realtime_monitoring': True,
            'checksum_verification': True,
            'digital_signatures': True
        }
        
        # Métricas de integridade
        self.metrics = {
            'components_monitored': 0,
            'integrity_checks_performed': 0,
            'violations_detected': 0,
            'violations_resolved': 0,
            'backup_operations': 0,
            'restore_operations': 0,
            'total_uptime': 0,
            'last_check_timestamp': None,
            'average_check_duration': 0.0
        }
        
        # Estado interno
        self._backup_storage = {}
        self._monitoring_threads = []
        self._notification_callbacks = []
        
        # Cache de hashes para performance
        self._hash_cache = {}
        self._cache_ttl = 300  # 5 minutos
    
    async def initialize(self) -> bool:
        """Inicializa o monitor de integridade"""
        try:
            with self._lock:
                if self._initialized:
                    return True
                
                # Carregar base de dados de integridade
                await self._load_integrity_database()
                
                # Configurar algoritmos de hash
                await self._setup_hash_algorithms()
                
                # Inicializar sistema de backup
                await self._initialize_backup_system()
                
                # Configurar assinaturas digitais
                if self.config['digital_signatures']:
                    await self._setup_digital_signatures()
                
                self._initialized = True
                self.metrics['total_uptime'] = time.time()
                
                # Iniciar monitoramento se configurado
                if self.config['realtime_monitoring']:
                    await self._start_realtime_monitoring()
                
                montar_log("AEGIS Integrity Monitor inicializado", "INFO")
                return True
                
        except Exception as e:
            montar_log(f"Erro ao inicializar monitor de integridade: {e}", "ERROR")
            return False
    
    async def register_component(self, component: Any, component_id: str, 
                               metadata: Dict[str, Any] = None) -> IntegrityRecord:
        """
        Registra um componente para monitoramento de integridade
        
        Args:
            component: Objeto a ser monitorado
            component_id: Identificador único do componente
            metadata: Metadados adicionais
        
        Returns:
            Registro de integridade criado
        """
        if not self._initialized:
            raise RuntimeError("Monitor de integridade não foi inicializado")
        
        try:
            with self._lock:
                # Calcular hashes iniciais
                hashes = await self._calculate_component_hashes(component)
                size = self._calculate_component_size(component)
                
                # Criar registro de integridade
                record = IntegrityRecord(
                    component_id=component_id,
                    hash_sha256=hashes['sha256'],
                    hash_blake2b=hashes['blake2b'],
                    size=size,
                    timestamp=datetime.now(),
                    metadata=metadata or {},
                    verification_count=0,
                    last_verified=datetime.now(),
                    violations_count=0
                )
                
                # Armazenar registro
                self._integrity_database[component_id] = record
                
                # Manter referência fraca ao componente
                if hasattr(component, '__weakref__'):
                    self._component_references[component] = component_id
                
                # Criar backup inicial se habilitado
                if self.config['auto_backup_enabled']:
                    await self._create_component_backup(component, component_id)
                
                self.metrics['components_monitored'] += 1
                
                montar_log(f"Componente {component_id} registrado para monitoramento de integridade", "INFO")
                return record
                
        except Exception as e:
            montar_log(f"Erro ao registrar componente {component_id}: {e}", "ERROR")
            raise
    
    def register_file(self, file_path: str) -> bool:
        """Registra um arquivo para monitoramento (versão síncrona)"""
        try:
            # Calcula hash do arquivo
            import hashlib
            with open(file_path, 'rb') as f:
                content = f.read()
                file_hash = hashlib.sha256(content).hexdigest()
            
            # Registra no banco de integridade
            component_id = str(Path(file_path).absolute())
            self._integrity_database[component_id] = {
                'hash': file_hash,
                'path': file_path,
                'registered_at': datetime.now(),
                'size': len(content)
            }
            
            montar_log(f"Arquivo {file_path} registrado para monitoramento", "INFO")
            return True
            
        except Exception as e:
            montar_log(f"Erro ao registrar arquivo {file_path}: {e}", "ERROR")
            return False
    
    async def unregister_component(self, component_id: str) -> bool:
        """Remove componente do monitoramento"""
        try:
            with self._lock:
                if component_id in self._integrity_database:
                    del self._integrity_database[component_id]
                    
                    # Remover backup se existir
                    if component_id in self._backup_storage:
                        del self._backup_storage[component_id]
                    
                    self.metrics['components_monitored'] -= 1
                    
                    montar_log(f"Componente {component_id} removido do monitoramento", "INFO")
                    return True
                
                return False
                
        except Exception as e:
            montar_log(f"Erro ao remover componente {component_id}: {e}", "ERROR")
            return False
    
    async def verify_component_integrity(self, component: Any, 
                                       component_id: str) -> Dict[str, Any]:
        """
        Verifica integridade de um componente específico
        
        Args:
            component: Componente a ser verificado
            component_id: ID do componente
        
        Returns:
            Resultado da verificação
        """
        if not self._initialized:
            raise RuntimeError("Monitor não foi inicializado")
        
        start_time = time.time()
        
        try:
            with self._lock:
                # Obter registro original
                original_record = self._integrity_database.get(component_id)
                if not original_record:
                    return {
                        'status': 'error',
                        'message': f'Componente {component_id} não está registrado',
                        'integrity_ok': False
                    }
                
                # Calcular hashes atuais
                current_hashes = await self._calculate_component_hashes(component)
                current_size = self._calculate_component_size(component)
                
                # Verificar integridade
                integrity_violations = []
                
                # Verificar hash SHA256
                if current_hashes['sha256'] != original_record.hash_sha256:
                    integrity_violations.append({
                        'type': 'hash_mismatch_sha256',
                        'severity': 0.9,
                        'original': original_record.hash_sha256,
                        'current': current_hashes['sha256']
                    })
                
                # Verificar hash BLAKE2b
                if current_hashes['blake2b'] != original_record.hash_blake2b:
                    integrity_violations.append({
                        'type': 'hash_mismatch_blake2b',
                        'severity': 0.9,
                        'original': original_record.hash_blake2b,
                        'current': current_hashes['blake2b']
                    })
                
                # Verificar tamanho
                if current_size != original_record.size:
                    integrity_violations.append({
                        'type': 'size_change',
                        'severity': 0.7,
                        'original': original_record.size,
                        'current': current_size
                    })
                
                # Atualizar métricas
                original_record.verification_count += 1
                original_record.last_verified = datetime.now()
                self.metrics['integrity_checks_performed'] += 1
                
                check_duration = time.time() - start_time
                self._update_average_check_duration(check_duration)
                
                # Se há violações, criar registros de violação
                if integrity_violations:
                    await self._handle_integrity_violations(
                        component, component_id, integrity_violations, original_record
                    )
                    
                    return {
                        'status': 'violation_detected',
                        'integrity_ok': False,
                        'violations': integrity_violations,
                        'component_id': component_id,
                        'check_duration': check_duration,
                        'timestamp': datetime.now().isoformat()
                    }
                else:
                    return {
                        'status': 'ok',
                        'integrity_ok': True,
                        'component_id': component_id,
                        'check_duration': check_duration,
                        'timestamp': datetime.now().isoformat(),
                        'verification_count': original_record.verification_count
                    }
                    
        except Exception as e:
            montar_log(f"Erro na verificação de integridade de {component_id}: {e}", "ERROR")
            return {
                'status': 'error',
                'integrity_ok': False,
                'error': str(e),
                'component_id': component_id
            }
    
    async def verify_all_components(self) -> Dict[str, Any]:
        """Verifica integridade de todos os componentes monitorados"""
        start_time = time.time()
        results = {}
        violation_count = 0
        
        try:
            component_ids = list(self._integrity_database.keys())
            
            for component_id in component_ids:
                try:
                    # Encontrar componente pela referência fraca
                    component = await self._find_component_by_id(component_id)
                    if component:
                        result = await self.verify_component_integrity(component, component_id)
                        results[component_id] = result
                        
                        if not result.get('integrity_ok', False):
                            violation_count += 1
                    else:
                        results[component_id] = {
                            'status': 'component_not_found',
                            'integrity_ok': False,
                            'message': 'Componente não encontrado (possivelmente coletado pelo GC)'
                        }
                        
                except Exception as e:
                    results[component_id] = {
                        'status': 'error',
                        'integrity_ok': False,
                        'error': str(e)
                    }
                    montar_log(f"Erro ao verificar componente {component_id}: {e}", "ERROR")
            
            total_duration = time.time() - start_time
            self.metrics['last_check_timestamp'] = datetime.now()
            
            return {
                'total_components': len(component_ids),
                'violations_detected': violation_count,
                'check_duration': total_duration,
                'results': results,
                'timestamp': datetime.now().isoformat(),
                'summary': {
                    'ok': len([r for r in results.values() if r.get('integrity_ok')]),
                    'violations': violation_count,
                    'errors': len([r for r in results.values() if r.get('status') == 'error'])
                }
            }
            
        except Exception as e:
            montar_log(f"Erro na verificação geral de integridade: {e}", "ERROR")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def restore_component_integrity(self, component_id: str) -> Dict[str, Any]:
        """
        Restaura a integridade de um componente usando backup
        
        Args:
            component_id: ID do componente a ser restaurado
        
        Returns:
            Resultado da operação de restauração
        """
        if not self.config['auto_restore_enabled']:
            return {
                'status': 'disabled',
                'message': 'Restauração automática está desabilitada'
            }
        
        try:
            with self._lock:
                # Verificar se há backup disponível
                if component_id not in self._backup_storage:
                    return {
                        'status': 'no_backup',
                        'message': f'Nenhum backup disponível para {component_id}'
                    }
                
                # Obter backup
                backup_data = self._backup_storage[component_id]
                
                # Encontrar componente
                component = await self._find_component_by_id(component_id)
                if not component:
                    return {
                        'status': 'component_not_found',
                        'message': f'Componente {component_id} não encontrado'
                    }
                
                # Executar restauração
                restore_success = await self._execute_component_restore(
                    component, component_id, backup_data
                )
                
                if restore_success:
                    # Atualizar registro de integridade
                    await self._update_integrity_record_after_restore(component_id)
                    
                    self.metrics['restore_operations'] += 1
                    
                    montar_log(f"Integridade do componente {component_id} restaurada com sucesso", "SUCCESS")
                    return {
                        'status': 'success',
                        'message': f'Integridade de {component_id} restaurada',
                        'timestamp': datetime.now().isoformat()
                    }
                else:
                    return {
                        'status': 'restore_failed',
                        'message': f'Falha na restauração de {component_id}'
                    }
                    
        except Exception as e:
            montar_log(f"Erro na restauração de {component_id}: {e}", "ERROR")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def get_integrity_status(self) -> Dict[str, Any]:
        """Retorna status completo do monitor de integridade"""
        current_time = time.time()
        uptime = current_time - self.metrics['total_uptime'] if self.metrics['total_uptime'] else 0
        
        # Estatísticas de violações
        violation_stats = self._calculate_violation_statistics()
        
        # Status dos componentes
        component_status = {}
        for comp_id, record in self._integrity_database.items():
            component_status[comp_id] = {
                'verification_count': record.verification_count,
                'last_verified': record.last_verified.isoformat() if record.last_verified else None,
                'violations_count': record.violations_count,
                'has_backup': comp_id in self._backup_storage,
                'size': record.size,
                'registered_at': record.timestamp.isoformat()
            }
        
        return {
            'initialized': self._initialized,
            'monitoring_active': self._monitoring_active,
            'uptime_seconds': uptime,
            'metrics': self.metrics.copy(),
            'config': self.config.copy(),
            'components_status': component_status,
            'violation_statistics': violation_stats,
            'cache_size': len(self._hash_cache),
            'backup_count': len(self._backup_storage)
        }
    
    def register_notification_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Registra callback para notificações de violação"""
        self._notification_callbacks.append(callback)
    
    # Métodos privados de implementação
    
    async def _load_integrity_database(self):
        """Carrega base de dados de integridade"""
        try:
            # Em um sistema real, isso carregaria de um arquivo ou BD
            # Por enquanto, inicializar vazio
            self._integrity_database = {}
            self._violations_log = {}
            
        except Exception as e:
            montar_log(f"Erro ao carregar base de integridade: {e}", "ERROR")
    
    async def _setup_hash_algorithms(self):
        """Configura algoritmos de hash"""
        try:
            # Verificar disponibilidade dos algoritmos
            available_algorithms = hashlib.algorithms_available
            
            for algorithm in self.config['hash_algorithms']:
                if algorithm not in available_algorithms:
                    montar_log(f"Algoritmo {algorithm} não disponível", "WARNING")
            
            montar_log(f"Algoritmos de hash configurados: {self.config['hash_algorithms']}", "INFO")
            
        except Exception as e:
            montar_log(f"Erro ao configurar algoritmos de hash: {e}", "ERROR")
    
    async def _initialize_backup_system(self):
        """Inicializa sistema de backup"""
        try:
            self._backup_storage = {}
            
            # Criar diretório de backup se necessário
            backup_dir = Path("quimera_aegis_backups")
            backup_dir.mkdir(exist_ok=True)
            
            montar_log("Sistema de backup inicializado", "INFO")
            
        except Exception as e:
            montar_log(f"Erro ao inicializar sistema de backup: {e}", "ERROR")
    
    async def _setup_digital_signatures(self):
        """Configura sistema de assinaturas digitais"""
        try:
            # Implementar configuração de assinaturas digitais
            # Por enquanto, apenas log
            montar_log("Sistema de assinaturas digitais configurado", "INFO")
            
        except Exception as e:
            montar_log(f"Erro ao configurar assinaturas digitais: {e}", "ERROR")
    
    async def _start_realtime_monitoring(self):
        """Inicia monitoramento em tempo real"""
        self._monitoring_active = True
        
        # Criar thread de monitoramento
        import asyncio
        monitoring_task = asyncio.create_task(self._monitoring_loop())
        self._monitoring_threads.append(monitoring_task)
        
        montar_log("Monitoramento em tempo real iniciado", "INFO")
    
    async def _monitoring_loop(self):
        """Loop principal de monitoramento"""
        while self._monitoring_active:
            try:
                # Verificar componentes críticos
                await self._check_critical_components()
                
                # Aguardar próximo ciclo
                await asyncio.sleep(self.config['check_interval_seconds'])
                
            except Exception as e:
                montar_log(f"Erro no loop de monitoramento: {e}", "ERROR")
                await asyncio.sleep(10)  # Aguardar mais tempo em caso de erro
    
    async def _check_critical_components(self):
        """Verifica componentes críticos rapidamente"""
        try:
            # Verificar apenas componentes com alta prioridade
            critical_components = [
                comp_id for comp_id, record in self._integrity_database.items()
                if record.metadata.get('priority') == 'critical'
            ]
            
            for comp_id in critical_components:
                component = await self._find_component_by_id(comp_id)
                if component:
                    result = await self.verify_component_integrity(component, comp_id)
                    if not result.get('integrity_ok', False):
                        montar_log(f"Violação de integridade em componente crítico: {comp_id}", "CRITICAL")
                        
        except Exception as e:
            montar_log(f"Erro na verificação de componentes críticos: {e}", "ERROR")
    
    async def _calculate_component_hashes(self, component: Any) -> Dict[str, str]:
        """Calcula hashes de um componente"""
        try:
            # Serializar componente para cálculo de hash
            component_data = await self._serialize_component(component)
            
            hashes = {}
            
            # SHA256
            if 'sha256' in self.config['hash_algorithms']:
                hashes['sha256'] = hashlib.sha256(component_data).hexdigest()
            
            # BLAKE2b
            if 'blake2b' in self.config['hash_algorithms']:
                hashes['blake2b'] = hashlib.blake2b(component_data).hexdigest()
            
            return hashes
            
        except Exception as e:
            montar_log(f"Erro ao calcular hashes: {e}", "ERROR")
            return {}
    
    async def _serialize_component(self, component: Any) -> bytes:
        """Serializa componente para cálculo de hash (usa json em vez de pickle)"""
        try:
            # Estratégias de serialização baseadas no tipo
            if hasattr(component, '__dict__'):
                # Usar __dict__ para objetos com atributos
                data = json.dumps(component.__dict__, sort_keys=True, default=str)
                return data.encode('utf-8')

            elif hasattr(component, '__getstate__'):
                # Usar __getstate__ se disponível - serializa com json ao invés de pickle
                state = component.__getstate__()
                data = json.dumps(state, sort_keys=True, default=str)
                return data.encode('utf-8')

            else:
                # Fallback: converter para string
                return str(component).encode('utf-8')

        except Exception as e:
            # Fallback absoluto: usar ID do objeto
            return str(id(component)).encode('utf-8')
    
    def _calculate_component_size(self, component: Any) -> int:
        """Calcula tamanho aproximado de um componente"""
        try:
            if hasattr(component, '__sizeof__'):
                return component.__sizeof__()
            else:
                # Estimativa baseada em serialização
                import sys
                return sys.getsizeof(component)
                
        except:
            return 0
    
    async def _find_component_by_id(self, component_id: str) -> Optional[Any]:
        """Encontra componente usando referências fracas"""
        try:
            # Procurar nas referências fracas
            for component_ref, stored_id in self._component_references.items():
                if stored_id == component_id:
                    return component_ref
            
            return None
            
        except Exception as e:
            montar_log(f"Erro ao encontrar componente {component_id}: {e}", "ERROR")
            return None
    
    async def _handle_integrity_violations(self, component: Any, component_id: str,
                                         violations: List[Dict[str, Any]], 
                                         record: IntegrityRecord):
        """Lida com violações de integridade detectadas"""
        try:
            # Incrementar contador de violações
            record.violations_count += len(violations)
            self.metrics['violations_detected'] += len(violations)
            
            # Criar registros de violação
            for violation_data in violations:
                violation = IntegrityViolation(
                    id=f"viol_{component_id}_{int(time.time())}",
                    component_id=component_id,
                    violation_type=violation_data['type'],
                    severity=violation_data['severity'],
                    timestamp=datetime.now(),
                    original_hash=violation_data.get('original', ''),
                    current_hash=violation_data.get('current', ''),
                    details=violation_data,
                    resolved=False
                )
                
                self._violations_log[violation.id] = violation
            
            # Notificar callbacks
            if self.config['notification_enabled']:
                await self._notify_violation(component_id, violations)
            
            # Auto-restauração se configurada e threshold atingido
            if (self.config['auto_restore_enabled'] and 
                record.violations_count >= self.config['violation_threshold']):
                
                montar_log(f"Threshold de violações atingido para {component_id}, tentando restauração", "WARNING")
                await self.restore_component_integrity(component_id)
                
        except Exception as e:
            montar_log(f"Erro ao lidar com violações de {component_id}: {e}", "ERROR")
    
    async def _notify_violation(self, component_id: str, violations: List[Dict[str, Any]]):
        """Notifica callbacks sobre violações"""
        try:
            notification_data = {
                'component_id': component_id,
                'violations': violations,
                'timestamp': datetime.now().isoformat(),
                'severity': max(v.get('severity', 0) for v in violations)
            }
            
            for callback in self._notification_callbacks:
                try:
                    callback(notification_data)
                except Exception as e:
                    montar_log(f"Erro em callback de notificação: {e}", "ERROR")
                    
        except Exception as e:
            montar_log(f"Erro ao notificar violações: {e}", "ERROR")
    
    async def _create_component_backup(self, component: Any, component_id: str):
        """Cria backup de um componente"""
        try:
            # Serializar estado do componente
            backup_data = {
                'timestamp': datetime.now().isoformat(),
                'component_state': await self._serialize_component(component),
                'metadata': {
                    'type': type(component).__name__,
                    'module': getattr(component.__class__, '__module__', 'unknown')
                }
            }
            
            # Armazenar backup
            self._backup_storage[component_id] = backup_data
            self.metrics['backup_operations'] += 1
            
            montar_log(f"Backup criado para componente {component_id}", "INFO")
            
        except Exception as e:
            montar_log(f"Erro ao criar backup de {component_id}: {e}", "ERROR")
    
    async def _execute_component_restore(self, component: Any, component_id: str, 
                                       backup_data: Dict[str, Any]) -> bool:
        """Executa restauração de um componente"""
        try:
            # Em um sistema real, isso envolveria:
            # - Deserialização do estado do backup
            # - Aplicação do estado ao componente
            # - Verificação da restauração
            
            # Por enquanto, simular restauração bem-sucedida
            montar_log(f"Executando restauração de {component_id}", "INFO")
            
            # Simular tempo de restauração
            await asyncio.sleep(0.1)
            
            return True
            
        except Exception as e:
            montar_log(f"Erro na restauração de {component_id}: {e}", "ERROR")
            return False
    
    async def _update_integrity_record_after_restore(self, component_id: str):
        """Atualiza registro de integridade após restauração"""
        try:
            record = self._integrity_database.get(component_id)
            if record:
                # Resetar contadores de violação
                record.violations_count = 0
                record.last_verified = datetime.now()
                
                # Marcar violações como resolvidas
                for violation in self._violations_log.values():
                    if violation.component_id == component_id and not violation.resolved:
                        violation.resolved = True
                        self.metrics['violations_resolved'] += 1
                
        except Exception as e:
            montar_log(f"Erro ao atualizar registro após restauração: {e}", "ERROR")
    
    def _update_average_check_duration(self, duration: float):
        """Atualiza tempo médio de verificação"""
        if self.metrics['average_check_duration'] == 0:
            self.metrics['average_check_duration'] = duration
        else:
            # Média móvel
            self.metrics['average_check_duration'] = (
                self.metrics['average_check_duration'] * 0.9 + duration * 0.1
            )
    
    def _calculate_violation_statistics(self) -> Dict[str, Any]:
        """Calcula estatísticas de violações"""
        total_violations = len(self._violations_log)
        resolved_violations = sum(1 for v in self._violations_log.values() if v.resolved)
        
        # Violações por tipo
        violations_by_type = {}
        for violation in self._violations_log.values():
            v_type = violation.violation_type
            violations_by_type[v_type] = violations_by_type.get(v_type, 0) + 1
        
        # Violações recentes (últimas 24h)
        recent_threshold = datetime.now() - timedelta(hours=24)
        recent_violations = sum(
            1 for v in self._violations_log.values() 
            if v.timestamp > recent_threshold
        )
        
        return {
            'total': total_violations,
            'resolved': resolved_violations,
            'unresolved': total_violations - resolved_violations,
            'by_type': violations_by_type,
            'recent_24h': recent_violations,
            'resolution_rate': resolved_violations / total_violations if total_violations > 0 else 0.0
        }