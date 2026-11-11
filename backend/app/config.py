import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

PASTA_BACKEND = Path(__file__).resolve().parent.parent
VALORES_DOTENV = dotenv_values(PASTA_BACKEND / ".env")


def valor_ambiente(nome: str, padrao: str = "") -> str:
    """Obtém a configuração sem deixar uma variável de ambiente vazia ocultar o .env.

    Isso é comum no Windows quando uma sessão/IDE exportou ``GEMINI_API_KEY=``.
    Um valor não vazio do ambiente ainda tem prioridade, como esperado em produção.
    """
    return os.getenv(nome) or VALORES_DOTENV.get(nome) or padrao

PROVEDORES_IA = ("claude", "lmstudio", "compativel", "gemini", "google")
FORMATOS_RESPOSTA_COMPATIVEL = ("json_schema", "json_object", "prompt")


@dataclass(frozen=True)
class Configuracoes:
    provedor_ia: str = valor_ambiente("PROVEDOR_IA", "claude").strip().lower()
    modelo_claude: str = valor_ambiente("MODELO_CLAUDE", "claude-opus-5-5").strip()
    lmstudio_url: str = valor_ambiente("LMSTUDIO_URL", "http://127.0.0.1:1234/v1").rstrip("/")
    lmstudio_modelo: str = valor_ambiente("LMSTUDIO_MODELO").strip()
    lmstudio_timeout: float = float(valor_ambiente("LMSTUDIO_TIMEOUT", "600"))
    # Qualquer serviço que implemente /v1/chat/completions (OpenAI, Groq, Ollama,
    # OpenRouter, Together, vLLM, etc.). A URL deve incluir o sufixo /v1.
    compativel_url: str = valor_ambiente("API_COMPATIVEL_URL", "https://api.openai.com/v1").rstrip("/")
    compativel_chave: str = valor_ambiente("API_COMPATIVEL_CHAVE").strip()
    compativel_modelo: str = valor_ambiente("API_COMPATIVEL_MODELO", "gpt-4o-mini").strip()
    compativel_nome: str = valor_ambiente("API_COMPATIVEL_NOME", "API compatível com OpenAI").strip()
    compativel_timeout: float = float(valor_ambiente("API_COMPATIVEL_TIMEOUT", "120"))
    compativel_formato_resposta: str = valor_ambiente("API_COMPATIVEL_FORMATO_RESPOSTA", "json_schema").strip().lower()
    gemini_chave: str = valor_ambiente("GEMINI_API_KEY").strip()
    gemini_modelo: str = valor_ambiente("GEMINI_MODELO", "gemini-2.5-flash").strip()
    gemini_timeout: float = float(valor_ambiente("GEMINI_TIMEOUT", "120"))
    # Os caminhos padrão ficam dentro de backend/, independentemente de onde o servidor é iniciado
    database_url: str = valor_ambiente("DATABASE_URL") or f"sqlite:///{(PASTA_BACKEND / 'primefiscal.db').as_posix()}"
    pasta_uploads: Path = Path(valor_ambiente("PASTA_UPLOADS") or PASTA_BACKEND / "uploads")
    cors_origins: list[str] = field(
        default_factory=lambda: [
            o.strip() for o in valor_ambiente("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()
        ]
    )
    tamanho_maximo_bytes: int = int(valor_ambiente("TAMANHO_MAXIMO_MB", "20")) * 1024 * 1024

    def __post_init__(self) -> None:
        if self.provedor_ia not in PROVEDORES_IA:
            raise ValueError(
                f"PROVEDOR_IA inválido: '{self.provedor_ia}'. Use um destes: {', '.join(PROVEDORES_IA)}."
            )
        # "google" é aceito por ser a forma mais intuitiva no .env; internamente
        # o provedor se chama Gemini, que é a API generativa da Google.
        if self.provedor_ia == "google":
            object.__setattr__(self, "provedor_ia", "gemini")
        if self.compativel_formato_resposta not in FORMATOS_RESPOSTA_COMPATIVEL:
            raise ValueError(
                "API_COMPATIVEL_FORMATO_RESPOSTA inválido: "
                f"'{self.compativel_formato_resposta}'. Use um destes: {', '.join(FORMATOS_RESPOSTA_COMPATIVEL)}."
            )


configuracoes = Configuracoes()
