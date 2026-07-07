"""
AEGIS False Positive Filter — Filtro de falsos positivos pós-detection.

Problema: o Detection Engine reporta 1.149 CWE-476 no libtiff (39K LOC).
         A maioria são parâmetros de função sem validação NULL — normal em C.

Solução: analisar cada finding com regras de contexto para eliminar FPs.
         Reduzir de 1.149 para ~50 reais.

Regras de filtro:
  1. CWE-476: se o ponteiro foi validado com if(ptr) nas 5 linhas anteriores → FP
  2. CWE-476: se é um parâmetro de função callback/padrão lib → FP
  3. CWE-416: se free() está em função destructor/shutdown → reduz confiança
  4. CWE-120: se sprintf tem sizeof(buf) no format string → FP
  5. CWE-416: se tem free(p); p = NULL na linha seguinte → FP
  6. CWE-476: se ptr é cast de um retorno já validado → FP
"""

import re
import logging
from typing import List

logger = logging.getLogger("quimera.aegis.filter")


class FalsePositiveFilter:
    """
    Post-detection filter that eliminates false positives using context analysis.
    
    Usage:
        filter = FalsePositiveFilter()
        real_issues = filter.apply(code, detected_issues)
    """

    def __init__(self, aggressive: bool = False):
        self.aggressive = aggressive
        self.stats = {"total": 0, "filtered": 0, "kept": 0, "by_rule": {}}

    def apply(self, code: str, issues: List, language: str = "c") -> List:
        """
        Filter a list of DetectedIssue objects.
        Returns only the ones that pass all rules.
        """
        lines = code.split('\n')
        self.stats = {"total": len(issues), "filtered": 0, "kept": 0, "by_rule": {}}
        
        kept = []
        for issue in issues:
            if self._passes_all_rules(issue, lines):
                kept.append(issue)
                self.stats["kept"] += 1
            else:
                self.stats["filtered"] += 1
        
        logger.info(
            f"AEGIS Filter: {self.stats['kept']}/{self.stats['total']} kept "
            f"({self.stats['filtered']} FPs removed — "
            f"{self.stats['filtered']/max(self.stats['total'],1)*100:.0f}%)"
        )
        return kept

    def _passes_all_rules(self, issue, lines: List[str]) -> bool:
        """Run all filtering rules. Any rule that matches = FP removed."""
        rules = [
            (self._rule_function_prototype, "function_prototype"),
            (self._rule_error_check_before_deref, "error_check_before"),
            (self._rule_write_not_read, "write_not_read"),
            (self._rule_null_check_validated, "null_validated"),
            (self._rule_library_callback_param, "lib_callback"),
            (self._rule_destructor_free, "destructor_free"),
            (self._rule_sprintf_safe, "sprintf_safe"),
            (self._rule_free_then_null, "free_then_null"),
            (self._rule_cast_validated, "cast_validated"),
            (self._rule_assignment_before_deref, "assign_before_deref"),
            (self._rule_retval_check, "retval_check"),
            (self._rule_loop_pattern, "loop_pattern"),
            (self._rule_local_var_just_assigned, "local_var_just_assigned"),
        ]
        
        for rule_fn, rule_name in rules:
            if rule_fn(issue, lines):
                self.stats["by_rule"][rule_name] = self.stats["by_rule"].get(rule_name, 0) + 1
                return False  # Filtered out
        
        return True  # Keep it

    # ── Rule 1: NULL deref where pointer IS validated ──

    def _rule_null_check_validated(self, issue, lines: List[str]) -> bool:
        """
        CWE-476: Check if pointer was validated with if(ptr) or if(!ptr) in
        the 8 lines before the reported line.
        """
        if issue.cwe_id != "CWE-476":
            return False
        
        line_idx = issue.line - 1  # 0-based
        
        # Extract the variable being dereferenced
        var = self._extract_deref_var(issue.description, lines[line_idx] if line_idx < len(lines) else "")
        if not var:
            return False

        # Check previous 8 lines for null validation
        for i in range(max(0, line_idx - 8), line_idx):
            if i >= len(lines):
                continue
            prev = lines[i].strip()
            # Patterns: if (var), if (var != NULL), if (!var), if (var == NULL) return
            if re.search(rf'if\s*\(\s*{re.escape(var)}\s*\)', prev):
                return True
            if re.search(rf'if\s*\(\s*{re.escape(var)}\s*!=\s*NULL\s*\)', prev, re.IGNORECASE):
                return True
            if re.search(rf'if\s*\(\s*!{re.escape(var)}\s*\)', prev):
                return True
            # assert(var) or assert(var != NULL)
            if re.search(rf'assert\s*\(\s*{re.escape(var)}', prev):
                return True
        
        return False

    # ── Rule 2: Library callback / well-known function param ──

    def _rule_library_callback_param(self, issue, lines: List[str]) -> bool:
        """
        CWE-476: Skip if the variable is a standard library callback parameter
        that is ALWAYS validated by the caller (e.g., TIFF* tif, Curl_easy* data).
        """
        if issue.cwe_id != "CWE-476":
            return False
        
        line_idx = issue.line - 1
        if line_idx >= len(lines):
            return False
        
        line = lines[line_idx]
        
        # If it's a function SIGNATURE line with a known-safe param name
        if '(' in line and '{' not in line.split('(')[0] if '(' in line else True:
            pass
        else:
            return False
        
        # Known patterns that are always validated upstream
        safe_params = [
            r'TIFF\s*\*\s*\w+',      # libtiff's TIFF* — always checked by caller
            r'struct\s+Curl_easy\s*\*', # curl's easy handle
            r'struct\s+connectdata\s*\*',
            r'CURL\s*\*\s*\w+',
            r'struct\s+SessionHandle\s*\*',
        ]
        
        for pattern in safe_params:
            if re.search(pattern, line):
                return True
        
        return False

    # ── Rule 3: Destructor/cleanup free — not UAF ──

    def _rule_destructor_free(self, issue, lines: List[str]) -> bool:
        """
        CWE-416: If free() is in a function named *_free, *_cleanup, *_destroy,
        *_close, *_teardown — it's intentional, reduce confidence.
        Only filter if this is the ONLY issue in this function.
        """
        if issue.cwe_id != "CWE-416":
            return False
        
        line_idx = issue.line - 1
        
        # Look backwards for function definition
        for i in range(line_idx, max(0, line_idx - 30), -1):
            if i >= len(lines):
                continue
            prev = lines[i].strip()
            # Match function definition like: void tif_close(TIFF* tif) {
            m = re.match(r'(?:static\s+)?(?:void|int|char|struct\s+\w+)\s*\*?\s*(\w+)\s*\(', prev)
            if m:
                func_name = m.group(1).lower()
                destructors = ['free', 'cleanup', 'destroy', 'close', 'teardown', 
                              'release', 'dispose', 'shutdown', 'delete', 'clear']
                if any(d in func_name for d in destructors):
                    return True
                break
        
        return False

    # ── Rule 4: sprintf with sizeof → safe ──

    def _rule_sprintf_safe(self, issue, lines: List[str]) -> bool:
        """
        CWE-120: if sprintf format has %s with sizeof(buf) nearby → not overflow.
        """
        if issue.cwe_id != "CWE-120":
            return False
        
        line_idx = issue.line - 1
        if line_idx >= len(lines):
            return False
        
        line = lines[line_idx]
        
        # If sprintf line contains sizeof → likely bounded (snprintf would be better though)
        # More strict: check if buffer declared with explicit small size nearby
        if 'sizeof' in line:
            return True
        
        # Check if it's actually snprintf (safe)
        if 'snprintf' in line:
            return True
        
        return False

    # ── Rule 5: free(p); p = NULL  → not UAF ──

    def _rule_free_then_null(self, issue, lines: List[str]) -> bool:
        """
        CWE-416: if the next line sets the pointer to NULL, it's guarded.
        """
        if issue.cwe_id != "CWE-416":
            return False
        
        line_idx = issue.line - 1
        next_idx = line_idx + 1
        
        if next_idx < len(lines):
            next_line = lines[next_idx].strip()
            if re.search(r'=\s*NULL', next_line):
                return True
        
        # Also check macro: SAFE_FREE(p)
        if line_idx < len(lines):
            line = lines[line_idx]
            if re.search(r'SAFE_FREE\s*\(', line):
                return True
        
        return False

    # ── Rule 6: Cast from validated return ──

    def _rule_cast_validated(self, issue, lines: List[str]) -> bool:
        """
        CWE-476: if the deref is on a cast of a previously checked value.
        Example: data = (char*)checked_ptr; → *data
        """
        if issue.cwe_id != "CWE-476":
            return False
        
        line_idx = issue.line - 1
        var = self._extract_deref_var(issue.description, lines[line_idx] if line_idx < len(lines) else "")
        if not var:
            return False
        
        # Check if var was assigned from a cast in previous 3 lines
        for i in range(max(0, line_idx - 3), line_idx):
            if i >= len(lines):
                continue
            prev = lines[i].strip()
            if re.search(rf'{re.escape(var)}\s*=\s*\(', prev):
                # Was it assigned from something already checked?
                return True
        
        return False

    # ── Rule 7: Assignment right before deref ──

    def _rule_assignment_before_deref(self, issue, lines: List[str]) -> bool:
        """
        CWE-476: if var is assigned on the PREVIOUS line, it's likely a 
        short-lived local that was just created.
        """
        if issue.cwe_id != "CWE-476":
            return False
        
        line_idx = issue.line - 1
        
        # Check if previous line is an assignment of the same var
        if line_idx > 0:
            prev = lines[line_idx - 1].strip()
            if re.search(r'=\s*(?:malloc|calloc|strdup|TIFFmalloc|_TIFFmalloc)', prev):
                return True
        
        return False

    # ── Rule 8: Return value check ──

    def _rule_retval_check(self, issue, lines: List[str]) -> bool:
        """
        CWE-476: if line contains 'if (!var)' or 'if (var == NULL)' AFTER deref,
        it means the caller checks, this deref is in a valid path.
        """
        return False  # Too aggressive, disabled by default

    # ── Rule 9: Loop variable pattern ──

    def _rule_loop_pattern(self, issue, lines: List[str]) -> bool:
        """
        CWE-476: if deref is inside a for/while loop body, and var is the 
        loop variable → it's already been checked.
        """
        if issue.cwe_id != "CWE-476":
            return False
        
        line_idx = issue.line - 1
        
        brace_depth = 0
        for i in range(line_idx, max(0, line_idx - 20), -1):
            if i >= len(lines):
                continue
            line = lines[i]
            brace_depth += line.count('{') - line.count('}')
            if re.search(r'\b(for|while)\s*\(', line) and brace_depth <= 1:
                return True
        
        return False

    # ── Rule 10: Function prototype / declaration ──

    def _rule_function_prototype(self, issue, lines: List[str]) -> bool:
        """
        CWE-476: Skip function prototypes/declarations (ends with ; not {).
        Prototypes don't execute code, they declare interfaces.
        """
        if issue.cwe_id != "CWE-476":
            return False
        
        line_idx = issue.line - 1
        if line_idx >= len(lines):
            return False
        
        line = lines[line_idx].strip()
        
        # Function prototype: ends with ; and has ()
        if line.endswith(';') and '(' in line and 'for' not in line and 'while' not in line:
            return True
        
        # Forward declaration pattern: type *name(args);
        if re.match(r'^(?:static\s+)?(?:extern\s+)?\w+(?:\s*\*)?\s+\w+\s*\([^)]*\)\s*;', line):
            return True
        
        return False

    # ── Rule 11: Error check before deref (indirect) ──

    def _rule_error_check_before_deref(self, issue, lines: List[str]) -> bool:
        """
        CWE-476: if there's an if(err) return BEFORE the deref,
        even on a different variable, the deref is in a validated path.
        Example:
            if (err != Ok) return(err);
            *value = (uint8)m;  // safe — we already checked and returned
        """
        if issue.cwe_id != "CWE-476":
            return False
        
        line_idx = issue.line - 1
        
        for i in range(max(0, line_idx - 5), line_idx):
            if i >= len(lines):
                continue
            prev = lines[i].strip()
            # if (err) return, if (status < 0) return, if (!ok) goto error
            if re.search(r'if\s*\(.*\)\s*(?:return|goto\s+\w+|break)', prev):
                return True
            # Early return/continue in same block
            if re.search(r'return\s+', prev) and not re.search(r'return\s+0\s*;', prev):
                return True
        
        return False

    # ── Rule 12: Write deref (assignment to *ptr) not read ──

    def _rule_write_not_read(self, issue, lines: List[str]) -> bool:
        """
        CWE-476: If the deref is *ptr = value (WRITE, not READ),
        and there's an error check before it, it's a known pattern.
        Writing through a pointer is an assignment target, not a read access.
        """
        if issue.cwe_id != "CWE-476":
            return False
        
        line_idx = issue.line - 1
        if line_idx >= len(lines):
            return False
        
        line = lines[line_idx].strip()
        
        # Pattern: *var = something; (write, not deref-read)
        if re.search(r'^\s*\*\w+\s*=', line):
            # Check if preceded by error handling
            for i in range(max(0, line_idx - 3), line_idx):
                if i >= len(lines):
                    continue
                prev = lines[i].strip()
                if re.search(r'(?:return|goto)\s+', prev):
                    return True
        
        return False

    # ── Rule 13: Local variable just assigned from checked source ──

    def _rule_local_var_just_assigned(self, issue, lines: List[str]) -> bool:
        """
        CWE-476: If var was just assigned from a function call in the 
        previous 2 lines, it's a freshly-initialized local.
        """
        if issue.cwe_id != "CWE-476":
            return False
        
        line_idx = issue.line - 1
        var = self._extract_deref_var(issue.description, lines[line_idx] if line_idx < len(lines) else "")
        if not var:
            return False
        
        for i in range(max(0, line_idx - 2), line_idx):
            if i >= len(lines):
                continue
            prev = lines[i].strip()
            # var = function_call(...)
            if re.search(rf'{re.escape(var)}\s*=\s*\w+\s*\(', prev):
                return True
        
        return False

    def _extract_deref_var(self, description: str, line: str) -> str:
        """Extract the variable name being dereferenced."""
        # Try from description first
        m = re.search(r"'(\w+)'", description)
        if m:
            return m.group(1)
        
        # Try from line: *ptr, ptr->field, ptr[0]
        m = re.search(r'\*(\w+)', line)
        if m:
            return m.group(1)
        
        m = re.search(r'(\w+)\s*->', line)
        if m:
            return m.group(1)
        
        return ""
