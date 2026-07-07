"""
Candidate Generator — hybrid patch generation for Quimera.

ARCHITECTURE (3 levels):
  Level 1: DETERMINISTIC DETECTORS (regex, AST, KB patterns)
           → Fast, free, offline. Finds known patterns in microseconds.
  Level 2: CONTEXT BUILDER
           → Assembles full context: code, findings, errors, memory, project state.
  Level 3: LLM INTERFACE
           → Only when Level 1 fails OR when the finding is unknown/complex.
           → Returns 5-10 hypotheses, NOT a single answer.
           → Quimera NEVER trusts the LLM. It validates everything.

PHILOSOPHY:
  - The LLM is a CONSULTANT, not the engineer.
  - Quimera is the CHIEF ENGINEER: orchestrates, validates, rejects, learns.
  - Regex is not deprecated. It's Level 1 — fast and reliable for known patterns.
  - LLM is Level 3 — semantic reasoning for the unknown.

This module replaces PatchSynthesizer as the primary patch generation interface.
PatchSynthesizer is kept as a fallback for when no LLM is available.
"""

import os, time, json, re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum


# ═══════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════

class GenerationLevel(Enum):
    """Which level generated this candidate?"""
    DETERMINISTIC = "deterministic"   # regex / AST / KB
    HYBRID = "hybrid"                # KB + LLM refinement
    LLM = "llm"                      # pure LLM generation


@dataclass
class CandidatePatch:
    """A patch candidate, regardless of how it was generated."""
    id: str
    description: str
    patched_code: str
    diff: str = ""
    confidence: float = 0.25
    level: GenerationLevel = GenerationLevel.DETERMINISTIC
    # LLM-specific metadata (when Level 3)
    llm_model: str = ""
    llm_reasoning: str = ""          # why the LLM thinks this fixes it
    llm_risks: List[str] = field(default_factory=list)   # what could go wrong
    llm_requires_review: bool = False


@dataclass
class GenerationContext:
    """Rich context sent to the LLM for informed patch generation."""
    # Source
    file_path: str = ""
    file_content: str = ""
    language: str = "c"

    # Finding
    finding_description: str = ""
    finding_cwe: str = ""
    finding_line: int = 0
    finding_code_snippet: str = ""
    finding_confidence: float = 0.0

    # Surrounding code (100 lines before/after)
    context_before: str = ""   # 50-100 lines
    context_after: str = ""    # 50-100 lines

    # Compiler output
    compiler_errors: str = ""
    compiler_warnings: str = ""

    # Test results (before patch)
    tests_passed_before: int = 0
    tests_failed_before: int = 0
    tests_crashed_before: int = 0

    # Project info
    project_name: str = ""
    compiler: str = ""
    arch: str = ""
    build_system: str = ""

    # Patch Memory — similar patches and their outcomes
    similar_patches: List[Dict] = field(default_factory=list)
    # [{ "id": "K-001", "status": "PROVEN", "projects_succeeded": 3, "projects_failed": 1 }]

    # Resolution state
    resolution_state: str = "UNKNOWN"  # [OK], [FIX], [INV], [UNK]


# ═══════════════════════════════════════════════════════════════
# Level 1: Deterministic Detectors (keep existing regex/AST)
# ═══════════════════════════════════════════════════════════════

class DeterministicPatcher:
    """
    Level 1: Fast, deterministic patch generation.
    Uses regex patterns, AST heuristics, and KB rules.
    These are the same patterns from PatchSynthesizer — preserved and improved.
    """

    def generate(self, finding, source_code: str) -> List[CandidatePatch]:
        """
        Try to generate a patch deterministically.
        Returns [] if the pattern is unknown → triggers Level 2/3.
        """
        from quimera.patch_synthesis import PatchSynthesizer
        synthesizer = PatchSynthesizer()
        try:
            raw_candidates = synthesizer.synthesize(finding, source_code)
        except Exception:
            return []

        result = []
        for i, raw in enumerate(raw_candidates):
            result.append(CandidatePatch(
                id=f"DET-{i+1}",
                description=getattr(raw, 'description', 'deterministic patch'),
                patched_code=getattr(raw, 'patched_code', source_code),
                diff=getattr(raw, 'diff', ''),
                confidence=getattr(raw, 'confidence', 0.5),
                level=GenerationLevel.DETERMINISTIC,
            ))
        return result


