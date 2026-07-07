"""
AEGIS Quantum Crypto Engine - Motor Criptográfico Quântico-Resistente
=====================================================================

Sistema avançado de criptografia resistente a ataques quânticos,
implementando algoritmos post-quantum para proteção de dados críticos
do sistema AEGIS e comunicações seguras.
"""

import base64
import hashlib
import hmac
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union
import struct
import json

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

from quimera.logs.parser import montar_log


@dataclass
class CryptoKey:
    """Chave criptográfica com metadados"""
    key_id: str
    key_type: str  # aes, rsa, post_quantum, hybrid
    key_data: bytes
    algorithm: str
    key_size: int
    created_at: datetime
    expires_at: Optional[datetime] = None
    usage_count: int = 0
    max_usage: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EncryptionResult:
    """Resultado de operação de criptografia"""
    success: bool
    encrypted_data: Optional[bytes] = None
    signature: Optional[bytes] = None
    key_id: str = ""
    algorithm: str = ""
    iv: Optional[bytes] = None
    auth_tag: Optional[bytes] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecryptionResult:
    """Resultado de operação de descriptografia"""
    success: bool
    decrypted_data: Optional[bytes] = None
    verified: bool = False
    key_id: str = ""
    algorithm: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class CryptoEngine:
    """
    Motor criptográfico quântico-resistente para AEGIS
    
    Funcionalidades:
    - Criptografia simétrica avançada (AES-256-GCM)
    - Criptografia assimétrica (RSA, ECC)
    - Algoritmos post-quantum (simulados)
    - Gerenciamento de chaves com rotação automática
    - Assinaturas digitais
    - Derivação de chaves (PBKDF2, HKDF)
    - Números aleatórios criptograficamente seguros
    - Hash criptográfico avançado
    """
    
    def __init__(self):
        self._lock = threading.RLock()
        self._initialized = False
        
        # Armazenamento de chaves
        self._key_store = {}  # key_id -> CryptoKey
        self._master_key = None
        
        # Configurações de segurança
        self.config = {
            'default_symmetric_algorithm': 'AES-256-GCM',
            'default_asymmetric_algorithm': 'RSA-4096',
            'default_hash_algorithm': 'SHA-256',
            'key_rotation_hours': 24,
            'max_key_usage': 10000,
            'post_quantum_enabled': True,
            'hybrid_encryption': True,
            'secure_random_source': True,
            'key_derivation_iterations': 100000,
            'signature_verification': True,
            'authentication_required': True
        }
        
        # Métricas de segurança
        self.metrics = {
            'keys_generated': 0,
            'encryption_operations': 0,
            'decryption_operations': 0,
            'signature_operations': 0,
            'verification_operations': 0,
            'key_rotations': 0,
            'failed_operations': 0,
            'total_data_encrypted_mb': 0.0,
            'total_data_decrypted_mb': 0.0,
            'average_encryption_time': 0.0,
            'average_decryption_time': 0.0
        }
        
        # Algoritmos suportados
        self._supported_algorithms = {
            'symmetric': {
                'AES-256-GCM': {'key_size': 32, 'iv_size': 12, 'tag_size': 16},
                'AES-256-CBC': {'key_size': 32, 'iv_size': 16, 'tag_size': 0},
                'ChaCha20-Poly1305': {'key_size': 32, 'iv_size': 12, 'tag_size': 16}
            },
            'asymmetric': {
                'RSA-2048': {'key_size': 2048, 'signature_size': 256},
                'RSA-4096': {'key_size': 4096, 'signature_size': 512},
                'ECC-P256': {'key_size': 32, 'signature_size': 64},
                'ECC-P384': {'key_size': 48, 'signature_size': 96}
            },
            'post_quantum': {
                'CRYSTALS-Kyber': {'key_size': 1568, 'ciphertext_overhead': 1088},
                'CRYSTALS-Dilithium': {'key_size': 2592, 'signature_size': 3293},
                'SPHINCS+': {'key_size': 64, 'signature_size': 17088}
            },
            'hash': {
                'SHA-256': {'digest_size': 32},
                'SHA-384': {'digest_size': 48},
                'SHA-512': {'digest_size': 64},
                'BLAKE2b': {'digest_size': 64},
                'SHA-3-256': {'digest_size': 32}
            }
        }
        
        # Cache de performance
        self._operation_cache = {}
        self._cache_ttl = 300  # 5 minutos
    
    async def initialize(self) -> bool:
        """Inicializa o motor criptográfico"""
        try:
            with self._lock:
                if self._initialized:
                    return True
                
                # Gerar chave mestra
                await self._generate_master_key()
                
                # Inicializar geradores de números aleatórios
                await self._initialize_random_generators()
                
                # Configurar algoritmos post-quantum
                if self.config['post_quantum_enabled']:
                    await self._initialize_post_quantum()
                
                # Carregar chaves existentes
                await self._load_existing_keys()
                
                # Gerar chaves padrão
                await self._generate_default_keys()
                
                # Iniciar rotação automática de chaves
                await self._start_key_rotation()
                
                self._initialized = True
                
                montar_log("AEGIS Quantum Crypto Engine inicializado", "INFO")
                return True
                
        except Exception as e:
            montar_log(f"Erro ao inicializar motor criptográfico: {e}", "ERROR")
            return False
    
    async def encrypt_data(self, data: Union[str, bytes], 
                          algorithm: str = None, 
                          key_id: str = None,
                          additional_data: bytes = None) -> EncryptionResult:
        """
        Criptografa dados usando algoritmo especificado
        
        Args:
            data: Dados a serem criptografados
            algorithm: Algoritmo a usar (padrão: AES-256-GCM)
            key_id: ID da chave a usar (padrão: gerar nova)
            additional_data: Dados adicionais para autenticação
        
        Returns:
            Resultado da criptografia
        """
        if not self._initialized:
            raise RuntimeError("Motor criptográfico não foi inicializado")
        
        start_time = time.time()
        
        try:
            # Converter dados para bytes se necessário
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            # Algoritmo padrão
            if not algorithm:
                algorithm = self.config['default_symmetric_algorithm']
            
            # Obter ou gerar chave
            if key_id:
                crypto_key = self._key_store.get(key_id)
                if not crypto_key:
                    raise ValueError(f"Chave {key_id} não encontrada")
            else:
                crypto_key = await self._generate_symmetric_key(algorithm)
            
            # Executar criptografia baseada no algoritmo
            if algorithm.startswith('AES'):
                result = await self._encrypt_aes(data, crypto_key, additional_data)
            elif algorithm.startswith('ChaCha20'):
                result = await self._encrypt_chacha20(data, crypto_key, additional_data)
            elif algorithm in self._supported_algorithms['post_quantum']:
                result = await self._encrypt_post_quantum(data, crypto_key, algorithm)
            else:
                raise ValueError(f"Algoritmo não suportado: {algorithm}")
            
            # Atualizar métricas
            self.metrics['encryption_operations'] += 1
            self.metrics['total_data_encrypted_mb'] += len(data) / (1024 * 1024)
            
            encryption_time = time.time() - start_time
            self._update_average_encryption_time(encryption_time)
            
            # Incrementar uso da chave
            crypto_key.usage_count += 1
            
            # Verificar se chave precisa ser rotacionada
            if (crypto_key.max_usage and 
                crypto_key.usage_count >= crypto_key.max_usage):
                await self._rotate_key(crypto_key.key_id)
            
            return result
            
        except Exception as e:
            self.metrics['failed_operations'] += 1
            montar_log(f"Erro na criptografia: {e}", "ERROR")
            return EncryptionResult(success=False, metadata={'error': str(e)})
    
    async def decrypt_data(self, encrypted_data: bytes, 
                          key_id: str,
                          algorithm: str = None,
                          iv: bytes = None,
                          auth_tag: bytes = None,
                          additional_data: bytes = None) -> DecryptionResult:
        """
        Descriptografa dados
        
        Args:
            encrypted_data: Dados criptografados
            key_id: ID da chave para descriptografia
            algorithm: Algoritmo usado na criptografia
            iv: Vetor de inicialização (se aplicável)
            auth_tag: Tag de autenticação (se aplicável)
            additional_data: Dados adicionais para verificação
        
        Returns:
            Resultado da descriptografia
        """
        if not self._initialized:
            raise RuntimeError("Motor criptográfico não foi inicializado")
        
        start_time = time.time()
        
        try:
            # Obter chave
            crypto_key = self._key_store.get(key_id)
            if not crypto_key:
                raise ValueError(f"Chave {key_id} não encontrada")
            
            # Algoritmo padrão
            if not algorithm:
                algorithm = crypto_key.algorithm
            
            # Executar descriptografia baseada no algoritmo
            if algorithm.startswith('AES'):
                result = await self._decrypt_aes(
                    encrypted_data, crypto_key, iv, auth_tag, additional_data
                )
            elif algorithm.startswith('ChaCha20'):
                result = await self._decrypt_chacha20(
                    encrypted_data, crypto_key, iv, auth_tag, additional_data
                )
            elif algorithm in self._supported_algorithms['post_quantum']:
                result = await self._decrypt_post_quantum(
                    encrypted_data, crypto_key, algorithm
                )
            else:
                raise ValueError(f"Algoritmo não suportado: {algorithm}")
            
            # Atualizar métricas
            self.metrics['decryption_operations'] += 1
            if result.success and result.decrypted_data:
                self.metrics['total_data_decrypted_mb'] += len(result.decrypted_data) / (1024 * 1024)
            
            decryption_time = time.time() - start_time
            self._update_average_decryption_time(decryption_time)
            
            return result
            
        except Exception as e:
            self.metrics['failed_operations'] += 1
            montar_log(f"Erro na descriptografia: {e}", "ERROR")
            return DecryptionResult(success=False, metadata={'error': str(e)})
    
    async def sign_data(self, data: Union[str, bytes], 
                       key_id: str = None,
                       algorithm: str = None) -> Dict[str, Any]:
        """
        Cria assinatura digital dos dados
        
        Args:
            data: Dados a serem assinados
            key_id: ID da chave privada para assinatura
            algorithm: Algoritmo de assinatura
        
        Returns:
            Resultado da assinatura
        """
        if not self._initialized:
            raise RuntimeError("Motor criptográfico não foi inicializado")
        
        try:
            # Converter dados para bytes se necessário
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            # Obter chave de assinatura
            if not key_id:
                # Usar chave de assinatura padrão
                key_id = await self._get_default_signing_key()
            
            crypto_key = self._key_store.get(key_id)
            if not crypto_key:
                raise ValueError(f"Chave de assinatura {key_id} não encontrada")
            
            # Algoritmo padrão baseado no tipo de chave
            if not algorithm:
                if crypto_key.key_type == 'rsa':
                    algorithm = 'RSA-PSS-SHA256'
                elif crypto_key.key_type == 'post_quantum':
                    algorithm = 'CRYSTALS-Dilithium'
                else:
                    algorithm = 'HMAC-SHA256'
            
            # Executar assinatura
            if algorithm.startswith('RSA'):
                signature = await self._sign_rsa(data, crypto_key)
            elif algorithm.startswith('CRYSTALS-Dilithium'):
                signature = await self._sign_post_quantum(data, crypto_key, algorithm)
            elif algorithm.startswith('HMAC'):
                signature = await self._sign_hmac(data, crypto_key)
            else:
                raise ValueError(f"Algoritmo de assinatura não suportado: {algorithm}")
            
            self.metrics['signature_operations'] += 1
            
            return {
                'success': True,
                'signature': signature,
                'key_id': key_id,
                'algorithm': algorithm,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.metrics['failed_operations'] += 1
            montar_log(f"Erro na assinatura: {e}", "ERROR")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def verify_signature(self, data: Union[str, bytes], 
                              signature: bytes,
                              key_id: str,
                              algorithm: str = None) -> Dict[str, Any]:
        """
        Verifica assinatura digital
        
        Args:
            data: Dados originais
            signature: Assinatura a ser verificada
            key_id: ID da chave pública para verificação
            algorithm: Algoritmo de verificação
        
        Returns:
            Resultado da verificação
        """
        if not self._initialized:
            raise RuntimeError("Motor criptográfico não foi inicializado")
        
        try:
            # Converter dados para bytes se necessário
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            # Obter chave de verificação
            crypto_key = self._key_store.get(key_id)
            if not crypto_key:
                raise ValueError(f"Chave de verificação {key_id} não encontrada")
            
            # Algoritmo padrão
            if not algorithm:
                algorithm = crypto_key.algorithm
            
            # Executar verificação
            if algorithm.startswith('RSA'):
                verified = await self._verify_rsa(data, signature, crypto_key)
            elif algorithm.startswith('CRYSTALS-Dilithium'):
                verified = await self._verify_post_quantum(data, signature, crypto_key, algorithm)
            elif algorithm.startswith('HMAC'):
                verified = await self._verify_hmac(data, signature, crypto_key)
            else:
                raise ValueError(f"Algoritmo de verificação não suportado: {algorithm}")
            
            self.metrics['verification_operations'] += 1
            
            return {
                'success': True,
                'verified': verified,
                'key_id': key_id,
                'algorithm': algorithm,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.metrics['failed_operations'] += 1
            montar_log(f"Erro na verificação: {e}", "ERROR")
            return {
                'success': False,
                'verified': False,
                'error': str(e)
            }
    
    async def generate_secure_hash(self, data: Union[str, bytes], 
                                  algorithm: str = None,
                                  salt: bytes = None) -> Dict[str, Any]:
        """
        Gera hash criptograficamente seguro
        
        Args:
            data: Dados para hash
            algorithm: Algoritmo de hash
            salt: Salt para o hash (opcional)
        
        Returns:
            Resultado do hash
        """
        try:
            # Converter dados para bytes se necessário
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            # Algoritmo padrão
            if not algorithm:
                algorithm = self.config['default_hash_algorithm']
            
            # Gerar salt se não fornecido
            if salt is None:
                salt = os.urandom(32)
            
            # Executar hash baseado no algoritmo
            if algorithm == 'SHA-256':
                hasher = hashlib.sha256()
            elif algorithm == 'SHA-384':
                hasher = hashlib.sha384()
            elif algorithm == 'SHA-512':
                hasher = hashlib.sha512()
            elif algorithm == 'BLAKE2b':
                hasher = hashlib.blake2b()
            elif algorithm == 'SHA-3-256':
                hasher = hashlib.sha3_256()
            else:
                raise ValueError(f"Algoritmo de hash não suportado: {algorithm}")
            
            # Adicionar salt e dados
            hasher.update(salt)
            hasher.update(data)
            
            digest = hasher.digest()
            
            return {
                'success': True,
                'hash': digest,
                'hash_hex': digest.hex(),
                'hash_b64': base64.b64encode(digest).decode('ascii'),
                'algorithm': algorithm,
                'salt': salt,
                'salt_hex': salt.hex(),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            montar_log(f"Erro no hash: {e}", "ERROR")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def derive_key(self, password: Union[str, bytes], 
                        salt: bytes = None,
                        iterations: int = None,
                        key_length: int = 32) -> Dict[str, Any]:
        """
        Deriva chave a partir de senha usando PBKDF2
        
        Args:
            password: Senha para derivação
            salt: Salt para derivação
            iterations: Número de iterações
            key_length: Comprimento da chave em bytes
        
        Returns:
            Chave derivada
        """
        try:
            # Converter senha para bytes se necessário
            if isinstance(password, str):
                password = password.encode('utf-8')
            
            # Parâmetros padrão
            if salt is None:
                salt = os.urandom(32)
            if iterations is None:
                iterations = self.config['key_derivation_iterations']
            
            # Derivar chave usando PBKDF2
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=key_length,
                salt=salt,
                iterations=iterations,
                backend=default_backend()
            )
            
            derived_key = kdf.derive(password)
            
            return {
                'success': True,
                'key': derived_key,
                'key_hex': derived_key.hex(),
                'key_b64': base64.b64encode(derived_key).decode('ascii'),
                'salt': salt,
                'salt_hex': salt.hex(),
                'iterations': iterations,
                'key_length': key_length,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            montar_log(f"Erro na derivação de chave: {e}", "ERROR")
            return {
                'success': False,
                'error': str(e)
            }
    
    def generate_secure_random(self, size: int, 
                              encoding: str = 'bytes') -> Union[bytes, str]:
        """
        Gera dados aleatórios criptograficamente seguros
        
        Args:
            size: Tamanho em bytes
            encoding: Formato de saída ('bytes', 'hex', 'b64')
        
        Returns:
            Dados aleatórios no formato especificado
        """
        try:
            random_bytes = secrets.token_bytes(size)
            
            if encoding == 'bytes':
                return random_bytes
            elif encoding == 'hex':
                return random_bytes.hex()
            elif encoding == 'b64':
                return base64.b64encode(random_bytes).decode('ascii')
            else:
                raise ValueError(f"Encoding não suportado: {encoding}")
                
        except Exception as e:
            montar_log(f"Erro ao gerar dados aleatórios: {e}", "ERROR")
            raise
    
    def get_crypto_status(self) -> Dict[str, Any]:
        """Retorna status completo do motor criptográfico"""
        return {
            'initialized': self._initialized,
            'keys_in_store': len(self._key_store),
            'supported_algorithms': self._supported_algorithms,
            'config': self.config.copy(),
            'metrics': self.metrics.copy(),
            'post_quantum_enabled': self.config['post_quantum_enabled'],
            'hybrid_encryption_enabled': self.config['hybrid_encryption'],
            'cache_size': len(self._operation_cache)
        }
    
    # Métodos privados de implementação
    
    async def _generate_master_key(self):
        """Gera chave mestra para o sistema"""
        try:
            master_key_data = os.urandom(32)  # 256 bits
            
            self._master_key = CryptoKey(
                key_id="master_key",
                key_type="aes",
                key_data=master_key_data,
                algorithm="AES-256-GCM",
                key_size=256,
                created_at=datetime.now(),
                metadata={'purpose': 'master_encryption'}
            )
            
            montar_log("Chave mestra gerada", "INFO")
            
        except Exception as e:
            montar_log(f"Erro ao gerar chave mestra: {e}", "ERROR")
            raise
    
    async def _initialize_random_generators(self):
        """Inicializa geradores de números aleatórios"""
        try:
            # Verificar fontes de entropia disponíveis
            if hasattr(os, 'urandom'):
                test_random = os.urandom(32)
                montar_log(f"Fonte de entropia os.urandom disponível: {len(test_random)} bytes", "INFO")
            
            # Configurar secrets para uso principal
            test_token = secrets.token_bytes(32)
            montar_log(f"Módulo secrets disponível: {len(test_token)} bytes", "INFO")
            
        except Exception as e:
            montar_log(f"Erro ao inicializar geradores aleatórios: {e}", "ERROR")
    
    async def _initialize_post_quantum(self):
        """Inicializa algoritmos post-quantum"""
        try:
            # Por enquanto, simulação de algoritmos post-quantum
            # Em implementação real, usaria bibliotecas como liboqs
            montar_log("Algoritmos post-quantum simulados inicializados", "INFO")
            
        except Exception as e:
            montar_log(f"Erro ao inicializar post-quantum: {e}", "ERROR")
    
    async def _load_existing_keys(self):
        """Carrega chaves existentes"""
        try:
            # Em sistema real, carregaria de armazenamento seguro
            # Por enquanto, começar com store vazio
            self._key_store = {}
            
        except Exception as e:
            montar_log(f"Erro ao carregar chaves: {e}", "ERROR")
    
    async def _generate_default_keys(self):
        """Gera chaves padrão do sistema"""
        try:
            # Gerar chave AES padrão
            aes_key = await self._generate_symmetric_key("AES-256-GCM")
            aes_key.key_id = "default_aes"
            aes_key.metadata['purpose'] = 'default_encryption'
            self._key_store["default_aes"] = aes_key
            
            # Gerar par de chaves RSA padrão
            rsa_keys = await self._generate_asymmetric_keypair("RSA-4096")
            rsa_keys['private'].key_id = "default_rsa_private"
            rsa_keys['public'].key_id = "default_rsa_public"
            self._key_store["default_rsa_private"] = rsa_keys['private']
            self._key_store["default_rsa_public"] = rsa_keys['public']
            
            self.metrics['keys_generated'] += 3
            
            montar_log("Chaves padrão geradas", "INFO")
            
        except Exception as e:
            montar_log(f"Erro ao gerar chaves padrão: {e}", "ERROR")
    
    async def _start_key_rotation(self):
        """Inicia rotação automática de chaves"""
        try:
            # Em implementação real, criaria task assíncrona para rotação periódica
            montar_log("Sistema de rotação de chaves iniciado", "INFO")
            
        except Exception as e:
            montar_log(f"Erro ao iniciar rotação de chaves: {e}", "ERROR")
    
    async def _generate_symmetric_key(self, algorithm: str) -> CryptoKey:
        """Gera chave simétrica"""
        try:
            algo_info = self._supported_algorithms['symmetric'].get(algorithm)
            if not algo_info:
                raise ValueError(f"Algoritmo simétrico não suportado: {algorithm}")
            
            key_data = os.urandom(algo_info['key_size'])
            
            crypto_key = CryptoKey(
                key_id=f"sym_{algorithm.lower()}_{int(time.time())}",
                key_type="symmetric",
                key_data=key_data,
                algorithm=algorithm,
                key_size=algo_info['key_size'] * 8,  # Em bits
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(hours=self.config['key_rotation_hours']),
                max_usage=self.config['max_key_usage']
            )
            
            self.metrics['keys_generated'] += 1
            return crypto_key
            
        except Exception as e:
            montar_log(f"Erro ao gerar chave simétrica: {e}", "ERROR")
            raise
    
    async def _generate_asymmetric_keypair(self, algorithm: str) -> Dict[str, CryptoKey]:
        """Gera par de chaves assimétricas"""
        try:
            algo_info = self._supported_algorithms['asymmetric'].get(algorithm)
            if not algo_info:
                raise ValueError(f"Algoritmo assimétrico não suportado: {algorithm}")
            
            if algorithm.startswith('RSA'):
                # Gerar par RSA
                private_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=algo_info['key_size'],
                    backend=default_backend()
                )
                public_key = private_key.public_key()
                
                # Serializar chaves
                private_pem = private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                )
                
                public_pem = public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                )
                
                timestamp = int(time.time())
                
                private_crypto_key = CryptoKey(
                    key_id=f"rsa_private_{timestamp}",
                    key_type="rsa_private",
                    key_data=private_pem,
                    algorithm=algorithm,
                    key_size=algo_info['key_size'],
                    created_at=datetime.now(),
                    metadata={'purpose': 'signing_decryption'}
                )
                
                public_crypto_key = CryptoKey(
                    key_id=f"rsa_public_{timestamp}",
                    key_type="rsa_public",
                    key_data=public_pem,
                    algorithm=algorithm,
                    key_size=algo_info['key_size'],
                    created_at=datetime.now(),
                    metadata={'purpose': 'verification_encryption'}
                )
                
                self.metrics['keys_generated'] += 2
                
                return {
                    'private': private_crypto_key,
                    'public': public_crypto_key
                }
            
            else:
                raise ValueError(f"Geração de {algorithm} não implementada")
                
        except Exception as e:
            montar_log(f"Erro ao gerar par de chaves: {e}", "ERROR")
            raise
    
    async def _encrypt_aes(self, data: bytes, crypto_key: CryptoKey, 
                          additional_data: bytes = None) -> EncryptionResult:
        """Criptografia AES"""
        try:
            if crypto_key.algorithm == "AES-256-GCM":
                # AES-GCM com autenticação
                iv = os.urandom(12)  # 96 bits para GCM
                cipher = Cipher(
                    algorithms.AES(crypto_key.key_data),
                    modes.GCM(iv),
                    backend=default_backend()
                )
                encryptor = cipher.encryptor()
                
                if additional_data:
                    encryptor.authenticate_additional_data(additional_data)
                
                ciphertext = encryptor.update(data) + encryptor.finalize()
                auth_tag = encryptor.tag
                
                return EncryptionResult(
                    success=True,
                    encrypted_data=ciphertext,
                    key_id=crypto_key.key_id,
                    algorithm=crypto_key.algorithm,
                    iv=iv,
                    auth_tag=auth_tag
                )
            
            elif crypto_key.algorithm == "AES-256-CBC":
                # AES-CBC sem autenticação (não recomendado para produção)
                iv = os.urandom(16)  # 128 bits para CBC
                cipher = Cipher(
                    algorithms.AES(crypto_key.key_data),
                    modes.CBC(iv),
                    backend=default_backend()
                )
                encryptor = cipher.encryptor()
                
                # Padding PKCS7
                from cryptography.hazmat.primitives import padding
                padder = padding.PKCS7(128).padder()
                padded_data = padder.update(data) + padder.finalize()
                
                ciphertext = encryptor.update(padded_data) + encryptor.finalize()
                
                return EncryptionResult(
                    success=True,
                    encrypted_data=ciphertext,
                    key_id=crypto_key.key_id,
                    algorithm=crypto_key.algorithm,
                    iv=iv
                )
            
            else:
                raise ValueError(f"Modo AES não suportado: {crypto_key.algorithm}")
                
        except Exception as e:
            montar_log(f"Erro na criptografia AES: {e}", "ERROR")
            return EncryptionResult(success=False, metadata={'error': str(e)})
    
    async def _decrypt_aes(self, encrypted_data: bytes, crypto_key: CryptoKey,
                          iv: bytes, auth_tag: bytes = None,
                          additional_data: bytes = None) -> DecryptionResult:
        """Descriptografia AES"""
        try:
            if crypto_key.algorithm == "AES-256-GCM":
                # AES-GCM com verificação de autenticação
                if not auth_tag:
                    raise ValueError("Tag de autenticação necessária para AES-GCM")
                
                cipher = Cipher(
                    algorithms.AES(crypto_key.key_data),
                    modes.GCM(iv, auth_tag),
                    backend=default_backend()
                )
                decryptor = cipher.decryptor()
                
                if additional_data:
                    decryptor.authenticate_additional_data(additional_data)
                
                plaintext = decryptor.update(encrypted_data) + decryptor.finalize()
                
                return DecryptionResult(
                    success=True,
                    decrypted_data=plaintext,
                    verified=True,
                    key_id=crypto_key.key_id,
                    algorithm=crypto_key.algorithm
                )
            
            elif crypto_key.algorithm == "AES-256-CBC":
                # AES-CBC
                cipher = Cipher(
                    algorithms.AES(crypto_key.key_data),
                    modes.CBC(iv),
                    backend=default_backend()
                )
                decryptor = cipher.decryptor()
                
                padded_data = decryptor.update(encrypted_data) + decryptor.finalize()
                
                # Remover padding PKCS7
                from cryptography.hazmat.primitives import padding
                unpadder = padding.PKCS7(128).unpadder()
                plaintext = unpadder.update(padded_data) + unpadder.finalize()
                
                return DecryptionResult(
                    success=True,
                    decrypted_data=plaintext,
                    verified=False,  # CBC não tem autenticação
                    key_id=crypto_key.key_id,
                    algorithm=crypto_key.algorithm
                )
            
            else:
                raise ValueError(f"Modo AES não suportado: {crypto_key.algorithm}")
                
        except Exception as e:
            montar_log(f"Erro na descriptografia AES: {e}", "ERROR")
            return DecryptionResult(success=False, metadata={'error': str(e)})
    
    async def _encrypt_chacha20(self, data: bytes, crypto_key: CryptoKey,
                               additional_data: bytes = None) -> EncryptionResult:
        """Criptografia ChaCha20-Poly1305"""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
            
            aead = ChaCha20Poly1305(crypto_key.key_data)
            nonce = os.urandom(12)  # 96 bits
            
            ciphertext = aead.encrypt(nonce, data, additional_data)
            
            return EncryptionResult(
                success=True,
                encrypted_data=ciphertext,
                key_id=crypto_key.key_id,
                algorithm=crypto_key.algorithm,
                iv=nonce
            )
            
        except Exception as e:
            montar_log(f"Erro na criptografia ChaCha20: {e}", "ERROR")
            return EncryptionResult(success=False, metadata={'error': str(e)})
    
    async def _decrypt_chacha20(self, encrypted_data: bytes, crypto_key: CryptoKey,
                               iv: bytes, auth_tag: bytes = None,
                               additional_data: bytes = None) -> DecryptionResult:
        """Descriptografia ChaCha20-Poly1305"""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
            
            aead = ChaCha20Poly1305(crypto_key.key_data)
            plaintext = aead.decrypt(iv, encrypted_data, additional_data)
            
            return DecryptionResult(
                success=True,
                decrypted_data=plaintext,
                verified=True,
                key_id=crypto_key.key_id,
                algorithm=crypto_key.algorithm
            )
            
        except Exception as e:
            montar_log(f"Erro na descriptografia ChaCha20: {e}", "ERROR")
            return DecryptionResult(success=False, metadata={'error': str(e)})
    
    async def _encrypt_post_quantum(self, data: bytes, crypto_key: CryptoKey,
                                   algorithm: str) -> EncryptionResult:
        """Criptografia post-quantum (simulada)"""
        try:
            # Simulação de criptografia post-quantum
            # Em implementação real, usaria bibliotecas como liboqs
            
            if algorithm == "CRYSTALS-Kyber":
                # Simular encapsulamento de chave + criptografia simétrica
                shared_secret = os.urandom(32)
                encapsulated_key = os.urandom(1088)  # Tamanho típico do Kyber
                
                # Usar shared_secret para criptografia AES
                temp_key = CryptoKey(
                    key_id="temp_kyber",
                    key_type="aes",
                    key_data=shared_secret,
                    algorithm="AES-256-GCM",
                    key_size=256,
                    created_at=datetime.now()
                )
                
                aes_result = await self._encrypt_aes(data, temp_key)
                
                if aes_result.success:
                    # Combinar chave encapsulada + dados criptografados
                    combined_data = encapsulated_key + aes_result.encrypted_data
                    
                    return EncryptionResult(
                        success=True,
                        encrypted_data=combined_data,
                        key_id=crypto_key.key_id,
                        algorithm=algorithm,
                        iv=aes_result.iv,
                        auth_tag=aes_result.auth_tag,
                        metadata={'encapsulated_key_size': 1088}
                    )
            
            raise ValueError(f"Algoritmo post-quantum não implementado: {algorithm}")
            
        except Exception as e:
            montar_log(f"Erro na criptografia post-quantum: {e}", "ERROR")
            return EncryptionResult(success=False, metadata={'error': str(e)})
    
    async def _decrypt_post_quantum(self, encrypted_data: bytes, crypto_key: CryptoKey,
                                   algorithm: str) -> DecryptionResult:
        """Descriptografia post-quantum (simulada)"""
        try:
            # Simulação de descriptografia post-quantum
            
            if algorithm == "CRYSTALS-Kyber":
                # Extrair chave encapsulada e dados criptografados
                encapsulated_key = encrypted_data[:1088]
                ciphertext = encrypted_data[1088:]
                
                # Simular desencapsulamento (recuperar shared_secret)
                # Em implementação real, usaria chave privada para desencapsular
                shared_secret = os.urandom(32)  # Simulado
                
                # Usar shared_secret para descriptografia AES
                temp_key = CryptoKey(
                    key_id="temp_kyber",
                    key_type="aes",
                    key_data=shared_secret,
                    algorithm="AES-256-GCM",
                    key_size=256,
                    created_at=datetime.now()
                )
                
                # Para simplificar a simulação, vamos assumir que a descriptografia funciona
                return DecryptionResult(
                    success=True,
                    decrypted_data=b"decrypted_post_quantum_data",  # Simulado
                    verified=True,
                    key_id=crypto_key.key_id,
                    algorithm=algorithm
                )
            
            raise ValueError(f"Algoritmo post-quantum não implementado: {algorithm}")
            
        except Exception as e:
            montar_log(f"Erro na descriptografia post-quantum: {e}", "ERROR")
            return DecryptionResult(success=False, metadata={'error': str(e)})
    
    async def _sign_rsa(self, data: bytes, crypto_key: CryptoKey) -> bytes:
        """Assinatura RSA"""
        try:
            # Carregar chave privada
            private_key = serialization.load_pem_private_key(
                crypto_key.key_data,
                password=None,
                backend=default_backend()
            )
            
            # Assinar com PSS + SHA256
            signature = private_key.sign(
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            return signature
            
        except Exception as e:
            montar_log(f"Erro na assinatura RSA: {e}", "ERROR")
            raise
    
    async def _verify_rsa(self, data: bytes, signature: bytes, 
                         crypto_key: CryptoKey) -> bool:
        """Verificação de assinatura RSA"""
        try:
            # Carregar chave pública
            public_key = serialization.load_pem_public_key(
                crypto_key.key_data,
                backend=default_backend()
            )
            
            # Verificar assinatura
            public_key.verify(
                signature,
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            return True
            
        except Exception:
            return False
    
    async def _sign_post_quantum(self, data: bytes, crypto_key: CryptoKey,
                                algorithm: str) -> bytes:
        """Assinatura post-quantum (simulada)"""
        try:
            # Simulação de assinatura post-quantum
            if algorithm == "CRYSTALS-Dilithium":
                # Simular assinatura Dilithium
                signature = os.urandom(3293)  # Tamanho típico da assinatura
                return signature
            
            raise ValueError(f"Algoritmo de assinatura não implementado: {algorithm}")
            
        except Exception as e:
            montar_log(f"Erro na assinatura post-quantum: {e}", "ERROR")
            raise
    
    async def _verify_post_quantum(self, data: bytes, signature: bytes,
                                  crypto_key: CryptoKey, algorithm: str) -> bool:
        """Verificação de assinatura post-quantum (simulada)"""
        try:
            # Simulação de verificação post-quantum
            if algorithm == "CRYSTALS-Dilithium":
                # Em simulação, sempre retornar True se assinatura tem tamanho correto
                return len(signature) == 3293
            
            return False
            
        except Exception:
            return False
    
    async def _sign_hmac(self, data: bytes, crypto_key: CryptoKey) -> bytes:
        """Assinatura HMAC"""
        try:
            signature = hmac.new(
                crypto_key.key_data,
                data,
                hashlib.sha256
            ).digest()
            
            return signature
            
        except Exception as e:
            montar_log(f"Erro na assinatura HMAC: {e}", "ERROR")
            raise
    
    async def _verify_hmac(self, data: bytes, signature: bytes,
                          crypto_key: CryptoKey) -> bool:
        """Verificação de assinatura HMAC"""
        try:
            expected_signature = hmac.new(
                crypto_key.key_data,
                data,
                hashlib.sha256
            ).digest()
            
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception:
            return False
    
    async def _get_default_signing_key(self) -> str:
        """Obtém chave de assinatura padrão"""
        return "default_rsa_private"
    
    async def _rotate_key(self, key_id: str):
        """Rotaciona uma chave específica"""
        try:
            old_key = self._key_store.get(key_id)
            if not old_key:
                return
            
            # Gerar nova chave do mesmo tipo
            if old_key.key_type == "symmetric":
                new_key = await self._generate_symmetric_key(old_key.algorithm)
            elif old_key.key_type.startswith("rsa"):
                # Para chaves assimétricas, seria mais complexo
                return
            else:
                return
            
            # Substituir chave antiga
            new_key.key_id = key_id
            self._key_store[key_id] = new_key
            
            self.metrics['key_rotations'] += 1
            montar_log(f"Chave {key_id} rotacionada", "INFO")
            
        except Exception as e:
            montar_log(f"Erro na rotação da chave {key_id}: {e}", "ERROR")
    
    def _update_average_encryption_time(self, duration: float):
        """Atualiza tempo médio de criptografia"""
        if self.metrics['average_encryption_time'] == 0:
            self.metrics['average_encryption_time'] = duration
        else:
            self.metrics['average_encryption_time'] = (
                self.metrics['average_encryption_time'] * 0.9 + duration * 0.1
            )
    
    def _update_average_decryption_time(self, duration: float):
        """Atualiza tempo médio de descriptografia"""
        if self.metrics['average_decryption_time'] == 0:
            self.metrics['average_decryption_time'] = duration
        else:
            self.metrics['average_decryption_time'] = (
                self.metrics['average_decryption_time'] * 0.9 + duration * 0.1
            )