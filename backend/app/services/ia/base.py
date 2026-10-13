"""Partes comuns a todos os provedores de IA."""

PROMPT_SISTEMA = """Você é um especialista em documentos fiscais brasileiros: NF-e (DANFE), NFC-e e NFS-e.
Sua tarefa é extrair os dados do documento recebido exatamente como aparecem nele.

Regras:
- Identifique o tipo do documento (NF-e, NFC-e ou NFS-e). Use "desconhecido" se não for uma nota fiscal.
- Valores monetários e quantidades são números decimais com ponto (ex.: 1234.56), sem símbolo de moeda.
- Datas no formato AAAA-MM-DD.
- CNPJ, CPF e chave de acesso sem pontuação nem espaços.
- Liste todos os itens ou serviços, na ordem em que aparecem.
- Se um campo não existir no documento ou estiver ilegível, use null. Nunca invente nem calcule valores que não estejam no documento."""

INSTRUCAO_USUARIO = "Extraia os dados desta nota fiscal."


def mensagem_com_texto(texto: str) -> str:
    return f"Texto extraído de uma nota fiscal em PDF:\n\n<documento>\n{texto}\n</documento>\n\n{INSTRUCAO_USUARIO}"


class ErroExtracao(Exception):
    """A IA não conseguiu devolver uma extração utilizável."""
