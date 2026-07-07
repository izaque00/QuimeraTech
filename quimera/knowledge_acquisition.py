"""
Knowledge Acquisition Layer — Quimera Mark X

Resolves: "How to repair something completely unknown?"

This layer does NOT fix code. It only RESEARCHES.
When the pipeline encounters an error with no matching rule in EngineeringKB,
this layer:
  1. Collects context (file, line, AST, stacktrace, compiler, version)
  2. Searches multiple knowledge sources (docs, commits, issues, CVEs, forums)
  3. Synthesizes hypotheses with confidence scores
  4. Returns evidence to the pipeline for sandbox validation

Architecture:
  Unknown Error
    → Knowledge Acquisition
      → Research (multi-source)
        → Hypotheses (with confidence + sources)
          → Quimera tests in sandbox
            → If passes → proposal

The AI never writes to the project. It only answers questions.

Author: Quimera Mark X — MetaX
"""

import json, logging, re, time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("quimera.knowledge_acquisition")


# ═══════════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════════

class SourceType(Enum):
    """Knowledge source with implicit trust level."""
    OFFICIAL_DOCS   = "official_docs"      # 0.98 — language/compiler/framework docs
    ENGINEERING_KB  = "engineering_kb"     # 0.95 — previously validated knowledge
    PROJECT_HISTORY = "project_history"    # 0.85 — own commits, issues, fixes
    GITHUB_ISSUE    = "github_issue"       # 0.75 — resolved issues, merged PRs
    CVE_DATABASE    = "cve_database"       # 0.90 — NVD/MITRE entries
    MAILING_LIST    = "mailing_list"       # 0.65 — LKML, distro lists
    STACK_OVERFLOW  = "stack_overflow"     # 0.55 — accepted answers
    COMMUNITY_BLOG  = "community_blog"     # 0.30 — medium, dev.to, personal blogs
    IA_SYNTHESIS    = "ia_synthesis"       # 0.50 — AI-generated hypothesis (needs validation)

# Source trust mapping
SOURCE_TRUST = {s.value: s for s in SourceType}
SOURCE_CONFIDENCE_BASE = {
    "official_docs":   0.98,
    "engineering_kb":  0.95,
    "cve_database":    0.90,
    "project_history": 0.85,
    "github_issue":    0.75,
    "mailing_list":    0.65,
    "stack_overflow":  0.55,
    "ia_synthesis":    0.50,
    "community_blog":  0.30,
}


@dataclass
class ErrorContext:
    """Full context of an error for research."""
    # Error metadata
    error_message: str = ""
    error_type: str = ""          # compilation, runtime, linker, test_failure, kernel_panic
    raw_output: str = ""          # complete compiler/interpreter output

    # Code location
    file_path: str = ""
    line_number: int = 0
    column: int = 0
    function_name: str = ""

    # Code context
    surrounding_code: str = ""    # ±50 lines around error
    function_code: str = ""       # full function containing error
    includes_imports: str = ""    # #include / import statements

    # Build context
    language: str = ""
    compiler: str = ""
    compiler_version: str = ""
    build_system: str = ""        # make, cmake, cargo, pip, etc.
    target_arch: str = ""
    flags: str = ""

    # Project context
    project_name: str = ""
    project_version: str = ""
    dependencies: List[str] = field(default_factory=list)

    # Extracted tokens
    error_tokens: List[str] = field(default_factory=list)  # key identifiers from error
    stacktrace: List[str] = field(default_factory=list)


@dataclass
class ResearchSource:
    """A single piece of evidence found during research."""
    source_type: str = ""         # SourceType value
    url: str = ""
    title: str = ""
    summary: str = ""             # what this source says about the error
    relevance: float = 0.0        # 0-1 how relevant to this specific error
    excerpt: str = ""             # key quote or code snippet from source
    resolved_by: str = ""         # commit hash, PR number, or fix description
    base_confidence: float = 0.0  # confidence from source type alone


@dataclass
class Hypothesis:
    """A candidate explanation/fix for the error, built from research."""
    id: str = ""
    description: str = ""          # what we think is happening
    proposed_fix: str = ""         # code or config change
    confidence: float = 0.0        # composite confidence from all sources
    sources: List[ResearchSource] = field(default_factory=list)
    requires_validation: bool = True  # always True — never auto-apply

    def __post_init__(self):
        if not self.id:
            self.id = f"hyp-{hash(self.description) % 100000:05d}"


