"""Testes dos provedores Gemini, LM Studio e APIs compatíveis com OpenAI, sem chamadas externas."""

import base64
import json
from types import SimpleNamespace

import httpx
import pytest

from app.services.ia import base, compativel, gemini, lmstudio
from app.services.ia.base import ErroExtracao
from tests.conftest import NOTA_EXTRAIDA
from tests.pdf_teste import pdf_com_texto

# ---------- Partes comuns ----------


def test_schema_sem_referencias_e_com_limite_de_texto_livre():
    assert "$ref" not in json.dumps(base.SCHEMA_NOTA)
    assert "razao_social" in json.dumps(base.SCHEMA_NOTA["properties"]["emitente"])
    campo = base.SCHEMA_NOTA["properties"]["informacoes_complementares"]
    assert next(o for o in campo["anyOf"] if o.get("type") == "string")["maxLength"] == 500


def test_resposta_em_bloco_markdown_e_aceita():
    nota = base.interpretar_resposta(f"```json\n{json.dumps(NOTA_EXTRAIDA)}\n```", "Teste")
    assert nota.numero == "123"


def test_resposta_fora_do_formato():
    with pytest.raises(ErroExtracao, match="Teste devolveu dados fora do formato esperado"):
        base.interpretar_resposta('{"numero": "123"}', "Teste")


def test_pdf_corrompido_nao_vira_imagem():
    with pytest.raises(ErroExtracao, match="Não foi possível ler o PDF"):
        base.paginas_como_imagens(b"%PDF-1.4 isto nao e um pdf de verdade")


# ---------- APIs compatíveis com OpenAI ----------


def resposta_chat(conteudo: str, finish_reason: str = "stop") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": "modelo-da-api",
            "choices": [{"message": {"content": conteudo}, "finish_reason": finish_reason}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        },
    )


@pytest.fixture
def config_compativel(monkeypatch):
    def configurar(**valores):
        padrao = dict(
            compativel_nome="Groq",
            compativel_url="https://api.groq.com/openai/v1",
            compativel_chave="chave-secreta",
            compativel_modelo="llama-teste",
            compativel_timeout=30,
            compativel_formato_resposta="json_schema",
        )
        monkeypatch.setattr(compativel, "configuracoes", SimpleNamespace(**{**padrao, **valores}))

    configurar()
    return configurar


def test_compativel_extrai_com_schema(api_falsa, config_compativel):
    recebidas = api_falsa(resposta_chat(json.dumps(NOTA_EXTRAIDA)))
    dados, metadados = compativel.extrair_de_texto("texto da nota")

    metodo, url, parametros = recebidas[0]
    assert (metodo, url) == ("POST", "https://api.groq.com/openai/v1/chat/completions")
    assert parametros["headers"]["Authorization"] == "Bearer chave-secreta"
    assert parametros["json"]["response_format"]["type"] == "json_schema"
    assert dados.numero == "123"
    assert (metadados.provedor, metadados.modelo, metadados.tokens_entrada) == ("Groq", "modelo-da-api", 100)


def test_compativel_sem_schema_pede_o_formato_no_prompt(api_falsa, config_compativel):
    config_compativel(compativel_formato_resposta="prompt", compativel_chave="")
    recebidas = api_falsa(resposta_chat(f"```json\n{json.dumps(NOTA_EXTRAIDA)}\n```"))
    compativel.extrair_de_texto("texto")

    parametros = recebidas[0][2]
    assert "response_format" not in parametros["json"]
    assert "Authorization" not in parametros["headers"]
    assert "JSON Schema" in parametros["json"]["messages"][0]["content"]


def test_compativel_json_object(api_falsa, config_compativel):
    config_compativel(compativel_formato_resposta="json_object")
    recebidas = api_falsa(resposta_chat(json.dumps(NOTA_EXTRAIDA)))
    compativel.extrair_de_texto("texto")
    assert recebidas[0][2]["json"]["response_format"] == {"type": "json_object"}


def test_compativel_envia_paginas_como_imagem(api_falsa, config_compativel):
    recebidas = api_falsa(resposta_chat(json.dumps(NOTA_EXTRAIDA)))
    compativel.extrair_de_pdf(pdf_com_texto("DANFE teste"))

    partes = recebidas[0][2]["json"]["messages"][1]["content"]
    imagens = [parte for parte in partes if parte["type"] == "image_url"]
    assert len(imagens) == 1
    assert imagens[0]["image_url"]["url"].startswith("data:image/png;base64,")


@pytest.mark.parametrize(
    "resposta, trecho",
    [
        (httpx.Response(401, json={"error": {"message": "Invalid API key"}}), "Groq respondeu com erro 401: Invalid API key"),
        (httpx.Response(200, json={"error": "modelo descarregado"}), "formato inesperado"),
        (httpx.Response(200, text="isto nao e json"), "formato inesperado"),
        (resposta_chat('{"tipo', finish_reason="length"), "cortada pelo limite de tokens"),
        (httpx.ConnectError("recusado"), "Não foi possível conectar ao serviço Groq"),
        (httpx.ReadTimeout("demorou"), "Groq não respondeu em 30 segundos"),
    ],
)
def test_compativel_falhas_viram_mensagens_claras(api_falsa, config_compativel, resposta, trecho):
    api_falsa(resposta)
    with pytest.raises(ErroExtracao, match=trecho):
        compativel.extrair_de_texto("texto")


