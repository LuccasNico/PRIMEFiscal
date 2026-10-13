from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.config import configuracoes

engine = create_engine(
    configuracoes.database_url,
    connect_args={"check_same_thread": False} if configuracoes.database_url.startswith("sqlite") else {},
)
SessaoLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


class NotaFiscalRegistro(Base):
    __tablename__ = "notas_fiscais"

    id: Mapped[int] = mapped_column(primary_key=True)
    arquivo: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), index=True)
    lote_id: Mapped[str | None] = mapped_column(String(36), index=True)
    tipo_documento: Mapped[str | None] = mapped_column(String(20))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    # O JSON completo fica em colunas JSON; tabelas normalizadas (emitente, itens) entram na Fase 3
    dados: Mapped[dict | None] = mapped_column(JSON)
    validacao: Mapped[dict | None] = mapped_column(JSON)
    metadados: Mapped[dict | None] = mapped_column(JSON)
    erro: Mapped[str | None] = mapped_column(Text)


def criar_tabelas() -> None:
    Base.metadata.create_all(engine)


def obter_sessao():
    sessao = SessaoLocal()
    try:
        yield sessao
    finally:
        sessao.close()
