"""Testes do provedor Claude sem chamar a API: o cliente do SDK é trocado por um objeto falso."""

from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from app.schemas.nota_fiscal import NotaFiscalExtraida
from app.services.ia import claude
from app.services.ia.base import ErroExtracao
from tests.conftest import NOTA_EXTRAIDA


def resposta_falsa(stop_reason: str = "end_turn"):
    return SimpleNamespace(
        stop_reason=stop_reason,
        parsed_output=NotaFiscalExtraida(**NOTA_EXTRAIDA),
        model="claude-opus-5-5",
        usage=SimpleNamespace(input_tokens=1200, output_tokens=300),
    )


@pytest.fixture
def api(monkeypatch):
    """Define o que a API falsa devolve (ou lança) e guarda os parâmetros recebidos."""
    recebidos = []

    def configurar(resultado, modelo: str = "claude-opus-5-5"):
        def parse(**parametros):
            recebidos.append(parametros)
            if isinstance(resultado, Exception):
                raise resultado
            return resultado

        cliente = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(parse=parse)))
        monkeypatch.setattr(claude, "_cliente", lambda: cliente)
        monkeypatch.setattr(claude, "configuracoes", SimpleNamespace(modelo_claude=modelo))
        return recebidos

    return configurar


def erro_http(classe, status: int):
    requisicao = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return classe("mensagem da API", response=httpx2.Response(status, request=requisicao), body=None)


def test_extrair_de_texto(api):
    recebidos = api(resposta_falsa())
    dados, metadados = claude.extrair_de_texto("texto da nota")

    assert dados.numero == "123"
    assert (metadados.abordagem, metadados.tokens_entrada, metadados.tokens_saida) == ("texto", 1200, 300)
    assert recebidos[0]["output_format"] is NotaFiscalExtraida


def test_extrair_de_pdf_envia_o_documento(api):
    recebidos = api(resposta_falsa())
    claude.extrair_de_pdf(b"%PDF-1.4 conteudo")

    bloco = recebidos[0]["messages"][0]["content"][0]
    assert bloco["type"] == "document"
    assert bloco["source"]["media_type"] == "application/pdf"


def test_fallback_so_e_enviado_para_modelos_que_aceitam(api):
    recebidos = api(resposta_falsa(), modelo="claude-opus-5-5")
    claude.extrair_de_texto("texto")
    assert recebidos[-1]["model"] == "claude-opus-5-5"
    assert recebidos[-1]["fallbacks"] == "default"

    api(resposta_falsa(), modelo="claude-haiku-5-5")
    claude.extrair_de_texto("texto")
    assert recebidos[-1]["model"] == "claude-haiku-5-5"
    assert "fallbacks" not in recebidos[-1]
    assert "betas" not in recebidos[-1]


@pytest.mark.parametrize(
    "erro, trecho",
    [
        (erro_http(anthropic.AuthenticationError, 401), "Chave da Claude API inválida"),
        (erro_http(anthropic.NotFoundError, 404), "não encontrado"),
        (erro_http(anthropic.RateLimitError, 429), "Limite de requisições"),
        (erro_http(anthropic.InternalServerError, 500), "Erro na Claude API (500)"),
        (anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com")), "Falha de conexão"),
        (TypeError("Could not resolve authentication method"), "Credenciais da Claude API não encontradas"),
    ],
)
def test_falhas_da_api_viram_mensagens_claras(api, erro, trecho):
    api(erro)
    with pytest.raises(ErroExtracao, match=trecho.replace("(", r"\(").replace(")", r"\)")):
        claude.extrair_de_texto("texto")


def test_outro_type_error_nao_e_mascarado(api):
    api(TypeError("argumento inesperado"))
    with pytest.raises(TypeError):
        claude.extrair_de_texto("texto")


@pytest.mark.parametrize("stop_reason, trecho", [("refusal", "recusou"), ("max_tokens", "limite de tokens")])
def test_resposta_incompleta(api, stop_reason, trecho):
    api(resposta_falsa(stop_reason))
    with pytest.raises(ErroExtracao, match=trecho):
        claude.extrair_de_texto("texto")