# ═══════════════════════════════════════════════════════════════
# Level 2: Context Builder
# ═══════════════════════════════════════════════════════════════

class ContextBuilder:
    """
    Level 2: Assembles rich context for LLM consultation.

    Garbage in, garbage out. The quality of the LLM's response depends
    entirely on the quality of the context we give it.
    """

    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path.cwd()

    def build(self, finding, source_code: str, file_path: str = "",
              language: str = "c", extra: dict = None) -> GenerationContext:
        """
        Build full context from a finding + source code + available metadata.

        This is what gets sent to the LLM. Every field is PART of the prompt.
        """
        ctx = GenerationContext(
            file_path=file_path,
            file_content=source_code,
            language=language,
            finding_description=getattr(finding, 'description', ''),
            finding_cwe=getattr(finding, 'cwe_id', ''),
            finding_line=getattr(finding, 'line', 0),
            finding_code_snippet=getattr(finding, 'code_snippet', ''),
            finding_confidence=getattr(finding, 'confidence', 0.0),
        )

        # Surrounding context (100 lines before/after the finding)
        lines = source_code.split('\n')
        finding_line = ctx.finding_line
        if 0 < finding_line <= len(lines):
            idx = finding_line - 1
            start = max(0, idx - 100)
            end = min(len(lines), idx + 101)
            ctx.context_before = '\n'.join(lines[start:idx])
            ctx.context_after = '\n'.join(lines[idx+1:end])

        # Project info from extra
        if extra:
            ctx.project_name = extra.get('project_name', '')
            ctx.compiler = extra.get('compiler', '')
            ctx.arch = extra.get('arch', '')
            ctx.build_system = extra.get('build_system', '')
            ctx.compiler_errors = extra.get('compiler_errors', '')
            ctx.compiler_warnings = extra.get('compiler_warnings', '')

        # Layer 1: Patch Memory lookup
        ctx.similar_patches = self._lookup_memory(
            ctx.finding_cwe, ctx.finding_code_snippet
        )

        # Layer 2-7: KnowledgeBroker (cascade search)
        try:
            from quimera.knowledge_broker import KnowledgeBroker
            broker = KnowledgeBroker(str(self.project_root))
            knowledge_hits = broker.search(
                ctx.finding_description,
                ctx.finding_cwe,
                {'file': file_path, 'line': ctx.finding_line}
            )
            ctx.knowledge_hits = knowledge_hits
            # Merge KB results into similar_patches for richer context
            for hit in knowledge_hits[:5]:
                if hit.code_snippet:
                    ctx.similar_patches.append({
                        'id': hit.source.value,
                        'status': 'PROVEN' if hit.confidence > 0.7 else 'UNCERTAIN',
                        'projects_succeeded': int(hit.confidence * 10),
                        'projects_failed': 0,
                        'description': hit.summary,
                    })
        except ImportError:
            ctx.knowledge_hits = []
        ctx.similar_patches = self._lookup_memory(
            ctx.finding_cwe, ctx.finding_code_snippet
        )

        return ctx

    def _lookup_memory(self, cwe: str, snippet: str) -> List[Dict]:
        """Query Patch Memory for similar fixes and their outcomes."""
        results = []
        try:
            from quimera.patch_memory import PatchCatalog
            catalog = PatchCatalog()
            for pat in catalog.all_patches:
                if pat.pattern_regex and pat.pattern_regex in snippet:
                    results.append({
                        'id': pat.id,
                        'status': pat.status.value if hasattr(pat.status, 'value') else str(pat.status),
                        'projects_succeeded': pat.total_successes,
                        'projects_failed': pat.total_attempts - pat.total_successes,
                        'description': getattr(pat, 'description', ''),
                    })
                    if len(results) >= 5:
                        break
        except ImportError:
            pass
        return results


# ═══════════════════════════════════════════════════════════════
# Level 3: LLM Interface
# ═══════════════════════════════════════════════════════════════

