from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIB = 1024 * 1024


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "local"
    sprites_api_token: str | None = None
    sprites_gateway_base: str = "https://api.sprites.dev/v1/gateway"
    sprites_api_base: str = "https://api.sprites.dev/v1"
    airlock_sprite_name: str = "cupbearer-airlock"
    airlock_connection_id: str = "airlock-self"
    airlock_baseline_checkpoint_id: str | None = None
    telegram_connection_id: str = "telegram"
    telegram_webhook_secret: str = "dev-secret"
    box_connection_id: str = "box"
    box_inbox_folder_id: str = "0"
    box_hold_folder_id: str = "0"
    box_verified_folder_id: str = "0"
    pinecone_connection_id: str = "pinecone"
    pinecone_index_name: str = "cupbearer"
    pinecone_index_host: str | None = None
    llm_connection_id: str = "gemini"
    llm_provider: str = "gemini"
    llm_model: str = "gemini-3.5-flash-lite"
    public_base_url: str = "http://localhost:8000"
    desk_access_token: str = "dev-desk-token"
    sqlite_path: Path = Path("data/cupbearer.db")
    artifacts_dir: Path = Path("data/artifacts")
    max_artifact_bytes: int = Field(default=16 * MIB, le=16 * MIB)
    poll_interval_seconds: int = 300
    airlock_timeout_seconds: int = 25
    local_airlock: bool = True

    @field_validator("llm_provider")
    @classmethod
    def provider_supported(cls, value: str) -> str:
        if value not in {"gemini", "ollama", "off"}:
            raise ValueError("llm_provider must be gemini, ollama, or off")
        return value

    @field_validator("max_artifact_bytes")
    @classmethod
    def within_sprite_write_cap(cls, value: int) -> int:
        if value <= 0 or value > 16 * MIB:
            raise ValueError("max_artifact_bytes must be positive and no more than 16 MiB")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
