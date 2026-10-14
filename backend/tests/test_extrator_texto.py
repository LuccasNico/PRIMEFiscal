from app.services.extrator_texto import extrair_texto, extrair_texto_estruturado
from tests.pdf_teste import gerar_pdf, pdf_com_texto, texto


def pdf_com_quadros() -> bytes:
    """Imita o quadro "Cálculo do imposto" do DANFE: rótulo pequeno em cima, valor embaixo."""
    conteudo = "0.5 w 50 700 300 40 re S 200 700 m 200 740 l S\n"  # duas células lado a lado
    conteudo += texto(55, 728, "VALOR DO ICMS", 6) + texto(55, 710, "10,80")
    conteudo += texto(205, 728, "VALOR TOTAL DA NOTA", 6) + texto(205, 710, "90,00")
    return gerar_pdf(conteudo)


def test_quadros_saem_como_rotulo_e_valor():
    estruturado = extrair_texto_estruturado(pdf_com_quadros())
    assert "VALOR DO ICMS / 10,80 || VALOR TOTAL DA NOTA / 90,00" in estruturado


def test_texto_corrido_separa_rotulos_dos_valores():
    # Motivo da extração estruturada: no texto corrido os valores ficam numa linha separada
    corrido = extrair_texto(pdf_com_quadros())
    assert "VALOR DO ICMS / 10,80" not in corrido


def test_pagina_sem_quadros_usa_texto_corrido():
    estruturado = extrair_texto_estruturado(pdf_com_texto("CUPOM NFC-e"))
    assert "CUPOM NFC-e" in estruturado
    assert "Quadros do documento" not in estruturado
