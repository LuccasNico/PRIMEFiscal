"""Schema do JSON de saída.

O mesmo modelo Pydantic é usado em três lugares:
1. como formato de saída estruturada exigido do Claude (structured outputs);
2. como contrato da API REST;
3. como base para a validação fiscal e para a avaliação contra o XML.
"""

from datetime import date, datetime, timezone
from enum import Enum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator


def _em_utc(valor: datetime | None) -> datetime | None:
    # As datas são gravadas em UTC, mas o SQLite as devolve sem fuso
    return valor.replace(tzinfo=timezone.utc) if valor and valor.tzinfo is None else valor


DataHoraUTC = Annotated[datetime, AfterValidator(_em_utc)]


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
    endereco: str | None = Field(None, description="Logradouro, número e bairro")
    cep: str | None = Field(None, description="CEP com 8 dígitos, sem pontuação")
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


class Pagamento(BaseModel):
    forma: str = Field(description="Forma de pagamento, ex.: Dinheiro, Cartão de Débito, PIX, Boleto")
    valor: float | None = None


# Limite do único campo de texto livre: sem ele, modelos pequenos tendem a copiar o documento inteiro ali
LIMITE_INFORMACOES_COMPLEMENTARES = 500


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
    pagamentos: list[Pagamento] = Field(default_factory=list)
    informacoes_complementares: str | None = Field(
        None,
        description=(
            "Somente o texto do quadro 'Informações Complementares' ou 'Informações Adicionais', "
            f"resumido em até {LIMITE_INFORMACOES_COMPLEMENTARES} caracteres. Não repita itens, endereços, "
            "valores ou qualquer dado que já tenha campo próprio."
        ),
    )

    @field_validator("informacoes_complementares")
    @classmethod
    def _limitar_texto(cls, valor: str | None) -> str | None:
        return valor[:LIMITE_INFORMACOES_COMPLEMENTARES] if valor else valor


class ResultadoValidacao(BaseModel):
    valido: bool
    pontuacao: float = Field(description="Fração das verificações aplicáveis que passaram (0 a 1)")
    verificacoes: dict[str, bool] = Field(default_factory=dict)
    erros: list[str] = Field(default_factory=list)


class Metadados(BaseModel):
    abordagem: str
    provedor: str | None = Field(None, description="Nome do provedor de IA que fez a extração")
    modelo: str
    tokens_entrada: int | None = None
    tokens_saida: int | None = None
    tempo_ms: int


class StatusNota(str, Enum):
    PENDENTE = "pendente"  # na fila, aguardando a vez
    PROCESSANDO = "processando"  # sendo lida pela IA neste momento
    PROCESSADA = "processada"  # extraída e aprovada na validação fiscal
    REVISAR = "revisar"  # extraída, mas com inconsistências apontadas pela validação
    REVISADA = "revisada"  # corrigida manualmente
    ERRO = "erro"  # a extração falhou


STATUS_NA_FILA = (StatusNota.PENDENTE, StatusNota.PROCESSANDO)


# Status em que a extração terminou com sucesso e a nota pode ir para o banco de notas
STATUS_QUE_PODEM_SER_SALVOS = (StatusNota.PROCESSADA, StatusNota.REVISAR, StatusNota.REVISADA)


class SituacaoNoBanco(BaseModel):
    id: int = Field(description="Id da nota no banco de notas (/api/banco/notas/{id})")
    salva_em: DataHoraUTC
    atualizada_em: DataHoraUTC
    em_dia: bool = Field(
        description="Falso quando a nota foi corrigida ou reprocessada depois de salva: salve de novo para atualizar"
    )


class NotaFiscalResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    arquivo: str
    status: StatusNota
    lote_id: str | None = Field(None, description="Identifica as notas enviadas na mesma requisição")
    abordagem: str | None = None
    modelo: str | None = Field(None, description="Modelo de IA escolhido no envio; nulo = o padrão do provedor")
    tem_pdf: bool = Field(False, description="Indica se o PDF original está guardado no servidor")
    criado_em: DataHoraUTC
    enfileirado_em: DataHoraUTC | None = None
    iniciado_em: DataHoraUTC | None = None
    dados: NotaFiscalExtraida | None = None
    validacao: ResultadoValidacao | None = None
    metadados: Metadados | None = None
    erro: str | None = None
    no_banco: SituacaoNoBanco | None = Field(None, description="Preenchido quando a nota já foi salva no banco de notas")


class NotaSalvaResumo(BaseModel):
    """Nota do banco de notas, sem o JSON completo."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    processamento_id: int | None = Field(
        None, description="Nota da área de trabalho (/api/notas/{id}) que deu origem a esta; nulo se foi excluída"
    )
    tipo_documento: TipoDocumento
    chave_acesso: str | None = None
    numero: str | None = None
    serie: str | None = None
    data_emissao: date | None = None
    emitente_nome: str | None = None
    emitente_documento: str | None = Field(None, description="CNPJ ou CPF do emitente")
    valor_total_nota: float | None = None
    arquivo: str | None = Field(None, description="Nome do PDF de origem")
    salva_em: DataHoraUTC
    atualizada_em: DataHoraUTC


class NotaSalvaDetalhe(NotaSalvaResumo):
    dados: NotaFiscalExtraida = Field(description="O JSON extraído da nota")
    validacao: ResultadoValidacao | None = None
    abordagem: str | None = None
    provedor_ia: str | None = None
    modelo_ia: str | None = None


class RemocaoResposta(BaseModel):
    removidas: int
