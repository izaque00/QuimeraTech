from __future__ import annotations
import re
import logging
import argparse
from typing import Dict, Any, List, Optional, Union, Tuple, Set, Callable
from collections import defaultdict
from abc import ABC, abstractmethod

# Tenta importar as dependências Z3 e pycparser.
try:
    from z3 import *
    from pycparser import c_parser, c_ast, c_generator
    Z3_AVAILABLE = True
except ImportError:
    Z3_AVAILABLE = False
    # Stub namespace for pycparser so class definitions (Z3Visitor, CTypeCollector)
    # that inherit from c_ast.NodeVisitor don't crash at definition time.
    # Runtime methods that use c_ast are guarded by Z3_AVAILABLE checks.
    class _StubNodeVisitor:
        def generic_visit(self, node): pass
    _stub_ns = type('_stub_ns', (), {})()
    _stub_ns.NodeVisitor = _StubNodeVisitor
    c_ast = _stub_ns

logger = logging.getLogger(__name__)

def montar_log(msg, log_level="INFO"):
    """Função de logging centralizada."""
    if log_level.upper() == "ERROR":
        logger.error(msg)
    elif log_level.upper() == "WARNING":
        logger.warning(msg)
    else:
        logger.info(msg)

if not Z3_AVAILABLE:
    montar_log("Faltam dependências críticas (z3-solver, pycparser). Funcionalidades Z3 desabilitadas.", log_level="WARNING")
    pass  # exit(1) removed — graceful degradation

# --- Real C Type and Memory Layout Management ---

class StructLayout:
    """Armazena o layout de memória de uma struct C."""
    def __init__(self, name: str, arch_bits: int = 64):
        self.name = name
        self.fields: List[Tuple[str, str]] = [] # (field_name, type_name)
        self.offsets: Dict[str, int] = {} # field_name -> byte_offset
        self.size = 0
        self.alignment = 1
        self.arch_bits = arch_bits

