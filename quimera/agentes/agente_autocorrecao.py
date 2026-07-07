"""
Agente de Autocorreção Avançado para o Sistema Quimera
Sistema de autocorreção inteligente que monitora e corrige falhas do próprio sistema
"""

import sys
import asyncio
import logging
import json
import os
import time
import traceback
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque

from quimera.logs.parser import montar_log
from quimera.quadro_negro import QuadroNegro
try:
    from quimera.agentes.roteador_modelos import RoteadorModelos
except ImportError:
    RoteadorModelos = None  # RoteadorModelos não disponível
from quimera.core.knowledge_base import KnowledgeBase
from quimera.db.base import get_db
from quimera.db import service as db_service
from quimera import config

logger = logging.getLogger(__name__)


@dataclass
class FalhaDetectada:
    """Representa uma falha detectada no sistema"""
    timestamp: datetime
    tipo: str  # 'patch_invalido', 'erro_compilacao', 'timeout', 'excecao'
    componente: str  # qual agente/módulo falhou
    detalhes: Dict[str, Any]
    severidade: str  # 'baixa', 'media', 'alta', 'critica'
    tentativas_correcao: int = 0
    corrigida: bool = False
    estrategias_tentadas: List[str] = field(default_factory=list)


@dataclass
class MetricaPerformance:
    """Métricas de performance do sistema"""
    timestamp: datetime
    taxa_sucesso_patches: float
    tempo_medio_geracao: float
    taxa_erro_compilacao: float
    memoria_utilizada: float
    cpu_utilizada: float
    agentes_ativos: int


class MonitorInteligente:
    """Monitor inteligente que detecta padrões de falha"""

    def __init__(self):
        self.historico_falhas = deque(maxlen=1000)
        self.metricas_performance = deque(maxlen=100)
        self.padroes_falha = defaultdict(int)
        self.alertas_ativos = set()

    def registrar_falha(self, falha: FalhaDetectada):
        """Registra uma nova falha e analisa padrões"""
        self.historico_falhas.append(falha)

        # Detectar padrões de falha
        padrao_key = f"{falha.tipo}_{falha.componente}"
        self.padroes_falha[padrao_key] += 1

        # Alertar se padrão crítico detectado
        if self.padroes_falha[padrao_key] >= 3:
            self.alertas_ativos.add(f"PADRÃO_CRÍTICO_{padrao_key}")
            montar_log(f"ALERTA: Padrão crítico detectado - {padrao_key} ({self.padroes_falha[padrao_key]} ocorrências)", "CRITICAL")

    def analisar_tendencias(self) -> Dict[str, Any]:
        """Analisa tendências nas falhas e performance"""
        if len(self.historico_falhas) < 5:
            return {"status": "dados_insuficientes"}

        # Análise temporal das falhas
        agora = datetime.now()
        falhas_recentes = [f for f in self.historico_falhas if f.timestamp > agora - timedelta(hours=1)]

        # Análise por componente
        falhas_por_componente = defaultdict(int)
        for falha in falhas_recentes:
            falhas_por_componente[falha.componente] += 1

        # Análise por tipo
        falhas_por_tipo = defaultdict(int)
        for falha in falhas_recentes:
            falhas_por_tipo[falha.tipo] += 1

        return {
            "status": "ok",
            "falhas_ultima_hora": len(falhas_recentes),
            "componente_mais_problematico": max(falhas_por_componente.items(), key=lambda x: x[1]) if falhas_por_componente else None,
            "tipo_falha_mais_comum": max(falhas_por_tipo.items(), key=lambda x: x[1]) if falhas_por_tipo else None,
            "alertas_ativos": list(self.alertas_ativos),
            "padroes_detectados": dict(self.padroes_falha)
        }


