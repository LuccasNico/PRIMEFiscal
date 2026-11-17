"""Senha de acesso: as rotas da API exigem um token Bearer obtido com a senha."""

from types import SimpleNamespace

import pytest

from app import acesso
from app.main import app
from app.routers import acesso as rotas_de_acesso
from tests.conftest import aguardar
from tests.pdf_teste import pdf_com_texto

SENHA = "senha-de-teste"


@pytest.fixture
def com_senha(monkeypatch, cliente):
    monkeypatch.setattr(acesso, "configuracoes", SimpleNamespace(acesso_senha=SENHA, acesso_validade_horas=12))
    monkeypatch.setattr(rotas_de_acesso, "ESPERA_APOS_SENHA_ERRADA_SEGUNDOS", 0)
    return cliente


def entrar(cliente, senha: str = SENHA):
    return cliente.post("/api/acesso", json={"senha": senha})


def com_token(token: str) -> dict:
    return {"headers": {"Authorization": f"Bearer {token}"}}


def enviar(cliente, **parametros):
    arquivo = ("arquivos", ("nota.pdf", pdf_com_texto("nota"), "application/pdf"))
    return cliente.post("/api/notas?abordagem=texto", files=[arquivo], **parametros)


def test_sem_senha_configurada_a_ia_fica_liberada(cliente):
    assert cliente.get("/api/saude").json()["exige_senha"] is False
    assert enviar(cliente).status_code == 202
    assert entrar(cliente).status_code == 400


def test_toda_rota_da_api_exige_token_menos_saude_e_acesso():
    # Uma rota nova que esqueça a proteção faz este teste falhar. As rotas com exigir_acesso aparecem
    # no OpenAPI com o esquema de segurança Bearer (o cadeado no /docs).
    operacoes = [
        (metodo.upper(), caminho, bool(operacao.get("security")))
        for caminho, operacoes_do_caminho in app.openapi()["paths"].items()
        for metodo, operacao in operacoes_do_caminho.items()
    ]
    abertas = {(metodo, caminho) for metodo, caminho, protegida in operacoes if not protegida}
    assert abertas == {("GET", "/api/saude"), ("POST", "/api/acesso")}
    assert len(operacoes) > 10


def test_rotas_exigem_token(com_senha):
    cliente = com_senha
    assert cliente.get("/api/saude").json()["exige_senha"] is True

    sem_token = enviar(cliente)
    assert sem_token.status_code == 401
    assert sem_token.headers["www-authenticate"] == "Bearer"
    assert "senha de acesso" in sem_token.json()["detail"]
    for metodo, rota in [
        ("GET", "/api/notas"),
        ("GET", "/api/notas/1"),
        ("GET", "/api/notas/1/pdf"),
        ("PUT", "/api/notas/1"),
        ("DELETE", "/api/notas/1"),
        ("DELETE", "/api/notas?status=pendente"),
        ("POST", "/api/notas/1/reprocessar"),
        ("POST", "/api/notas/1/salvar"),
        ("GET", "/api/banco/notas"),
        ("GET", "/api/banco/notas/1"),
        ("DELETE", "/api/banco/notas/1"),
        ("GET", "/api/modelos"),
    ]:
        assert cliente.request(metodo, rota).status_code == 401, (metodo, rota)
    assert enviar(cliente, **com_token("4102444800.assinatura-falsa")).status_code == 401
    assert enviar(cliente, **com_token("nao-e-um-token")).status_code == 401


def test_senha_errada_nao_gera_token(com_senha):
    resposta = entrar(com_senha, "outra-senha")
    assert resposta.status_code == 401
    assert "token" not in resposta.json()


def test_token_obtido_com_a_senha_libera_a_ia(com_senha):
    cliente = com_senha
    resposta = entrar(cliente)
    assert resposta.status_code == 200
    token = resposta.json()["token"]

    [criada] = enviar(cliente, **com_token(token)).json()
    aguardar(cliente, criada["id"], "processada", **com_token(token))
    assert cliente.post(f"/api/notas/{criada['id']}/reprocessar", **com_token(token)).status_code == 202
    assert cliente.get(f"/api/notas/{criada['id']}/pdf", **com_token(token)).status_code == 200
    assert [nota["id"] for nota in cliente.get("/api/notas", **com_token(token)).json()] == [criada["id"]]


def test_token_vencido_adulterado_ou_de_outra_senha_e_recusado(com_senha):
    cliente = com_senha
    token = entrar(cliente).json()["token"]
    expira_em, assinatura = token.split(".")
    adulterado = f"{int(expira_em) + 3600}.{assinatura}"
    assert enviar(cliente, **com_token(adulterado)).status_code == 401

    acesso.configuracoes.acesso_validade_horas = -1
    vencido = entrar(cliente).json()["token"]
    resposta = enviar(cliente, **com_token(vencido))
    assert resposta.status_code == 401
    assert "expirou" in resposta.json()["detail"]

    acesso.configuracoes.acesso_validade_horas = 12
    acesso.configuracoes.acesso_senha = "senha-nova"
    assert enviar(cliente, **com_token(token)).status_code == 401
