# quimera/agentes/agente_transformador.py


# Verificações de dependências adicionadas automaticamente
def verificar_dependencia(nome_modulo, funcionalidade="essa funcionalidade"):
    """Verifica se uma dependência está disponível"""
    try:
        __import__(nome_modulo)
        return True
    except ImportError:
        print(f"⚠️  {nome_modulo} não instalado - {funcionalidade} não disponível")
        return False
        pipeline = None

import logging
_logger = logging.getLogger(__name__)


def _unavailable_feature(feature_name: str, *args, **kwargs):
    """Loga warning quando funcionalidade não está disponível por falta de dependências."""
    _logger.warning(f"Funcionalidade '{feature_name}' indisponível — dependência não instalada")
    return None

import ast
import logging
from typing import Dict, Any, Tuple
from functools import lru_cache
try:
    from transformers import pipeline, Pipeline
except ImportError:
    Pipeline = object
    def pipeline(*args, **kwargs):
        raise ImportError("transformers not installed")

# Configuração do logger para este módulo
logger = logging.getLogger(__name__)


class ASTSecurityRefactorer(ast.NodeTransformer):
    """
    Um NodeTransformer que percorre a AST e substitui padrões de código
    inseguros conhecidos por alternativas mais seguras.
    Esta é uma implementação determinística para correções de segurança.
    """
    def __init__(self):
        super().__init__()
        self.modificado = False
        logger.info("ASTSecurityRefactorer inicializado.")

    def visit_Call(self, node: ast.Call) -> ast.Call:
        """
        Visita cada nó de chamada de função na AST.
        Procura por chamadas a 'strcpy' e as substitui por 'strncpy'.
        """
        # Garante que estamos lidando com uma chamada de função simples por nome
        if isinstance(node.func, ast.Name) and node.func.id == 'strcpy':
            if len(node.args) == 2:
                logger.warning("Função insegura 'strcpy' detectada. Transformando para 'strncpy'.")
                self.modificado = True

                destino_arg = node.args[0]
                fonte_arg = node.args[1]

                # Cria um novo nó de chamada para 'sizeof(destino)'
                sizeof_call = ast.Call(
                    func=ast.Name(id='sizeof', ctx=ast.Load()),
                    args=[destino_arg],
                    keywords=[]
                )

                # Retorna um novo nó de chamada para 'strncpy(destino, fonte, sizeof(destino))'
                return ast.Call(
                    func=ast.Name(id='strncpy', ctx=ast.Load()),
                    args=[destino_arg, fonte_arg, sizeof_call],
                    keywords=[]
                )

        # Continua a travessia para outros nós
        return self.generic_visit(node)


