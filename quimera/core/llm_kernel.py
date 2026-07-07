# quimera/core/llm_kernel.py
import logging
import json
import asyncio
from typing import Dict, Any, Optional, List, Callable
import aiohttp # Para asyncio.ClientSession

# NOTA: Removido import direto de quimera.agentes.roteador_modelos
# para evitar violacao de camadas arquiteturais (core -> agentes).
# O cliente LLM ou uma factory function devem ser injetados.

logger = logging.getLogger("LLM_Kernel")

class LLMQueryEngine:
    """
    Engine para interagir com diferentes modelos de LLM.
    Atua como uma camada centralizada para todas as chamadas LLM do sistema.
    
    NOTA: Este modulo NAO importa diretamente de quimera.agentes para
    manter o desacoplamento de camadas. Use factory_llm_client ou
    passe o cliente_llm diretamente.
    """
    def __init__(
        self,
        nome_modelo: str = 'LLaMA 3 70B Instruct',
        llm_cliente: Any = None,
        factory_llm_client: Optional[Callable[[str], Any]] = None
    ):
        """
        Inicializa o motor de consulta LLM.

        Args:
            nome_modelo: Nome do modelo LLM a ser utilizado.
            llm_cliente: Cliente LLM já instanciado (opcional).
            factory_llm_client: Factory function que recebe nome_modelo e
                              retorna um cliente LLM (opcional).
                              Ex: factory_llm_client = roteador._obter_cliente_llm
        """
        self.nome_modelo = nome_modelo

        if llm_cliente is not None:
            self.llm_cliente = llm_cliente
        elif factory_llm_client is not None:
            self.llm_cliente = factory_llm_client(self.nome_modelo)
        else:
            # Fallback: tenta importar via lazy import para compatibilidade
            # mas loga um WARNING sobre a violacao de camadas
            try:
                from quimera.agentes.roteador_modelos import obter_cliente_llm
                logger.warning(
                    "[LLMQueryEngine] Usando import direto de quimera.agentes. "
                    "Isso viola o desacoplamento de camadas. "
                    "Prefira passar llm_cliente ou factory_llm_client."
                )
                self.llm_cliente = obter_cliente_llm(self.nome_modelo)
            except ImportError:
                self.llm_cliente = None

        if not self.llm_cliente:
            raise Exception(
                f"[{self.__class__.__name__}] Não foi possível criar cliente LLM para "
                f"'{self.nome_modelo}'. Forneça llm_cliente ou factory_llm_client, "
                f"ou verifique a configuração no roteador_modelos.py e as chaves de API."
            )
        logger.info(f"[{self.__class__.__name__}] Inicializado com sucesso com modelo '{self.nome_modelo}'.")

    async def consultar_llm(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        Realiza uma consulta assíncrona ao modelo LLM.

        Args:
            prompt (str): O prompt de texto para o LLM.
            **kwargs: Parâmetros adicionais para a chamada LLM (ex: temperature, max_tokens).

        Returns:
            Dict[str, Any]: Um dicionário contendo o 'content' da resposta e 'metadata'.
        """
        if not prompt or not prompt.strip():
            logger.warning(f"[{self.__class__.__name__}] Prompt vazio fornecido para consulta LLM.")
            return {"content": "", "metadata": {"status": "prompt_vazio"}}

        try:
            # Parâmetros de geração padrão
            generation_config = {
                "temperature": kwargs.get("temperature", 0.5),
                "max_output_tokens": kwargs.get("max_output_tokens", 384) # Seu protótipo usava 384
            }

            # LangChain retorna um objeto, pegamos o conteúdo
            # A chamada .invoke pode ser síncrona ou assíncrona dependendo do cliente LangChain
            # Se for síncrona, use await asyncio.to_thread(self.llm_cliente.invoke, ...)
            # Se for assíncrona (como com aiohttp), use await self.llm_cliente.invoke(...)
            # Assumimos que o cliente LLM é assíncrono para esta implementação.

            # Adaptação para aiohttp.ClientSession se o cliente for personalizado e usar request/aiohttp
            # Se o cliente for uma instância padrão de ChatOpenAI/ChatGroq/etc, .invoke já é assíncrono.

            resposta_llm = await self.llm_cliente.invoke(prompt, **generation_config)
            content = resposta_llm.content

            logger.debug(f"[{self.__class__.__name__}] Consulta LLM bem-sucedida para modelo '{self.nome_modelo}'.")
            return {"content": content, "metadata": {"status": "sucesso", "modelo": self.nome_modelo}}
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Falha na consulta LLM para modelo '{self.nome_modelo}': {e}", exc_info=True)
            return {"content": "", "metadata": {"status": "erro", "erro_msg": str(e), "modelo": self.nome_modelo}}

    # Adaptação de funções de hamo.py para LLMQueryEngine se necessário.
    # Ex: _restore_failed_at, throttle_request, etc.