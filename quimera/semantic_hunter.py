"""
Semantic Bug Hunter — LLM-powered detection for logical/semantic bugs.

Problema: O Detection Engine baseado em regex/AST/heurísticas pega
         bugs estruturais (double free, buffer overflow, UAF, NULL deref)
         mas NÃO pega bugs lógicos (race, overflow semântico, TOCTOU, etc).

Solução: Usar LLM para analisar SEMÂNTICA do código — não padrões.
         O LLM não busca por "malloc sem free" — ele PERGUNTA:
         "O que esse código está tentando fazer e onde pode dar errado?"

ARQUITETURA:
  1. Extrair funções do código via AST
  2. Para cada função, construir prompt analítico
  3. Enviar para LLM com foco em bugs LÓGICOS (não estruturais)
  4. LLM retorna findings com: tipo, linha, descrição, confiança
  5. Cross-reference com findings estruturais (evitar duplicatas)

FILOSOFIA:
  - LLM é usado APENAS para o que regex/AST não pega
  - Detection Engine cobre bugs estruturais (rápido, determinístico)
  - Semantic Hunter cobre bugs lógicos (mais lento, precisa de LLM)
  - Os dois se complementam — NENHUM substitui o outro
"""

import re
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger("quimera.semantic_hunter")


@dataclass
class SemanticFinding:
    """A logical/semantic bug found by LLM analysis."""
    cwe_id: str
    line: int
    description: str
    confidence: float  # 0.0-1.0
    code_context: str = ""
    fix_suggestion: str = ""
    category: str = ""  # race, overflow, logic, etc


@dataclass  
class SemanticFinding:
    """A logical/semantic bug found by LLM analysis."""
    cwe_id: str
    line: int
    description: str
    confidence: float  # 0.0-1.0
    code_context: str = ""
    fix_suggestion: str = ""
    category: str = ""  # race, overflow, logic, etc


