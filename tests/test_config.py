from __future__ import annotations

from pydantic import ValidationError
import pytest

from debugrelay.config import Settings


def test_production_requires_explicit_strong_admin_token() -> None:
    with pytest.raises(ValidationError, match="Production requires DEBUGRELAY_ADMIN_TOKEN"):
        Settings(
            DEBUGRELAY_ENV="production",
            DEBUGRELAY_ADMIN_TOKEN=None,
            DATABASE_URL="postgresql+asyncpg://debugrelay:example@127.0.0.1/debugrelay",
            _env_file=None,
        )


def test_local_mode_has_loopback_development_token() -> None:
    settings = Settings(
        DEBUGRELAY_ENV="local",
        DEBUGRELAY_ADMIN_TOKEN=None,
        DATABASE_URL="postgresql+asyncpg://debugrelay:example@127.0.0.1/debugrelay",
        _env_file=None,
    )

    assert settings.effective_admin_token == "debugrelay-local-admin"
