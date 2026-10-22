"""Runtime settings, read once from the environment (and backend/.env)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


def _origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [o.strip() for o in raw.split(",") if o.strip()]


@dataclass(frozen=True)
class Settings:
    llm_api_key: str | None = field(default_factory=lambda: os.getenv("SARVAM_API_KEY"))
    llm_base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.sarvam.ai/v2"))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gemma4"))

    cors_origins: list[str] = field(default_factory=_origins)

    max_upload_mb: int = field(default_factory=lambda: _int("MAX_UPLOAD_MB", 20))
    max_pages: int = field(default_factory=lambda: _int("MAX_PAGES", 150))
    chunk_chars: int = field(default_factory=lambda: _int("CHUNK_CHARS", 5000))
    max_chunks: int = field(default_factory=lambda: _int("MAX_CHUNKS", 40))
    extract_workers: int = field(default_factory=lambda: _int("EXTRACT_WORKERS", 4))

    max_graphs: int = field(default_factory=lambda: _int("MAX_GRAPHS", 50))
    graph_ttl_seconds: int = field(default_factory=lambda: _int("GRAPH_TTL_SECONDS", 6 * 3600))


settings = Settings()
