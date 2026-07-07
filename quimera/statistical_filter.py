"""
Statistical False Positive Classifier — ML-based post-filter for CWE-476.

Problem: After rule-based AEGIS filter, ~127 CWE-476 remain in libtiff.
         Most are function pointers or struct member access in validated contexts.

Solution: Simple statistical classifier using code features.
          No external ML dependencies — just statistics and heuristics.
          
Features per CWE-476 finding:
  1. Is it inside a loop? (for/while/do)
  2. Is the variable a function parameter?
  3. Is the dereference inside an if-block?
  4. Distance from function entry (lines)
  5. Is the line a function signature/prototype?
  6. How many times is this var guarded in the function?
  7. Is the deref on the LEFT side of = (write, not read)?
  8. Is there an error check (if err return) in the 5 lines above?
  9. Is the variable a struct member access (var->field)?
  10. Is the variable inside a goto error-handling block?

Scoring: each feature votes FP or REAL. Weighted sum determines final classification.
"""

import re
from typing import List, Tuple, Dict


class StatisticalFilter:
    """
    Lightweight statistical classifier for CWE-476 false positives.
    
    Usage:
        sf = StatisticalFilter()
        real, fp = sf.classify(code, remaining_cwe476_issues)
    """

    def __init__(self, threshold: float = 0.4):
        self.threshold = threshold
        self.feature_weights = {
            # Feature name → (weight, is_FP_vote)
            # Weight > 0 means HIGHER weight → more likely FP
            # Weight < 0 means LOWER weight → more likely REAL
            'is_loop':              (0.15, True),   # In loop → FP
            'is_param':             (0.12, True),   # Function param → FP
            'inside_if_block':      (-0.20, True),  # Inside if → REAL (already guarded context)
            'dist_from_entry':      (0.00, True),   # Far from entry → slight FP
            'is_signature':         (0.30, True),   # Function signature → FP
            'guard_count_high':     (-0.25, True),  # Many guards → REAL
            'is_write_deref':       (0.10, True),   # *ptr = x → FP (write, not read)
            'has_error_check':      (-0.15, True),  # Error check above → REAL path
            'is_struct_access':     (0.08, True),   # var->field → FP
            'in_goto_error_block':  (0.05, True),   # Error handling block → FP
            'just_assigned':        (0.08, True),   # var = func() right before → FP
            'in_switch_case':       (0.10, True),   # switch case block → FP
        }

    def classify(self, code: str, issues: List) -> Tuple[List, List]:
        """
        Split issues into real and false positive.
        Returns (real_issues, fp_issues).
        """
        lines = code.split('\n')
        real_issues = []
        fp_issues = []

        for issue in issues:
            if not hasattr(issue, 'cwe_id') or issue.cwe_id != 'CWE-476':
                real_issues.append(issue)
                continue

            score = self._compute_score(issue, lines)
            if score >= self.threshold:
                fp_issues.append(issue)
            else:
                real_issues.append(issue)

        return real_issues, fp_issues

    def _compute_score(self, issue, lines: List[str]) -> float:
        """Compute FP probability score for a single issue."""
        line_idx = issue.line - 1
        features = self._extract_features(issue, lines, line_idx)

        score = 0.0
        for feat_name, feat_value in features.items():
            if feat_name in self.feature_weights:
                weight, is_fp = self.feature_weights[feat_name]
                if is_fp:
                    score += weight * feat_value
                else:
                    score += weight * (1 - feat_value)

        return max(0.0, min(1.0, score))

    def _extract_features(self, issue, lines: List[str], line_idx: int) -> Dict[str, float]:
        """Extract all features for a CWE-476 finding."""
        features = {}
        var = self._get_var(issue, lines[line_idx] if line_idx < len(lines) else "")

        # 1. Inside a loop?
        features['is_loop'] = 1.0 if self._in_loop(lines, line_idx) else 0.0

        # 2. Is it a function parameter?
        features['is_param'] = 1.0 if self._is_param(lines, line_idx, var) else 0.0

        # 3. Inside if-block?
        features['inside_if_block'] = 1.0 if self._inside_if(lines, line_idx) else 0.0

        # 4. Distance from function entry
        features['dist_from_entry'] = min(1.0, self._dist_from_entry(lines, line_idx) / 100.0)

        # 5. Is it a function signature?
        features['is_signature'] = 1.0 if self._is_signature(lines, line_idx) else 0.0

        # 6. Guard count
        guard_count = self._count_guards(lines, var)
        features['guard_count_high'] = min(1.0, guard_count / 3.0)

        # 7. Write deref (*ptr = x)?
        features['is_write_deref'] = 1.0 if self._is_write_deref(lines, line_idx) else 0.0

        # 8. Error check before?
        features['has_error_check'] = 1.0 if self._has_error_check(lines, line_idx) else 0.0

        # 9. Struct member access?
        features['is_struct_access'] = 1.0 if self._is_struct_access(lines, line_idx) else 0.0

        # 10. In goto error block?
        features['in_goto_error_block'] = 1.0 if self._in_goto_error(lines, line_idx) else 0.0

        # 11. Just assigned?
        features['just_assigned'] = 1.0 if self._just_assigned(lines, line_idx, var) else 0.0

        # 12. In switch case?
        features['in_switch_case'] = 1.0 if self._in_switch(lines, line_idx) else 0.0

        return features

    # ── Feature extractors ──

    def _get_var(self, issue, line: str) -> str:
        if hasattr(issue, 'variable'):
            return issue.variable
        m = re.search(r'\*(\w+)|(\w+)\s*->|(\w+)\s*\[', line)
        if m:
            return m.group(1) or m.group(2) or m.group(3)
        return ""

    def _in_loop(self, lines: List[str], line_idx: int) -> bool:
        brace_depth = 0
        for i in range(line_idx, max(0, line_idx - 30), -1):
            if i >= len(lines):
                continue
            line = lines[i]
            brace_depth += line.count('{') - line.count('}')
            if re.search(r'\b(?:for|while|do)\b', line) and brace_depth <= 2:
                return True
        return False

    def _is_param(self, lines: List[str], line_idx: int, var: str) -> bool:
        # Find enclosing function
        for i in range(line_idx, max(0, line_idx - 50), -1):
            if i >= len(lines):
                continue
            line = lines[i].strip()
            m = re.match(r'(?:static\s+)?(?:inline\s+)?[\w\*\s]+\s+(\w+)\s*\(([^)]*)\)', line)
            if m:
                params = m.group(2)
                if re.search(rf'\b{re.escape(var)}\b', params):
                    return True
                break
        return False

    def _inside_if(self, lines: List[str], line_idx: int) -> bool:
        brace_depth = 0
        for i in range(line_idx, max(0, line_idx - 10), -1):
            if i >= len(lines):
                continue
            line = lines[i].strip()
            brace_depth += line.count('{') - line.count('}')
            if re.search(r'\bif\s*\(', line) and brace_depth <= 1:
                return True
        return False

    def _dist_from_entry(self, lines: List[str], line_idx: int) -> int:
        for i in range(line_idx, max(0, line_idx - 100), -1):
            if i >= len(lines):
                continue
            if re.match(r'^(?:static\s+)?(?:inline\s+)?[\w\*\s]+\s+\w+\s*\(', lines[i].strip()):
                return line_idx - i
        return 0

    def _is_signature(self, lines: List[str], line_idx: int) -> bool:
        if line_idx >= len(lines):
            return False
        line = lines[line_idx].strip()
        return line.endswith(';') and '(' in line and '{' not in line

    def _count_guards(self, lines: List[str], var: str) -> int:
        if not var:
            return 0
        count = 0
        for line in lines:
            if re.search(rf'if\s*\(\s*{re.escape(var)}\s*[\)!]', line):
                count += 1
        return count

    def _is_write_deref(self, lines: List[str], line_idx: int) -> bool:
        if line_idx >= len(lines):
            return False
        return bool(re.search(r'^\s*\*\w+\s*=', lines[line_idx].strip()))

    def _has_error_check(self, lines: List[str], line_idx: int) -> bool:
        for i in range(max(0, line_idx - 5), line_idx):
            if i >= len(lines):
                continue
            if re.search(r'if\s*\(.*\)\s*(?:return|goto|break)', lines[i].strip()):
                return True
        return False

    def _is_struct_access(self, lines: List[str], line_idx: int) -> bool:
        if line_idx >= len(lines):
            return False
        return '->' in lines[line_idx]

    def _in_goto_error(self, lines: List[str], line_idx: int) -> bool:
        for i in range(line_idx, max(0, line_idx - 20), -1):
            if i >= len(lines):
                continue
            if re.match(r'^\w+error\s*:', lines[i].strip()):
                return True
            if re.match(r'^\w+_err\s*:', lines[i].strip()):
                return True
            if re.match(r'^out\s*:', lines[i].strip()):
                return True
        return False

    def _just_assigned(self, lines: List[str], line_idx: int, var: str) -> bool:
        if not var:
            return False
        for i in range(max(0, line_idx - 2), line_idx):
            if i >= len(lines):
                continue
            if re.search(rf'{re.escape(var)}\s*=\s*\w+\s*\(', lines[i]):
                return True
        return False

    def _in_switch(self, lines: List[str], line_idx: int) -> bool:
        brace_depth = 0
        for i in range(line_idx, max(0, line_idx - 30), -1):
            if i >= len(lines):
                continue
            line = lines[i]
            brace_depth += line.count('{') - line.count('}')
            if re.search(r'\bswitch\s*\(', line) and brace_depth <= 1:
                return True
        return False
