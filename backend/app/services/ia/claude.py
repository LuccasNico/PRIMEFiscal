"""Provedor Claude API (Anthropic).

O PDF pode ser enviado direto: o Claude lê texto e imagem da página, inclusive
de notas escaneadas. A resposta é restrita ao schema NotaFiscalExtraida
(structured outputs), então o retorno é sempre um JSON válido nesse formato.
"""

import base64
import time
from functools import lru_cache

import anthropic
from pydantic import ValidationError

from app.config import configuracoes
from app.schemas.nota_fiscal import Metadados, NotaFiscalExtraida
from app.services.ia.base import INSTRUCAO_USUARIO, PROMPT_SISTEMA, ErroExtracao, mensagem_com_texto

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
    # Lê ANTHROPIC_API_KEY do ambiente (.env)
    return anthropic.Anthropic()


def _chamar_api(conteudo: list[dict]):
    """Faz a requisição e converte as falhas do SDK em mensagens que o usuário consegue resolver."""
    parametros = dict(
        model=configuracoes.modelo_claude,
        max_tokens=16000,
        system=PROMPT_SISTEMA,
        messages=[{"role": "user", "content": conteudo}],
        output_format=NotaFiscalExtraida,
    )
    if configuracoes.modelo_claude in MODELOS_COM_FALLBACK:
        parametros.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")

    try:
        return _cliente().beta.messages.parse(**parametros)
    except anthropic.AuthenticationError as e:
        raise ErroExtracao("Chave da Claude API inválida. Confira ANTHROPIC_API_KEY em backend/.env.") from e
    except anthropic.PermissionDeniedError as e:
        raise ErroExtracao(
            f"A chave da Claude API não tem permissão para usar o modelo '{configuracoes.modelo_claude}'."
        ) from e
    except anthropic.NotFoundError as e:
        raise ErroExtracao(
            f"Modelo '{configuracoes.modelo_claude}' não encontrado. Confira MODELO_CLAUDE em backend/.env."
        ) from e
    except anthropic.RateLimitError as e:
        raise ErroExtracao("Limite de requisições da Claude API atingido. Tente novamente em instantes.") from e
    except anthropic.APIStatusError as e:
        raise ErroExtracao(f"Erro na Claude API ({e.status_code}): {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise ErroExtracao("Falha de conexão com a Claude API. Verifique a internet.") from e
    except anthropic.AnthropicError as e:
        raise ErroExtracao(f"Erro no cliente da Claude API: {e}") from e
    except ValidationError as e:
        raise ErroExtracao(f"O modelo devolveu dados fora do formato esperado: {e.error_count()} erro(s).") from e
    except TypeError as e:
        # Sem nenhuma credencial configurada, o SDK lança TypeError antes de enviar a requisição
        if "authentication" in str(e):
            raise ErroExtracao(
                "Credenciais da Claude API não encontradas. Defina ANTHROPIC_API_KEY em backend/.env."
            ) from e
        raise


def _extrair(conteudo: list[dict], abordagem: str) -> tuple[NotaFiscalExtraida, Metadados]:
    inicio = time.perf_counter()
    resposta = _chamar_api(conteudo)
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
