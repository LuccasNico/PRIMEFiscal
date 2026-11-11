"""Extração do texto embutido no PDF (abordagem "texto" e baseline)."""

import io
import re

import pdfplumber


def extrair_texto(pdf_bytes: bytes) -> str:
    """Retorna o texto de todas as páginas, preservando aproximadamente o layout."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        paginas = [pagina.extract_text(layout=True) or "" for pagina in pdf.pages]
    return "\n\n".join(paginas).strip()


def compactar(texto: str) -> str:
    """Remove linhas vazias e reduz sequências de espaços (o modo layout do pdfplumber alinha
    colunas com muitos espaços, que só gastam tokens e podem estourar o contexto de modelos locais)."""
    linhas = (re.sub(r"[ \t]{2,}", "  ", linha).strip() for linha in texto.splitlines())
    return "\n".join(linha for linha in linhas if linha)


def _celula(texto: str | None) -> str:
    """Junta as linhas de uma célula: no DANFE, a 1ª linha é o rótulo e as seguintes o valor."""
    return " / ".join(linha.strip() for linha in (texto or "").splitlines() if linha.strip())


def _fora_das_caixas(caixas: list[tuple]):
    def filtro(objeto) -> bool:
        centro_x = (objeto["x0"] + objeto["x1"]) / 2
        centro_y = (objeto["top"] + objeto["bottom"]) / 2
        return not any(x0 <= centro_x <= x1 and topo <= centro_y <= base for x0, topo, x1, base in caixas)

    return filtro


def extrair_texto_estruturado(pdf_bytes: bytes) -> str:
    """Texto pensado para o modelo de IA.

    No DANFE, os dados ficam em quadros com o rótulo em cima e o valor embaixo. No texto
    corrido, a linha de rótulos e a linha de valores saem desalinhadas, e modelos pequenos
    não conseguem associá-las. Aqui as bordas dos quadros são detectadas como tabelas e
    cada célula sai como "Rótulo / valor". Páginas sem quadros (ex.: NFC-e) usam o texto corrido.
    """
    partes = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for pagina in pdf.pages:
            tabelas = pagina.find_tables()
            linhas_quadros = []
            for tabela in tabelas:
                for linha in tabela.extract():
                    celulas = [_celula(c) for c in linha if _celula(c)]
                    if celulas:
                        linhas_quadros.append(" || ".join(celulas))

            # Sem quadros com texto (NFC-e, ou página só com bordas desenhadas), vale o texto corrido
            if not linhas_quadros:
                partes.append(pagina.extract_text(layout=True) or "")
                continue

            restante = pagina.filter(_fora_das_caixas([t.bbox for t in tabelas])).extract_text(layout=True) or ""
            partes.append(
                "Quadros do documento (cada célula no formato 'Rótulo / valor'; células separadas por '||'):\n"
                + "\n".join(linhas_quadros)
                + ("\n\nTexto fora dos quadros:\n" + restante.strip() if restante.strip() else "")
            )
    return "\n\n".join(compactar(p) for p in partes if p.strip())
