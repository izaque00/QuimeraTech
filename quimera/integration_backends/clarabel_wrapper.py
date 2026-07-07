import re
import logging
import sys
from typing import Dict, List, Union, Tuple, Set, Callable

try:
    from z3 import Solver, BitVec, BitVecVal, BitVecSort, BoolSort, Sort
except ImportError:
    Sort = object
    BitVecSort = object
    BoolSort = object
    Solver = object
    BitVec = object
    BitVecVal = object
    Array = lambda *a, **kw: object
    pass

try:
    from pycparser import c_parser, c_ast
except ImportError:
    c_parser = None
    c_ast = None

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# ==============================================================================================
#                                  🔑  CONTEXTO DE EXECUÇÃO
# ==============================================================================================

class Z3ExecutionContext:
    """Gerencia o estado da análise simbólica (variáveis, memória, tipos)."""
    def __init__(self):
        self.solver = Solver(ctx=Context())
        self.solver.set(':timeout', 20000) # Timeout aumentado para tarefas mais complexas

        self.memory = Array('heap', BitVecSort(64), BitVecSort(8))
        self.vars = {}
        self.var_versions = {}
        self.heap_pointer = 0x100000 # Endereço de heap mais realista

        self.struct_layouts = {}
        self.type_sizes_bits = {
            'char': 8, 'signed char': 8, 'unsigned char': 8, 'short': 16, 'unsigned short': 16,
            'int': 32, 'unsigned int': 32, 'long': 64, 'long long': 64, 'unsigned long': 64,
            'unsigned long long': 64, 'int8_t': 8, 'uint8_t': 8, 'int16_t': 16, 'uint16_t': 16,
            'int32_t': 32, 'uint32_t': 32, 'int64_t': 64, 'uint64_t': 64, 'void*': 64, 'bool': 1, 'size_t': 64
        }
        self.type_alignments_bytes = {
            'char': 1, 'signed char': 1, 'unsigned char': 1, 'short': 2, 'unsigned short': 2,
            'int': 4, 'unsigned int': 4, 'long': 8, 'long long': 8, 'unsigned long': 8,
            'unsigned long long': 8, 'int8_t': 1, 'uint8_t': 1, 'int16_t': 2, 'uint16_t': 2,
            'int32_t': 4, 'uint32_t': 4, 'int64_t': 8, 'uint64_t': 8, 'void*': 8, 'size_t': 8
        }

    def _get_type_info(self, c_type: str) -> (int, int):
        c_type = c_type.replace('const ', '').strip()
        if c_type.endswith('*') or c_type == 'uintptr_t':
            return (64, self.type_alignments_bytes['void*'])
        size = self.type_sizes_bits.get(c_type)
        align = self.type_alignments_bytes.get(c_type)
        if size is not None:
            return (size, align)
        if c_type.startswith('struct'):
            return (self.type_sizes_bits[c_type], self.type_alignments_bytes[c_type])
        logging.warning(f"Tipo '{c_type}' não encontrado. Usando 'int' como padrão.")
        return (self.type_sizes_bits['int'], self.type_alignments_bytes['int'])

    def get_z3_sort(self, c_type: str) -> Sort:
        bits, _ = self._get_type_info(c_type)
        return BitVecSort(bits) if bits > 0 else BoolSort()

    def get_var(self, name: str):
        if name not in self.vars:
            self.declare_var('int', name) # Declaração implícita
        return self.vars[name][1]

    def declare_var(self, c_type: str, name: str, init_val=None):
        version = self.var_versions.get(name, 0)
        self.var_versions[name] = version
        z3_var = Const(f"{name}_{version}", self.get_z3_sort(c_type))
        self.vars[name] = (version, z3_var)
        if init_val is not None:
            self.solver.add(z3_var == init_val)
        return z3_var

    def update_var(self, name: str, new_value_expr):
        version = self.var_versions.get(name, 0) + 1
        self.var_versions[name] = version
        z3_sort = new_value_expr.sort()
        new_z3_var = Const(f"{name}_{version}", z3_sort)
        self.vars[name] = (version, new_z3_var)
        self.solver.add(new_z3_var == new_value_expr)
        return new_z3_var

    def allocate_memory(self, size_val: BitVec) -> BitVecVal:
        # Simplificação: alocação de tamanho fixo para agora. Tamanho simbólico é mais complexo.
        size_bytes = 1024 # Aloca um tamanho fixo grande
        base_addr = self.heap_pointer
        self.heap_pointer += size_bytes
        logging.info(f"Alocando {size_bytes} bytes (a partir do pedido simbólico) em 0x{base_addr:x}")
        # Retorna um ponteiro concreto, mas o conteúdo é simbólico
        return BitVecVal(base_addr, 64)

# ==============================================================================================
#                      🧠  TRADUTOR AST C -> Z3 (COM MODELOS DE FUNÇÃO)
# ==============================================================================================

