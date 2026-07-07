# TheAnd Manifesto

## O que o Quimera é

O Quimera é um **orquestrador de engenharia baseado em evidências**.

Ele não corrige código. Ele **investiga, formula hipóteses, gera candidatos, valida e aprende**.

```
Detectar → Pesquisar → Formular hipóteses → Gerar candidatos → Validar → Aprender
```

Cada decisão é rastreável. Cada patch tem uma explicação.

---

## O que o Quimera NÃO é

### ❌ Não é um corretor de código

Corretores de código recebem entrada → produzem saída. O Quimera recebe entrada, pesquisa em 12 fontes de conhecimento, cruza evidências, gera múltiplos candidatos, valida em 9+ níveis, compara com o comportamento original, e explica por que escolheu aquela solução.

A correção é o resultado final de um processo de engenharia. Não é o produto.

### ❌ Não é um framework generalista

O Quimera não vai resolver bugs em Python, gerar CRUDs em React, escrever documentação, responder perguntas de StackOverflow, ou competir com o ChatGPT.

Ele faz **uma coisa**: engenharia de software em C/C++ orientada a vulnerabilidades.

Se o problema não é um `free()` sem `NULL`, um buffer overflow, um null pointer dereference — o Quimera não é a ferramenta certa. E está tudo bem.

### ❌ Não é uma IA mágica

O Quimera não "pensa". Ele não cria objetivos próprios. Ele não decide o que quer fazer.

É um sistema **determinístico com componentes adaptativos**: as regras são fixas, os pesos se ajustam com a experiência.

Aprendizado de máquina real só acontece em duas circunstâncias:

1. O `CandidateRanker` ajusta os pesos dos validadores baseado no histórico
2. O `SourceCatalog` recalibra a ordem das fontes conforme aprende quais acertam

Fora isso, tudo é determinístico.

---

## Os Quatro Níveis da Arquitetura

```
L1 — EXECUÇÃO
    Planner → Build → Detection → Knowledge → Patch → Validate
    "O que fazer e como fazer."

L2 — INTELIGÊNCIA
    KnowledgeBroker (12 fontes) → HypothesisBuilder → SourceCatalog
    "Qual hipótese faz mais sentido? Qual fonte costuma acertar?"

L3 — SEGURANÇA
    AEGIS Shield → ASan → UBSan → Formal Verification → Differential Validator
    "Esse patch é seguro? O bug realmente sumiu?"

L4 — APRENDIZADO
    UnifiedMemory → LiveCatalog → DecisionReport
    "O que aprendemos? Como a próxima execução será melhor?"
```

---

## Os Limites de Responsabilidade

### O Quimera se responsabiliza por:

1. **Detectar** vulnerabilidades em C/C++ (14 categorias CWE, expandindo)
2. **Pesquisar** em 12 fontes (local, web, GitHub, CVE, man pages, LLM)
3. **Formular** hipóteses com cross-reference de evidências
4. **Gerar** múltiplos candidatos (AST-based, nunca regex)
5. **Validar** em 9 níveis + AEGIS + diferencial
6. **Comparar** comportamento antes vs depois do patch
7. **Aprender** com cada execução e recalibrar
8. **Explicar** cada decisão (DecisionReport)
9. **Medir** performance contra projetos reais (BenchmarkRunner)

### O Quimera NÃO se responsabiliza por:

1. **Decidir o que fazer** — o usuário define a missão
2. **Garantir correção 100%** — engenharia de software tem riscos inerentes
3. **Substituir revisão humana** — é um acelerador, não substituto
4. **Resolver bugs em runtime** — analisa código fonte, não binários
5. **Funcionar com qualquer linguagem** — C/C++ apenas
6. **Ser SaaS ou API REST** — é CLI + biblioteca Python
7. **Competir com Copilot ou ChatGPT** — produtos e propósitos diferentes

---

## O que NUNCA vai entrar no Quimera

- ❌ Geração de código a partir de linguagem natural
- ❌ Chatbot de propósito geral
- ❌ Correção de bugs em Python, JavaScript, Ruby, Go
- ❌ Integração com IDEs (VSCode, JetBrains)
- ❌ Interface web ou dashboard
- ❌ SaaS, nuvem, ou modelo de assinatura
- ❌ Agentes autônomos sem input do usuário
- ❌ Fine-tuning de LLMs com dados proprietários
- ❌ Geração de exploits ou ferramentas ofensivas
- ❌ Suporte a Windows (Linux apenas)

---

## Princípios de Design

1. **Evidência sobre opinião** — Nenhum patch sem múltiplos validadores
2. **Determinismo com adaptação** — Regras fixas, pesos ajustáveis
3. **Cascata, não monolito** — Local → Web → GitHub → CVE → LLM
4. **AST, nunca regex** — Manipulação sintática, não textual
5. **Memória unificada** — Seis stores, uma API
6. **Explicabilidade** — DecisionReport em toda decisão
7. **Arquitetura congelada** — Zero módulos novos, só refinamento
8. **Português como primeira língua** — Interface NL em PT-BR

---

## O Que Torna o Quimera Diferente

Não é gerar patches. Qualquer LLM faz isso.

É o **ciclo completo**:

```
1. Detectar com 14+ padrões CWE e filtros FP
2. Pesquisar em 12 fontes com cascata progressiva
3. Cruzar evidências com pesos por confiabilidade
4. Gerar 5-20 candidatos com AST
5. Validar em 9 níveis independentes
6. Verificar com escudo defensivo AEGIS
7. Comparar antes vs depois (o bug sumiu?)
8. Aprender e recalibrar
9. Explicar por que escolheu aquele patch
```

Nenhuma etapa é inédita. A combinação, sim.

---

## O Que Vem Depois

Arquitetura congelada. Foco:

1. **Qualidade > Quantidade** — Melhores patches, não mais módulos
2. **Benchmarks** — Linux, FFmpeg, QEMU, OpenSSL, SQLite, curl, zlib
3. **CWEs** — Expandir de 14 para 30, 50, 80
4. **FP < 5%** — Redução contínua de falsos positivos
5. **FN < 10%** — Redução contínua de falsos negativos
6. **Differential** — Provar que o bug sumiu, não só que compilou

O caminho não é adicionar funcionalidades. É provar, com evidência reproduzível, que o que já existe funciona.

---

> *"The Quimera is not an AI that fixes code. It's an evidence-driven engineering platform that investigates, hypothesizes, generates, validates, and learns — and explains every decision it makes."*

— TheAnd Manifesto, v1.0
