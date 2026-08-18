FROM python:3.13-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.6.1 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_CACHE_DIR=/opt/uv-cache \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    EYLO_HOME=/app/server \
    PORT=8000

WORKDIR /app/server

COPY server/pyproject.toml server/uv.lock ./
RUN --mount=type=cache,target=/opt/uv-cache \
    uv export --frozen --no-dev --no-emit-project \
        --format requirements-txt > /tmp/requirements.lock && \
    uv venv /opt/venv && \
    uv pip install --python /opt/venv/bin/python -r /tmp/requirements.lock

COPY server/ /app/server/

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=6 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5).read()"]

CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:8000", "--worker-class", "uvicorn.workers.UvicornWorker", "--timeout", "120", "main:app"]
