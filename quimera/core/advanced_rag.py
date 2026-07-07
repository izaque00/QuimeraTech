# quimera/core/advanced_rag.py

import sys
import logging
import os
from typing import List, Dict, Any

from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.retrievers import EnsembleRetriever
from langchain.retrievers.bm25 import BM25Retriever
from langchain.docstore.document import Document
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.llms import OpenAI

logger = logging.getLogger(__name__)

class AdvancedRAG:
    """
    Implementa um sistema de Geração Aumentada por Recuperação (RAG) avançado,
    utilizando uma abordagem híbrida de busca (keyword + semântica) para
    melhorar a relevância dos documentos recuperados.
    """
    def __init__(self, documents: List[str], openai_api_key: str, llm_model_name: str = "gpt-4o-mini"):
        """
        Inicializa o sistema AdvancedRAG.

        Args:
            documents (List[str]): Uma lista de strings, onde cada string é o conteúdo de um documento.
            openai_api_key (str): A chave de API da OpenAI.
            llm_model_name (str): O nome do modelo LLM a ser usado para a geração de respostas.
        """
        if not openai_api_key:
            raise ValueError("A chave de API da OpenAI não foi fornecida.")

        self.openai_api_key = openai_api_key
        self.llm = OpenAI(openai_api_key=self.openai_api_key, temperature=0, model_name=llm_model_name)
        self.embeddings = OpenAIEmbeddings(openai_api_key=self.openai_api_key)

        # Divide os documentos em chunks
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        self.docs = [Document(page_content=d) for d in documents]
        self.texts = self.text_splitter.split_documents(self.docs)

        # Configura o retriever avançado
        self.retriever = self._setup_advanced_retriever()

    def _setup_advanced_retriever(self) -> EnsembleRetriever:
        """
        Configura um retriever híbrido que combina busca por similaridade de vetores (FAISS)
        e busca por palavras-chave (BM25).
        """
        logger.info("Configurando o Advanced Retriever (Híbrido)...")

        # 1. Retriever de palavras-chave (BM25)
        keyword_retriever = BM25Retriever.from_documents(self.texts)
        keyword_retriever.k = 5  # Número de documentos a serem recuperados

        # 2. Retriever vetorial (FAISS)
        vectorstore = FAISS.from_documents(self.texts, self.embeddings)
        vector_retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

        # 3. Combina os dois retrievers em um Ensemble
        # O peso define a importância de cada retriever no score final. 0.5 para cada dá peso igual.
        ensemble_retriever = EnsembleRetriever(
            retrievers=[keyword_retriever, vector_retriever],
            weights=[0.5, 0.5]
        )

        # NOTA: A etapa de re-ranking com CohereRerank foi omitida para simplificar
        # as dependências, mas poderia ser adicionada aqui para ainda mais precisão.

        return ensemble_retriever

    def query(self, question: str) -> str:
        """
        Executa uma consulta contra o sistema RAG e retorna uma resposta gerada pelo LLM.

        Args:
            question (str): A pergunta do usuário.

        Returns:
            str: A resposta gerada pelo LLM, fundamentada nos documentos recuperados.
        """
        logger.info(f"Processando query RAG: '{question[:80]}...'")

        retrieved_docs = self.retriever.get_relevant_documents(question)
        if not retrieved_docs:
            return "Não foi possível encontrar informações relevantes nos documentos fornecidos para responder a esta pergunta."

        context = "\n\n".join([doc.page_content for doc in retrieved_docs])

        prompt_template = """
        Use o contexto fornecido para responder à pergunta do usuário.
        Se a resposta não estiver no contexto, diga que não sabe.

        Contexto:
        {context}

        Pergunta:
        {question}

        Resposta:
        """
        prompt = PromptTemplate(template=prompt_template, input_variables=["context", "question"])

        llm_chain = LLMChain(llm=self.llm, prompt=prompt)
        response = llm_chain.run(context=context, question=question)
        return response.strip()

# Exemplo de uso para teste do módulo
if __name__ == "__main__":
    # Para testar, defina sua chave da OpenAI como uma variável de ambiente:
    # export OPENAI_API_KEY="sk-..."
    if "OPENAI_API_KEY" not in os.environ:
        print("Erro: A variável de ambiente OPENAI_API_KEY não está definida.")
    else:
        sample_documents = [
            "O Brasil é o maior país da América do Sul e o quinto maior do mundo em área territorial.",
            "A capital do Brasil é Brasília, e a língua oficial é o português.",
            "A Amazônia é a maior floresta tropical do mundo, localizada principalmente no Brasil.",
            "O futebol é o esporte mais popular no Brasil, com a seleção nacional tendo ganhado a Copa do Mundo cinco vezes.",
            "A culinária brasileira é diversa, com pratos como feijoada e pão de queijo sendo muito conhecidos."
        ]

        try:
            rag_system = AdvancedRAG(sample_documents, os.environ["OPENAI_API_KEY"])

            print("\n--- Teste 1: Pergunta com contexto --- ")
            question1 = "Qual é a capital do Brasil?"
            answer1 = rag_system.query(question1)
            print(f"Pergunta: {question1}\nResposta: {answer1}")

            print("\n--- Teste 2: Pergunta sem contexto --- ")
            question2 = "Qual é a capital da França?"
            answer2 = rag_system.query(question2)
            print(f"Pergunta: {question2}\nResposta: {answer2}")

            print("\n--- Teste 3: Pergunta com contexto parcial --- ")
            question3 = "O que é a Amazônia?"
            answer3 = rag_system.query(question3)
            print(f"Pergunta: {question3}\nResposta: {answer3}")

        except Exception as e:
            print(f"Ocorreu um erro durante o teste: {e}")