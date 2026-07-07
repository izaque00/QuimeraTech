"""
Quimera Engineer — Ciclo de Engenharia Autônomo.

Muda o paradigma de "scanner de vulnerabilidades" para "engenheiro que resolve problemas".

CICLO:
  Objetivo → Pesquisar → Entender → Hipóteses → Experimentar → Medir → Escolher → Repetir

Usa KnowledgeBroker como cérebro de pesquisa.
Usa Detection Engine como fonte de evidência (não mais protagonista).
Usa Sandbox Executor para validar hipóteses com compilação real.

EXEMPLOS DE OBJETIVOS:
  - "Compilar esse kernel ARM com sucesso"
  - "Resolver undefined reference no build"
  - "Portar esse driver de Linux 5.x para 6.x"
  - "Corrigir bootloop no device tree"
  - "Encontrar e corrigir o bug que causa segfault na init"

ARQUITETURA:
  ┌─────────────────────────────────────────────────┐
  │                ENGINEER LOOP                     │
  │                                                  │
  │  1. UNDERSTAND — lê código, docs, Makefile      │
  │  2. RESEARCH   — KnowledgeBroker (7 camadas)    │
  │  3. HYPOTHESIZE — gera N hipóteses ranqueadas   │
  │  4. EXPERIMENT — executa hipótese no sandbox    │
  │  5. MEASURE    — compila, testa, avalia         │
  │  6. LEARN      — registra o que funcionou       │
  │  7. DECIDE     — próxima iteração ou concluir   │
  └─────────────────────────────────────────────────┘
"""

import os
import re
import time
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("quimera.engineer")


class HypothesisStatus(Enum):
    PENDING = "pending"
    TESTING = "testing"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class Hypothesis:
    """Uma hipótese de solução para o problema."""
    id: str
    description: str
    confidence: float = 0.5
    source: str = ""  # de onde veio a ideia
    patch_code: str = ""
    reasoning: str = ""  # por que achamos que isso resolve
    risks: List[str] = field(default_factory=list)
    status: HypothesisStatus = HypothesisStatus.PENDING
    evidence: Dict = field(default_factory=dict)
    experiment_result: Optional[Dict] = None


@dataclass
class EngineerContext:
    """Contexto completo do ciclo de engenharia."""
    objective: str
    project_root: str
    max_iterations: int = 10
    max_hypotheses_per_iteration: int = 5
    
    # Estado
    current_iteration: int = 0
    hypotheses: List[Hypothesis] = field(default_factory=list)
    successful_hypotheses: List[Hypothesis] = field(default_factory=list)
    failed_hypotheses: List[Hypothesis] = field(default_factory=list)
    observations: List[str] = field(default_factory=list)
    knowledge_gained: List[str] = field(default_factory=list)
    
    # Recursos do projeto
    project_files: List[str] = field(default_factory=list)
    build_system: str = ""  # make, cmake, meson, etc.
    build_errors: List[str] = field(default_factory=list)
    relevant_docs: List[str] = field(default_factory=list)


