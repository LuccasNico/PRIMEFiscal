"""Pipeline completo: PDF -> extração com IA -> validação fiscal."""

from enum import Enum

from app.schemas.nota_fiscal import Metadados, NotaFiscalExtraida, ResultadoValidacao
from app.services import extrator_texto, ia
from app.services.validacao import validar_nota

# Abaixo disso o PDF é tratado como escaneado (sem texto embutido)
MINIMO_CARACTERES_DE_TEXTO = 50


class Abordagem(str, Enum):
    PDF = "pdf"
    TEXTO = "texto"


def _texto_do_pdf(pdf_bytes: bytes) -> str:
    try:
        texto = extrator_texto.extrair_texto_estruturado(pdf_bytes)
    except Exception as e:
        # O pdfplumber/pdfminer lança exceções de vários tipos para arquivos corrompidos ou com senha
        raise ia.ErroExtracao("Não foi possível ler o PDF (arquivo corrompido ou protegido por senha).") from e
    if len(texto) < MINIMO_CARACTERES_DE_TEXTO:
        raise ia.ErroExtracao("O PDF não tem texto embutido (provavelmente escaneado). Use a abordagem 'pdf'.")
    return texto


def processar_pdf(
    pdf_bytes: bytes, abordagem: Abordagem = Abordagem.PDF, modelo: str | None = None
) -> tuple[NotaFiscalExtraida, ResultadoValidacao, Metadados]:
    """`modelo` vazio usa o modelo padrão do provedor."""
    if abordagem == Abordagem.TEXTO:
        dados, metadados = ia.extrair_de_texto(_texto_do_pdf(pdf_bytes), modelo)
    else:
        dados, metadados = ia.extrair_de_pdf(pdf_bytes, modelo)

    return dados, validar_nota(dados), metadados
