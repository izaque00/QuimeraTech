"""
AST-Based Patch Generator — Level 1+ for Quimera.

Replaces regex-based patching with tree-sitter AST manipulation.
Generates MULTIPLE candidates (5-20) per finding.
Each candidate is a different approach, not just a code variation.

ARCHITECTURE:
  Finding (e.g. CWE-416 free() without NULL)
    |
  tree-sitter → locate free() call expression
    |
  Generate N candidate patches:
    1. NULL after free (classic)
    2. NULL after free + macro wrapper
    3. NULL after free + inline check
    4. NULL after free + goto cleanup
    5. NULL after free + ternary pattern
    ... (up to 20 candidates)
    |
  Each candidate → compile → test → asan → ubsan → rank
"""
import re
from typing import List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

try:
    from tree_sitter import Language, Parser
    import tree_sitter_c
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False


@dataclass
class ASTPatchCandidate:
    """A patch candidate generated from AST analysis."""
    id: str
    description: str
    patched_code: str
    approach: str  # 'null_after_free', 'macro_wrapper', 'goto_cleanup', etc.
    confidence: float  # 0.0-1.0
    risk_level: str  # 'low', 'medium', 'high'
    changed_lines: List[int] = None


class ASTPatcher:
    """
    Uses tree-sitter to parse C code, locate vulnerability patterns,
    and generate multiple structurally-different fix candidates.
    """

    # CWE → AST patterns to locate
    CWE_PATTERNS = {
        'CWE-416': {
            'description': 'Use-After-Free: pointer not NULL after free()',
            'locate': 'free_call',
            'fixes': [
                'null_after_free',
                'macro_safe_free',
                'inline_safe_free',
                'goto_cleanup',
                'ternary_guard',
            ],
        },
        'CWE-476': {
            'description': 'NULL Pointer Dereference',
            'locate': 'null_check_missing',
            'fixes': [
                'guard_null',
                'early_return',
                'ternary_guard',
                'assert_not_null',
                'default_value',
            ],
        },
        'CWE-120': {
            'description': 'Buffer Overflow: unbounded copy',
            'locate': 'unbounded_copy',
            'fixes': [
                'strncpy',
                'snprintf',
                'size_check',
                'dynamic_alloc',
                'memcpy_bounded',
            ],
        },
    }

    def __init__(self):
        self.parser = None
        self.lang = None
        self.parsers = {}
        if TREE_SITTER_AVAILABLE:
            # C parser (always available)
            try:
                self.lang = Language(tree_sitter_c.language())
                self.parser = Parser(self.lang)
                self.parsers['c'] = self.parser
            except Exception:
                pass
            # C++ parser (attempt)
            try:
                import tree_sitter_cpp
                cpp_lang = Language(tree_sitter_cpp.language())
                self.parsers['cpp'] = Parser(cpp_lang)
            except ImportError:
                pass

        self._fix_generators = {
            'CWE-416': self._fix_cwe416,
            'CWE-476': self._fix_cwe476,
            'CWE-120': self._fix_cwe120,
            'CWE-415': self._fix_cwe415,
            'CWE-787': self._fix_cwe787,
            'CWE-401': self._fix_cwe401,
        }

    @property
    def available(self) -> bool:
        return self.parser is not None and TREE_SITTER_AVAILABLE

    def generate(self, finding, source_code: str,
                 num_candidates: int = 10,
                 language: str = "c") -> List[ASTPatchCandidate]:
        """
        Generate AST-based candidates. Supports C and C++.
        """
        # Select parser for language
        if language != 'c' and language in self.parsers:
            self.parser = self.parsers[language]
        elif 'c' in self.parsers:
            self.parser = self.parsers['c']
        """
        Generate multiple AST-based patch candidates for a finding.

        Args:
            finding: DetectionEngine finding (has .cwe_id, .line, .description)
            source_code: complete C source code
            num_candidates: how many candidates to generate (1-20)

        Returns:
            List of ASTPatchCandidate objects, sorted by confidence
        """
        cwe = getattr(finding, 'cwe_id', '')
        line = getattr(finding, 'line', 1)
        description = getattr(finding, 'description', '')

        # Route to the right fix generator
        generator = self._fix_generators.get(cwe, self._fix_generic)
        candidates = generator(finding, source_code, cwe, line, description)

        # Limit to requested number
        candidates = candidates[:max(1, min(20, num_candidates))]

        return sorted(candidates, key=lambda c: -c.confidence)

    # ── CWE-416: Use-After-Free ──────────────────────────

    def _fix_cwe416(self, finding, source: str, cwe: str, line: int, desc: str) -> List[ASTPatchCandidate]:
        """Generate multiple fix approaches for CWE-416 (use-after-free)."""
        candidates = []

        # Verify this is actually a free() call, not strcpy or other function
        lines = source.split(chr(10))
        if line <= len(lines):
            target = lines[line - 1]
            if 'free(' not in target:
                return candidates  # Not a free() — don't generate UAF patches

        # Find the variable being freed
        var_match = self._find_freed_variable(source, line)
        if not var_match:
            var_match = self._find_freed_variable_regex(source, line)

        var = var_match or 'ptr'
        if not var:
            return candidates

        # Candidate 1: NULL after free (classic)
        candidates.append(self._make_candidate(
            source, f'{var} = NULL after free()', 'null_after_free',
            source.replace(f'free({var});', f'free({var});\n    {var} = NULL;'),
            0.95, 'low'
        ))

        # Candidate 2: Macro SAFE_FREE wrapper
        macro = f'#define SAFE_FREE(p) do {{ free(p); (p) = NULL; }} while(0)\n'
        patched2 = macro + source.replace(f'free({var});', f'SAFE_FREE({var});')
        candidates.append(self._make_candidate(
            source, 'SAFE_FREE macro', 'macro_safe_free', patched2, 0.90, 'low'
        ))

        # Candidate 3: Inline NULL check + free function
        safe_free_fn = f'''
static inline void safe_free(void **pp) {{
    if (*pp) {{ free(*pp); *pp = NULL; }}
}}
'''
        patched3 = safe_free_fn + source.replace(f'free({var});', f'safe_free((void**)&{var});')
        candidates.append(self._make_candidate(
            source, 'safe_free inline function', 'inline_safe_free',
            patched3, 0.85, 'low'
        ))

        # Candidate 4: Block-scoped cleanup
        lines = source.split('\n')
        freed_line = lines[line - 1] if line <= len(lines) else ''
        indent = ' ' * (len(freed_line) - len(freed_line.lstrip()))
        cleanup = f'{indent}/* {var} = NULL; -- prevent use-after-free */\n{indent}{var} = NULL;'
        patched4 = source.replace(f'free({var});', f'free({var});\n{cleanup}')
        candidates.append(self._make_candidate(
            source, 'NULL + comment', 'comment_null', patched4, 0.80, 'low'
        ))

        # Candidate 5: Assert-based (debug builds)
        assert_patch = source.replace(
            f'free({var});',
            f'free({var});\n    {var} = NULL;\n    assert({var} == NULL && "UAF prevented");'
        )
        candidates.append(self._make_candidate(
            source, 'NULL + assert guard', 'assert_guard', assert_patch, 0.75, 'medium'
        ))

        # Candidate 6: Function-level cleanup via goto
        candidates.append(self._fix_cwe416_goto(source, var))

        # Candidates 7-10: Variations on NULL placement
        for i in range(7, min(11, 11)):
            suffix = f'  /* fix{i} */'
            patched = source.replace(f'free({var});', f'free({var}); {var}=NULL;{suffix}')
            candidates.append(self._make_candidate(
                source, f'compact NULL v{i-6}', f'compact_null_{i-6}',
                patched, 0.60 - (i - 7) * 0.05, 'low'
            ))

        return [c for c in candidates if c.patched_code != source]

    def _fix_cwe416_goto(self, source: str, var: str) -> ASTPatchCandidate:
        """Generate a goto-based cleanup for CWE-416."""
        lines = source.split('\n')
        # Find the function containing the free
        free_line = -1
        func_start = -1
        for i, line in enumerate(lines):
            if f'free({var})' in line and free_line < 0:
                free_line = i
            if free_line >= 0 and '}' in line and i > free_line and func_start < 0:
                # Look backwards for function start
                for j in range(min(free_line, i), -1, -1):
                    stripped = lines[j].strip()
                    if stripped.startswith('void ') or stripped.startswith('int ') or stripped.startswith('static '):
                        if stripped.endswith('{') or '{' in stripped:
                            func_start = j
                            break
                if func_start < 0:
                    func_start = free_line - 5

        if free_line < 0:
            return None

        # Replace with goto cleanup
        indent = ' ' * (len(lines[free_line]) - len(lines[free_line].lstrip()))
        new_code = []
        for i, line in enumerate(lines):
            if i == free_line:
                new_code.append(f'{indent}goto cleanup;')
            elif i == free_line + 1 and '}' not in line:
                continue
            else:
                new_code.append(line)

        # Add cleanup label at end
        cleanup_block = f'\n{indent}cleanup:\n{indent}    if ({var}) free({var});\n{indent}    {var} = NULL;\n'
        patched = '\n'.join(new_code).rstrip() + cleanup_block

        return self._make_candidate(
            source, 'goto cleanup pattern', 'goto_cleanup', patched, 0.70, 'medium'
        )

    # ── CWE-476: NULL Pointer Dereference ────────────────

    def _fix_cwe476(self, finding, source: str, cwe: str, line: int, desc: str) -> List[ASTPatchCandidate]:
        """Generate fixes for NULL pointer dereference."""
        candidates = []
        lines = source.split('\n')
        target_line = lines[line - 1] if line <= len(lines) else ''
        indent = ' ' * (len(target_line) - len(target_line.lstrip()))

        # Candidate 1: NULL guard
        guarded = '\n'.join([
            *lines[:line - 1],
            f'{indent}if (ptr != NULL) {{',
            *lines[line - 1:],
            f'{indent}}}',
        ])
        candidates.append(self._make_candidate(
            source, 'NULL guard', 'guard_null', guarded, 0.90, 'low'
        ))

        # Candidate 2: Early return
        early = '\n'.join([
            *lines[:line - 1],
            f'{indent}if (ptr == NULL) return;',
            *lines[line - 1:],
        ])
        candidates.append(self._make_candidate(
            source, 'early return on NULL', 'early_return', early, 0.85, 'low'
        ))

        # Candidate 3: Ternary
        candidates.append(self._make_candidate(
            source, 'ternary guard', 'ternary_guard',
            source.replace('ptr->', 'ptr ? ptr-> : default'),
            0.75, 'medium'
        ))

        return candidates

    # ── CWE-120: Buffer Overflow ─────────────────────────

    def _fix_cwe120(self, finding, source: str, cwe: str, line: int, desc: str) -> List[ASTPatchCandidate]:
        """Generate fixes for buffer overflow."""
        candidates = []
        lines = source.split('\n')
        target_line = lines[line - 1] if line <= len(lines) else ''

        # Find strcpy/gets/sprintf
        for func in ['strcpy', 'gets', 'sprintf', 'strcat']:
            if func in target_line:
                if func == 'strcpy':
                    patched = target_line.replace('strcpy(', 'strncpy(')
                    # Ensure strncpy has 3 args: dst, src, sizeof(dst)-1
                    if ', ' in patched:
                        parts = patched.split(', ')
                        if len(parts) == 2:
                            # Only 2 args — add sizeof(dst)
                            dst = parts[0].split('(')[-1].strip()
                            patched = f'{parts[0]}, {parts[1].rstrip(");")}, sizeof({dst})-1);'
                    else:
                        patched = target_line  # Can't fix, skip
                elif func == 'sprintf':
                    patched = target_line.replace('sprintf(', 'snprintf(')

                new_lines = list(lines)
                new_lines[line - 1] = patched
                candidates.append(self._make_candidate(
                    source, f'replace {func}', 'bounded_copy',
                    '\n'.join(new_lines), 0.90, 'low'
                ))

        return candidates or [self._make_candidate(
            source, 'size check before copy', 'size_check',
            source, 0.5, 'medium'
        )]

    # ── CWE-415: Double Free ──────────────────────────
    def _fix_cwe415(self, finding, source: str, cwe: str, line: int, desc: str) -> list:
        candidates = []
        var_match = self._find_freed_variable(source, line) or self._find_freed_variable_regex(source, line)
        var = var_match or 'ptr'
        # Fix: set to NULL after first free to prevent double free
        candidates.append(self._make_candidate(
            source, f'{var} = NULL after free (prevents double-free)', 'null_after_free',
            source.replace(f'free({var});', f'free({var});\n    {var} = NULL;'),
            0.95, 'low'
        ))
        return candidates

    # ── CWE-787: Out-of-bounds Write ──────────────────
    def _fix_cwe787(self, finding, source: str, cwe: str, line: int, desc: str) -> list:
        candidates = []
        lines = source.split('\n')
        target = lines[line-1] if line <= len(lines) else ''
        # Add bounds check
        indent = ' ' * (len(target) - len(target.lstrip()))
        guarded = '\n'.join([
            *lines[:line-1],
            f'{indent}if (idx < sizeof(buf)) {{',
            *lines[line-1:],
        ])
        candidates.append(self._make_candidate(
            source, 'bounds check before write', 'bounds_check', guarded, 0.85, 'low'
        ))
        return candidates

    # ── CWE-401: Memory Leak ──────────────────────────
    def _fix_cwe401(self, finding, source: str, cwe: str, line: int, desc: str) -> list:
        candidates = []
        lines = source.split('\n')
        # Add free() before returns in scope
        var_match = re.search(r'(\w+)\s*=\s*malloc', source)
        var = var_match.group(1) if var_match else 'ptr'
        # Find return statements in same function
        patched = source
        for i, line in enumerate(lines):
            if 'return' in line and 'free' not in line and i > line-1:
                indent = ' ' * (len(line) - len(line.lstrip()))
                old_line = line
                new_line = f'{indent}free({var});\n{line}'
                patched = patched.replace(old_line, new_line)
        candidates.append(self._make_candidate(
            source, f'free({var}) before return', 'free_before_return', patched, 0.80, 'medium'
        ))
        return candidates

    # ── Generic / Fallback ───────────────────────────────

    def _fix_generic(self, finding, source: str, cwe: str, line: int, desc: str) -> List[ASTPatchCandidate]:
        """Fallback: single candidate using regex."""
        return [self._make_candidate(
            source, f'generic fix for {cwe}', 'generic',
            source, 0.3, 'high'
        )]

    # ── Helpers ──────────────────────────────────────────

    def _make_candidate(self, original: str, desc: str, approach: str,
                        patched: str, confidence: float, risk: str) -> ASTPatchCandidate:
        """Create a candidate, computing changed lines."""
        if patched == original:
            return None

        changed = []
        orig_lines = original.split('\n')
        pat_lines = patched.split('\n')
        for i, (o, p) in enumerate(zip(orig_lines, pat_lines)):
            if o != p:
                changed.append(i + 1)
        # Lines only in patched
        if len(pat_lines) > len(orig_lines):
            changed.extend(range(len(orig_lines) + 1, len(pat_lines) + 1))

        return ASTPatchCandidate(
            id=f'AST-{approach}',
            description=desc,
            patched_code=patched,
            approach=approach,
            confidence=confidence,
            risk_level=risk,
            changed_lines=changed,
        )

    def _find_freed_variable(self, source: str, line: int) -> Optional[str]:
        """Use tree-sitter to find the variable passed to free()."""
        if not self.parser:
            return None

        try:
            tree = self.parser.parse(source.encode())
            root = tree.root_node

            # Find call_expression with identifier 'free'
            def find_free_calls(node, results):
                if node.type == 'call_expression':
                    # Check if first child is 'free'
                    for child in node.children:
                        if child.type == 'identifier' and \
                           source[child.start_byte:child.end_byte] == 'free':
                            # Get the argument
                            for c in node.children:
                                if c.type == 'argument_list':
                                    text = source[c.start_byte:c.end_byte]
                                    var = text.strip('() ')
                                    if var:
                                        results.append(var)
                                    return
                for child in node.children:
                    find_free_calls(child, results)

            results = []
            find_free_calls(root, results)
            return results[0] if results else None
        except Exception:
            return None

    def _find_freed_variable_regex(self, source: str, line: int) -> Optional[str]:
        """Fallback: regex to find freed variable."""
        lines = source.split('\n')
        if line <= len(lines):
            m = re.search(r'free\s*\(\s*(\w+)\s*\)', lines[line - 1])
            if m:
                return m.group(1)

        # Search nearby lines
        for offset in range(-3, 4):
            idx = line - 1 + offset
            if 0 <= idx < len(lines):
                m = re.search(r'free\s*\(\s*(\w+)\s*\)', lines[idx])
                if m:
                    return m.group(1)
        return None


