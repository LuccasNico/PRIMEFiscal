"""Validação fiscal determinística dos dados extraídos pela IA.

As regras não dependem de IA: servem para detectar erros de leitura ou
"alucinações" do modelo e gerar uma pontuação de confiança para a nota.
"""

import re
from datetime import date

from app.schemas.nota_fiscal import NotaFiscalExtraida, ResultadoValidacao, TipoDocumento


def _so_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor)


def cnpj_valido(cnpj: str) -> bool:
    """Valida o CNPJ numérico e o alfanumérico (Receita Federal, a partir de jul/2026).

    No alfanumérico, cada caractere vale ord(c) - 48 no cálculo do módulo 11;
    os dois dígitos verificadores continuam numéricos.
    """
    cnpj = re.sub(r"[^0-9A-Za-z]", "", cnpj).upper()
    if not re.fullmatch(r"[0-9A-Z]{12}[0-9]{2}", cnpj) or len(set(cnpj)) == 1:
        return False

    def digito(base: str) -> int:
        pesos = [2, 3, 4, 5, 6, 7, 8, 9]
        soma = sum((ord(c) - 48) * pesos[i % 8] for i, c in enumerate(reversed(base)))
        resto = soma % 11
        return 0 if resto < 2 else 11 - resto

    dv1 = digito(cnpj[:12])
    dv2 = digito(cnpj[:12] + str(dv1))
    return cnpj[12:] == f"{dv1}{dv2}"


def cpf_valido(cpf: str) -> bool:
    cpf = _so_digitos(cpf)
    if len(cpf) != 11 or len(set(cpf)) == 1:
        return False
    for posicao in (9, 10):
        soma = sum(int(cpf[i]) * (posicao + 1 - i) for i in range(posicao))
        dv = (soma * 10) % 11 % 10
        if dv != int(cpf[posicao]):
            return False
    return True


def chave_acesso_valida(chave: str) -> bool:
    """Chave de 44 dígitos da NF-e/NFC-e; o último é o DV (módulo 11, pesos 2 a 9)."""
    chave = _so_digitos(chave)
    if len(chave) != 44:
        return False
    pesos = [2, 3, 4, 5, 6, 7, 8, 9]
    soma = sum(int(c) * pesos[i % 8] for i, c in enumerate(reversed(chave[:43])))
    resto = soma % 11
    dv = 0 if resto < 2 else 11 - resto
    return dv == int(chave[43])


def data_valida(valor: str) -> bool:
    try:
        return date.fromisoformat(valor) <= date.today()
    except ValueError:
        return False


def _proximo(a: float, b: float, tolerancia_relativa: float = 0.005, minimo: float = 0.05) -> bool:
    return abs(a - b) <= max(minimo, abs(b) * tolerancia_relativa)


def validar_nota(nota: NotaFiscalExtraida) -> ResultadoValidacao:
    verificacoes: dict[str, bool] = {}
    erros: list[str] = []

    def verificar(nome: str, ok: bool, mensagem: str) -> None:
        verificacoes[nome] = ok
        if not ok:
            erros.append(mensagem)

    verificar("tipo_identificado", nota.tipo_documento != TipoDocumento.DESCONHECIDO,
              "Tipo de documento não identificado.")

    if nota.emitente.cnpj:
        verificar("cnpj_emitente", cnpj_valido(nota.emitente.cnpj),
                  f"CNPJ do emitente inválido: {nota.emitente.cnpj}")
    elif nota.emitente.cpf:
        verificar("cpf_emitente", cpf_valido(nota.emitente.cpf),
                  f"CPF do emitente inválido: {nota.emitente.cpf}")
    else:
        verificar("documento_emitente", False, "CNPJ/CPF do emitente não encontrado.")

    if nota.destinatario and nota.destinatario.cnpj:
        verificar("cnpj_destinatario", cnpj_valido(nota.destinatario.cnpj),
                  f"CNPJ do destinatário inválido: {nota.destinatario.cnpj}")
    elif nota.destinatario and nota.destinatario.cpf:
        verificar("cpf_destinatario", cpf_valido(nota.destinatario.cpf),
                  f"CPF do destinatário inválido: {nota.destinatario.cpf}")

    # NF-e e NFC-e sempre têm chave de acesso; NFS-e municipais geralmente não
    if nota.tipo_documento in (TipoDocumento.NFE, TipoDocumento.NFCE) or nota.chave_acesso:
        verificar("chave_acesso", bool(nota.chave_acesso) and chave_acesso_valida(nota.chave_acesso),
                  f"Chave de acesso ausente ou inválida: {nota.chave_acesso}")

    if nota.data_emissao:
        verificar("data_emissao", data_valida(nota.data_emissao),
                  f"Data de emissão inválida: {nota.data_emissao}")

    total_declarado = nota.valor_total_produtos or nota.valor_total_nota or 0
    if total_declarado > 0:
        verificar("itens_extraidos", bool(nota.itens),
                  "Nenhum item foi extraído, embora a nota tenha valor total.")

    itens_inconsistentes = [
        i + 1 for i, item in enumerate(nota.itens)
        if None not in (item.quantidade, item.valor_unitario, item.valor_total)
        and not _proximo(item.quantidade * item.valor_unitario, item.valor_total)
    ]
    if nota.itens:
        verificar("itens_qtd_x_valor", not itens_inconsistentes,
                  f"Quantidade × valor unitário não confere nos itens: {itens_inconsistentes}")

    totais_itens = [item.valor_total for item in nota.itens if item.valor_total is not None]
    if nota.valor_total_produtos is not None and totais_itens:
        soma = round(sum(totais_itens), 2)
        verificar("soma_itens", _proximo(soma, nota.valor_total_produtos),
                  f"Soma dos itens ({soma}) difere do total de produtos ({nota.valor_total_produtos}).")

    if nota.valor_total_nota is None:
        verificar("valor_total_nota", False, "Valor total da nota não encontrado.")

    pontuacao = sum(verificacoes.values()) / len(verificacoes) if verificacoes else 0.0
    return ResultadoValidacao(
        valido=not erros,
        pontuacao=round(pontuacao, 3),
        verificacoes=verificacoes,
        erros=erros,
    )