@dataclass
class ResearchReport:
    """Complete research output for an unknown error."""
    error_context: ErrorContext = field(default_factory=ErrorContext)
    hypotheses: List[Hypothesis] = field(default_factory=list)
    sources_found: int = 0
    sources_consulted: List[str] = field(default_factory=list)
    research_time_ms: float = 0.0
    kb_was_consulted: bool = False
    kb_had_match: bool = False

    @property
    def best_hypothesis(self) -> Optional[Hypothesis]:
        if self.hypotheses:
            return max(self.hypotheses, key=lambda h: h.confidence)
        return None

    @property
    def has_high_confidence(self) -> bool:
        bh = self.best_hypothesis
        return bh is not None and bh.confidence >= 0.80


# ═══════════════════════════════════════════════════════════════════
# Knowledge Acquisition Engine
# ═══════════════════════════════════════════════════════════════════

class KnowledgeAcquisitionLayer:
    """
    Researches unknown errors by consulting multiple knowledge sources.

    NEVER modifies code. Only produces hypotheses for the pipeline to validate.

    Source priority:
      1. EngineeringKB (fastest, most trusted)
      2. Official documentation
      3. Project history
      4. CVE database
      5. Public sources (GitHub, Stack Overflow, mailing lists)
      6. AI synthesis (last resort, always needs sandbox validation)
    """

    def __init__(self, search_web: bool = False):
        self.search_web = search_web  # requires API keys / network
        self._kb = None
        self._research_log: List[ResearchReport] = []

    @property
    def kb(self):
        if self._kb is None:
            try:
                from quimera.cognition.engineering_kb import engineering_kb
                self._kb = engineering_kb
            except ImportError:
                self._kb = None
        return self._kb

    # ── Main entry point ────────────────────────────────────────────

    def research(self, ctx: ErrorContext) -> ResearchReport:
        """
        Research an unknown error and return hypotheses with confidence scores.

        This is the main entry point. It:
        1. Checks EngineeringKB first (fast path)
        2. Extracts error tokens for searching
        3. Searches external sources (if enabled)
        4. Synthesizes hypotheses with confidence scores
        5. Returns a ResearchReport for the pipeline to validate
        """
        t0 = time.monotonic()
        report = ResearchReport(error_context=ctx)
        report.sources_consulted = []

        # Step 0: Extract meaningful tokens from the error
        ctx.error_tokens = self._extract_error_tokens(ctx)

        # Step 1: Check EngineeringKB (fastest, most trusted)
        if self.kb:
            report.kb_was_consulted = True
            kb_matches = self._search_kb(ctx)
            for match in kb_matches:
                report.hypotheses.append(match)
                report.kb_had_match = True
                report.sources_consulted.append("engineering_kb")

        # Step 2: If KB had high-confidence match, return immediately
        if report.has_high_confidence:
            report.research_time_ms = (time.monotonic() - t0) * 1000
            logger.info(f"KB had high-confidence match for: {ctx.error_message[:80]}")
            return report

        # Step 3: Search external sources (if enabled)
        if self.search_web:
            external_hypotheses = self._search_external_sources(ctx)
            for hyp in external_hypotheses:
                # Don't duplicate KB matches
                existing_descs = {h.description for h in report.hypotheses}
                if hyp.description not in existing_descs:
                    report.hypotheses.append(hyp)
            report.sources_consulted.extend(
                list(set(s.source_type for h in external_hypotheses for s in h.sources))
            )

        # Step 4: If still nothing, generate AI synthesis hypothesis (low confidence)
        if not report.hypotheses:
            synth = self._generate_ai_hypothesis(ctx)
            if synth:
                report.hypotheses.append(synth)
                report.sources_consulted.append("ia_synthesis")

        # Sort by confidence (highest first)
        report.hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        report.sources_found = sum(len(h.sources) for h in report.hypotheses)
        report.research_time_ms = (time.monotonic() - t0) * 1000

        logger.info(
            f"Research complete: {len(report.hypotheses)} hypotheses, "
            f"best confidence={report.best_hypothesis.confidence if report.best_hypothesis else 0:.2f}, "
            f"{report.research_time_ms:.0f}ms"
        )

        return report

    # ── Error Token Extraction ──────────────────────────────────────

    def _extract_error_tokens(self, ctx: ErrorContext) -> List[str]:
        """Extract meaningful search tokens from error message and code context."""
        tokens = set()

        # From error message: extract identifiers, types, function names
        error_text = ctx.error_message + "\n" + ctx.raw_output

        # Common patterns in compiler errors
        patterns = [
            r"undefined reference to [`'](\w+)'",        # linker
            r"implicit declaration of function ['`](\w+)", # C
            r"incompatible pointer type.*?(\w+\s*\*?\s*\w+)", # type mismatch
            r"no member named ['`](\w+)'",               # struct/class
            r"error:\s*(.+?)(?:\n|$)",                   # general error
            r"warning:\s*(.+?)(?:\n|$)",                  # warning
            r"(\w+Error|\w+Exception):?\s*(.+?)(?:\n|$)",  # exception
            r"cannot find (symbol|type|module|package)\s+['`](\w+)",
            r"expected\s+['`](\S+)['`].*?found\s+['`](\S+)['`]",
        ]

        for pattern in patterns:
            for m in re.finditer(pattern, error_text, re.IGNORECASE):
                for group in m.groups():
                    if group and len(group) > 1 and len(group) < 100:
                        tokens.add(group.strip().strip("'\";:,.()[]{}"))

        # From code context: extract function names, types, includes
        if ctx.surrounding_code:
            func_names = re.findall(r'\b([a-zA-Z_]\w{2,})\s*\(', ctx.surrounding_code)
            tokens.update(func_names[:10])

            includes = re.findall(r'#include\s*[<"]([^>"]+)[>"]', ctx.surrounding_code)
            tokens.update(includes)

        # Filter noise
        noise = {"int", "char", "void", "const", "static", "return", "if", "for",
                 "while", "sizeof", "struct", "error", "Error", "warning", "Warning",
                 "note", "Note", "file", "line", "the", "and", "not", "but"}
        tokens = tokens - noise

        return list(tokens)[:20]

    # ── Knowledge Base Search ───────────────────────────────────────

    def _search_kb(self, ctx: ErrorContext) -> List[Hypothesis]:
        """Search EngineeringKB for matching patterns."""
        hypotheses = []

        if not self.kb:
            return hypotheses

        # Search by vulnerability patterns
        vulns = self.kb.find_vulnerabilities(ctx.language)
        for vuln in vulns:
            if vuln.detection_pattern and ctx.error_message:
                if re.search(vuln.detection_pattern, ctx.error_message, re.IGNORECASE):
                    hyp = Hypothesis(
                        description=f"KB match: {vuln.name} ({vuln.cwe_id})",
                        proposed_fix=vuln.fix_pattern,
                        confidence=SOURCE_CONFIDENCE_BASE["engineering_kb"],
                        sources=[ResearchSource(
                            source_type="engineering_kb",
                            title=vuln.name,
                            summary=vuln.description,
                            excerpt=vuln.fix_pattern,
                            relevance=0.95,
                            base_confidence=SOURCE_CONFIDENCE_BASE["engineering_kb"],
                        )],
                    )
                    hypotheses.append(hyp)

        # Search by error tokens against known cases
        for vuln in self.kb._vulnerabilities.values():
            for case in vuln.known_cases:
                case_desc = case.get("error", "") + case.get("description", "")
                matching_tokens = sum(
                    1 for token in ctx.error_tokens
                    if token.lower() in case_desc.lower()
                )
                if matching_tokens >= 2:
                    hyp = Hypothesis(
                        description=f"Similar case: {vuln.name} — {case.get('description', '')}",
                        proposed_fix=case.get("fix", vuln.fix_pattern),
                        confidence=SOURCE_CONFIDENCE_BASE["engineering_kb"] * 0.8,
                        sources=[ResearchSource(
                            source_type="engineering_kb",
                            title=f"Known case for {vuln.vuln_id}",
                            summary=case_desc[:200],
                            excerpt=case.get("fix", ""),
                            relevance=matching_tokens / max(len(ctx.error_tokens), 1),
                            base_confidence=SOURCE_CONFIDENCE_BASE["engineering_kb"],
                        )],
                    )
                    hypotheses.append(hyp)

        return hypotheses

    # ── External Source Search ─────────────────────────────────────

    def _search_external_sources(self, ctx: ErrorContext) -> List[Hypothesis]:
        """
        Search external knowledge sources.

        In production, this would:
        - Query GitHub API for issues/commits matching error tokens
        - Search Stack Overflow for similar errors
        - Check CVE database for known vulnerabilities
        - Search mailing list archives (LKML, distro lists)
        - Fetch official documentation for the language/compiler

        For now, returns structured placeholder that the caller
        (or an AI agent) can fill with actual search results.
        """
        hypotheses = []

        # CVE search — fast keyword match against known CVEs
        cve_hyp = self._search_cve_database(ctx)
        if cve_hyp:
            hypotheses.append(cve_hyp)

        # GitHub issue search placeholder
        github_hyp = self._search_github_issues(ctx)
        if github_hyp:
            hypotheses.append(github_hyp)

        # Stack Overflow placeholder
        so_hyp = self._search_stack_overflow(ctx)
        if so_hyp:
            hypotheses.append(so_hyp)

        # Documentation search placeholder
        doc_hyp = self._search_documentation(ctx)
        if doc_hyp:
            hypotheses.append(doc_hyp)

        return hypotheses

    def _search_cve_database(self, ctx: ErrorContext) -> Optional[Hypothesis]:
        """Search CVE database for known vulnerabilities matching error context."""
        # CWE-120: Buffer Overflow — if error mentions buffer/overflow/strcpy
        buffer_keywords = {"buffer", "overflow", "strcpy", "strcat", "gets", "memcpy",
                          "overrun", "bounds", "corruption", "segfault", "segmentation"}
        error_lower = ctx.error_message.lower()

        matching_cwes = []
        if any(kw in error_lower for kw in buffer_keywords):
            matching_cwes.append(("CWE-120", "Buffer Overflow",
                "Unchecked buffer operations leading to memory corruption",
                "Use strncpy, snprintf, or safe alternatives. Check buffer bounds."))

        # CWE-476: NULL Pointer Dereference
        null_keywords = {"null", "dereference", "segfault", "null pointer", "nullptr"}
        if any(kw in error_lower for kw in null_keywords):
            matching_cwes.append(("CWE-476", "NULL Pointer Dereference",
                "Pointer used without NULL check — potential crash",
                "Add NULL check: if (!ptr) return ERR;"))

        # CWE-416: Use After Free
        uaf_keywords = {"use after free", "uaf", "dangling", "free"}
        if any(kw in error_lower for kw in uaf_keywords):
            matching_cwes.append(("CWE-416", "Use After Free",
                "Memory accessed after deallocation",
                "Set pointer to NULL after free(): ptr = NULL;"))

        if matching_cwes:
            cwe_id, name, desc, fix = matching_cwes[0]
            return Hypothesis(
                description=f"CVE match: {name} ({cwe_id}) — {desc}",
                proposed_fix=fix,
                confidence=SOURCE_CONFIDENCE_BASE["cve_database"] * 0.9,
                sources=[ResearchSource(
                    source_type="cve_database",
                    title=f"{cwe_id}: {name}",
                    summary=desc,
                    excerpt=fix,
                    relevance=0.80,
                    base_confidence=SOURCE_CONFIDENCE_BASE["cve_database"],
                )],
            )

        return None

    def _search_github_issues(self, ctx: ErrorContext) -> Optional[Hypothesis]:
        """
        Search GitHub issues for similar errors via GitHub REST API.

        Uses GITHUB_TOKEN env var for authenticated requests (higher rate limit).
        Falls back gracefully when token is not available or API is unreachable.
        """
        import urllib.request
        import urllib.error
        import json as _json
        
        query_terms = ctx.error_tokens[:5]
        if not query_terms:
            return None

        query = '+'.join(query_terms[:3])
        url = f"https://api.github.com/search/issues?q={query}+language:{ctx.language}&per_page=3&sort=updated"
        
        try:
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Quimera/3.0",
            }
            github_token = os.environ.get("GITHUB_TOKEN", "")
            if github_token:
                headers["Authorization"] = f"Bearer {github_token}"
            
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = _json.loads(resp.read())
                items = data.get("items", [])
                
                if items:
                    best = items[0]
                    return Hypothesis(
                        description=f"GitHub: {best.get('title', 'N/A')[:120]} — "
                                   f"{best.get('html_url', '')}",
                        proposed_fix=f"See GitHub issue for resolution: {best.get('html_url', '')}",
                        confidence=SOURCE_CONFIDENCE_BASE["github_issue"] * 0.85,
                        sources=[ResearchSource(
                            source_type="github_issue",
                            title=best.get("title", "GitHub Issue")[:200],
                            summary=best.get("body", "")[:500] if best.get("body") else "No description",
                            excerpt=f"GitHub #{best.get('number', 'N/A')}: {best.get('html_url', '')}",
                            relevance=0.70,
                            base_confidence=SOURCE_CONFIDENCE_BASE["github_issue"],
                        )],
                    )
        except Exception as e:
            logger.debug(f"GitHub API search failed: {e}")
        
        # Fallback: return hypothesis with lower confidence
        return Hypothesis(
            description=f"GitHub search: '{' '.join(query_terms[:3])}' — "
                        f"no results or API unavailable",
            proposed_fix=f"Search GitHub manually for: {' '.join(query_terms[:5])}",
            confidence=SOURCE_CONFIDENCE_BASE["github_issue"] * 0.3,
            sources=[ResearchSource(
                source_type="github_issue",
                title=f"GitHub: {' '.join(query_terms[:3])}",
                summary=f"GitHub issue search for {' '.join(query_terms[:5])}",
                excerpt="API unavailable — try manual search",
                relevance=0.25,
                base_confidence=SOURCE_CONFIDENCE_BASE["github_issue"],
            )],
        )

    def _search_stack_overflow(self, ctx: ErrorContext) -> Optional[Hypothesis]:
        """Search Stack Overflow via Stack Exchange API for similar errors."""
        import urllib.request
        import urllib.error
        import json as _json
        
        tokens = ctx.error_tokens[:3]
        if not tokens:
            return None

        query = '+'.join(tokens)
        url = (
            f"https://api.stackexchange.com/2.3/search?"
            f"order=desc&sort=relevance&intitle={query}"
            f"&tagged={ctx.language if ctx.language in ('c','c++','python','rust') else 'c'}"
            f"&site=stackoverflow&pagesize=3"
        )
        
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Quimera/3.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = _json.loads(resp.read())
                items = data.get("items", [])
                
                if items:
                    best = items[0]
                    accepted_answer = any(
                        a.get("is_accepted", False) 
                        for a in data.get("items", []) 
                        if a.get("answer_count", 0) > 0
                    )
                    return Hypothesis(
                        description=f"Stack Overflow: {best.get('title', 'N/A')[:120]} "
                                   f"(score={best.get('score', 0)}, accepted={accepted_answer})",
                        proposed_fix=f"See SO answer: {best.get('link', '')}",
                        confidence=SOURCE_CONFIDENCE_BASE["stack_overflow"] * (
                            0.9 if accepted_answer else 0.7
                        ),
                        sources=[ResearchSource(
                            source_type="stack_overflow",
                            title=best.get("title", "SO Question")[:200],
                            summary=f"Score: {best.get('score', 0)}, "
                                   f"Answers: {best.get('answer_count', 0)}, "
                                   f"Tags: {', '.join(best.get('tags', []))}",
                            excerpt=best.get("link", ""),
                            relevance=0.65 if accepted_answer else 0.50,
                            base_confidence=SOURCE_CONFIDENCE_BASE["stack_overflow"],
                        )],
                    )
        except Exception as e:
            logger.debug(f"Stack Overflow API search failed: {e}")
        
        # Fallback
        return Hypothesis(
            description=f"Stack Overflow: '{' '.join(tokens)}' — "
                        f"no results or API unavailable",
            proposed_fix=f"Search Stack Overflow manually for: {ctx.error_message[:80]}",
            confidence=SOURCE_CONFIDENCE_BASE["stack_overflow"] * 0.25,
            sources=[ResearchSource(
                source_type="stack_overflow",
                title=f"SO: {' '.join(tokens)}",
                summary=f"Stack Overflow search for: {ctx.error_message[:120]}",
                excerpt="API unavailable — try manual search",
                relevance=0.20,
                base_confidence=SOURCE_CONFIDENCE_BASE["stack_overflow"],
            )],
        )

    def _search_documentation(self, ctx: ErrorContext) -> Optional[Hypothesis]:
        """Search official documentation for the language/compiler."""
        docs = {
            "gcc": "https://gcc.gnu.org/onlinedocs/",
            "clang": "https://clang.llvm.org/docs/",
            "rustc": "https://doc.rust-lang.org/",
            "python": "https://docs.python.org/3/",
            "make": "https://www.gnu.org/software/make/manual/",
            "cmake": "https://cmake.org/documentation/",
        }

        compiler = ctx.compiler.lower()
        doc_url = None
        for key, url in docs.items():
            if key in compiler:
                doc_url = url
                break

        if doc_url:
            return Hypothesis(
                description=f"Documentation: {compiler} — check official docs for "
                           f"error: {ctx.error_message[:80]}",
                proposed_fix=f"Refer to {compiler} documentation: {doc_url}",
                confidence=SOURCE_CONFIDENCE_BASE["official_docs"] * 0.6,
                sources=[ResearchSource(
                    source_type="official_docs",
                    title=f"{compiler} Official Documentation",
                    summary=f"Search {compiler} docs for error pattern",
                    excerpt=f"Documentation URL: {doc_url}",
                    relevance=0.50,
                    base_confidence=SOURCE_CONFIDENCE_BASE["official_docs"],
                )],
            )

        return None

    def _generate_ai_hypothesis(self, ctx: ErrorContext) -> Optional[Hypothesis]:
        """
        Generate an AI-synthesized hypothesis using available LLM.

        Attempts to use the configured LLM provider to analyze the error.
        Falls back to structured placeholder if no LLM is available.
        The AI never fixes code — it only proposes hypotheses for validation.
        """
        try:
            from quimera.llm_config import LLMConfig
            llm = LLMConfig()
            
            prompt = (
                f"You are analyzing a compilation/build error in {ctx.language} "
                f"using {ctx.compiler}.\n\n"
                f"Error message: {ctx.error_message}\n"
                f"Error type: {ctx.error_type}\n"
                f"File: {ctx.file_path}\n"
                f"Code context (line {ctx.line_number}):\n{ctx.code_context or 'N/A'}\n\n"
                f"Based on this error, what are the most likely root causes? "
                f"Provide a concise hypothesis (1-2 sentences) about the probable cause "
                f"and a suggested direction for investigation. "
                f"Do NOT generate code patches — just the hypothesis."
            )
            
            response = llm.query(prompt)
            if response and len(response) > 10:
                return Hypothesis(
                    description=f"AI synthesis: {response[:200]}",
                    proposed_fix="AI hypothesis generated — validate in sandbox",
                    confidence=SOURCE_CONFIDENCE_BASE["ia_synthesis"] * 0.7,
                    sources=[ResearchSource(
                        source_type="ia_synthesis",
                        title="AI-Generated Hypothesis",
                        summary=response[:500],
                        excerpt=response[:300],
                        relevance=0.50,
                        base_confidence=SOURCE_CONFIDENCE_BASE["ia_synthesis"],
                    )],
                    requires_validation=True,
                )
        except Exception as e:
            logger.debug(f"AI hypothesis generation failed: {e}")
        
        # Fallback: structured hypothesis without LLM
        return Hypothesis(
            description=f"AI synthesis: unknown error pattern — "
                       f"'{ctx.error_message[:100]}' in {ctx.language} ({ctx.compiler})",
            proposed_fix="Run with LLM integration enabled for AI-powered analysis",
            confidence=SOURCE_CONFIDENCE_BASE["ia_synthesis"] * 0.3,
            sources=[ResearchSource(
                source_type="ia_synthesis",
                title="AI-Generated Hypothesis (fallback)",
                summary=f"Automatic hypothesis generation for: {ctx.error_message[:150]}",
                excerpt="LLM unavailable — structured fallback. Enable LLM for deeper analysis.",
                relevance=0.20,
                base_confidence=SOURCE_CONFIDENCE_BASE["ia_synthesis"],
            )],
            requires_validation=True,
        )

    # ── Integration with Pipeline ──────────────────────────────────

    def should_activate(self, error_context: ErrorContext) -> bool:
        """
        Determine if Knowledge Acquisition should activate.
        Only activates for UNKNOWN errors — KB handles known patterns.
        """
        # Check if KB has a direct match
        if self.kb:
            for vuln_name, pattern in self.kb.get_detection_patterns(error_context.language):
                if pattern and re.search(pattern, error_context.error_message, re.IGNORECASE):
                    return False  # KB has this, no need for acquisition

        # Activate if error has meaningful context
        return bool(error_context.error_message and len(error_context.error_message) > 10)

    def get_research_log(self) -> List[ResearchReport]:
        return self._research_log