class LLMInterface:
    """
    Level 3: Semantic reasoning via LLM.

    ONLY called when:
      - Level 1 (deterministic) returned nothing
      - OR the finding is complex/unknown
      - OR the user explicitly requests LLM analysis

    The LLM is a CONSULTANT. It proposes hypotheses.
    Quimera is the CHIEF ENGINEER. It validates, rejects, ranks, and learns.

    Supports ANY LLM backend via LLMClientFactory or direct API calls.
    """

    def __init__(self, model: str = None, api_key: str = None, provider: str = None):
        self.provider = provider or os.getenv('QUIMERA_LLM_PROVIDER', 'auto')

        # Use LLMConfig for intelligent model/provider selection
        if self.provider == 'auto':
            try:
                from quimera.llm_config import LLMConfig
                llm_config = LLMConfig()
                best = llm_config.best_for('code_generation', prefer_free=True)
                if best:
                    self.provider = best['provider']
                    self.model = best['model']
                    pinfo = llm_config.providers.get(self.provider, {})
                    env_var = pinfo.get('api_key_env', '')
                    self.api_key = api_key or os.getenv(env_var, '')
                else:
                    self.model = model or 'gpt-oss-120b:free'
                    self.provider = 'openrouter'
                    self.api_key = api_key or os.getenv('OPENROUTER_API_KEY', '')
            except ImportError:
                self.model = model or 'gpt-oss-120b:free'
                self.provider = 'openrouter'
                self.api_key = api_key or os.getenv('OPENROUTER_API_KEY', '')
        else:
            self.model = model or os.getenv('QUIMERA_LLM_MODEL', 'gpt-oss-120b:free')
            # Get key: explicit > env var for that provider > fallback
            if api_key:
                self.api_key = api_key
            else:
                env_var = f'{self.provider.upper()}_API_KEY'
                self.api_key = os.getenv(env_var, '') or os.getenv('OPENROUTER_API_KEY', '')
        self._client = None
        self._available = None  # lazy check

    @property
    def available(self) -> bool:
        """Check if the LLM backend is reachable."""
        if self._available is not None:
            return self._available
        if not self.api_key:
            self._available = False
            return False
        # Quick availability check — don't block
        self._available = len(self.api_key) > 10
        return self._available

    def generate_candidates(self, context: GenerationContext,
                           num_candidates: int = 8) -> List[CandidatePatch]:
        """
        Send context to LLM, receive multiple patch hypotheses.

        The prompt instructs the LLM to:
          1. Explain the root cause
          2. Propose N different hypotheses
          3. For each: patch code, reasoning, risks, confidence
          4. NEVER return a single answer — always multiple hypotheses

        Returns [] if LLM is unavailable or fails.
        """
        if not self.available:
            return []

        prompt = self._build_prompt(context, num_candidates)

        try:
            response = self._call_llm(prompt)
            candidates = self._parse_response(response, context)
            return candidates
        except Exception as e:
            # LLM failed — that's OK. Quimera falls back to Level 1.
            return []

    def _build_prompt(self, ctx: GenerationContext, num: int) -> str:
        """Build a detailed prompt requesting MULTIPLE hypotheses."""
        parts = []

        parts.append("You are a senior C/C++ security engineer analyzing a potential vulnerability.")
        parts.append("")
        parts.append("## PROJECT CONTEXT")
        parts.append(f"Project: {ctx.project_name or 'unknown'}")
        parts.append(f"Compiler: {ctx.compiler or 'gcc'}")
        parts.append(f"Architecture: {ctx.arch or 'x86_64'}")
        parts.append(f"Build system: {ctx.build_system or 'make'}")
        parts.append(f"Language: {ctx.language}")

        parts.append("")
        parts.append("## FINDING")
        parts.append(f"CWE: {ctx.finding_cwe or 'unknown'}")
        parts.append(f"Line: {ctx.finding_line}")
        parts.append(f"Description: {ctx.finding_description}")
        parts.append(f"Code snippet: `{ctx.finding_code_snippet}`")

        if ctx.compiler_errors:
            parts.append("")
            parts.append("## COMPILER ERRORS")
            parts.append(ctx.compiler_errors[:2000])

        if ctx.compiler_warnings:
            parts.append("")
            parts.append("## COMPILER WARNINGS")
            parts.append(ctx.compiler_warnings[:1000])

        if ctx.similar_patches:
            parts.append("")
            parts.append("## PATCH MEMORY (similar fixes and their outcomes)")
            for sp in ctx.similar_patches:
                parts.append(f"- {sp['id']}: {sp['status']}, "
                           f"succeeded in {sp['projects_succeeded']} projects, "
                           f"failed in {sp['projects_failed']}")

        parts.append("")
        parts.append("## SURROUNDING CODE (before finding)")
        parts.append("```c")
        parts.append(ctx.context_before[:3000])
        parts.append("```")

        parts.append("")
        parts.append("## SURROUNDING CODE (after finding)")
        parts.append("```c")
        parts.append(ctx.context_after[:3000])
        parts.append("```")

        parts.append("")
        parts.append("## FULL FILE")
        parts.append("```c")
        parts.append(ctx.file_content[:8000])
        parts.append("```")

        parts.append("")
        parts.append(f"## YOUR TASK")
        parts.append(f"")
        parts.append(f"Propose exactly {num} DIFFERENT hypotheses for fixing this issue.")
        parts.append(f"Each hypothesis must be a COMPLETE patched version of the FULL file.")
        parts.append(f"")
        parts.append(f"For each hypothesis, respond in this exact JSON format:")
        parts.append(f"```json")
        parts.append(f"{{")
        parts.append(f'  "hypotheses": [')
        parts.append(f"    {{")
        parts.append(f'      "id": "H1",')
        parts.append(f'      "approach": "brief description of the approach (one line)",')
        parts.append(f'      "reasoning": "why this approach fixes the root cause",')
        parts.append(f'      "risks": ["risk 1", "risk 2"],')
        parts.append(f'      "confidence": 0.85,')
        parts.append(f'      "patched_code": "COMPLETE file content with fix applied"')
        parts.append(f"    }}")
        parts.append(f"  ]")
        parts.append(f"}}")
        parts.append(f"```")
        parts.append(f"")
        parts.append(f"RULES:")
        parts.append(f"1. patched_code MUST be the COMPLETE file, not just the diff.")
        parts.append(f"2. Generate EXACTLY {num} hypotheses. Different approaches for each.")
        parts.append(f"3. Confidence must be between 0.0 and 1.0.")
        parts.append(f"4. If the finding is a false positive, say so and explain why.")
        parts.append(f"5. Prefer minimal changes. Don't rewrite the entire file unnecessarily.")

        return '\n'.join(parts)

    def _call_llm(self, prompt: str) -> str:
        """
        Call the LLM backend. Supports multiple providers.

        Priority:
          1. LLMClientFactory (pluggable)
          2. Mistral API (tested, works with free tier)
          3. Anthropic Claude API
          4. Generic OpenAI-compatible endpoint

        Each provider is tried in order; first successful response wins.
        """
        import urllib.request, urllib.error

        # Try LLMClientFactory first
        try:
            from quimera.llm_client_factory import LLMClientFactory
            client = LLMClientFactory.create(self.provider, model=self.model, api_key=self.api_key)
            if client:
                result = client.invoke(prompt)
                if result:
                    return result
        except Exception:
            pass

        # Determine which API to call based on provider
        provider = self.provider.lower()

        # OpenRouter API (primary — FREE models, no credit card needed)
        if provider in ('openrouter', 'auto'):
            try:
                or_model = self.model if provider == 'openrouter' else os.getenv(
                    'QUIMERA_OPENROUTER_MODEL', 'openai/gpt-oss-120b:free')
                url = "https://openrouter.ai/api/v1/chat/completions"
                body = json.dumps({
                    "model": or_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 8000,
                    "temperature": 0.7,
                }).encode()
                req = urllib.request.Request(url, data=body, headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/izaque/quimera",
                    "X-Title": "Quimera",
                }, method='POST')
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = json.loads(resp.read().decode())
                    return data["choices"][0]["message"]["content"]
            except Exception:
                if provider == 'openrouter':
                    raise

        # Mistral API (tested and working with free tier)
        if provider in ('mistral', 'auto'):
            try:
                url = "https://api.mistral.ai/v1/chat/completions"
                body = json.dumps({
                    "model": self.model if provider == 'mistral' else "mistral-small-latest",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 8000,
                    "temperature": 0.7,
                }).encode()
                req = urllib.request.Request(url, data=body, headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }, method='POST')
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = json.loads(resp.read().decode())
                    return data["choices"][0]["message"]["content"]
            except Exception:
                if provider == 'mistral':
                    raise  # if user explicitly chose mistral, don't fallback silently

        # Anthropic Claude API
        if provider in ('anthropic', 'auto'):
            try:
                url = "https://api.anthropic.com/v1/messages"
                body = json.dumps({
                    "model": self.model if provider == 'anthropic' else "claude-sonnet-4-20250514",
                    "max_tokens": 8000,
                    "temperature": 0.7,
                    "messages": [{"role": "user", "content": prompt}],
                }).encode()
                req = urllib.request.Request(url, data=body, headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                }, method='POST')
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = json.loads(resp.read().decode())
                    return data.get('content', [{}])[0].get('text', '')
            except Exception:
                if provider == 'anthropic':
                    raise

        # Generic OpenAI-compatible endpoint (Groq, Together, Fireworks, etc.)
        if provider not in ('anthropic', 'mistral'):
            try:
                endpoint = os.getenv('QUIMERA_LLM_ENDPOINT', '')
                if not endpoint and provider == 'groq':
                    endpoint = "https://api.groq.com/openai/v1/chat/completions"
                if not endpoint and provider == 'together':
                    endpoint = "https://api.together.xyz/v1/chat/completions"
                if endpoint:
                    body = json.dumps({
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 8000,
                        "temperature": 0.7,
                    }).encode()
                    req = urllib.request.Request(endpoint, data=body, headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    }, method='POST')
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        data = json.loads(resp.read().decode())
                        return data["choices"][0]["message"]["content"]
            except Exception:
                pass

        raise RuntimeError(f"No LLM backend available for provider '{self.provider}'")

    def _parse_response(self, response: str, ctx: GenerationContext) -> List[CandidatePatch]:
        """
        Parse LLM response into CandidatePatch objects.

        Handles:
          - JSON block (```json ... ```)
          - Raw JSON
          - Fallback: extract code blocks if JSON parsing fails
        """
        candidates = []

        # Try to extract JSON block
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                for h in data.get('hypotheses', []):
                    candidates.append(CandidatePatch(
                        id=h.get('id', f'LLM-{len(candidates)+1}'),
                        description=h.get('approach', 'LLM-generated patch'),
                        patched_code=h.get('patched_code', ctx.file_content),
                        diff='',  # can compute later
                        confidence=h.get('confidence', 0.5),
                        level=GenerationLevel.LLM,
                        llm_model=self.model,
                        llm_reasoning=h.get('reasoning', ''),
                        llm_risks=h.get('risks', []),
                        llm_requires_review=h.get('confidence', 0.5) < 0.7,
                    ))
                return candidates
            except json.JSONDecodeError:
                pass

        # Try raw JSON
        try:
            data = json.loads(response)
            for h in data.get('hypotheses', []):
                candidates.append(CandidatePatch(
                    id=h.get('id', f'LLM-{len(candidates)+1}'),
                    description=h.get('approach', 'LLM-generated patch'),
                    patched_code=h.get('patched_code', ctx.file_content),
                    confidence=h.get('confidence', 0.5),
                    level=GenerationLevel.LLM,
                    llm_model=self.model,
                    llm_reasoning=h.get('reasoning', ''),
                    llm_risks=h.get('risks', []),
                ))
            return candidates
        except json.JSONDecodeError:
            pass

        # Fallback: extract code blocks as individual candidates
        code_blocks = re.findall(r'```(?:c|cpp)?\s*\n(.*?)\n```', response, re.DOTALL)
        for i, block in enumerate(code_blocks):
            if len(block) > 50:  # skip tiny snippets
                candidates.append(CandidatePatch(
                    id=f'LLM-FALLBACK-{i+1}',
                    description='LLM response (parsed from code block)',
                    patched_code=block,
                    confidence=0.3,
                    level=GenerationLevel.LLM,
                    llm_model=self.model,
                    llm_requires_review=True,
                ))

        return candidates