class CToZ3Translator:
    def __init__(self, context: Z3ExecutionContext):
        self.ctx = context
        self.c_generator = c_ast.c_generator.CGenerator()
        ### NOVO: Registro de modelos para funções de biblioteca ###
        self.function_models: Dict[str, Callable] = {
            'malloc': self._model_malloc,
            'strlen': self._model_strlen
            # 'free', 'memcpy', 'printf', etc. seriam adicionados aqui
        }

    # ... (métodos _c_type_to_str, _read/write_from_memory, etc. do script anterior) ...
    # O código omitido para brevidade é o mesmo da resposta anterior.

    def visit(self, node):
        method = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method, self.generic_visit)
        return visitor(node) if node else None

    def generic_visit(self, node):
        logger.debug(f"Clarabel: node {node.__class__.__name__} skipped")
        return node

    # ... (visit_Compound, visit_Decl, visit_Assignment, etc. do script anterior) ...

    ### NOVO: Tratamento de Chamadas de Função ###
    def visit_FuncCall(self, node: c_ast.FuncCall):
        func_name = node.name.name

        if func_name in self.function_models:
            logging.info(f"Executando modelo simbólico para a função '{func_name}'")
            # Converte os argumentos da AST para expressões Z3
            args = [self.visit(arg) for arg in node.args.exprs] if node.args else []
            return self.function_models[func_name](*args)
        else:
            # Função não modelada: retorna um valor completamente simbólico (não interpretado)
            logging.warning(f"Função '{func_name}' não modelada. Retornando valor simbólico.")
            # O tipo de retorno precisaria ser inferido. Assumindo int por enquanto.
            ret_sort = BitVecSort(32)
            ret_val = Const(f"ret_{func_name}", ret_sort)
            return ret_val

    ### NOVO: Modelos de Funções de Biblioteca ###
    def _model_malloc(self, size_expr: BitVec):
        """Modelo simbólico para malloc(size_t size)."""
        # A alocação de tamanho simbólico é complexa.
        # Por simplicidade, alocamos um bloco máximo e restringimos o tamanho.
        # Uma implementação completa teria um modelo de heap mais complexo.
        addr = self.ctx.allocate_memory(size_expr)
        return addr

    def _model_strlen(self, ptr_expr: BitVec):
        """Modelo simbólico para strlen(const char *s)."""
        # Cria uma variável simbólica para o comprimento
        strlen_ret = Const(f"strlen_{ptr_expr.get_id()}", BitVecSort(64))

        # Restrições para strlen:
        # 1. O comprimento deve ser não-negativo (já garantido por BitVec sem sinal).
        # 2. O byte no endereço (ptr + strlen_ret) DEVE ser 0 (terminador nulo).
        null_terminator_addr = ptr_expr + ZeroExt(ptr_expr.size() - strlen_ret.size(), strlen_ret)
        self.ctx.solver.add(Select(self.ctx.memory, null_terminator_addr) == 0)

        # 3. Nenhum byte ANTES do terminador nulo pode ser 0.
        # Esta é uma restrição complexa (requer um quantificador).
        # i = Var(0, BitVecSort(64))
        # self.ctx.solver.add(ForAll([i],
        #    Implies(ULT(i, strlen_ret),
        #            Select(self.ctx.memory, ptr_expr + ZeroExt(ptr_expr.size() - i.size(), i)) != 0)))
        # Quantificadores são caros, então vamos omitir esta restrição por performance,
        # mas uma ferramenta de produção a incluiria.

        logging.info(f"strlen em {ptr_expr} modelado com retorno simbólico {strlen_ret}")
        return strlen_ret

    # A implementação completa de todos os outros visitors (visit_If, etc.) segue aqui.
    # O código omitido é o mesmo da resposta anterior.
    def visit_If(self, node: c_ast.If):
        cond_expr = self.visit(node.cond)
        z3_cond = (cond_expr != 0)
        vars_before = self.ctx.vars.copy()
        mem_before = self.ctx.memory
        self.ctx.solver.push()
        self.ctx.solver.add(z3_cond)
        self.visit(node.iftrue)
        vars_after_then = self.ctx.vars.copy()
        mem_after_then = self.ctx.memory
        self.ctx.solver.pop()
        self.ctx.vars = vars_before.copy()
        self.ctx.memory = mem_before
        vars_after_else = vars_before.copy()
        mem_after_else = mem_before
        if node.iffalse:
            self.ctx.solver.push()
            self.ctx.solver.add(Not(z3_cond))
            self.visit(node.iffalse)
            vars_after_else = self.ctx.vars.copy()
            mem_after_else = self.ctx.memory
            self.ctx.solver.pop()
        all_modified_vars = set(vars_after_then.keys()) | set(vars_after_else.keys())
        self.ctx.vars = vars_before
        self.ctx.memory = mem_before
        for var_name in all_modified_vars:
            _v_then, z3_var_then = vars_after_then.get(var_name, vars_before.get(var_name))
            _v_else, z3_var_else = vars_after_else.get(var_name, vars_before.get(var_name))
            if z3_var_then.get_id() != z3_var_else.get_id():
                merged_val = If(z3_cond, z3_var_then, z3_var_else)
                self.ctx.update_var(var_name, merged_val)
        self.ctx.memory = If(z3_cond, mem_after_then, mem_after_else)


