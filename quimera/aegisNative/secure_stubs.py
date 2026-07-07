# quimera/aegisNative/secure_stubs.py

import os
import hashlib
import time
from collections import Counter
import re
import logging
from typing import Dict, Any, Tuple

# Importa módulos de utilidade
from quimera.logs.parser import montar_log
# check_blacklist: segurança via sandbox # Reutilizamos a função da blacklist

logger = logging.getLogger(__name__)

def check_gene_collision(hashcode: str) -> bool:
    """
    Verifica se um hash de código (representando um "gene" ou mutação) colide com
    hashes de "genes" proibidos ou maliciosos previamente conhecidos.
    Este seria um banco de dados de "assinaturas" de código malicioso ou que causou problemas graves.
    """
    montar_log(f"Verificando colisão de genes para hash: {hashcode[:8]}...", log_level="DEBUG")

    # Exemplo de "genes" (hashes) proibidos
    # Em um sistema real, isso viria de um arquivo de configuração ou DB de ameaças.
    prohibited_genes = {
        "deadbeef0123456789abcdef0123456789abcdef0123456789abcdef0123456789": "Exploit: Kernel Panic NulPoinTer",
        "malwarehash0123456789abcdef0123456789abcdef0123456789abcdef012345": "Malware: Rootkit Backdoor",
        # ... adicionar mais hashes de patologias conhecidas
    }

    if hashcode in prohibited_genes:
        montar_log(f"[GENE_COLLISION] Hash de gene proibido detectado: {hashcode[:8]}... Motivo: {prohibited_genes[hashcode]}", log_level="CRITICAL")
        return True # Colisão detectada

    # Critério heurístico adicional (ex: hashes que parecem aleatórios demais ou muito repetitivos)
    # Exemplo: Se o hash começar ou terminar com muitos zeros ou for repetitivo.
    if hashcode.startswith("0000") or hashcode.endswith("0000"):
        montar_log(f"[GENE_COLLISION] Hash suspeito detectado: {hashcode[:8]}... Padrão de início/fim incomum.", log_level="WARNING")
        # Dependendo da severidade, isso pode ser um `return True` para bloquear imediatamente.

    return False # Nenhuma colisão detectada

def type_safecheck(source_code: str) -> bool:
    """
    Realiza uma verificação de segurança de alto nível baseada em padrões de código,
    integridade e contexto. É uma versão "turbinada" do linting e da análise de segurança estática.
    """
    montar_log("Executando type_safecheck (verificação de segurança turbinada)...", log_level="DEBUG")

    # --- Passo 1: Verificar contra a blacklist de padrões ---
    if checar_blacklist(source_code):
        montar_log("[TYPE_SAFECHECK] Código contém padrões da blacklist. INSEGURO.", log_level="CRITICAL")
        return False # Não é seguro se contiver itens da blacklist

    # --- Passo 2: Análise heurística de complexidade e anomalias ---
    # Em um sistema real, isso envolveria:
    # 1. Análise de AST (com pycparser) para verificar tipos, ponteiros, fluxo de dados.
    # 2. Heurísticas de complexidade (ciclomática, aninhamento).
    # 3. Análise de taticas de evasao de seguranca (ex: ofuscação de strings, chamadas indiretas).

    # Exemplo simplificado: verifica se há muitos includes ou linhas muito longas (pode indicar código gerado ou confuso)
    num_includes = source_code.count("#include")
    max_line_len = max(len(line) for line in source_code.splitlines()) if source_code else 0

    if num_includes > 50 or max_line_len > 200: # Limiares arbitrários
        montar_log("[TYPE_SAFECHECK] Código com alta contagem de includes ou linhas muito longas. Possível ofuscação ou complexidade excessiva.", log_level="WARNING")
        # return False # Se isso for um critério rigoroso

    # Exemplo: verifica se há uso de ponteiros desreferenciados sem verificação de nulidade (heurística simples)
    if "->" in source_code and "if (" not in source_code.replace("->", "").__repr__(): # Muito rudimentar, precisa de AST real
        montar_log("[TYPE_SAFECHECK] Possível uso de ponteiro sem verificação de nulidade (heurística).", log_level="WARNING")
        # return False

    montar_log("Type-safecheck concluído. Código considerado seguro pelas regras atuais.", log_level="DEBUG")
    return True # Passou nas verificações de segurança base


