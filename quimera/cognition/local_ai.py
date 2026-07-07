"""
Local AI Interface — Consciência situacional em tempo real.

Permite que o Quimera:
  1. Trabalhe enquanto conversa com o usuário
  2. Atualize o ProjectContext com novas informações do usuário
  3. Faça perguntas inteligentes baseadas no que já descobriu
  4. Mantenha contexto da conversa entre múltiplas interações

A IA local não corrige código — ela entende o usuário e enriquece o contexto.

Autor: Quimera MarkX — MetaX
"""
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from quimera.cognition.project_context import (
    ProjectContext, RiskLevel, ProjectHealth, ArchitecturePattern,
)

logger = logging.getLogger("quimera.local_ai")


class ConversationState(str, Enum):
    """Estado da conversa com o usuário."""
    GREETING = "greeting"                   # Início: "Olá, estou analisando..."
    ANALYZING = "analyzing"                 # Analisando o projeto
    ASKING_CLARIFICATION = "asking"         # Perguntando ao usuário
    WAITING_USER = "waiting"                # Aguardando resposta
    EXECUTING = "executing"                 # Executando plano
    REPORTING = "reporting"                 # Gerando relatório
    IDLE = "idle"                           # Conversa encerrada


@dataclass
class ConversationTurn:
    """Um turno da conversa entre IA e usuário."""
    timestamp: str
    speaker: str                            # "ai" ou "user"
    message: str
    context_snapshot: Optional[str] = None  # Hash do ProjectContext neste momento
    discoveries: List[str] = field(default_factory=list)  # O que foi descoberto neste turno


