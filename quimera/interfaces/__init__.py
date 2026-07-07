"""
Interfaces abstratas do sistema Quimera.
Define contratos para todos os componentes principais,
garantindo desacoplamento entre camadas.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class ILLMProvider(ABC):
    """Interface para provedores de LLM.
    
    Toda implementação deve fornecer geração de texto
    e identificação do modelo utilizado.
    """

    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        """Gera texto a partir de um prompt.
        
        Args:
            prompt: Texto de entrada para o modelo.
            **kwargs: Parâmetros adicionais (temperature, max_tokens, etc.)
        
        Returns:
            Texto gerado pelo modelo.
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Retorna o nome do modelo em uso.
        
        Returns:
            Identificador do modelo (ex: 'LLaMA 3 70B Instruct').
        """
        pass


class IBlackboard(ABC):
    """Interface para o Quadro Negro (Blackboard Pattern).
    
    Mecanismo de comunicação entre agentes via espaço de
    dados compartilhado publica-subscreve.
    """

    @abstractmethod
    def publish(self, key: str, value: Any) -> None:
        """Publica um valor no quadro negro.
        
        Args:
            key: Chave de identificação do dado.
            value: Valor a ser publicado.
        """
        pass

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Obtém um valor do quadro negro.
        
        Args:
            key: Chave do dado desejado.
        
        Returns:
            O valor armazenado ou None se não existir.
        """
        pass


class IRetrievalEngine(ABC):
    """Interface para motores de recuperação (RAG).
    
    Define contrato para busca semântica e indexação
    de documentos, independente da implementação subjacente.
    """

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """Executa busca semântica nos documentos indexados.
        
        Args:
            query: Texto da consulta.
            top_k: Número máximo de resultados.
        
        Returns:
            Lista de documentos relevantes com metadados.
        """
        pass

    @abstractmethod
    def add_documents(self, documents: List[str]) -> None:
        """Adiciona documentos ao índice.
        
        Args:
            documents: Lista de textos a serem indexados.
        """
        pass


class IModelRouter(ABC):
    """Interface para roteamento de modelos.
    
    Responsável por selecionar o melhor provedor/modelo
    para uma determinada tarefa, considerando custo,
    disponibilidade e habilidades requeridas.
    """

    @abstractmethod
    def selecionar_agentes_para_tarefa(
        self,
        habilidade_requerida: str,
        quantidade: int = 1,
        nivel_de_investimento: str = "gratuito"
    ) -> List[Dict[str, Any]]:
        """Seleciona agentes para uma tarefa específica.
        
        Args:
            habilidade_requerida: Habilidade necessária (ex: 'sintese_de_codigo').
            quantidade: Número de agentes desejados.
            nivel_de_investimento: Nível de custo aceitável.
        
        Returns:
            Lista de agentes selecionados com seus clientes LLM.
        """
        pass

    @abstractmethod
    def obter_cliente_llm(self, nome_modelo: str) -> Optional[Any]:
        """Obtém um cliente LLM pelo nome do modelo.
        
        Args:
            nome_modelo: Nome do modelo desejado.
        
        Returns:
            Cliente LLM configurado ou None.
        """
        pass
