from fastapi.testclient import TestClient

from app import armazenamento
from app.db import NotaFiscalRegistro, SessaoLocal, agora
from app.main import app
from app.services.ia.base import ErroExtracao
from app.services.processamento import Abordagem
from tests.conftest import aguardar, limpar_banco
from tests.pdf_teste import pdf_com_texto

CONCLUIDA = ("processada", "revisar")


def enviar(cliente, *nomes: str, abordagem: str = "texto"):
    arquivos = [("arquivos", (nome, pdf_com_texto(nome), "application/pdf")) for nome in nomes]
    return cliente.post(f"/api/notas?abordagem={abordagem}", files=arquivos)


def test_nota_enviada_entra_na_fila_e_e_processada(cliente):
    resposta = enviar(cliente, "nota.pdf")
    assert resposta.status_code == 202
    [criada] = resposta.json()
    assert criada["status"] in ("pendente", "processando")
    assert criada["tem_pdf"] is True
    assert criada["lote_id"]

    nota = aguardar(cliente, criada["id"], *CONCLUIDA)
    assert nota["status"] == "processada"
    assert nota["dados"]["numero"] == "123"
    assert nota["validacao"]["valido"] is True
    assert nota["metadados"]["abordagem"] == "texto"
    assert nota["erro"] is None


def test_notas_sao_processadas_uma_por_vez_na_ordem_de_envio(cliente, ia_falsa):
    ia_falsa.liberar.clear()
    criadas = enviar(cliente, "a.pdf", "b.pdf", "c.pdf").json()
    ids = [nota["id"] for nota in criadas]
    assert len({nota["lote_id"] for nota in criadas}) == 1

    aguardar(cliente, ids[0], "processando")
    situacao = {nota["id"]: nota["status"] for nota in cliente.get("/api/notas").json()}
    assert [situacao[i] for i in ids] == ["processando", "pendente", "pendente"]

    ia_falsa.liberar.set()
    for nota_id in ids:
        aguardar(cliente, nota_id, *CONCLUIDA)
    assert [pdf for pdf, _ in ia_falsa.chamadas] == [pdf_com_texto(n) for n in ("a.pdf", "b.pdf", "c.pdf")]


def test_remover_nota_da_fila(cliente, ia_falsa):
    ia_falsa.liberar.clear()
    primeira, segunda = (nota["id"] for nota in enviar(cliente, "a.pdf", "b.pdf").json())
    aguardar(cliente, primeira, "processando")

    assert cliente.delete(f"/api/notas/{segunda}").status_code == 204
    assert cliente.get(f"/api/notas/{segunda}").status_code == 404
    assert not armazenamento.tem_pdf(segunda)

    # A nota que está sendo processada não pode ser removida
    assert cliente.delete(f"/api/notas/{primeira}").status_code == 409

    ia_falsa.liberar.set()
    aguardar(cliente, primeira, *CONCLUIDA)
    assert len(ia_falsa.chamadas) == 1  # a nota removida nunca chegou à IA

    assert cliente.delete(f"/api/notas/{primeira}").status_code == 204
    assert not armazenamento.tem_pdf(primeira)


def test_esvaziar_a_fila(cliente, ia_falsa):
    ia_falsa.liberar.clear()
    ids = [nota["id"] for nota in enviar(cliente, "a.pdf", "b.pdf", "c.pdf").json()]
    aguardar(cliente, ids[0], "processando")

    assert cliente.delete("/api/notas?status=pendente").json() == {"removidas": 2}
    assert cliente.delete("/api/notas?status=processando").status_code == 409
    assert [nota["id"] for nota in cliente.get("/api/notas").json()] == [ids[0]]


def test_erro_na_extracao_e_reprocessamento(cliente, ia_falsa):
    ia_falsa.erros.append(ErroExtracao("LM Studio desligado"))
    [criada] = enviar(cliente, "nota.pdf", abordagem="texto").json()

    nota = aguardar(cliente, criada["id"], "erro")
    assert nota["erro"] == "LM Studio desligado"
    assert nota["dados"] is None

    resposta = cliente.post(f"/api/notas/{criada['id']}/reprocessar?abordagem=pdf")
    assert resposta.status_code == 202
    nota = aguardar(cliente, criada["id"], *CONCLUIDA)
    assert nota["erro"] is None
    assert nota["metadados"]["abordagem"] == "pdf"
    assert [abordagem for _, abordagem in ia_falsa.chamadas] == [Abordagem.TEXTO, Abordagem.PDF]


def test_reprocessar_nota_que_ja_esta_na_fila(cliente, ia_falsa):
    ia_falsa.liberar.clear()
    [criada] = enviar(cliente, "nota.pdf").json()
    assert cliente.post(f"/api/notas/{criada['id']}/reprocessar").status_code == 409


def test_erro_inesperado_em_uma_nota_nao_derruba_a_fila(cliente, ia_falsa):
    ia_falsa.erros.extend([RuntimeError("falha interna"), None])
    primeira, segunda = (nota["id"] for nota in enviar(cliente, "a.pdf", "b.pdf").json())

    assert "Erro inesperado" in aguardar(cliente, primeira, "erro")["erro"]
    assert aguardar(cliente, segunda, *CONCLUIDA)["status"] == "processada"


def test_pdf_original_fica_disponivel(cliente):
    [criada] = enviar(cliente, "nota.pdf").json()
    resposta = cliente.get(f"/api/notas/{criada['id']}/pdf")
    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == "application/pdf"
    assert resposta.content == pdf_com_texto("nota.pdf")


def test_corrigir_nota_manualmente(cliente, ia_falsa):
    [criada] = enviar(cliente, "nota.pdf").json()
    nota = aguardar(cliente, criada["id"], *CONCLUIDA)

    dados = {**nota["dados"], "numero": "999"}
    corrigida = cliente.put(f"/api/notas/{criada['id']}", json=dados).json()
    assert corrigida["status"] == "revisada"
    assert corrigida["dados"]["numero"] == "999"

    # Enquanto a nota está na fila, a correção manual é recusada
    ia_falsa.liberar.clear()
    cliente.post(f"/api/notas/{criada['id']}/reprocessar")
    assert cliente.put(f"/api/notas/{criada['id']}", json=dados).status_code == 409


def test_nota_interrompida_volta_para_a_fila_quando_o_servidor_reinicia(ia_falsa):
    limpar_banco()
    with SessaoLocal() as sessao:
        registro = NotaFiscalRegistro(
            arquivo="interrompida.pdf", status="processando", abordagem="texto", enfileirado_em=agora()
        )
        sessao.add(registro)
        sessao.commit()
        nota_id = registro.id
    armazenamento.salvar_pdf(nota_id, pdf_com_texto("interrompida.pdf"))

    with TestClient(app) as cliente:
        assert aguardar(cliente, nota_id, *CONCLUIDA)["status"] == "processada"


def test_nota_sem_pdf_guardado_termina_em_erro(ia_falsa):
    limpar_banco()
    with SessaoLocal() as sessao:
        registro = NotaFiscalRegistro(arquivo="antiga.pdf", status="pendente")
        sessao.add(registro)
        sessao.commit()
        nota_id = registro.id

    with TestClient(app) as cliente:
        nota = aguardar(cliente, nota_id, "erro")
        assert "não está mais disponível" in nota["erro"]
        assert nota["tem_pdf"] is False
        assert cliente.post(f"/api/notas/{nota_id}/reprocessar").status_code == 409
    assert ia_falsa.chamadas == []
