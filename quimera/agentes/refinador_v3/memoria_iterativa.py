# quimera/agentes/refinador_v3/memoria_iterativa.py

import json
import os
import logging
from pathlib import Path
from typing import List, Dict, Any

from quimera.logs.parser import montar_log

logger = logging.getLogger(__name__)

class MemoriaIterativa:
    """
    Sistema de persistência robusto para o histórico completo do processo de refinamento.

    Salva a árvore de mutações, avaliações e scores em um arquivo JSON estruturado,
    facilitando a análise pós-missão, a depuração de estratégias de refinamento e
    o re-treinamento de modelos futuros. É resiliente a erros de I/O e lida
    com a serialização de objetos complexos.
    """
    def __init__(self, dir_base: str = "quimera/dados/refinador_memoria"):
        """
        Inicializa a memória iterativa, garantindo que o diretório de destino exista.
        Implementa um fallback para /tmp em caso de problemas de permissão.

        Args:
            dir_base (str): O diretório base onde os logs de refinamento serão salvos.
        """
        self.dir_base = Path(dir_base)
        try:
            self.dir_base.mkdir(parents=True, exist_ok=True)
            montar_log(f"Diretório de memória do refinador está em: {self.dir_base.resolve()}", "INFO")
        except OSError as e:
            montar_log(f"Não foi possível criar o diretório de memória em '{dir_base}': {e}. Tentando fallback para /tmp.", "WARNING")
            # Fallback para um diretório temporário se o principal não puder ser criado
            self.dir_base = Path("/tmp/quimera_refinador_memoria")
            self.dir_base.mkdir(parents=True, exist_ok=True)
            montar_log(f"Usando diretório de fallback para memória do refinador: {self.dir_base.resolve()}", "WARNING")

    def salvar(self, patch_id: str, historico: List[Dict[str, Any]]):
        """
        Salva o histórico de refinamento de um patch em um arquivo JSON.
        Limpa os dados de objetos não-serializáveis antes de salvar.

        Args:
            patch_id (str): Um ID único para o patch (geralmente um hash SHA-256).
            historico (List[Dict[str, Any]]): Uma lista de dicionários, cada um
                                               representando uma iteração do refinamento.
        """
        if not patch_id or patch_id == "empty_patch":
            montar_log("ID do patch é nulo ou vazio. Não é possível salvar o histórico do refinamento.", "ERROR")
            return

        path_arquivo = self.dir_base / f"{patch_id}.json"

        try:
            # Prepara o histórico para serialização, evitando objetos complexos.
            # A avaliação completa pode conter objetos não serializáveis, como clientes LLM.
            # Esta função de limpeza garante que apenas dados puros sejam salvos.
            historico_serializavel = self._limpar_historico_para_json(historico)

            with open(path_arquivo, "w", encoding="utf-8") as f:
                json.dump(historico_serializavel, f, indent=2, ensure_ascii=False)
            montar_log(f"Histórico de refinamento para o patch ID '{patch_id}' salvo em: {path_arquivo}", "INFO")

        except (TypeError, IOError) as e:
            montar_log(f"Falha ao salvar o histórico de refinamento para o patch ID '{patch_id}': {e}", "CRITICAL", exc_info=True)

    def _limpar_historico_para_json(self, historico: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Percorre a lista de histórico e remove chaves que podem conter
        objetos não-serializáveis, como clientes de LLM ou outras classes complexas.
        """
        historico_limpo = []
        for item in historico:
            item_limpo = item.copy() # Evita modificar o dicionário original

            # Navega na estrutura aninhada para limpar a avaliação
            if "avaliacao" in item_limpo and isinstance(item_limpo["avaliacao"], dict):
                avaliacao_limpa = item_limpo["avaliacao"].copy()

                if "detalhes" in avaliacao_limpa and isinstance(avaliacao_limpa["detalhes"], dict):
                    detalhes_limpos = avaliacao_limpa["detalhes"].copy()

                    # Limpa a avaliação lógica do LLM se existir
                    if "avaliacao_logica_llm" in detalhes_limpos and isinstance(detalhes_limpos["avaliacao_logica_llm"], dict):
                        avaliacao_llm_limpa = detalhes_limpos["avaliacao_logica_llm"].copy()
                        # Remove chaves que podem conter objetos de classe
                        avaliacao_llm_limpa.pop('cliente_llm', None)
                        detalhes_limpos["avaliacao_logica_llm"] = avaliacao_llm_limpa

                    avaliacao_limpa["detalhes"] = detalhes_limpos

                item_limpo["avaliacao"] = avaliacao_limpa

            historico_limpo.append(item_limpo)

        return historico_limpo