class NeuralCodeReconstructor:
    """
    Utiliza um modelo de linguagem grande (LLM) para refatorar e aprimorar
    a qualidade geral do código que já passou pelas verificações de segurança.
    """
    def __init__(self, model_id: str = "bigcode/starcoder2-3b"):
        self.model_id = model_id
        # O pipeline é carregado sob demanda e cacheado
        logger.info(f"NeuralCodeReconstructor configurado para usar o modelo '{model_id}'.")

    @staticmethod
    @lru_cache(maxsize=2)
    def _carregar_pipeline(model_id: str) -> Pipeline:
        """Carrega e cacheia o pipeline do modelo para evitar recarregamentos."""
        logger.info(f"Carregando pipeline para o modelo: {model_id}...")
        return pipeline("text-generation", model=model_id, device_map="auto")

    def _criar_prompt_refatoracao(self, code: str) -> str:
        """Cria um prompt detalhado para guiar o LLM na refatoração."""
        return f"""<|user|>
Você é um engenheiro de software sênior e especialista em refatoração de código C.
Sua tarefa é analisar o código C a seguir e reescrevê-lo para melhorar a clareza, eficiência, e aderência às melhores práticas de codificação moderna, mantendo a funcionalidade original intacta.

Foque em:
- Melhorar nomes de variáveis para maior clareza.
- Simplificar a lógica complexa, se possível.
- Adicionar comentários onde a lógica for não-trivial.
- Garantir o tratamento adequado de erros.

Retorne APENAS o bloco de código C completo e refatorado, sem nenhuma explicação ou texto adicional.

Código para refatorar:
```c
{code}
```<|end|>
<|assistant|>
```c
"""

    def refine_code(self, code: str) -> str:
        """
        Usa o LLM para refinar um segmento de código.

        Args:
            code (str): O código original a ser refinado.

        Returns:
            str: O código refinado pelo LLM.
        """
        try:
            pipe = self._carregar_pipeline(self.model_id)
            prompt = self._criar_prompt_refatoracao(code)

            logger.info("Invocando LLM para refatoração neural do código...")
            resultado_raw = pipe(prompt, max_new_tokens=len(code.split())*2, temperature=0.2, do_sample=True)

            # Extrai o código da resposta
            texto_gerado = resultado_raw[0]['generated_text']
            codigo_refatorado = texto_gerado.split("<|assistant|>")[1].strip()

            # Limpa os delimitadores de bloco de código que pedimos
            if codigo_refatorado.startswith("```c"):
                codigo_refatorado = codigo_refatorado[4:]
            if codigo_refatorado.endswith("```"):
                codigo_refatorado = codigo_refatorado[:-3]

            return codigo_refatorado.strip()
        except Exception as e:
            logger.error(f"Falha na refatoração neural: {e}", exc_info=True)
            return code # Retorna o código original em caso de erro

class AgenteRejoinderRerank:
    """
    Agente Transformador de Código que aplica uma estratégia de duas etapas:
    1.  Refatoração determinística de segurança via AST.
    2.  Refatoração qualitativa neural via LLM.
    """
    def __init__(self):
        self.ast_refactorer = ASTSecurityRefactorer()
        self.neural_reconstructor = NeuralCodeReconstructor()
        logger.info("AgenteRejoinderRerank (Transformador) inicializado com componentes reais.")

    async def corrigir_codigo_neural(self, code: str, caminho: str) -> Dict[str, Any]:
        """
        Executa o processo de correção e refatoração para um dado código.

        Args:
            code (str): O código-fonte a ser corrigido/transformado.
            caminho (str): O caminho do arquivo para fins de contextualização.

        Returns:
            Dict[str, Any]: Um dicionário com o status e o resultado da operação.
        """
        logger.info(f"Iniciando processo de transformação para o arquivo: {caminho}...")

        try:
            code_tree = ast.parse(code)
        except SyntaxError as e:
            logger.error(f"Erro de sintaxe irrecuperável ao parsear o código para AST em '{caminho}': {e}")
            return {"status": "falha_critica_sintaxe", "motivo": str(e), "caminho_arquivo": caminho}

        # Etapa 1: Refatoração de Segurança Determinística via AST
        refactorer = self.ast_refactorer
        ast_modificada = refactorer.visit(code_tree)

        if refactorer.modificado:
            logger.info("Vulnerabilidade de segurança foi encontrada e corrigida via AST.")
            try:
                codigo_corrigido = ast.unparse(ast_modificada)
                return {"status": "sucesso_refatoracao_seguranca", "codigo_corrigido": codigo_corrigido}
            except Exception as e:
                logger.error(f"Falha ao converter a AST de segurança de volta para código: {e}", exc_info=True)
                return {"status": "falha_unparse_seguranca", "motivo": str(e)}

        # Etapa 2: Se nenhum problema de segurança foi encontrado, proceder com a refatoração neural
        logger.info("Nenhuma vulnerabilidade óbvia encontrada na AST. Procedendo com a refatoração neural para melhoria de qualidade.")
        codigo_refinado_neuralmente = self.neural_reconstructor.refine_code(code)

        if codigo_refinado_neuralmente != code:
            return {"status": "sucesso_refatoracao_neural", "codigo_corrigido": codigo_refinado_neuralmente}
        else:
            return {"status": "sem_mudancas_necessarias", "codigo_corrigido": code}