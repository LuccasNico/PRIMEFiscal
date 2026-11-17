"""Provedor Gemini API (Google), o padrão do projeto.

Usa a API nativa (generateContent). O PDF vai direto para o modelo, que lê texto e imagem da
página, inclusive de notas escaneadas. A resposta é restrita ao JSON Schema da nota.
"""

import base64
import time

from app.config import configuracoes
from app.schemas.nota_fiscal import Metadados
from app.services.ia import http
from app.services.ia.base import (
    INSTRUCAO_USUARIO,
    PROMPT_SISTEMA,
    SCHEMA_NOTA,
    ErroExtracao,
    Extracao,
    Provedor,
    interpretar_resposta,
    mensagem_com_texto,
)

NOME = "Google Gemini"
URL_DOS_MODELOS = "https://generativelanguage.googleapis.com/v1beta/models"

# Motivos de término que indicam resposta incompleta ou bloqueada
MOTIVOS_DE_FALHA = {
    "MAX_TOKENS": "A resposta foi cortada pelo limite de tokens (documento muito extenso).",
    "SAFETY": "O modelo recusou processar o documento (filtro de segurança).",
    "RECITATION": "O modelo interrompeu a resposta (filtro de recitação).",
}


def _extrair(partes: list[dict], abordagem: str) -> Extracao:
    if not configuracoes.gemini_chave:
        raise ErroExtracao(f"Chave de API do {NOME} não encontrada. Defina GEMINI_API_KEY em backend/.env.")

    inicio = time.perf_counter()
    corpo = http.requisitar(
        "POST",
        f"{URL_DOS_MODELOS}/{configuracoes.gemini_modelo}:generateContent",
        nome=NOME,
        timeout=configuracoes.gemini_timeout,
        dica_conexao="Verifique a conexão com a internet.",
        dica_erro="Confira GEMINI_MODELO em backend/.env.",
        headers={"x-goog-api-key": configuracoes.gemini_chave},
        json={
            "systemInstruction": {"parts": [{"text": PROMPT_SISTEMA}]},
            "contents": [{"role": "user", "parts": partes}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseJsonSchema": SCHEMA_NOTA,
            },
        },
    )
    tempo_ms = int((time.perf_counter() - inicio) * 1000)

    bloqueio = (corpo.get("promptFeedback") or {}).get("blockReason")
    if bloqueio:
        raise ErroExtracao(f"O modelo recusou processar o documento (motivo: {bloqueio}).")
    try:
        candidato = corpo["candidates"][0]
        texto = "".join(parte.get("text", "") for parte in candidato["content"]["parts"])
    except (KeyError, IndexError, TypeError) as e:
        raise ErroExtracao(f"{NOME} devolveu uma resposta em formato inesperado.") from e
    if candidato.get("finishReason") in MOTIVOS_DE_FALHA:
        raise ErroExtracao(MOTIVOS_DE_FALHA[candidato["finishReason"]])

    uso = corpo.get("usageMetadata") or {}
    metadados = Metadados(
        abordagem=abordagem,
        provedor=NOME,
        modelo=corpo.get("modelVersion") or configuracoes.gemini_modelo,
        tokens_entrada=uso.get("promptTokenCount"),
        tokens_saida=uso.get("candidatesTokenCount"),
        tempo_ms=tempo_ms,
    )
    return interpretar_resposta(texto, NOME), metadados


def descrever() -> Provedor:
    return Provedor(nome=NOME, modelo=configuracoes.gemini_modelo, pdf_exige_visao=False)


def extrair_de_pdf(pdf_bytes: bytes) -> Extracao:
    pdf = base64.standard_b64encode(pdf_bytes).decode("ascii")
    return _extrair([{"inlineData": {"mimeType": "application/pdf", "data": pdf}}, {"text": INSTRUCAO_USUARIO}], "pdf")


def extrair_de_texto(texto: str) -> Extracao:
    return _extrair([{"text": mensagem_com_texto(texto)}], "texto")
