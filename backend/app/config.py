import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Configuracoes:
    modelo_claude: str = os.getenv("MODELO_CLAUDE", "claude-opus-5-5")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./primefiscal.db")
    cors_origins: list[str] = field(
        default_factory=lambda: [
            o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()
        ]
    )
    tamanho_maximo_bytes: int = int(os.getenv("TAMANHO_MAXIMO_MB", "20")) * 1024 * 1024


configuracoes = Configuracoes()
