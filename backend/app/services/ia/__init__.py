"""Seleciona o provedor de IA configurado em PROVEDOR_IA."""

from app.config import configuracoes
from app.schemas.nota_fiscal import Metadados, NotaFiscalExtraida
from app.services.ia.base import ErroExtracao

__all__ = ["ErroExtracao", "extrair_de_pdf", "extrair_de_texto"]


def _provedor():
    if configuracoes.provedor_ia == "lmstudio":
        from app.services.ia import lmstudio

        return lmstudio
    if configuracoes.provedor_ia == "compativel":
        from app.services.ia import compativel

        return compativel
    if configuracoes.provedor_ia == "gemini":
        from app.services.ia import gemini

        return gemini
    from app.services.ia import claude

    return claude


def extrair_de_pdf(pdf_bytes: bytes) -> tuple[NotaFiscalExtraida, Metadados]:
    return _provedor().extrair_de_pdf(pdf_bytes)


def extrair_de_texto(texto: str) -> tuple[NotaFiscalExtraida, Metadados]:
    return _provedor().extrair_de_texto(texto)
