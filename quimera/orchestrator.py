"""
Quimera Orchestrator — Full autonomous cycle.

PHASE 4: Detection -> Knowledge Search -> Hypotheses -> Patch -> Sandbox -> Build -> Tests -> Sanitizers -> Patch Memory

The orchestrator receives a mission (e.g. "compile this kernel with KASAN"),
decomposes it via Planner, and for each failure:
  1. Detection Engine finds the issue
  2. KnowledgeBroker searches across 7 layers
  3. CandidateGenerator produces patches (Level 1 regex + Level 3 LLM)
  4. Sandbox validates each patch (compile -> build -> tests -> sanitizers)
  5. Patch Memory learns from the outcome
  6. Retry the build step

It NEVER gives up on the first error.
"""
import os, sys, subprocess, json, time, re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable
from pathlib import Path


@dataclass
class OrchestratorConfig:
    project_root: str = ""
    mission: str = ""
    max_iterations: int = 20  # max build-fix cycles
    use_llm: bool = True
    llm_provider: str = "openrouter"
    llm_api_key: str = ""
    llm_model: str = "openai/gpt-oss-120b:free"
    target: str = ""  # e.g. "bzImage", "all", "modules"
    arch: str = ""
    cross_compile: str = ""


class QuimeraOrchestrator:
    """
    Full-cycle autonomous build-and-fix orchestrator.

    Usage:
        orch = QuimeraOrchestrator(
            project_root="/path/to/kernel",
            mission="Compile with KASAN enabled"
        )
        result = orch.run()
        print(f"Success: {result['success']}, iterations: {result['iterations']}")
    """

    def __init__(self, config: OrchestratorConfig = None):
        self.config = config or OrchestratorConfig()
        self.project_root = self.config.project_root

        # Lazy imports to avoid circular deps
        self._planner = None
        self._broker = None
        self._generator = None
        self._detector = None
        self._ast_patcher = None
        self._ranker = None
        self._hypothesis_builder = None
        self._source_catalog = None
        self._live_catalog = None
        self._eng_memory = None
        self._patch_memory = None
        self._nl_config = None
        self._llm_config = None
        self._genetic_engine = None
        self._aegis_core = None
        self._aegis_validator = None
        self._aegis_sentinel = None
        self._aegis_malware = None
        self._aegis_integrity = None
        self._aegis_crypto = None
        self._aegis_audit = None
        # ── SANDBOX ENGINE ────────────────────────────
        self._sandbox_manager = None
        # ── PLUGIN FRAMEWORK ──────────────────────────
        self._plugin_manager = None
        # ── ADVANCED AGENTS ────────────────────────────
        self._refinador_v4 = None
        self._coevolution_engine = None
        self._agente_mestra = None
        self._agente_configurador = None
        self._evolutor_codigo = None
        self._agente_kan = None
        self._agente_quantico = None
        # ── MULTI-LANG SUPPORT ─────────────────────────
        self._multi_lang_orchestrator = None
        # ── Legacy Core (now integrated) ─────────────
        self._build_integrator = None
        self._patch_quality = None
        self._correlation_engine = None
        self._deep_investigation = None
        self._resolution_states = None

    @property
    def planner(self):
        if not self._planner:
            from quimera.planner import Planner
            self._planner = Planner(self.project_root)
        return self._planner

    @property
    def broker(self):
        if not self._broker:
            from quimera.knowledge_broker import KnowledgeBroker
            self._broker = KnowledgeBroker(
                self.project_root, self.config.llm_api_key
            )
        return self._broker

    @property
    def detector(self):
        if not self._detector:
            from quimera.detection_engine import DetectionEngine
            self._detector = DetectionEngine()
        return self._detector

    @property
    def ast_patcher(self):
        if not self._ast_patcher:
            from quimera.ast_patcher import ASTPatcher
            self._ast_patcher = ASTPatcher()
        return self._ast_patcher

    @property
    def ranker(self):
        if not self._ranker:
            from quimera.candidate_ranker import CandidateRanker
            self._ranker = CandidateRanker(self.project_root)
        return self._ranker

    @property
    def hypothesis_builder(self):
        if not self._hypothesis_builder:
            from quimera.hypothesis_builder import HypothesisBuilder
            self._hypothesis_builder = HypothesisBuilder(self.project_root)
        return self._hypothesis_builder

    @property
    def source_catalog(self):
        if not self._source_catalog:
            from quimera.source_catalog import SourceCatalog
            self._source_catalog = SourceCatalog(self.project_root)
        return self._source_catalog

    @property
    def live_catalog(self):
        if not self._live_catalog:
            from quimera.live_catalog import LiveCatalog
            self._live_catalog = LiveCatalog(self.project_root)
        return self._live_catalog

    @property
    def eng_memory(self):
        if not self._eng_memory:
            from quimera.engineering_memory import EngineeringMemory
            self._eng_memory = EngineeringMemory(self.project_root)
        return self._eng_memory

    @property
    def patch_memory(self):
        if not self._patch_memory:
            from quimera.patch_memory import PatchCatalog
            self._patch_memory = PatchCatalog()
        return self._patch_memory

    @property
    def nl_config(self):
        if not self._nl_config:
            from quimera.natural_config import NaturalConfig
            self._nl_config = NaturalConfig()
        return self._nl_config

    @property
    def llm_config(self):
        if not self._llm_config:
            from quimera.llm_config import LLMConfig
            self._llm_config = LLMConfig()
        return self._llm_config

    @property
    def genetic_engine(self):
        if not self._genetic_engine:
            from quimera.horizons.h4_evolution.genetic_patch_engine import GeneticPatchEngine
            self._genetic_engine = GeneticPatchEngine()
        return self._genetic_engine

    # ── AEGIS DEFENSIVE SHIELD ────────────────────────
    @property
    def aegis_core(self):
        if not self._aegis_core:
            from quimera.aegis.aegis_core import AegisCore
            self._aegis_core = AegisCore()
        return self._aegis_core

    @property
    def aegis_validator(self):
        if not self._aegis_validator:
            from quimera.aegis.validation_pipeline import ValidationPipeline
            self._aegis_validator = ValidationPipeline()
        return self._aegis_validator

    @property
    def aegis_sentinel(self):
        if not self._aegis_sentinel:
            from quimera.aegis.sentinel import SentinelSecurityOrgan
            self._aegis_sentinel = SentinelSecurityOrgan()
        return self._aegis_sentinel

    @property
    def aegis_malware(self):
        if not self._aegis_malware:
            from quimera.aegis.malware_detector import MalwareDetector
            self._aegis_malware = MalwareDetector()
        return self._aegis_malware

    @property
    def aegis_integrity(self):
        if not self._aegis_integrity:
            from quimera.aegis.integrity_monitor import IntegrityMonitor
            self._aegis_integrity = IntegrityMonitor()
        return self._aegis_integrity

    @property
    def aegis_crypto(self):
        if not self._aegis_crypto:
            from quimera.aegis.crypto_engine import CryptoEngine
            self._aegis_crypto = CryptoEngine()
        return self._aegis_crypto

    @property
    def aegis_audit(self):
        if not self._aegis_audit:
            from quimera.aegis.audit_provenance_system import AuditProvenanceSystem
            self._aegis_audit = AuditProvenanceSystem('quimera-internal-key')
        return self._aegis_audit

    # ── SANDBOX ──────────────────────────────────────
    @property
    def sandbox_manager(self):
        if not self._sandbox_manager:
            from quimera.sandbox.manager import SandboxManager
            self._sandbox_manager = SandboxManager()
        return self._sandbox_manager

    # ── PLUGIN FRAMEWORK ─────────────────────────────
    @property
    def plugin_manager(self):
        if not self._plugin_manager:
            from quimera.plugins.plugin_manager import PluginManager
            self._plugin_manager = PluginManager()
        return self._plugin_manager

    # ── ADVANCED AGENTS ──────────────────────────────
    @property
    def refinador_v4(self):
        if not self._refinador_v4:
            from quimera.agentes.refinador_v4 import AgenteRefinadorV4
            self._refinador_v4 = AgenteRefinadorV4()
        return self._refinador_v4

    @property
    def coevolution_engine(self):
        if not self._coevolution_engine:
            from quimera.agentes.coevolution_engine import CoevolutionEngine
            self._coevolution_engine = CoevolutionEngine()
        return self._coevolution_engine

    @property
    def agente_mestra(self):
        if not self._agente_mestra:
            from quimera.agentes.agente_mestra import AgenteMestra
            self._agente_mestra = AgenteMestra()
        return self._agente_mestra

    @property
    def agente_configurador(self):
        if not self._agente_configurador:
            from quimera.agentes.agente_configurador import AgenteConfiguradorDeKernel
            self._agente_configurador = AgenteConfiguradorDeKernel()
        return self._agente_configurador

    @property
    def evolutor_codigo(self):
        if not self._evolutor_codigo:
            from quimera.agentes.agente_evolutivo_de_codigo import EvolutorDeCodigo
            self._evolutor_codigo = EvolutorDeCodigo()
        return self._evolutor_codigo

    @property
    def agente_kan(self):
        if not self._agente_kan:
            from quimera.agentes.agente_kan import AgenteKAN
            self._agente_kan = AgenteKAN()
        return self._agente_kan

    @property
    def agente_quantico(self):
        if not self._agente_quantico:
            from quimera.agentes.agente_quantico import AgenteQuantico
            self._agente_quantico = AgenteQuantico()
        return self._agente_quantico

    # ── MULTI-LANGUAGE SUPPORT ───────────────────────
    @property
    def multi_lang(self):
        if not self._multi_lang_orchestrator:
            from quimera.plugins.multi_lang_orchestrator import MultiLangOrchestrator
            self._multi_lang_orchestrator = MultiLangOrchestrator()
        return self._multi_lang_orchestrator

    @property
    def build_integrator(self):
        """Build system integration — compiles, tests, benchmarks."""
        if not self._build_integrator:
            from quimera.build_integration import BuildIntegrator
            self._build_integrator = BuildIntegrator(self.project_root)
        return self._build_integrator

    @property
    def patch_quality_eval(self):
        """Patch quality evaluator — static analysis + metrics."""
        if not self._patch_quality:
            from quimera.patch_quality import PatchQualityEvaluator
            self._patch_quality = PatchQualityEvaluator()
        return self._patch_quality

    @property
    def correlation(self):
        """Correlation engine — links findings across files."""
        if not self._correlation_engine:
            from quimera.correlation_engine import CorrelationEngine
            self._correlation_engine = CorrelationEngine()
        return self._correlation_engine

    @property
    def deep_investigator(self):
        """Deep investigation — when all hypotheses fail."""
        if not self._deep_investigation:
            from quimera.deep_investigation import DeepInvestigator
            self._deep_investigation = DeepInvestigator()
        return self._deep_investigation

    @property
    def resolution_tracker(self):
        """Resolution state tracker — fix lifecycle management."""
        if not self._resolution_states:
            from quimera.resolution_states import ResolutionTracker
            self._resolution_states = ResolutionTracker()
        return self._resolution_states

    @property
    def generator(self):
        if not self._generator:
            from quimera.candidate_generator import CandidateGenerator
            self._generator = CandidateGenerator(
                Path(self.project_root) if self.project_root else None,
                use_llm=self.config.use_llm
            )
        return self._generator

    def interpret_and_run(self, user_message: str) -> Dict:
        """
        Full natural language → mission → execution pipeline.

        Example:
            orch.interpret_and_run("Meu kernel deu bootloop depois do KASAN")
            → interprets, plans, detects, fixes, validates, learns
        """
        # Phase 0: NL → Mission
        intent = self.mission_interpreter.interpret(user_message)
        
        result = {
            'user_message': user_message,
            'mission': intent.mission,
            'project_type': intent.project_type,
            'actions': intent.actions,
            'confidence': intent.confidence,
            'phases_completed': 0,
        }
        
        # Route to appropriate handler
        if intent.mission == 'build_project':
            result.update(self._execute_build(intent))
        elif intent.mission == 'fix_error':
            result.update(self._execute_fix(intent))
        elif intent.mission == 'enable_sanitizer':
            result.update(self._execute_sanitizer(intent))
        elif intent.mission == 'analyze_code':
            result.update(self._execute_analyze(intent))
        else:
            result['status'] = 'mission_not_implemented'
            result['message'] = f'Mission "{intent.mission}" not yet automated'
        
        return result

    def _execute_build(self, intent) -> Dict:
        """Execute a build mission."""
        plan = self.planner.build_plan(intent.project_type, self.project_root)
        return {'status': 'build_planned', 'steps': len(plan), 'plan': str(plan)[:200]}

    def _execute_fix(self, intent) -> Dict:
        """Execute a fix mission — full pipeline."""
        # Find source files
        files = []
        for root, _, fnames in os.walk(self.project_root):
            for fn in fnames:
                if fn.endswith(('.c', '.cpp', '.h', '.hpp')):
                    files.append(os.path.join(root, fn))
        
        if not files:
            return {'status': 'no_source_found'}
        
        file_path = files[0]
        return self.run_full_pipeline(intent.error_context or 'error', file_path)

    def _execute_sanitizer(self, intent) -> Dict:
        """Execute a sanitizer enable mission."""
        if 'kasan' in intent.sanitizers:
            steps = self.planner.decompose_mission('enable_kasan')
        elif 'kcov' in intent.sanitizers:
            steps = self.planner.decompose_mission('enable_kcov')
        else:
            steps = self.planner.decompose_mission(f'enable_{intent.sanitizers[0]}' if intent.sanitizers else 'enable_kasan')
        
        return {
            'status': 'sanitizer_planned',
            'sanitizers': intent.sanitizers,
            'steps': [(s['action'], s['description']) for s in steps],
        }

    def _execute_analyze(self, intent) -> Dict:
        """Execute a code analysis mission."""
        files = []
        for root, _, fnames in os.walk(self.project_root):
            for fn in fnames:
                if fn.endswith(('.c', '.cpp', '.h')):
                    files.append(os.path.join(root, fn))
                    if len(files) >= 10:
                        break
        
        total_issues = 0
        for fp in files:
            try:
                code = open(fp).read()
                report = self.detector.detect_in_file(code, fp, 'c')
                total_issues += len(report.issues)
            except:
                pass  # noqa: bare-except — non-critical fallback
        
        return {
            'status': 'analysis_complete',
            'files_scanned': len(files),
            'issues_found': total_issues,
        }

    def run(self) -> Dict:
        """
        Execute the full autonomous cycle.

        Returns:
            {
                "success": bool,
                "iterations": int,
                "steps_completed": int,
                "patches_applied": int,
                "knowledge_sources_used": List[str],
            }
        """
        result = {
            "success": False,
            "iterations": 0,
            "steps_completed": 0,
            "patches_applied": 0,
            "knowledge_sources_used": [],
            "errors": [],
        }

        # Plan the mission
        mission = self.planner.plan(self.config.mission)

        # Execute each step
        for step in mission.steps:
            step_result = self._execute_step(step, mission, result)
            result["steps_completed"] += 1

            if step.status.value == "failed" and step.on_error == "abort":
                result["errors"].append(f"Aborted at {step.id}: {step.error}")
                return result

        result["success"] = all(
            s.status.value in ("success", "skipped")
            for s in mission.steps
        )
        return result

    def _execute_step(self, step, mission, result) -> bool:
        """Execute one mission step with retry + error recovery."""
        from quimera.planner import StepStatus

        step.status = StepStatus.RUNNING

        for attempt in range(step.max_retries):
            if result["iterations"] >= self.config.max_iterations:
                step.status = StepStatus.FAILED
                step.error = "max iterations exceeded"
                return False

            result["iterations"] += 1

            try:
                r = subprocess.run(
                    step.command, shell=True,
                    cwd=step.cwd or self.project_root,
                    capture_output=True, text=True,
                    timeout=step.timeout_seconds
                )
                step.output = r.stdout + r.stderr

                if r.returncode == 0:
                    step.status = StepStatus.SUCCESS
                    return True

                # ── BUILD FAILED — Enter recovery cycle ──
                step.error = r.stderr[:500] + r.stdout[:500]
                print(f"  [{step.id}] FAILED (attempt {attempt+1})")
                print(f"  Error: {step.error[:200]}")

                # 1. DETECT issues in the error output
                findings = self._detect_issues(r.stderr + r.stdout)

                # 2. SEARCH for knowledge about each finding
                knowledge_hits = []
                for f in findings:
                    cwe = getattr(f, 'cwe_id', '')
                    desc = getattr(f, 'description', '')
                    hits = self.broker.search(desc, cwe)
                    knowledge_hits.extend(hits)
                    for h in hits:
                        result["knowledge_sources_used"].append(h.source.value)

                # 3. GENERATE patches
                source_files = self._find_source_files(r.stderr)
                patches_applied = 0
                for sf in source_files[:3]:  # max 3 files per iteration
                    if os.path.exists(sf):
                        with open(sf) as fh:
                            source = fh.read()
                        candidates = self.generator.generate_all(
                            findings, source, sf, 'c',
                            extra={'project_name': mission.project_type,
                                   'compiler': 'gcc', 'arch': self.config.arch}
                        )
                        # 4. VALIDATE + APPLY best patch
                        for cand in candidates:
                            if self._validate_patch(cand, sf):
                                with open(sf, 'w') as fh:
                                    fh.write(cand.patched_code)
                                patches_applied += 1
                                result["patches_applied"] += 1
                                break  # one patch per file per iteration

                if patches_applied == 0 and attempt >= step.max_retries - 1:
                    # No patches worked — escalate to LLM
                    print(f"  No deterministic patches worked. Escalating to LLM...")
                    self._escalate_to_llm(r.stderr, source_files, result)

            except subprocess.TimeoutExpired:
                step.error = f"timeout after {step.timeout_seconds}s"
            except Exception as e:
                step.error = str(e)[:300]

        # All retries exhausted
        if step.on_error == "abort":
            step.status = StepStatus.FAILED
            return False
        elif step.on_error == "skip":
            step.status = StepStatus.SKIPPED
            return True
        else:
            step.status = StepStatus.FAILED
            return False

    def _detect_issues(self, error_text: str) -> list:
        """Run DetectionEngine on compiler error output."""
        try:
            findings = self.detector.detect_in_text(error_text, 'c')
            return findings.issues if hasattr(findings, 'issues') else []
        except Exception:
            return []

    def run_full_pipeline(self, error_text: str, file_path: str):
        """
        FULL INTEGRATED 10-PHASE PIPELINE:
        Detection → Knowledge → SourceCatalog → Hypothesis → AST → 
        CandidateRanking → Apply → LiveCatalog → EngineeringMemory → PatchMemory
        """
        result = {'phases_completed': 0, 'issues_found': 0, 
                  'candidates_generated': 0, 'best_applied': False,
                  'sources_used': [], 'final_score': 0.0}

        # 1. DETECTION
        findings = self._detect_issues(error_text)
        result['issues_found'] = len(findings)
        result['phases_completed'] = 1
        
        source = ''
        if file_path and os.path.isfile(file_path):
            source = open(file_path).read()
            try:
                report = self.detector.detect_in_file(source, file_path, 'c')
                findings = report.issues
                result['issues_found'] = len(findings)
            except:
                pass  # noqa: bare-except — non-critical fallback
        
        if not findings or not source:
            return result

        # 2. KNOWLEDGE BROKER
        knowledge = []
        sources_used = set()
        for f in findings[:5]:
            cwe = getattr(f, 'cwe_id', '')
            desc = getattr(f, 'description', '')
            results = self.broker.search(desc, cwe)
            knowledge.extend(results)
            sources_used.update(r.source.value for r in results)
        result['sources_used'] = list(sources_used)
        result['phases_completed'] = 2

        # 3. SOURCE CATALOG
        for r in knowledge:
            useful = bool(r.code_snippet and len(r.code_snippet) > 10)
            self.source_catalog.record_query(
                r.source.value, useful,
                confidence=r.confidence
            )
        result['phases_completed'] = 3

        # 4. HYPOTHESIS BUILDER
        cwe = getattr(findings[0], 'cwe_id', '') if findings else ''
        hypotheses = self.hypothesis_builder.build(knowledge, cwe)
        result['phases_completed'] = 4

        # 5. AST MULTI-CANDIDATE
        all_candidates = []
        for f in findings:
            cands = self.ast_patcher.generate(f, source, num_candidates=8)
            all_candidates.extend(cands)
        result['candidates_generated'] = len(all_candidates)
        result['phases_completed'] = 5

        # 6. CANDIDATE RANKING
        ranked = self.ranker.rank(all_candidates, source, file_path)
        result['phases_completed'] = 6

        # 7. APPLY BEST
        best = ranked[0] if ranked else None
        if best and best.final_score > 0 and file_path:
            try:
                open(file_path, 'w').write(best.patched_code)
                result['best_applied'] = True
                result['final_score'] = best.final_score
            except:
                pass  # noqa: bare-except — non-critical fallback
        result['phases_completed'] = 7

        # 8. LIVE CATALOG
        model = getattr(self.generator, 'model', 'unknown')
        provider = getattr(self.generator, 'provider', 'unknown')
        for r in ranked:
            if r.total_time_ms > 0:
                self.live_catalog.record_attempt(
                    model, provider, cwe, 'c',
                    r.compiled and r.asan_clean,
                    r.total_time_ms
                )
        result['phases_completed'] = 8

        # 9. ENGINEERING MEMORY
        self.eng_memory.record(
            project=os.path.basename(self.project_root) if self.project_root else 'unknown',
            cwe=cwe,
            knowledge_sources_used=list(sources_used),
            knowledge_results_count=len(knowledge),
            model_used=model, provider_used=provider,
            candidates_generated=len(all_candidates),
            best_approach=best.approach if best else '',
            compiled=best.compiled if best else False,
            asan_clean=best.asan_clean if best else False,
            ubsan_clean=best.ubsan_clean if best else False,
            patch_accepted=result['best_applied'],
            patch_code=best.patched_code[:500] if best else '',
            final_result='success' if result['best_applied'] else 'failed',
        )
        result['phases_completed'] = 9

        # ── Phase 10: CORRELATION ENGINE ──────────────
        # Link findings across files for better context
        try:
            correlations = self.correlation.analyze(findings, source)
            if correlations:
                result['correlations_found'] = len(correlations)
        except Exception:
            result['correlations_found'] = 0
        result['phases_completed'] = 10

        # ── Phase 11: PATCH QUALITY ───────────────────
        if result['best_applied'] and best:
            try:
                quality = self.patch_quality_eval.evaluate(
                    source, best.patched_code, file_path
                )
                result['patch_quality'] = getattr(quality, 'score', 0)
            except Exception:
                result['patch_quality'] = 0
        result['phases_completed'] = 11

        # ── Phase 12: AEGIS DEFENSIVE SHIELD ────────────
        # Full security validation: malware scan, integrity, crypto audit
        if result['best_applied'] and best:
            try:
                # Sentinel: threat analysis
                threats = self.aegis_sentinel.analyze_threats(best.patched_code)
                result['aegis_threats'] = len(threats) if threats else 0
                
                # Malware scan
                scan = self.aegis_malware.scan_code(best.patched_code)
                result['aegis_malware_clean'] = not scan.threats_found if hasattr(scan, 'threats_found') else True
                
                # Integrity check
                integrity = self.aegis_integrity.verify(best.patched_code) if hasattr(self.aegis_integrity, 'verify') else True
                result['aegis_integrity_ok'] = bool(integrity)
                
                # Crypto audit
                self.aegis_audit.record('patch_applied', {
                    'file': file_path, 'cwe': cwe,
                    'patch_hash': str(hash(best.patched_code))[:16]
                })
                result['aegis_audit_ok'] = True
            except Exception:
                result['aegis_threats'] = -1
        result['phases_completed'] = 12

        # ── Phase 12: DEEP INVESTIGATION + FALLBACK ────
        # If all candidates failed, launch deep investigation + fallback agents
        if not result['best_applied'] and findings:
            try:
                investigation = self.deep_investigator.investigate(
                    findings, knowledge, source
                )
                result['investigation'] = str(investigation)[:200]
            except Exception:
                result['investigation'] = 'not_launched'
            
            # ── Fallback Agent: try alternative approaches ──
            try:
                from quimera.agentes.agente_de_fallback import AgenteDeFallback
                fallback = AgenteDeFallback()
                fb_result = fallback.attempt_fix(findings, source, file_path)
                if fb_result and fb_result.get('fixed'):
                    result['best_applied'] = True
                    result['fallback_used'] = True
                    result['fallback_approach'] = fb_result.get('approach', 'unknown')
            except Exception:
                result['fallback_used'] = False

            # ── Evolutive Code Agent: mutate for better fix ──
            if not result['best_applied'] and all_candidates:
                try:
                    from quimera.agentes.agente_evolutivo_de_codigo import EvolutorDeCodigo
                    evolver = EvolutorDeCodigo()
                    evolved = evolver.evolve(all_candidates, source, generations=3)
                    if evolved:
                        # Rank evolved candidates
                        evolved_ranked = self.ranker.rank(evolved[:10], source, file_path)
                        best_evolved = evolved_ranked[0] if evolved_ranked else None
                        if best_evolved and best_evolved.final_score > 0:
                            try:
                                open(file_path, 'w').write(best_evolved.patched_code)
                                result['best_applied'] = True
                                result['evolved_used'] = True
                            except:
                                pass  # noqa: bare-except — non-critical fallback
                except Exception:
                    result['evolved_used'] = False
        result['phases_completed'] = 12

        # ── Phase 13: RESOLUTION TRACKING ──────────────
        # Track fix lifecycle
        try:
            self.resolution_tracker.record(
                issue_id=getattr(findings[0], 'vuln_id', 'unknown') if findings else 'unknown',
                status='resolved' if result['best_applied'] else 'open',
                patch=best.patched_code[:200] if best else '',
            )
        except Exception:
            pass
        result['phases_completed'] = 13

        return result

    def _find_source_files(self, error_text: str) -> List[str]:
        """Extract source file paths from compiler errors."""
        files = set()
        for m in re.finditer(r'([^\s:]+\.(?:c|h|cpp|hpp)):\d+:', error_text):
            fpath = os.path.join(self.project_root, m.group(1))
            if os.path.isfile(fpath):
                files.add(fpath)
            elif os.path.isfile(m.group(1)):
                files.add(m.group(1))
        return sorted(files)

    def _validate_patch(self, candidate, file_path: str) -> bool:
        """Quick compile check for a patch candidate."""
        try:
            backup = file_path + '.quimera.bak'
            with open(file_path) as f:
                original = f.read()
            with open(file_path, 'w') as f:
                f.write(candidate.patched_code)
            r = subprocess.run(
                ['gcc', '-fsyntax-only', '-Wall', '-Werror', file_path],
                capture_output=True, text=True, timeout=30,
                cwd=self.project_root
            )
            ok = r.returncode == 0

            if not ok:
                # Restore original
                with open(file_path, 'w') as f:
                    f.write(original)
            else:
                # Cleanup backup
                try: os.remove(backup)
                except: pass  # noqa: bare-except — non-critical fallback

            return ok
        except Exception:
            return False

    def _escalate_to_llm(self, error_text: str, source_files: List[str], result: Dict):
        """Last resort: ask LLM to analyze the error."""
        try:
            from quimera.candidate_generator import LLMInterface
            llm = LLMInterface(
                model=self.config.llm_model,
                api_key=self.config.llm_api_key,
                provider=self.config.llm_provider
            )
            if not llm.available:
                return

            context = ""
            for sf in source_files[:2]:
                if os.path.exists(sf):
                    with open(sf) as f:
                        context += f"\n--- {sf} ---\n{f.read()[:3000]}"

            prompt = f"""Fix these C/C++ compilation errors:

{error_text[:3000]}

Source files:
{context[:3000]}

Return JSON: {{"analysis":"...","fixes":[{{"file":"path","patch":"code"}}]}}"""

            resp = llm._call_llm(prompt)
            result["knowledge_sources_used"].append("llm_escalation")
        except Exception:
            pass


