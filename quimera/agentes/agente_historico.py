# quimera/agentes/agente_historico.py

import logging
import json
from pathlib import Path
from typing import Dict, List, Optional
import os  # <<< CORREÇÃO APLICADA AQUI

from quimera.quadro_negro import QuadroNegro

logger = logging.getLogger(__name__)

PATCHBASE_PATH = "quimera/dados/patchbase_full_1000.json"

class AgenteHistoriador:
    """
    Agente especialista em analisar a base de dados de patches históricos
    para encontrar padrões, confirmar diagnósticos e extrair insights.
    """
    _instance = None
    _patch_database: List[Dict] = []

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AgenteHistoriador, cls).__new__(cls)
            cls._instance._load_patchbase()
        return cls._instance

    def _load_patchbase(self):
        """Carrega a base de dados de patches do arquivo JSON."""
        db_path = Path(PATCHBASE_PATH)
        if not db_path.exists():
            logger.warning(f"Base de dados de patches em '{PATCHBASE_PATH}' não encontrada.")
            return

        try:
            with open(db_path, 'r', encoding='utf-8') as f:
                self._patch_database = json.load(f)
            logger.info(f"AgenteHistoriador carregou {len(self._patch_database)} patches da base de dados.")
        except Exception as e:
            logger.error(f"Falha ao carregar a base de dados de patches: {e}", exc_info=True)

    def analisar_diagnostico(self, diagnostico_analista: Dict) -> Dict:
        """
        Compara o diagnóstico de um AgenteAnalista com a base de dados histórica.

        Args:
            diagnostico_analista (Dict): A saída JSON do EngenheiroDebug.

        Returns:
            Um dicionário com insights e uma pontuação de confiança histórica.
        """
        if not self._patch_database:
            return {"confianca": 0.5, "insight": "Base de dados histórica não disponível."}

        tipo_erro_analisado = diagnostico_analista.get("causa_raiz", "").lower()
        arquivo_afetado = diagnostico_analista.get("arquivo_afetado", "")

        casos_relevantes = []
        for caso in self._patch_database:
            # Busca por casos com o mesmo tipo de erro no mesmo subsistema
            dir_caso = os.path.dirname(caso["arquivos_afetados"][0]) if caso.get("arquivos_afetados") else ""
            dir_analisado = os.path.dirname(arquivo_afetado)

            if caso.get("erro_tipo", "").lower() in tipo_erro_analisado and dir_caso == dir_analisado:
                casos_relevantes.append(caso)

        if not casos_relevantes:
            return {"confianca": 0.6, "insight": "Nenhum caso histórico diretamente correspondente encontrado. A análise do LLM é a melhor fonte."}

        # Gera insights a partir dos casos encontrados
        total_casos = len(casos_relevantes)
        categorias = [c.get("categoria") for c in casos_relevantes]
        categoria_comum = max(set(categorias), key=categorias.count) if categorias else "N/A"

        insight = (
            f"Análise histórica encontrou {total_casos} caso(s) similar(es) neste subsistema. "
            f"A categoria de correção mais comum foi '{categoria_comum}'. "
            "Isso aumenta a confiança no diagnóstico atual."
        )

        # Retorna o patch mais recente como o melhor exemplo
        caso_exemplo = sorted(casos_relevantes, key=lambda x: x.get('data_commit', '1970-01-01'), reverse=True)[0]

        return {
            "confianca": 0.9, # Alta confiança, pois há precedentes
            "insight": insight,
            "melhor_exemplo_historico": caso_exemplo
        }