"""Schema do JSON de saída.

O mesmo modelo Pydantic é usado em três lugares:
1. como formato de saída estruturada exigido do Claude (structured outputs);
2. como contrato da API REST;
3. como base para a validação fiscal e para a avaliação contra o XML.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TipoDocumento(str, Enum):
    NFE = "NF-e"
    NFCE = "NFC-e"
    NFSE = "NFS-e"
    DESCONHECIDO = "desconhecido"


class Participante(BaseModel):
    razao_social: str | None = Field(None, description="Nome ou razão social")
    cnpj: str | None = Field(None, description="CNPJ com 14 caracteres, sem pontuação")
    cpf: str | None = Field(None, description="CPF com 11 dígitos, sem pontuação")
    inscricao_estadual: str | None = None
    inscricao_municipal: str | None = None
    municipio: str | None = None
    uf: str | None = Field(None, description="Sigla do estado, ex.: SP")


class Item(BaseModel):
    codigo: str | None = Field(None, description="Código do produto ou serviço")
    descricao: str
    ncm: str | None = None
    cfop: str | None = None
    unidade: str | None = Field(None, description="Unidade comercial, ex.: UN, KG")
    quantidade: float | None = None
    valor_unitario: float | None = None
    valor_total: float | None = None


class Impostos(BaseModel):
    base_calculo_icms: float | None = None
    valor_icms: float | None = None
    valor_icms_st: float | None = None
    valor_ipi: float | None = None
    valor_pis: float | None = None
    valor_cofins: float | None = None
    valor_iss: float | None = Field(None, description="ISS (NFS-e)")
    valor_ibs: float | None = Field(None, description="IBS (reforma tributária)")
    valor_cbs: float | None = Field(None, description="CBS (reforma tributária)")
    valor_aproximado_tributos: float | None = Field(
        None, description="Valor aproximado dos tributos (Lei 12.741/2012)"
    )


class NotaFiscalExtraida(BaseModel):
    tipo_documento: TipoDocumento
    chave_acesso: str | None = Field(None, description="Chave de acesso com 44 dígitos, sem espaços")
    numero: str | None = None
    serie: str | None = None
    data_emissao: str | None = Field(None, description="Data de emissão no formato AAAA-MM-DD")
    emitente: Participante
    destinatario: Participante | None = None
    itens: list[Item] = Field(default_factory=list, description="Todos os itens ou serviços, na ordem do documento")
    impostos: Impostos = Field(default_factory=Impostos)
    valor_total_produtos: float | None = Field(None, description="Soma dos itens (ou valor dos serviços)")
    valor_desconto: float | None = None
    valor_frete: float | None = None
    valor_total_nota: float | None = None
    observacoes: str | None = Field(None, description="Informações complementares relevantes")


class ResultadoValidacao(BaseModel):
    valido: bool
    pontuacao: float = Field(description="Fração das verificações aplicáveis que passaram (0 a 1)")
    verificacoes: dict[str, bool] = Field(default_factory=dict)
    erros: list[str] = Field(default_factory=list)


class Metadados(BaseModel):
    abordagem: str
    modelo: str
    tokens_entrada: int | None = None
    tokens_saida: int | None = None
    tempo_ms: int


class StatusNota(str, Enum):
    PENDENTE = "pendente"
    PROCESSADA = "processada"
    REVISAR = "revisar"
    REVISADA = "revisada"
    ERRO = "erro"


class NotaFiscalResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    arquivo: str
    status: StatusNota
    lote_id: str | None = None
    criado_em: datetime
    dados: NotaFiscalExtraida | None = None
    validacao: ResultadoValidacao | None = None
    metadados: Metadados | None = None
    erro: str | None = None


class LoteResposta(BaseModel):
    lote_id: str
    notas: list[int]