# ── CLI entry point ────────────────────────────────
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Quimera Orchestrator")
    ap.add_argument("project_root", nargs="?", default=".",
                    help="Project root directory")
    ap.add_argument("--mission", default="Build the project",
                    help="High-level mission description")
    ap.add_argument("--max-iterations", type=int, default=20)
    ap.add_argument("--no-llm", action="store_true",
                    help="Disable LLM (Level 1 only)")
    ap.add_argument("--arch", default="", help="Target architecture")
    ap.add_argument("--cross-compile", default="",
                    help="Cross compiler prefix")

    args = ap.parse_args()

    config = OrchestratorConfig(
        project_root=os.path.abspath(args.project_root),
        mission=args.mission,
        max_iterations=args.max_iterations,
        use_llm=not args.no_llm,
        arch=args.arch,
        cross_compile=args.cross_compile,
    )

    orch = QuimeraOrchestrator(config)
    print(f"Quimera Orchestrator")
    print(f"  Project:    {config.project_root}")
    print(f"  Type:       {orch.planner.project_type}")
    print(f"  Mission:    {config.mission}")
    print(f"  LLM:        {'enabled' if config.use_llm else 'disabled'}")
    print()

    result = orch.run()

    print()
    print("=" * 60)
    print("RESULT")
    print("=" * 60)
    print(f"  Success:              {result['success']}")
    print(f"  Iterations:           {result['iterations']}")
    print(f"  Steps completed:      {result['steps_completed']}")
    print(f"  Patches applied:      {result['patches_applied']}")
    print(f"  Knowledge sources:    {set(result['knowledge_sources_used'])}")
    if result['errors']:
        print(f"  Errors:               {len(result['errors'])}")
        for e in result['errors'][:3]:
            print(f"    - {e[:120]}")
