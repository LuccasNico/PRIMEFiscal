"""Configurações do backend, lidas das variáveis de ambiente e de backend/.env."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

PASTA_BACKEND = Path(__file__).resolve().parent.parent
# ARQUIVO_ENV permite usar outro arquivo; os testes apontam para um inexistente para não ler o .env real
VALORES_DO_ENV = dotenv_values(os.getenv("ARQUIVO_ENV") or PASTA_BACKEND / ".env")

PROVEDORES_IA = ("gemini", "claude", "lmstudio", "compativel")
# "google" é aceito no .env por ser o nome mais lembrado; o provedor é a Gemini API
APELIDOS_DE_PROVEDOR = {"google": "gemini"}
FORMATOS_DE_RESPOSTA = ("json_schema", "json_object", "prompt")


def valor_ambiente(nome: str, padrao: str = "") -> str:
    """Lê uma configuração: variável de ambiente, depois backend/.env, depois o padrão.

    Uma variável de ambiente vazia é ignorada para não esconder o valor do .env, o que
    acontece no Windows quando o terminal ou a IDE exportou, por exemplo, ``GEMINI_API_KEY=``.
    """
    return (os.getenv(nome) or VALORES_DO_ENV.get(nome) or padrao).strip()


def _provedor_ia() -> str:
    nome = valor_ambiente("PROVEDOR_IA", "gemini").lower()
    return APELIDOS_DE_PROVEDOR.get(nome, nome)


def url_do_banco(url: str) -> str:
    """Ajusta a URL do banco. Vazia = SQLite em backend/primefiscal.db.

    Serviços de PostgreSQL na nuvem (Neon, Supabase, Render, Railway) fornecem a URL como
    ``postgres://`` ou ``postgresql://``; o SQLAlchemy precisa do nome do driver (psycopg).
    """
    if not url:
        return f"sqlite:///{(PASTA_BACKEND / 'primefiscal.db').as_posix()}"
    for prefixo in ("postgres://", "postgresql://"):
        if url.startswith(prefixo):
            return "postgresql+psycopg://" + url.removeprefix(prefixo)
    return url


def _lista(texto: str) -> list[str]:
    return [item.strip() for item in texto.split(",") if item.strip()]


def _origens(texto: str) -> list[str]:
    """Origens do CORS. O navegador envia a origem sem barra no fim, então ela é removida."""
    return [origem.rstrip("/") for origem in _lista(texto)]


@dataclass(frozen=True)
class Configuracoes:
    provedor_ia: str = _provedor_ia()

    # Gemini API (Google), o provedor padrão
    gemini_chave: str = valor_ambiente("GEMINI_API_KEY")
    gemini_modelo: str = valor_ambiente("GEMINI_MODELO", "gemini-3.5-flash")
    gemini_timeout: float = float(valor_ambiente("GEMINI_TIMEOUT", "120"))

    # Claude API (Anthropic)
    claude_chave: str = valor_ambiente("ANTHROPIC_API_KEY")
    claude_modelo: str = valor_ambiente("MODELO_CLAUDE", "claude-opus-5-5")

    # LM Studio (modelo local)
    lmstudio_url: str = valor_ambiente("LMSTUDIO_URL", "http://127.0.0.1:1234/v1").rstrip("/")
    lmstudio_modelo: str = valor_ambiente("LMSTUDIO_MODELO")
    lmstudio_timeout: float = float(valor_ambiente("LMSTUDIO_TIMEOUT", "600"))

    # Qualquer serviço com a rota /chat/completions no padrão da OpenAI (OpenAI, Groq, OpenRouter,
    # Ollama etc.). A URL termina em /v1.
    compativel_nome: str = valor_ambiente("API_COMPATIVEL_NOME", "API compatível com OpenAI")
    compativel_url: str = valor_ambiente("API_COMPATIVEL_URL", "https://api.openai.com/v1").rstrip("/")
    compativel_chave: str = valor_ambiente("API_COMPATIVEL_CHAVE")
    compativel_modelo: str = valor_ambiente("API_COMPATIVEL_MODELO", "gpt-4o-mini")
    compativel_timeout: float = float(valor_ambiente("API_COMPATIVEL_TIMEOUT", "120"))
    compativel_formato_resposta: str = valor_ambiente("API_COMPATIVEL_FORMATO_RESPOSTA", "json_schema").lower()

    # Os caminhos padrão ficam dentro de backend/, independentemente de onde o servidor é iniciado
    database_url: str = url_do_banco(valor_ambiente("DATABASE_URL"))
    pasta_uploads: Path = Path(valor_ambiente("PASTA_UPLOADS") or PASTA_BACKEND / "uploads")
    cors_origins: list[str] = field(
        default_factory=lambda: _origens(valor_ambiente("CORS_ORIGINS", "http://localhost:5173"))
    )
    tamanho_maximo_bytes: int = int(valor_ambiente("TAMANHO_MAXIMO_MB", "20")) * 1024 * 1024

    def __post_init__(self) -> None:
        if self.provedor_ia not in PROVEDORES_IA:
            aceitos = ", ".join((*PROVEDORES_IA, *APELIDOS_DE_PROVEDOR))
            raise ValueError(f"PROVEDOR_IA inválido: '{self.provedor_ia}'. Use um destes: {aceitos}.")
        if self.compativel_formato_resposta not in FORMATOS_DE_RESPOSTA:
            raise ValueError(
                f"API_COMPATIVEL_FORMATO_RESPOSTA inválido: '{self.compativel_formato_resposta}'. "
                f"Use um destes: {', '.join(FORMATOS_DE_RESPOSTA)}."
            )


configuracoes = Configuracoes()
