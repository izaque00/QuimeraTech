"""
Multi-LLM Orchestrator Ultra-Avançado
Sistema de orquestração inteligente de múltiplos modelos de linguagem
Tecnologia de nível NASA/Google para análise de código distribuída
"""

import asyncio
import logging
import json
import time
import hashlib
import statistics
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict, deque
import threading
import sqlite3
from pathlib import Path

# Integração com modelos de IA
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Integração com modelos locais
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

try:
    from llama_cpp import Llama
    LLAMACPP_AVAILABLE = True
except ImportError:
    LLAMACPP_AVAILABLE = False

from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)


class LLMSpecialization(Enum):
    """Especializations for different LLMs"""
    CODE_ANALYSIS = "code_analysis"
    VULNERABILITY_DETECTION = "vulnerability_detection"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    CODE_GENERATION = "code_generation"
    REFACTORING = "refactoring"
    DOCUMENTATION = "documentation"
    DEBUGGING = "debugging"
    ARCHITECTURE_REVIEW = "architecture_review"
    SECURITY_ANALYSIS = "security_analysis"
    CODE_REVIEW = "code_review"


@dataclass
class LLMRequest:
    """Request to be processed by LLM"""
    id: str
    specialization: LLMSpecialization
    prompt: str
    code_context: str
    metadata: Dict[str, Any]
    priority: int = 1  # 1=highest, 5=lowest
    timeout: int = 30
    requires_consensus: bool = False
    min_models: int = 1
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class LLMResponse:
    """Response from LLM processing"""
    request_id: str
    model_name: str
    response: str
    confidence: float
    processing_time: float
    tokens_used: int
    cost_estimate: float
    metadata: Dict[str, Any]
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class LLMModel:
    """Configuration for an LLM model"""
    name: str
    provider: str  # openai, anthropic, huggingface, ollama, llamacpp
    model_id: str
    specializations: List[LLMSpecialization]
    max_tokens: int
    cost_per_token: float
    performance_score: float
    availability: bool = True
    endpoint: Optional[str] = None
    api_key: Optional[str] = None
    local_path: Optional[str] = None
    config: Dict[str, Any] = field(default_factory=dict)


