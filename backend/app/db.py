"""Tabelas do banco de dados.

São duas partes:

- **Área de trabalho** (``notas_fiscais``): a fila de processamento e o resultado de cada extração,
  que ainda pode ser reprocessado ou corrigido.
- **Banco de notas** (``notas_salvas``, ``participantes``, ``itens_nota`` e ``pagamentos_nota``): as notas
  que o usuário conferiu e salvou. Guarda o JSON extraído e, ao lado, os mesmos dados em tabelas
  relacionais, prontos para consultas e integração com outros sistemas.

O script ``banco/criar_banco.sql`` cria estas mesmas tabelas em um PostgreSQL (ex.: banco na nuvem).
"""

from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Engine,
    Float,
    ForeignKey,
    Identity,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    inspect,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app import armazenamento
from app.config import configuracoes

engine = create_engine(
    configuracoes.database_url,
    connect_args={"check_same_thread": False} if configuracoes.database_url.startswith("sqlite") else {},
    # Bancos na nuvem encerram conexões ociosas; isto testa a conexão antes de reutilizá-la
    pool_pre_ping=True,
)
SessaoLocal = sessionmaker(bind=engine, autoflush=False)


if engine.dialect.name == "sqlite":

    @event.listens_for(engine, "connect")
    def _ativar_chaves_estrangeiras(conexao_dbapi, _registro) -> None:
        # O SQLite só respeita FOREIGN KEY (ON DELETE CASCADE / SET NULL) com esta opção ligada
        cursor = conexao_dbapi.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()


def agora() -> datetime:
    return datetime.now(timezone.utc)


# JSONB no PostgreSQL (armazenamento binário, indexável); JSON comum nos demais bancos
JSONVariavel = JSON().with_variant(JSONB(), "postgresql")
# Valores em reais com 2 casas; devolvidos como float, igual ao JSON
Dinheiro = Numeric(15, 2, asdecimal=False)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------- Área de trabalho (fila)


class NotaFiscalRegistro(Base):
    __tablename__ = "notas_fiscais"
    # Sem isso o SQLite reaproveita o id de uma nota excluída, e o id também nomeia o PDF guardado
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    arquivo: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), index=True)
    lote_id: Mapped[str | None] = mapped_column(String(36), index=True)
    abordagem: Mapped[str | None] = mapped_column(String(10))
    # Modelo escolhido na interface; vazio = o padrão do provedor
    modelo: Mapped[str | None] = mapped_column(String(100))
    tipo_documento: Mapped[str | None] = mapped_column(String(20))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    # Ordem da fila: muda quando a nota é reprocessada, para ela voltar ao fim
    enfileirado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    iniciado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dados: Mapped[dict | None] = mapped_column(JSONVariavel)
    validacao: Mapped[dict | None] = mapped_column(JSONVariavel)
    metadados: Mapped[dict | None] = mapped_column(JSONVariavel)
    erro: Mapped[str | None] = mapped_column(Text)

    # Cópia no banco de notas, se a nota já foi salva. Carregada junto com a nota (uma consulta a
    # mais por listagem) porque a interface mostra em toda nota se ela está salva.
    nota_salva: Mapped["NotaSalvaRegistro | None"] = relationship(back_populates="processamento", lazy="selectin")

    @property
    def tem_pdf(self) -> bool:
        return armazenamento.tem_pdf(self.id)

    @property
    def no_banco(self) -> dict | None:
        """Situação da nota no banco de notas; ``em_dia`` é falso se os dados mudaram depois de salvos."""
        salva = self.nota_salva
        if salva is None:
            return None
        return {
            "id": salva.id,
            "salva_em": salva.salva_em,
            "atualizada_em": salva.atualizada_em,
            "em_dia": salva.dados == self.dados,
        }


# ---------------------------------------------------------------- Banco de notas


class ParticipanteRegistro(Base):
    """Emitente ou destinatário. Uma empresa (CNPJ) ou pessoa (CPF) aparece uma vez só."""

    __tablename__ = "participantes"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    cnpj: Mapped[str | None] = mapped_column(String(14), unique=True)
    cpf: Mapped[str | None] = mapped_column(String(11), unique=True)
    razao_social: Mapped[str | None] = mapped_column(String(255))
    inscricao_estadual: Mapped[str | None] = mapped_column(String(20))
    inscricao_municipal: Mapped[str | None] = mapped_column(String(20))
    endereco: Mapped[str | None] = mapped_column(String(255))
    cep: Mapped[str | None] = mapped_column(String(8))
    municipio: Mapped[str | None] = mapped_column(String(100))
    uf: Mapped[str | None] = mapped_column(String(2))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, onupdate=agora)


