import ast
from ast import AST, NodeVisitor
from typing import List, Tuple, Optional, Union


def parse_code(code: str) -> Optional[AST]:
    """Transforma código em AST. Se sintaxe inválida, retorna None."""
    try:
        return ast.parse(code)
    except SyntaxError as e:
        print(f"[Parser][SYNERR] {str(e)}")
        return None


def ast_depth(node: AST) -> int:
    """Calcula a profundidade máxima do AST."""
    class DepthCounter(NodeVisitor):
        def __init__(self):
            self.max_depth = 0
            self.current_depth = 0

        def generic_visit(self, node):
            self.current_depth += 1
            if self.current_depth > self.max_depth:
                self.max_depth = self.current_depth
            super().generic_visit(node)
            self.current_depth -= 1

    counter = DepthCounter()
    try:
        target = ast.parse(node) if isinstance(node, str) else node
    except SyntaxError:
        return 0
    counter.visit(node=target)
    return counter.max_depth


class _NodeCollector(NodeVisitor):
    """Coleta todos os nós de um AST."""
    def __init__(self):
        self.nodes = []

    def generic_visit(self, node):
        self.nodes.append(node)
        super().generic_visit(node)


class _NodeTypeCollector(NodeVisitor):
    """Coleta nós de um tipo específico do AST."""
    def __init__(self, nodetype: str):
        self.nodes = []
        self.nodetype = nodetype

    def visit(self, node):
        if node.__class__.__name__ == self.nodetype:
            self.nodes.append(node)
        return super().visit(node)


def ast_compare(ast1: AST, ast2: AST) -> Tuple[List[str], float]:
    """
    Compara dois ASTs e retorna a divergência estrutural.

    Retorna:
        - mismatch_nodes: lista de nomes de tipos de nós presentes em ast1
          mas não encontrados (por tipo) em ast2
        - match_ratio: razão de divergência (0.0 = clone; 1.0 = completamente novo)
    """
    # Coleta todos os nós de ambos os ASTs
    collector1 = _NodeCollector()
    collector1.visit(ast1)
    nodes1 = collector1.nodes

    collector2 = _NodeCollector()
    collector2.visit(ast2)
    nodes2 = collector2.nodes

    # Razão baseada na diferença de contagem de nós
    match_ratio = abs(len(nodes1) - len(nodes2)) / max(len(nodes1) + 1, 1)

    # Verifica nós em ast1 que não têm correspondência em ast2 (por tipo)
    mismatch_nodes = []
    tipos_ast2 = {n.__class__.__name__ for n in nodes2}
    for n1 in nodes1:
        tipo = n1.__class__.__name__
        if tipo not in tipos_ast2 and tipo not in mismatch_nodes:
            mismatch_nodes.append(tipo)

    return mismatch_nodes, match_ratio


def extrair_nodos(code1: str, code2: str, nodetype: str) -> Tuple[list, float]:
    """
    Extrai e compara nós de um tipo específico entre dois códigos.

    Retorna:
        - mismatch_nodes: lista de nós do tipo solicitado presentes em code1
          mas não em code2
        - match_ratio: razão de divergência na contagem do tipo específico
    """
    ast1 = parse_code(code1)
    ast2 = parse_code(code2)

    if not ast1 or not ast2:
        return [], 1.0

    collector1 = _NodeTypeCollector(nodetype)
    collector1.visit(ast1)
    nodes1 = collector1.nodes

    collector2 = _NodeTypeCollector(nodetype)
    collector2.visit(ast2)
    nodes2 = collector2.nodes

    match_ratio = abs(len(nodes1) - len(nodes2)) / max(len(nodes1) + 1, 1)

    mismatch_nodes = []
    tipos_ast2 = {n.__class__.__name__ for n in nodes2}
    for n1 in nodes1:
        tipo = n1.__class__.__name__
        if tipo not in tipos_ast2 and tipo not in mismatch_nodes:
            mismatch_nodes.append(tipo)

    return mismatch_nodes, match_ratio


class ASTNuance:
    """
    Métodos de comparação estrutural K-stable.
    """
    def mismatch_by_type(self, code1: str, code2: str, nodetype: str) -> Tuple[list, float]:
        ast1 = parse_code(code1)
        ast2 = parse_code(code2)

        if not ast1 or not ast2:
            print("[AST] Parse falha: código de entrada com sintaxe inválida.")
            return [], 1.0
        return extrair_nodos(code1, code2, nodetype)

    def calcular_drift(self, code1: str, code2: str) -> float:
        ast1 = parse_code(code1)
        ast2 = parse_code(code2)

        if not ast1 or not ast2:
            return 1.0

        max_depth = max(ast_depth(ast1), ast_depth(ast2), 1)
        drift_layers = abs(ast_depth(ast1) - ast_depth(ast2)) / max_depth
        mismatch_nodes, drift_base = ast_compare(ast1, ast2)

        # Drift total k-weighted
        drift_weight = (drift_base * 2 + drift_layers) / 3
        return drift_weight
