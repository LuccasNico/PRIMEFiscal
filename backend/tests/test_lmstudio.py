import json

import httpx
import pytest

from app.services.ia import lmstudio
from app.services.ia.base import ErroExtracao
from tests.pdf_teste import pdf_com_texto


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


def test_schema_limita_texto_livre():
    campo = lmstudio.SCHEMA_NOTA["properties"]["informacoes_complementares"]
    opcao_texto = next(o for o in campo["anyOf"] if o.get("type") == "string")
    assert opcao_texto["maxLength"] == 500


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
    lmstudio.extrair_de_pdf(pdf_com_texto("DANFE teste"))

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