class NotaSalvaRegistro(Base):
    """Cabeçalho da nota salva: identificação, totais, impostos e o JSON completo."""

    __tablename__ = "notas_salvas"
    __table_args__ = (
        CheckConstraint(
            "tipo_documento IN ('NF-e', 'NFC-e', 'NFS-e', 'desconhecido')", name="ck_notas_salvas_tipo_documento"
        ),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    # Nota da área de trabalho que deu origem a esta; vira NULL se ela for excluída de lá
    processamento_id: Mapped[int | None] = mapped_column(
        ForeignKey("notas_fiscais.id", ondelete="SET NULL"), unique=True
    )
    tipo_documento: Mapped[str] = mapped_column(String(20))
    # A chave identifica a nota no país inteiro: a mesma nota não entra duas vezes (a NFS-e pode não ter)
    chave_acesso: Mapped[str | None] = mapped_column(String(44), unique=True)
    numero: Mapped[str | None] = mapped_column(String(20))
    serie: Mapped[str | None] = mapped_column(String(20))
    data_emissao: Mapped[date | None] = mapped_column(Date, index=True)
    emitente_id: Mapped[int | None] = mapped_column(ForeignKey("participantes.id"), index=True)
    destinatario_id: Mapped[int | None] = mapped_column(ForeignKey("participantes.id"), index=True)

    valor_total_produtos: Mapped[float | None] = mapped_column(Dinheiro)
    valor_desconto: Mapped[float | None] = mapped_column(Dinheiro)
    valor_frete: Mapped[float | None] = mapped_column(Dinheiro)
    valor_total_nota: Mapped[float | None] = mapped_column(Dinheiro)

    # Impostos: relação 1 para 1 com a nota, por isso ficam na mesma tabela
    base_calculo_icms: Mapped[float | None] = mapped_column(Dinheiro)
    valor_icms: Mapped[float | None] = mapped_column(Dinheiro)
    valor_icms_st: Mapped[float | None] = mapped_column(Dinheiro)
    valor_ipi: Mapped[float | None] = mapped_column(Dinheiro)
    valor_pis: Mapped[float | None] = mapped_column(Dinheiro)
    valor_cofins: Mapped[float | None] = mapped_column(Dinheiro)
    valor_iss: Mapped[float | None] = mapped_column(Dinheiro)
    valor_ibs: Mapped[float | None] = mapped_column(Dinheiro)
    valor_cbs: Mapped[float | None] = mapped_column(Dinheiro)
    valor_aproximado_tributos: Mapped[float | None] = mapped_column(Dinheiro)

    informacoes_complementares: Mapped[str | None] = mapped_column(Text)

    # Como a nota foi extraída
    arquivo: Mapped[str | None] = mapped_column(String(255))
    abordagem: Mapped[str | None] = mapped_column(String(10))
    provedor_ia: Mapped[str | None] = mapped_column(String(100))
    modelo_ia: Mapped[str | None] = mapped_column(String(100))
    validacao_valida: Mapped[bool | None] = mapped_column(Boolean)
    validacao_pontuacao: Mapped[float | None] = mapped_column(Float)

    # O JSON extraído, exatamente como estava na área de trabalho quando a nota foi salva
    dados: Mapped[dict] = mapped_column(JSONVariavel)
    validacao: Mapped[dict | None] = mapped_column(JSONVariavel)

    salva_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    atualizada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)

    processamento: Mapped[NotaFiscalRegistro | None] = relationship(back_populates="nota_salva")
    emitente: Mapped[ParticipanteRegistro | None] = relationship(foreign_keys=[emitente_id])
    destinatario: Mapped[ParticipanteRegistro | None] = relationship(foreign_keys=[destinatario_id])
    itens: Mapped[list["ItemRegistro"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="ItemRegistro.numero_item"
    )
    pagamentos: Mapped[list["PagamentoRegistro"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="PagamentoRegistro.id"
    )

    @property
    def emitente_nome(self) -> str | None:
        return self.emitente.razao_social if self.emitente else None

    @property
    def emitente_documento(self) -> str | None:
        return (self.emitente.cnpj or self.emitente.cpf) if self.emitente else None


class ItemRegistro(Base):
    __tablename__ = "itens_nota"
    __table_args__ = (UniqueConstraint("nota_id", "numero_item", name="uq_itens_nota_numero"),)

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    nota_id: Mapped[int] = mapped_column(ForeignKey("notas_salvas.id", ondelete="CASCADE"))
    numero_item: Mapped[int] = mapped_column(SmallInteger)  # posição na nota: 1, 2, 3...
    codigo: Mapped[str | None] = mapped_column(String(60))
    descricao: Mapped[str] = mapped_column(Text)
    ncm: Mapped[str | None] = mapped_column(String(8))
    cfop: Mapped[str | None] = mapped_column(String(4))
    unidade: Mapped[str | None] = mapped_column(String(20))
    quantidade: Mapped[float | None] = mapped_column(Numeric(15, 4, asdecimal=False))
    valor_unitario: Mapped[float | None] = mapped_column(Numeric(21, 10, asdecimal=False))
    valor_total: Mapped[float | None] = mapped_column(Dinheiro)


class PagamentoRegistro(Base):
    __tablename__ = "pagamentos_nota"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    nota_id: Mapped[int] = mapped_column(ForeignKey("notas_salvas.id", ondelete="CASCADE"), index=True)
    forma: Mapped[str] = mapped_column(String(60))
    valor: Mapped[float | None] = mapped_column(Dinheiro)


# ---------------------------------------------------------------- Criação e sessão


def adicionar_colunas_novas(motor: Engine) -> None:
    """Migração mínima: acrescenta as colunas que faltam em bancos criados por versões anteriores.

    O create_all só cria tabelas inexistentes. Como todas as colunas novas aceitam NULL,
    um ALTER TABLE ... ADD COLUMN basta e evita depender de uma ferramenta de migração no protótipo.
    """
    tabela = NotaFiscalRegistro.__table__
    existentes = {coluna["name"] for coluna in inspect(motor).get_columns(tabela.name)}
    with motor.begin() as conexao:
        for coluna in tabela.columns:
            if coluna.name not in existentes:
                tipo = coluna.type.compile(motor.dialect)
                conexao.execute(text(f"ALTER TABLE {tabela.name} ADD COLUMN {coluna.name} {tipo}"))


def criar_tabelas() -> None:
    """Cria as tabelas que ainda não existem. Num banco criado pelo script SQL, não faz nada."""
    Base.metadata.create_all(engine)
    adicionar_colunas_novas(engine)


def obter_sessao():
    sessao = SessaoLocal()
    try:
        yield sessao
    finally:
        sessao.close()
