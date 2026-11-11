"""Testes do provedor Gemini sem fazer chamadas externas."""

import json
from types import SimpleNamespace

import httpx

from app.services.ia import gemini
from app.services.ia.base import ErroExtracao
from tests.conftest import NOTA_EXTRAIDA


def _resposta(conteudo):
    return httpx.Response(
        200,
        json={
            "candidates": [{"content": {"parts": [{"text": conteudo}]}}],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 20},
        },
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com"),
    )


def test_envia_schema_e_interpreta_resposta(monkeypatch):
    recebido = {}
    monkeypatch.setattr(
        gemini,
        "configuracoes",
        SimpleNamespace(gemini_chave="chave", gemini_modelo="gemini-teste", gemini_timeout=3),
    )

    def post(url, **kwargs):
        recebido["url"] = url
        recebido.update(kwargs)
        return _resposta(json.dumps(NOTA_EXTRAIDA))

    monkeypatch.setattr(gemini.httpx, "post", post)
    dados, metadados = gemini.extrair_de_texto("texto da nota")

    assert dados.numero == "123"
    assert metadados.modelo == "gemini/gemini-teste"
    assert recebido["headers"]["x-goog-api-key"] == "chave"
    assert recebido["json"]["generationConfig"]["responseMimeType"] == "application/json"
    assert "responseJsonSchema" in recebido["json"]["generationConfig"]


def test_exige_chave(monkeypatch):
    monkeypatch.setattr(gemini, "configuracoes", SimpleNamespace(gemini_chave=""))
    try:
        gemini.extrair_de_texto("texto")
    except ErroExtracao as erro:
        assert "GEMINI_API_KEY" in str(erro)
    else:
        raise AssertionError("Era esperado ErroExtracao")
