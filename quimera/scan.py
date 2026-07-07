#!/usr/bin/env python3
"""
Quimera Scan — Análise de vulnerabilidades com um comando.

Uso:
  python -m quimera.scan arquivo.c
  python -m quimera.scan ~/Downloads/filep3s/

A chave GROQ_API_KEY é lida do .env automaticamente.
"""
import sys, os, time, glob

# Carrega .env
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(root, '.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                k, v = k.strip(), v.strip()
                if k not in os.environ:
                    os.environ[k] = v

sys.path.insert(0, root)
from quimera.hybrid_detector import HybridDetector


def scan_file(path, detector):
    try:
        with open(path) as f: code = f.read()
    except Exception as e:
        return None
    return detector.analyze(code, path, 'c')


def main():
    if len(sys.argv) < 2:
        print("🔍 Quimera Scan — Análise de vulnerabilidades C")
        print()
        print("Uso:  python -m quimera.scan <arquivo.c | pasta/>")
        print()
        print("Exemplos:")
        print("  python -m quimera.scan driver.c")
        print("  python -m quimera.scan ~/Downloads/filep3s/")
        print("  python -m quimera.scan ./src/")
        sys.exit(0)

    target = os.path.expanduser(sys.argv[1])
    files = []

    if os.path.isfile(target):
        files = [target]
    elif os.path.isdir(target):
        files = sorted(glob.glob(os.path.join(target, '**', '*.c'), recursive=True))
        if not files:
            files = sorted(glob.glob(os.path.join(target, '**', '*.h'), recursive=True))
    else:
        print(f"❌ Caminho não encontrado: {target}")
        sys.exit(1)

    if not files:
        print(f"⚠️  Nenhum arquivo .c/.h em {target}")
        sys.exit(1)

    detector = HybridDetector()
    has_llm = bool(detector.api_key)
    total_issues = total_fps = total_files = 0
    t_start = time.time()

    print("=" * 60)
    print(f"🔍 QUIMERA SCAN  |  {'Groq LLM' if has_llm else 'Regex rápido'}")
    print(f"📁 {target}  |  📄 {len(files)} arquivo(s)")
    print("=" * 60)

    for fpath in files:
        fname = os.path.basename(fpath)
        report = scan_file(fpath, detector)
        if report is None: continue
        total_files += 1
        total_issues += report.final_issues
        total_fps += report.false_positives_removed

        if report.final_issues > 0:
            print(f"\n📄 {fname} — {report.final_issues} vulnerabilidade(s):")
            for iss in report.issues:
                icon = "🔴" if iss.confidence >= 0.8 else ("🟡" if iss.confidence >= 0.6 else "🟢")
                print(f"  {icon} [{iss.cwe_id}] L{iss.line}: {iss.description[:90]}")

    elapsed = time.time() - t_start
    print(f"\n{'='*60}")
    print(f"📊 {total_issues} issues | {total_fps} FPs removidos | {total_files} arquivos | {elapsed:.1f}s")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
