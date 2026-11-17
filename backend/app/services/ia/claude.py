"""Provedor Claude API (Anthropic).

O PDF vai direto para o modelo, que lê texto e imagem da página, inclusive de notas
escaneadas. A resposta é restrita ao schema NotaFiscalExtraida (structured outputs).
"""

import base64
import time
from functools import lru_cache

import anthropic
from pydantic import ValidationError

from app.config import configuracoes
from app.schemas.nota_fiscal import Metadados, NotaFiscalExtraida
from app.services.ia.base import (
    INSTRUCAO_USUARIO,
    PROMPT_SISTEMA,
    ErroExtracao,
    Extracao,
    Provedor,
    mensagem_com_texto,
)

NOME = "Claude (Anthropic)"

# Modelos em que a API reexecuta a requisição em um modelo alternativo quando há recusa por
# política de segurança. Nos demais (ex.: Haiku), o parâmetro `fallbacks` não tem efeito ou é rejeitado.
MODELOS_COM_FALLBACK = {
    "claude-fable-5-2",
    "claude-fable-5-1",
    "claude-opus-5-5",
    "claude-opus-5",
    "claude-sonnet-5-5",
}


@lru_cache
def _cliente() -> anthropic.Anthropic:
    # Sem chave no .env, o SDK procura outras credenciais (ex.: login feito com `ant auth login`)
    return anthropic.Anthropic(api_key=configuracoes.claude_chave or None)


def _chamar_api(conteudo: list[dict]):
    """Faz a requisição e converte as falhas do SDK em mensagens que o usuário consegue resolver."""
    parametros = dict(
        model=configuracoes.claude_modelo,
        max_tokens=16000,
        system=PROMPT_SISTEMA,
        messages=[{"role": "user", "content": conteudo}],
        output_format=NotaFiscalExtraida,
    )
    if configuracoes.claude_modelo in MODELOS_COM_FALLBACK:
        parametros.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")

    try:
        return _cliente().beta.messages.parse(**parametros)
    except anthropic.AuthenticationError as e:
        raise ErroExtracao(f"Chave de API do {NOME} inválida. Confira ANTHROPIC_API_KEY em backend/.env.") from e
    except anthropic.PermissionDeniedError as e:
        raise ErroExtracao(
            f"A chave de API do {NOME} não tem permissão para usar o modelo '{configuracoes.claude_modelo}'."
        ) from e
    except anthropic.NotFoundError as e:
        raise ErroExtracao(
            f"Modelo '{configuracoes.claude_modelo}' não encontrado. Confira MODELO_CLAUDE em backend/.env."
        ) from e
    except anthropic.RateLimitError as e:
        raise ErroExtracao(f"O limite de uso do {NOME} foi atingido. Tente de novo mais tarde.") from e
    except anthropic.APIStatusError as e:
        raise ErroExtracao(f"{NOME} respondeu com erro {e.status_code}: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise ErroExtracao(f"Não foi possível conectar ao serviço {NOME}. Verifique a conexão com a internet.") from e
    except anthropic.AnthropicError as e:
        raise ErroExtracao(f"Erro no cliente do {NOME}: {e}") from e
    except ValidationError as e:
        raise ErroExtracao(f"{NOME} devolveu dados fora do formato esperado ({e.error_count()} erro(s)).") from e
    except TypeError as e:
        # Sem nenhuma credencial configurada, o SDK lança TypeError antes de enviar a requisição
        if "authentication" in str(e):
            raise ErroExtracao(f"Chave de API do {NOME} não encontrada. Defina ANTHROPIC_API_KEY em backend/.env.") from e
        raise


def _extrair(conteudo: list[dict], abordagem: str) -> Extracao:
    inicio = time.perf_counter()
    resposta = _chamar_api(conteudo)
    tempo_ms = int((time.perf_counter() - inicio) * 1000)

    if resposta.stop_reason == "refusal":
        raise ErroExtracao("O modelo recusou processar o documento.")
    if resposta.stop_reason == "max_tokens":
        raise ErroExtracao("A resposta foi cortada pelo limite de tokens (documento muito extenso).")
    if resposta.parsed_output is None:
        raise ErroExtracao(f"{NOME} não devolveu dados estruturados.")

    metadados = Metadados(
        abordagem=abordagem,
        provedor=NOME,
        modelo=resposta.model,
        tokens_entrada=resposta.usage.input_tokens,
        tokens_saida=resposta.usage.output_tokens,
        tempo_ms=tempo_ms,
    )
    return resposta.parsed_output, metadados


def descrever() -> Provedor:
    return Provedor(nome=NOME, modelo=configuracoes.claude_modelo, pdf_exige_visao=False)


def extrair_de_pdf(pdf_bytes: bytes) -> Extracao:
    pdf = base64.standard_b64encode(pdf_bytes).decode("ascii")
    conteudo = [
        {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": pdf}},
        {"type": "text", "text": INSTRUCAO_USUARIO},
    ]
    return _extrair(conteudo, abordagem="pdf")


def extrair_de_texto(texto: str) -> Extracao:
    return _extrair([{"type": "text", "text": mensagem_com_texto(texto)}], abordagem="texto")
