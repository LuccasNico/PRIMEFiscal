import os
import tempfile
import threading
import time
from types import SimpleNamespace

import pytest

# Ambiente isolado, definido antes de importar a aplicação (tem prioridade sobre o .env do desenvolvedor).
# Os testes nunca chamam uma IA de verdade: o backend/.env não é lido e o LM Studio aponta para uma porta fechada.
# Para rodar os testes num PostgreSQL, defina DATABASE_URL_TESTES com um banco descartável: ele é APAGADO a cada teste.
_pasta = tempfile.mkdtemp()
os.environ.update(
    {
        "DATABASE_URL": os.getenv("DATABASE_URL_TESTES") or f"sqlite:///{os.path.join(_pasta, 'teste.db')}",
        "PASTA_UPLOADS": os.path.join(_pasta, "uploads"),
        "TAMANHO_MAXIMO_MB": "1",
        "ARQUIVO_ENV": os.path.join(_pasta, "nao-existe.env"),
        "PROVEDOR_IA": "lmstudio",
        "LMSTUDIO_URL": "http://127.0.0.1:9/v1",
    }
)

from fastapi.testclient import TestClient  # noqa: E402

from app.db import (  # noqa: E402
    ItemRegistro,
    NotaFiscalRegistro,
    NotaSalvaRegistro,
    PagamentoRegistro,
    ParticipanteRegistro,
    SessaoLocal,
    criar_tabelas,
)
from app.main import app  # noqa: E402
from app.schemas.nota_fiscal import Metadados, NotaFiscalExtraida  # noqa: E402
from app.services.validacao import validar_nota  # noqa: E402

NOTA_EXTRAIDA = {
    "tipo_documento": "NFS-e",
    "numero": "123",
    "emitente": {"razao_social": "Empresa Exemplo LTDA", "cnpj": "11222333000181"},
    "itens": [{"descricao": "Serviço A", "quantidade": 2, "valor_unitario": 10.5, "valor_total": 21.0}],
    "valor_total_produtos": 21.0,
    "valor_total_nota": 21.0,
}


def limpar_banco() -> None:
    criar_tabelas()
    with SessaoLocal() as sessao:
        # Das tabelas que dependem para as tabelas de que dependem
        for modelo in (ItemRegistro, PagamentoRegistro, NotaSalvaRegistro, ParticipanteRegistro, NotaFiscalRegistro):
            sessao.query(modelo).delete()
        sessao.commit()


@pytest.fixture
def api_falsa(monkeypatch):
    """Troca as requisições HTTP dos provedores por respostas definidas no teste.

    Uso: `recebidas = api_falsa(resposta1, resposta2, ...)`. Cada item é um `httpx.Response`
    ou uma exceção a ser lançada. `recebidas` guarda (método, url, parâmetros) de cada chamada.
    """
    import httpx

    recebidas = []

    def configurar(*respostas):
        fila_de_respostas = list(respostas)

        def requisicao_falsa(metodo, url, **parametros):
            recebidas.append((metodo, url, parametros))
            resposta = fila_de_respostas.pop(0)
            if isinstance(resposta, Exception):
                raise resposta
            resposta.request = httpx.Request(metodo, url)
            return resposta

        monkeypatch.setattr("app.services.ia.http.httpx.request", requisicao_falsa)
        return recebidas

    return configurar


@pytest.fixture
def ia_falsa(monkeypatch):
    """Troca a extração com IA por uma função controlada pelo teste.

    - `liberar`: enquanto estiver desligado, o processamento fica parado (simula uma IA lenta);
    - `erros`: exceções lançadas nas próximas chamadas, na ordem (None = sucesso);
    - `chamadas`: (pdf_bytes, abordagem) de cada nota processada.
    """
    controle = SimpleNamespace(liberar=threading.Event(), erros=[], chamadas=[])
    controle.liberar.set()

    def processar_falso(pdf_bytes, abordagem):
        controle.chamadas.append((pdf_bytes, abordagem))
        controle.liberar.wait(timeout=10)
        erro = controle.erros.pop(0) if controle.erros else None
        if erro is not None:
            raise erro
        dados = NotaFiscalExtraida(**NOTA_EXTRAIDA)
        return dados, validar_nota(dados), Metadados(abordagem=abordagem.value, modelo="ia-falsa", tempo_ms=1)

    monkeypatch.setattr("app.services.fila.processar_pdf", processar_falso)
    return controle


@pytest.fixture
def cliente(ia_falsa):
    """Aplicação no ar (com a fila rodando), banco vazio e IA falsa."""
    limpar_banco()
    with TestClient(app) as cliente_http:
        yield cliente_http
        ia_falsa.liberar.set()  # não deixa a fila presa ao encerrar


def aguardar(cliente, nota_id: int, *status: str, limite_segundos: float = 10) -> dict:
    """Consulta a nota até ela chegar a um dos status esperados."""
    fim = time.monotonic() + limite_segundos
    while True:
        nota = cliente.get(f"/api/notas/{nota_id}").json()
        if nota["status"] in status:
            return nota
        if time.monotonic() > fim:
            raise AssertionError(f"A nota {nota_id} ficou em '{nota['status']}'; esperado: {status}")
        time.sleep(0.02)
