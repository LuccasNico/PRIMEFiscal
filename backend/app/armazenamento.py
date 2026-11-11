"""Armazenamento dos PDFs enviados.

O PDF fica guardado enquanto a nota existir: é ele que permite processar a fila depois
de um reinício do servidor, reprocessar uma nota e conferir os dados extraídos com o original.
"""

from pathlib import Path

from app.config import configuracoes


def caminho_pdf(nota_id: int) -> Path:
    return configuracoes.pasta_uploads / f"{nota_id}.pdf"


def salvar_pdf(nota_id: int, conteudo: bytes) -> None:
    configuracoes.pasta_uploads.mkdir(parents=True, exist_ok=True)
    caminho_pdf(nota_id).write_bytes(conteudo)


def ler_pdf(nota_id: int) -> bytes:
    return caminho_pdf(nota_id).read_bytes()


def tem_pdf(nota_id: int) -> bool:
    return caminho_pdf(nota_id).is_file()


def remover_pdf(nota_id: int) -> None:
    caminho_pdf(nota_id).unlink(missing_ok=True)
