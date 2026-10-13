"""Extração do texto embutido no PDF (abordagem "texto" e baseline)."""

import io

import pdfplumber


def extrair_texto(pdf_bytes: bytes) -> str:
    """Retorna o texto de todas as páginas, preservando aproximadamente o layout."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        paginas = [pagina.extract_text(layout=True) or "" for pagina in pdf.pages]
    return "\n\n".join(paginas).strip()


def tem_camada_de_texto(pdf_bytes: bytes, minimo_caracteres: int = 50) -> bool:
    """PDFs escaneados não têm texto embutido; nesse caso só a abordagem "pdf" funciona."""
    return len(extrair_texto(pdf_bytes)) >= minimo_caracteres
