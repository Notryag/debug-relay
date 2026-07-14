from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine


ROOT = Path(__file__).resolve().parents[2]
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://debugrelay:debugrelay@127.0.0.1:5432/debugrelay_test",
)
ADMIN_TOKEN = "test-admin-token-with-at-least-32-characters"

if not (make_url(TEST_DATABASE_URL).database or "").endswith("_test"):
    raise RuntimeError("TEST_DATABASE_URL database name must end in _test")

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["DEBUGRELAY_ENV"] = "test"
os.environ["DEBUGRELAY_ADMIN_TOKEN"] = ADMIN_TOKEN

from debugrelay.config import Settings, get_settings  # noqa: E402
from debugrelay.main import create_app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> Iterator[None]:
    get_settings.cache_clear()
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    yield


@pytest_asyncio.fixture(autouse=True)
async def clean_database(migrated_database: None) -> AsyncIterator[None]:
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE TABLE projects CASCADE"))
    await engine.dispose()
    yield


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)


@pytest_asyncio.fixture
async def client(clean_database: None, settings: Settings) -> AsyncIterator[AsyncClient]:
    app = create_app(settings)
    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as http_client:
            yield http_client
