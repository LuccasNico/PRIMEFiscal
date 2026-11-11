"""Provedor local via LM Studio (API compatível com OpenAI, padrão http://localhost:1234/v1).

Modelos locais não leem PDF diretamente, então:
- abordagem "texto": envia o texto extraído pelo pdfplumber (funciona com qualquer modelo);
- abordagem "pdf":   renderiza as páginas como imagens PNG (exige um modelo com visão).

A saída é restrita ao JSON Schema de NotaFiscalExtraida via `response_format`.
"""

import base64
import io
import time

import httpx
import pdfplumber
from pydantic import ValidationError

from app.config import configuracoes
from app.schemas.nota_fiscal import LIMITE_INFORMACOES_COMPLEMENTARES, Metadados, NotaFiscalExtraida
from app.services.ia.base import INSTRUCAO_USUARIO, PROMPT_SISTEMA, ErroExtracao, mensagem_com_texto

RESOLUCAO_IMAGEM_DPI = 150


def schema_sem_referencias(schema: dict) -> dict:
    """Substitui os $ref do Pydantic pelas definições, porque nem todo backend local entende $defs."""
    definicoes = schema.get("$defs", {})

    def resolver(no):
        if isinstance(no, dict):
            if "$ref" in no:
                return resolver(definicoes[no["$ref"].split("/")[-1]])
            return {chave: resolver(valor) for chave, valor in no.items() if chave != "$defs"}
        if isinstance(no, list):
            return [resolver(item) for item in no]
        return no

    return resolver(schema)


def _com_limite_de_texto_livre(schema: dict) -> dict:
    """Impõe o limite de tamanho no próprio schema: o LM Studio restringe a geração a ele,
    então o modelo não consegue despejar o documento inteiro em informacoes_complementares."""
    campo = schema["properties"]["informacoes_complementares"]
    for opcao in campo.get("anyOf", [campo]):
        if opcao.get("type") == "string":
            opcao["maxLength"] = LIMITE_INFORMACOES_COMPLEMENTARES
    return schema


SCHEMA_NOTA = _com_limite_de_texto_livre(schema_sem_referencias(NotaFiscalExtraida.model_json_schema()))


def _paginas_como_imagens(pdf_bytes: bytes) -> list[str]:
    imagens = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for pagina in pdf.pages:
                buffer = io.BytesIO()
                pagina.to_image(resolution=RESOLUCAO_IMAGEM_DPI).original.save(buffer, format="PNG")
                imagens.append(base64.standard_b64encode(buffer.getvalue()).decode("ascii"))
    except Exception as e:
        # O pdfplumber/pdfminer lança exceções de vários tipos para arquivos corrompidos ou com senha
        raise ErroExtracao("Não foi possível ler o PDF (arquivo corrompido ou protegido por senha).") from e
    return imagens


def _modelo() -> str:
    """Usa o modelo do .env ou, se vazio, o primeiro modelo de linguagem disponível no LM Studio."""
    if configuracoes.lmstudio_modelo:
        return configuracoes.lmstudio_modelo
    resposta = httpx.get(f"{configuracoes.lmstudio_url}/models", timeout=10)
    resposta.raise_for_status()
    # A lista também traz modelos de embedding, que não geram texto
    modelos = [m["id"] for m in resposta.json().get("data", []) if "embed" not in m["id"].lower()]
    if not modelos:
        raise ErroExtracao("Nenhum modelo disponível no LM Studio. Baixe e carregue um modelo.")
    return modelos[0]


def _extrair(conteudo: str | list[dict], abordagem: str) -> tuple[NotaFiscalExtraida, Metadados]:
    inicio = time.perf_counter()
    try:
        modelo = _modelo()
        resposta = httpx.post(
            f"{configuracoes.lmstudio_url}/chat/completions",
            json={
                "model": modelo,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": PROMPT_SISTEMA},
                    {"role": "user", "content": conteudo},
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "nota_fiscal", "strict": True, "schema": SCHEMA_NOTA},
                },
            },
            timeout=configuracoes.lmstudio_timeout,
        )
    except httpx.ConnectError:
        raise ErroExtracao(
            f"Não foi possível conectar ao LM Studio em {configuracoes.lmstudio_url}. "
            "Verifique se o servidor local está ligado (aba Developer > Start Server)."
        )
    except httpx.TimeoutException:
        raise ErroExtracao("O modelo local demorou demais para responder. Tente um modelo menor ou a abordagem 'texto'.")
    except httpx.HTTPError as e:
        raise ErroExtracao(f"Falha na comunicação com o LM Studio: {e}")

    if resposta.status_code != 200:
        detalhe = resposta.text[:300]
        if abordagem == "pdf":
            detalhe += " (a abordagem 'pdf' exige um modelo com visão; tente a abordagem 'texto')"
        raise ErroExtracao(f"Erro do LM Studio ({resposta.status_code}): {detalhe}")

    try:
        corpo = resposta.json()
        escolha = corpo["choices"][0]
        texto_resposta = escolha["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        raise ErroExtracao("O LM Studio devolveu uma resposta em formato inesperado.")

    if escolha.get("finish_reason") == "length":
        raise ErroExtracao(
            "A resposta do modelo local foi cortada por limite de tokens. "
            "Aumente o Context Length do modelo no LM Studio (recomendado: 8192 ou mais)."
        )

    try:
        dados = NotaFiscalExtraida.model_validate_json(texto_resposta or "")
    except ValidationError as e:
        raise ErroExtracao(f"O modelo local devolveu um JSON fora do formato esperado: {e.error_count()} erro(s).")

    uso = corpo.get("usage") or {}
    metadados = Metadados(
        abordagem=abordagem,
        modelo=f"lmstudio/{corpo.get('model', modelo)}",
        tokens_entrada=uso.get("prompt_tokens"),
        tokens_saida=uso.get("completion_tokens"),
        tempo_ms=int((time.perf_counter() - inicio) * 1000),
    )
    return dados, metadados


def extrair_de_pdf(pdf_bytes: bytes) -> tuple[NotaFiscalExtraida, Metadados]:
    conteudo = [{"type": "text", "text": INSTRUCAO_USUARIO}] + [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{imagem}"}}
        for imagem in _paginas_como_imagens(pdf_bytes)
    ]
    return _extrair(conteudo, abordagem="pdf")


def extrair_de_texto(texto: str) -> tuple[NotaFiscalExtraida, Metadados]:
    return _extrair(mensagem_com_texto(texto), abordagem="texto")
