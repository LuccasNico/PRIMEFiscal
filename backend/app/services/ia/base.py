"""Partes comuns a todos os provedores de IA: o prompt, o schema da resposta e a leitura dela."""

import base64
import io
import json
from typing import NamedTuple

import pdfplumber
from pydantic import ValidationError

from app.schemas.nota_fiscal import LIMITE_INFORMACOES_COMPLEMENTARES, Metadados, NotaFiscalExtraida

PROMPT_SISTEMA = """Você é um especialista em documentos fiscais brasileiros: NF-e (DANFE), NFC-e e NFS-e.
Sua tarefa é extrair os dados do documento recebido exatamente como aparecem nele.

Regras gerais:
- Identifique o tipo do documento (NF-e, NFC-e ou NFS-e). Use "desconhecido" se não for uma nota fiscal.
- Converta números do formato brasileiro para decimal com ponto, sem símbolo de moeda: "1.234,56" -> 1234.56; "5,00" -> 5.0.
- Converta datas para AAAA-MM-DD: "11/08/2026" -> "2026-08-11".
- CNPJ, CPF, CEP e chave de acesso sem pontuação nem espaços.
- Se um campo não existir no documento ou estiver ilegível, use null. Nunca invente nem calcule valores que não estejam no documento.
- Coloque cada informação no seu campo próprio. Nunca copie trechos grandes do documento para nenhum campo.

Formato do texto: quando o documento tiver quadros (como no DANFE), eles aparecem como
"Rótulo / valor", com as células de uma mesma linha separadas por "||". O valor é o que vem depois da barra.
Se uma célula tiver dois rótulos e dois valores ("Rótulo A Rótulo B / 1,00 2,00"), associe-os na mesma ordem.

Onde encontrar cada dado:
- Número e série: "Nº", "Número", "Série" (na NFC-e aparecem como "Número: 2 Série: 1").
- Data de emissão: "Emissão" ou "Data de emissão".
- Chave de acesso: 44 dígitos, geralmente em grupos de 4 separados por espaço; junte todos os dígitos.
- Emitente: quem vende ou presta o serviço (topo do documento). Destinatário: o comprador, "Consumidor" na NFC-e ou "Tomador" na NFS-e.
- Endereços vão em "endereco", "cep", "municipio" e "uf" do participante correspondente.
- Itens: cada produto ou serviço vira um elemento de "itens". Na NFC-e, um item costuma ocupar duas linhas: "CÓDIGO DESCRIÇÃO" e, abaixo, "QTDE UN x VALOR UNITÁRIO = VALOR TOTAL". Na NFS-e, cada serviço discriminado é um item.
- Impostos e totais da NF-e ficam no quadro "Cálculo do imposto": base de cálculo do ICMS, valor do ICMS,
  ICMS ST, valor do IPI, valor total dos produtos, frete, desconto e valor total da nota. Na NFS-e, procure
  o valor do ISS/ISSQN. O valor aproximado dos tributos (Lei 12.741/2012) aparece como "Total aproximado de
  tributos" ou "Tributos Totais Incidentes".
- Nos itens, não confunda o preço unitário e o total do item com a base de cálculo ou o valor dos impostos do item.
- Formas de pagamento e seus valores vão em "pagamentos".
- "informacoes_complementares" recebe apenas o quadro de informações complementares, em poucas linhas."""

INSTRUCAO_USUARIO = "Extraia os dados desta nota fiscal."

RESOLUCAO_DAS_IMAGENS_DPI = 150

Extracao = tuple[NotaFiscalExtraida, Metadados]


class ErroExtracao(Exception):
    """A extração falhou. A mensagem é mostrada ao usuário, então deve dizer o que aconteceu e como resolver."""


class Provedor(NamedTuple):
    """Descrição do provedor de IA em uso, mostrada na interface."""

    nome: str
    modelo: str
    pdf_exige_visao: bool  # na abordagem "pdf", o modelo precisa aceitar imagens


class Modelo(NamedTuple):
    """Um modelo que pode ser escolhido na interface."""

    id: str  # o nome usado na API, ex.: gemini-3.5-flash
    nome: str  # o nome para exibição, ex.: Gemini 3.5 Flash
    descricao: str = ""


def mensagem_com_texto(texto: str) -> str:
    return f"Texto extraído de uma nota fiscal em PDF:\n\n<documento>\n{texto}\n</documento>\n\n{INSTRUCAO_USUARIO}"


def _sem_referencias(schema: dict) -> dict:
    """Troca os $ref gerados pelo Pydantic pelas próprias definições, porque nem toda API entende $defs."""
    definicoes = schema.get("$defs", {})

    def resolver(no):
        if isinstance(no, dict):
            if "$ref" in no:
                return resolver(definicoes[no["$ref"].split("/")[-1]])
            return {chave: resolver(valor) for chave, valor in no.items() if chave != "$defs"}
        if isinstance(no, list):
            return [resolver(item) for item in no]
        return no

    return resolver(schema)


def _schema_da_nota() -> dict:
    schema = _sem_referencias(NotaFiscalExtraida.model_json_schema())
    # O limite do texto livre vai no próprio schema: quando a API restringe a geração a ele,
    # o modelo não consegue despejar o documento inteiro em informacoes_complementares
    campo = schema["properties"]["informacoes_complementares"]
    for opcao in campo.get("anyOf", [campo]):
        if opcao.get("type") == "string":
            opcao["maxLength"] = LIMITE_INFORMACOES_COMPLEMENTARES
    return schema


# JSON Schema da resposta, usado pelos provedores que recebem o schema na requisição
SCHEMA_NOTA = _schema_da_nota()

# Para APIs que não restringem a resposta a um schema: o formato é pedido no próprio prompt
INSTRUCAO_DE_FORMATO = (
    "Responda somente com um objeto JSON, sem nenhum texto antes ou depois, seguindo este JSON Schema:\n"
    + json.dumps(SCHEMA_NOTA, ensure_ascii=False)
)


def interpretar_resposta(texto: str | None, nome_provedor: str) -> NotaFiscalExtraida:
    """Converte o JSON devolvido pelo modelo na nota extraída."""
    texto = (texto or "").strip()
    # Sem restrição por schema, alguns modelos embrulham o JSON em um bloco Markdown
    if texto.startswith("```"):
        texto = texto.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return NotaFiscalExtraida.model_validate_json(texto)
    except ValidationError as e:
        raise ErroExtracao(
            f"{nome_provedor} devolveu dados fora do formato esperado ({e.error_count()} erro(s))."
        ) from e


def paginas_como_imagens(pdf_bytes: bytes) -> list[str]:
    """Cada página do PDF como PNG em base64, para modelos que leem imagens mas não leem PDF."""
    imagens = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for pagina in pdf.pages:
                buffer = io.BytesIO()
                pagina.to_image(resolution=RESOLUCAO_DAS_IMAGENS_DPI).original.save(buffer, format="PNG")
                imagens.append(base64.standard_b64encode(buffer.getvalue()).decode("ascii"))
    except Exception as e:
        # O pdfplumber/pdfminer lança exceções de vários tipos para arquivos corrompidos ou com senha
        raise ErroExtracao("Não foi possível ler o PDF (arquivo corrompido ou protegido por senha).") from e
    return imagens