class TypeReflector:
    """
    Reflete tipos C em representações Z3, incluindo o layout de memória
    realista para tipos primitivos e compostos (structs, arrays).
    Assume uma arquitetura de 64 bits para alinhamento e tamanhos.
    """
    def __init__(self):
        self.types_cache: Dict[str, SortRef] = {}
        self.struct_layouts: Dict[str, StructLayout] = {}

        # Modelo de tamanhos e alinhamentos para arquitetura 64-bit (ex: x86-64)
        self.type_info: Dict[str, Dict[str, int]] = {
            'char':     {'size': 1, 'align': 1}, 'int8_t':   {'size': 1, 'align': 1},
            'short':    {'size': 2, 'align': 2}, 'int16_t':  {'size': 2, 'align': 2},
            'int':      {'size': 4, 'align': 4}, 'int32_t':  {'size': 4, 'align': 4},
            'long':     {'size': 8, 'align': 8}, 'int64_t':  {'size': 8, 'align': 8},
            'void*':    {'size': 8, 'align': 8}, 'ptr':      {'size': 8, 'align': 8},
            'bool':     {'size': 1, 'align': 1}, '_Bool':    {'size': 1, 'align': 1},
        }

    def get_type_info(self, type_name: str) -> Dict[str, int]:
        """Retorna o tamanho e alinhamento para um dado tipo."""
        type_name = type_name.replace('unsigned ', '').strip()
        if type_name.endswith('*') or type_name == 'ptr':
            return self.type_info['void*']
        if type_name.startswith('struct '):
            layout = self.struct_layouts.get(type_name.replace('struct ', ''))
            return {'size': layout.size, 'align': layout.alignment} if layout else {'size': 0, 'align': 1}
        return self.type_info.get(type_name, {'size': 4, 'align': 4}) # Default para int

    def register_struct_layout(self, node: c_ast.Struct):
        """Analisa uma AST de struct e calcula seu layout de memória real."""
        if not node.name or node.name in self.struct_layouts:
            return

        layout = StructLayout(node.name)
        current_offset = 0

        for decl in node.decls:
            field_type_str = self._parse_declaration_to_type(decl)
            field_info = self.get_type_info(field_type_str)
            field_size = field_info['size']
            field_align = field_info['align']

            # Adiciona padding para garantir alinhamento do campo
            padding = (field_align - (current_offset % field_align)) % field_align
            current_offset += padding

            layout.fields.append((decl.name, field_type_str))
            layout.offsets[decl.name] = current_offset
            layout.alignment = max(layout.alignment, field_align)
            current_offset += field_size

        # Adiciona padding final para alinhar o tamanho total da struct
        final_padding = (layout.alignment - (current_offset % layout.alignment)) % layout.alignment
        layout.size = current_offset + final_padding

        self.struct_layouts[node.name] = layout
        montar_log(f"Struct '{node.name}' registrada. Tamanho: {layout.size}, Alinhamento: {layout.alignment}, Offsets: {layout.offsets}")

    def reflector_type(self, type_name: str) -> SortRef:
        """Gera Z3 Sort a partir do tipo C simples ou composto."""
        type_name = type_name.strip()
        if type_name in self.types_cache:
            return self.types_cache[type_name]

        width = self.get_type_info(type_name)['size'] * 8

        if type_name in ('bool', '_Bool'):
            result = BoolSort()
        elif type_name.startswith('struct '):
            struct_name = type_name.replace('struct ', '')
            if struct_name in self.struct_layouts:
                # O tipo de uma struct é seu endereço de memória (um ponteiro)
                result = BitVecSort(64, name=f"t_ptr_{struct_name}")
            else:
                montar_log(f"Struct '{struct_name}' não registrada. Tratando como ponteiro opaco.", log_level="WARNING")
                result = BitVecSort(64, name="t_ptr_opaque")
        elif '[]' in type_name or type_name.startswith('array'):
            base = type_name.replace('[]', '').replace('array ', '').strip()
            element_sort = self.reflector_type(base)
            index_sort = BitVecSort(64) # Índices de array como ponteiros
            result = ArraySort(index_sort, element_sort)
        else:
            # Default para Bit-Vectors
            result = BitVecSort(width if width > 0 else 32)

        self.types_cache[type_name] = result
        return result

    def _parse_declaration_to_type(self, node: c_ast.Decl) -> str:
        """Extrai string de tipo a partir de uma AST de declaração."""
        # Esta é uma função simplificada; uma versão completa seria mais complexa.
        if isinstance(node.type, c_ast.TypeDecl):
            return ' '.join(node.type.type.names)
        elif isinstance(node.type, c_ast.PtrDecl):
            # Simplificação: todos os ponteiros são 'void*' para fins de tipo.
            return 'void*'
        elif isinstance(node.type, c_ast.ArrayDecl):
            return f"array {self._parse_declaration_to_type(c_ast.Decl(name=None, quals=[], storage=[], funcspec=[], type=node.type.type, init=None, bitsize=None))}"
        elif isinstance(node.type, c_ast.Struct):
            return f"struct {node.type.name}"
        return 'int' # Fallback


# --- AST Visitor para traduzir C para Z3 ---

