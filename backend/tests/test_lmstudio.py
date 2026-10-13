import json

import httpx
import pytest

from app.services.ia import lmstudio
from app.services.ia.base import ErroExtracao


def gerar_pdf(texto: str) -> bytes:
    """PDF mínimo de uma página com uma linha de texto, para os testes."""
    stream = f"BT /F1 12 Tf 72 720 Td ({texto}) Tj ET".encode()
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


NOTA_JSON = {
    "tipo_documento": "NF-e",
    "numero": "123",
    "emitente": {"razao_social": "Empresa Exemplo LTDA", "cnpj": "11222333000181"},
    "itens": [{"descricao": "Produto A", "quantidade": 2, "valor_unitario": 10.5, "valor_total": 21.0}],
    "valor_total_nota": 21.0,
}


def resposta_lmstudio(conteudo: str, finish_reason: str = "stop") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": "modelo-teste",
            "choices": [{"message": {"content": conteudo}, "finish_reason": finish_reason}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        },
    )


@pytest.fixture
def requisicoes(monkeypatch):
    """Substitui as chamadas HTTP e guarda o corpo enviado ao LM Studio."""
    enviadas = []
    monkeypatch.setattr(lmstudio, "_modelo", lambda: "modelo-teste")

    def configurar(resposta: httpx.Response):
        def post_falso(url, json, timeout):
            enviadas.append(json)
            return resposta

        monkeypatch.setattr(lmstudio.httpx, "post", post_falso)
        return enviadas

    return configurar


def test_schema_sem_referencias():
    assert "$ref" not in json.dumps(lmstudio.SCHEMA_NOTA)
    assert "$defs" not in lmstudio.SCHEMA_NOTA
    assert "razao_social" in json.dumps(lmstudio.SCHEMA_NOTA["properties"]["emitente"])


def test_extrair_de_texto(requisicoes):
    enviadas = requisicoes(resposta_lmstudio(json.dumps(NOTA_JSON)))
    dados, metadados = lmstudio.extrair_de_texto("texto da nota")

    assert dados.numero == "123"
    assert dados.itens[0].valor_total == 21.0
    assert metadados.modelo == "lmstudio/modelo-teste"
    assert metadados.tokens_entrada == 100
    assert enviadas[0]["response_format"]["type"] == "json_schema"


def test_extrair_de_pdf_envia_paginas_como_imagem(requisicoes):
    enviadas = requisicoes(resposta_lmstudio(json.dumps(NOTA_JSON)))
    lmstudio.extrair_de_pdf(gerar_pdf("DANFE teste"))

    partes = enviadas[0]["messages"][1]["content"]
    imagens = [p for p in partes if p["type"] == "image_url"]
    assert len(imagens) == 1
    assert imagens[0]["image_url"]["url"].startswith("data:image/png;base64,")


def test_json_fora_do_formato(requisicoes):
    requisicoes(resposta_lmstudio('{"numero": "123"}'))
    with pytest.raises(ErroExtracao, match="fora do formato"):
        lmstudio.extrair_de_texto("texto")


def test_resposta_cortada(requisicoes):
    requisicoes(resposta_lmstudio('{"tipo', finish_reason="length"))
    with pytest.raises(ErroExtracao, match="cortada"):
        lmstudio.extrair_de_texto("texto")


def test_lmstudio_desligado(monkeypatch):
    monkeypatch.setattr(lmstudio, "_modelo", lambda: "modelo-teste")

    def post_falso(*args, **kwargs):
        raise httpx.ConnectError("recusado")

    monkeypatch.setattr(lmstudio.httpx, "post", post_falso)
    with pytest.raises(ErroExtracao, match="Não foi possível conectar"):
        lmstudio.extrair_de_texto("texto")
