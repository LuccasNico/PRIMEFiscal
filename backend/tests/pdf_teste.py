"""Geração de PDFs mínimos para os testes (sem depender de notas reais)."""


def gerar_pdf(conteudo: str) -> bytes:
    """PDF de uma página A4 com o fluxo de conteúdo informado (operadores PDF)."""
    stream = conteudo.encode()
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = b"%PDF-1.4\n"
    posicoes = []
    for i, objeto in enumerate(objetos, start=1):
        posicoes.append(len(pdf))
        pdf += f"{i} 0 obj\n".encode() + objeto + b"\nendobj\n"
    inicio_xref = len(pdf)
    pdf += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    pdf += b"".join(f"{p:010d} 00000 n \n".encode() for p in posicoes)
    pdf += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{inicio_xref}\n%%EOF".encode()
    return pdf


def texto(x: float, y: float, conteudo: str, tamanho: int = 10) -> str:
    return f"BT /F1 {tamanho} Tf {x} {y} Td ({conteudo}) Tj ET\n"


def pdf_com_texto(conteudo: str) -> bytes:
    return gerar_pdf(texto(72, 720, conteudo))
