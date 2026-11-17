import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import armazenamento
from app.config import configuracoes
from app.db import NotaFiscalRegistro, agora, obter_sessao
from app.schemas.nota_fiscal import (
    STATUS_NA_FILA,
    NotaFiscalExtraida,
    NotaFiscalResposta,
    RemocaoResposta,
    StatusNota,
)
from app.services import banco_notas
from app.services.fila import fila
from app.services.processamento import Abordagem
from app.services.validacao import validar_nota

router = APIRouter(prefix="/api/notas", tags=["notas"])

MAXIMO_DE_ARQUIVOS_POR_ENVIO = 50


async def _ler_pdf(arquivo: UploadFile) -> bytes:
    # Quando o tamanho já é conhecido, recusa antes de carregar o arquivo na memória
    if arquivo.size is not None and arquivo.size > configuracoes.tamanho_maximo_bytes:
        raise HTTPException(413, f"'{arquivo.filename}' excede o tamanho máximo permitido.")
    conteudo = await arquivo.read()
    if not conteudo.startswith(b"%PDF"):
        raise HTTPException(415, f"'{arquivo.filename}' não é um PDF.")
    if len(conteudo) > configuracoes.tamanho_maximo_bytes:
        raise HTTPException(413, f"'{arquivo.filename}' excede o tamanho máximo permitido.")
    return conteudo


def _buscar(nota_id: int, sessao: Session) -> NotaFiscalRegistro:
    registro = sessao.get(NotaFiscalRegistro, nota_id)
    if registro is None:
        raise HTTPException(404, "Nota não encontrada.")
    return registro


@router.post(
    "",
    response_model=list[NotaFiscalResposta],
    status_code=202,
    summary="Envia uma ou mais notas fiscais para a fila de processamento",
)
async def enviar_notas(
    arquivos: list[UploadFile] = File(..., description="Um ou mais arquivos PDF"),
    abordagem: Abordagem = Query(Abordagem.PDF),
    sessao: Session = Depends(obter_sessao),
):
    """As notas entram na fila com status `pendente` e são processadas uma por vez.
    Acompanhe o andamento consultando cada nota ou filtrando a lista pelo `lote_id` retornado."""
    if len(arquivos) > MAXIMO_DE_ARQUIVOS_POR_ENVIO:
        raise HTTPException(413, f"Envie no máximo {MAXIMO_DE_ARQUIVOS_POR_ENVIO} arquivos por vez.")

    # Todos os arquivos são validados antes de qualquer gravação: ou entram todos, ou nenhum
    pdfs = [((arquivo.filename or "nota.pdf")[:255], await _ler_pdf(arquivo)) for arquivo in arquivos]

    lote_id = str(uuid.uuid4())
    registros = [
        NotaFiscalRegistro(
            arquivo=nome,
            status=StatusNota.PENDENTE.value,
            lote_id=lote_id,
            abordagem=abordagem.value,
            enfileirado_em=agora(),
        )
        for nome, _ in pdfs
    ]
    sessao.add_all(registros)
    sessao.flush()  # gera os ids, que dão nome aos PDFs guardados
    try:
        for registro, (_, conteudo) in zip(registros, pdfs):
            armazenamento.salvar_pdf(registro.id, conteudo)
        sessao.commit()
    except Exception:
        sessao.rollback()
        for registro in registros:
            armazenamento.remover_pdf(registro.id)
        raise

    fila.avisar()
    return registros


@router.get("", response_model=list[NotaFiscalResposta], summary="Lista as notas, das mais recentes para as mais antigas")
def listar_notas(
    lote_id: str | None = None,
    status: StatusNota | None = None,
    sessao: Session = Depends(obter_sessao),
):
    consulta = select(NotaFiscalRegistro).order_by(NotaFiscalRegistro.id.desc())
    if lote_id:
        consulta = consulta.where(NotaFiscalRegistro.lote_id == lote_id)
    if status:
        consulta = consulta.where(NotaFiscalRegistro.status == status.value)
    return sessao.scalars(consulta).all()


@router.delete("", response_model=RemocaoResposta, summary="Remove todas as notas com o status informado")
def remover_notas(status: StatusNota, sessao: Session = Depends(obter_sessao)):
    """Com `status=pendente`, esvazia a fila de espera."""
    if status == StatusNota.PROCESSANDO:
        raise HTTPException(409, "A nota em processamento não pode ser removida. Aguarde a conclusão.")
    registros = sessao.scalars(select(NotaFiscalRegistro).where(NotaFiscalRegistro.status == status.value)).all()
    ids = [registro.id for registro in registros]
    for registro in registros:
        sessao.delete(registro)
    sessao.commit()
    for nota_id in ids:
        armazenamento.remover_pdf(nota_id)
    return RemocaoResposta(removidas=len(ids))


