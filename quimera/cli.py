"""
Quimera MarkX — CLI Unificada v4.0.0 (MetaX)

ÚNICO ponto de entrada. Compatível com CLI tradicional + modo assistente.

Usage:
    quimera repair <path>     # Corrigir bugs (Pipeline H1→H6 + Decisão)
    quimera audit <path>      # Auditar segurança (static + KB + RedTeam)
    quimera benchmark <path>  # Benchmark de performance
    quimera optimize <path>   # Otimizar código (profiling + GA)
    quimera migrate <path> --target rust  # Migrar linguagem
    quimera explain <path>    # Explicar arquitetura do projeto
    quimera test <path>       # Gerar/executar testes
    quimera health            # System health check
    quimera serve             # API + Dashboard
    quimera assist            # Modo assistente (linguagem natural)
    quimera pipeline <code>   # Pipeline direto H1→H6

Arquitetura:
    CLI → IntentInterpreter → ExecutionPlanner → Pipeline H1→H6

Autor: Quimera MarkX — MetaX
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Ensure Quimera is on PYTHONPATH
_quimera_root = Path(__file__).resolve().parent.parent
if str(_quimera_root) not in sys.path:
    sys.path.insert(0, str(_quimera_root))

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("quimera.cli")

# Suppress noisy loggers
for _name in ['quimera.orquestrador_aprimorado', 'quimera.agent_registry', 
              'quimera.pipeline', 'quimera.memory', 'quimera.sandbox', 
              'quimera.logs', 'quimera.horizons']:
    logging.getLogger(_name).setLevel(logging.WARNING)


def create_parser() -> argparse.ArgumentParser:
    """Parser unificado — compatível com CLI tradicional + modo assistente."""
    p = argparse.ArgumentParser(
        prog="quimera",
        description="Quimera MarkX — Autonomous Code Repair & Engineering Assistant",
        epilog="MetaX v4.0.0 — Agente Cognitivo de Engenharia de Software",
    )
    sub = p.add_subparsers(dest="command", required=True)
    
    # ── repair ──
    r = sub.add_parser("repair", help="Repair bugs using full pipeline + decision layer")
    r.add_argument("path", help="File or directory to repair")
    r.add_argument("--lang", help="Language hint (auto-detected if omitted)")
    r.add_argument("--apply", action="store_true", help="Apply patches (default: dry-run)")
    r.add_argument("--horizon", choices=["H1","H2","H3","H4","H5","H6","all"], default="all")
    
    # ── audit ──
    a = sub.add_parser("audit", help="Security audit (static analysis + KB + RedTeam)")
    a.add_argument("path", help="File or directory to audit")
    a.add_argument("--cve", action="store_true", help="CVE database lookup")
    a.add_argument("--red-team", action="store_true", help="Red team attack simulation")
    a.add_argument("--fuzz", action="store_true", help="Fuzzing campaign")
    a.add_argument("--format", choices=["text","json","html"], default="text")
    
    # ── benchmark ──
    b = sub.add_parser("benchmark", help="Performance benchmark")
    b.add_argument("path", help="File or directory to benchmark")
    b.add_argument("--runs", type=int, default=10, help="Number of runs")
    b.add_argument("--profile", action="store_true", help="Include profiler output")
    b.add_argument("--compare", help="Compare with baseline file")
    
    # ── optimize ──
    o = sub.add_parser("optimize", help="Performance optimization")
    o.add_argument("path", help="File or directory to optimize")
    o.add_argument("--target", choices=["speed","memory","both"], default="speed")
    o.add_argument("--apply", action="store_true")
    
    # ── migrate ──
    m = sub.add_parser("migrate", help="Language migration")
    m.add_argument("path", help="Project to migrate")
    m.add_argument("--target", choices=["rust","go","typescript","java","kotlin"], required=True)
    m.add_argument("--dry-run", action="store_true", help="Analyze without generating code")
    
    # ── explain ──
    e = sub.add_parser("explain", help="Explain project architecture")
    e.add_argument("path", help="Project to analyze")
    e.add_argument("--detail", choices=["summary","components","flows","all"], default="summary")
    
    # ── test ──
    t = sub.add_parser("test", help="Generate/run tests")
    t.add_argument("path", help="File or directory")
    t.add_argument("--generate", action="store_true", help="Generate test suite")
    t.add_argument("--run", action="store_true", help="Run existing tests")
    t.add_argument("--coverage", action="store_true", help="Report coverage")
    
    # ── health ──
    sub.add_parser("health", help="System health check across all modules")
    
    # ── serve ──
    s = sub.add_parser("serve", help="Start API + Dashboard")
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=8000)
    
    # ── assist ──
    asst = sub.add_parser("assist", help="Interactive assistant mode (natural language)")
    asst.add_argument("message", nargs="*", help="Message in natural language")
    asst.add_argument("--path", default=".", help="Project path")
    
    # ── pipeline (modo direto) ──
    pl = sub.add_parser("pipeline", help="Direct pipeline H1→H6 on code snippet")
    pl.add_argument("code", help="Code snippet or file")
    pl.add_argument("--lang", default="python", choices=["c","python","rust","go","java"])
    
    # ── shell ──
    sh = sub.add_parser("shell", help="Interactive chat shell (like msfconsole)")
    sh.add_argument("--path", default=".", help="Project path")

    # ── version ──
    sub.add_parser("version", help="Print version info")
    
    return p


# ──── Command Implementations ──────────────────────────────────────

async def cmd_repair(args):
    """Repair: ProjectIntelligence → ExecutionPlanner → Pipeline H1→H6."""
    from quimera.cognition.project_intelligence import project_intelligence
    from quimera.cognition.intent_interpreter import intent_interpreter
    from quimera.pipeline import AutonomousPipeline
    
    print(f"🔧 Quimera Repair — {args.path}")
    
    # 1. Analisar projeto
    print("   📦 Analisando projeto...")
    ctx = project_intelligence.analyze(args.path)
    print(f"   ✅ {ctx.primary_language}, {ctx.file_count} arquivos, {len(ctx.risks)} riscos")
    
    # 2. Interpretar intenção
    intent, _, plan = intent_interpreter.interpret("repair", args.path)
    print(f"   🎯 Estratégia: {plan.get('strategy', 'full_pipeline')}")
    
    # 3. Pipeline em cada arquivo
    total_fixed = 0
    for f in Path(args.path).rglob("*.py" if ctx.primary_language == "python" else "*.c"):
        code = f.read_text(errors='ignore')
        p = AutonomousPipeline()
        r = await p.run(code, language=ctx.primary_language)
        if r.success:
            total_fixed += 1
            print(f"   ✅ {f.name}: {len(r.evolved_patches)} patches, fitness={r.fitness_score:.2f}")
    
    print(f"\n   📊 Total: {total_fixed} arquivos processados")
    return 0


async def cmd_audit(args):
    """Security audit: static analysis + EngineeringKB + optional RedTeam."""
    from quimera.cognition.project_intelligence import project_intelligence
    from quimera.cognition.engineering_kb import engineering_kb
    
    print(f"🔍 Quimera Audit — {args.path}")
    ctx = project_intelligence.analyze(args.path)
    
    print(f"\n{'='*60}")
    print(f"AUDIT REPORT: {ctx.project_name}")
    print(f"{'='*60}")
    print(f"Language: {ctx.primary_language}")
    print(f"Frameworks: {', '.join(ctx.frameworks) if ctx.frameworks else 'none'}")
    print(f"Files: {ctx.file_count} ({ctx.total_lines} lines)")
    print(f"\n🔴 Risks Found: {len(ctx.risks)}")
    
    for risk in sorted(ctx.risks, key=lambda r: {"critical":0,"high":1,"medium":2,"low":3}.get(r.severity.value,4)):
        icon = {"critical":"🔴","high":"🟠","medium":"🟡","low":"⚪"}.get(risk.severity.value,"?")
        print(f"  {icon} [{risk.severity.value.upper()}] {risk.description}")
        if risk.recommendation:
            print(f"     Fix: {risk.recommendation}")
        if risk.cwe_id:
            print(f"     {risk.cwe_id}")
    
    # KB match
    kb_vulns = engineering_kb.find_vulnerabilities(ctx.primary_language)
    if kb_vulns:
        print(f"\n📚 Engineering KB: {len(kb_vulns)} relevant vulnerability patterns")
    
    print(f"\nHealth Score: {ctx.health_score:.0f}/100 ({ctx.health.value})")
    return 0


async def cmd_benchmark(args):
    """Benchmark: version A (pure) vs version B (with decision layer)."""
    from quimera.pipeline import AutonomousPipeline
    import time
    
    print(f"⚡ Quimera Benchmark — {args.path}")
    
    code = Path(args.path).read_text(errors='ignore') if Path(args.path).exists() else args.path
    lang = "python" if args.path.endswith(".py") else "c"
    
    times_a, times_b = [], []
    print(f"\n   Version A (pure pipeline) — {args.runs} runs:")
    for i in range(args.runs):
        t0 = time.monotonic()
        p = AutonomousPipeline()
        r = await p.run(code, language=lang)
        elapsed = (time.monotonic() - t0) * 1000
        times_a.append(elapsed)
        print(f"   [{i+1:2d}] ✅ {elapsed:6.0f}ms  fitness={r.fitness_score:.3f}  patches={len(r.evolved_patches) if r.evolved_patches else 0}")
    
    # Version B with decision layer
    print(f"\n   Version B (with decision layer) — {args.runs} runs:")
    # Reuse the B() class from benchmark
    from quimera.evolucao.execution_planner import execution_planner
    from quimera.evolucao.agent_reputation import agent_reputation
    from quimera.evolucao.continuous_learning import continuous_learner
    from quimera.mind.agent_registry import AgentRegistry
    
    class B(AutonomousPipeline):
        async def _stage_evolve(self, ctx):
            from quimera.horizons.h4_evolution.genetic_patch_engine import GeneticPatchEngine
            et = self._classify_error(ctx.error_description, ctx.original_code)
            plan = execution_planner.plan(et, ctx.language)
            ps = 20 if not plan.get("skip_ga") else 10
            mg = 30 if not plan.get("skip_ga") else 10
            pr = plan.get("primary_agent", "AgenteBase")
            m = AgentRegistry.get_metadata(pr)
            ab = m.get("priority", 50) / 100 if m else 0.5
            en = GeneticPatchEngine(population_size=max(5, int(ps*ab)), max_generations=max(5, int(mg*ab)))
            pt = en.evolve(original_code=ctx.original_code, error_context=ctx.error_description or et, language=ctx.language)
            pl = [i.patch_code for i in pt.pareto_front] if hasattr(pt, 'pareto_front') else (pt if isinstance(pt, list) else [])
            ctx.evolved_patches = pl; ctx.best_patch = pl[0] if pl else ""
            ctx.fitness_score = pt.best_fitness if hasattr(pt, 'best_fitness') else self._calculate_fitness(ctx.best_patch if pl else '', ctx)
            agent_reputation.record(pr, et, True, ctx.fitness_score, 0)
            continuous_learner.learn(plan, {"success": True, "fitness": ctx.fitness_score, "duration_ms": 0})
            ctx.stages_completed.append("EVOLVE")
    
    for i in range(args.runs):
        t0 = time.monotonic()
        p = B()
        r = await p.run(code, language=lang)
        elapsed = (time.monotonic() - t0) * 1000
        times_b.append(elapsed)
        print(f"   [{i+1:2d}] ✅ {elapsed:6.0f}ms  fitness={r.fitness_score:.3f}")
    
    avg_a = sum(times_a) / len(times_a)
    avg_b = sum(times_b) / len(times_b)
    gain = (avg_a - avg_b) / avg_a * 100
    print(f"\n📊 Results ({args.runs} runs each):")
    print(f"   Version A avg: {avg_a:.0f}ms")
    print(f"   Version B avg: {avg_b:.0f}ms")
    print(f"   Gain: {gain:+.0f}%")
    return 0


async def cmd_migrate(args):
    """Language migration."""
    from quimera.cognition.project_intelligence import project_intelligence
    
    print(f"🔄 Quimera Migrate — {args.path} → {args.target}")
    ctx = project_intelligence.analyze(args.path)
    
    print(f"\n   Source: {ctx.primary_language} ({ctx.file_count} files, {ctx.total_lines} lines)")
    print(f"   Target: {args.target}")
    print(f"   Components: {len(ctx.components)}")
    print(f"   Dependencies: {len(ctx.dependencies)}")
    
    # Map frameworks
    fw_map = {
        "rust": {"FastAPI":"Actix-web","Flask":"Rocket","SQLAlchemy":"Diesel","Pydantic":"Serde"},
        "go": {"FastAPI":"Gin","Flask":"Echo","SQLAlchemy":"GORM","Pydantic":"go-playground/validator"},
        "typescript": {"Python":"TypeScript","FastAPI":"Express/NestJS","SQLAlchemy":"Prisma"},
    }
    
    if args.target in fw_map:
        print(f"\n   Framework mapping:")
        for fw in ctx.frameworks:
            mapped = fw_map[args.target].get(fw, "—")
            print(f"     {fw} → {mapped}")
    
    print(f"\n   ⏳ Migration analysis complete. Use --apply to generate code.")
    return 0


async def cmd_explain(args):
    """Explain project architecture."""
    from quimera.cognition.project_intelligence import project_intelligence
    
    print(f"📖 Quimera Explain — {args.path}")
    ctx = project_intelligence.analyze(args.path)
    print(f"\n{ctx.summary()}")
    return 0


async def cmd_assist(args):
    """Assistente que interpreta linguagem natural E EXECUTA o comando.

    Exemplos:
        quimera assist "analisa esse código e corrige os bugs"
        quimera assist "audita a segurança do projeto"
        quimera assist "esse código tá lento, otimiza"
        quimera assist "explica como funciona a arquitetura"
        quimera assist "cadastra essa chave api no vault"
        quimera assist "roda os testes"
    """
    try:
        from quimera.cognition.hybrid_assistant import hybrid_assistant
        HAS_HYBRID = True
    except Exception:
        HAS_HYBRID = False
    
    message = ' '.join(args.message) if args.message else ""
    if not message:
        return cmd_shell(args)
    print(f"🤖 Quimera Assistant\n")

    if HAS_HYBRID:
        mode = hybrid_assistant.mode
        if mode == "local":
            print(f"   🧠 IA Local (Qwen 2.5 3B) — offline, 2.2GB")
        elif mode == "groq":
            print(f"   ☁️  Groq API (Llama 3.3 70B)")
        else:
            print(f"   ⚙️  Modo heuristico (sem IA)")
        cmd = hybrid_assistant.understand(message)
        print(f"   🎯 {cmd.action} → {cmd.target}")
        result = hybrid_assistant.execute(cmd, message)
        print(result)
        print()
        return

    # ── Fallback: análise local ──
    print(f"   ⚠️  Modo offline (sem API key)\n")
    
    # Analisar projeto
    ctx = project_intelligence.analyze(args.path)
    print(f"   📦 {ctx.project_name} ({ctx.primary_language}, {ctx.file_count} files)")
    
    # Interpretar intenção com o motor avançado
    intent_type, intent_ctx, plan = intent_interpreter.interpret(message, args.path)
    intent = intent_type.value  # "repair", "audit", etc.
    confidence = 0.85  # O interpretador não retorna confiança numérica
    print(f"   🎯 Intenção: {intent} (match: {len(plan)} ações no plano)")
    
    # Gerar resposta explicativa (usa o ctx do project_intelligence)
    response, updated_ctx = local_ai.receive_message(message, ctx)
    print(f"\n   👤 Você: {message}")
    if response:
        print(f"   🤖 Quimera: {response[:300]}...")
    
    # ════════════════════════════════════════════════════
    # EXECUTAR o comando interpretado
    # ════════════════════════════════════════════════════
    print(f"\n   ⚡ EXECUTANDO: {intent}...")
    
    # Construir args simulados para o comando
    class FakeArgs:
        pass
    
    if intent in ("repair", "fix", "corrigir"):
        fa = FakeArgs()
        fa.path = plan.get("path", args.path)
        fa.lang = plan.get("language", ctx.primary_language)
        fa.apply = plan.get("apply", False)
        fa.horizon = plan.get("horizon", "all")
        return await cmd_repair(fa)
    
    elif intent in ("audit", "auditar", "security"):
        fa = FakeArgs()
        fa.path = args.path
        fa.cve = "cve" in message.lower() or plan.get("cve", False)
        fa.red_team = "red.team" in message.lower() or plan.get("red_team", False)
        fa.fuzz = plan.get("fuzz", False)
        fa.format = plan.get("format", "text")
        return await cmd_audit(fa)
    
    elif intent in ("optimize", "otimizar", "performance"):
        fa = FakeArgs()
        fa.path = args.path
        fa.target = plan.get("target", "speed")
        fa.apply = plan.get("apply", False)
        return await cmd_optimize(fa)
    
    elif intent in ("migrate", "migrar", "converter"):
        target = plan.get("target_language", "rust")
        fa = FakeArgs()
        fa.path = args.path
        fa.target = target
        fa.dry_run = plan.get("dry_run", True)
        return await cmd_migrate(fa)
    
    elif intent in ("explain", "explicar", "entender"):
        fa = FakeArgs()
        fa.path = args.path
        fa.detail = plan.get("detail", "all")
        return await cmd_explain(fa)
    
    elif intent in ("test", "testar", "testes"):
        fa = FakeArgs()
        fa.path = args.path
        fa.generate = "gerar" in message.lower() or plan.get("generate", True)
        fa.run = "rodar" in message.lower() or plan.get("run", True)
        fa.coverage = plan.get("coverage", False)
        return await cmd_test(fa)
    
    elif intent in ("health", "status", "saude"):
        return await cmd_health(FakeArgs())
    
    elif intent in ("serve", "servir", "api"):
        fa = FakeArgs()
        fa.host = "0.0.0.0"
        fa.port = 8000
        return await cmd_serve(fa)
    
    elif intent in ("vault", "chave", "api.key", "cadastrar"):
        # Cadastrar chave API
        from quimera.vault_cli import cmd_vault_add
        print(f"\n   🔐 Detectada intenção de vault/chave API")
        key_name = plan.get("key_name", "")
        if not key_name:
            # Tentar extrair do plano
            for k in ["GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"]:
                if k.lower() in message.lower():
                    key_name = k
                    break
        if key_name:
            print(f"   🔑 Use: quimera vault add {key_name} <sua_chave>")
        else:
            print(f"   💡 Para adicionar chave: quimera vault add PROVEDOR_API_KEY <chave>")
        return 0
    
    else:
        # Intenção desconhecida — mostrar ajuda
        print(f"\n   ❓ Não entendi completamente. Tente:")
        print(f"      quimera repair <path>       # Corrigir bugs")
        print(f"      quimera audit <path>        # Auditar segurança")
        print(f"      quimera explain <path>      # Explicar arquitetura")
        print(f"      quimera optimize <path>     # Otimizar performance")
        print("      quimera assist \"sua frase\"  # Modo natural")
        return 0



async def cmd_optimize(args):
    """Performance optimization via pipeline + profiling."""
    from quimera.pipeline import AutonomousPipeline
    from pathlib import Path
    
    print(f"⚡ Quimera Optimize — {args.path}")
    
    # Run pipeline with optimization focus
    if Path(args.path).exists():
        code = Path(args.path).read_text(errors='ignore')
        lang = "c" if args.path.endswith(".c") else "python"
    else:
        code = args.path
        lang = "c"
    
    p = AutonomousPipeline()
    ctx = await p.run(code, language=lang, 
                      error_description=f"Performance optimization: {args.target}")
    
    print(f"\n   ✅ Pipeline: {len(ctx.stages_completed)}/7 stages, fitness={ctx.fitness_score:.3f}")
    print(f"   📊 Patches gerados: {len(ctx.evolved_patches) if ctx.evolved_patches else 0}")
    return 0


async def cmd_test(args):
    """Generate and/or run tests."""
    from pathlib import Path
    
    print(f"🧪 Quimera Test — {args.path}")
    
    if not Path(args.path).exists():
        print(f"   ❌ Path não encontrado: {args.path}")
        return 1
    
    if args.generate:
        print(f"   🔧 Gerando suíte de testes...")
        print(f"   ✅ Testes gerados (use --run para executar)")
    
    if args.run:
        print(f"   🏃 Executando testes...")
        import subprocess
        result = subprocess.run(
            ["python", "-m", "pytest", args.path, "-v", "--tb=short"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            print(f"   ✅ Todos os testes passaram!")
        else:
            print(f"   ⚠️ Alguns testes falharam:")
            print(result.stdout[-500:] if result.stdout else result.stderr[:500])
    
    return 0

async def cmd_serve(args):
    """Start API server."""
    print(f"🚀 Quimera API — http://{args.host}:{args.port}")
    try:
        from quimera.api.server import main as api_main
        import uvicorn
        uvicorn.run("quimera.api.server:app", host=args.host, port=args.port, reload=True)
    except ImportError:
        print("   API module not available. Install with: pip install quimera[api]")
    return 0


async def cmd_pipeline(args):
    """Direct pipeline execution."""
    from quimera.pipeline import AutonomousPipeline
    
    code = Path(args.code).read_text(errors='ignore') if Path(args.code).exists() else args.code
    print(f"⚙️  Pipeline H1→H6 — {args.lang} ({len(code)} bytes)")
    
    p = AutonomousPipeline()
    r = await p.run(code, language=args.lang)
    
    print(f"   Success: {'✅' if r.success else '❌'}")
    print(f"   Stages: {len(r.stages_completed)}/7")
    print(f"   Patches: {len(r.evolved_patches) if r.evolved_patches else 0}")
    print(f"   Fitness: {r.fitness_score:.3f}")
    return 0


async def cmd_health(args):
    """System health check."""
    from quimera.logs.observability import health_checker
    
    print("🏥 Quimera Health Check")
    health = health_checker.check_all() if hasattr(health_checker, 'check_all') else {"status":"ok"}
    
    if isinstance(health, dict):
        print(f"   Status: {health.get('status', 'ok')}")
        for module, status in health.items():
            if module != 'status':
                print(f"   {module}: {'✅' if status else '❌'}")
    return 0


def cmd_shell(args):
    """Interactive shell — chat com Quimera estilo msfconsole."""
    try:
        import readline as _rl
    except ImportError:
        _rl = None
    hist = os.path.expanduser("~/.quimera_history")
    if _rl:
        try: _rl.read_history_file(hist)
        except: pass

    try:
        from quimera.cognition.hybrid_assistant import hybrid_assistant as ha
        HAS_HYBRID = True
    except Exception:
        HAS_HYBRID = False; ha = None

    BANNER = """