class Z3Visitor(c_ast.NodeVisitor):
    """
    Visitor que percorre a AST do C e traduz expressões para o formalismo do Z3.
    """
    def __init__(self, type_reflector: TypeReflector, variable_types: Dict[str, str]):
        self.type_reflector = type_reflector
        self.var_store: Dict[str, ExprRef] = {}
        self.context_var_types = variable_types

        # Memória simbólica: um grande array de bytes. Endereço 64-bit -> Byte 8-bit
        self.memory = Array('heap_memory', BitVecSort(64), BitVecSort(8))

        # Inicializa variáveis simbólicas com base nos tipos coletados
        for var, c_type in variable_types.items():
            z3_type = self.type_reflector.reflector_type(c_type)
            self.var_store[var] = Const(var, z3_type)

    def visit_ID(self, node: c_ast.ID) -> ExprRef:
        """Visita um identificador (variável) e retorna seu valor simbólico."""
        if node.name in self.var_store:
            return self.var_store[node.name]

        montar_log(f"Variável '{node.name}' não declarada encontrada. Criando como 'int' simbólico.", log_level="WARNING")
        # Cria como um int simbólico se não for encontrado. Em um modo estrito, isso seria um erro.
        sym = Const(node.name, BitVecSort(32))
        self.var_store[node.name] = sym
        return sym

    def visit_Constant(self, node: c_ast.Constant) -> ExprRef:
        """Visita uma constante C e a converte para um valor Z3."""
        val_type = node.type.lower()
        value = node.value

        if val_type == 'int':
            return BitVecVal(int(value), 32)
        elif val_type == 'long':
            return BitVecVal(int(value), 64)
        elif 'char' in val_type:
             # Remove aspas de 'c' ou "c"
            char_val = value.strip("'\"")
            return BitVecVal(ord(char_val[0]), 8)
        elif val_type == 'string':
            # Strings são tratadas como ponteiros para uma área de memória simbólica.
            # Não implementado nesta versão, retorna ponteiro nulo.
            return BitVecVal(0, 64)
        return BitVecVal(0, 32) # Fallback

    def visit_Assignment(self, node: c_ast.Assignment):
        """Trata atribuições: x = y, x += y, etc."""
        lvalue = node.lvalue
        rvalue_expr = self.visit(node.rvalue)

        # Atribuição simples: x = y
        if node.op == '=':
            if isinstance(lvalue, c_ast.ID):
                self.var_store[lvalue.name] = rvalue_expr
            elif isinstance(lvalue, c_ast.StructRef):
                # Atribuição a campo de struct: s->field = val
                struct_ptr = self.visit(lvalue.name)
                field_name = lvalue.field.name
                self._store_memory_for_field(struct_ptr, field_name, rvalue_expr)
            # Outros lvalues (ArrayRef, etc.) podem ser adicionados aqui.
            return rvalue_expr

        # Atribuição composta: x += y -> x = x + y
        else:
            if not isinstance(lvalue, c_ast.ID):
                montar_log("Atribuição composta em não-IDs não é suportada.", "WARNING")
                return

            op = node.op.replace('=', '') # De '+=' para '+'
            current_val = self.visit(lvalue)
            new_val = self._eval_binary_op(op, current_val, rvalue_expr)
            self.var_store[lvalue.name] = new_val
            return new_val

    def visit_BinaryOp(self, node: c_ast.BinaryOp) -> ExprRef:
        """Visita uma operação binária."""
        lhs = self.visit(node.left)
        rhs = self.visit(node.right)
        return self._eval_binary_op(node.op, lhs, rhs)

    def _eval_binary_op(self, op: str, lhs: ExprRef, rhs: ExprRef) -> ExprRef:
        """Lógica central para avaliar operadores binários C em Z3."""
        # Coerção de tipo simples para operações
        if lhs.sort().kind() != rhs.sort().kind():
             # Simplificação: estende o menor para o tamanho do maior
            size_l, size_r = lhs.sort().size(), rhs.sort().size()
            if size_l < size_r:
                lhs = ZeroExt(size_r - size_l, lhs)
            else:
                rhs = ZeroExt(size_l - size_r, rhs)

        # Mapeamento de operadores C para funções Z3
        ops = {
            '+': lambda a, b: a + b, '-': lambda a, b: a - b,
            '*': lambda a, b: a * b, '/': lambda a, b: UDiv(a, b),
            '%': lambda a, b: URem(a, b),
            '<': lambda a, b: ULT(a, b), '>': lambda a, b: UGT(a, b),
            '<=': lambda a, b: ULE(a, b), '>=': lambda a, b: UGE(a, b),
            '==': lambda a, b: a == b, '!=': lambda a, b: a != b,
            '&&': lambda a, b: And(a, b), '||': lambda a, b: Or(a, b),
            '&': lambda a, b: a & b, '|': lambda a, b: a | b,
            '^': lambda a, b: a ^ b, '<<': lambda a, b: shl(a, b),
            '>>': lambda a, b: lshr(a, b),
        }
        if op in ops:
            return ops[op](lhs, rhs)
        else:
            montar_log(f"Operador binário '{op}' não suportado.", "ERROR")
            return lhs # Retorna algo para não quebrar a árvore

    def visit_UnaryOp(self, node: c_ast.UnaryOp):
        """Visita uma operação unária."""
        expr = self.visit(node.expr)
        op = node.op

        if op == '!': return Not(expr)
        if op == '-': return -expr
        if op == '~': return ~expr
        if op == 'p++' or op == '++': return expr + 1
        if op == 'p--' or op == '--': return expr - 1

        # Operador de endereço '&'
        if op == '&':
            if isinstance(node.expr, c_ast.ID):
                 # Retorna um valor simbólico representando o endereço da variável
                 # Numa implementação real, este endereço seria gerenciado num modelo de stack.
                 return Const(f"addr_of_{node.expr.name}", BitVecSort(64))

        # Operador de desreferência '*'
        if op == '*':
            # Assume que expr é um ponteiro (BitVec de 64 bits)
            # Lê um valor de 32 bits da memória por padrão.
            return self._load_memory(expr, 32)

        return expr

    def visit_StructRef(self, node: c_ast.StructRef):
        """Acessa um campo de struct: `s->field`."""
        struct_ptr_expr = self.visit(node.name)
        field_name = node.field.name

        # O tipo da variável ponteiro nos informa qual layout de struct usar
        var_name = node.name.name
        c_type = self.context_var_types.get(var_name)
        if not c_type or not c_type.startswith('struct'):
            montar_log(f"Não foi possível determinar o tipo de struct para o ponteiro '{var_name}'.", "ERROR")
            return Const(f"unknown_field_{field_name}", BitVecSort(32))

        field_type = self._get_field_type(c_type, field_name)
        field_info = self.type_reflector.get_type_info(field_type)

        return self._load_memory_for_field(struct_ptr_expr, field_name, c_type)

    def _get_field_type(self, struct_c_type: str, field_name: str) -> str:
        """Obtém o tipo C de um campo de uma struct registrada."""
        struct_name = struct_c_type.replace('struct ', '').replace('*', '').strip()
        layout = self.type_reflector.struct_layouts.get(struct_name)
        if layout:
            for f_name, f_type in layout.fields:
                if f_name == field_name:
                    return f_type
        return 'int' # Fallback

    def _get_field_offset(self, struct_ptr_expr, field_name: str, struct_c_type: str) -> int:
        """Calcula o offset de um campo a partir do ponteiro base."""
        struct_name = struct_c_type.replace('struct ', '').replace('*', '').strip()
        layout = self.type_reflector.struct_layouts.get(struct_name)
        if layout and field_name in layout.offsets:
            return layout.offsets[field_name]

        montar_log(f"Offset não encontrado para o campo '{field_name}' na struct '{struct_name}'.", "ERROR")
        return 0

    def _load_memory_for_field(self, base_ptr: ExprRef, field_name: str, struct_c_type: str) -> ExprRef:
        """Lê o valor de um campo da memória simbólica."""
        offset = self._get_field_offset(base_ptr, field_name, struct_c_type)
        field_addr = base_ptr + BitVecVal(offset, 64)

        field_type = self._get_field_type(struct_c_type, field_name)
        field_bits = self.type_reflector.get_type_info(field_type)['size'] * 8

        return self._load_memory(field_addr, field_bits)

    def _store_memory_for_field(self, base_ptr: ExprRef, field_name: str, value_expr: ExprRef):
        """Escreve o valor de um campo na memória simbólica."""
        var_name = base_ptr.decl().name()
        c_type = self.context_var_types.get(var_name)
        offset = self._get_field_offset(base_ptr, field_name, c_type)
        field_addr = base_ptr + BitVecVal(offset, 64)

        self._store_memory(field_addr, value_expr)

    def _load_memory(self, addr: BitVecRef, bits: int) -> BitVecRef:
        """Lê um valor de 'bits' da memória no endereço 'addr' (little-endian)."""
        num_bytes = bits // 8
        bytes_list = [Select(self.memory, addr + i) for i in range(num_bytes)]

        # Concatena em ordem little-endian
        return Concat(*reversed(bytes_list))

    def _store_memory(self, addr: BitVecRef, value: BitVecRef):
        """Escreve 'value' na memória no endereço 'addr' (little-endian)."""
        num_bytes = value.sort().size() // 8
        for i in range(num_bytes):
            byte = Extract(i * 8 + 7, i * 8, value)
            self.memory = Store(self.memory, addr + i, byte)

