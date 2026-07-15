FROM python:3.11-slim-bookworm AS build

ARG UV_VERSION=0.11.28

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN pip install --no-cache-dir "uv==${UV_VERSION}"

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev

FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/app/.venv/bin:$PATH

WORKDIR /app

RUN groupadd --system debugrelay \
    && useradd --system --gid debugrelay --home-dir /app debugrelay

COPY --from=build --chown=debugrelay:debugrelay /app/.venv ./.venv
COPY --chown=debugrelay:debugrelay src ./src
COPY --chown=debugrelay:debugrelay alembic.ini ./
COPY --chown=debugrelay:debugrelay alembic ./alembic
COPY --chown=debugrelay:debugrelay schemas ./schemas

USER debugrelay

EXPOSE 8010

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn debugrelay.main:app --host 0.0.0.0 --port 8010"]