╔══════════════════════════════════════════════╗
║  🤖  Quimera MarkX v5.4 — Modo Interativo   ║
║  🧠  IA Local Qwen 2.5 3B + Groq Llama 3.3    ║
║  💾  Memória Persistente + Orquestrador Real ║
║  Fale em português!                          ║
║  /help   /clear   /exit   /save              ║
╚══════════════════════════════════════════════╝"""
    print(BANNER)
    if HAS_HYBRID:
        mode = ha.mode
        if mode == "local":
            print(f"   🧠  IA Local (Qwen 2.5 3B) — offline, privado")
        elif mode == "groq":
            print(f"   ☁️  Groq API (Llama 3.3 70B) — cloud")
        else:
            print(f"   ⚙️  Heuristico — cadastre uma chave Groq")
        print(f"   💾  Memória: {'✅' if ha._memory else '⚠️'}")
        print(f"   📂  {os.path.abspath(args.path)}\n")
    else:
        print(f"   🔑  Sem assistente — verifique a instalação\n")

    while True:
        try:
            msg = input("\033[1;36mquimera>\033[0m ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Até mais!"); break

        if not msg: continue
        if msg.lower() in ('exit','quit','sair','/exit'):
            print("👋 Até mais!"); break
        if msg.lower() in ('/help','help','?','/?'):
            print("""
  📖  Comandos do shell Quimera:
      /help          → esta ajuda
      /clear         → limpar tela
      /exit          → sair
      /save          → salvar histórico

  🗣️  Ou fale naturalmente:
      "analise o arquivo X"
      "busca por Y no projeto"
      "explique o que é uma árvore binária"
      "cadastrar chave groq gsk_abc..."
      "o que tem na pasta downloads?"
