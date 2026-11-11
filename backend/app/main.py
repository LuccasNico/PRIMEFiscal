from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import configuracoes
from app.db import criar_tabelas
from app.routers import notas
from app.services.fila import fila


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    criar_tabelas()
    fila.iniciar()
    yield
    fila.parar()


app = FastAPI(
    title="PRIMEFiscal API",
    description="Extração e estruturação automatizada de dados de notas fiscais (NF-e, NFC-e, NFS-e) com IA.",
    version="0.2.0",
    lifespan=ciclo_de_vida,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=configuracoes.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notas.router)


@app.get("/api/saude", tags=["sistema"], summary="Informa se a API está no ar e qual IA está configurada")
def saude():
    if configuracoes.provedor_ia == "lmstudio":
        modelo = configuracoes.lmstudio_modelo or "(primeiro disponível)"
    elif configuracoes.provedor_ia == "compativel":
        modelo = configuracoes.compativel_modelo
    elif configuracoes.provedor_ia == "gemini":
        modelo = configuracoes.gemini_modelo
    else:
        modelo = configuracoes.modelo_claude
    return {
        "status": "ok",
        "provedor": configuracoes.provedor_ia,
        "modelo": modelo,
        "nome_provedor": (
            configuracoes.compativel_nome if configuracoes.provedor_ia == "compativel" else "Google Gemini"
            if configuracoes.provedor_ia == "gemini"
            else configuracoes.provedor_ia
        ),
        "requer_modelo_visao_pdf": configuracoes.provedor_ia != "claude",
        "tamanho_maximo_mb": configuracoes.tamanho_maximo_bytes // (1024 * 1024),
        "maximo_de_arquivos_por_envio": notas.MAXIMO_DE_ARQUIVOS_POR_ENVIO,
    }
