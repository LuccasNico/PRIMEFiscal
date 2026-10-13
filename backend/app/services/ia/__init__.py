"""Seleciona o provedor de IA configurado em PROVEDOR_IA (claude ou lmstudio)."""

from app.config import configuracoes
from app.schemas.nota_fiscal import Metadados, NotaFiscalExtraida
from app.services.ia.base import ErroExtracao

__all__ = ["ErroExtracao", "extrair_de_pdf", "extrair_de_texto"]


def _provedor():
    if configuracoes.provedor_ia == "lmstudio":
        from app.services.ia import lmstudio

        return lmstudio
    from app.services.ia import claude

    return claude


def extrair_de_pdf(pdf_bytes: bytes) -> tuple[NotaFiscalExtraida, Metadados]:
    return _provedor().extrair_de_pdf(pdf_bytes)


def extrair_de_texto(texto: str) -> tuple[NotaFiscalExtraida, Metadados]:
    return _provedor().extrair_de_texto(texto)