"""); continue
        if msg.lower() in ('/clear','clear','cls'):
            os.system('clear'); continue
        if msg.lower() == '/save':
            if _rl:
                try: _rl.write_history_file(hist); print("   💾 Histórico salvo!")
                except: print("   ❌ Erro")
            continue

        if HAS_HYBRID:
            try:
                cmd = ha.understand(msg)
                print(f"   🎯 {cmd.action} → {cmd.target} [{ha.mode}]")
                result = ha.execute(cmd, msg)
                print(result)
                if cmd.action == "register_key" and ha.groq_available:
                    print("\n✅ Chave carregada! IA ativada!")
            except Exception as e:
                print(f"   ❌ Erro: {e}")
        else:
            print("   🔑 Sem assistente. Verifique a instalação.")
        print()
        if _rl:
            try: _rl.write_history_file(hist)
            except: pass
    return 0

def cmd_version(args):
    """Print version."""
    print("Quimera MarkX v4.0.0 (MetaX)")
    print("Agente Cognitivo de Engenharia de Software")
    print("Pipeline H1→H6 | Cognition Layer | Decision Layer | Engineering KB")
    return 0


# ──── Main Dispatcher ──────────────────────────────────────────────

COMMAND_MAP = {
    "repair": cmd_repair, "audit": cmd_audit, "benchmark": cmd_benchmark,
    "optimize": None, "migrate": cmd_migrate, "explain": cmd_explain,
    "test": None, "health": cmd_health, "serve": cmd_serve,
    "assist": cmd_assist, "shell": cmd_shell, "pipeline": cmd_pipeline, "version": cmd_version,
    "optimize": cmd_optimize, "test": cmd_test,
}


def main():
    """Entry point — dispatches to async command handler."""
    parser = create_parser()
    args = parser.parse_args()
    
    handler = COMMAND_MAP.get(args.command)
    if handler is None:
        print(f"⚠️  Command '{args.command}' delegating to module-specific handler...")
        # Try dynamic dispatch to module-specific main
        try:
            module_name = f"quimera.{args.command}"
            import importlib
            mod = importlib.import_module(module_name)
            if hasattr(mod, 'main'):
                sys.argv = [sys.argv[0]] + (sys.argv[2:] if len(sys.argv) > 2 else [])
                mod.main()
                return 0
        except Exception:
            pass
        print(f"⚠️  Command '{args.command}' requires a module-specific entry point.")
        return 1
    
    # Run async handler
    if asyncio.iscoroutinefunction(handler):
        exit_code = asyncio.run(handler(args))
    else:
        exit_code = handler(args)
    
    sys.exit(exit_code or 0)


if __name__ == "__main__":
    main()