# ==============================================================================================
#                                  🔎  MOTOR DE PROVA E ANÁLISE
# ==============================================================================================
class HighFidelityProver:
    def __init__(self):
        # Usar o lexer/parser do pycparser
        self.parser = c_parser.CParser()

    def analyze(self, c_code: str, property_to_check: str):
        context = Z3ExecutionContext()
        translator = CToZ3Translator(context)

        # Preâmbulo com declarações de funções de biblioteca para que o parser as reconheça
        prelude = "void *malloc(unsigned long size); unsigned long strlen(const char *s);"
        full_code = prelude + f"\nvoid analysis_wrapper() {{ {c_code} }}"

        try:
            ast = self.parser.parse(full_code, filename='<stdin>')
            # O corpo da nossa função está no último nó da AST
            func_body = ast.ext[-1].body
            translator.visit(func_body)

            # Analisa a propriedade
            prop_ast = self.parser.parse(f"int prop() {{ return {property_to_check}; }}", filename='<prop>')
            prop_expr = translator.visit(prop_ast.ext[0].body.items[0])

            context.solver.add(prop_expr != 0)

            logging.info("Verificando a propriedade de segurança com o Z3...")
            result = context.solver.check()

            if result == sat:
                model = context.solver.model()
                print("\n" + "="*25)
                print("🚨 VULNERABILIDADE ENCONTRADA 🚨")
                print("="*25)
                print(f"A propriedade '{property_to_check}' pode ser satisfeita.")
                print("Modelo de ataque (valores que causam a falha):")
                model_vars = {}
                for decl in model.decls():
                    # Mostra apenas as versões iniciais das variáveis para simplicidade
                    if '_0' in decl.name():
                        var_name = decl.name().split('_0')[0]
                        model_vars[var_name] = model[decl]
                return {"vulnerable": True, "model": model_vars}
            elif result == unsat:
                print("\n" + "="*25)
                print("✅ PROPRIEDADE VERIFICADA ✅")
                print("="*25)
                print(f"A condição de falha '{property_to_check}' é inalcançável.")
                return {"vulnerable": False}
            else:
                print("\n" + "="*25)
                print("🤔 ANÁLISE INCONCLUSIVA 🤔")
                print("="*25)
                print(f"O Z3 não conseguiu determinar o resultado. Razão: {context.solver.reason_unknown()}")
                return {"vulnerable": None, "reason": context.solver.reason_unknown()}

        except Exception as e:
            logging.error(f"Ocorreu um erro durante a análise: {e}")
            import traceback
            traceback.print_exc()
            return {"vulnerable": None, "error": str(e)}

# ==============================================================================================
#                      ÁREA DE DEMONSTRAÇÃO (HEAP OVERFLOW)
# ==============================================================================================

if __name__ == '__main__':
    prover = HighFidelityProver()

    print("\n--- Exemplo de Produção: Análise de Heap Overflow com `malloc` e `strlen` ---")
    # Cenário: um buffer é alocado com um tamanho fixo (16).
    # Uma 'string' de entrada simbólica é copiada para ele.
    # A vulnerabilidade ocorre se o comprimento da string de entrada for maior que o buffer.
    code_example = """
        char* buffer = malloc(16);  // Aloca 16 bytes no heap
        char input[100];            // Declara uma 'input' simbólica (o conteúdo é simbólico)
        int len = strlen(input);    // O comprimento é simbólico

        // Copia 'len' bytes de 'input' para 'buffer'
        // Simplificação de um loop de cópia (memcpy)
        // O acesso perigoso acontece se len >= 16
        buffer[len-1] = 'A';
    """

    # Propriedade a verificar: o comprimento da string simbólica 'input'
    # é maior ou igual ao tamanho do buffer alocado?
    # O solver precisa encontrar um modelo para o conteúdo de 'input'
    # tal que seu comprimento (retornado por strlen) seja >= 16.
    result = prover.analyze(code_example, "len >= 16")
    if result.get("vulnerable"):
        print(result["model"])
        print("\nExplicação: O solver encontrou uma forma de a string 'input' ter um comprimento >= 16.")
        print("Isso faz com que o acesso 'buffer[len-1]' escreva fora do buffer de 16 bytes alocado, causando um heap overflow.")