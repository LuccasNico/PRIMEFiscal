"""Banco de notas: grava a nota conferida pelo usuário.

A nota da área de trabalho (fila) é copiada para o banco de notas em duas formas:

- o JSON extraído, inteiro, na coluna ``notas_salvas.dados``;
- os mesmos dados em tabelas relacionais (cabeçalho, participantes, itens e pagamentos),
  para consultas em SQL e integração com outros sistemas.

Salvar de novo a mesma nota atualiza a cópia já gravada em vez de criar outra.
"""

import re
from datetime import date

from sqlalchemy import Numeric, String, select
from sqlalchemy.orm import Session

from app.db import (
    Base,
    ItemRegistro,
    NotaFiscalRegistro,
    NotaSalvaRegistro,
    PagamentoRegistro,
    ParticipanteRegistro,
    agora,
)
from app.schemas.nota_fiscal import STATUS_QUE_PODEM_SER_SALVOS, NotaFiscalExtraida, Participante


class ErroAoSalvar(Exception):
    def __init__(self, mensagem: str, status_http: int = 422) -> None:
        super().__init__(mensagem)
        self.status_http = status_http


def _texto(valor: str | None) -> str | None:
    valor = (valor or "").strip()
    return valor or None


def _so_digitos(valor: str | None) -> str | None:
    return re.sub(r"\D", "", valor or "") or None


def _cnpj(valor: str | None) -> str | None:
    # O CNPJ alfanumérico (a partir de 2026) tem letras; só a pontuação é removida
    return re.sub(r"[^0-9A-Za-z]", "", valor or "").upper() or None


def _data(valor: str | None) -> date | None:
    """A IA devolve AAAA-MM-DD; se vier outra coisa, a coluna fica vazia (o texto original segue no JSON)."""
    try:
        return date.fromisoformat((valor or "")[:10])
    except ValueError:
        return None


def _conferir_limites(registro: Base, onde: str) -> None:
    """Confere se cada valor cabe na coluna antes de gravar.

    O PostgreSQL recusaria o valor de qualquer forma, mas com um erro genérico; o SQLite nem
    confere. Assim a mensagem é a mesma nos dois bancos e diz qual campo corrigir.
    """
    for coluna in registro.__table__.columns:
        valor = getattr(registro, coluna.key)
        if valor is None:
            continue
        tipo = coluna.type
        if isinstance(tipo, String) and tipo.length and len(valor) > tipo.length:
            raise ErroAoSalvar(
                f"{onde}: o campo '{coluna.name}' tem {len(valor)} caracteres e o banco aceita até {tipo.length}. "
                "Corrija ou reprocesse a nota antes de salvar."
            )
        if isinstance(tipo, Numeric) and tipo.precision and abs(valor) >= 10 ** (tipo.precision - (tipo.scale or 0)):
            raise ErroAoSalvar(f"{onde}: o valor {valor} do campo '{coluna.name}' é grande demais para o banco.")


def _participante(sessao: Session, participante: Participante | None, onde: str) -> ParticipanteRegistro | None:
    """Encontra o participante pelo CNPJ ou CPF (e atualiza os dados dele) ou cria um novo."""
    if participante is None:
        return None
    campos = {
        "cnpj": _cnpj(participante.cnpj),
        "cpf": _so_digitos(participante.cpf),
        "razao_social": _texto(participante.razao_social),
        "inscricao_estadual": _texto(participante.inscricao_estadual),
        "inscricao_municipal": _texto(participante.inscricao_municipal),
        "endereco": _texto(participante.endereco),
        "cep": _so_digitos(participante.cep),
        "municipio": _texto(participante.municipio),
        "uf": _texto(participante.uf.upper() if participante.uf else None),
    }
    if not any(campos.values()):
        return None

    registro = None
    if campos["cnpj"]:
        registro = sessao.scalar(select(ParticipanteRegistro).where(ParticipanteRegistro.cnpj == campos["cnpj"]))
    if registro is None and campos["cpf"]:
        registro = sessao.scalar(select(ParticipanteRegistro).where(ParticipanteRegistro.cpf == campos["cpf"]))
    if registro is None:
        registro = ParticipanteRegistro()
        sessao.add(registro)

    # Os dados mais recentes prevalecem (ex.: mudança de endereço), mas um campo vazio não apaga o que já existe
    for nome, valor in campos.items():
        if valor is not None:
            setattr(registro, nome, valor)
    _conferir_limites(registro, onde)
    # Grava já, para o destinatário encontrar o emitente quando os dois têm o mesmo documento
    sessao.flush()
    return registro


