# quimera/db/schemas.py

from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime

"""
Este módulo define os schemas Pydantic para o projeto Quimera.
Os schemas são usados para validação de dados, serialização e documentação da API de dados.
Eles garantem que os dados trocados entre a lógica da aplicação e a camada de banco de dados
sejam bem-formados e sigam uma estrutura previsível.
"""

# --- Schemas para ScriptProfile ---

class ScriptProfileBase(BaseModel):
    """Schema base com campos comuns para um perfil de script."""
    caminho_arquivo: str = Field(..., description="Caminho absoluto para o arquivo de código-fonte.")
    hash_atual: str = Field(..., max_length=64, description="Hash SHA-256 do conteúdo atual do arquivo.")

class ScriptProfileCreate(ScriptProfileBase):
    """Schema usado para criar um novo perfil de script no banco de dados."""
    pass

class ScriptProfileSchema(ScriptProfileBase):
    """Schema completo para representar um perfil de script lido do banco de dados."""
    id: int = Field(..., gt=0, description="Identificador único do perfil de script.")
    ultima_modificacao: datetime = Field(..., description="Timestamp da última modificação registrada.")

    class Config:
        from_attributes = True # Permite que o Pydantic mapeie dados de um objeto ORM.

# --- Schemas para HistoricoPatch ---

class HistoricoPatchBase(BaseModel):
    """Schema base com campos comuns para um registro de histórico de patch."""
    patch_id: str = Field(..., max_length=64, description="ID único do patch (hash do seu conteúdo).")
    conteudo_patch: str = Field(..., description="O conteúdo completo do patch no formato diff.")
    status: str = Field("proposto", description="Status atual do patch (ex: 'proposto', 'aplicado').")
    agente_criador: str = Field(..., description="Nome do agente de IA que gerou o patch.")
    score_avaliacao: Optional[float] = Field(None, ge=0.0, le=1.0, description="Score de avaliação do patch (0.0 a 1.0).")
    comentario: Optional[str] = Field(None, description="Comentários ou justificativas do Agente Crítico ou Mestra.")

class HistoricoPatchCreate(HistoricoPatchBase):
    """Schema usado para criar um novo registro de histórico de patch."""
    perfil_script_id: int = Field(..., gt=0, description="ID do perfil de script ao qual este patch pertence.")

class HistoricoPatchSchema(HistoricoPatchBase):
    """Schema completo para representar um registro de patch lido do banco de dados."""
    id: int = Field(..., gt=0, description="Identificador único do registro de patch.")
    perfil_script_id: int
    timestamp_aplicacao: datetime = Field(..., description="Timestamp de quando o patch foi criado ou aplicado.")

    class Config:
        from_attributes = True

# --- Schemas para RegistroDrift ---

class RegistroDriftBase(BaseModel):
    """Schema base com campos comuns para um registro de drift."""
    tipo_drift: str = Field(..., description="Tipo de drift detectado (ex: 'sintaxe', 'seguranca').")
    score_drift: float = Field(..., ge=0.0, le=1.0, description="Pontuação da severidade do drift (0.0 a 1.0).")
    detalhes: Optional[str] = Field(None, description="Descrição detalhada do drift encontrado.")
    resolvido: bool = Field(False, description="Indica se o drift foi resolvido por um patch subsequente.")

class RegistroDriftCreate(RegistroDriftBase):
    """Schema usado para criar um novo registro de drift."""
    perfil_script_id: int = Field(..., gt=0, description="ID do perfil de script onde o drift foi detectado.")

class RegistroDriftSchema(RegistroDriftBase):
    """Schema completo para representar um registro de drift lido do banco de dados."""
    id: int = Field(..., gt=0, description="Identificador único do registro de drift.")
    perfil_script_id: int
    detectado_em: datetime = Field(..., description="Timestamp de quando o drift foi detectado.")

    class Config:
        from_attributes = True

# --- Schemas para MetricaAgente ---

