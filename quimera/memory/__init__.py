"""
Quimera Mark X — Long-Term Memory System (Horizonte 2)

Privacy-preserving, cross-kernel, retrieval-augmented memory.

Modules:
    vector_store    — Embedding storage (in-memory, FAISS, Chroma)
    memory_engine   — RAR pipeline with LRU cache
    cross_kernel    — Transfer learning between kernel architectures
    federated       — Privacy-preserving federated memory
    integration     — Memory-to-Repair pipeline connector
    dashboard       — Real-time metrics and monitoring

Usage:
    from quimera.memory import MemoryPipeline, MemoryEngine, VectorStore
    
    store = VectorStore(InMemoryBackend(dim=384))
    engine = MemoryEngine(store, persistence_path="memory.json")
    pipeline = MemoryPipeline(engine)
    
    # Pre-repair
    candidates = await pipeline.retrieve_solutions(ctx)
    
    # Post-repair
    await pipeline.record_outcome(mission_id, ctx, solution, success=True)
    
    # Stats
    from quimera.memory import MemoryDashboard
    dashboard = MemoryDashboard(pipeline)
    report = await dashboard.get_full_report()
"""

from .vector_store import VectorStore, InMemoryBackend, VectorBackend
from .memory_engine import MemoryEngine, SolutionCandidate, LRUCache
from .cross_kernel import CrossKernelTransfer, KernelProfile
from .federated import FederatedMemory, Sensitivity, ShareConsent, DifferentialPrivacy
from .integration import MemoryPipeline, MemoryContext, MemoryEnhancedResult
from .dashboard import MemoryDashboard

__version__ = "2.2.1"
