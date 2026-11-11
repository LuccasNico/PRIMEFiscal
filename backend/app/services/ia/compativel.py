"""Provedor para APIs compatíveis com OpenAI Chat Completions.

Configure URL, chave e modelo em ``API_COMPATIVEL_*``.  O mesmo adaptador atende
OpenAI, Ollama, Groq, OpenRouter, Together, vLLM e outros serviços que expõem
``/v1/chat/completions``. Para APIs com protocolo próprio, é necessário um
adaptador específico.
"""

import json
import time

import httpx
from pydantic import ValidationError

from app.config import configuracoes
from app.schemas.nota_fiscal import Metadados, NotaFiscalExtraida
from app.services.ia.base import INSTRUCAO_USUARIO, PROMPT_SISTEMA, ErroExtracao, mensagem_com_texto
from app.services.ia.lmstudio import SCHEMA_NOTA, _paginas_como_imagens


def _extrair_json(texto: str) -> NotaFiscalExtraida:
    """Aceita JSON puro e a forma mais comum de resposta em bloco Markdown."""
    texto = (texto or "").strip()
    if texto.startswith("```"):
        texto = texto.split("\n", 1)[-1]
        texto = texto.rsplit("```", 1)[0].strip()
    try:
        return NotaFiscalExtraida.model_validate_json(texto)
    except ValidationError as e:
        raise ErroExtracao(f"A API devolveu um JSON fora do formato esperado: {e.error_count()} erro(s).") from e


def _extrair(conteudo: str | list[dict], abordagem: str) -> tuple[NotaFiscalExtraida, Metadados]:
    inicio = time.perf_counter()
    formato = configuracoes.compativel_formato_resposta
    corpo: dict = {
        "model": configuracoes.compativel_modelo,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": PROMPT_SISTEMA},
            {"role": "user", "content": conteudo},
        ],
    }
    if formato == "json_schema":
        corpo["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "nota_fiscal", "strict": True, "schema": SCHEMA_NOTA},
        }
    elif formato == "json_object":
        corpo["response_format"] = {"type": "json_object"}
    else:
        corpo["messages"][0]["content"] += "\nResponda apenas com um JSON válido conforme o schema solicitado."

    cabecalhos = {"Content-Type": "application/json"}
    if configuracoes.compativel_chave:
        cabecalhos["Authorization"] = f"Bearer {configuracoes.compativel_chave}"

    try:
        resposta = httpx.post(
            f"{configuracoes.compativel_url}/chat/completions",
            json=corpo,
            headers=cabecalhos,
            timeout=configuracoes.compativel_timeout,
        )
    except httpx.ConnectError as e:
        raise ErroExtracao(f"Não foi possível conectar a {configuracoes.compativel_nome} em {configuracoes.compativel_url}.") from e
    except httpx.TimeoutException as e:
        raise ErroExtracao(f"{configuracoes.compativel_nome} demorou demais para responder.") from e
    except httpx.HTTPError as e:
        raise ErroExtracao(f"Falha na comunicação com {configuracoes.compativel_nome}: {e}") from e

    if resposta.status_code >= 400:
        detalhe = resposta.text[:500]
        if abordagem == "pdf":
            detalhe += " (a abordagem 'pdf' exige um modelo com visão)"
        raise ErroExtracao(f"Erro em {configuracoes.compativel_nome} ({resposta.status_code}): {detalhe}")

    try:
        retorno = resposta.json()
        escolha = retorno["choices"][0]
        texto = escolha["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise ErroExtracao(f"{configuracoes.compativel_nome} devolveu uma resposta em formato inesperado.") from e
    if escolha.get("finish_reason") == "length":
        raise ErroExtracao("A resposta foi cortada por limite de tokens. Aumente o limite de saída do modelo.")

    dados = _extrair_json(texto)
    uso = retorno.get("usage") or {}
    return dados, Metadados(
        abordagem=abordagem,
        modelo=f"{configuracoes.provedor_ia}/{retorno.get('model', configuracoes.compativel_modelo)}",
        tokens_entrada=uso.get("prompt_tokens"),
        tokens_saida=uso.get("completion_tokens"),
        tempo_ms=int((time.perf_counter() - inicio) * 1000),
    )


def extrair_de_pdf(pdf_bytes: bytes) -> tuple[NotaFiscalExtraida, Metadados]:
    conteudo = [{"type": "text", "text": INSTRUCAO_USUARIO}] + [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{imagem}"}}
        for imagem in _paginas_como_imagens(pdf_bytes)
    ]
    return _extrair(conteudo, abordagem="pdf")


def extrair_de_texto(texto: str) -> tuple[NotaFiscalExtraida, Metadados]:
    return _extrair(mensagem_com_texto(texto), abordagem="texto")
