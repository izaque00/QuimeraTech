# quimera/quadro_negro.py
import redis
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

logger = logging.getLogger("QuadroNegro")

class QuadroNegroError(Exception):
    """Exceção personalizada para erros do Quadro Negro."""
    pass

class QuadroNegro:
    """
    Sistema de gerenciamento de conhecimento compartilhado e persistente entre agentes.
    Implementado com Redis para alta performance e persistência de dados.
    """

    def __init__(self, host: str = 'localhost', port: int = 6379, db: int = 0):
        """
        Inicializa a conexão com o banco de dados Redis.

        Args:
            host (str): O host do servidor Redis.
            port (int): A porta do servidor Redis.
            db (int): O número do banco de dados Redis a ser usado.
        """
        try:
            self.redis = redis.StrictRedis(
                host=host,
                port=port,
                db=db,
                decode_responses=True # Garante que as respostas sejam strings
            )
            self.redis.ping()
            logger.info(f"Quadro Negro conectado com sucesso ao Redis em {host}:{port}/{db}.")
        except redis.exceptions.ConnectionError as e:
            logger.critical(f"Falha CRÍTICA na conexão com Redis: {e}. O Quadro Negro não pode operar.")
            raise QuadroNegroError(f"Não foi possível conectar ao Redis: {e}")

    def _serializar(self, data: Any) -> str:
        """Serializa dados Python para uma string JSON."""
        return json.dumps(data)

    def _desserializar(self, data_str: Optional[str]) -> Any:
        """Desserializa uma string JSON para dados Python, com tratamento de erro."""
        if data_str is None:
            return None
        try:
            return json.loads(data_str)
        except json.JSONDecodeError:
            logger.warning(f"Erro ao desserializar dados do Quadro Negro. Retornando dados brutos.")
            return data_str

    def publicar_artefato(self, chave: str, conteudo: Any, autor: str, metadados: Optional[Dict] = None, ttl: Optional[int] = 86400):
        """
        Publica um novo artefato de conhecimento no Quadro Negro.

        Args:
            chave (str): A chave única para o artefato.
            conteudo (Any): O dado a ser armazenado.
            autor (str): O nome do agente ou sistema que publicou o artefato.
            metadados (Optional[Dict]): Dicionário com informações adicionais.
            ttl (Optional[int]): Tempo de vida do artefato em segundos. Se None, persiste indefinidamente.
        """
        try:
            artefato = {
                "conteudo": conteudo,
                "autor": autor,
                "timestamp": datetime.now().isoformat(),
                "metadados": metadados or {}
            }
            artefato_serializado = self._serializar(artefato)

            if ttl:
                self.redis.setex(chave, ttl, artefato_serializado)
            else:
                self.redis.set(chave, artefato_serializado)

            logger.info(f"Artefato '{chave}' publicado por '{autor}'.")
        except Exception as e:
            logger.error(f"Falha ao publicar artefato '{chave}': {e}", exc_info=True)
            raise QuadroNegroError(f"Erro ao publicar no Redis: {e}")

    def obter_artefato(self, chave: str) -> Optional[Dict]:
        """
        Busca um artefato completo (conteúdo e metadados) pela sua chave.

        Args:
            chave (str): A chave exata do artefato.

        Returns:
            Um dicionário representando o artefato, ou None se não encontrado.
        """
        try:
            artefato_serializado = self.redis.get(chave)
            if artefato_serializado:
                return self._desserializar(artefato_serializado)
            logger.debug(f"Artefato com chave '{chave}' não encontrado.")
            return None
        except Exception as e:
            logger.error(f"Falha ao obter artefato '{chave}': {e}", exc_info=True)
            return None

    def obter_conteudo_artefato(self, chave: str) -> Optional[Any]:
        """Busca apenas o campo 'conteudo' de um artefato."""
        artefato = self.obter_artefato(chave)
        return artefato.get("conteudo") if artefato else None

    def atualizar_artefato(self, chave: str, novos_dados: Dict):
        """
        Atualiza um artefato existente, mesclando os novos dados.
        Preserva o autor e o timestamp original, mas adiciona um timestamp de atualização.
        """
        artefato_atual = self.obter_artefato(chave)
        if not artefato_atual:
            logger.warning(f"Tentativa de atualizar artefato inexistente: '{chave}'.")
            return

        # Mescla o conteúdo e os metadados
        conteudo_atual = artefato_atual.get("conteudo", {})
        if isinstance(conteudo_atual, dict) and isinstance(novos_dados, dict):
            conteudo_atual.update(novos_dados)
            artefato_atual["conteudo"] = conteudo_atual
        else:
            artefato_atual["conteudo"] = novos_dados # Sobrescreve se não forem dicionários

        artefato_atual["timestamp_atualizacao"] = datetime.now().isoformat()

        try:
            self.redis.set(chave, self._serializar(artefato_atual))
            logger.info(f"Artefato '{chave}' atualizado.")
        except Exception as e:
            logger.error(f"Falha ao atualizar artefato '{chave}': {e}", exc_info=True)
            raise QuadroNegroError(f"Erro ao atualizar no Redis: {e}")

    def listar_chaves(self, padrao: str = "*") -> List[str]:
        """
        Lista todas as chaves no Quadro Negro que correspondem a um padrão.

        Args:
            padrao (str): Padrão de busca (ex: "Log_Compilacao_*").

        Returns:
            Lista de chaves correspondentes.
        """
        return self.redis.keys(padrao)

    def reiniciar(self, prefixo: Optional[str] = None):
        """
        Limpa o Quadro Negro. Se um prefixo for fornecido, apaga apenas as chaves
        que começam com ele. Caso contrário, apaga todo o banco de dados.

        Args:
            prefixo (Optional[str]): Prefixo das chaves a serem removidas.
        """
        if prefixo:
            chaves_para_deletar = self.listar_chaves(f"{prefixo}*")
            if chaves_para_deletar:
                self.redis.delete(*chaves_para_deletar)
                logger.info(f"{len(chaves_para_deletar)} artefatos com prefixo '{prefixo}' removidos.")
            else:
                logger.info(f"Nenhum artefato com prefixo '{prefixo}' para remover.")
        else:
            self.redis.flushdb()
            logger.warning("Quadro Negro completamente reiniciado (FLUSHDB). Todos os dados foram perdidos.")