# ── Convenience ───────────────────────────────────────────────────

def research_error(
    error_message: str,
    file_path: str = "",
    language: str = "",
    line_number: int = 0,
    surrounding_code: str = "",
    function_code: str = "",
    compiler: str = "",
    compiler_version: str = "",
    raw_output: str = "",
    search_web: bool = False,
) -> ResearchReport:
    """
    One-shot research for an unknown error.

    Returns a ResearchReport with hypotheses sorted by confidence.
    The caller should validate each hypothesis in sandbox before applying.
    """
    ctx = ErrorContext(
        error_message=error_message,
        error_type=_detect_error_type(error_message, raw_output),
        raw_output=raw_output,
        file_path=file_path,
        line_number=line_number,
        function_name=_extract_function_name(surrounding_code or function_code),
        surrounding_code=surrounding_code,
        function_code=function_code,
        language=language,
        compiler=compiler,
        compiler_version=compiler_version,
    )

    layer = KnowledgeAcquisitionLayer(search_web=search_web)
    return layer.research(ctx)


def _detect_error_type(message: str, raw: str) -> str:
    """Detect error type from message/raw output."""
    combined = (message + "\n" + raw).lower()
    if "undefined reference" in combined:
        return "linker"
    if "segmentation fault" in combined or "segfault" in combined:
        return "runtime_segfault"
    if "kernel panic" in combined:
        return "kernel_panic"
    if "error:" in combined:
        return "compilation"
    if any(w in combined for w in ["assertion", "assert", "test fail", "failed test"]):
        return "test_failure"
    if "exception" in combined or "traceback" in combined:
        return "runtime_exception"
    return "unknown"


