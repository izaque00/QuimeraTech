# KERNEL.md — Quimera Core (FROZEN)

## Arquitetura Atual

```
Missao → Planner → Orchestrator
                       ↓
                  Build Step
                       ↓
                  Erro? → Detection → KnowledgeBroker (7 layers)
                                              ↓
                                         CandidateGenerator (3 levels)
                                              ↓
                                         Sandbox (compile → test → asan → ubsan → fuzz)
                                              ↓
                                         Patch Memory (aprender)
                                              ↓
                                         Retry
```

## Modulos Congelados (nao modificar)

- **H1 Detection**: `quimera/detection_engine.py`
- **H2 Evidence**: `quimera/evidence_score.py`
- **H3 Correlation**: `quimera/correlation_engine.py`
- **H4 Resolution**: `quimera/resolution_states.py`
- **H5 Investigation**: `quimera/deep_investigation.py`
- **H6 Synthesis**: `quimera/patch_synthesis.py`
- **Pipeline**: `quimera/pipeline.py`
- **Patch Memory**: `quimera/patch_memory.py`
- **Patch Ranker**: `quimera/patch_ranker.py`
- **Patch Quality**: `quimera/patch_quality.py`
- **Build Integration**: `quimera/build_integration.py`
- **Knowledge Acquisition**: `quimera/knowledge_acquisition.py`
- **Candidate Generator**: `quimera/candidate_generator.py`
- **Validators (10)**: `quimera/validators/`
- **Sandbox (7)**: `quimera/sandbox/`

## Plugins (extensoes sobre o Kernel)

- **KnowledgeBroker**: `quimera/knowledge_broker.py` — 7-layer search
- **Planner**: `quimera/planner.py` — mission decomposition (6 project types)
- **Orchestrator**: `quimera/orchestrator.py` — full autonomous cycle

## Proxima Fase: Fortalecer o CandidateGenerator

O gargalo atual NAO e arquitetura. E o gerador de patches.

Prioridades:
1. AST-based patching (substituir regex gradualmente)
2. Multi-candidate generation (5-20 por erro)
3. Busca por commits/PRs/issues alem de docs/CVEs
4. Validacao diferencial (antes/depois do patch)
5. Execucao em projetos grandes (horas/dias, retomar em falhas)

## Regra de Ouro

Toda funcionalidade nova entra como PLUGIN.
O Kernel so muda para corrigir bugs criticos.
LLM e sempre a ULTIMA opcao, nunca a primeira.
Quimera decide; LLM apenas sugere.
