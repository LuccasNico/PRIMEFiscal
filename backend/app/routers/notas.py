import uuid

import anthropic
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import configuracoes
from app.db import NotaFiscalRegistro, SessaoLocal, obter_sessao
from app.schemas.nota_fiscal import (
    LoteResposta,
    NotaFiscalExtraida,
    NotaFiscalResposta,
    StatusNota,
)
from app.services.ia import ErroExtracao
from app.services.processamento import Abordagem, processar_pdf
from app.services.validacao import validar_nota

router = APIRouter(prefix="/api/notas", tags=["notas"])


async def _ler_pdf(arquivo: UploadFile) -> bytes:
    conteudo = await arquivo.read()
    if not conteudo.startswith(b"%PDF"):
        raise HTTPException(415, f"'{arquivo.filename}' não é um PDF.")
    if len(conteudo) > configuracoes.tamanho_maximo_bytes:
        raise HTTPException(413, f"'{arquivo.filename}' excede o tamanho máximo permitido.")
    return conteudo


def _aplicar_processamento(registro: NotaFiscalRegistro, pdf_bytes: bytes, abordagem: Abordagem) -> None:
    """Processa o PDF e grava o resultado (ou o erro) no registro."""
    try:
        dados, validacao, metadados = processar_pdf(pdf_bytes, abordagem)
    except ErroExtracao as e:
        registro.status, registro.erro = StatusNota.ERRO.value, str(e)
        return
    except anthropic.APIStatusError as e:
        registro.status, registro.erro = StatusNota.ERRO.value, f"Erro na Claude API ({e.status_code}): {e.message}"
        return
    except anthropic.APIConnectionError:
        registro.status, registro.erro = StatusNota.ERRO.value, "Falha de conexão com a Claude API."
        return

    registro.tipo_documento = dados.tipo_documento.value
    registro.dados = dados.model_dump(mode="json")
    registro.validacao = validacao.model_dump(mode="json")
    registro.metadados = metadados.model_dump(mode="json")
    registro.status = (StatusNota.PROCESSADA if validacao.valido else StatusNota.REVISAR).value
    registro.erro = None


@router.post("", response_model=NotaFiscalResposta, summary="Envia e processa uma nota fiscal")
async def enviar_nota(
    arquivo: UploadFile = File(...),
    abordagem: Abordagem = Query(Abordagem.PDF),
    sessao: Session = Depends(obter_sessao),
):
    pdf_bytes = await _ler_pdf(arquivo)
    registro = NotaFiscalRegistro(arquivo=arquivo.filename or "nota.pdf", status=StatusNota.PENDENTE.value)
    # A chamada à IA é bloqueante: roda em thread para não travar o servidor
    await run_in_threadpool(_aplicar_processamento, registro, pdf_bytes, abordagem)
    sessao.add(registro)
    sessao.commit()
    sessao.refresh(registro)
    return registro


def _processar_lote(itens: list[tuple[int, bytes]], abordagem: Abordagem) -> None:
    with SessaoLocal() as sessao:
        for nota_id, pdf_bytes in itens:
            registro = sessao.get(NotaFiscalRegistro, nota_id)
            if registro is None:
                continue
            _aplicar_processamento(registro, pdf_bytes, abordagem)
            sessao.commit()


@router.post("/lote", response_model=LoteResposta, summary="Envia várias notas para processamento em segundo plano")
async def enviar_lote(
    background: BackgroundTasks,
    arquivos: list[UploadFile] = File(...),
    abordagem: Abordagem = Query(Abordagem.PDF),
    sessao: Session = Depends(obter_sessao),
):
    lote_id = str(uuid.uuid4())
    pdfs = [(arquivo.filename or "nota.pdf", await _ler_pdf(arquivo)) for arquivo in arquivos]

    registros = [
        NotaFiscalRegistro(arquivo=nome, status=StatusNota.PENDENTE.value, lote_id=lote_id) for nome, _ in pdfs
    ]
    sessao.add_all(registros)
    sessao.commit()

    background.add_task(
        _processar_lote, [(r.id, conteudo) for r, (_, conteudo) in zip(registros, pdfs)], abordagem
    )
    return LoteResposta(lote_id=lote_id, notas=[r.id for r in registros])


@router.get("", response_model=list[NotaFiscalResposta], summary="Lista as notas processadas")
def listar_notas(lote_id: str | None = None, sessao: Session = Depends(obter_sessao)):
    consulta = select(NotaFiscalRegistro).order_by(NotaFiscalRegistro.id.desc())
    if lote_id:
        consulta = consulta.where(NotaFiscalRegistro.lote_id == lote_id)
    return sessao.scalars(consulta).all()


def _buscar(nota_id: int, sessao: Session) -> NotaFiscalRegistro:
    registro = sessao.get(NotaFiscalRegistro, nota_id)
    if registro is None:
        raise HTTPException(404, "Nota não encontrada.")
    return registro


@router.get("/{nota_id}", response_model=NotaFiscalResposta, summary="Detalha uma nota")
def obter_nota(nota_id: int, sessao: Session = Depends(obter_sessao)):
    return _buscar(nota_id, sessao)


@router.put("/{nota_id}", response_model=NotaFiscalResposta, summary="Corrige manualmente os dados de uma nota")
def corrigir_nota(nota_id: int, dados: NotaFiscalExtraida, sessao: Session = Depends(obter_sessao)):
    registro = _buscar(nota_id, sessao)
    registro.dados = dados.model_dump(mode="json")
    registro.validacao = validar_nota(dados).model_dump(mode="json")
    registro.tipo_documento = dados.tipo_documento.value
    registro.status = StatusNota.REVISADA.value
    sessao.commit()
    sessao.refresh(registro)
    return registro