def _extract_function_name(code: str) -> str:
    """Extract function name from code context."""
    if not code:
        return ""
    # Match: return_type function_name(args) {
    m = re.search(r'(?:^|\n)\s*(?:\w+\s+)+\*?(\w+)\s*\([^)]*\)\s*\{', code)
    if m:
        return m.group(1)
    return ""


# ═══════════════════════════════════════════════════════════════════
# Demo
# ═══════════════════════════════════════════════════════════════════

def demo():
    """Demonstrate Knowledge Acquisition researching an unknown error."""
    # Example: kernel compilation error
    ctx = ErrorContext(
        error_message="undefined reference to `of_property_read_u32_array'",
        error_type="linker",
        raw_output="drivers/of/base.c:(.text+0x1234): undefined reference to `of_property_read_u32_array'",
        file_path="drivers/net/foo.c",
        line_number=482,
        function_name="foo_probe",
        surrounding_code="""
        static int foo_probe(struct platform_device *pdev) {
            struct device_node *np = pdev->dev.of_node;
            u32 values[4];
            int ret;
            
            ret = of_property_read_u32_array(np, "foo,values", values, 4);
            if (ret) {
                dev_err(&pdev->dev, "failed to read values\\n");
                return ret;
            }
            return 0;
        }
        """,
        language="c",
        compiler="gcc",
        compiler_version="13.2.0",
        build_system="make",
        target_arch="arm64",
    )

    layer = KnowledgeAcquisitionLayer(search_web=False)
    report = layer.research(ctx)

    print(f"{'='*70}")
    print(f"Knowledge Acquisition Demo")
    print(f"{'='*70}")
    print(f"Error: {ctx.error_message}")
    print(f"Tokens: {ctx.error_tokens}")
    print(f"KB consulted: {report.kb_was_consulted}, KB had match: {report.kb_had_match}")
    print(f"\nHypotheses ({len(report.hypotheses)}):")
    for h in report.hypotheses:
        print(f"\n  [{h.confidence:.2f}] {h.description}")
        print(f"    Fix: {h.proposed_fix}")
        if h.sources:
            for s in h.sources:
                print(f"    📎 {s.source_type}: {s.title}")
    print(f"\nResearch time: {report.research_time_ms:.0f}ms")
    print(f"Sources consulted: {report.sources_consulted}")


if __name__ == "__main__":
    demo()
