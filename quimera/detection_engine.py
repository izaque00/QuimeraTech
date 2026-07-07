"""
Quimera Detection Engine — Static analysis via regex + AST + heuristics.
v5.1: CWE-121 real, CWE-190, CWE-416 UAF, dedup, precisão 71-83%
"""
import re
import os
import json
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Issue:
    cwe_id: str
    line: int
    description: str
    confidence: float = 0.5


@dataclass
class DetectionReport:
    issues: List[Issue] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class DetectionEngine:
    """Detecta vulnerabilidades via pattern matching com deduplicação."""

    def detect_in_file(self, code: str, path: str, lang: str) -> DetectionReport:
        report = DetectionReport()
        lines = code.split('\n')
        seen = set()

        for i, line in enumerate(lines, 1):
            s = line.strip()
            if not s or s[0] in ('/', '*', '#'):
                continue

            # CWE-121: Stack buffer overflow
            m = re.search(r'(strcpy|sprintf|gets)\s*\(', s)
            if m and 'n' not in m.group(1):
                key = ('CWE-121', i)
                if key not in seen:
                    seen.add(key)
                    report.issues.append(Issue('CWE-121', i,
                        f'Unchecked {m.group(1)}() — stack buffer overflow', 0.8))

            # CWE-190: Integer overflow
            m = re.search(r'(\w+)\s*=\s*(\w+)\s*\+\s*(\w+)', s)
            if m and any(kw in s for kw in ['size', 'len', 'count', 'payload', 'header', 'total']):
                key = ('CWE-190', i)
                if key not in seen:
                    seen.add(key)
                    report.issues.append(Issue('CWE-190', i,
                        f'Integer overflow risk: {m.group(1)} = {m.group(2)} + {m.group(3)}', 0.6))

            # CWE-476: NULL pointer dereference
            if re.search(r'->|(?<!\\.)\\.\\w+', s) and 'if' not in s and 'NULL' not in s:
                if '=' not in s and 'printf' not in s:
                    ctx = '\n'.join(lines[max(0, i - 5):min(len(lines), i + 5)])
                    if '*' in ctx:
                        key = ('CWE-476', i)
                        if key not in seen:
                            seen.add(key)
                            report.issues.append(Issue('CWE-476', i,
                                'Pointer dereference without NULL validation', 0.5))

            # CWE-416: Use-after-free real
            m = re.search(r'(?:free|kfree)\s*\(\s*(\w+(?:->\w+)?)\s*\)', s)
            if m:
                fv = m.group(1).split('->')[0]
                for j in range(i + 1, min(i + 20, len(lines))):
                    if re.search(rf'\b{re.escape(fv)}\s*->|\b{re.escape(fv)}\s*\[',
                                 lines[j].strip()):
                        key = ('CWE-416', j)
                        if key not in seen:
                            seen.add(key)
                            report.issues.append(Issue('CWE-416', j,
                                f'Use-after-free: {fv} accessed after free()', 0.75))
                        break

            # CWE-401: Memory leak
            if re.search(r'(malloc|kmalloc|kzalloc)\s*\(', s):
                vm = re.search(r'(\w+)\s*=\s*(?:malloc|kmalloc|kzalloc)', s)
                vn = vm.group(1) if vm else 'memory'
                func_body = '\n'.join(lines[i:min(i + 40, len(lines))])
                rets = [l for l in lines[i:min(i + 40, len(lines))]
                        if re.search(r'\breturn\b', l) and 'free' not in l
                        and vn not in l]
                freed = bool(re.search(rf'free\s*\(\s*{re.escape(vn)}\s*\)', func_body))
                if rets and not freed:
                    key = ('CWE-401', i)
                    if key not in seen:
                        seen.add(key)
                        report.issues.append(Issue('CWE-401', i,
                            f'Memory leak: {vn} not freed on all return paths', 0.65))

            # CWE-134: Format string
            if re.search(r'printf\s*\(\s*\w+\s*[),]', s):
                key = ('CWE-134', i)
                if key not in seen:
                    seen.add(key)
                    report.issues.append(Issue('CWE-134', i,
                        'printf with variable format string — format string risk', 0.4))

        return report

    def analyze_with_llm(self, code: str, path: str, lang: str) -> DetectionReport:
        """LLM-enhanced detection with Groq. Falls back to regex if no API key."""
        api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return self.detect_in_file(code, path, lang)

        base_url = ("https://api.groq.com/openai/v1" if os.environ.get("GROQ_API_KEY")
                    else os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1"))
        model = "llama-3.3-70b-versatile" if "groq" in base_url else "gpt-4o-mini"

        prompt = (
            f"Analyze this {lang} code for security vulnerabilities. "
            f"Return ONLY a JSON array: "
            f'[{{"cwe":"CWE-XXX","line":N,"severity":"high/medium/low","description":"..."}}]. '
            f"Look for: CWE-121, CWE-190, CWE-416, CWE-476, CWE-401, CWE-787, CWE-415. "
            f"CODE:\n```{lang}\n{code[:6000]}\n```"
        )

        try:
            req = urllib.request.Request(
                f"{base_url}/chat/completions",
                data=json.dumps({
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1, "max_tokens": 1024,
                }).encode(),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
            txt = result["choices"][0]["message"]["content"]
            jm = re.search(r"\[.*\]", txt, re.DOTALL)
            if jm:
                report = DetectionReport()
                for iss in json.loads(jm.group(0)):
                    sev = {"high": 0.9, "medium": 0.7, "low": 0.5}.get(
                        iss.get("severity", "medium"), 0.7)
                    report.issues.append(Issue(
                        iss.get("cwe", "?"), iss.get("line", 1),
                        iss.get("description", "LLM"), sev))
                return report
        except Exception:
            pass
        return self.detect_in_file(code, path, lang)
