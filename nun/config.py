"""Runtime settings from the environment / .env (see .env.example)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # env_ignore_empty: `WEB_ORIGIN=` (blank, as in .env.example) means "use the default", not ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    public_base_url: str = "http://localhost:5173"
    web_origin: str = "http://localhost:5173"
    referral_contact_ar: str = ""
    referral_contact_en: str = ""
    gpu_tier: str = "auto"
    vlm_adapter: str = "Omartificial-Intelligence-Space/Nun-Vision-30B-Lora"
    log_level: str = "info"
    data_dir: Path = Path("data")

    @property
    def corpus_dir(self) -> Path:
        return self.data_dir / "corpus"


@lru_cache
def settings() -> Settings:
    return Settings()
