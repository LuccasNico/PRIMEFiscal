"""Provedor Gemini API (Google), o padrão do projeto.

Usa a API nativa (generateContent). O PDF vai direto para o modelo, que lê texto e imagem da
página, inclusive de notas escaneadas. A resposta é restrita ao JSON Schema da nota.

O modelo é escolhido na interface, entre os que a própria API lista para a chave configurada.
"""

import base64
import re
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
    Modelo,
    Provedor,
    interpretar_resposta,
    mensagem_com_texto,
)

NOME = "Google Gemini"
URL_DOS_MODELOS = "https://generativelanguage.googleapis.com/v1beta/models"

# Usado quando a requisição não escolhe o modelo e sugerido primeiro na interface
MODELO_PADRAO = "gemini-3.5-flash"

# A lista muda pouco: guardá-la evita consultar o Google a cada envio e a cada abertura da interface
VALIDADE_DA_LISTA_SEGUNDOS = 600
TIMEOUT_DA_LISTA_SEGUNDOS = 20
# Modelos que geram conteúdo, mas não servem para extrair dados em JSON (voz, transcrição, geração de
# imagem — a família Nano Banana —, tempo real etc.)
TRECHOS_DE_MODELOS_EXCLUIDOS = (
    "tts",
    "transcribe",
    "image",
    "banana",
    "audio",
    "live",
    "embedding",
    "computer-use",
    "robotics",
)

# Motivos de término que indicam resposta incompleta ou bloqueada
MOTIVOS_DE_FALHA = {
    "MAX_TOKENS": "A resposta foi cortada pelo limite de tokens (documento muito extenso).",
    "SAFETY": "O modelo recusou processar o documento (filtro de segurança).",
    "RECITATION": "O modelo interrompeu a resposta (filtro de recitação).",
}

_lista_guardada: tuple[float, list[Modelo]] | None = None


def _cabecalhos() -> dict:
    if not configuracoes.gemini_chave:
        raise ErroExtracao(f"Chave de API do {NOME} não encontrada. Defina GEMINI_API_KEY em backend/.env.")
    return {"x-goog-api-key": configuracoes.gemini_chave}


def _serve_para_extracao(modelo: dict) -> bool:
    nome = modelo.get("name", "")
    return (
        nome.startswith("models/gemini")
        and "generateContent" in modelo.get("supportedGenerationMethods", [])
        and not any(trecho in nome for trecho in TRECHOS_DE_MODELOS_EXCLUIDOS)
    )


def _ordem(modelo: Modelo) -> tuple:
    # Versões mais novas primeiro; apelidos sem número (ex.: gemini-flash-latest) no fim
    versao = re.match(r"gemini-(\d+(?:\.\d+)?)", modelo.id)
    return (-float(versao.group(1)) if versao else 0, modelo.id)


def listar_modelos() -> list[Modelo]:
    """Modelos Gemini que a chave pode usar e que geram texto, dos mais novos para os mais antigos."""
    global _lista_guardada
    if _lista_guardada and time.monotonic() - _lista_guardada[0] < VALIDADE_DA_LISTA_SEGUNDOS:
        return _lista_guardada[1]

    modelos, pagina = [], None
    while True:
        corpo = http.requisitar(
            "GET",
            URL_DOS_MODELOS,
            nome=NOME,
            timeout=TIMEOUT_DA_LISTA_SEGUNDOS,
            dica_conexao="Verifique a conexão com a internet.",
            headers=_cabecalhos(),
            params={"pageSize": 1000, **({"pageToken": pagina} if pagina else {})},
        )
        for item in corpo.get("models") or []:
            if _serve_para_extracao(item):
                id_modelo = item["name"].removeprefix("models/")
                modelos.append(Modelo(id_modelo, item.get("displayName") or id_modelo, item.get("description") or ""))
        pagina = corpo.get("nextPageToken")
        if not pagina:
            break

    if not modelos:
        raise ErroExtracao(f"A chave de API do {NOME} não tem acesso a nenhum modelo de texto.")
    modelos.sort(key=_ordem)
    _lista_guardada = (time.monotonic(), modelos)
    return modelos


def _extrair(partes: list[dict], abordagem: str, modelo: str | None) -> Extracao:
    modelo = modelo or MODELO_PADRAO
    inicio = time.perf_counter()
    corpo = http.requisitar(
        "POST",
        f"{URL_DOS_MODELOS}/{modelo}:generateContent",
        nome=NOME,
        timeout=configuracoes.gemini_timeout,
        dica_conexao="Verifique a conexão com a internet.",
        dica_erro="Escolha outro modelo na interface.",
        headers=_cabecalhos(),
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
        modelo=corpo.get("modelVersion") or modelo,
        tokens_entrada=uso.get("promptTokenCount"),
        tokens_saida=uso.get("candidatesTokenCount"),
        tempo_ms=tempo_ms,
    )
    return interpretar_resposta(texto, NOME), metadados


def descrever() -> Provedor:
    return Provedor(nome=NOME, modelo=MODELO_PADRAO, pdf_exige_visao=False)


def extrair_de_pdf(pdf_bytes: bytes, modelo: str | None = None) -> Extracao:
    pdf = base64.standard_b64encode(pdf_bytes).decode("ascii")
    partes = [{"inlineData": {"mimeType": "application/pdf", "data": pdf}}, {"text": INSTRUCAO_USUARIO}]
    return _extrair(partes, "pdf", modelo)


def extrair_de_texto(texto: str, modelo: str | None = None) -> Extracao:
    return _extrair([{"text": mensagem_com_texto(texto)}], "texto", modelo)
