FROM ghcr.io/astral-sh/uv:0.11.28 AS uv
FROM python:3.11-slim-bookworm

COPY --from=uv /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev

COPY alembic.ini ./
COPY alembic ./alembic
COPY schemas ./schemas

RUN groupadd --system debugrelay \
    && useradd --system --gid debugrelay --home-dir /app debugrelay \
    && chown -R debugrelay:debugrelay /app

USER debugrelay

EXPOSE 8010

CMD ["sh", "-c", ".venv/bin/alembic upgrade head && exec .venv/bin/uvicorn debugrelay.main:app --host 0.0.0.0 --port 8010"]