class SemanticHunter:
    """
    LLM-powered detection of logical/semantic bugs.
    
    Integrates with llm_config.py to use YOUR existing API keys.
    Auto-detects best provider (free OpenRouter → paid OpenAI/Claude).
    Falls back to OfflineSemanticHunter if no LLM available.
    """

    STRUCTURAL_CWES = {
        'CWE-476', 'CWE-416', 'CWE-415', 'CWE-401', 'CWE-134', 'CWE-120',
    }

    def __init__(self, llm_config=None, use_llm: bool = True):
        """
        Args:
            llm_config: LLMConfig from llm_config.py (auto-detects your keys)
            use_llm: If True, try LLM first. Falls back to heuristics if no LLM.
        """
        self.use_llm = use_llm
        self._offline = OfflineSemanticHunter()
        self._structural_findings: List = []
        
        # Auto-detect LLM config from user's keys
        if llm_config:
            self._llm_config = llm_config
        else:
            try:
                from quimera.llm_config import LLMConfig
                self._llm_config = LLMConfig()
            except ImportError:
                self._llm_config = None
        
        # Check if we have a working provider
        self._provider = None
        if self._llm_config:
            self._provider = self._llm_config.get_best_provider()
            if self._provider:
                logger.info(f"SemanticHunter: using {self._provider.name} ({self._provider.model})")

    def set_structural_findings(self, findings: List):
        """Tell the hunter what the structural engine already found."""
        self._structural_findings = findings

    async def hunt(self, code: str, language: str = "c") -> List[SemanticFinding]:
        """
        Find logical/semantic bugs.
        Tries LLM first (using YOUR API keys via llm_config).
        Falls back to offline heuristics if no LLM available.
        """
        # Try LLM first
        if self.use_llm and self._provider:
            logger.info(f"SemanticHunter: using LLM ({self._provider.name})")
            try:
                llm_findings = await self._hunt_with_llm(code, language)
                if llm_findings:
                    logger.info(f"LLM found {len(llm_findings)} semantic bugs")
                    return llm_findings
            except Exception as e:
                logger.warning(f"LLM hunt failed, falling back to offline: {e}")
        
        # Fallback: offline heuristics
        logger.info("SemanticHunter: using offline heuristics")
        return self._offline.hunt(code, language)

    def hunt_sync(self, code: str, language: str = "c") -> List[SemanticFinding]:
        """Synchronous wrapper for hunt()."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.hunt(code, language))

    async def _hunt_with_llm(self, code: str, language: str) -> List[SemanticFinding]:
        """Use the actual LLM (via user's API keys) to find semantic bugs."""
        functions = self._extract_functions(code)
        if not functions:
            return []
        
        all_findings = []
        for func_name, func_code, start_line in functions:
            if len(func_code) < 20:
                continue
            
            prompt = self._build_prompt(func_name, func_code, start_line)
            response = await self._call_llm_with_config(prompt)
            if not response:
                continue
            
            findings = self._parse_llm_response(response, start_line)
            for f in findings:
                if not self._is_duplicate(f):
                    all_findings.append(f)
        
        return all_findings

    async def _call_llm_with_config(self, prompt: str) -> Optional[str]:
        """Call LLM using the auto-detected provider from user's config."""
        if not self._provider:
            return None
        
        return await self._call_llm(prompt)

    def _extract_functions(self, code: str) -> List[Tuple[str, str, int]]:
        """
        Extract function names, bodies, and line numbers from C code.
        Simple heuristic-based extraction — sufficient for LLM prompts.
        """
        lines = code.split('\n')
        functions = []
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Match function definition: type name(...) {
            func_match = re.match(
                r'^(?:static\s+)?(?:inline\s+)?(?:__\w+\s+)*'
                r'(?:void|int|char|long|short|float|double|ssize_t|size_t|'
                r'struct\s+\w+|unsigned\s+\w+)\s*[*\s]+'
                r'(\w+)\s*\([^)]*\)\s*\{?',
                line
            )
            
            if func_match and not line.startswith(('if', 'while', 'for', 'switch')):
                func_name = func_match.group(1)
                func_lines = [line]
                brace_count = line.count('{') - line.count('}')
                
                j = i + 1
                while j < len(lines) and brace_count > 0:
                    func_lines.append(lines[j])
                    brace_count += lines[j].count('{') - lines[j].count('}')
                    j += 1
                
                func_code = '\n'.join(func_lines)
                functions.append((func_name, func_code, i + 1))
                i = j
            else:
                i += 1
        
        return functions

    def _build_prompt(self, func_name: str, func_code: str, 
                      start_line: int) -> str:
        """
        Build a focused prompt that asks the LLM to find LOGICAL bugs only.
        Explicitly tell it to IGNORE structural issues.
        """
        return f"""Analyze this C function for LOGICAL and SEMANTIC bugs only.

IGNORE structural issues (these are handled by static analysis):
- NULL pointer checks (CWE-476)
- Simple buffer overflows from strcpy/sprintf (CWE-120)
- Format string vulnerabilities (CWE-134)
- Simple use-after-free patterns (CWE-416)
- Simple double-free patterns (CWE-415)

FOCUS ONLY on bugs that require understanding code INTENT:
- Race conditions (missing locks on shared data)
- TOCTOU (check-then-use with changing state)
- Double fetch vulnerabilities
- Integer overflow/underflow with security impact
- Logic errors (wrong conditions, off-by-one, inverted checks)
- Resource leaks in non-obvious paths
- Semantic errors (code does something different than intended)

CODE:
```c
{func_code}
```

Return ONLY a JSON array. Each finding with:
- "line": line number (relative to function start at line {start_line})
- "cwe": CWE ID (e.g., "CWE-362" for race, "CWE-190" for overflow)
- "description": what the bug is (one sentence)
- "confidence": 0.0-1.0 (how sure you are)
- "fix": one-line fix suggestion

Example:
[{{"line": 5, "cwe": "CWE-362", "description": "device_open_count incremented without locking — race condition on concurrent open", "confidence": 0.9, "fix": "Use atomic_inc(&device_open_count) or add mutex_lock"}}]

If NO logical bugs found, return empty array [].

JSON:"""

    async def _call_llm(self, prompt: str) -> Optional[str]:
        """Call LLM API using the configured provider from user's keys."""
        import aiohttp
        
        if not self._provider:
            return None
        
        headers = {
            "Content-Type": "application/json",
        }
        url = ""
        
        p = self._provider
        
        if p.provider == "openrouter":
            headers["Authorization"] = f"Bearer {p.api_key}"
            headers["HTTP-Referer"] = "https://quimera.dev"
            url = f"{p.api_base}/chat/completions"
        elif p.provider == "openai":
            headers["Authorization"] = f"Bearer {p.api_key}"
            url = "https://api.openai.com/v1/chat/completions"
        elif p.provider == "ollama":
            url = f"{p.api_base}/api/generate"
        else:
            return None
        
        payload = {
            "model": p.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": p.max_tokens,
            "temperature": p.temperature,
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, json=payload, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=p.timeout_seconds)
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.warning(f"LLM error {resp.status}: {text[:200]}")
                        return None
                    
                    data = await resp.json()
                    
                    if p.provider == "ollama":
                        return data.get("response", "")
                    
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "")
        except Exception as e:
            logger.warning(f"LLM call failed: {e}")
        
        return None

    def _parse_llm_response(self, response: str, start_line: int) -> List[SemanticFinding]:
        """Parse the JSON response from the LLM into SemanticFinding objects."""
        findings = []
        
        # Extract JSON array from response
        response = response.strip()
        
        # Find JSON array boundaries
        start = response.find('[')
        end = response.rfind(']')
        
        if start == -1 or end == -1:
            # Try to find at least one JSON object
            start = response.find('{')
            end = response.rfind('}')
            if start != -1 and end != -1:
                response = '[' + response[start:end+1] + ']'
            else:
                logger.debug(f"No JSON in LLM response: {response[:100]}")
                return []
        else:
            response = response[start:end+1]
        
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            logger.debug(f"Failed to parse JSON: {response[:200]}")
            return []
        
        if not isinstance(data, list):
            data = [data]
        
        for item in data:
            try:
                finding = SemanticFinding(
                    cwe_id=item.get("cwe", "CWE-000"),
                    line=int(item.get("line", 1)) + start_line - 1,
                    description=item.get("description", "")[:200],
                    confidence=float(item.get("confidence", 0.5)),
                    fix_suggestion=item.get("fix", ""),
                    category=self._classify_category(item.get("cwe", "")),
                )
                findings.append(finding)
            except (ValueError, TypeError) as e:
                logger.debug(f"Invalid finding: {e}")
        
        return findings

    def _is_duplicate(self, finding: SemanticFinding) -> bool:
        """Check if this finding is already covered by structural analysis."""
        # Check against known structural CWEs
        if finding.cwe_id in self.STRUCTURAL_CWES:
            return True
        
        # Check against actual structural findings (same line + similar)
        for sf in self._structural_findings:
            if hasattr(sf, 'line') and abs(sf.line - finding.line) <= 2:
                if hasattr(sf, 'cwe_id') and sf.cwe_id == finding.cwe_id:
                    return True
        
        return False

    def _classify_category(self, cwe_id: str) -> str:
        """Classify CWE into category for reporting."""
        cwe_map = {
            'CWE-362': 'race',
            'CWE-367': 'toctou',
            'CWE-190': 'overflow',
            'CWE-191': 'underflow',
            'CWE-682': 'logic',
            'CWE-667': 'locking',
            'CWE-820': 'locking',
            'CWE-1255': 'double_fetch',
            'CWE-404': 'resource_leak',
        }
        return cwe_map.get(cwe_id, 'logic')


class OfflineSemanticHunter:
    """
    Fallback: heuristic-based semantic bug detection WITHOUT LLM.
    
    Uses advanced heuristics and patterns that go beyond simple regex.
    Catches SOME logical bugs without requiring API calls.
    Good for: CI/CD, offline use, privacy-sensitive code.
    """

    def hunt(self, code: str, language: str = "c") -> List[SemanticFinding]:
        """Find potential logical bugs using heuristics only."""
        findings = []
        lines = code.split('\n')
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Race condition heuristics
            if self._is_race_indicator(stripped, code):
                findings.append(SemanticFinding(
                    cwe_id="CWE-362",
                    line=i,
                    description="Potential race condition: shared variable modified without visible synchronization",
                    confidence=0.4,
                    category="race",
                    fix_suggestion="Add mutex, spinlock, or atomic operation",
                ))
            
            # Integer overflow heuristics
            if self._is_overflow_risk(stripped, lines, i):
                findings.append(SemanticFinding(
                    cwe_id="CWE-190",
                    line=i,
                    description="Potential integer overflow: arithmetic operation without bounds check",
                    confidence=0.35,
                    category="overflow",
                    fix_suggestion="Add bounds check before arithmetic operation",
                ))
            
            # TOCTOU heuristics
            if self._is_toctou_pattern(lines, i):
                findings.append(SemanticFinding(
                    cwe_id="CWE-367",
                    line=i,
                    description="Potential TOCTOU: check followed by use with possible state change between",
                    confidence=0.3,
                    category="toctou",
                    fix_suggestion="Re-check condition after use, or hold lock during check+use",
                ))
        
        return findings

    def _is_race_indicator(self, line: str, full_code: str) -> bool:
        """Detect potential race conditions without LLM."""
        # Shared variable modification
        shared_mod = re.search(r'(\w+)\+\+|\+\+(\w+)|(\w+)\s*=\s*.*\1', line)
        if shared_mod:
            var = shared_mod.group(1) or shared_mod.group(2) or shared_mod.group(3)
            # Check if there's no lock/mutex/atomic in the file
            if not re.search(r'mutex|spinlock|atomic|semaphore|lock|rcu', 
                           full_code, re.IGNORECASE):
                return True
        
        return False

    def _is_overflow_risk(self, line: str, lines: List[str], lineno: int) -> bool:
        """Detect potential integer overflow without LLM."""
        # Arithmetic without bounds check
        if re.search(r'[\w\[\]]+\s*[\+\-\*]\s*[\w\[\]]+', line):
            # Check if there's a bounds check in the surrounding context
            context_start = max(0, lineno - 5)
            context = '\n'.join(lines[context_start:lineno+1])
            if not re.search(r'if\s*\(.*>|if\s*\(.*<|if\s*\(.*>=|if\s*\(.*<=|SIZE_MAX|INT_MAX|UINT_MAX', context):
                return True
        
        return False

    def _is_toctou_pattern(self, lines: List[str], lineno: int) -> bool:
        """Detect potential TOCTOU pattern without LLM."""
        if lineno >= len(lines):
            return False
        
        # Check followed by use
        line = lines[lineno - 1].strip()
        if re.search(r'if\s*\(.+\)', line):
            # Look ahead for use of same variable
            for j in range(lineno, min(lineno + 5, len(lines))):
                next_line = lines[j].strip()
                # Extract variable from check
                var_match = re.search(r'if\s*\(([^)]+)\)', line)
                if var_match and any(w in next_line for w in ['copy_to_user', 'copy_from_user', 'memcpy', 'strcpy', '=']):
                    return True
        
        return False