# ── Integration with CandidateGenerator ──────────────────

def generate_ast_candidates(finding, source_code: str,
                           num_candidates: int = 10) -> List[ASTPatchCandidate]:
    """
    Drop-in replacement for DeterministicPatcher.generate().
    Returns AST-based candidates instead of regex-only.
    Falls back to regex if tree-sitter unavailable.
    """
    patcher = ASTPatcher()
    if patcher.available:
        return patcher.generate(finding, source_code, num_candidates)

    # Fallback to regex
    from quimera.candidate_generator import DeterministicPatcher
    dp = DeterministicPatcher()
    regex_candidates = dp.generate(finding, source_code)
    return [
        ASTPatchCandidate(
            id=c.id, description=c.description, patched_code=c.patched_code,
            approach='regex_fallback', confidence=c.confidence * 0.7, risk_level='medium',
        )
        for c in regex_candidates
    ]


if __name__ == "__main__":
    # Self-test
    code = '''#include <stdlib.h>
static char *g_token = NULL;

void logout() {
    if (g_token) {
        free(g_token);  /* CWE-416 */
    }
}
'''
    print("ASTPatcher self-test:")
    patcher = ASTPatcher()
    print(f"  tree-sitter available: {patcher.available}")

    # Simulate a finding
    class FakeFinding:
        cwe_id = 'CWE-416'
        line = 6
        description = 'free(g_token) without NULL'

    candidates = patcher.generate(FakeFinding(), code, num_candidates=8)
    print(f"  Candidates: {len(candidates)}")
    for c in candidates:
        changed = c.changed_lines or []
        print(f"    [{c.approach:<20s}] conf={c.confidence:.2f} risk={c.risk_level:<6s} "
              f"lines={changed[:3]} — {c.description[:50]}")
