"""Provedor para APIs no padrão Chat Completions da OpenAI.

O mesmo código atende OpenAI, Groq, OpenRouter, Together, Ollama, vLLM e qualquer outro serviço
com a rota ``/chat/completions`` (configurado em ``API_COMPATIVEL_*``). O provedor LM Studio
também usa este módulo. APIs com protocolo próprio precisam de um módulo específico.

Esses modelos não leem PDF: na abordagem "pdf", as páginas vão como imagens.
"""

import time
from dataclasses import dataclass

from app.config import configuracoes
from app.schemas.nota_fiscal import Metadados
from app.services.ia import http
from app.services.ia.base import (
    INSTRUCAO_DE_FORMATO,
    INSTRUCAO_USUARIO,
    PROMPT_SISTEMA,
    SCHEMA_NOTA,
    ErroExtracao,
    Extracao,
    Provedor,
    interpretar_resposta,
    mensagem_com_texto,
    paginas_como_imagens,
)

DICA_SEM_VISAO = "A abordagem 'pdf' exige um modelo com visão; se não for o caso, use a abordagem 'texto'."


@dataclass(frozen=True)
class Servico:
    """Um serviço no padrão da OpenAI e as dicas mostradas quando ele falha."""

    nome: str
    url: str
    modelo: str
    timeout: float
    chave: str = ""
    formato_resposta: str = "json_schema"
    dica_conexao: str = ""
    dica_demora: str = ""
    dica_resposta_cortada: str = "Aumente o limite de tokens de saída do modelo."


def _formato_da_resposta(formato: str) -> dict:
    """Como a API deve restringir a resposta. No formato "prompt" não há restrição: vale o pedido do prompt."""
    if formato == "json_schema":
        esquema = {"name": "nota_fiscal", "strict": True, "schema": SCHEMA_NOTA}
        return {"response_format": {"type": "json_schema", "json_schema": esquema}}
    if formato == "json_object":
        return {"response_format": {"type": "json_object"}}
    return {}


def extrair(servico: Servico, conteudo: str | list[dict], abordagem: str) -> Extracao:
    # Só o formato json_schema leva o schema na requisição; nos outros, ele vai escrito no prompt
    prompt = PROMPT_SISTEMA
    if servico.formato_resposta != "json_schema":
        prompt += "\n\n" + INSTRUCAO_DE_FORMATO

    inicio = time.perf_counter()
    corpo = http.requisitar(
        "POST",
        f"{servico.url}/chat/completions",
        nome=servico.nome,
        timeout=servico.timeout,
        dica_conexao=servico.dica_conexao,
        dica_demora=servico.dica_demora,
        dica_erro=DICA_SEM_VISAO if abordagem == "pdf" else "",
        headers={"Authorization": f"Bearer {servico.chave}"} if servico.chave else {},
        json={
            "model": servico.modelo,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": conteudo},
            ],
            **_formato_da_resposta(servico.formato_resposta),
        },
    )
    tempo_ms = int((time.perf_counter() - inicio) * 1000)

    try:
        escolha = corpo["choices"][0]
        texto = escolha["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise ErroExtracao(f"{servico.nome} devolveu uma resposta em formato inesperado.") from e
    if escolha.get("finish_reason") == "length":
        raise ErroExtracao(
            f"A resposta de {servico.nome} foi cortada pelo limite de tokens. {servico.dica_resposta_cortada}"
        )

    uso = corpo.get("usage") or {}
    metadados = Metadados(
        abordagem=abordagem,
        provedor=servico.nome,
        modelo=corpo.get("model") or servico.modelo,
        tokens_entrada=uso.get("prompt_tokens"),
        tokens_saida=uso.get("completion_tokens"),
        tempo_ms=tempo_ms,
    )
    return interpretar_resposta(texto, servico.nome), metadados


def conteudo_com_imagens(pdf_bytes: bytes) -> list[dict]:
    """Mensagem do usuário com as páginas do PDF como imagens."""
    return [{"type": "text", "text": INSTRUCAO_USUARIO}] + [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{imagem}"}}
        for imagem in paginas_como_imagens(pdf_bytes)
    ]


def _servico() -> Servico:
    return Servico(
        nome=configuracoes.compativel_nome,
        url=configuracoes.compativel_url,
        modelo=configuracoes.compativel_modelo,
        timeout=configuracoes.compativel_timeout,
        chave=configuracoes.compativel_chave,
        formato_resposta=configuracoes.compativel_formato_resposta,
        dica_conexao=f"Confira API_COMPATIVEL_URL em backend/.env ({configuracoes.compativel_url}).",
    )


def descrever() -> Provedor:
    return Provedor(nome=configuracoes.compativel_nome, modelo=configuracoes.compativel_modelo, pdf_exige_visao=True)


def extrair_de_pdf(pdf_bytes: bytes) -> Extracao:
    return extrair(_servico(), conteudo_com_imagens(pdf_bytes), abordagem="pdf")


def extrair_de_texto(texto: str) -> Extracao:
    return extrair(_servico(), mensagem_com_texto(texto), abordagem="texto")