class ModelPerformanceTracker:
    """Tracks model performance and automatically adjusts selection"""

    def __init__(self, db_path: str = "llm_performance.db"):
        self.db_path = db_path
        self._init_db()
        self.performance_cache = defaultdict(list)
        self.lock = threading.Lock()

    def _init_db(self):
        """Initialize SQLite database for performance tracking"""
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS model_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL,
                specialization TEXT NOT NULL,
                response_time REAL NOT NULL,
                accuracy_score REAL,
                cost REAL,
                tokens_used INTEGER,
                success BOOLEAN NOT NULL,
                timestamp REAL NOT NULL
            )
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_model_spec
            ON model_performance(model_name, specialization)
        ''')
        conn.commit()
        conn.close()

    def record_performance(self, model_name: str, specialization: LLMSpecialization,
                          response_time: float, accuracy: Optional[float] = None,
                          cost: float = 0, tokens: int = 0, success: bool = True):
        """Record model performance metrics"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute('''
                INSERT INTO model_performance
                (model_name, specialization, response_time, accuracy_score, cost, tokens_used, success, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (model_name, specialization.value, response_time, accuracy, cost, tokens, success, time.time()))
            conn.commit()
            conn.close()

            # Update cache
            key = f"{model_name}_{specialization.value}"
            self.performance_cache[key].append({
                'response_time': response_time,
                'accuracy': accuracy,
                'cost': cost,
                'success': success,
                'timestamp': time.time()
            })

            # Keep only last 100 entries in cache
            if len(self.performance_cache[key]) > 100:
                self.performance_cache[key] = self.performance_cache[key][-100:]

    def get_model_score(self, model_name: str, specialization: LLMSpecialization) -> float:
        """Get composite performance score for model/specialization combination"""
        key = f"{model_name}_{specialization.value}"

        if key not in self.performance_cache:
            # Load from database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute('''
                SELECT response_time, accuracy_score, cost, success
                FROM model_performance
                WHERE model_name = ? AND specialization = ?
                ORDER BY timestamp DESC LIMIT 100
            ''', (model_name, specialization.value))

            data = cursor.fetchall()
            conn.close()

            if not data:
                return 0.5  # Default score for new models

            self.performance_cache[key] = [
                {
                    'response_time': row[0],
                    'accuracy': row[1],
                    'cost': row[2],
                    'success': bool(row[3])
                }
                for row in data
            ]

        metrics = self.performance_cache[key]
        if not metrics:
            return 0.5

        # Calculate composite score
        success_rate = sum(1 for m in metrics if m['success']) / len(metrics)
        avg_response_time = statistics.mean(m['response_time'] for m in metrics)
        avg_cost = statistics.mean(m['cost'] for m in metrics if m['cost'] > 0)
        accuracies = [m['accuracy'] for m in metrics if m['accuracy'] is not None]
        avg_accuracy = statistics.mean(accuracies) if accuracies else 0.7

        # Normalize and weight components
        time_score = max(0, 1 - (avg_response_time / 60))  # Penalize if > 60s
        cost_score = max(0, 1 - (avg_cost / 0.1))  # Penalize if > $0.10

        composite_score = (
            success_rate * 0.4 +
            avg_accuracy * 0.3 +
            time_score * 0.2 +
            cost_score * 0.1
        )

        return max(0, min(1, composite_score))


class MultiLLMOrchestrator:
    """
    Orquestrador ultra-avançado de múltiplos modelos de linguagem
    Seleciona automaticamente os melhores modelos para cada tarefa
    """

    def __init__(self, config_path: Optional[str] = None, cache_dir: str = ".llm_cache"):
        self.models: Dict[str, LLMModel] = {}
        self.active_models: Dict[str, Any] = {}  # Loaded model instances
        self.performance_tracker = ModelPerformanceTracker()
        self.request_queue = asyncio.Queue()
        self.response_cache: Dict[str, LLMResponse] = {}
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

        # Consensus mechanisms
        self.consensus_threshold = 0.8
        self.max_consensus_models = 5

        # Rate limiting
        self.rate_limits = defaultdict(lambda: {'requests': 0, 'reset_time': time.time() + 60})

        # Load model configurations
        self._load_default_models()
        if config_path:
            self._load_config(config_path)

        # Initialize available models
        self._initialize_models()

        montar_log(f"Multi-LLM Orchestrator inicializado com {len(self.models)} modelos", "SUCCESS")

    def _load_default_models(self):
        """Load default model configurations"""
        default_models = [
            # OpenAI Models
            LLMModel(
                name="gpt-4-turbo",
                provider="openai",
                model_id="gpt-4-1106-preview",
                specializations=[
                    LLMSpecialization.CODE_ANALYSIS,
                    LLMSpecialization.ARCHITECTURE_REVIEW,
                    LLMSpecialization.CODE_REVIEW,
                    LLMSpecialization.DEBUGGING
                ],
                max_tokens=128000,
                cost_per_token=0.00003,
                performance_score=0.95
            ),
            LLMModel(
                name="gpt-3.5-turbo",
                provider="openai",
                model_id="gpt-3.5-turbo-1106",
                specializations=[
                    LLMSpecialization.CODE_GENERATION,
                    LLMSpecialization.REFACTORING,
                    LLMSpecialization.DOCUMENTATION
                ],
                max_tokens=16000,
                cost_per_token=0.000002,
                performance_score=0.85
            ),

            # Anthropic Models
            LLMModel(
                name="claude-3-opus",
                provider="anthropic",
                model_id="claude-3-opus-20240229",
                specializations=[
                    LLMSpecialization.SECURITY_ANALYSIS,
                    LLMSpecialization.VULNERABILITY_DETECTION,
                    LLMSpecialization.CODE_ANALYSIS,
                    LLMSpecialization.ARCHITECTURE_REVIEW
                ],
                max_tokens=200000,
                cost_per_token=0.000075,
                performance_score=0.98
            ),
            LLMModel(
                name="claude-3-sonnet",
                provider="anthropic",
                model_id="claude-3-sonnet-20240229",
                specializations=[
                    LLMSpecialization.CODE_REVIEW,
                    LLMSpecialization.REFACTORING,
                    LLMSpecialization.PERFORMANCE_OPTIMIZATION
                ],
                max_tokens=200000,
                cost_per_token=0.000015,
                performance_score=0.92
            ),

            # Local/Open Source Models via Ollama
            LLMModel(
                name="codellama-13b",
                provider="ollama",
                model_id="codellama:13b-instruct",
                specializations=[
                    LLMSpecialization.CODE_GENERATION,
                    LLMSpecialization.CODE_ANALYSIS,
                    LLMSpecialization.DEBUGGING
                ],
                max_tokens=4096,
                cost_per_token=0.0,  # Local model
                performance_score=0.80
            ),
            LLMModel(
                name="starcoder-7b",
                provider="ollama",
                model_id="starcoder:7b",
                specializations=[
                    LLMSpecialization.CODE_GENERATION,
                    LLMSpecialization.REFACTORING
                ],
                max_tokens=8192,
                cost_per_token=0.0,
                performance_score=0.75
            ),
            LLMModel(
                name="wizardcoder-13b",
                provider="ollama",
                model_id="wizardcoder:13b-python",
                specializations=[
                    LLMSpecialization.CODE_GENERATION,
                    LLMSpecialization.DEBUGGING,
                    LLMSpecialization.CODE_ANALYSIS
                ],
                max_tokens=4096,
                cost_per_token=0.0,
                performance_score=0.78
            ),
            LLMModel(
                name="llama2-13b",
                provider="ollama",
                model_id="llama2:13b-chat",
                specializations=[
                    LLMSpecialization.DOCUMENTATION,
                    LLMSpecialization.CODE_REVIEW
                ],
                max_tokens=4096,
                cost_per_token=0.0,
                performance_score=0.70
            ),

            # HuggingFace Models (for specific tasks)
            LLMModel(
                name="codebert-base",
                provider="huggingface",
                model_id="microsoft/codebert-base",
                specializations=[
                    LLMSpecialization.VULNERABILITY_DETECTION,
                    LLMSpecialization.CODE_ANALYSIS
                ],
                max_tokens=512,
                cost_per_token=0.0,
                performance_score=0.72
            )
        ]

        for model in default_models:
            self.models[model.name] = model

    def _load_config(self, config_path: str):
        """Load additional model configurations from file"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)

            for model_config in config.get('models', []):
                model = LLMModel(**model_config)
                self.models[model.name] = model

            montar_log(f"Configurações carregadas de {config_path}", "INFO")
        except Exception as e:
            montar_log(f"Erro ao carregar configurações: {e}", "WARNING")

    def _initialize_models(self):
        """Initialize available model instances"""
        initialized_count = 0

        for model_name, model in self.models.items():
            try:
                if model.provider == "openai" and OPENAI_AVAILABLE:
                    if model.api_key or "OPENAI_API_KEY" in os.environ:
                        client = openai.OpenAI(api_key=model.api_key)
                        self.active_models[model_name] = {
                            'client': client,
                            'type': 'openai'
                        }
                        initialized_count += 1

                elif model.provider == "anthropic" and ANTHROPIC_AVAILABLE:
                    if model.api_key or "ANTHROPIC_API_KEY" in os.environ:
                        client = anthropic.Anthropic(api_key=model.api_key)
                        self.active_models[model_name] = {
                            'client': client,
                            'type': 'anthropic'
                        }
                        initialized_count += 1

                elif model.provider == "ollama" and OLLAMA_AVAILABLE:
                    # Test if Ollama is running and model is available
                    if self._test_ollama_model(model.model_id):
                        self.active_models[model_name] = {
                            'client': ollama,
                            'type': 'ollama'
                        }
                        initialized_count += 1

                elif model.provider == "huggingface" and TRANSFORMERS_AVAILABLE:
                    # Load HuggingFace model
                    tokenizer = AutoTokenizer.from_pretrained(model.model_id)
                    model_instance = AutoModelForCausalLM.from_pretrained(model.model_id)
                    self.active_models[model_name] = {
                        'tokenizer': tokenizer,
                        'model': model_instance,
                        'type': 'huggingface'
                    }
                    initialized_count += 1

                elif model.provider == "llamacpp" and LLAMACPP_AVAILABLE:
                    if model.local_path and Path(model.local_path).exists():
                        llm = Llama(model_path=model.local_path)
                        self.active_models[model_name] = {
                            'client': llm,
                            'type': 'llamacpp'
                        }
                        initialized_count += 1

            except Exception as e:
                montar_log(f"Falha ao inicializar modelo {model_name}: {e}", "WARNING")
                model.availability = False

        montar_log(f"{initialized_count} modelos inicializados com sucesso", "INFO")

    def _test_ollama_model(self, model_id: str) -> bool:
        """Test if Ollama model is available"""
        try:
            response = ollama.generate(model=model_id, prompt="test", stream=False)
            return True
        except:
            return False

    def _generate_cache_key(self, request: LLMRequest) -> str:
        """Generate cache key for request"""
        content = f"{request.specialization.value}_{request.prompt}_{request.code_context}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[LLMResponse]:
        """Get response from cache"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                return LLMResponse(**data)
            except:
                pass  # noqa: bare-except — non-critical fallback
        return None

    def _save_to_cache(self, cache_key: str, response: LLMResponse):
        """Save response to cache"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, 'w') as f:
                json.dump(asdict(response), f, default=str)
        except Exception as e:
            montar_log(f"Erro ao salvar cache: {e}", "WARNING")

    def select_best_models(self, specialization: LLMSpecialization,
                          count: int = 1, exclude_models: List[str] = None) -> List[str]:
        """Select best models for a given specialization"""
        exclude_models = exclude_models or []

        # Filter models by specialization and availability
        candidates = [
            (name, model) for name, model in self.models.items()
            if specialization in model.specializations
            and model.availability
            and name in self.active_models
            and name not in exclude_models
        ]

        if not candidates:
            return []

        # Score models based on performance and specialization fit
        scored_models = []
        for name, model in candidates:
            performance_score = self.performance_tracker.get_model_score(name, specialization)

            # Adjust score based on cost and availability
            cost_factor = 1.0 - min(model.cost_per_token * 1000, 0.5)  # Favor cheaper models
            availability_factor = 1.0 if name in self.active_models else 0.0

            final_score = (
                performance_score * 0.6 +
                model.performance_score * 0.3 +
                cost_factor * 0.1
            ) * availability_factor

            scored_models.append((name, final_score))

        # Sort by score and return top models
        scored_models.sort(key=lambda x: x[1], reverse=True)
        return [name for name, score in scored_models[:count]]

    async def process_request(self, request: LLMRequest) -> Union[LLMResponse, List[LLMResponse]]:
        """Process a single LLM request"""

        # Check cache first
        cache_key = self._generate_cache_key(request)
        cached_response = self._get_from_cache(cache_key)
        if cached_response:
            montar_log(f"Cache hit para request {request.id}", "INFO")
            return cached_response

        # Select models for this request
        if request.requires_consensus:
            model_names = self.select_best_models(
                request.specialization,
                count=min(request.min_models, self.max_consensus_models)
            )
        else:
            model_names = self.select_best_models(request.specialization, count=1)

        if not model_names:
            error_response = LLMResponse(
                request_id=request.id,
                model_name="none",
                response="",
                confidence=0.0,
                processing_time=0.0,
                tokens_used=0,
                cost_estimate=0.0,
                metadata={},
                error="No suitable models available"
            )
            return error_response

        # Process with selected models
        responses = []
        tasks = []

        for model_name in model_names:
            task = asyncio.create_task(
                self._execute_model_request(model_name, request)
            )
            tasks.append(task)

        # Wait for all responses
        completed_responses = await asyncio.gather(*tasks, return_exceptions=True)

        for response in completed_responses:
            if isinstance(response, LLMResponse):
                responses.append(response)

                # Record performance
                self.performance_tracker.record_performance(
                    response.model_name,
                    request.specialization,
                    response.processing_time,
                    response.confidence,
                    response.cost_estimate,
                    response.tokens_used,
                    response.error is None
                )

        if not responses:
            error_response = LLMResponse(
                request_id=request.id,
                model_name="none",
                response="",
                confidence=0.0,
                processing_time=0.0,
                tokens_used=0,
                cost_estimate=0.0,
                metadata={},
                error="All models failed to respond"
            )
            return error_response

        # Handle consensus if required
        if request.requires_consensus and len(responses) > 1:
            consensus_response = self._build_consensus_response(responses, request)
            self._save_to_cache(cache_key, consensus_response)
            return consensus_response
        else:
            best_response = max(responses, key=lambda r: r.confidence)
            self._save_to_cache(cache_key, best_response)
            return best_response

    async def _execute_model_request(self, model_name: str, request: LLMRequest) -> LLMResponse:
        """Execute request on specific model"""
        start_time = time.time()
        model_config = self.models[model_name]
        model_instance = self.active_models[model_name]

        try:
            # Build prompt
            system_prompt = self._build_system_prompt(request.specialization)
            full_prompt = f"{system_prompt}\\n\\nCode Context:\\n{request.code_context}\\n\\nTask: {request.prompt}"

            # Execute based on provider
            if model_instance['type'] == 'openai':
                response = await self._execute_openai(model_instance['client'], model_config, full_prompt)
            elif model_instance['type'] == 'anthropic':
                response = await self._execute_anthropic(model_instance['client'], model_config, full_prompt)
            elif model_instance['type'] == 'ollama':
                response = await self._execute_ollama(model_instance['client'], model_config, full_prompt)
            elif model_instance['type'] == 'huggingface':
                response = await self._execute_huggingface(model_instance, model_config, full_prompt)
            elif model_instance['type'] == 'llamacpp':
                response = await self._execute_llamacpp(model_instance['client'], model_config, full_prompt)
            else:
                raise ValueError(f"Unknown provider type: {model_instance['type']}")

            processing_time = time.time() - start_time

            # Calculate confidence based on response characteristics
            confidence = self._calculate_confidence(response, request.specialization)

            # Estimate tokens and cost
            tokens_used = len(full_prompt.split()) + len(response.split())  # Rough estimate
            cost_estimate = tokens_used * model_config.cost_per_token

            return LLMResponse(
                request_id=request.id,
                model_name=model_name,
                response=response,
                confidence=confidence,
                processing_time=processing_time,
                tokens_used=tokens_used,
                cost_estimate=cost_estimate,
                metadata={'model_provider': model_config.provider}
            )

        except Exception as e:
            processing_time = time.time() - start_time
            return LLMResponse(
                request_id=request.id,
                model_name=model_name,
                response="",
                confidence=0.0,
                processing_time=processing_time,
                tokens_used=0,
                cost_estimate=0.0,
                metadata={},
                error=str(e)
            )

    async def _execute_openai(self, client, model_config: LLMModel, prompt: str) -> str:
        """Execute OpenAI model request"""
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model=model_config.model_id,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=min(4000, model_config.max_tokens),
                temperature=0.1
            )
        )
        return response.choices[0].message.content

    async def _execute_anthropic(self, client, model_config: LLMModel, prompt: str) -> str:
        """Execute Anthropic model request"""
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.messages.create(
                model=model_config.model_id,
                max_tokens=min(4000, model_config.max_tokens),
                messages=[{"role": "user", "content": prompt}]
            )
        )
        return response.content[0].text

    async def _execute_ollama(self, client, model_config: LLMModel, prompt: str) -> str:
        """Execute Ollama model request"""
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.generate(
                model=model_config.model_id,
                prompt=prompt,
                stream=False
            )
        )
        return response['response']

    async def _execute_huggingface(self, model_instance: Dict, model_config: LLMModel, prompt: str) -> str:
        """Execute HuggingFace model request"""
        tokenizer = model_instance['tokenizer']
        model = model_instance['model']

        inputs = tokenizer.encode(prompt, return_tensors='pt')

        with torch.no_grad():
            outputs = model.generate(
                inputs,
                max_length=inputs.shape[1] + 512,
                temperature=0.1,
                do_sample=True,
                pad_token_id=tokenizer.eos_token_id
            )

        response = tokenizer.decode(outputs[0][inputs.shape[1]:], skip_special_tokens=True)
        return response

    async def _execute_llamacpp(self, client, model_config: LLMModel, prompt: str) -> str:
        """Execute LlamaCpp model request"""
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client(
                prompt,
                max_tokens=512,
                temperature=0.1,
                stop=["\\n\\n"]
            )
        )
        return response['choices'][0]['text']

    def _build_system_prompt(self, specialization: LLMSpecialization) -> str:
        """Build system prompt based on specialization"""
        prompts = {
            LLMSpecialization.CODE_ANALYSIS: "You are an expert code analyst. Analyze the provided code for structure, patterns, and overall quality.",
            LLMSpecialization.VULNERABILITY_DETECTION: "You are a security expert. Identify potential vulnerabilities and security issues in the code.",
            LLMSpecialization.PERFORMANCE_OPTIMIZATION: "You are a performance optimization expert. Identify bottlenecks and suggest optimizations.",
            LLMSpecialization.CODE_GENERATION: "You are an expert programmer. Generate high-quality, efficient code based on requirements.",
            LLMSpecialization.REFACTORING: "You are a refactoring expert. Suggest improvements to code structure and maintainability.",
            LLMSpecialization.DOCUMENTATION: "You are a technical documentation expert. Create clear, comprehensive documentation.",
            LLMSpecialization.DEBUGGING: "You are a debugging expert. Help identify and fix issues in the code.",
            LLMSpecialization.ARCHITECTURE_REVIEW: "You are a software architect. Review and provide feedback on system architecture.",
            LLMSpecialization.SECURITY_ANALYSIS: "You are a cybersecurity expert. Perform comprehensive security analysis.",
            LLMSpecialization.CODE_REVIEW: "You are a senior developer performing code review. Provide constructive feedback."
        }
        return prompts.get(specialization, "You are a helpful coding assistant.")

    def _calculate_confidence(self, response: str, specialization: LLMSpecialization) -> float:
        """Calculate confidence score for response"""
        # Simple heuristic-based confidence calculation
        score = 0.5  # Base score

        # Length-based scoring
        if len(response) > 100:
            score += 0.1
        if len(response) > 500:
            score += 0.1

        # Content-based scoring
        technical_keywords = ['function', 'class', 'variable', 'algorithm', 'performance', 'security', 'vulnerability', 'optimization']
        keyword_count = sum(1 for keyword in technical_keywords if keyword.lower() in response.lower())
        score += min(keyword_count * 0.05, 0.2)

        # Structure-based scoring
        if '1.' in response or '-' in response:  # Structured response
            score += 0.1

        # Code examples
        if '```' in response or 'def ' in response or 'class ' in response:
            score += 0.15

        return min(1.0, score)

    def _build_consensus_response(self, responses: List[LLMResponse], request: LLMRequest) -> LLMResponse:
        """Build consensus response from multiple model responses"""
        if not responses:
            raise ValueError("No responses to build consensus from")

        # Simple consensus: weighted average based on confidence
        total_weight = sum(r.confidence for r in responses)
        weighted_responses = []

        for response in responses:
            weight = response.confidence / total_weight if total_weight > 0 else 1.0 / len(responses)
            weighted_responses.append((response, weight))

        # For now, use the highest confidence response as base
        best_response = max(responses, key=lambda r: r.confidence)

        # Aggregate metadata
        consensus_metadata = {
            'consensus_models': [r.model_name for r in responses],
            'individual_confidences': [r.confidence for r in responses],
            'consensus_method': 'weighted_confidence'
        }

        # Calculate consensus metrics
        avg_confidence = statistics.mean(r.confidence for r in responses)
        total_cost = sum(r.cost_estimate for r in responses)
        total_tokens = sum(r.tokens_used for r in responses)
        total_time = max(r.processing_time for r in responses)

        return LLMResponse(
            request_id=request.id,
            model_name=f"consensus_{len(responses)}_models",
            response=best_response.response,  # Could be enhanced to merge responses
            confidence=min(avg_confidence * 1.1, 1.0),  # Slight boost for consensus
            processing_time=total_time,
            tokens_used=total_tokens,
            cost_estimate=total_cost,
            metadata=consensus_metadata
        )

    async def batch_process(self, requests: List[LLMRequest]) -> List[LLMResponse]:
        """Process multiple requests in parallel"""
        tasks = [self.process_request(request) for request in requests]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        valid_responses = []
        for response in responses:
            if isinstance(response, LLMResponse):
                valid_responses.append(response)
            elif isinstance(response, Exception):
                montar_log(f"Erro no processamento em lote: {response}", "ERROR")

        return valid_responses

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for all models"""
        summary = {}

        for model_name in self.models:
            model_summary = {}
            for spec in LLMSpecialization:
                score = self.performance_tracker.get_model_score(model_name, spec)
                model_summary[spec.value] = score

            summary[model_name] = {
                'specialization_scores': model_summary,
                'overall_score': statistics.mean(model_summary.values()),
                'available': model_name in self.active_models
            }

        return summary

    def health_check(self) -> Dict[str, Any]:
        """Perform health check on all models"""
        health_status = {
            'timestamp': datetime.now().isoformat(),
            'total_models': len(self.models),
            'active_models': len(self.active_models),
            'models': {}
        }

        for model_name, model in self.models.items():
            health_status['models'][model_name] = {
                'available': model_name in self.active_models,
                'provider': model.provider,
                'specializations': [s.value for s in model.specializations],
                'cost_per_token': model.cost_per_token
            }

        return health_status


# Convenience functions for easy integration
async def analyze_code(code: str, specialization: LLMSpecialization = LLMSpecialization.CODE_ANALYSIS) -> str:
    """Quick code analysis using the best available model"""
    orchestrator = MultiLLMOrchestrator()

    request = LLMRequest(
        id=f"analysis_{int(time.time())}",
        specialization=specialization,
        prompt="Analyze this code and provide detailed insights",
        code_context=code,
        metadata={}
    )

    response = await orchestrator.process_request(request)
    return response.response if isinstance(response, LLMResponse) else ""


async def get_security_analysis(code: str, require_consensus: bool = True) -> str:
    """Get security analysis with optional consensus from multiple models"""
    orchestrator = MultiLLMOrchestrator()

    request = LLMRequest(
        id=f"security_{int(time.time())}",
        specialization=LLMSpecialization.SECURITY_ANALYSIS,
        prompt="Perform comprehensive security analysis and identify vulnerabilities",
        code_context=code,
        metadata={},
        requires_consensus=require_consensus,
        min_models=2 if require_consensus else 1
    )

    response = await orchestrator.process_request(request)
    return response.response if isinstance(response, LLMResponse) else ""


if __name__ == "__main__":
    # Test the orchestrator
    async def test_orchestrator():
        orchestrator = MultiLLMOrchestrator()

        # Health check
        health = orchestrator.health_check()
        print("Health Check:", json.dumps(health, indent=2))

        # Test request
        test_code = '''
def vulnerable_function(user_input):
    command = f"ls {user_input}"
    os.system(command)  # Command injection vulnerability
    return "done"
        '''

        result = await get_security_analysis(test_code)
        print("Security Analysis Result:", result)

    asyncio.run(test_orchestrator())