# --- Coletores de Informação da AST ---

class CTypeCollector(c_ast.NodeVisitor):
    """
    Visitor que percorre a AST para registrar definições de struct e coletar
    tipos de todas as variáveis declaradas.
    """
    def __init__(self, type_reflector: TypeReflector):
        self.type_reflector = type_reflector
        self.variable_types: Dict[str, str] = {} # var_name -> c_type_str

    def visit_Decl(self, node: c_ast.Decl):
        """Visita uma declaração para extrair o nome e o tipo da variável."""
        if node.name:
            c_type = self.type_reflector._parse_declaration_to_type(node)
            self.variable_types[node.name] = c_type
            montar_log(f"Variável coletada: '{node.name}' com tipo '{c_type}'")

    def visit_Struct(self, node: c_ast.Struct):
        """Visita uma definição de struct para registrar seu layout."""
        if node.decls: # Apenas se for uma definição, não uma declaração
            self.type_reflector.register_struct_layout(node)


# --- Wrapper Principal do Z3 ---

class Z3Wrapper:
    """
    Wrapper avançado para o Z3 que orquestra a análise de código C.
    """
    def __init__(self):
        self._solver = Solver()
        self._solver.set(timeout=15000) # Timeout de 15 segundos
        self.type_reflector = TypeReflector()

    def _parse_and_collect_types(self, c_code: str) -> Dict[str, str]:
        """Usa o CTypeCollector para analisar o código e preparar os tipos."""
        parser = c_parser.CParser()
        ast = parser.parse(c_code)

        type_collector = CTypeCollector(self.type_reflector)
        type_collector.visit(ast)

        return type_collector.variable_types

    def check_c_assertion(self, c_code: str, c_assertion: str):
        """
        Verifica se uma asserção em C é sempre verdadeira, dado um trecho de código.
        Retorna o resultado da análise.
        """
        montar_log("Iniciando análise de asserção C...")
        try:
            # 1. Analisa o código fonte para coletar todos os tipos e layouts de struct
            montar_log("Passo 1: Coletando tipos e layouts de struct do código fonte.")
            variable_types = self._parse_and_collect_types(c_code)

            # 2. Prepara um Z3Visitor com os tipos coletados
            montar_log("Passo 2: Inicializando o visitor do Z3 com o contexto de tipos.")
            # Combina o código principal com a asserção para uma única AST
            full_code_for_ast = f"{c_code}\n void __assertion_wrapper__() {{ {c_assertion}; }}"
            parser = c_parser.CParser()
            ast = parser.parse(full_code_for_ast, filename='<stdin>')

            visitor = Z3Visitor(self.type_reflector, variable_types)
            visitor.visit(ast) # Executa simbolicamente o código principal para popular o estado

            # 3. Traduz a asserção para uma expressão Z3
            montar_log("Passo 3: Traduzindo a asserção C para uma expressão lógica Z3.")
            # A asserção é o último item do corpo da função wrapper
            assertion_ast = ast.ext[-1].body.block_items[0]
            assertion_expr = visitor.visit(assertion_ast)

            # 4. Prova a negação da asserção
            montar_log(f"Passo 4: Tentando provar a NEGAÇÃO da asserção: Not({assertion_expr})")
            self._solver.add(Not(assertion_expr))

            check_result = self._solver.check()
            montar_log(f"Resultado do Solver: {check_result}")

            # 5. Interpreta e reporta o resultado
            if check_result == unsat:
                print("\n--- ANÁLISE CONCLUÍDA ---")
                print("Status: \033[92mPROVADO SEGURO\033[0m")
                print("A asserção é sempre verdadeira sob as condições do código.")
                return True
            elif check_result == sat:
                print("\n--- ANÁLISE CONCLUÍDA ---")
                print("Status: \033[91mVIOLAÇÃO ENCONTRADA (BUG EM POTENCIAL)\033[0m")
                print("A asserção pode ser falsa. Um contra-exemplo foi encontrado:")
                model = self._solver.model()
                print(model)
                return False
            else:
                print("\n--- ANÁLISE CONCLUÍDA ---")
                print("Status: \033[93mINCONCLUSIVO\033[0m")
                print("O solver não conseguiu determinar o resultado (possivelmente devido a timeout ou complexidade).")
                return None

        except c_parser.ParseError as e:
            montar_log(f"Erro de parsing no código C: {e}", "ERROR")
            return None
        except Exception as e:
            montar_log(f"Ocorreu um erro inesperado durante a análise: {e}", "ERROR")
            import traceback
            traceback.print_exc()
            return None

# --- Interface de Linha de Comando ---

def main():
    """Função principal para executar a ferramenta via linha de comando."""
    parser = argparse.ArgumentParser(
        description="Quimera - Ferramenta de Análise Simbólica para Código C.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('c_file', help='Caminho para o arquivo .c contendo o código a ser analisado.')
    parser.add_argument(
        'assertion',
        help='A asserção em C a ser verificada (ex: "x > 10" ou "ptr->field == 0").'
    )
    args = parser.parse_args()

    try:
        with open(args.c_file, 'r') as f:
            c_code = f.read()
    except FileNotFoundError:
        montar_log(f"Erro: O arquivo '{args.c_file}' não foi encontrado.", "ERROR")
        return

    engine = Z3Wrapper()
    engine.check_c_assertion(c_code, args.assertion)


if __name__ == "__main__":
    main()