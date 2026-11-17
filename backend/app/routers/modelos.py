"""Modelos de IA que podem ser escolhidos na interface."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.acesso import exigir_acesso
from app.services import ia

router = APIRouter(prefix="/api/modelos", tags=["ia"], dependencies=[Depends(exigir_acesso)])


class ModeloResposta(BaseModel):
    id: str
    nome: str
    descricao: str = ""


class ListaDeModelos(BaseModel):
    padrao: str
    modelos: list[ModeloResposta]


def _modelos_disponiveis() -> list[ia.Modelo]:
    if not ia.permite_escolher_modelo():
        raise HTTPException(400, f"O provedor {ia.descrever().nome} não permite escolher o modelo pela interface.")
    try:
        return ia.listar_modelos()
    except ia.ErroExtracao as e:
        raise HTTPException(502, str(e)) from e


def modelo_escolhido(
    modelo: str | None = Query(None, max_length=100, description="Id do modelo (GET /api/modelos); se omitido, usa o padrão"),
) -> str | None:
    """Dependência das rotas que mandam notas para a fila: aceita só um modelo da lista."""
    if modelo is not None and modelo not in {disponivel.id for disponivel in _modelos_disponiveis()}:
        raise HTTPException(422, f"O modelo '{modelo}' não está disponível. Escolha outro na lista.")
    return modelo


@router.get(
    "",
    response_model=ListaDeModelos,
    summary="Lista os modelos do provedor de IA que podem ser escolhidos na interface",
)
def listar():
    """Hoje só o Gemini permite a escolha; a lista vem da própria API do Google, dos modelos mais novos para os
    mais antigos. `padrao` é o modelo usado quando a nota é enviada sem escolher um."""
    modelos = _modelos_disponiveis()
    padrao = ia.descrever().modelo
    if modelos and padrao not in {modelo.id for modelo in modelos}:
        padrao = modelos[0].id
    return ListaDeModelos(padrao=padrao, modelos=[ModeloResposta(**modelo._asdict()) for modelo in modelos])
