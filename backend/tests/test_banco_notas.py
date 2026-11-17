import copy

import pytest
from sqlalchemy import func, select

from app.config import url_do_banco
from app.db import ItemRegistro, NotaSalvaRegistro, ParticipanteRegistro, SessaoLocal
from app.services.ia import ErroExtracao
from tests.conftest import NOTA_EXTRAIDA, aguardar
from tests.test_api import pdf

CHAVE = "35260811222333000181550010000001231000001234"


def nota_com(**campos) -> dict:
    dados = copy.deepcopy(NOTA_EXTRAIDA)
    dados.update(campos)
    return dados


def preparar(cliente, dados: dict | None = None, nome: str = "nota.pdf") -> dict:
    """Envia uma nota, espera a extração (IA falsa) e, se `dados` for informado, aplica-os como correção."""
    [criada] = cliente.post("/api/notas", files=[pdf(nome)]).json()
    nota = aguardar(cliente, criada["id"], "processada", "revisar")
    if dados is not None:
        resposta = cliente.put(f"/api/notas/{nota['id']}", json=dados)
        assert resposta.status_code == 200, resposta.text
        nota = resposta.json()
    return nota


def salvar(cliente, nota_id: int):
    return cliente.post(f"/api/notas/{nota_id}/salvar")


def contar(modelo) -> int:
    with SessaoLocal() as sessao:
        return sessao.scalar(select(func.count()).select_from(modelo))


def test_salva_o_json_e_os_dados_em_tabelas(cliente):
    dados = nota_com(
        tipo_documento="NF-e",
        chave_acesso=" ".join(CHAVE[i : i + 4] for i in range(0, 44, 4)),
        data_emissao="2026-08-11",
        emitente={"razao_social": "Empresa Exemplo LTDA", "cnpj": "11.222.333/0001-81", "uf": "sp", "cep": "11700-000"},
        destinatario={"razao_social": "Fulano de Tal", "cpf": "529.982.247-25"},
        itens=[
            {"descricao": "Produto A", "ncm": "8471.30.12", "cfop": "5.102", "quantidade": 2, "valor_unitario": 10.5, "valor_total": 21.0},
            {"descricao": "Produto B", "quantidade": 1, "valor_unitario": 5, "valor_total": 5},
        ],
        impostos={"valor_icms": 3.78},
        pagamentos=[{"forma": "PIX", "valor": 26.0}],
        valor_total_produtos=26.0,
        valor_total_nota=26.0,
    )
    nota = preparar(cliente, dados)
    assert nota["no_banco"] is None

    resposta = salvar(cliente, nota["id"])
    assert resposta.status_code == 200, resposta.text
    no_banco = resposta.json()["no_banco"]
    assert no_banco["em_dia"] is True

    salva = cliente.get(f"/api/banco/notas/{no_banco['id']}").json()
    assert salva["dados"] == nota["dados"]  # o JSON extraído é guardado como está
    assert salva["processamento_id"] == nota["id"]
    assert salva["chave_acesso"] == CHAVE
    assert salva["data_emissao"] == "2026-08-11"
    assert salva["emitente_documento"] == "11222333000181"
    assert salva["valor_total_nota"] == 26.0

    with SessaoLocal() as sessao:
        gravada = sessao.get(NotaSalvaRegistro, no_banco["id"])
        assert gravada.valor_icms == 3.78
        assert [(i.numero_item, i.descricao, i.ncm, i.cfop) for i in gravada.itens] == [
            (1, "Produto A", "84713012", "5102"),
            (2, "Produto B", None, None),
        ]
        assert (gravada.itens[0].quantidade, gravada.itens[0].valor_unitario) == (2, 10.5)
        assert [(p.forma, p.valor) for p in gravada.pagamentos] == [("PIX", 26.0)]
        assert (gravada.emitente.uf, gravada.emitente.cep) == ("SP", "11700000")
        assert gravada.destinatario.cpf == "52998224725"


def test_salvar_de_novo_atualiza_a_mesma_nota(cliente):
    nota = preparar(cliente)
    primeira = salvar(cliente, nota["id"]).json()["no_banco"]

    corrigida = nota_com(
        itens=[
            {"descricao": "Serviço A", "quantidade": 1, "valor_unitario": 10, "valor_total": 10},
            {"descricao": "Serviço B", "quantidade": 1, "valor_unitario": 11, "valor_total": 11},
        ]
    )
    nota = cliente.put(f"/api/notas/{nota['id']}", json=corrigida).json()
    assert nota["no_banco"]["em_dia"] is False  # corrigida depois de salva

    segunda = salvar(cliente, nota["id"]).json()["no_banco"]
    assert segunda["id"] == primeira["id"]
    assert segunda["salva_em"] == primeira["salva_em"]
    assert segunda["em_dia"] is True
    assert contar(NotaSalvaRegistro) == 1
    assert contar(ItemRegistro) == 2


