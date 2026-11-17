import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import acesso
from app.config import configuracoes
from app.db import criar_tabelas
from app.routers import acesso as rotas_de_acesso
from app.routers import banco, modelos, notas
from app.services import ia
from app.services.fila import fila

log = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    if not acesso.exige_senha():
        log.warning("ACESSO_SENHA vazia: qualquer pessoa com o endereço da API pode ver as notas e usar a IA. Defina-a no deploy.")
    criar_tabelas()
    fila.iniciar()
    yield
    fila.parar()


app = FastAPI(
    title="PRIMEFiscal API",
    description="Extração e estruturação automatizada de dados de notas fiscais (NF-e, NFC-e, NFS-e) com IA.",
    version="0.5.0",
    lifespan=ciclo_de_vida,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=configuracoes.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notas.router)
app.include_router(banco.router)
app.include_router(modelos.router)
app.include_router(rotas_de_acesso.router)


# Única rota aberta além de /api/acesso: a interface a consulta antes do login e o Render a usa como health check
@app.get("/api/saude", tags=["sistema"], summary="Informa se a API está no ar, qual IA está em uso, se ela exige senha e os limites de envio")
def saude():
    provedor = ia.descrever()
    return {
        "status": "ok",
        "provedor": configuracoes.provedor_ia,
        "nome_provedor": provedor.nome,
        "modelo": provedor.modelo,
        "escolhe_modelo": ia.permite_escolher_modelo(),
        "pdf_exige_visao": provedor.pdf_exige_visao,
        "exige_senha": acesso.exige_senha(),
        "tamanho_maximo_mb": configuracoes.tamanho_maximo_bytes // (1024 * 1024),
        "maximo_de_arquivos_por_envio": notas.MAXIMO_DE_ARQUIVOS_POR_ENVIO,
    }