class EstrategiaCorrecao:
    """Estratégias de correção para diferentes tipos de falha"""

    @staticmethod
    async def corrigir_patch_invalido(detalhes: Dict[str, Any], quadro_negro: QuadroNegro) -> bool:
        """Corrige problemas com patches inválidos"""
        montar_log("Aplicando estratégia de correção para patch inválido", "INFO")

        # Estratégia 1: Regenerar patch com modelo diferente
        try:
            # Forçar uso de modelo mais conservador ou de um modelo diferente
            quadro_negro.publicar_artefato("FORCE_REGENERATION_STRATEGY", {"strategy": "conservative_fallback"}, "AutoCorrecao")
            montar_log("Sinalizando para usar estratégia de regeneração conservadora.", "INFO")
            return True
        except Exception as e:
            montar_log(f"Falha na correção de patch inválido: {e}", "ERROR")
            return False

    @staticmethod
    async def corrigir_erro_compilacao(detalhes: Dict[str, Any], quadro_negro: QuadroNegro) -> bool:
        """Corrige problemas de compilação persistentes"""
        montar_log("Aplicando estratégia de correção para erro de compilação persistente", "INFO")

        try:
            # Estratégia: Limpar cache e recompilar
            kernel_root = os.getenv("KERNEL_ROOT")
            if kernel_root:
                montar_log("Executando 'make clean' no diretório do kernel...", "INFO")
                # Idealmente, usar asyncio.create_subprocess_shell para não bloquear
                process = await asyncio.create_subprocess_shell(
                    f"cd {kernel_root} && make clean",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await process.communicate()
                if process.returncode == 0:
                    quadro_negro.publicar_artefato("COMPILATION_CACHE_CLEARED", True, "AutoCorrecao")
                    montar_log("Cache de compilação limpo com sucesso.", "SUCCESS")
                    return True
                else:
                    montar_log("Falha ao limpar cache de compilação.", "ERROR")
                    return False
            return False
        except Exception as e:
            montar_log(f"Falha na correção de erro de compilação: {e}", "ERROR")
            return False

    @staticmethod
    async def corrigir_timeout(detalhes: Dict[str, Any], quadro_negro: QuadroNegro) -> bool:
        """Corrige problemas de timeout"""
        montar_log("Aplicando estratégia de correção para timeout", "INFO")

        try:
            # Estratégia: Aumentar timeouts e reduzir complexidade da próxima tarefa
            quadro_negro.publicar_artefato("ADJUST_SYSTEM_PARAMS", {"timeout_multiplier": 1.5, "task_complexity": "low"}, "AutoCorrecao")
            montar_log("Parâmetros do sistema ajustados para lidar com timeouts.", "INFO")
            return True
        except Exception as e:
            montar_log(f"Falha na correção de timeout: {e}", "ERROR")
            return False

    @staticmethod
    async def corrigir_excecao(detalhes: Dict[str, Any], quadro_negro: QuadroNegro) -> bool:
        """Corrige exceções não tratadas no sistema"""
        componente = detalhes.get("componente", "desconhecido")
        montar_log(f"Aplicando estratégia de correção para exceção no componente: {componente}", "INFO")

        try:
            # Estratégia: Reinicializar componentes problemáticos (simulado via quadro-negro)
            quadro_negro.publicar_artefato(f"RESTART_COMPONENT_{componente.upper()}", {"timestamp": datetime.now().isoformat()}, "AutoCorrecao")
            montar_log(f"Sinal de reinicialização enviado para o componente {componente}.", "INFO")
            return True
        except Exception as e:
            montar_log(f"Falha na correção de exceção: {e}", "ERROR")
            return False


class AgenteAutoCorrecao:
    """
    Agente de Autocorreção Avançado
    Monitora o sistema, detecta falhas e aplica correções automaticamente
    """

    def __init__(self, quadro_negro: QuadroNegro):
        self.quadro_negro = quadro_negro
        self.roteador = RoteadorModelos() if RoteadorModelos is not None else None
        try:
            self.knowledge_base = KnowledgeBase()
        except RuntimeError as e:
            montar_log(f"AVISO: KnowledgeBase não inicializada no AgenteAutoCorrecao. Funcionalidades RAG para autocorreção serão desativadas. Erro: {e}", "WARNING")
            self.knowledge_base = None
        self.monitor = MonitorInteligente()
        self.estrategias = EstrategiaCorrecao()

        # Estado interno
        self.ativo = False
        self.ciclos_monitoramento = 0
        self.ultima_verificacao = datetime.now()

        # Configurações
        self.intervalo_monitoramento = 30  # segundos
        self.max_tentativas_correcao = 3
        self.timeout_correcao = 300  # 5 minutos

        montar_log("AgenteAutoCorrecao inicializado", "INFO")

    async def iniciar_monitoramento(self):
        """Inicia o monitoramento contínuo do sistema em background"""
        if self.ativo:
            montar_log("Monitoramento de autocorreção já está ativo.", "WARNING")
            return

        self.ativo = True
        montar_log("Iniciando monitoramento contínuo de autocorreção...", "INFO")

        async def loop_monitoramento():
            while self.ativo:
                try:
                    await self._ciclo_monitoramento()
                    await asyncio.sleep(self.intervalo_monitoramento)
                except asyncio.CancelledError:
                    montar_log("Loop de monitoramento cancelado.", "INFO")
                    break
                except Exception as e:
                    montar_log(f"Erro crítico no ciclo de monitoramento: {e}", "CRITICAL", exc_info=True)
                    await asyncio.sleep(self.intervalo_monitoramento * 2)  # Backoff em caso de erro

        asyncio.create_task(loop_monitoramento())

    def parar_monitoramento(self):
        """Para o monitoramento"""
        self.ativo = False
        montar_log("Monitoramento de autocorreção parado.", "INFO")

    async def _ciclo_monitoramento(self):
        """Executa um ciclo completo de monitoramento"""
        self.ciclos_monitoramento += 1
        self.ultima_verificacao = datetime.now()

        # 1. Coletar métricas do sistema
        await self._coletar_metricas()

        # 2. Detectar falhas
        falhas_detectadas = await self._detectar_falhas()

        # 3. Analisar padrões
        analise_tendencias = self.monitor.analisar_tendencias()

        # 4. Aplicar correções se necessário
        if falhas_detectadas:
            await self._aplicar_correcoes(falhas_detectadas)

        # 5. Otimizar sistema se necessário
        if self.ciclos_monitoramento % 10 == 0:  # A cada 10 ciclos
            await self._otimizar_sistema(analise_tendencias)

        # Log de status
        if self.ciclos_monitoramento % 20 == 0:  # A cada 10 ciclos (~10 min)
            montar_log(f"Autocorreção - Ciclo {self.ciclos_monitoramento}: {len(falhas_detectadas)} falhas detectadas na última verificação.", "DEBUG")

    async def _coletar_metricas(self) -> MetricaPerformance:
        """Coleta métricas de performance do sistema"""
        try:
            # Coletar dados do quadro negro
            artefatos = self.quadro_negro.listar_artefatos()

            # Calcular métricas básicas
            patches_gerados = len([a for a in artefatos if 'PATCH_INTELIGENTE' in a])
            patches_validos = len([a for a in artefatos if 'PATCH_INTELIGENTE' in a and self.quadro_negro.obter_artefato(a).get('valido', False)])

            taxa_sucesso = (patches_validos / max(patches_gerados, 1)) if patches_gerados > 0 else 0.0

            # Métricas de sistema (usando psutil)
            try:
                import psutil
                process = psutil.Process(os.getpid())
                memoria_utilizada = process.memory_info().rss / (1024 * 1024) # em MB
                cpu_utilizada = process.cpu_percent(interval=0.1)
            except ImportError:
                memoria_utilizada = 0.0
                cpu_utilizada = 0.0

            metrica = MetricaPerformance(
                timestamp=datetime.now(),
                taxa_sucesso_patches=taxa_sucesso,
                tempo_medio_geracao=30.0,  # Simulado - seria calculado do histórico de missões
                taxa_erro_compilacao=0.1,  # Simulado - seria calculado do histórico
                memoria_utilizada=memoria_utilizada,
                cpu_utilizada=cpu_utilizada,
                agentes_ativos=len(self.roteador.obter_nomes_modelos_para_habilidade('geracao_patch_elite'))
            )

            self.monitor.metricas_performance.append(metrica)
            return metrica

        except Exception as e:
            montar_log(f"Erro ao coletar métricas: {e}", "ERROR")
            return MetricaPerformance(timestamp=datetime.now(), taxa_sucesso_patches=0.0, tempo_medio_geracao=0.0, taxa_erro_compilacao=1.0, memoria_utilizada=0.0, cpu_utilizada=0.0, agentes_ativos=0)

    async def _detectar_falhas(self) -> List[FalhaDetectada]:
        """Detecta falhas no sistema a partir de artefatos do Quadro Negro"""
        falhas = []

        try:
            artefatos = self.quadro_negro.listar_artefatos_desde(self.ultima_verificacao - timedelta(seconds=self.intervalo_monitoramento))

            for key, artefato_data in artefatos.items():
                if 'FALHA' in key or 'ERRO' in key:
                    tipo_falha = 'excecao'
                    componente = artefato_data.get('origem', 'desconhecido')
                    severidade = 'alta'

                    if 'COMPILACAO' in key:
                        tipo_falha = 'erro_compilacao'
                    elif 'PATCH' in key:
                        tipo_falha = 'patch_invalido'
                    elif 'TIMEOUT' in key:
                        tipo_falha = 'timeout'

                    falha = FalhaDetectada(
                        timestamp=artefato_data.get('timestamp', datetime.now()),
                        tipo=tipo_falha,
                        componente=componente,
                        detalhes=artefato_data,
                        severidade=severidade
                    )
                    falhas.append(falha)
                    self.monitor.registrar_falha(falha)

        except Exception as e:
            montar_log(f"Erro na detecção de falhas: {e}", "ERROR")
            falha = FalhaDetectada(
                timestamp=datetime.now(),
                tipo='excecao',
                componente='agente_autocorrecao',
                detalhes={'erro': str(e), 'traceback': traceback.format_exc()},
                severidade='critica'
            )
            falhas.append(falha)
            self.monitor.registrar_falha(falha)

        return falhas

    async def _aplicar_correcoes(self, falhas: List[FalhaDetectada]):
        """Aplica correções para as falhas detectadas"""
        for falha in falhas:
            if falha.tentativas_correcao >= self.max_tentativas_correcao or falha.corrigida:
                continue

            montar_log(f"Tentando aplicar correção para falha: {falha.tipo} no componente {falha.componente}", "INFO")

            try:
                sucesso = False
                estrategia = "nenhuma"

                if falha.tipo == 'patch_invalido':
                    estrategia = "corrigir_patch_invalido"
                    sucesso = await self.estrategias.corrigir_patch_invalido(falha.detalhes, self.quadro_negro)
                elif falha.tipo == 'erro_compilacao':
                    estrategia = "corrigir_erro_compilacao"
                    sucesso = await self.estrategias.corrigir_erro_compilacao(falha.detalhes, self.quadro_negro)
                elif falha.tipo == 'timeout':
                    estrategia = "corrigir_timeout"
                    sucesso = await self.estrategias.corrigir_timeout(falha.detalhes, self.quadro_negro)
                elif falha.tipo == 'excecao':
                    estrategia = "corrigir_excecao"
                    sucesso = await self.estrategias.corrigir_excecao(falha.detalhes, self.quadro_negro)

                falha.tentativas_correcao += 1
                falha.estrategias_tentadas.append(estrategia)

                if sucesso:
                    falha.corrigida = True
                    montar_log(f"Correção ({estrategia}) aplicada com sucesso para {falha.tipo}", "SUCCESS")
                else:
                    montar_log(f"Correção ({estrategia}) falhou para {falha.tipo}", "WARNING")

            except Exception as e:
                montar_log(f"Erro ao aplicar correção para {falha.tipo}: {e}", "ERROR", exc_info=True)
                falha.tentativas_correcao += 1

    async def _otimizar_sistema(self, analise_tendencias: Dict[str, Any]):
        """Otimiza o sistema baseado na análise de tendências"""
        try:
            if analise_tendencias.get("status") != "ok":
                return

            # Otimização baseada no componente mais problemático
            componente_problematico_info = analise_tendencias.get("componente_mais_problematico")
            if componente_problematico_info:
                componente, count = componente_problematico_info
                if count > 5:  # Threshold para otimização
                    montar_log(f"Otimizando componente problemático: {componente}", "INFO")
                    self.quadro_negro.publicar_artefato(f"OPTIMIZE_COMPONENT_{componente.upper()}", True, "AutoCorrecao")

            # Otimização baseada no tipo de falha mais comum
            tipo_falha_comum_info = analise_tendencias.get("tipo_falha_mais_comum")
            if tipo_falha_comum_info:
                tipo, count = tipo_falha_comum_info
                if count > 3:
                    montar_log(f"Aplicando otimização preventiva para tipo de falha: {tipo}", "INFO")
                    self.quadro_negro.publicar_artefato(f"PREVENT_FAILURE_{tipo.upper()}", True, "AutoCorrecao")

        except Exception as e:
            montar_log(f"Erro na otimização do sistema: {e}", "ERROR")

    def obter_relatorio_status(self) -> Dict[str, Any]:
        """Gera relatório de status da autocorreção"""
        analise_tendencias = self.monitor.analisar_tendencias()

        taxa_sucesso_media = sum(m.taxa_sucesso_patches for m in self.monitor.metricas_performance) / max(len(self.monitor.metricas_performance), 1) if self.monitor.metricas_performance else 0
        memoria_media = sum(m.memoria_utilizada for m in self.monitor.metricas_performance) / max(len(self.monitor.metricas_performance), 1) if self.monitor.metricas_performance else 0
        cpu_media = sum(m.cpu_utilizada for m in self.monitor.metricas_performance) / max(len(self.monitor.metricas_performance), 1) if self.monitor.metricas_performance else 0

        return {
            "ativo": self.ativo,
            "ciclos_executados": self.ciclos_monitoramento,
            "ultima_verificacao": self.ultima_verificacao.isoformat(),
            "total_falhas_historico": len(self.monitor.historico_falhas),
            "falhas_corrigidas": len([f for f in self.monitor.historico_falhas if f.corrigida]),
            "analise_tendencias": analise_tendencias,
            "metricas_recentes": {
                "taxa_sucesso_media": taxa_sucesso_media,
                "memoria_media_mb": memoria_media,
                "cpu_media_percent": cpu_media
            }
        }

    async def diagnostico_completo(self) -> Dict[str, Any]:
        """Executa um diagnóstico completo do sistema"""
        montar_log("Executando diagnóstico completo do sistema de autocorreção", "INFO")

        # Coletar todas as informações disponíveis
        metricas = await self._coletar_metricas()
        falhas = await self._detectar_falhas() # Detecta apenas falhas recentes
        relatorio = self.obter_relatorio_status()

        # Análise de saúde geral
        saude_geral = "excelente"
        if len(self.monitor.historico_falhas) > 10: saude_geral = "bom"
        if len(self.monitor.historico_falhas) > 50: saude_geral = "regular"
        if any(f.severidade in ['alta', 'critica'] for f in self.monitor.historico_falhas): saude_geral = "ruim"

        diagnostico = {
            "timestamp": datetime.now().isoformat(),
            "saude_geral": saude_geral,
            "metricas_atuais": {
                "taxa_sucesso_patches": metricas.taxa_sucesso_patches,
                "memoria_utilizada_mb": metricas.memoria_utilizada,
                "cpu_utilizada_percent": metricas.cpu_utilizada,
                "agentes_ativos": metricas.agentes_ativos
            },
            "falhas_ativas": len(falhas),
            "falhas_criticas_ativas": len([f for f in falhas if f.severidade == 'critica']),
            "relatorio_completo": relatorio,
            "recomendacoes": self._gerar_recomendacoes(falhas, metricas)
        }

        return diagnostico

    def _gerar_recomendacoes(self, falhas: List[FalhaDetectada], metricas: MetricaPerformance) -> List[str]:
        """Gera recomendações baseadas no estado atual"""
        recomendacoes = []

        # Recomendações baseadas em falhas
        if len(falhas) > 5:
            recomendacoes.append("Sistema está enfrentando um número elevado de falhas simultâneas. Considere uma reinicialização completa se a autocorreção não estabilizar o sistema.")

        if any(f.severidade == 'critica' for f in falhas):
            recomendacoes.append("Falhas críticas detectadas. Intervenção manual pode ser necessária se a autocorreção falhar.")

        # Recomendações baseadas em métricas
        if metricas.taxa_sucesso_patches < 0.5 and self.ciclos_monitoramento > 20:
            recomendacoes.append("Taxa de sucesso de patches persistentemente baixa. Recomenda-se revisar os modelos de IA ou prompts de geração.")

        if metricas.memoria_utilizada > 90:
            recomendacoes.append("Uso de memória está criticamente alto. O sistema pode se tornar instável. Considere aumentar a memória disponível ou investigar vazamentos.")

        if metricas.cpu_utilizada > 90:
            recomendacoes.append("Uso de CPU persistentemente alto. Verifique por loops infinitos ou tarefas de alta intensidade.")

        if not recomendacoes:
            recomendacoes.append("Sistema operando dentro dos parâmetros normais.")

        return recomendacoes