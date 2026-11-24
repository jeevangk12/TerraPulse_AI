from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def _csv_env(name: str, default: str) -> list[str]:
    return [part.strip() for part in os.getenv(name, default).split(",") if part.strip()]


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    gemini_model: str
    copernicus_client_id: str
    copernicus_client_secret: str
    cors_origins: list[str]
    open_meteo_timeout_seconds: float
    copernicus_timeout_seconds: float
    copernicus_max_cloud_cover_percent: float
    gemini_timeout_seconds: float


def load_settings() -> Settings:
    return Settings(
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip(),
        copernicus_client_id=os.getenv("COPERNICUS_CLIENT_ID", "").strip(),
        copernicus_client_secret=os.getenv("COPERNICUS_CLIENT_SECRET", "").strip(),
        cors_origins=_csv_env(
            "CORS_ORIGINS",
            "http://localhost:8080,http://127.0.0.1:8080,http://localhost:5173,http://127.0.0.1:5173",
        ),
        open_meteo_timeout_seconds=float(os.getenv("OPEN_METEO_TIMEOUT_SECONDS", "12")),
        copernicus_timeout_seconds=float(os.getenv("COPERNICUS_TIMEOUT_SECONDS", "30")),
        copernicus_max_cloud_cover_percent=float(os.getenv("COPERNICUS_MAX_CLOUD_COVER_PERCENT", "80")),
        gemini_timeout_seconds=float(os.getenv("GEMINI_TIMEOUT_SECONDS", "18")),
    )


settings = load_settings()