def salvar(sessao: Session, registro: NotaFiscalRegistro) -> NotaSalvaRegistro:
    """Grava a nota no banco de notas (ou atualiza a cópia já gravada). Quem chama faz o commit."""
    if registro.status not in {status.value for status in STATUS_QUE_PODEM_SER_SALVOS} or not registro.dados:
        raise ErroAoSalvar("Só é possível salvar notas cuja extração terminou com sucesso.", 409)

    dados = NotaFiscalExtraida.model_validate(registro.dados)
    chave = _so_digitos(dados.chave_acesso)
    nota = registro.nota_salva

    if chave:
        outra = sessao.scalar(select(NotaSalvaRegistro).where(NotaSalvaRegistro.chave_acesso == chave))
        if outra is not None and outra is not nota:
            origem = f" a partir de '{outra.arquivo}'" if outra.arquivo else ""
            raise ErroAoSalvar(
                f"Já existe no banco uma nota com esta chave de acesso (nº {outra.id}, salva{origem}).", 409
            )

    if nota is None:
        nota = NotaSalvaRegistro(processamento=registro, salva_em=agora())
        sessao.add(nota)
    else:
        # Os itens antigos saem antes de os novos entrarem, senão a numeração (nota, nº do item) se repetiria
        nota.itens.clear()
        nota.pagamentos.clear()
        sessao.flush()

    impostos = dados.impostos
    metadados = registro.metadados or {}
    validacao = registro.validacao or {}

    nota.tipo_documento = dados.tipo_documento.value
    nota.chave_acesso = chave
    nota.numero = _texto(dados.numero)
    nota.serie = _texto(dados.serie)
    nota.data_emissao = _data(dados.data_emissao)
    nota.valor_total_produtos = dados.valor_total_produtos
    nota.valor_desconto = dados.valor_desconto
    nota.valor_frete = dados.valor_frete
    nota.valor_total_nota = dados.valor_total_nota
    for nome in type(impostos).model_fields:
        setattr(nota, nome, getattr(impostos, nome))
    nota.informacoes_complementares = _texto(dados.informacoes_complementares)
    nota.arquivo = registro.arquivo
    nota.abordagem = metadados.get("abordagem") or registro.abordagem
    nota.provedor_ia = metadados.get("provedor")
    nota.modelo_ia = metadados.get("modelo")
    nota.validacao_valida = validacao.get("valido")
    nota.validacao_pontuacao = validacao.get("pontuacao")
    nota.dados = registro.dados
    nota.validacao = registro.validacao
    nota.atualizada_em = agora()
    _conferir_limites(nota, "Nota")

    nota.emitente = _participante(sessao, dados.emitente, "Emitente")
    nota.destinatario = _participante(sessao, dados.destinatario, "Destinatário")

    for numero, item in enumerate(dados.itens, start=1):
        novo = ItemRegistro(
            numero_item=numero,
            codigo=_texto(item.codigo),
            descricao=_texto(item.descricao) or "(sem descrição)",
            ncm=_so_digitos(item.ncm),
            cfop=_so_digitos(item.cfop),
            unidade=_texto(item.unidade),
            quantidade=item.quantidade,
            valor_unitario=item.valor_unitario,
            valor_total=item.valor_total,
        )
        _conferir_limites(novo, f"Item {numero}")
        nota.itens.append(novo)

    for numero, pagamento in enumerate(dados.pagamentos, start=1):
        novo = PagamentoRegistro(forma=_texto(pagamento.forma) or "(não informada)", valor=pagamento.valor)
        _conferir_limites(novo, f"Pagamento {numero}")
        nota.pagamentos.append(novo)

    sessao.flush()
    return nota
