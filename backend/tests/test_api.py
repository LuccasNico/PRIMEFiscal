from fastapi.testclient import TestClient

from app.main import app


def test_saude():
    with TestClient(app) as cliente:
        resposta = cliente.get("/api/saude")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "ok"


def test_rejeita_arquivo_que_nao_e_pdf():
    with TestClient(app) as cliente:
        resposta = cliente.post("/api/notas", files={"arquivo": ("nota.txt", b"nao sou um pdf", "text/plain")})
    assert resposta.status_code == 415


def test_nota_inexistente():
    with TestClient(app) as cliente:
        resposta = cliente.get("/api/notas/9999")
    assert resposta.status_code == 404
