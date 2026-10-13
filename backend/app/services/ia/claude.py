"""Provedor Claude API (Anthropic).

O PDF pode ser enviado direto: o Claude lê texto e imagem da página, inclusive
de notas escaneadas. A resposta é restrita ao schema NotaFiscalExtraida
(structured outputs), então o retorno é sempre um JSON válido nesse formato.
"""

import base64
import time
from functools import lru_cache

import anthropic

from app.config import configuracoes
from app.schemas.nota_fiscal import Metadados, NotaFiscalExtraida
from app.services.ia.base import INSTRUCAO_USUARIO, PROMPT_SISTEMA, ErroExtracao, mensagem_com_texto


@lru_cache
def _cliente() -> anthropic.Anthropic:
    # Lê ANTHROPIC_API_KEY do ambiente (.env)
    return anthropic.Anthropic()


def _extrair(conteudo: list[dict], abordagem: str) -> tuple[NotaFiscalExtraida, Metadados]:
    inicio = time.perf_counter()
    resposta = _cliente().beta.messages.parse(
        model=configuracoes.modelo_claude,
        max_tokens=16000,
        # Se o modelo recusar por política de segurança, a API reexecuta em um modelo alternativo
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=PROMPT_SISTEMA,
        messages=[{"role": "user", "content": conteudo}],
        output_format=NotaFiscalExtraida,
    )
    tempo_ms = int((time.perf_counter() - inicio) * 1000)

    if resposta.stop_reason == "refusal":
        raise ErroExtracao("O modelo recusou processar o documento.")
    if resposta.stop_reason == "max_tokens":
        raise ErroExtracao("A resposta excedeu o limite de tokens (documento muito extenso).")
    if resposta.parsed_output is None:
        raise ErroExtracao("O modelo não retornou dados estruturados.")

    metadados = Metadados(
        abordagem=abordagem,
        modelo=resposta.model,
        tokens_entrada=resposta.usage.input_tokens,
        tokens_saida=resposta.usage.output_tokens,
        tempo_ms=tempo_ms,
    )
    return resposta.parsed_output, metadados


def extrair_de_pdf(pdf_bytes: bytes) -> tuple[NotaFiscalExtraida, Metadados]:
    dados_b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")
    conteudo = [
        {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": dados_b64},
        },
        {"type": "text", "text": INSTRUCAO_USUARIO},
    ]
    return _extrair(conteudo, abordagem="pdf")


def extrair_de_texto(texto: str) -> tuple[NotaFiscalExtraida, Metadados]:
    return _extrair([{"type": "text", "text": mensagem_com_texto(texto)}], abordagem="texto")