def test_compativel_dica_de_visao_na_abordagem_pdf(api_falsa, config_compativel):
    api_falsa(httpx.Response(400, text="model does not support images"))
    with pytest.raises(ErroExtracao, match="exige um modelo com visão"):
        compativel.extrair_de_pdf(pdf_com_texto("DANFE"))


# ---------- LM Studio ----------


@pytest.fixture
def config_lmstudio(monkeypatch):
    def configurar(modelo=""):
        monkeypatch.setattr(
            lmstudio,
            "configuracoes",
            SimpleNamespace(lmstudio_url="http://lm/v1", lmstudio_modelo=modelo, lmstudio_timeout=60),
        )

    configurar()
    return configurar


def test_lmstudio_usa_o_primeiro_modelo_que_nao_e_de_embedding(api_falsa, config_lmstudio):
    modelos = httpx.Response(200, json={"data": [{"id": "text-embedding-nomic"}, {"id": "qwen3-4b"}]})
    recebidas = api_falsa(modelos, resposta_chat(json.dumps(NOTA_EXTRAIDA)))
    _, metadados = lmstudio.extrair_de_texto("texto")

    assert recebidas[1][2]["json"]["model"] == "qwen3-4b"
    assert "Authorization" not in recebidas[1][2]["headers"]
    assert metadados.provedor == "LM Studio"


def test_lmstudio_modelo_do_env_tem_prioridade(api_falsa, config_lmstudio):
    config_lmstudio(modelo="gemma-3-4b")
    recebidas = api_falsa(resposta_chat(json.dumps(NOTA_EXTRAIDA)))
    lmstudio.extrair_de_texto("texto")
    assert len(recebidas) == 1
    assert recebidas[0][2]["json"]["model"] == "gemma-3-4b"


def test_lmstudio_sem_modelos(api_falsa, config_lmstudio):
    api_falsa(httpx.Response(200, json={"data": []}))
    with pytest.raises(ErroExtracao, match="Nenhum modelo disponível no LM Studio"):
        lmstudio.extrair_de_texto("texto")


def test_lmstudio_desligado(api_falsa, config_lmstudio):
    api_falsa(httpx.ConnectError("recusado"))
    with pytest.raises(ErroExtracao, match="servidor local do LM Studio está ligado"):
        lmstudio.extrair_de_texto("texto")


def test_lmstudio_resposta_cortada_sugere_aumentar_o_contexto(api_falsa, config_lmstudio):
    config_lmstudio(modelo="qwen3-4b")
    api_falsa(resposta_chat('{"tipo', finish_reason="length"))
    with pytest.raises(ErroExtracao, match="Context Length"):
        lmstudio.extrair_de_texto("texto")


# ---------- Gemini ----------


def resposta_gemini(conteudo: str, finish_reason: str = "STOP") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "candidates": [{"content": {"parts": [{"text": conteudo}]}, "finishReason": finish_reason}],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 20},
            "modelVersion": "gemini-teste-001",
        },
    )


@pytest.fixture
def config_gemini(monkeypatch):
    def configurar(chave="chave-gemini"):
        monkeypatch.setattr(
            gemini, "configuracoes", SimpleNamespace(gemini_chave=chave, gemini_modelo="gemini-teste", gemini_timeout=30)
        )

    configurar()
    return configurar


def test_gemini_extrai_com_schema(api_falsa, config_gemini):
    recebidas = api_falsa(resposta_gemini(json.dumps(NOTA_EXTRAIDA)))
    dados, metadados = gemini.extrair_de_texto("texto da nota")

    _, url, parametros = recebidas[0]
    assert url.endswith("/models/gemini-teste:generateContent")
    assert parametros["headers"]["x-goog-api-key"] == "chave-gemini"
    assert parametros["json"]["generationConfig"]["responseJsonSchema"] == base.SCHEMA_NOTA
    assert dados.numero == "123"
    assert (metadados.provedor, metadados.modelo, metadados.tokens_saida) == ("Google Gemini", "gemini-teste-001", 20)


def test_gemini_recebe_o_pdf_direto(api_falsa, config_gemini):
    recebidas = api_falsa(resposta_gemini(json.dumps(NOTA_EXTRAIDA)))
    pdf = pdf_com_texto("DANFE")
    gemini.extrair_de_pdf(pdf)

    documento = recebidas[0][2]["json"]["contents"][0]["parts"][0]["inlineData"]
    assert documento["mimeType"] == "application/pdf"
    assert base64.b64decode(documento["data"]) == pdf


def test_gemini_exige_chave(config_gemini):
    config_gemini(chave="")
    with pytest.raises(ErroExtracao, match="GEMINI_API_KEY"):
        gemini.extrair_de_texto("texto")


@pytest.mark.parametrize(
    "resposta, trecho",
    [
        (resposta_gemini('{"tipo', finish_reason="MAX_TOKENS"), "limite de tokens"),
        (httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}}), "recusou processar"),
        (httpx.Response(400, json={"error": {"message": "API key not valid"}}), "erro 400: API key not valid"),
        (httpx.Response(429, json={"error": {"message": "Quota exceeded"}}), "limite de uso foi atingido"),
        (httpx.Response(503, json={"error": {"message": "high demand"}}), "erro 503: high demand O serviço está instável"),
    ],
)
def test_gemini_falhas_viram_mensagens_claras(api_falsa, config_gemini, resposta, trecho):
    api_falsa(resposta)
    with pytest.raises(ErroExtracao, match=trecho):
        gemini.extrair_de_texto("texto")
