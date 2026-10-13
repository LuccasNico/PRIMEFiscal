from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import configuracoes
from app.db import criar_tabelas
from app.routers import notas


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    criar_tabelas()
    yield


app = FastAPI(
    title="PRIMEFiscal API",
    description="Extração e estruturação automatizada de dados de notas fiscais (NF-e, NFC-e, NFS-e) com IA.",
    version="0.1.0",
    lifespan=ciclo_de_vida,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=configuracoes.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notas.router)


@app.get("/api/saude", tags=["sistema"])
def saude():
    if configuracoes.provedor_ia == "lmstudio":
        modelo = configuracoes.lmstudio_modelo or "(primeiro disponível)"
    else:
        modelo = configuracoes.modelo_claude
    return {"status": "ok", "provedor": configuracoes.provedor_ia, "modelo": modelo}
