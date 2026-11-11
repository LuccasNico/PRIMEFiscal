from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Engine, String, Text, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app import armazenamento
from app.config import configuracoes

engine = create_engine(
    configuracoes.database_url,
    connect_args={"check_same_thread": False} if configuracoes.database_url.startswith("sqlite") else {},
)
SessaoLocal = sessionmaker(bind=engine, autoflush=False)


def agora() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class NotaFiscalRegistro(Base):
    __tablename__ = "notas_fiscais"
    # Sem isso o SQLite reaproveita o id de uma nota excluída, e o id também nomeia o PDF guardado
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    arquivo: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), index=True)
    lote_id: Mapped[str | None] = mapped_column(String(36), index=True)
    abordagem: Mapped[str | None] = mapped_column(String(10))
    tipo_documento: Mapped[str | None] = mapped_column(String(20))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    # Ordem da fila: muda quando a nota é reprocessada, para ela voltar ao fim
    enfileirado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    iniciado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # O JSON completo fica em colunas JSON; tabelas normalizadas (emitente, itens) entram na Fase 3
    dados: Mapped[dict | None] = mapped_column(JSON)
    validacao: Mapped[dict | None] = mapped_column(JSON)
    metadados: Mapped[dict | None] = mapped_column(JSON)
    erro: Mapped[str | None] = mapped_column(Text)

    @property
    def tem_pdf(self) -> bool:
        return armazenamento.tem_pdf(self.id)


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
    Base.metadata.create_all(engine)
    adicionar_colunas_novas(engine)


def obter_sessao():
    sessao = SessaoLocal()
    try:
        yield sessao
    finally:
        sessao.close()