def test_participante_e_reaproveitado_pelo_documento(cliente):
    a = preparar(cliente, nota_com(numero="1", emitente={"razao_social": "Nome Antigo", "cnpj": "11222333000181"}))
    # Emitente e destinatário com o mesmo CNPJ (ex.: transferência) também viram um participante só
    b = preparar(
        cliente,
        nota_com(
            numero="2",
            emitente={"razao_social": "Nome Novo", "cnpj": "11.222.333/0001-81"},
            destinatario={"cnpj": "11222333000181"},
        ),
    )
    assert salvar(cliente, a["id"]).status_code == 200
    assert salvar(cliente, b["id"]).status_code == 200

    assert contar(ParticipanteRegistro) == 1
    lista = cliente.get("/api/banco/notas?documento_emitente=11222333000181").json()
    assert [nota["numero"] for nota in lista] == ["2", "1"]
    assert {nota["emitente_nome"] for nota in lista} == {"Nome Novo"}


def test_filtros_do_banco(cliente):
    a = preparar(cliente, nota_com(tipo_documento="NF-e", numero="1", data_emissao="2026-01-10"))
    b = preparar(cliente, nota_com(tipo_documento="NFS-e", numero="2", data_emissao="2026-03-05"))
    for nota in (a, b):
        assert salvar(cliente, nota["id"]).status_code == 200

    def numeros(consulta: str) -> list[str]:
        return [nota["numero"] for nota in cliente.get(f"/api/banco/notas{consulta}").json()]

    assert numeros("") == ["2", "1"]
    assert numeros("?tipo_documento=NF-e") == ["1"]
    assert numeros("?emitida_de=2026-02-01") == ["2"]
    assert numeros("?emitida_ate=2026-02-01") == ["1"]
    assert numeros("?documento_emitente=00000000000000") == []


def test_a_mesma_chave_nao_entra_duas_vezes(cliente):
    dados = nota_com(chave_acesso=CHAVE)
    a = preparar(cliente, dados, "a.pdf")
    b = preparar(cliente, dados, "b.pdf")

    assert salvar(cliente, a["id"]).status_code == 200
    resposta = salvar(cliente, b["id"])
    assert resposta.status_code == 409
    assert "a.pdf" in resposta.json()["detail"]
    assert contar(NotaSalvaRegistro) == 1


def test_so_salva_notas_com_extracao_concluida(cliente, ia_falsa):
    assert salvar(cliente, 9999).status_code == 404

    ia_falsa.liberar.clear()
    [criada] = cliente.post("/api/notas", files=[pdf()]).json()
    assert salvar(cliente, criada["id"]).status_code == 409  # ainda na fila

    ia_falsa.erros.append(ErroExtracao("A IA não respondeu."))
    ia_falsa.liberar.set()
    aguardar(cliente, criada["id"], "erro")
    assert salvar(cliente, criada["id"]).status_code == 409
    assert contar(NotaSalvaRegistro) == 0


def test_excluir_da_area_de_trabalho_mantem_a_nota_no_banco(cliente):
    nota = preparar(cliente)
    id_no_banco = salvar(cliente, nota["id"]).json()["no_banco"]["id"]

    assert cliente.delete(f"/api/notas/{nota['id']}").status_code == 204

    salva = cliente.get(f"/api/banco/notas/{id_no_banco}").json()
    assert salva["processamento_id"] is None
    assert salva["dados"]["itens"][0]["descricao"] == "Serviço A"


def test_remover_do_banco(cliente):
    nota = preparar(cliente)
    id_no_banco = salvar(cliente, nota["id"]).json()["no_banco"]["id"]

    assert cliente.delete(f"/api/banco/notas/{id_no_banco}").status_code == 204
    assert cliente.get(f"/api/banco/notas/{id_no_banco}").status_code == 404
    assert cliente.delete(f"/api/banco/notas/{id_no_banco}").status_code == 404
    assert contar(ItemRegistro) == 0  # os itens saem junto (ON DELETE CASCADE)
    assert contar(ParticipanteRegistro) == 1  # a empresa continua cadastrada
    assert cliente.get(f"/api/notas/{nota['id']}").json()["no_banco"] is None


def test_valor_que_nao_cabe_no_banco_e_recusado_sem_gravar_nada(cliente):
    nota = preparar(cliente, nota_com(emitente={"razao_social": "Empresa", "cnpj": "11222333000181", "uf": "São Paulo"}))

    resposta = salvar(cliente, nota["id"])
    assert resposta.status_code == 422
    assert "Emitente" in resposta.json()["detail"] and "'uf'" in resposta.json()["detail"]
    assert contar(NotaSalvaRegistro) == 0
    assert contar(ParticipanteRegistro) == 0


@pytest.mark.parametrize(
    ("informada", "usada"),
    [
        ("postgres://u:s@host/db", "postgresql+psycopg://u:s@host/db"),
        ("postgresql://u:s@host/db?sslmode=require", "postgresql+psycopg://u:s@host/db?sslmode=require"),
        ("postgresql+psycopg://u:s@host/db", "postgresql+psycopg://u:s@host/db"),
        ("sqlite:///outro.db", "sqlite:///outro.db"),
    ],
)
def test_url_do_banco_na_nuvem(informada, usada):
    assert url_do_banco(informada) == usada


def test_sem_url_usa_sqlite_local():
    assert url_do_banco("").startswith("sqlite:///") and url_do_banco("").endswith("/primefiscal.db")
