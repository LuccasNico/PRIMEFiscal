"""Senha de acesso à API.

Sem proteção, qualquer pessoa que descobrisse o endereço da API poderia ler e apagar as notas (que
têm CNPJ, CPF e endereços) e enviar notas para gastar a cota (ou os créditos) do provedor de IA. Um
token fixo embutido no frontend não resolveria: ele fica visível no JavaScript publicado e nas
requisições. Por isso a interface pede uma senha (ACESSO_SENHA) e a troca, em POST /api/acesso,
por um token com prazo de validade, enviado depois no cabeçalho ``Authorization: Bearer <token>``.

Todas as rotas exigem o token, menos /api/saude (a verificação de saúde do Render e a interface
precisam dela antes do login) e /api/acesso.

O token é ``<expiração em segundos Unix>.<assinatura HMAC-SHA256 da expiração>``. A chave da
assinatura é derivada da senha com PBKDF2, então nada precisa ser guardado no servidor: os tokens
continuam valendo depois de um reinício (o plano gratuito do Render dorme) e deixam de valer
quando a senha muda.

Com ACESSO_SENHA vazia não há verificação, o que só convém no desenvolvimento local.
"""

import hashlib
import hmac
import time
from functools import cache

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import configuracoes

ITERACOES_PBKDF2 = 200_000
SAL_PBKDF2 = b"primefiscal-acesso"

_bearer = HTTPBearer(auto_error=False, description="Token obtido em POST /api/acesso com a senha de acesso")


def exige_senha() -> bool:
    return bool(configuracoes.acesso_senha)


def senha_correta(senha: str) -> bool:
    # compare_digest leva o mesmo tempo para qualquer senha errada, sem revelar quantos caracteres acertaram
    return hmac.compare_digest(senha.encode(), configuracoes.acesso_senha.encode())


@cache
def _chave(senha: str) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", senha.encode(), SAL_PBKDF2, ITERACOES_PBKDF2)


def _assinatura(expira_em: int) -> str:
    return hmac.new(_chave(configuracoes.acesso_senha), str(expira_em).encode(), hashlib.sha256).hexdigest()


def gerar_token() -> tuple[str, int]:
    """Devolve o token e o momento em que ele expira (segundos Unix)."""
    expira_em = int(time.time() + configuracoes.acesso_validade_horas * 3600)
    return f"{expira_em}.{_assinatura(expira_em)}", expira_em


def token_valido(token: str) -> bool:
    expira_em, _, assinatura = token.partition(".")
    if not expira_em.isdigit():
        return False
    assinatura_certa = hmac.compare_digest(assinatura.encode(), _assinatura(int(expira_em)).encode())
    return assinatura_certa and int(expira_em) > time.time()


def exigir_acesso(credenciais: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> None:
    """Dependência das rotas protegidas: recusa a requisição sem um token válido."""
    if not exige_senha():
        return
    if credenciais is None:
        mensagem = "Esta ação exige a senha de acesso."
    elif not token_valido(credenciais.credentials):
        mensagem = "Sua sessão expirou. Digite a senha de acesso novamente."
    else:
        return
    raise HTTPException(401, mensagem, headers={"WWW-Authenticate": "Bearer"})
