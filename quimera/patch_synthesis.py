"""Patch Synthesis — generates fix candidates from findings."""
import re
from dataclasses import dataclass
from typing import List
from enum import Enum

class PVS(Enum):
    PASSED="passed"; COMPILE_FAILED="compile_failed"; TEST_FAILED="test_failed"
    REGRESSION="regression"; BENCHMARK_DEGRADED="benchmark_degraded"; NOT_ATTEMPTED="not_attempted"

@dataclass
class PatchCandidate:
    id: str; finding_id: str; description: str
    original_code: str; patched_code: str; diff: str
    confidence: float = 0.25
    validation_status: PVS = PVS.NOT_ATTEMPTED

class PatchSynthesizer:
    def synthesize(self, finding, source_code, source_path=""):
        # Accept both dict and DetectedIssue object
        if not isinstance(finding, dict):
            finding = {
                "cwe": getattr(finding, 'cwe_id', ''),
                "var": self._extract_var(getattr(finding, 'code_snippet', '') or 
                       getattr(finding, 'fix_pattern', '') or ''),
                "l": getattr(finding, 'line', 0),
            }
        cwe = finding.get("cwe",""); var = finding.get("var","ptr"); ln = finding.get("l",0)
        lines = source_code.splitlines()
        if ln < 1 or ln > len(lines): return []
        idx = ln - 1; orig = lines[idx]; pad = ' ' * (len(orig) - len(orig.lstrip()))
        if "416" in cwe: return self._uaf(lines, idx, var, orig, pad)
        if "476" in cwe: return self._null(lines, idx, var, orig, pad)
        if "190" in cwe: return self._ovf(lines, idx, orig, pad)
        if "120" in cwe: return self._bounds(lines, idx, orig, pad)
        if "367" in cwe: return self._toctou(lines, idx, orig, pad)
        if "839" in cwe: return self._signed(lines, idx, orig, pad)
        if "404" in cwe: return self._va_end(lines, idx, orig, pad)
        if "252" in cwe: return self._realloc(lines, idx, orig, pad)
        if "193" in cwe: return self._offby1(lines, idx, orig, pad)
        if "688" in cwe: return self._macro(lines, idx, orig, pad)
        return []
    
    def _mk(self, lines, idx, add, sid, conf=0.10):
        n = lines[:idx] + add + lines[idx+1:]
        d = '\n'.join(['- '+lines[idx].strip()[:80]] + ['+ '+l.strip()[:80] for l in add])
        return PatchCandidate(f"fix-{sid}", sid, add[0].strip()[:60], lines[idx], '\n'.join(n), d, conf)
    
    def _extract_var(self, text):
        """Extract variable name from code/text for patching."""
        import re
        m = re.search(r'(?:free|kfree)\s*\(\s*(\w+)', text)
        if m: return m.group(1)
        m = re.search(r'malloc\s*\([^)]*\)\s*;?\s*(\w+)', text)
        if m: return m.group(1)
        return 'ptr'

    def _uaf(self, lines, idx, var, orig, pad):
        cs = []
        if 'free(' in orig or 'kfree(' in orig:
            cs.append(self._mk(lines, idx, [orig, pad + f'{var} = NULL;'], "uaf-A", 0.90))
        return cs
    
    def _null(self, lines, idx, var, orig, pad):
        return [self._mk(lines,idx,[orig,pad+f'if(!{var}) return NULL;'],"null-A",0.88)]
    
    def _ovf(self, lines, idx, orig, pad):
        m = re.search(r'(\w+)\s*=\s*(\w+)\s*\*\s*(\w+)', orig)
        if m:
            a, b = m.group(2), m.group(3)
            return [self._mk(lines,idx,[pad+f'if({a}>{b} && {a}>SIZE_MAX/{b}) return NULL;',orig],"ovf",0.92)]
        return []
    
    def _bounds(self, lines, idx, orig, pad):
        m = re.search(r'memcpy\s*\(\s*(\w+)\s*,\s*(\w+)\s*,\s*(\w+)\s*\)', orig)
        if m:
            d, s, z = m.group(1), m.group(2), m.group(3)
            return [self._mk(lines,idx,[pad+f'if({z}<=sizeof({d})) memcpy({d},{s},{z});',pad+'else return -1;'],"bounds",0.82)]
        return []
    
    def _toctou(self, lines, idx, orig, pad):
        for i in range(idx, min(len(lines), idx+5)):
            if 'open(' in lines[i]:
                p = ' '*(len(lines[i])-len(lines[i].lstrip()))
                return [self._mk(lines,i,[p+'if (fd < 0) return -1;',p+'if (fstat(fd, &st) != 0) { close(fd); return -1; }'],"toctou",0.85)]
        return []
    
    def _signed(self, lines, idx, orig, pad): return [self._mk(lines,idx,[pad+'if (len == 0) return -1;',orig],"signed",0.88)]
    def _va_end(self, lines, idx, orig, pad):
        for i in range(idx, min(len(lines), idx+8)):
            if 'vprintf' in lines[i]:
                p = ' '*(len(lines[i])-len(lines[i].lstrip()))
                return [self._mk(lines,i,[lines[i],p+'va_end(args);'],"vaend",0.95)]
        return []
    def _realloc(self, lines, idx, orig, pad):
        for i in range(idx, min(len(lines), idx+5)):
            if 'realloc(' in lines[i]:
                p = ' '*(len(lines[i])-len(lines[i].lstrip()))
                return [self._mk(lines,i,[p+'int *tmp = realloc(buf, nsz * sizeof(int));',p+'if (!tmp) return buf;',p+'buf = tmp;'],"realloc",0.90)]
        return []
    def _offby1(self, lines, idx, orig, pad):
        for i in range(idx, min(len(lines), idx+5)):
            if 'v[' in lines[i] or 'vals[' in lines[i]:
                p = ' '*(len(lines[i])-len(lines[i].lstrip()))
                return [self._mk(lines,i,[p+'if (l->n >= MAX) return;',lines[i]],"offby1",0.92)]
        return []
    def _macro(self, lines, idx, orig, pad):
        for i in range(max(0, idx-1), min(len(lines), idx+3)):
            if '#define MAX' in lines[i]:
                return [self._mk(lines,i,['#define MAX(a,b) ({ typeof(a) _a=(a); typeof(b) _b=(b); _a>_b?_a:_b; })'],"macro",0.88)]
        return []
