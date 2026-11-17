from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import configuracoes
from app.db import criar_tabelas
from app.routers import notas
from app.services import ia
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
    version="0.3.0",
    lifespan=ciclo_de_vida,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=configuracoes.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notas.router)


@app.get("/api/saude", tags=["sistema"], summary="Informa se a API está no ar, qual IA está em uso e os limites de envio")
def saude():
    provedor = ia.descrever()
    return {
        "status": "ok",
        "provedor": configuracoes.provedor_ia,
        "nome_provedor": provedor.nome,
        "modelo": provedor.modelo,
        "pdf_exige_visao": provedor.pdf_exige_visao,
        "tamanho_maximo_mb": configuracoes.tamanho_maximo_bytes // (1024 * 1024),
        "maximo_de_arquivos_por_envio": notas.MAXIMO_DE_ARQUIVOS_POR_ENVIO,
    }
