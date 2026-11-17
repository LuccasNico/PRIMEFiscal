import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import acesso

router = APIRouter(prefix="/api/acesso", tags=["acesso"])

# Cada senha errada demora a ser respondida, o que torna inviável testar senhas em sequência
ESPERA_APOS_SENHA_ERRADA_SEGUNDOS = 1.0


class PedidoDeAcesso(BaseModel):
    senha: str = Field(max_length=200)


class TokenDeAcesso(BaseModel):
    token: str = Field(description="Envie no cabeçalho Authorization: Bearer <token>")
    expira_em: datetime


@router.post("", response_model=TokenDeAcesso, summary="Troca a senha de acesso por um token para as rotas que usam a IA")
async def entrar(pedido: PedidoDeAcesso):
    if not acesso.exige_senha():
        raise HTTPException(400, "Este servidor não exige senha de acesso.")
    if not acesso.senha_correta(pedido.senha):
        await asyncio.sleep(ESPERA_APOS_SENHA_ERRADA_SEGUNDOS)
        raise HTTPException(401, "Senha incorreta.")
    token, expira_em = acesso.gerar_token()
    return TokenDeAcesso(token=token, expira_em=datetime.fromtimestamp(expira_em, timezone.utc))