def check_in_kernelguard(path_kernel: str) -> Dict[str, Any]:
    """
    A função que atua como um "kernel guard", inspecionando o código do kernel
    para detectar anomalias e possíveis falhas de segurança antes de permitir operações críticas.
    """
    montar_log(f"Iniciando KernelGuard para: {path_kernel}", log_level="INFO")

    inspection_results = {
        "timestamp": time.time(),
        "is_safe": True, # Indicação geral de segurança
        "BD": 0, # "Badness Detector": Métrica de qualidade/segurança
        "objdig": 0, # "Object Digest": Hash/checksum de integridade
        "lugars": {}, # Contagem de construções/padrões específicos
        "flag_REF": False, # Detecção de referências/flags suspeitas
        "elapsed": 0.0, # Tempo gasto na inspeção
        "details": [] # Detalhes dos problemas encontrados
    }

    try:
        if not os.path.exists(path_kernel):
            montar_log(f"[KERNEL_GUARD] Arquivo do kernel não encontrado: {path_kernel}", log_level="ERROR")
            inspection_results["is_safe"] = False
            inspection_results["details"].append("Arquivo não encontrado.")
            return inspection_results

        with open(path_kernel, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()

        # --- 1. Verificação de Colisão de Genes / Hash Proibido ---
        code_hash = hashlib.sha256(code.encode('utf-8')).hexdigest()
        if check_gene_collision(code_hash):
            inspection_results["is_safe"] = False
            inspection_results["details"].append("Colisão de gene detectada (hash proibido).")

        # --- 2. Type-Safecheck e Blacklist ---
        if not type_safecheck(code):
            inspection_results["is_safe"] = False
            inspection_results["details"].append("Type-safecheck falhou (padrões de blacklist ou anomalias).")

        # --- 3. Análise de Padrões e Contagens ("Badness Detector", "Lugares") ---
        # A. Complexidade Heurística (simulada por maiúsculas no hash, mas poderia ser análise AST)
        inspection_results["BD"] = sum(c.isupper() for c in code_hash[:20]) # Exemplo simples de métrica
        if inspection_results["BD"] > 10: # Limiar arbitrário
            montar_log("[KERNEL_GUARD] Alta 'Badness' heurística detectada.", log_level="WARNING")
            # inspection_results["is_safe"] = False # Se for um critério de segurança

        # B. Contagem de certas construções (ex: chamadas de função, macros)
        inspection_results["lugars"] = Counter(i[0] for i in re.findall(r"(\w+)\(", code)) # Conta chamadas de função
        if inspection_results["lugars"].get("system", 0) > 0: # Exemplo: detecta chamadas a 'system()'
            montar_log("[KERNEL_GUARD] Chamadas a 'system()' detectadas. Potencial risco de segurança.", log_level="CRITICAL")
            inspection_results["is_safe"] = False
            inspection_results["details"].append("Chamada 'system()' detectada.")

        # --- 4. Verificação de Integridade do Objeto (hash do arquivo) ---
        inspection_results["objdig"] = os.stat(path_kernel).st_ino # Inode number (identificador do arquivo no FS)
        # Pode adicionar hash do arquivo completo para comparação com um hash conhecido de um "estado seguro".

        # --- 5. Detecção de Flags/Referências Suspeitas ---
        if re.search(r'__kernel_execution\s*=\s*"[^"]*"', code):
            inspection_results["flag_REF"] = True
            montar_log("[KERNEL_GUARD] Flag de execução de kernel suspeita encontrada. Requer atenção.", log_level="WARNING")

    except Exception as e:
        montar_log(f"[KERNEL_GUARD] Erro inesperado durante a inspeção: {e}", log_level="ERROR")
        inspection_results["is_safe"] = False # Em caso de erro na inspeção, assume que não é seguro
        inspection_results["details"].append(f"Erro inesperado durante a inspeção: {str(e)}")

    inspection_results["elapsed"] = time.time() - inspection_results["timestamp"]
    montar_log(f"KernelGuard concluído. Segurança: {inspection_results['is_safe']}. Tempo: {inspection_results['elapsed']:.2f}s", log_level="INFO")

    return inspection_results