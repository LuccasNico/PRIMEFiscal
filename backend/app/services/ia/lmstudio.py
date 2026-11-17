"""Provedor local via LM Studio.

O servidor do LM Studio segue o padrão da OpenAI, então a extração é a do módulo `compativel`.
Aqui ficam só as particularidades: a escolha automática do modelo e as dicas de configuração.
"""

from app.config import configuracoes
from app.services.ia import compativel, http
from app.services.ia.base import ErroExtracao, Extracao, Provedor, mensagem_com_texto

NOME = "LM Studio"
DICA_CONEXAO = "Verifique se o servidor local do LM Studio está ligado e se LMSTUDIO_URL em backend/.env está correto."


def _modelo() -> str:
    """Usa o modelo do .env ou, se vazio, o primeiro modelo de linguagem disponível no LM Studio."""
    if configuracoes.lmstudio_modelo:
        return configuracoes.lmstudio_modelo
    corpo = http.requisitar(
        "GET", f"{configuracoes.lmstudio_url}/models", nome=NOME, timeout=10, dica_conexao=DICA_CONEXAO
    )
    try:
        # A lista também traz modelos de embedding, que não geram texto
        modelos = [modelo["id"] for modelo in corpo["data"] if "embed" not in modelo["id"].lower()]
    except (KeyError, TypeError) as e:
        raise ErroExtracao(f"{NOME} devolveu uma resposta em formato inesperado.") from e
    if not modelos:
        raise ErroExtracao(f"Nenhum modelo disponível no {NOME}. Baixe e carregue um modelo.")
    return modelos[0]


def _servico() -> compativel.Servico:
    return compativel.Servico(
        nome=NOME,
        url=configuracoes.lmstudio_url,
        modelo=_modelo(),
        timeout=configuracoes.lmstudio_timeout,
        dica_conexao=DICA_CONEXAO,
        dica_demora="Tente um modelo menor ou a abordagem 'texto'.",
        dica_resposta_cortada="Aumente o Context Length do modelo no LM Studio (recomendado: 8192 ou mais).",
    )


def descrever() -> Provedor:
    modelo = configuracoes.lmstudio_modelo or "primeiro modelo disponível"
    return Provedor(nome=NOME, modelo=modelo, pdf_exige_visao=True)


def extrair_de_pdf(pdf_bytes: bytes) -> Extracao:
    return compativel.extrair(_servico(), compativel.conteudo_com_imagens(pdf_bytes), abordagem="pdf")


def extrair_de_texto(texto: str) -> Extracao:
    return compativel.extrair(_servico(), mensagem_com_texto(texto), abordagem="texto")
