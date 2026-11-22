"""Konfiguracja aplikacji (zmienne środowiskowe z prefiksem WODA_)."""
from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # .env w katalogu repo (uruchomienie z backend/) albo w bieżącym katalogu
    model_config = SettingsConfigDict(env_prefix="WODA_", env_file=(REPO_ROOT / ".env", ".env"), extra="ignore")

    # Ścieżki
    cache_dir: Path = REPO_ROOT / "data" / "cache"
    knowledge_dir: Path = REPO_ROOT / "data" / "knowledge"

    # Budżety czasowe (wymóg KOWR: rekomendacja < 30 s na działkę)
    total_budget_s: float = 25.0
    default_connector_timeout_s: float = 12.0
    http_connect_timeout_s: float = 5.0

    # Okno historyczne (wymóg: dane z ostatnich 10 lat)
    history_years: int = 10

    # Bufor wokół działki do analiz terenu/hydrologii (woda nie zna granic działek)
    analysis_buffer_m: float = 300.0

    # Identyfikacja klienta wobec zewnętrznych API (bez danych osobowych!)
    user_agent: str = "KOWR-HackNation2026-Prototype/0.1 (+research prototype)"

    # CORS dla frontendu
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # LLM (OpenAI) – tylko do wyjaśnień prostym językiem i czatu; decyzje prawne zostają w regułach.
    # Bez klucza aplikacja działa w pełni (szablony tekstów zamiast LLM).
    openai_api_key: str | None = Field(default=None, validation_alias=AliasChoices("OPENAI_API_KEY", "WODA_OPENAI_API_KEY"))
    openai_model: str = "gpt-5.4-mini"
    llm_timeout_s: float = 15.0


settings = Settings()
