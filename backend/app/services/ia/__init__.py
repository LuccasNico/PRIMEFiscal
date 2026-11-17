"""Escolhe o provedor de IA configurado em PROVEDOR_IA.

Cada provedor é um módulo com as mesmas três funções: `extrair_de_pdf`, `extrair_de_texto`
e `descrever`. Para acrescentar outro, basta criar o módulo e registrá-lo em `_MODULOS`.

Um provedor que também tenha `listar_modelos` deixa a interface escolher o modelo; nesse caso,
as funções de extração recebem o argumento `modelo`. Hoje, só o Gemini oferece a escolha.
"""

from importlib import import_module

from app.config import configuracoes
from app.services.ia.base import ErroExtracao, Extracao, Modelo, Provedor

__all__ = [
    "ErroExtracao",
    "Modelo",
    "descrever",
    "extrair_de_pdf",
    "extrair_de_texto",
    "listar_modelos",
    "permite_escolher_modelo",
]

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


def permite_escolher_modelo() -> bool:
    return hasattr(_provedor(), "listar_modelos")


def listar_modelos() -> list[Modelo]:
    """Modelos que podem ser escolhidos na interface. Só chame se `permite_escolher_modelo()`."""
    return _provedor().listar_modelos()


def _escolha(modelo: str | None) -> dict:
    # Um modelo guardado numa nota é ignorado se o provedor atual não permite escolher
    return {"modelo": modelo} if modelo and permite_escolher_modelo() else {}


def extrair_de_pdf(pdf_bytes: bytes, modelo: str | None = None) -> Extracao:
    return _provedor().extrair_de_pdf(pdf_bytes, **_escolha(modelo))


def extrair_de_texto(texto: str, modelo: str | None = None) -> Extracao:
    return _provedor().extrair_de_texto(texto, **_escolha(modelo))
