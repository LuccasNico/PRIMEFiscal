"""Escolha do modelo de IA na interface: a lista vem do provedor e o modelo escolhido segue com a nota."""

import pytest

from app.services import ia
from tests.conftest import aguardar
from tests.pdf_teste import pdf_com_texto

MODELOS = [ia.Modelo("modelo-novo", "Modelo Novo", "o mais recente"), ia.Modelo("modelo-antigo", "Modelo Antigo")]


@pytest.fixture
def provedor_com_escolha(monkeypatch):
    """O provedor dos testes (LM Studio) não permite escolher o modelo; aqui ele passa a permitir."""
    monkeypatch.setattr(ia, "permite_escolher_modelo", lambda: True)
    monkeypatch.setattr(ia, "listar_modelos", lambda: MODELOS)


def enviar(cliente, parametros: str = ""):
    arquivo = ("arquivos", ("nota.pdf", pdf_com_texto("nota"), "application/pdf"))
    return cliente.post(f"/api/notas?abordagem=texto{parametros}", files=[arquivo])


def test_lista_de_modelos(cliente, provedor_com_escolha):
    resposta = cliente.get("/api/modelos")
    assert resposta.status_code == 200
    # O padrão do provedor não está na lista, então o primeiro (o mais novo) é sugerido
    assert resposta.json() == {
        "padrao": "modelo-novo",
        "modelos": [
            {"id": "modelo-novo", "nome": "Modelo Novo", "descricao": "o mais recente"},
            {"id": "modelo-antigo", "nome": "Modelo Antigo", "descricao": ""},
        ],
    }


def test_modelo_escolhido_segue_com_a_nota(cliente, ia_falsa, provedor_com_escolha):
    [criada] = enviar(cliente, "&modelo=modelo-antigo").json()
    assert criada["modelo"] == "modelo-antigo"
    aguardar(cliente, criada["id"], "processada")

    # Sem modelo, o reprocessamento repete o anterior; com modelo, troca
    cliente.post(f"/api/notas/{criada['id']}/reprocessar")
    aguardar(cliente, criada["id"], "processada")
    cliente.post(f"/api/notas/{criada['id']}/reprocessar?modelo=modelo-novo")
    aguardar(cliente, criada["id"], "processada")

    assert ia_falsa.modelos == ["modelo-antigo", "modelo-antigo", "modelo-novo"]


def test_sem_modelo_usa_o_padrao_do_provedor(cliente, ia_falsa, provedor_com_escolha):
    [criada] = enviar(cliente).json()
    aguardar(cliente, criada["id"], "processada")
    assert criada["modelo"] is None
    assert ia_falsa.modelos == [None]


def test_modelo_fora_da_lista_e_recusado(cliente, provedor_com_escolha):
    resposta = enviar(cliente, "&modelo=modelo-caro-qualquer")
    assert resposta.status_code == 422
    assert "modelo-caro-qualquer" in resposta.json()["detail"]
    assert cliente.get("/api/notas").json() == []


def test_provedor_sem_escolha_de_modelo(cliente):
    assert cliente.get("/api/modelos").status_code == 400
    assert enviar(cliente, "&modelo=qualquer").status_code == 400
    assert enviar(cliente).status_code == 202


def test_falha_ao_consultar_os_modelos(cliente, monkeypatch, provedor_com_escolha):
    def falhar():
        raise ia.ErroExtracao("Não foi possível conectar ao serviço Google Gemini.")

    monkeypatch.setattr(ia, "listar_modelos", falhar)
    resposta = cliente.get("/api/modelos")
    assert resposta.status_code == 502
    assert "Google Gemini" in resposta.json()["detail"]
