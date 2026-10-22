"""Runtime settings, read once from the environment (and backend/.env)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw and raw.strip() else default


def _origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [o.strip() for o in raw.split(",") if o.strip()]


@dataclass(frozen=True)
class Settings:
    # Any OpenAI-compatible endpoint. Defaults to the opencode-go gateway; bulk extraction
    # is general LLM traffic and should not run through a voice platform's quota.
    llm_api_key: str | None = field(default_factory=lambda: os.getenv("LLM_API_KEY"))
    llm_base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "https://opencode.ai/zen/go/v1"))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "deepseek-v4-flash"))

    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", ROOT / "data")))
    cors_origins: list[str] = field(default_factory=_origins)
    allow_uploads: bool = field(default_factory=lambda: os.getenv("ALLOW_UPLOADS", "1") == "1")

    max_upload_mb: int = field(default_factory=lambda: _int("MAX_UPLOAD_MB", 60))
    chunk_chars: int = field(default_factory=lambda: _int("CHUNK_CHARS", 9000))
    extract_workers: int = field(default_factory=lambda: _int("EXTRACT_WORKERS", 4))

    # Red-flag thresholds (percent of revenue from operations, latest fiscal).
    rpt_high_pct: float = field(default_factory=lambda: _float("RPT_HIGH_PCT", 10.0))
    rpt_medium_pct: float = field(default_factory=lambda: _float("RPT_MEDIUM_PCT", 3.0))

    @property
    def db_path(self) -> Path:
        return self.data_dir / "footnote.db"

    @property
    def filings_dir(self) -> Path:
        return self.data_dir / "filings"


settings = Settings()
