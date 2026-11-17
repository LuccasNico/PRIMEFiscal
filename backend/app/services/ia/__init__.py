"""Escolhe o provedor de IA configurado em PROVEDOR_IA.

Cada provedor é um módulo com as mesmas três funções: `extrair_de_pdf`, `extrair_de_texto`
e `descrever`. Para acrescentar outro, basta criar o módulo e registrá-lo em `_MODULOS`.
"""

from importlib import import_module

from app.config import configuracoes
from app.services.ia.base import ErroExtracao, Extracao, Provedor

__all__ = ["ErroExtracao", "descrever", "extrair_de_pdf", "extrair_de_texto"]

_MODULOS = {
    "gemini": "app.services.ia.gemini",
    "claude": "app.services.ia.claude",
    "lmstudio": "app.services.ia.lmstudio",
    "compativel": "app.services.ia.compativel",
}


def _provedor():
    # Importado só quando usado: quem não usa o Claude, por exemplo, não carrega o SDK da Anthropic
    return import_module(_MODULOS[configuracoes.provedor_ia])


def descrever() -> Provedor:
    return _provedor().descrever()


def extrair_de_pdf(pdf_bytes: bytes) -> Extracao:
    return _provedor().extrair_de_pdf(pdf_bytes)


def extrair_de_texto(texto: str) -> Extracao:
    return _provedor().extrair_de_texto(texto)
