"""Consulta ao banco de notas: as notas que o usuário conferiu e salvou."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.db import NotaSalvaRegistro, ParticipanteRegistro, obter_sessao
from app.schemas.nota_fiscal import NotaSalvaDetalhe, NotaSalvaResumo, TipoDocumento

router = APIRouter(prefix="/api/banco/notas", tags=["banco de notas"])


def _buscar(nota_id: int, sessao: Session) -> NotaSalvaRegistro:
    nota = sessao.get(NotaSalvaRegistro, nota_id)
    if nota is None:
        raise HTTPException(404, "Nota não encontrada no banco de notas.")
    return nota


@router.get("", response_model=list[NotaSalvaResumo], summary="Lista as notas salvas, das mais recentes para as mais antigas")
def listar(
    tipo_documento: TipoDocumento | None = None,
    documento_emitente: str | None = None,
    emitida_de: date | None = None,
    emitida_ate: date | None = None,
    sessao: Session = Depends(obter_sessao),
):
    """Filtros opcionais: tipo, CNPJ/CPF do emitente (sem pontuação) e período de emissão."""
    consulta = (
        select(NotaSalvaRegistro)
        .options(selectinload(NotaSalvaRegistro.emitente))
        .order_by(NotaSalvaRegistro.id.desc())
    )
    if tipo_documento:
        consulta = consulta.where(NotaSalvaRegistro.tipo_documento == tipo_documento.value)
    if documento_emitente:
        consulta = consulta.join(NotaSalvaRegistro.emitente).where(
            or_(ParticipanteRegistro.cnpj == documento_emitente, ParticipanteRegistro.cpf == documento_emitente)
        )
    if emitida_de:
        consulta = consulta.where(NotaSalvaRegistro.data_emissao >= emitida_de)
    if emitida_ate:
        consulta = consulta.where(NotaSalvaRegistro.data_emissao <= emitida_ate)
    return sessao.scalars(consulta).all()


@router.get("/{nota_id}", response_model=NotaSalvaDetalhe, summary="Detalha uma nota salva, com o JSON extraído")
def obter(nota_id: int, sessao: Session = Depends(obter_sessao)):
    return _buscar(nota_id, sessao)


@router.delete("/{nota_id}", status_code=204, summary="Remove a nota do banco de notas (a área de trabalho não muda)")
def remover(nota_id: int, sessao: Session = Depends(obter_sessao)):
    sessao.delete(_buscar(nota_id, sessao))
    sessao.commit()
