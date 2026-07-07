"""
TypeContextExtractor — Extrai tamanhos de buffer, structs e defines para injeção no prompt LLM.
Elimina falsos positivos como memcpy(dst_mac, frame, 6) onde dst_mac[6] = 6 bytes.
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class BufferInfo:
    name: str
    size_bytes: int
    element_type: str
    source: str
    line: int
    scope: str


@dataclass
class TypeContext:
    buffers: List[BufferInfo] = field(default_factory=list)
    structs: Dict[str, Dict[str, int]] = field(default_factory=dict)
    typedefs: Dict[str, str] = field(default_factory=dict)
    defines: Dict[str, int] = field(default_factory=dict)


def extract_type_context(code: str) -> TypeContext:
    ctx = TypeContext()
    lines = code.split('\n')
    basic_sizes = {'char': 1, 'unsigned char': 1, 'uint8_t': 1, 'int8_t': 1,
                   'short': 2, 'uint16_t': 2, 'int16_t': 2,
                   'int': 4, 'unsigned': 4, 'uint32_t': 4, 'int32_t': 4,
                   'long': 8, 'uint64_t': 8, 'int64_t': 8, 'size_t': 8,
                   'void*': 8, 'float': 4, 'double': 8}

    def resolve_size(expr: str) -> int:
        expr = expr.strip()
        m = re.match(r'sizeof\s*\(\s*(\w+)\s*\)', expr)
        if m:
            tn = m.group(1)
            real = ctx.typedefs.get(tn, tn)
            if real in ctx.structs:
                return sum(v for v in ctx.structs[real].values() if v > 0)
            return basic_sizes.get(real, -1)
        try: return int(expr)
        except ValueError: pass
        if expr in ctx.defines: return ctx.defines[expr]
        m = re.match(r'(\w+)\s*\*\s*sizeof\s*\(\s*(\w+)\s*\)', expr)
        if m:
            cnt = ctx.defines.get(m.group(1), -1)
            esz = resolve_size(f'sizeof({m.group(2)})')
            return cnt * esz if cnt > 0 and esz > 0 else -1
        return -1

    # ── #define constants ──
    for line in lines:
        m = re.match(r'#define\s+(\w+)\s+(\d+)', line.strip())
        if m:
            try: ctx.defines[m.group(1)] = int(m.group(2))
            except ValueError: pass

    # ── typedefs + structs ──
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m = re.match(r'typedef\s+struct\s*\{', line)
        if m:
            fields = {}
            j = i + 1; depth = 1
            while j < len(lines) and depth > 0:
                fl = lines[j].strip()
                depth += fl.count('{') - fl.count('}')
                if depth > 0:
                    fa = re.match(r'\s*(\w+)\s+(\w+)\[(\d+)\]\s*;', fl)
                    if fa:
                        esz = resolve_size(f'sizeof({fa.group(1)})')
                        fields[fa.group(2)] = esz * int(fa.group(3)) if esz > 0 else int(fa.group(3))
                    else:
                        fm = re.match(r'\s*(\w+(?:\s*\*)?)\s+(\w+)\s*;', fl)
                        if fm: fields[fm.group(2)] = resolve_size(f'sizeof({fm.group(1).strip().rstrip("*").strip()})')
                j += 1
            if j < len(lines):
                tm = re.match(r'\}\s*(\w+)\s*;', lines[j].strip())
                if tm: ctx.structs[tm.group(1)] = fields
            i = j + 1; continue

        m = re.match(r'typedef\s+(\w+(?:\s*\*)?)\s+(\w+)\s*;', line)
        if m: ctx.typedefs[m.group(2)] = m.group(1).replace(' ', '')
        i += 1

    # ── Buffer declarations ──
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith('//') or s.startswith('/*') or s.startswith('#'): continue
        # Arrays: type name[N]
        m = re.search(r'\b(char|unsigned\s+char|uint8_t|int8_t)\s+(\w+)\[(\d+)\]', s)
        if m:
            ctx.buffers.append(BufferInfo(m.group(2), int(m.group(3)), m.group(1),
                                          f'array[{m.group(3)}]', i, 'local'))
        # malloc
        m = re.search(r'(\w+)\s*=\s*(?:\(\s*\w+\s*\*?\s*\))?\s*malloc\s*\(\s*([^)]+)\s*\)', s)
        if m:
            ctx.buffers.append(BufferInfo(m.group(1), resolve_size(m.group(2)), 'void*',
                                          f'malloc({m.group(2).strip()})', i, 'local'))
        # calloc
        m = re.search(r'(\w+)\s*=\s*(?:\(\s*\w+\s*\*?\s*\))?\s*calloc\s*\(\s*([^,]+)\s*,\s*([^)]+)\s*\)', s)
        if m:
            cnt = resolve_size(m.group(2)); esz = resolve_size(m.group(3))
            total = cnt * esz if cnt > 0 and esz > 0 else -1
            ctx.buffers.append(BufferInfo(m.group(1), total, 'void*',
                                          f'calloc({m.group(2).strip()},{m.group(3).strip()})', i, 'local'))
    return ctx


def generate_type_prompt_context(ctx: TypeContext, max_items: int = 15) -> str:
    parts = []
    if ctx.defines:
        parts.append("Buffer size constants: " +
                     ", ".join(f"{k}={v}" for k, v in list(ctx.defines.items())[:10]))
    if ctx.buffers:
        parts.append("\nKnown buffer allocations:")
        for b in ctx.buffers[:max_items]:
            sz = f"{b.size_bytes} bytes" if b.size_bytes > 0 else "unknown size"
            parts.append(f"  {b.name} = {b.source} ({sz}, line {b.line})")
    if ctx.structs:
        parts.append("\nStruct sizes:")
        for name, fields in list(ctx.structs.items())[:5]:
            total = sum(v for v in fields.values() if v > 0)
            parts.append(f"  {name}: ~{total} bytes ({len(fields)} fields)")
    return '\n'.join(parts)


def verify_finding(code: str, cwe: str, line: int, ctx: TypeContext) -> Tuple[bool, str, float]:
    lines = code.split('\n')
    if line < 1 or line > len(lines):
        return False, "line out of range", 0.0
    target = lines[line - 1].strip()
    ctx_window = '\n'.join(lines[max(0, line - 6):min(len(lines), line + 3)])

    if cwe == 'CWE-476':
        if re.search(r'if\s*\(\s*!?\s*\w+\s*\)\s*return', ctx_window, re.I):
            return False, "NULL guard found nearby", 0.1
        if '->' not in target and '.' not in target:
            return False, "no dereference on this line", 0.0
        return True, "no NULL guard found", 0.85

    if cwe in ('CWE-121', 'CWE-787'):
        m = re.search(r'(?:memcpy|strcpy|sprintf)\s*\(\s*(\w+)', target)
        if not m: return True, "buffer operation found", 0.7
        dest = m.group(1)
        buf = next((b for b in ctx.buffers if b.name == dest), None)
        if buf and buf.size_bytes > 0:
            sz = re.search(r'memcpy\s*\([^,]+,\s*[^,]+,\s*(\d+)\s*\)', target)
            if sz and int(sz.group(1)) <= buf.size_bytes:
                return False, f"copy size <= buffer size ({buf.size_bytes})", 0.0
        return True, "potential overflow", 0.8

    if cwe == 'CWE-416':
        has_free = any(re.search(r'free\s*\(', lines[l].strip())
                       for l in range(max(0, line - 15), line))
        has_access = '->' in target or '[' in target
        if has_free and has_access:
            return True, "access after free confirmed", 0.9
        return False, "no clear UAF pattern", 0.2

    if cwe == 'CWE-401':
        fs = max(0, line - 30); fe = min(len(lines), line + 30)
        has_malloc = any(re.search(r'malloc|calloc', lines[l].strip()) for l in range(fs, fe))
        rets = [l for l in range(fs, fe) if re.search(r'\breturn\b', lines[l].strip())]
        all_freed = all('free' in '\n'.join(lines[max(fs, r-3):r]) for r in rets)
        if has_malloc and not all_freed:
            return True, "return path without free", 0.85
        return True, "possible leak", 0.6

    if cwe == 'CWE-190':
        if re.search(r'\w+\s*=\s*\w+\s*[\+]\s*\w+', target) and 'if' not in ctx_window:
            return True, "addition without bounds check", 0.75
        return True, "potential overflow", 0.6

    return True, "unverified", 0.5


print("type_context.py loaded")
