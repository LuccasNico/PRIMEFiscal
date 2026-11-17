"""Requisições HTTP aos provedores de IA, com as falhas convertidas em mensagens para o usuário."""

import httpx

from app.services.ia.base import ErroExtracao

DICAS_POR_STATUS = {
    401: "Confira a chave de API em backend/.env.",
    403: "Confira a chave de API em backend/.env e as permissões da conta.",
    429: "O limite de uso foi atingido. Tente de novo mais tarde.",
}
DICA_ERRO_NO_SERVICO = "O serviço está instável ou sobrecarregado. Reprocesse a nota em alguns minutos."


def _detalhe_do_erro(resposta: httpx.Response) -> str:
    """Mensagem de erro devolvida pela API (em geral em error.message) ou o início do corpo da resposta."""
    try:
        erro = resposta.json().get("error")
    except (ValueError, AttributeError):
        erro = None
    if isinstance(erro, dict):
        erro = erro.get("message")
    return (erro if isinstance(erro, str) and erro else resposta.text)[:300].strip()


def requisitar(
    metodo: str,
    url: str,
    *,
    nome: str,
    timeout: float,
    dica_conexao: str = "",
    dica_demora: str = "",
    dica_erro: str = "",
    **parametros,
) -> dict:
    """Faz a requisição ao provedor `nome` e devolve o JSON da resposta.

    As dicas são frases acrescentadas à mensagem de erro para dizer ao usuário como resolver.
    """
    try:
        resposta = httpx.request(metodo, url, timeout=timeout, **parametros)
    except httpx.ConnectError as e:
        raise ErroExtracao(f"Não foi possível conectar ao serviço {nome}. {dica_conexao}".strip()) from e
    except httpx.TimeoutException as e:
        raise ErroExtracao(f"{nome} não respondeu em {timeout:g} segundos. {dica_demora}".strip()) from e
    except httpx.HTTPError as e:
        raise ErroExtracao(f"Falha na comunicação com {nome}: {e}") from e

    if resposta.status_code >= 400:
        if resposta.status_code >= 500:
            dica = DICA_ERRO_NO_SERVICO
        else:
            dica = DICAS_POR_STATUS.get(resposta.status_code, dica_erro)
        raise ErroExtracao(
            f"{nome} respondeu com erro {resposta.status_code}: {_detalhe_do_erro(resposta)} {dica}".strip()
        )
    try:
        return resposta.json()
    except ValueError as e:
        raise ErroExtracao(f"{nome} devolveu uma resposta em formato inesperado.") from e
