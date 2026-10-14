from app.schemas.nota_fiscal import (
    LIMITE_INFORMACOES_COMPLEMENTARES,
    Impostos,
    Item,
    NotaFiscalExtraida,
    Participante,
    TipoDocumento,
)
from app.services.validacao import chave_acesso_valida, cnpj_valido, cpf_valido, validar_nota

# Pesos da chave de acesso da esquerda para a direita, conforme o Manual de Orientação do Contribuinte
PESOS_CHAVE = [int(p) for p in "4329876543298765432987654329876543298765432"]


def gerar_chave(base43: str) -> str:
    resto = sum(int(d) * p for d, p in zip(base43, PESOS_CHAVE)) % 11
    return base43 + str(0 if resto < 2 else 11 - resto)


CHAVE_VALIDA = gerar_chave("3526100000000000000155001000000123100000012")


def test_cnpj_numerico():
    assert cnpj_valido("11.222.333/0001-81")
    assert not cnpj_valido("11.222.333/0001-80")
    assert not cnpj_valido("11111111111111")


def test_cnpj_alfanumerico():
    # Exemplo publicado pela Receita Federal para o CNPJ alfanumérico
    assert cnpj_valido("12.ABC.345/01DE-35")
    assert not cnpj_valido("12.ABC.345/01DE-36")


def test_cpf():
    assert cpf_valido("529.982.247-25")
    assert not cpf_valido("529.982.247-24")
    assert not cpf_valido("000.000.000-00")


def test_chave_acesso():
    assert chave_acesso_valida(CHAVE_VALIDA)
    errada = CHAVE_VALIDA[:-1] + str((int(CHAVE_VALIDA[-1]) + 1) % 10)
    assert not chave_acesso_valida(errada)
    assert not chave_acesso_valida("123")


def nota_exemplo(**alteracoes) -> NotaFiscalExtraida:
    dados = dict(
        tipo_documento=TipoDocumento.NFE,
        chave_acesso=CHAVE_VALIDA,
        numero="123",
        serie="1",
        data_emissao="2026-09-30",
        emitente=Participante(razao_social="Empresa Exemplo LTDA", cnpj="11222333000181", uf="SP"),
        itens=[
            Item(descricao="Produto A", quantidade=2, valor_unitario=10.5, valor_total=21.0),
            Item(descricao="Produto B", quantidade=1, valor_unitario=4.0, valor_total=4.0),
        ],
        impostos=Impostos(valor_icms=4.5),
        valor_total_produtos=25.0,
        valor_total_nota=25.0,
    )
    dados.update(alteracoes)
    return NotaFiscalExtraida(**dados)


def test_nota_valida():
    resultado = validar_nota(nota_exemplo())
    assert resultado.valido, resultado.erros
    assert resultado.pontuacao == 1.0


def test_soma_dos_itens_divergente():
    resultado = validar_nota(nota_exemplo(valor_total_produtos=30.0))
    assert not resultado.valido
    assert resultado.verificacoes["soma_itens"] is False


def test_item_com_quantidade_x_valor_errado():
    itens = [Item(descricao="Produto A", quantidade=3, valor_unitario=10.5, valor_total=21.0)]
    resultado = validar_nota(nota_exemplo(itens=itens, valor_total_produtos=21.0))
    assert resultado.verificacoes["itens_qtd_x_valor"] is False


def test_nota_com_valor_mas_sem_itens():
    resultado = validar_nota(nota_exemplo(itens=[]))
    assert not resultado.valido
    assert resultado.verificacoes["itens_extraidos"] is False


def test_informacoes_complementares_sao_limitadas():
    nota = nota_exemplo(informacoes_complementares="x" * 5000)
    assert len(nota.informacoes_complementares) == LIMITE_INFORMACOES_COMPLEMENTARES


def test_nfse_sem_chave_de_acesso_e_aceita():
    resultado = validar_nota(nota_exemplo(tipo_documento=TipoDocumento.NFSE, chave_acesso=None))
    assert "chave_acesso" not in resultado.verificacoes
    assert resultado.valido
