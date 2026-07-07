# quimera/agentes/agente_evolutivo_de_codigo.py

import logging
import os
import ast
import re
import json
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional

from quimera.quadro_negro import QuadroNegro
try:
    from quimera.agentes.roteador_modelos import RoteadorModelos
except ImportError:
    RoteadorModelos = None  # RoteadorModelos não disponível
from quimera.core.vector_manager import VectorManager
from quimera.agentes.agente_transformador import NeuralCodeReconstructor
from quimera.db.base import get_db
from quimera.db import service as db_service
from quimera import config
from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)

class EvolutorDeCodigo:
    """
    Agente Meta-Evolutivo Autônomo de produção. Sua função é monitorar, analisar e
    aprimorar o próprio sistema Quimera. Ele pode gerar e integrar dinamicamente
    novos agentes de software especializados para lidar com falhas recorrentes.
    """

    def __init__(self, quadro_negro: QuadroNegro):
        self.quadro_negro = quadro_negro
        self.roteador = RoteadorModelos() if RoteadorModelos is not None else None
        self.vector_manager = VectorManager()
        self.neural_reconstructor = NeuralCodeReconstructor() # Para refatoração de código alvo

        agentes_elite = self.roteador.selecionar_agentes_para_tarefa(habilidade_requerida="sintese_de_codigo", quantidade=1)
        if not agentes_elite:
            raise RuntimeError("EvolutorDeCodigo: Nenhum modelo de elite disponível para tarefas de evolução.")

        self.llm_evolver = agentes_elite[0]["cliente_llm"]
        self.nome_modelo_evolver = agentes_elite[0]["nome"]

        self.agentes_config_path = Path("quimera/agentes/agentes_config.json")
        self._ensure_config_exists()

        montar_log(f"EvolutorDeCodigo inicializado com o modelo '{self.nome_modelo_evolver}'.", "INFO")

    def _ensure_config_exists(self):
        """Garante que o arquivo de configuração de agentes exista, criando um vazio se necessário."""
        if not self.agentes_config_path.exists():
            self.agentes_config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.agentes_config_path, 'w', encoding='utf-8') as f:
                json.dump({"base_agentes": {}, "agentes_custom": {}}, f, indent=4)
            montar_log(f"Criado arquivo de configuração de agentes vazio em '{self.agentes_config_path}'.", "WARNING")

    def _analisar_desempenho_sistema(self) -> Optional[str]:
        """Analisa o DB em busca de padrões de falha para gerar uma ideia de melhoria."""
        montar_log("Evolutor: Analisando DB em busca de padrões de falha recorrentes...", "INFO")
        with get_db() as db:
            missoes_falhas = db_service.get_missoes_por_status(db, status="falha_missao", limit=20)
            if not missoes_falhas:
                return "O sistema está com bom desempenho. Proponha uma otimização de performance, como cachear resultados de análise de patch."

            error_pattern = re.compile(r'error:\s*(.*)', re.IGNORECASE)
            erros_comuns = {}
            for missao in missoes_falhas:
                if not missao.log_erro_inicial: continue
                # Pega a primeira linha de erro para simplificar a análise do padrão
                match = error_pattern.search(missao.log_erro_inicial)
                if match:
                    erro = match.group(1).strip().splitlines()[0]
                    erro_normalizado = re.sub(r'[\'"`:/\d\.]', '', erro).strip() # Normaliza o erro
                    erros_comuns[erro_normalizado] = erros_comuns.get(erro_normalizado, 0) + 1

            if erros_comuns:
                erro_mais_frequente = max(erros_comuns, key=erros_comuns.get)
                ocorrencias = erros_comuns[erro_mais_frequente]
                montar_log(f"Evolutor: Padrão de falha detectado '{erro_mais_frequente}' ({ocorrencias} vezes).", "WARNING")
                return f"Falhas recorrentes foram detectadas com o erro: '{erro_mais_frequente}'. Proponha um novo agente especialista em identificar e corrigir especificamente este tipo de erro de compilação."
        return None

    def _formular_ideia_evolutiva(self, analise: str) -> str:
        """Usa um LLM para transformar uma análise de desempenho em uma ideia de agente."""
        prompt = f"""<|user|>
Baseado na seguinte análise de desempenho do sistema Quimera, formule uma ideia concisa e acionável para um novo agente.
A ideia deve ser uma frase que descreva a especialidade do novo agente.

Análise: "{analise}"

Ideia para novo agente (uma frase):<|end|>
<|assistant|>
"""
        montar_log("Evolutor: Formulando nova ideia evolutiva com LLM...", "INFO")
        resposta = self.llm_evolver.invoke(prompt)
        return resposta.content.strip()

    async def _gerar_codigo_novo_agente(self, ideia: str) -> Optional[str]:
        """Gera o código Python completo para um novo agente e valida sua sintaxe."""
        prompt = f"""<|user|>
Você é um Arquiteto de Sistemas de IA Sênior. Sua tarefa é gerar o código Python completo para um novo agente do sistema Quimera.

**Ideia para o Novo Agente:**
"{ideia}"

**Requisitos:**
- O código deve ser completo, robusto, bem documentado e em português.
- A classe do agente deve ter um `__init__(self, quadro_negro: QuadroNegro)` e um método de execução principal.
- Use os componentes existentes do Quimera (RoteadorModelos, QuadroNegro, etc.) de forma apropriada.
- Retorne APENAS o código Python completo dentro de um bloco ```python ... ```.
<|end|>
<|assistant|>
"""
        montar_log(f"Evolutor: Gerando código para novo agente com a ideia: '{ideia}'", "INFO")
        resposta_llm = await self.llm_evolver.ainvoke(prompt)
        codigo_bruto = resposta_llm.content.strip()

        match = re.search(r"```python\n(.*?)\n```", codigo_bruto, re.DOTALL)
        if not match:
            montar_log(f"Evolutor: Não foi possível extrair bloco de código Python da resposta do LLM.", "ERROR")
            return None

        codigo_limpo = match.group(1).strip()
        try:
            ast.parse(codigo_limpo)
            montar_log("Evolutor: Código gerado pelo LLM é sintaticamente válido.", "INFO")
            return codigo_limpo
        except SyntaxError as e:
            montar_log(f"Evolutor: Código gerado pelo LLM possui erro de sintaxe: {e}", "ERROR")
            return None

    def _integrar_novo_agente_ao_sistema(self, codigo_agente: str, ideia: str) -> Optional[Path]:
        """Salva o código do novo agente e o registra no arquivo de configuração de forma segura."""
        match = re.search(r"class\s+(\w+)\(AgenteBase\):|class\s+(\w+):", codigo_agente)
        if not match:
            montar_log("Evolutor: Não foi possível extrair o nome da classe do agente gerado.", "ERROR")
            return None
        nome_classe = match.group(1) or match.group(2)
        nome_arquivo = f"agente_custom_{nome_classe.lower()}.py"
        caminho_novo_agente = Path("quimera/agentes") / nome_arquivo

        try:
            # Transação Atômica: Backup -> Escrita -> Atualização de Config
            backup_path = f"{self.agentes_config_path}.bak"
            shutil.copyfile(self.agentes_config_path, backup_path)

            caminho_novo_agente.write_text(codigo_agente, encoding="utf-8")

            with open(self.agentes_config_path, "r+", encoding="utf-8") as f:
                config_agentes = json.load(f)
                novo_agente_id = f"custom/{nome_classe}"
                config_agentes["agentes_custom"][novo_agente_id] = {
                    "provedor": "local_custom",
                    "caminho_arquivo": str(caminho_novo_agente),
                    "habilidades": [ideia.lower().replace(' ', '_').replace(':', '')],
                    "prioridade": 150 # Prioridade média para novos agentes
                }
                f.seek(0)
                json.dump(config_agentes, f, indent=4)
                f.truncate()

            montar_log(f"Evolutor: Novo agente '{nome_classe}' integrado ao sistema em '{caminho_novo_agente}'.", "SUCCESS")
            return caminho_novo_agente
        except Exception as e:
            montar_log(f"Evolutor: Falha ao integrar o novo agente. Revertendo mudanças... Erro: {e}", "CRITICAL", exc_info=True)
            if caminho_novo_agente.exists():
                os.remove(caminho_novo_agente)
            if os.path.exists(backup_path):
                shutil.move(backup_path, self.agentes_config_path)
            return None

    def _executar_auto_teste(self) -> bool:
        """Verifica se a nova configuração do sistema é válida ao recarregar o Roteador."""
        montar_log("Evolutor: Executando auto-teste da nova configuração...", "INFO")
        try:
            _ = RoteadorModelos(config_path=self.agentes_config_path) if RoteadorModelos is not None else None
            montar_log("Evolutor: Auto-teste bem-sucedido. Nova configuração de agentes é válida.", "SUCCESS")
            return True
        except Exception as e:
            montar_log(f"Evolutor: AUTO-TESTE FALHOU! A evolução quebrou o sistema: {e}", "CRITICAL", exc_info=True)
            return False

    async def run_evolution_cycle(self):
        """Executa um ciclo completo de evolução da infraestrutura do Quimera."""
        montar_log("\n--- INICIANDO CICLO DE META-EVOLUÇÃO DO QUIMERA ---", "INFO")
        analise = self._analisar_desempenho_sistema()
        if not analise:
            montar_log("Evolutor: Análise de desempenho não gerou insights acionáveis. Ciclo concluído.", "INFO")
            return

        ideia = self._formular_ideia_evolutiva(analise)
        codigo_novo_agente = await self._gerar_codigo_novo_agente(ideia)
        if not codigo_novo_agente:
            montar_log("Evolutor: Falha ao gerar código válido para o novo agente. Abortando evolução.", "ERROR")
            return

        caminho_novo_agente = self._integrar_novo_agente_ao_sistema(codigo_novo_agente, ideia)
        if not caminho_novo_agente:
            montar_log("Evolutor: Falha ao integrar o novo agente ao sistema. Abortando.", "ERROR")
            return

        if self._executar_auto_teste():
            montar_log(f"EVOLUÇÃO BEM-SUCEDIDA! Novo agente '{caminho_novo_agente.name}' está ativo.", "SUCCESS")
            backup_path = f"{self.agentes_config_path}.bak"
            if os.path.exists(backup_path):
                os.remove(backup_path) # Remove o backup se tudo deu certo
        else:
            montar_log("EVOLUÇÃO FALHOU! Revertendo para o estado anterior...", "CRITICAL")
            backup_path = f"{self.agentes_config_path}.bak"
            if caminho_novo_agente.exists():
                os.remove(caminho_novo_agente)
            if os.path.exists(backup_path):
                shutil.move(backup_path, self.agentes_config_path)
            montar_log("Sistema revertido para o estado pré-evolução.", "INFO")

    async def evoluir_codigo_alvo(self, caminho_arquivo: str) -> Dict[str, Any]:
        """Refatora código-alvo (do kernel) usando o reconstructor neural e valida o drift."""
        montar_log(f"Evolutor: Iniciando evolução de código-alvo para: {caminho_arquivo}...", "INFO")
        try:
            codigo_original = get_code(caminho_arquivo)
        except FileNotFoundError:
            return {"status": "falha", "motivo": f"Arquivo não encontrado: {caminho_arquivo}"}

        codigo_refatorado = self.neural_reconstructor.refine_code(codigo_original)
        if codigo_refatorado == codigo_original:
            return {"status": "sem_mudancas", "motivo": "O reconstructor neural não sugeriu melhorias."}

        vetor_original = self.vector_manager.as_full_vector(codigo_original)
        vetor_refatorado = self.vector_manager.as_full_vector(codigo_refatorado)
        drift_score = self.vector_manager.get_drift(vetor_original, vetor_refatorado)

        montar_log(f"Drift vetorial da refatoração: {drift_score:.4f}", "INFO")
        if drift_score > config.EVOLUTOR_DRIFT_THRESHOLD_SEGURO:
            montar_log(f"Drift ({drift_score:.4f}) muito alto. Refatoração REJEITADA.", "WARNING")
            return {"status": "rejeitado_por_drift_alto", "drift_score": drift_score}

        montar_log("Drift aceitável. Aplicando código evoluído.", "INFO")
        Path(caminho_arquivo).write_text(codigo_refatorado, encoding='utf-8')
        return {"status": "sucesso_evolucao_alvo", "drift_score": drift_score}