class MetricaAgenteBase(BaseModel):
    """Schema base com campos comuns para a métrica de um agente."""
    nome_modelo: str = Field(..., description="Nome único do modelo do agente (ex: 'llama3-70b-8192').")
    usos: int = Field(0, ge=0, description="Número total de vezes que o agente foi selecionado.")
    score_total: float = Field(0.0, ge=0.0, description="Soma cumulativa de todos os scores de recompensa recebidos.")
    sucessos: int = Field(0, ge=0, description="Número de vezes que o agente contribuiu para uma solução bem-sucedida.")

class MetricaAgenteCreate(MetricaAgenteBase):
    """Schema usado para criar um novo registro de métrica de agente."""
    pass

class MetricaAgenteSchema(MetricaAgenteBase):
    """Schema completo para representar a métrica de um agente lida do banco de dados."""
    id: int = Field(..., gt=0, description="Identificador único do registro de métrica.")

    class Config:
        from_attributes = True

# --- Schemas para MissaoTecnica ---

class MissaoTecnicaBase(BaseModel):
    """Schema base com campos comuns para uma missão técnica."""
    log_erro_inicial: str = Field(..., description="O log de compilação completo que iniciou a missão.")
    status_final: str = Field(..., description="O status final da missão (ex: 'sucesso', 'falha_missao').")
    mensagem_final: Optional[str] = Field(None, description="Uma mensagem descritiva sobre o resultado da missão.")

class MissaoTecnicaCreate(MissaoTecnicaBase):
    """Schema usado para criar um novo registro de missão técnica."""
    patch_vencedor_id: Optional[int] = Field(None, gt=0, description="ID do patch vencedor, se houver.")

class MissaoTecnicaSchema(MissaoTecnicaBase):
    """Schema completo para representar uma missão técnica lida do banco de dados."""
    id: int = Field(..., gt=0, description="Identificador único da missão.")
    iniciada_em: datetime
    finalizada_em: Optional[datetime] = None
    patch_vencedor: Optional[HistoricoPatchSchema] = None # Aninha o schema do patch vencedor

    class Config:
        from_attributes = True

# --- Schemas para HistoricoRefatoracao ---
# Este schema Pydantic corresponde ao modelo HistoricoRefatoracao em models.py.
# Ele contém APENAS as colunas que o AgenteGerador tenta inserir.
class HistoricoRefatoracaoBase(BaseModel):
    """Schema base para o histórico de refatorações (gerado pelo AgenteGerador)."""
    modelo_gerador: str = Field(..., description="Nome do modelo/agente que gerou este item.")
    log_erro_original: str = Field(..., description="Log de erro original para esta refatoração.")
    analise_causa_raiz: Any = Field(..., description="Análise de causa raiz (JSON/Dict).") # Any para flexibilidade
    patch_content: str = Field(..., description="Conteúdo do patch ou refatoração.")

class HistoricoRefatoracaoCreate(HistoricoRefatoracaoBase):
    """Schema para criação de um registro de histórico de refatoração."""
    pass

class HistoricoRefatoracaoSchema(HistoricoRefatoracaoBase):
    """Schema completo para leitura de um registro de histórico de refatoração."""
    id: int = Field(..., gt=0, description="ID do registro.")
    timestamp: datetime = Field(..., description="Timestamp da refatoração.")

    class Config:
        from_attributes = True

# --- Schemas para EntradaAnalise ---
# Este schema Pydantic corresponde ao modelo EntradaAnaliseModel em models.py.
class EntradaAnaliseBase(BaseModel):
    """Schema base para uma entrada de análise de causa raiz."""
    modelo: str = Field(..., description="Nome do modelo LLM usado para a análise.")
    log_bruto: str = Field(..., description="Log de erro completo que foi analisado.")
    resultado: Any = Field(..., description="Resultado estruturado da análise da causa raiz (Dict[str, Any]).")

class EntradaAnalise(EntradaAnaliseBase): # Este é o schema a ser usado para CRIAÇÃO
    """Schema usado para criar uma nova entrada de análise no banco de dados."""
    pass

class EntradaAnaliseSchema(EntradaAnaliseBase):
    """Schema completo para representar uma entrada de análise lida do banco de dados."""
    id: int = Field(..., gt=0, description="Identificador único da entrada de análise.")
    timestamp: datetime = Field(..., description="Timestamp da análise.")

    class Config:
        from_attributes = True