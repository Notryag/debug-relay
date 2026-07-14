from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["local", "test", "production"] = Field(
        default="local",
        alias="DEBUGRELAY_ENV",
    )
    log_level: str = Field(default="INFO", alias="DEBUGRELAY_LOG_LEVEL")
    database_url: str = Field(
        default="postgresql+asyncpg://debugrelay:debugrelay@127.0.0.1:5432/debugrelay",
        alias="DATABASE_URL",
    )
    admin_token: SecretStr | None = Field(default=None, alias="DEBUGRELAY_ADMIN_TOKEN")
    token_bytes: int = Field(default=32, alias="DEBUGRELAY_TOKEN_BYTES", ge=24, le=64)
    max_evidence_bytes: int = Field(
        default=10 * 1024 * 1024,
        alias="DEBUGRELAY_MAX_EVIDENCE_BYTES",
        ge=1024,
        le=10 * 1024 * 1024,
    )
    max_event_bytes: int = Field(
        default=256 * 1024,
        alias="DEBUGRELAY_MAX_EVENT_BYTES",
        ge=1024,
        le=1024 * 1024,
    )
    cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="DEBUGRELAY_CORS_ORIGINS",
    )

    @field_validator("database_url")
    @classmethod
    def require_postgresql(cls, value: str) -> str:
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use postgresql+asyncpg")
        return value

    @model_validator(mode="after")
    def require_production_admin_token(self) -> Settings:
        if self.environment != "production":
            return self
        if self.admin_token is None or len(self.admin_token.get_secret_value()) < 32:
            raise ValueError(
                "Production requires DEBUGRELAY_ADMIN_TOKEN with at least 32 characters"
            )
        return self

    @property
    def effective_admin_token(self) -> str:
        if self.admin_token is not None:
            return self.admin_token.get_secret_value()
        if self.environment == "production":
            raise RuntimeError("Production admin token is not configured")
        return "debugrelay-local-admin"

    @property
    def allowed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
