"""Pipeline completo: PDF -> extração com IA -> validação fiscal."""

from enum import Enum

from app.schemas.nota_fiscal import Metadados, NotaFiscalExtraida, ResultadoValidacao
from app.services import extrator_texto, ia
from app.services.validacao import validar_nota


class Abordagem(str, Enum):
    PDF = "pdf"
    TEXTO = "texto"


def processar_pdf(
    pdf_bytes: bytes, abordagem: Abordagem = Abordagem.PDF
) -> tuple[NotaFiscalExtraida, ResultadoValidacao, Metadados]:
    if abordagem == Abordagem.TEXTO:
        texto = extrator_texto.extrair_texto(pdf_bytes)
        if len(texto) < 50:
            raise ia.ErroExtracao(
                "O PDF não tem texto embutido (provavelmente escaneado). Use a abordagem 'pdf'."
            )
        dados, metadados = ia.extrair_de_texto(texto)
    else:
        dados, metadados = ia.extrair_de_pdf(pdf_bytes)

    return dados, validar_nota(dados), metadados