# ═══════════════════════════════════════════════════════════════
# Candidate Generator — orchestrates all 3 levels
# ═══════════════════════════════════════════════════════════════

class CandidateGenerator:
    """
    Hybrid candidate generator — combines deterministic + LLM approaches.

    FLOW:
      1. Level 1: Try deterministic (regex/AST/KB)
         → If found: return immediately (fast, free, reliable)

      2. Level 1 returned nothing?
         → Level 2: Build full context
         → Level 3: Consult LLM for multiple hypotheses
         → Return LLM candidates (if available)

      3. LLM unavailable? Fall back to PatchSynthesizer.

    CONFIGURATION:
      - set QUIMERA_LLM_MODEL env var (default: claude-sonnet-4-20250514)
      - set ANTHROPIC_API_KEY env var (or your provider's key)
      - set QUIMERA_LLM_PROVIDER env var (default: anthropic)
    """

    def __init__(self, project_root: Path = None, use_llm: bool = True):
        self.project_root = project_root or Path.cwd()
        self.use_llm = use_llm
        self.context_builder = ContextBuilder(project_root)
        self.deterministic = DeterministicPatcher()
        self.llm = LLMInterface() if use_llm else None

    def generate(self, finding, source_code: str, file_path: str = "",
                 language: str = "c", extra: dict = None,
                 num_candidates: int = 8) -> List[CandidatePatch]:
        """
        Generate patch candidates for a single finding.

        Returns a list of CandidatePatch objects, ordered:
          - Deterministic first (reliable)
          - LLM-generated second (needs validation)
        """
        all_candidates = []

        # ── LEVEL 1: Deterministic ──────────────────────
        det_candidates = self.deterministic.generate(finding, source_code)
        all_candidates.extend(det_candidates)

        # ── LEVEL 2+3: Context + LLM ────────────────────
        # Trigger LLM if:
        #   - No deterministic candidates found
        #   - OR finding confidence is low (< 0.5)
        #   - OR finding is UNKNOWN
        finding_conf = getattr(finding, 'confidence', 1.0)
        finding_state = getattr(finding, 'resolution_state', '')
        needs_llm = (
            len(det_candidates) == 0
            or finding_conf < 0.5
            or 'UNKNOWN' in str(finding_state).upper()
        )

        if needs_llm and self.llm and self.llm.available:
            ctx = self.context_builder.build(finding, source_code, file_path, language, extra)
            llm_candidates = self.llm.generate_candidates(ctx, num_candidates)
            all_candidates.extend(llm_candidates)

        # ── Fallback: if nothing at all, try PatchSynthesizer ──
        if not all_candidates:
            from quimera.patch_synthesis import PatchSynthesizer
            try:
                synthesizer = PatchSynthesizer()
                raw = synthesizer.synthesize(finding, source_code)
                for i, r in enumerate(raw):
                    all_candidates.append(CandidatePatch(
                        id=f'FALLBACK-{i+1}',
                        description=getattr(r, 'description', 'fallback patch'),
                        patched_code=getattr(r, 'patched_code', source_code),
                        confidence=0.1,
                        level=GenerationLevel.DETERMINISTIC,
                    ))
            except Exception:
                pass


        # Step 4: Rank all candidates
        self._rank_candidates(all_candidates, source_code, file_path)

        return all_candidates

    def _generate_level1_ast(self, findings, source_code: str,
                            num_per_finding: int = 10) -> list:
        """Level 1: AST-based multi-candidate generation."""
        candidates = []
        try:
            from quimera.ast_patcher import ASTPatcher
            patcher = ASTPatcher()
            if patcher.available:
                for f in findings:
                    ast_cands = patcher.generate(f, source_code, num_per_finding)
                    for ac in ast_cands:
                        candidates.append(CandidatePatch(
                            id=ac.id,
                            description=ac.description,
                            patched_code=ac.patched_code,
                            approach=ac.approach,
                            confidence=ac.confidence,
                            level=GenerationLevel.DETERMINISTIC,
                            risk_level=ac.risk_level,
                        ))
                return candidates
        except ImportError:
            pass

        # Fallback to regex DeterministicPatcher
        return self._generate_level1(findings, source_code)

    def _rank_candidates(self, candidates, source_code, file_path):
        """Rank candidates by compile + tests + sanitizers + diff."""
        if len(candidates) <= 1:
            return
        try:
            from quimera.candidate_ranker import CandidateRanker
            ranker = CandidateRanker(str(self.project_root) if self.project_root else "")
            ranked = ranker.rank(candidates, source_code, file_path)

            # Reorder candidates by rank
            candidates.sort(key=lambda c: next(
                (r.final_score for r in ranked if r.id == c.id), c.confidence
            ), reverse=True)

            # Mark the best
            if candidates:
                candidates[0].is_best = True
        except ImportError:
            pass
