"""Provedor nativo da Google Gemini API, sem depender da camada OpenAI-compatível."""

import time

import httpx
from pydantic import ValidationError

from app.config import configuracoes
from app.schemas.nota_fiscal import Metadados, NotaFiscalExtraida
from app.services.ia.base import INSTRUCAO_USUARIO, PROMPT_SISTEMA, ErroExtracao, mensagem_com_texto
from app.services.ia.lmstudio import SCHEMA_NOTA, _paginas_como_imagens

URL_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _resposta_json(resposta: httpx.Response) -> tuple[NotaFiscalExtraida, dict]:
    try:
        corpo = resposta.json()
        partes = corpo["candidates"][0]["content"]["parts"]
        texto = "".join(parte.get("text", "") for parte in partes)
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise ErroExtracao("A Gemini API devolveu uma resposta em formato inesperado.") from e
    try:
        return NotaFiscalExtraida.model_validate_json(texto), corpo
    except ValidationError as e:
        raise ErroExtracao(f"A Gemini API devolveu um JSON fora do formato esperado: {e.error_count()} erro(s).") from e


def _extrair(partes: list[dict], abordagem: str) -> tuple[NotaFiscalExtraida, Metadados]:
    if not configuracoes.gemini_chave:
        raise ErroExtracao("Chave da Gemini API não encontrada. Defina GEMINI_API_KEY em backend/.env.")
    inicio = time.perf_counter()
    requisicao = {
        "systemInstruction": {"parts": [{"text": PROMPT_SISTEMA}]},
        "contents": [{"role": "user", "parts": partes}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseJsonSchema": SCHEMA_NOTA,
        },
    }
    try:
        resposta = httpx.post(
            f"{URL_BASE}/{configuracoes.gemini_modelo}:generateContent",
            json=requisicao,
            headers={"x-goog-api-key": configuracoes.gemini_chave},
            timeout=configuracoes.gemini_timeout,
        )
    except httpx.ConnectError as e:
        raise ErroExtracao("Não foi possível conectar à Gemini API. Verifique a internet.") from e
    except httpx.TimeoutException as e:
        raise ErroExtracao("A Gemini API demorou demais para responder.") from e
    except httpx.HTTPError as e:
        raise ErroExtracao(f"Falha na comunicação com a Gemini API: {e}") from e
    if resposta.status_code >= 400:
        detalhe = resposta.text[:500]
        if abordagem == "pdf":
            detalhe += " (a abordagem 'pdf' exige um modelo Gemini com visão)"
        raise ErroExtracao(f"Erro na Gemini API ({resposta.status_code}): {detalhe}")

    dados, corpo = _resposta_json(resposta)
    uso = corpo.get("usageMetadata") or {}
    return dados, Metadados(
        abordagem=abordagem,
        modelo=f"gemini/{configuracoes.gemini_modelo}",
        tokens_entrada=uso.get("promptTokenCount"),
        tokens_saida=uso.get("candidatesTokenCount"),
        tempo_ms=int((time.perf_counter() - inicio) * 1000),
    )


def extrair_de_texto(texto: str) -> tuple[NotaFiscalExtraida, Metadados]:
    return _extrair([{"text": mensagem_com_texto(texto)}], abordagem="texto")


def extrair_de_pdf(pdf_bytes: bytes) -> tuple[NotaFiscalExtraida, Metadados]:
    partes = [{"text": INSTRUCAO_USUARIO}] + [
        {"inlineData": {"mimeType": "image/png", "data": imagem}} for imagem in _paginas_como_imagens(pdf_bytes)
    ]
    return _extrair(partes, abordagem="pdf")
