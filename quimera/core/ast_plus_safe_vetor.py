# quimera/core/ast_plus_safe_vetor.py

# Verificações de dependências adicionadas automaticamente
def verificar_dependencia(nome_modulo, funcionalidade="essa funcionalidade"):
    """Verifica se uma dependência está disponível"""
    try:
        __import__(nome_modulo)
        return True
    except ImportError:
        print(f"⚠️  {nome_modulo} não instalado - {funcionalidade} não disponível")
        return False

import logging
_logger = logging.getLogger(__name__)


def _unavailable_feature(feature_name: str, *args, **kwargs):
    """Loga warning quando funcionalidade não está disponível por falta de dependências."""
    _logger.warning(f"Funcionalidade '{feature_name}' indisponível — dependência não instalada")
    return None

import logging
try:
    import numpy as np
except ImportError:
    np = None  # Mock
# import faiss # Se for usar FAISS real, precisa instalar faiss-cpu
from typing import Dict, Any, List, Optional
import asyncio # Para asyncio.to_thread

# Importações internas para este módulo (assegurar que existam)
from quimera.core.vector_manager import VectorManager # Para VectorManager
# Não importamos QuadroNegro diretamente aqui para evitar dependências circulares.
# A interação com o histórico viria via VectorManager ou serviço de DB.

logger = logging.getLogger("VetorNeuralLaw")

class VetorNeuralLaw:
    """
    Legislação subjetiva do código: Avalia o "drift" (desvio) de um segmento de código
    em relação ao histórico de mudanças problemáticas. Se o drift for alto
    e similar a algo que falhou antes, o sistema pode aplicar um VETO.

    Adaptado do seu estudo 'ast_plus_safe_vetor.py'.
    """

    def __init__(self, vector_db_path: str = "./quimera_vectors.npz"):
        """
        Inicializa a Lei Neural Vetorial.

        Args:
            vector_db_path (str): Caminho para o banco de dados de vetores.
        """
        self.vector_manager = VectorManager(vector_db_path)
        # O histórico de mudanças problemáticas viria do banco de dados (ErrorHistorico, ConformanceHistory)
        # ou de um cache de vetores de código "ruins". Por enquanto, é conceitual.
        self.historic_mudancas_problematicas: Dict[str, List[float]] = {} # Hash do código -> vetor
        self._carregar_historico_problematico() # Carrega histórico real com fallback para seed vectors

        logger.info(f"[{self.__class__.__name__}] Inicializado com DB de vetores em '{vector_db_path}'.")

    def _carregar_historico_problematico(self):
        """Carrega histórico real de patches que falharam, do DB e/ou engineering_memory."""
        count = 0
        
        # 1. Tentar carregar do banco de dados
        try:
            from quimera.db.base import get_db
            with get_db() as db:
                # Busca registros de drift resolvidos como referência negativa
                from quimera.db.models import RegistroDrift
                drifts = db.query(RegistroDrift).filter(
                    RegistroDrift.resolvido == True
                ).limit(50).all()
                for entry in drifts:
                    if entry.detalhes:
                        vec = self.vector_manager.as_full_vector(entry.detalhes[:500])
                        if vec:
                            self.historic_mudancas_problematicas[f"db_drift_{entry.id}"] = vec
                            count += 1
        except Exception:
            logger.debug("DB unavailable for conformance history — using file-based fallback")
        
        # 2. Fallback: carregar do engineering_memory.jsonl
        if count == 0:
            try:
                import json as _json
                from pathlib import Path
                em_path = Path(__file__).parent.parent / "logs" / "engineering_memory.jsonl"
                if em_path.exists():
                    with open(em_path) as f:
                        for line in f:
                            if count >= 50:
                                break
                            try:
                                record = _json.loads(line)
                                patch_code = record.get("patch_code", record.get("patch", ""))
                                success = record.get("success", record.get("compilation_success", True))
                                if not success and patch_code:
                                    vec = self.vector_manager.as_full_vector(patch_code[:500])
                                    if vec:
                                        self.historic_mudancas_problematicas[f"em_{record.get('id', count)}"] = vec
                                        count += 1
                            except Exception:
                                pass
            except Exception:
                logger.debug("engineering_memory.jsonl unavailable")
        
        # 3. Último fallback: seed vectors sintáticos mínimos
        if count == 0:
            self.historic_mudancas_problematicas = {
                "seed_strcpy": self.vector_manager.as_full_vector("strcpy(dest, src)"),
                "seed_null": self.vector_manager.as_full_vector("NULL pointer dereference"),
                "seed_overflow": self.vector_manager.as_full_vector("buffer overflow"),
            }
            logger.info(f"[{self.__class__.__name__}] Seed vectors carregados (sem DB disponível)")
        else:
            logger.info(f"[{self.__class__.__name__}] {count} vetores problemáticos carregados")

    async def analisar_dset(self, code: str) -> Dict[str, Any]:
        """
        Analisa um segmento de código para detectar similaridade com padrões problemáticos históricos.

        Args:
            code (str): O segmento de código a ser analisado.

        Returns:
            Dict[str, Any]: Dicionário com 'status' ("OK" ou "VETO") e 'porque'.
        """
        if not self.historic_mudancas_problematicas:
            logger.info(f"[{self.__class__.__name__}] Histórico problemático vazio. Nenhuma análise de VETO por similaridade será feita.")
            return {"status": "OK", "porque": "Histórico problemático indisponível."}

        code_vector = self.vector_manager.as_full_vector(code)

        # Calcula o drift (dissimilaridade) com cada vetor problemático conhecido
        drifts = []
        for problem_hash, problem_vector in self.historic_mudancas_problematicas.items():
            drift = self.vector_manager.get_drift(problem_vector, code_vector)
            drifts.append(drift)

        if not drifts:
            return {"status": "OK", "porque": "Nenhum vetor de histórico para comparação."}

        min_drift = min(drifts) # O menor drift significa a MAIOR similaridade

        # Limiar de veto: se a similaridade for muito alta (drift muito baixo) com um código problemático
        # Ajuste este limiar conforme a necessidade (ex: 0.15 significa 85% de similaridade)
        VETO_DRIFT_THRESHOLD = 0.15

        if min_drift < VETO_DRIFT_THRESHOLD:
            logger.warning(f"[{self.__class__.__name__}] [VETO] Código detectado com alta similaridade ({min_drift:.4f} drift) a um padrão problemático conhecido. VETADO!")
            return {"status": "VETO", "porque": f"Alta similaridade ({min_drift:.4f} drift) com código problemático histórico."}

        logger.info(f"[{self.__class__.__name__}] Código considerado OK (menor drift: {min_drift:.4f}).")
        return {"status": "OK", "porque": "Sem drift perigoso perceptível."}