class LocalAI:
    """Interface de IA local com consciência situacional.
    
    Esta classe gerencia a conversa entre o Quimera e o usuário,
    mantendo o ProjectContext atualizado em tempo real.
    
    Em produção, pode ser conectada a um LLM local (Ollama, LlamaCPP, etc).
    Na versão atual, usa heurísticas determinísticas para simular o comportamento.
    
    A IA NÃO toma decisões de execução — ela apenas:
      - Interpreta a intenção do usuário
      - Enriquece o ProjectContext
      - Faz perguntas inteligentes
      - Mantém o histórico da conversa
    """
    
    def __init__(self, llm_backend: Optional[Any] = None):
        self.llm = llm_backend
        self.state = ConversationState.IDLE
        self.conversation: List[ConversationTurn] = []
        self.context: Optional[ProjectContext] = None
    
    # ──── Entrada do Usuário ───────────────────────────────────────
    
    def receive_message(self, message: str, context: ProjectContext) -> Tuple[str, ProjectContext]:
        """Processa uma mensagem do usuário e retorna resposta + contexto atualizado.
        
        Este é o método principal. Ele:
          1. Registra a mensagem do usuário
          2. Analisa o que o usuário quis dizer
          3. Enriquece o ProjectContext
          4. Determina se precisa perguntar algo
          5. Retorna a resposta da IA
        """
        self.context = context
        self.state = ConversationState.ANALYZING
        
        # Registrar turno do usuário
        self.conversation.append(ConversationTurn(
            timestamp=datetime.now(timezone.utc).isoformat(),
            speaker="user",
            message=message,
        ))
        context.conversation_context.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "speaker": "user",
            "message": message,
        })
        
        # Analisar a mensagem
        intent, extracted_info = self._analyze_message(message, context)
        
        # Atualizar contexto
        context = self._update_context(context, intent, extracted_info, message)
        
        # Gerar resposta
        response = self._generate_response(context, intent, extracted_info)
        
        # Registrar turno da IA
        self.conversation.append(ConversationTurn(
            timestamp=datetime.now(timezone.utc).isoformat(),
            speaker="ai",
            message=response,
            discoveries=self._extract_discoveries(context),
        ))
        context.conversation_context.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "speaker": "ai",
            "message": response,
        })
        
        return response, context
    
    def _analyze_message(self, message: str, context: ProjectContext) -> Tuple[str, Dict]:
        """Analisa a mensagem do usuário e extrai intenção + informações."""
        msg_lower = message.lower()
        info = {}
        
        # Detectar intenção
        intents = {
            "repair": ["não compila", "não funciona", "quebrou", "bug", "erro", "corrig",
                       "consert", "arrum", "fix", "broken", "crash", "fail", "500", "traceback"],
            "audit": ["audit", "segurança", "vulnerabilidade", "security", "vuln"],
            "optimize": ["lento", "devagar", "otimiz", "performance", "rápido", "memória"],
            "migrate": ["migrar", "converter", "transform", "reescrever"],
            "explain": ["explica", "como funciona", "arquitetura", "entender", "o que faz"],
            "test": ["teste", "test", "cobertura", "coverage"],
        }
        
        intent = "unknown"
        for candidate, keywords in intents.items():
            if any(kw in msg_lower for kw in keywords):
                intent = candidate
                break
        
        # Extrair informações específicas
        if intent == "migrate":
            for lang in ["rust", "go", "typescript", "java", "kotlin"]:
                if lang in msg_lower:
                    info["target_language"] = lang
        
        # Detectar urgência
        if any(w in msg_lower for w in ["urgente", "agora", "rápido", "asap", "produção", "production"]):
            info["priority"] = "high"
        elif any(w in msg_lower for w in ["depois", "amanhã", "quando der"]):
            info["priority"] = "low"
        else:
            info["priority"] = "medium"
        
        # Detectar menção de erro específico
        error_patterns = [
            (r'(Traceback.*?)(?:\n|$)', 'traceback'),
            (r'(Error:.*?)(?:\n|$)', 'error_message'),
            (r'(\d{3}\s+(?:Internal Server|Bad Request).*?)(?:\n|$)', 'http_error'),
        ]
        for pattern, etype in error_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                info["error_text"] = match.group(1).strip()[:200]
                info["error_type"] = etype
                break
        
        return intent, info
    
    def _update_context(
        self, context: ProjectContext, intent: str, info: Dict, message: str
    ) -> ProjectContext:
        """Atualiza o ProjectContext com as informações extraídas."""
        context.user_intent = intent
        context.user_message = message
        context.user_priority = info.get("priority", "medium")
        
        if "error_text" in info:
            context.current_error = info["error_text"]
            context.error_type = info.get("error_type", "")
        
        if "target_language" in info:
            context.tags.append(f"migration-target:{info['target_language']}")
        
        return context
    
    def _extract_discoveries(self, context: ProjectContext) -> List[str]:
        """Extrai descobertas relevantes do contexto atual."""
        discoveries = []
        
        if context.primary_language != "unknown":
            discoveries.append(f"Linguagem: {context.primary_language}")
        
        if context.frameworks:
            discoveries.append(f"Frameworks: {', '.join(context.frameworks[:3])}")
        
        if context.purpose:
            discoveries.append(f"Propósito: {context.purpose[:80]}")
        
        if context.file_count > 0:
            discoveries.append(f"Arquivos: {context.file_count} ({context.total_lines} linhas)")
        
        if len(context.components) > 0:
            discoveries.append(f"Componentes: {len(context.components)}")
        
        if context.risks:
            discoveries.append(f"Riscos: {len(context.risks)}")
        
        return discoveries
    
    # ──── Geração de Resposta ───────────────────────────────────────
    
    def _generate_response(self, context: ProjectContext, intent: str, info: Dict) -> str:
        """Gera uma resposta natural baseada no estado atual."""
        name = context.project_name or "seu projeto"
        lang = context.primary_language
        files = context.file_count
        frameworks = ', '.join(context.frameworks[:2]) if context.frameworks else ""
        
        if intent == "repair" and lang != "unknown":
            return self._repair_response(context, name, lang, files, frameworks)
        elif intent == "audit":
            return self._audit_response(context, name, lang, frameworks)
        elif intent == "optimize":
            return self._optimize_response(context, name, lang)
        elif intent == "migrate":
            target = info.get("target_language", "outra linguagem")
            return self._migrate_response(context, name, lang, target)
        elif intent == "explain":
            return self._explain_response(context, name, lang)
        elif intent == "test":
            return self._test_response(context, name)
        else:
            return self._general_response(context, name, lang, files)
    
    def _repair_response(self, ctx, name, lang, files, frameworks):
        """Gera resposta para intenção de reparo."""
        lines = []
        
        # O que já sabemos
        lines.append(f"Estou analisando **{name}**.")
        
        if files > 0:
            lines.append(f"Detectei que é um projeto **{lang.capitalize()}**")
            if frameworks:
                lines.append(f"usando **{frameworks}**")
            lines.append(f"com **{files} arquivos**.")
        
        if not ctx.has_tests:
            lines.append("\nNotei que o projeto **não tem testes automatizados**. Isso pode dificultar a validação das correções.")
        
        if ctx.current_error:
            lines.append(f"\nEntendi que o erro é: `{ctx.current_error[:100]}`")
        
        # Pergunta inteligente
        lines.append("\nEnquanto preparo a correção, me diga uma coisa:")
        
        if not ctx.expected_behavior:
            lines.append(f"- Como esse projeto **deveria** funcionar? O que você esperava que acontecesse?")
        elif not ctx.has_tests:
            lines.append(f"- Você tem ideia de **quando** esse problema começou? Após alguma atualização específica?")
        else:
            lines.append(f"- Já tentou alguma correção manual que não funcionou?")
        
        lines.append(f"\nEnquanto isso, já estou:")
        lines.append(f"- ⏳ Verificando dependências...")
        lines.append(f"- ⏳ Localizando o código relacionado ao erro...")
        lines.append(f"- ⏳ Preparando patches candidatos...")
        
        return '\n'.join(lines)
    
    def _audit_response(self, ctx, name, lang, frameworks):
        lines = [f"Iniciando auditoria de segurança em **{name}**."]
        
        if lang != "unknown":
            lines.append(f"\nProjeto **{lang.capitalize()}**")
            if frameworks:
                lines.append(f"com **{frameworks}**.")
            lines.append(f"\nJá carreguei **10 padrões de vulnerabilidade** específicos para {lang.capitalize()} da Engineering Knowledge Base.")
        
        lines.append(f"\nVou verificar:")
        lines.append(f"- Secrets hardcoded")
        lines.append(f"- Injeção (SQL, comando, template)")
        lines.append(f"- Configurações inseguras")
        lines.append(f"- Dependências vulneráveis")
        
        if ctx.current_error:
            lines.append(f"\nTambém vou analisar o erro atual: `{ctx.current_error[:80]}`")
        
        lines.append(f"\n🔍 Iniciando varredura...")
        return '\n'.join(lines)
    
    def _optimize_response(self, ctx, name, lang):
        lines = [f"Analisando performance de **{name}**."]
        
        if lang != "unknown":
            lines.append(f"\nProjeto **{lang.capitalize()}** com **{ctx.file_count} arquivos**.")
        
        lines.append(f"\nVou executar:")
        lines.append(f"- Profiler para identificar gargalos")
        lines.append(f"- Análise de complexidade dos componentes")
        lines.append(f"- Verificação de queries e acessos a I/O")
        
        if len(ctx.components) > 0:
            complex_components = sorted(ctx.components.values(), key=lambda c: -c.complexity)[:3]
            if complex_components:
                lines.append(f"\nComponentes mais complexos detectados:")
                for c in complex_components[:3]:
                    lines.append(f"- `{c.name}` (complexidade estimada: {c.complexity:.0f})")
        
        lines.append(f"\n⏳ Iniciando análise de performance...")
        return '\n'.join(lines)
    
    def _migrate_response(self, ctx, name, lang, target):
        lines = [f"Preparando migração de **{name}** de {lang.capitalize()} para **{target.capitalize()}**."]
        
        lines.append(f"\nVou mapear:")
        lines.append(f"- Estrutura de diretórios → equivalente em {target.capitalize()}")
        lines.append(f"- Dependências → pacotes equivalentes")
        lines.append(f"- Padrões de código → idioms de {target.capitalize()}")
        
        if ctx.frameworks:
            lines.append(f"\nFrameworks atuais: **{', '.join(ctx.frameworks[:3])}**")
            lines.append(f"Vou encontrar equivalentes em {target.capitalize()}.")
        
        lines.append(f"\n⏳ Iniciando análise de migração...")
        return '\n'.join(lines)
    
    def _explain_response(self, ctx, name, lang):
        if lang == "unknown":
            return f"Ainda estou analisando **{name}** para entender sua arquitetura. Me dê um momento."
        
        lines = [f"Análise arquitetural de **{name}**:"]
        lines.append(f"\n- **Linguagem:** {lang.capitalize()}")
        
        if ctx.frameworks:
            lines.append(f"- **Frameworks:** {', '.join(ctx.frameworks)}")
        
        lines.append(f"- **Arquitetura:** {ctx.architecture.value}")
        lines.append(f"- **Arquivos:** {ctx.file_count} ({ctx.total_lines} linhas)")
        lines.append(f"- **Entry point:** {ctx.entry_point or 'não identificado'}")
        
        if ctx.purpose:
            lines.append(f"- **Propósito:** {ctx.purpose[:100]}")
        
        if ctx.components:
            lines.append(f"\n**Principais componentes:**")
            for name, comp in list(ctx.components.items())[:5]:
                deps = len(comp.dependencies)
                lines.append(f"- `{name}` ({comp.type}) — {deps} dependências")
        
        if ctx.data_flows:
            lines.append(f"\n**Fluxo principal:**")
            for flow in ctx.data_flows[:1]:
                lines.append(f"  {' → '.join(flow[:8])}")
        
        return '\n'.join(lines)
    
    def _test_response(self, ctx, name):
        if ctx.has_tests:
            return f"**{name}** já tem testes configurados. Vou executá-los e analisar a cobertura."
        else:
            return f"**{name}** não tem testes automatizados. Vou gerar uma suíte de testes baseada nos componentes identificados ({len(ctx.components)} componentes)."
    
    def _general_response(self, ctx, name, lang, files):
        if lang == "unknown":
            return f"Estou analisando **{name}** para entender sua estrutura. Me dê um instante."
        
        lines = [f"Analisei **{name}** e encontrei:"]
        lines.append(f"- Projeto **{lang.capitalize()}** com **{files} arquivos**")
        if ctx.frameworks:
            lines.append(f"- Frameworks: **{', '.join(ctx.frameworks[:3])}**")
        if ctx.purpose:
            lines.append(f"- Propósito: {ctx.purpose[:100]}")
        lines.append(f"- Health Score: **{ctx.health_score:.0f}/100**")
        
        if ctx.risks:
            critical = [r for r in ctx.risks if r.severity == RiskLevel.CRITICAL]
            high = [r for r in ctx.risks if r.severity == RiskLevel.HIGH]
            if critical or high:
                lines.append(f"\n⚠️  Encontrei **{len(critical)} riscos críticos** e **{len(high)} riscos altos**.")
                lines.append(f"Quer que eu corrija?")
        
        lines.append(f"\nComo posso ajudar? Posso:")
        lines.append(f"- 🔧 Corrigir bugs e vulnerabilidades")
        lines.append(f"- 🔍 Auditar segurança")
        lines.append(f"- ⚡ Otimizar performance")
        lines.append(f"- 📝 Gerar testes e documentação")
        
        return '\n'.join(lines)
    
    # ──── Estado ────────────────────────────────────────────────────
    
    def get_state(self) -> ConversationState:
        return self.state
    
    def get_conversation_summary(self) -> Dict:
        return {
            "turns": len(self.conversation),
            "state": self.state.value,
            "user_intent": self.context.user_intent if self.context else "",
            "discoveries": [t.discoveries for t in self.conversation if t.speaker == "ai"],
            "pending_questions": self._get_pending_questions(),
        }
    
    def _get_pending_questions(self) -> List[str]:
        """Retorna perguntas que a IA ainda quer fazer."""
        questions = []
        if self.context:
            if not self.context.expected_behavior:
                questions.append("Como o projeto deveria funcionar?")
            if not self.context.current_error and self.context.user_intent == "repair":
                questions.append("Qual erro específico você está vendo?")
            if self.context.risks and not self.context.user_intent:
                questions.append(f"Encontrei {len(self.context.risks)} riscos. Quer que eu corrija?")
        return questions
    
    def reset(self):
        """Reseta a conversa."""
        self.state = ConversationState.IDLE
        self.conversation = []
        self.context = None


# Global
local_ai = LocalAI()
