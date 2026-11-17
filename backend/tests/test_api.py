from datetime import datetime

from sqlalchemy import create_engine, inspect, text

from app.db import NotaFiscalRegistro, adicionar_colunas_novas
from tests.pdf_teste import pdf_com_texto


def pdf(nome: str = "nota.pdf", conteudo: bytes | None = None):
    return ("arquivos", (nome, conteudo or pdf_com_texto(nome), "application/pdf"))


def test_saude(cliente):
    resposta = cliente.get("/api/saude")
    assert resposta.status_code == 200
    assert resposta.json() == {
        "status": "ok",
        "provedor": "lmstudio",
        "nome_provedor": "LM Studio",
        "modelo": "primeiro modelo disponível",
        "escolhe_modelo": False,
        "pdf_exige_visao": True,
        "exige_senha": False,
        "tamanho_maximo_mb": 1,
        "maximo_de_arquivos_por_envio": 50,
    }


def test_nota_inexistente(cliente):
    assert cliente.get("/api/notas/9999").status_code == 404
    assert cliente.get("/api/notas/9999/pdf").status_code == 404
    assert cliente.delete("/api/notas/9999").status_code == 404
    assert cliente.post("/api/notas/9999/reprocessar").status_code == 404


def test_rejeita_arquivo_que_nao_e_pdf(cliente):
    resposta = cliente.post("/api/notas", files=[("arquivos", ("nota.txt", b"nao sou um pdf", "text/plain"))])
    assert resposta.status_code == 415
    assert "nota.txt" in resposta.json()["detail"]


def test_rejeita_pdf_acima_do_tamanho_maximo(cliente):
    grande = b"%PDF-1.4\n" + b"0" * (1024 * 1024)  # o limite nos testes é 1 MB
    resposta = cliente.post("/api/notas", files=[pdf("grande.pdf", grande)])
    assert resposta.status_code == 413


def test_envio_com_um_arquivo_invalido_nao_cria_nenhuma_nota(cliente):
    arquivos = [pdf("boa.pdf"), ("arquivos", ("ruim.pdf", b"conteudo qualquer", "application/pdf"))]
    assert cliente.post("/api/notas", files=arquivos).status_code == 415
    assert cliente.get("/api/notas").json() == []


def test_rejeita_arquivos_demais_em_um_envio(cliente):
    assert cliente.post("/api/notas", files=[pdf(f"{i}.pdf") for i in range(51)]).status_code == 413


def test_filtros_da_listagem(cliente, ia_falsa):
    ia_falsa.liberar.clear()
    lote_a = cliente.post("/api/notas", files=[pdf("a.pdf")]).json()
    lote_b = cliente.post("/api/notas", files=[pdf("b.pdf"), pdf("c.pdf")]).json()

    do_lote_b = cliente.get(f"/api/notas?lote_id={lote_b[0]['lote_id']}").json()
    assert sorted(nota["arquivo"] for nota in do_lote_b) == ["b.pdf", "c.pdf"]
    assert lote_a[0]["lote_id"] != lote_b[0]["lote_id"]

    pendentes = cliente.get("/api/notas?status=pendente").json()
    assert all(nota["status"] == "pendente" for nota in pendentes)
    assert cliente.get("/api/notas?status=inexistente").status_code == 422


def test_datas_saem_com_fuso_horario(cliente):
    [criada] = cliente.post("/api/notas", files=[pdf()]).json()
    nota = cliente.get(f"/api/notas/{criada['id']}").json()
    assert datetime.fromisoformat(nota["criado_em"]).tzinfo is not None
    assert datetime.fromisoformat(nota["enfileirado_em"]).tzinfo is not None


def test_banco_de_versao_anterior_recebe_as_colunas_novas(tmp_path):
    motor = create_engine(f"sqlite:///{tmp_path / 'antigo.db'}")
    with motor.begin() as conexao:
        conexao.execute(
            text(
                "CREATE TABLE notas_fiscais (id INTEGER PRIMARY KEY, arquivo VARCHAR(255), status VARCHAR(20), "
                "lote_id VARCHAR(36), tipo_documento VARCHAR(20), criado_em DATETIME, dados JSON, "
                "validacao JSON, metadados JSON, erro TEXT)"
            )
        )
        conexao.execute(text("INSERT INTO notas_fiscais (arquivo, status) VALUES ('antiga.pdf', 'processada')"))

    adicionar_colunas_novas(motor)
    adicionar_colunas_novas(motor)  # rodar de novo não pode dar erro

    colunas = {coluna["name"] for coluna in inspect(motor).get_columns("notas_fiscais")}
    assert colunas == {coluna.name for coluna in NotaFiscalRegistro.__table__.columns}
    with motor.connect() as conexao:
        assert conexao.execute(text("SELECT arquivo, abordagem FROM notas_fiscais")).one() == ("antiga.pdf", None)