@router.get("/{nota_id}", response_model=NotaFiscalResposta, summary="Detalha uma nota")
def obter_nota(nota_id: int, sessao: Session = Depends(obter_sessao)):
    return _buscar(nota_id, sessao)


@router.get("/{nota_id}/pdf", response_class=FileResponse, summary="Devolve o PDF original da nota")
def obter_pdf(nota_id: int, sessao: Session = Depends(obter_sessao)):
    registro = _buscar(nota_id, sessao)
    if not registro.tem_pdf:
        raise HTTPException(404, "O PDF original desta nota não está disponível.")
    return FileResponse(
        armazenamento.caminho_pdf(nota_id),
        media_type="application/pdf",
        filename=registro.arquivo,
        content_disposition_type="inline",
    )


@router.put("/{nota_id}", response_model=NotaFiscalResposta, summary="Corrige manualmente os dados de uma nota")
def corrigir_nota(nota_id: int, dados: NotaFiscalExtraida, sessao: Session = Depends(obter_sessao)):
    registro = _buscar(nota_id, sessao)
    if registro.status in STATUS_NA_FILA:
        raise HTTPException(409, "A nota ainda está na fila de processamento.")
    registro.dados = dados.model_dump(mode="json")
    registro.validacao = validar_nota(dados).model_dump(mode="json")
    registro.tipo_documento = dados.tipo_documento.value
    registro.status = StatusNota.REVISADA.value
    registro.erro = None
    sessao.commit()
    sessao.refresh(registro)
    return registro


@router.post(
    "/{nota_id}/reprocessar",
    response_model=NotaFiscalResposta,
    status_code=202,
    summary="Devolve a nota para a fila, para uma nova extração",
)
def reprocessar_nota(
    nota_id: int,
    abordagem: Abordagem | None = Query(None, description="Se omitida, repete a abordagem anterior"),
    sessao: Session = Depends(obter_sessao),
):
    registro = _buscar(nota_id, sessao)
    if registro.status in STATUS_NA_FILA:
        raise HTTPException(409, "A nota já está na fila de processamento.")
    if not registro.tem_pdf:
        raise HTTPException(409, "O PDF original desta nota não está disponível. Envie o arquivo novamente.")
    if abordagem is not None:
        registro.abordagem = abordagem.value
    registro.status = StatusNota.PENDENTE.value
    registro.enfileirado_em = agora()
    registro.iniciado_em = None
    registro.erro = None
    sessao.commit()
    sessao.refresh(registro)
    fila.avisar()
    return registro


@router.post(
    "/{nota_id}/salvar",
    response_model=NotaFiscalResposta,
    summary="Salva a nota no banco de notas (ou atualiza a cópia já salva)",
)
def salvar_no_banco(nota_id: int, sessao: Session = Depends(obter_sessao)):
    """Grava o JSON extraído e os mesmos dados em tabelas relacionais (participantes, itens, pagamentos).
    A nota salva fica disponível em `/api/banco/notas` mesmo que depois seja excluída daqui."""
    registro = _buscar(nota_id, sessao)
    try:
        banco_notas.salvar(sessao, registro)
        sessao.commit()
    except banco_notas.ErroAoSalvar as e:
        sessao.rollback()
        raise HTTPException(e.status_http, str(e)) from e
    except IntegrityError as e:
        sessao.rollback()
        raise HTTPException(409, "A nota conflita com dados já gravados no banco (CNPJ, CPF ou chave repetidos).") from e
    sessao.refresh(registro)
    return registro


@router.delete(
    "/{nota_id}",
    status_code=204,
    summary="Remove a nota (ou a retira da fila) e apaga o PDF guardado; a cópia no banco de notas é mantida",
)
def remover_nota(nota_id: int, sessao: Session = Depends(obter_sessao)):
    registro = _buscar(nota_id, sessao)
    if registro.status == StatusNota.PROCESSANDO.value:
        raise HTTPException(409, "A nota está em processamento. Aguarde a conclusão para removê-la.")
    sessao.delete(registro)
    sessao.commit()
    armazenamento.remover_pdf(nota_id)
