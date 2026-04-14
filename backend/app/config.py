"""Settings from environment (.env via pydantic-settings + dotenv in main)."""

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(..., alias="DATABASE_URL")
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openai_base_url: str = Field(
        "https://api.openai.com/v1",
        validation_alias=AliasChoices("OPENAI_BASE_URL", "OPENAI_API_BASE"),
    )
    admin_api_key: str = Field(..., alias="ADMIN_API_KEY")
    jwt_secret: str = Field(..., alias="JWT_SECRET")
    jwt_expire_hours: int = Field(default=168, alias="JWT_EXPIRE_HOURS")
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")
    pricing_json: str = Field(
        default='{"gpt-5":{"prompt_per_million":1.25,"completion_per_million":10.0},'
        '"gpt-4o":{"prompt_per_million":2.50,"completion_per_million":10.0}}',
        alias="PRICING_JSON",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def ensure_async_driver(cls, v: Any) -> Any:
        if isinstance(v, str) and v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


def parse_pricing_json(raw: str) -> Dict[str, Dict[str, float]]:
    import json

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid PRICING_JSON: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("PRICING_JSON must be a JSON object")
    out: Dict[str, Dict[str, float]] = {}
    for model, rates in data.items():
        if not isinstance(rates, dict):
            continue
        out[str(model)] = {
            "prompt_per_million": float(rates.get("prompt_per_million", 0)),
            "completion_per_million": float(rates.get("completion_per_million", 0)),
        }
    return out
