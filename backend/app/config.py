import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PASTA_BACKEND = Path(__file__).resolve().parent.parent
load_dotenv(PASTA_BACKEND / ".env")

PROVEDORES_IA = ("claude", "lmstudio")


@dataclass(frozen=True)
class Configuracoes:
    provedor_ia: str = os.getenv("PROVEDOR_IA", "claude").strip().lower()
    modelo_claude: str = os.getenv("MODELO_CLAUDE", "claude-opus-5-5").strip()
    lmstudio_url: str = os.getenv("LMSTUDIO_URL", "http://127.0.0.1:1234/v1").rstrip("/")
    lmstudio_modelo: str = os.getenv("LMSTUDIO_MODELO", "").strip()
    lmstudio_timeout: float = float(os.getenv("LMSTUDIO_TIMEOUT", "600"))
    # Os caminhos padrão ficam dentro de backend/, independentemente de onde o servidor é iniciado
    database_url: str = os.getenv("DATABASE_URL") or f"sqlite:///{(PASTA_BACKEND / 'primefiscal.db').as_posix()}"
    pasta_uploads: Path = Path(os.getenv("PASTA_UPLOADS") or PASTA_BACKEND / "uploads")
    cors_origins: list[str] = field(
        default_factory=lambda: [
            o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()
        ]
    )
    tamanho_maximo_bytes: int = int(os.getenv("TAMANHO_MAXIMO_MB", "20")) * 1024 * 1024

    def __post_init__(self) -> None:
        if self.provedor_ia not in PROVEDORES_IA:
            raise ValueError(
                f"PROVEDOR_IA inválido: '{self.provedor_ia}'. Use um destes: {', '.join(PROVEDORES_IA)}."
            )


configuracoes = Configuracoes()
