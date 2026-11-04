from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=None, extra="ignore")

    env: str = "development"
    api_key: str | None = None
    upload_max_bytes: int = 10 * 1024 * 1024
    max_image_dimension: int = 8000
    model_manifest: Path = Path("models/manifest.json")
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
