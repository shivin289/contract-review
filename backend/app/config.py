"""Settings read from environment variables (see .env.example)."""
import base64
import os


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _clerk_host(publishable_key: str) -> str:
    """The Clerk frontend API host is base64-encoded inside the publishable key."""
    try:
        part = publishable_key.split("_", 2)[2]
        return base64.b64decode(part + "=" * (-len(part) % 4)).decode().rstrip("$")
    except Exception:
        return ""


class Settings:
    def __init__(self) -> None:
        self.database_url = _env("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/contracts")
        host = _clerk_host(_env("CLERK_PUBLISHABLE_KEY"))
        self.clerk_issuer = _env("CLERK_ISSUER") or (f"https://{host}" if host else "")
        self.clerk_jwks_url = _env("CLERK_JWKS_URL") or (
            f"{self.clerk_issuer}/.well-known/jwks.json" if self.clerk_issuer else ""
        )
        self.authorized_parties = [
            p.strip() for p in _env("CLERK_AUTHORIZED_PARTIES", "http://localhost:3000").split(",") if p.strip()
        ]
        self.frontend_origin = _env("FRONTEND_ORIGIN", "http://localhost:3000")
        self.openrouter_key = _env("OPENROUTER_API_KEY")
        self.openrouter_base_url = _env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        self.chat_model = _env("CHAT_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")
        self.embed_model = _env("EMBED_MODEL", "nvidia/nemotron-3.5-embed-1b:free")
        self.embed_dim = int(_env("EMBED_DIM", "2048"))
        self.max_upload_mb = int(_env("MAX_UPLOAD_MB", "20"))


settings = Settings()
