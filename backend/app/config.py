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
    jwt_expire_hours: int = Field(default=5, alias="JWT_EXPIRE_HOURS")
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")
    pricing_json: str = Field(
        default='{"gpt-5":{"prompt_per_million":1.25,"completion_per_million":10.0},'
        '"gpt-4o":{"prompt_per_million":2.50,"completion_per_million":10.0}}',
        alias="PRICING_JSON",
    )
    teams_webhook_url: str = Field(default="", alias="TEAMS_WEBHOOK_URL")
    spike_window_seconds: int = Field(default=60, alias="SPIKE_WINDOW_SECONDS")
    spike_max_cost_usd: float = Field(default=5.0, alias="SPIKE_MAX_COST_USD")
    spike_max_tokens: int = Field(default=500_000, alias="SPIKE_MAX_TOKENS")
    spike_max_requests: int = Field(default=120, alias="SPIKE_MAX_REQUESTS")
    budget_threshold_fraction: float = Field(default=0.8, alias="BUDGET_THRESHOLD_FRACTION")
    enable_ip_check: bool = Field(default=False, alias="ENABLE_IP_CHECK")
    enable_hmac_check: bool = Field(default=True, alias="ENABLE_HMAC_CHECK")
    hmac_signing_secret: str = Field(default="", alias="HMAC_SIGNING_SECRET")
    hmac_max_skew_seconds: int = Field(default=300, alias="HMAC_MAX_SKEW_SECONDS")
    hmac_nonce_ttl_seconds: int = Field(default=600, alias="HMAC_NONCE_TTL_SECONDS")
    log_to_files: bool = Field(default=True, alias="LOG_TO_FILES")
    log_dir: str = Field(default="logs", alias="LOG_DIR")
    dev_log_filename: str = Field(default="dev.log", alias="DEV_LOG_FILE")
    audit_log_filename: str = Field(default="audit.log", alias="AUDIT_LOG_FILE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_encryption_key: str = Field(default="", alias="LOG_ENCRYPTION_KEY")
    log_encrypt_audit: bool = Field(default=True, alias="LOG_ENCRYPT_AUDIT")
    log_encrypt_dev: bool = Field(default=False, alias="LOG_ENCRYPT_DEV")

    @field_validator("database_url", mode="before")
    @classmethod
    def ensure_async_mssql(cls, v: Any) -> Any:
        if not isinstance(v, str):
            return v
        s = v.strip()
        if s.startswith("postgresql://") or s.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL must use Microsoft SQL Server. "
                "Use mssql+aioodbc://... (see backend/.env.example)."
            )
        if s.startswith("mssql://"):
            return s.replace("mssql://", "mssql+aioodbc://", 1)
        if s.startswith("sqlserver://"):
            return "mssql+aioodbc://" + s[len("sqlserver://") :]
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
