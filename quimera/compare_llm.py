"""Comparação Regex vs LLM — mostra precisão de cada modo."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if len(sys.argv) > 1:
    code = open(sys.argv[1]).read()
else:
    code = open("/tmp/net_driver.c").read() if os.path.exists("/tmp/net_driver.c") else (
        '#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n'
        'int main(void) {\n  char buf[8];\n  strcpy(buf, "overflow!");\n'
        '  int *p = NULL; *p = 42;\n  return 0;\n}\n')

from quimera.detection_engine import DetectionEngine
det = DetectionEngine()

has_key = bool(os.environ.get("GROQ_API_KEY"))
print("=" * 60)
print(f"COMPARAÇÃO: Regex vs {'LLM (Groq)' if has_key else 'LLM (sem chave)'}")
print("=" * 60)

t0 = time.monotonic()
regex_r = det.detect_in_file(code, "test.c", "c")
print(f"\n📌 REGEX ({((time.monotonic()-t0)*1000):.0f}ms):")
for iss in regex_r.issues:
    print(f"  [{iss.cwe_id}] L{iss.line}: {iss.description}")

if has_key:
    print(f"\n📌 LLM — Groq:")
    t0 = time.monotonic()
    llm_r = det.analyze_with_llm(code, "test.c", "c")
    tllm = time.monotonic() - t0
    for iss in llm_r.issues:
        print(f"  [{iss.cwe_id}] L{iss.line}: {iss.description} (conf={iss.confidence:.0%})")
    print(f"\n⏱️  Regex: instantâneo | LLM: {tllm*1000:.0f}ms")
    print(f"📊 Regex: {len(regex_r.issues)} issues | LLM: {len(llm_r.issues)} issues")
else:
    print(f"\n⚠️  GROQ_API_KEY não definido. Edite .env e rode novamente.")