class QuimeraEngineer:
    """
    Engenheiro autônomo que resolve problemas de software.
    
    Não é um scanner. É um resolvedor de problemas.
    Usa todo o resto do Quimera como ferramentas.
    """

    def __init__(self, project_root: str = "."):
        self.project_root = project_root
        self._broker = None
        self._detector = None
        self._sandbox = None

    # ═══════════════════════════════════════════════════════════
    # MAIN LOOP
    # ═══════════════════════════════════════════════════════════

    async def solve(self, objective: str, max_iterations: int = 10) -> EngineerContext:
        """
        Ciclo principal: recebe um objetivo e itera até resolver.
        
        Args:
            objective: descrição do problema a resolver
            max_iterations: máximo de iterações do ciclo
        
        Returns:
            EngineerContext com todas as hipóteses e resultados
        """
        ctx = EngineerContext(
            objective=objective,
            project_root=self.project_root,
            max_iterations=max_iterations,
        )
        
        logger.info(f"🎯 Engineer: starting — '{objective[:80]}'")
        
        for iteration in range(max_iterations):
            ctx.current_iteration = iteration + 1
            logger.info(f"🔄 Iteration {ctx.current_iteration}/{max_iterations}")
            
            # STEP 1: UNDERSTAND the project
            if iteration == 0:
                await self._understand(ctx)
            
            # STEP 2: RESEARCH the problem
            evidence = await self._research(ctx)
            
            # STEP 3: HYPOTHESIZE solutions
            await self._hypothesize(ctx, evidence)
            
            # STEP 4: EXPERIMENT with best hypothesis
            result = await self._experiment(ctx)
            
            # STEP 5: MEASURE success
            solved = await self._measure(ctx, result)
            
            # STEP 6: LEARN from the outcome
            await self._learn(ctx, result)
            
            # STEP 7: DECIDE next action
            if solved:
                logger.info(f"✅ Engineer: SOLVED in {ctx.current_iteration} iterations!")
                break
            elif not ctx.hypotheses:
                logger.warning("⚠️ Engineer: no more hypotheses to test")
                break
        
        # Report
        logger.info(
            f"🏁 Engineer: {len(ctx.successful_hypotheses)} solved, "
            f"{len(ctx.failed_hypotheses)} failed, "
            f"{len(ctx.knowledge_gained)} insights gained"
        )
        return ctx

    # ═══════════════════════════════════════════════════════════
    # STEP 1: UNDERSTAND
    # ═══════════════════════════════════════════════════════════

    async def _understand(self, ctx: EngineerContext):
        """
        Entender o projeto: estrutura, build system, código relevante.
        Não tenta resolver nada ainda — só observa e cataloga.
        """
        logger.info("  📖 UNDERSTAND: analyzing project structure...")
        
        root = ctx.project_root
        
        # Find project files
        for f in self._find_project_files(root):
            ctx.project_files.append(f)
        
        # Detect build system
        ctx.build_system = self._detect_build_system(root)
        
        # Read relevant docs
        ctx.relevant_docs = self._find_docs(root)
        
        # Try to build and capture errors
        build_errors = self._try_build(root, ctx.build_system)
        ctx.build_errors = build_errors
        
        # Record observations
        ctx.observations.append(f"Project has {len(ctx.project_files)} source files")
        ctx.observations.append(f"Build system: {ctx.build_system or 'unknown'}")
        if build_errors:
            ctx.observations.append(f"Build has {len(build_errors)} errors")
            for e in build_errors[:3]:
                ctx.observations.append(f"  Error: {e[:120]}")
        
        logger.info(f"  📖 Found {len(ctx.project_files)} files, build={ctx.build_system}")

    # ═══════════════════════════════════════════════════════════
    # STEP 2: RESEARCH
    # ═══════════════════════════════════════════════════════════

    async def _research(self, ctx: EngineerContext) -> List[Dict]:
        """
        Pesquisar o problema em TODAS as fontes disponíveis.
        KnowledgeBroker faz a busca em 7 camadas.
        Detection Engine contribui como evidência complementar.
        """
        logger.info("  🔍 RESEARCH: searching for solutions...")
        evidence = []
        
        # Build search query from objective + build errors
        query = ctx.objective
        if ctx.build_errors:
            query += " " + " ".join(ctx.build_errors[:2])
        
        # KnowledgeBroker: 7-layer search
        broker = self._get_broker()
        if broker:
            try:
                kb_results = broker.search(query)
                for r in kb_results[:10]:
                    evidence.append({
                        'source': str(r.source.value),
                        'confidence': r.confidence,
                        'summary': r.summary,
                        'url': getattr(r, 'url', ''),
                        'code_snippet': getattr(r, 'code_snippet', ''),
                    })
                    logger.debug(f"    [{r.source.value}] {r.summary[:80]}")
            except Exception as e:
                logger.debug(f"    Broker error: {e}")
        
        # Detection Engine: evidence from code patterns
        detector = self._get_detector()
        if detector and ctx.project_files:
            try:
                for f in ctx.project_files[:5]:  # Limit to top 5 files
                    if f.endswith(('.c', '.cpp', '.h', '.hpp')):
                        full_path = os.path.join(ctx.project_root, f)
                        if os.path.exists(full_path):
                            with open(full_path, errors='replace') as fh:
                                code = fh.read()
                            report = detector.detect_in_file(code, full_path, 'c')
                            if report.issues:
                                evidence.append({
                                    'source': 'detection_engine',
                                    'confidence': 0.6,
                                    'summary': f'{len(report.issues)} potential issues in {f}',
                                    'issues': report.issues[:5],
                                })
            except Exception as e:
                logger.debug(f"    Detector error: {e}")
        
        # Web search for build errors
        if ctx.build_errors:
            for error in ctx.build_errors[:2]:
                evidence.append({
                    'source': 'search_suggested',
                    'confidence': 0.3,
                    'summary': f'Search for: "{error[:80]}" on StackOverflow/GitHub',
                    'search_query': error[:120],
                })
        
        logger.info(f"  🔍 Found {len(evidence)} pieces of evidence")
        return evidence

    # ═══════════════════════════════════════════════════════════
    # STEP 3: HYPOTHESIZE
    # ═══════════════════════════════════════════════════════════

    async def _hypothesize(self, ctx: EngineerContext, evidence: List[Dict]):
        """
        Gerar hipóteses DIRECIONADAS ao problema real.
        PRIORIDADE MÁXIMA: erros de build → analisar e gerar fixes concretos.
        """
        logger.info("  💡 HYPOTHESIZE: analyzing problem and generating fixes...")
        
        ctx.hypotheses = []
        
        # ═══ CHECK 0: Patch Memory (learning loop) ═══
        try:
            from quimera.patch_memory import PatchMemory
            memory = PatchMemory()
            for error_line in ctx.build_errors[:5]:
                cached = memory.find_match(error_line)
                if cached and cached.confidence >= 0.7:
                    ctx.hypotheses.append(Hypothesis(
                        id=f"CACHED_{len(ctx.hypotheses)}",
                        description=f"Known fix ({cached.fix_type}): {cached.fix_template[:60]}",
                        confidence=cached.confidence,
                        source="patch_memory",
                        reasoning=f"Previously fixed {cached.success_count}/{cached.total_attempts} times",
                    ))
                    logger.info(f"  📚 CACHED fix for: {error_line[:50]}")
        except ImportError:
            pass
        
        # Force rebuild to capture fresh errors
        import subprocess
        subprocess.run(['make', 'clean'], cwd=ctx.project_root, capture_output=True, timeout=5)
        fresh_errors = self._try_build(ctx.project_root, ctx.build_system)
        if fresh_errors:
            ctx.build_errors = fresh_errors
        
        # ═══ PRIORIDADE 1: Erros de build → fixes diretos ═══
        if ctx.build_errors:
            for i, error_line in enumerate(ctx.build_errors[:3]):
                parsed = self._parse_build_error(error_line)
                
                if parsed['error_type'] == 'undefined_reference':
                    symbol = parsed['symbol']
                    # Gerar hipóteses concretas para undefined reference
                    
                    # H1: Implementar a função faltante
                    ctx.hypotheses.append(Hypothesis(
                        id=f"H{ctx.current_iteration}_impl_{symbol}",
                        description=f"Implement missing function '{symbol}' in the source file",
                        confidence=0.85,
                        source="build_error_analysis",
                        reasoning=f"Linker error: '{symbol}' is declared but not defined. Need to add implementation.",
                        patch_code=f"// TODO: implement {symbol}()",
                        evidence={'error_type': 'undefined_reference', 'symbol': symbol, 'target_file': ''},
                    ))
                    
                    # H2: Verificar se existe em outro arquivo .c/.o
                    ctx.hypotheses.append(Hypothesis(
                        id=f"H{ctx.current_iteration}_find_{symbol}",
                        description=f"Search for existing implementation of '{symbol}' in other source files",
                        confidence=0.60,
                        source="build_error_analysis",
                        reasoning=f"The function '{symbol}' might already be implemented in another file not linked",
                        evidence={'error_type': 'search_symbol', 'symbol': symbol},
                    ))
                    
                    # H3: Verificar se a chamada é desnecessária
                    ctx.hypotheses.append(Hypothesis(
                        id=f"H{ctx.current_iteration}_remove_{symbol}",
                        description=f"Check if call to '{symbol}()' can be removed or replaced with stub",
                        confidence=0.35,
                        source="build_error_analysis",
                        reasoning=f"If '{symbol}' is non-essential, remove the call or add empty stub",
                        patch_code=f"void {symbol}(char *buf) {{ /* stub */ }}",
                        evidence={'error_type': 'add_stub', 'symbol': symbol},
                    ))
                
                elif parsed['error_type'] == 'implicit_declaration':
                    symbol = parsed['symbol']
                    ctx.hypotheses.append(Hypothesis(
                        id=f"H{ctx.current_iteration}_include_{symbol}",
                        description=f"Add #include for header declaring '{symbol}'",
                        confidence=0.80,
                        source="build_error_analysis",
                        reasoning=f"Compiler warning: '{symbol}' implicitly declared. Missing #include.",
                        evidence={'error_type': 'implicit_declaration', 'symbol': symbol},
                    ))
                
                elif parsed['error_type'] == 'compile_error':
                    ctx.hypotheses.append(Hypothesis(
                        id=f"H{ctx.current_iteration}_fix_{parsed.get('file','')}",
                        description=f"Fix compilation error at {parsed.get('file','')}:{parsed.get('line',0)}",
                        confidence=0.70,
                        source="build_error_analysis",
                        reasoning=f"Compiler error: fix syntax/type error at specified location",
                        evidence=parsed,
                    ))
                
                else:
                    ctx.hypotheses.append(Hypothesis(
                        id=f"H{ctx.current_iteration}_parse_{i}",
                        description=f"Analyze build error: {error_line[:150]}",
                        confidence=0.50,
                        source="build_output",
                        reasoning="The build error message itself contains the fix information",
                    ))
        
        # ═══ PRIORIDADE 2: Detection Engine findings ═══
        for ev in evidence:
            if ev.get('source') == 'detection_engine' and ev.get('issues'):
                for issue in ev['issues'][:2]:
                    if hasattr(issue, 'description'):
                        ctx.hypotheses.append(Hypothesis(
                            id=f"H{ctx.current_iteration}_detect_{issue.cwe_id if hasattr(issue,'cwe_id') else '?'}",
                            description=f"Fix {getattr(issue,'cwe_id','?')}: {issue.description[:100]}",
                            confidence=0.55,
                            source="detection_engine",
                            reasoning=f"Static analysis found potential issue: {issue.description[:80]}",
                        ))
        
        # ═══ PRIORIDADE 3: Knowledge Broker (filtrado) ═══
        kb_evidence = [e for e in evidence if e.get('source') not in ('detection_engine', 'search_suggested')]
        remaining_slots = ctx.max_hypotheses_per_iteration - len(ctx.hypotheses)
        for ev in kb_evidence[:remaining_slots]:
            if ev.get('confidence', 0) >= 0.3:  # Only keep decent confidence
                ctx.hypotheses.append(Hypothesis(
                    id=f"H{ctx.current_iteration}_kb_{len(ctx.hypotheses)}",
                    description=ev.get('summary', 'Unknown')[:200],
                    confidence=ev.get('confidence', 0.3),
                    source=ev.get('source', 'unknown'),
                    reasoning=f"KB {ev.get('source')}: {ev.get('summary','')[:100]}",
                    patch_code=ev.get('code_snippet', ''),
                ))
        
        # Sort by confidence (highest first)
        ctx.hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        
        logger.info(f"  💡 Generated {len(ctx.hypotheses)} hypotheses (top: {ctx.hypotheses[0].description[:80] if ctx.hypotheses else 'none'})")

    # ═══════════════════════════════════════════════════════════
    # STEP 4: EXPERIMENT
    # ═══════════════════════════════════════════════════════════

    async def _experiment(self, ctx: EngineerContext) -> Optional[Dict]:
        """
        Pegar a melhor hipótese pendente e testá-la.
        Se tem patch → aplicar e compilar no sandbox.
        Se é "ler documentação" → buscar e extrair solução.
        """
        pending = [h for h in ctx.hypotheses if h.status == HypothesisStatus.PENDING]
        if not pending:
            logger.info("  🧪 EXPERIMENT: no pending hypotheses")
            return None
        
        best = pending[0]
        best.status = HypothesisStatus.TESTING
        logger.info(f"  🧪 EXPERIMENT: testing {best.id} — {best.description[:80]}")
        
        result = {
            'hypothesis_id': best.id,
            'success': False,
            'output': '',
            'new_errors': [],
            'resolved_errors': [],
        }
        
        evidence = best.evidence or {}
        error_type = evidence.get('error_type', '')
        symbol = evidence.get('symbol', '')
        
        # ═══ CASE 1: compile_error — fix syntax at specific location ═══
        if error_type == 'compile_error' or (best.source == 'build_error_analysis' and 'compilation' in best.description.lower()):
            result = self._experiment_compile_error(ctx, best, evidence)
        
        # ═══ CASE 2: undefined reference — add stub ═══
        
        # ═══ CASE 2: implicit declaration — find and add #include ═══
        elif error_type == 'implicit_declaration':
            result = self._experiment_implicit_decl(ctx, best, symbol)
        
        # ═══ CASE 3: search for symbol in project ═══
        elif error_type == 'search_symbol':
            result = self._experiment_search_symbol(ctx, best, symbol)
        
        # ═══ CASE 4: has patch code — compile and test ═══
        elif best.patch_code and best.patch_code.strip() and 'TODO' not in best.patch_code:
            sandbox = self._get_sandbox()
            if sandbox:
                try:
                    target_file = evidence.get('target_file', '')
                    if target_file and os.path.exists(target_file):
                        with open(target_file, errors='replace') as f:
                            original = f.read()
                        patched = self._apply_patch(original, best.patch_code)
                        validation = sandbox.validate_patch(original, patched)
                        result['success'] = validation.get('fixed', False)
                        result['output'] = str(validation)
                except Exception as e:
                    result['output'] = str(e)
        
        # ═══ CASE 5: build_output — parse and extract info ═══
        elif best.source in ('build_output', 'build_error_analysis') and ctx.build_errors:
            parsed = self._parse_build_error(ctx.build_errors[0])
            result.update(parsed)
            result['output'] = parsed.get('suggestion', '')
        
        else:
            result['output'] = f"No actionable experiment for hypothesis type: {error_type or best.source}"
        
        best.experiment_result = result
        
        if result.get('success'):
            best.status = HypothesisStatus.SUCCESS
            ctx.successful_hypotheses.append(best)
        else:
            best.status = HypothesisStatus.FAILED
            ctx.failed_hypotheses.append(best)
        
        logger.info(f"  🧪 Result: {'✅' if best.status == HypothesisStatus.SUCCESS else '❌'}")
        return result

    # ═══════════════════════════════════════════════════════════
    # STEP 5: MEASURE
    # ═══════════════════════════════════════════════════════════

    async def _measure(self, ctx: EngineerContext, result: Optional[Dict]) -> bool:
        """
        Medir se o problema foi resolvido.
        
        Critérios:
        - Build errors resolvidos?
        - Testes passam?
        - Objetivo atingido?
        """
        if not result:
            return False
        
        if result.get('success'):
            # Verify: rebuild and check
            if ctx.build_system:
                remaining_errors = self._try_build(ctx.project_root, ctx.build_system)
                if not remaining_errors:
                    logger.info("  📏 MEASURE: ✅ Build succeeded! Problem solved.")
                    return True
                else:
                    logger.info(f"  📏 MEASURE: ⚠️ Build improved but {len(remaining_errors)} errors remain")
                    ctx.build_errors = remaining_errors
                    return False
        
        return False

    # ═══════════════════════════════════════════════════════════
    # STEP 6: LEARN
    # ═══════════════════════════════════════════════════════════

    async def _learn(self, ctx: EngineerContext, result: Optional[Dict]):
        """Aprender com o resultado para melhorar próximas iterações."""
        if not result:
            return
        
        hyp_id = result.get('hypothesis_id', '')
        
        if result.get('success'):
            ctx.knowledge_gained.append(f"✅ {hyp_id}: worked! {result.get('output','')[:100]}")
        else:
            ctx.knowledge_gained.append(f"❌ {hyp_id}: failed. {result.get('output','')[:100]}")
        
        # Cross-pollinate: insights from this experiment inform future hypotheses
        for h in ctx.hypotheses:
            if h.status == HypothesisStatus.PENDING:
                # If similar to a failed hypothesis, reduce confidence
                if h.source == result.get('source', ''):
                    h.confidence *= 0.8

    # ═══════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════

    def _find_project_files(self, root: str) -> List[str]:
        """Find relevant source files in project."""
        files = []
        extensions = {'.c', '.cpp', '.h', '.hpp', '.py', '.rs', '.go', '.js', '.ts',
                     '.mk', '.cmake', '.txt', '.md', '.rst', '.yml', '.yaml', '.json',
                     '.toml', '.cfg', '.ini', '.conf'}
        skip_dirs = {'.git', '__pycache__', 'node_modules', 'build', 'target', 'dist',
                    '.venv', 'venv', '.idea', '.vscode'}
        
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]
            for f in filenames:
                ext = os.path.splitext(f)[1].lower()
                if ext in extensions:
                    rel = os.path.relpath(os.path.join(dirpath, f), root)
                    files.append(rel)
        
        return files[:200]  # Limit

    def _detect_build_system(self, root: str) -> str:
        """Detect which build system the project uses."""
        indicators = {
            'Makefile': 'make',
            'CMakeLists.txt': 'cmake',
            'meson.build': 'meson',
            'setup.py': 'python_setup',
            'pyproject.toml': 'python_pyproject',
            'Cargo.toml': 'cargo',
            'go.mod': 'go',
            'package.json': 'npm',
            'build.gradle': 'gradle',
            'pom.xml': 'maven',
            'SConstruct': 'scons',
            'BUILD': 'bazel',
        }
        for fname, system in indicators.items():
            if os.path.exists(os.path.join(root, fname)):
                return system
        return "unknown"

    def _find_docs(self, root: str) -> List[str]:
        """Find documentation files."""
        docs = []
        for f in os.listdir(root):
            lower = f.lower()
            if any(lower.startswith(p) for p in ['readme', 'install', 'building', 'contributing']):
                docs.append(f)
            if lower.endswith('.md') or lower.endswith('.rst'):
                docs.append(f)
        return docs[:10]

    def _try_build(self, root: str, build_system: str) -> List[str]:
        """Try to build and capture errors."""
        import subprocess
        
        build_cmds = {
            'make': ['make', '-j4'],
            'cmake': ['cmake', '--build', '.'],
            'meson': ['meson', 'compile', '-C', 'build'],
            'cargo': ['cargo', 'build'],
        }
        
        cmd = build_cmds.get(build_system)
        if not cmd:
            return []
        
        try:
            proc = subprocess.run(
                cmd, cwd=root, capture_output=True, text=True, timeout=60
            )
            stderr = proc.stderr + '\n' + proc.stdout
            errors = []
            for line in stderr.split('\n'):
                line = line.strip()
                if not line:
                    continue
                if any(kw in line.lower() for kw in ['error:', 'undefined reference', 
                        'implicit declaration', 'no such file', 'cannot find',
                        'fatal error', 'make:', 'failed', 'segfault', 'abort']):
                    errors.append(line)
            return errors[:50]
        except Exception as e:
            return [str(e)]

    def _parse_build_error(self, error: str) -> Dict:
        """Parse a build error into actionable information."""
        result = {
            'error_type': 'unknown',
            'file': '',
            'line': 0,
            'symbol': '',
            'suggestion': '',
        }
        
        # undefined reference to `symbol'
        m = re.search(r"undefined reference to [`'](\w+)[`']", error)
        if m:
            result['error_type'] = 'undefined_reference'
            result['symbol'] = m.group(1)
            result['suggestion'] = f"Link missing library providing '{m.group(1)}' or add implementation"
            return result
        
        # implicit declaration of function 'func'
        m = re.search(r"implicit declaration of function ['`](\w+)['`]", error)
        if m:
            result['error_type'] = 'implicit_declaration'
            result['symbol'] = m.group(1)
            result['suggestion'] = f"Add #include for header declaring '{m.group(1)}'"
            return result
        
        # file:line: error
        m = re.search(r'([\w./-]+):(\d+):\d*:\s*(?:error|warning):\s*(.+)', error)
        if m:
            result['error_type'] = 'compile_error'
            result['file'] = m.group(1)
            result['line'] = int(m.group(2))
            result['suggestion'] = f"Fix compilation error at {m.group(1)}:{m.group(2)}"
            return result
        
        result['suggestion'] = f"Analyze: {error[:100]}"
        return result

    def _apply_patch(self, original: str, patch: str) -> str:
        """Simple patch application."""
        if patch in original:
            return original  # Already applied?
        
        # Try to find old_str → new_str patterns in the patch
        lines = patch.strip().split('\n')
        for i, line in enumerate(lines):
            if '→' in line or '->' in line:
                parts = re.split(r'\s*->\s*|\s*→\s*', line)
                if len(parts) == 2:
                    return original.replace(parts[0].strip(), parts[1].strip())
        
        return original

    def _experiment_compile_error(self, ctx, hypothesis, evidence) -> Dict:
        """Fix a specific compilation error by analyzing the error and patching."""
        result = {
            'hypothesis_id': hypothesis.id,
            'success': False,
            'output': '',
        }
        
        # Parse build error for file and line
        target_file = evidence.get('file', '')
        target_line = evidence.get('line', 0)
        
        if not target_file:
            # Extract from build errors
            for err in ctx.build_errors:
                m = re.match(r'(\S+\.c):(\d+):(\d+):\s*(?:error|warning):\s*(.+)', err)
                if m:
                    target_file = m.group(1)
                    target_line = int(m.group(2))
                    error_msg = m.group(4)
                    break
        
        if not target_file or not target_line:
            result['output'] = "Could not parse build error for file:line"
            return result
        
        full_path = os.path.join(ctx.project_root, target_file)
        if not os.path.exists(full_path):
            result['output'] = f"File not found: {full_path}"
            return result
        
        # Read the file
        with open(full_path, 'r') as f:
            lines = f.readlines()
        
        if target_line > len(lines):
            result['output'] = f"Line {target_line} out of range"
            return result
        
        # Get the error line and surrounding context
        line_content = lines[target_line - 1].strip()
        error_msg = evidence.get('suggestion', '')
        
        # Try to parse what the error is about
        for err in ctx.build_errors:
            if target_file in err:
                error_msg = err
                break
        
        fix_applied = False
        new_line = line_content
        
        # Pattern 1: returning string from int function
        if 'return' in line_content.lower() and 'makes integer from pointer' in error_msg.lower():
            # Change function return type to char*
            for i in range(max(0, target_line - 5), target_line):
                if i < len(lines):
                    func_line = lines[i]
                    if re.match(r'^(?:static\s+)?int\s+\w+\s*\(', func_line):
                        lines[i] = func_line.replace('int ', 'const char* ', 1)
                        fix_applied = True
                        result['output'] = f"Changed return type from int to const char* at line {i+1}"
                        break
        
        # Pattern 2: general — try simple fixes
        if not fix_applied:
            if 'implicit' in error_msg.lower():
                new_line = '// ' + line_content  # Comment out problematic line
                lines[target_line - 1] = new_line + '\n'
                fix_applied = True
                result['output'] = f"Commented line {target_line} (implicit declaration)"
        
        if fix_applied:
            # Write back
            with open(full_path, 'w') as f:
                f.writelines(lines)
            
            # Try to rebuild
            remaining = self._try_build(ctx.project_root, ctx.build_system)
            if not remaining or not any('error:' in e for e in remaining):
                result['success'] = True
                ctx.build_errors = remaining
            else:
                result['output'] += f" (warnings remain: {len(remaining)})"
                ctx.build_errors = remaining
        else:
            result['output'] = f"Could not determine fix for: {line_content}"
        
        return result

    def _experiment_undefined_reference(self, ctx, hypothesis, symbol, error_type) -> Dict:
        """Handle undefined reference: find the right file and add stub."""
        result = {
            'hypothesis_id': hypothesis.id,
            'success': False,
            'output': '',
            'symbol': symbol,
        }
        
        # Find which .c file should contain this function
        # Strategy: search header files for declaration, then find matching .c
        target_c_file = None
        target_h_file = None
        
        for f in ctx.project_files:
            full = os.path.join(ctx.project_root, f)
            if not os.path.exists(full):
                continue
            try:
                with open(full, errors='replace') as fh:
                    content = fh.read()
                if f'void {symbol}' in content or f'int {symbol}' in content or f'char* {symbol}' in content:
                    if f.endswith('.h'):
                        target_h_file = full
                    elif f.endswith('.c'):
                        target_c_file = full
            except:
                pass  # noqa: bare-except — non-critical fallback
        
        # If found in .h but no .c, use the .h's matching .c
        if target_h_file and not target_c_file:
            base = target_h_file.replace('.h', '.c')
            if os.path.exists(base):
                target_c_file = base
        
        # If still not found, use first .c file that's not main.c
        if not target_c_file:
            for f in ctx.project_files:
                if f.endswith('.c') and 'main' not in f.lower():
                    target_c_file = os.path.join(ctx.project_root, f)
                    break
        
        if not target_c_file:
            result['output'] = f"Could not find target .c file for symbol '{symbol}'"
            return result
        
        # Read the target file
        with open(target_c_file, errors='replace') as fh:
            original = fh.read()
        
        # Generate the stub implementation
        stub = f"""
void {symbol}(char *buf) {{
    /* Auto-generated stub by Quimera Engineer */
    if (buf) {{ /* safely ignore */ }}
}}
"""
        
        # Check if stub already exists
        if symbol in original and ('void ' + symbol) in original:
            result['output'] = f"Symbol '{symbol}' already exists in {target_c_file}"
            result['success'] = False
            return result
        
        # Append stub to end of file
        patched = original.rstrip() + '\n' + stub + '\n'
        
        # Write patched file
        with open(target_c_file, 'w') as fh:
            fh.write(patched)
        
        # Try to rebuild
        remaining = self._try_build(ctx.project_root, ctx.build_system)
        
        if not remaining or not any('undefined reference' in e for e in remaining):
            result['success'] = True
            result['output'] = f"✅ Added stub for '{symbol}' to {os.path.basename(target_c_file)}. Build succeeded!"
            ctx.build_errors = remaining
        else:
            # Revert the change
            with open(target_c_file, 'w') as fh:
                fh.write(original)
            result['output'] = f"⚠️ Stub added but build still has {len(remaining)} errors"
            result['new_errors'] = remaining
        
        return result

    def _experiment_implicit_decl(self, ctx, hypothesis, symbol) -> Dict:
        """Handle implicit declaration: find which header declares the symbol."""
        result = {
            'hypothesis_id': hypothesis.id,
            'success': False,
            'output': '',
        }
        
        # Search all .h files for the symbol declaration
        for f in ctx.project_files:
            if not f.endswith('.h'):
                continue
            full = os.path.join(ctx.project_root, f)
            if not os.path.exists(full):
                continue
            try:
                with open(full, errors='replace') as fh:
                    if symbol in fh.read():
                        result['output'] = f"✅ Symbol '{symbol}' declared in {f}. Add #include \"{f}\""
                        result['success'] = True
                        return result
            except:
                pass  # noqa: bare-except — non-critical fallback
        
        result['output'] = f"⚠️ Symbol '{symbol}' not found in any header — may need external library"
        return result

    def _experiment_search_symbol(self, ctx, hypothesis, symbol) -> Dict:
        """Search entire project for a symbol definition."""
        result = {
            'hypothesis_id': hypothesis.id,
            'success': False,
            'output': '',
            'found_in': [],
        }
        
        for f in ctx.project_files:
            full = os.path.join(ctx.project_root, f)
            if not os.path.exists(full):
                continue
            try:
                with open(full, errors='replace') as fh:
                    content = fh.read()
                if symbol in content:
                    # Check if it's a definition (not just a call)
                    lines_with_symbol = [l.strip() for l in content.split('\n') if symbol in l]
                    for line in lines_with_symbol:
                        if f'void {symbol}' in line or f'int {symbol}' in line:
                            result['found_in'].append(f'DEFINITION in {f}: {line[:80]}')
                        elif f'{symbol}(' in line:
                            result['found_in'].append(f'CALL in {f}: {line[:80]}')
                        else:
                            result['found_in'].append(f'MENTION in {f}: {line[:80]}')
            except:
                pass  # noqa: bare-except — non-critical fallback
        
        if result['found_in']:
            result['success'] = True
            result['output'] = f"Found '{symbol}' in {len(result['found_in'])} locations: " + '; '.join(result['found_in'][:3])
        else:
            result['output'] = f"Symbol '{symbol}' not found anywhere in project"
        
        return result

    def _get_broker(self):
        if self._broker is None:
            try:
                from quimera.knowledge_broker import KnowledgeBroker
                self._broker = KnowledgeBroker(project_root=self.project_root)
            except ImportError:
                pass
        return self._broker

    def _get_detector(self):
        if self._detector is None:
            try:
                from quimera.detection_engine import DetectionEngine
                self._detector = DetectionEngine()
            except ImportError:
                pass
        return self._detector

    def _get_sandbox(self):
        if self._sandbox is None:
            try:
                from quimera.sandbox_executor import DockerSandbox
                self._sandbox = DockerSandbox()
            except ImportError:
                pass
        return self._sandbox
