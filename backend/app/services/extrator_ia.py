"""Extração dos dados da nota fiscal com a Claude API.

Duas abordagens, comparadas nos experimentos do TCC:
- "pdf":   o PDF é enviado direto ao Claude, que lê texto e imagem da página
           (funciona também com notas escaneadas);
- "texto": o texto extraído pelo pdfplumber é enviado ao Claude.

Nas duas, a resposta é restrita ao schema NotaFiscalExtraida (structured outputs),
então o retorno é sempre um JSON válido nesse formato.
"""

import base64
import time
from functools import lru_cache

import anthropic

from app.config import configuracoes
from app.schemas.nota_fiscal import Metadados, NotaFiscalExtraida

PROMPT_SISTEMA = """Você é um especialista em documentos fiscais brasileiros: NF-e (DANFE), NFC-e e NFS-e.
Sua tarefa é extrair os dados do documento recebido exatamente como aparecem nele.

Regras:
- Identifique o tipo do documento (NF-e, NFC-e ou NFS-e). Use "desconhecido" se não for uma nota fiscal.
- Valores monetários e quantidades são números decimais com ponto (ex.: 1234.56), sem símbolo de moeda.
- Datas no formato AAAA-MM-DD.
- CNPJ, CPF e chave de acesso sem pontuação nem espaços.
- Liste todos os itens ou serviços, na ordem em que aparecem.
- Se um campo não existir no documento ou estiver ilegível, use null. Nunca invente nem calcule valores que não estejam no documento."""


class ErroExtracao(Exception):
    """A IA não conseguiu devolver uma extração utilizável."""


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
        {"type": "text", "text": "Extraia os dados desta nota fiscal."},
    ]
    return _extrair(conteudo, abordagem="pdf")


def extrair_de_texto(texto: str) -> tuple[NotaFiscalExtraida, Metadados]:
    conteudo = [
        {
            "type": "text",
            "text": f"Texto extraído de uma nota fiscal em PDF:\n\n<documento>\n{texto}\n</documento>\n\n"
            "Extraia os dados desta nota fiscal.",
        }
    ]
    return _extrair(conteudo, abordagem="texto")
