# Multi-stage Dockerfile for unified pipeline
# Build: docker build -t pipeline-ingestors --target ingestor .
# Run:   docker run ... pipeline-ingestors python mc.py ingestors massive

# STAGE 0: uv binary
FROM ghcr.io/astral-sh/uv:latest AS uv_bin

# STAGE 1: Builder (shared)
FROM python:3.14-slim AS builder

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=never

WORKDIR /app
COPY --from=uv_bin /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# STAGE 2: Ingestors
FROM python:3.14-slim AS ingestor
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY mc.py ./
COPY ingestors/ ./ingestors/
COPY processors/ ./processors/
COPY indicators/ ./indicators/
COPY publishers/ ./publishers/

ENTRYPOINT ["python", "mc.py"]
CMD ["ingestors", "massive"]

# STAGE 3: Processors
FROM python:3.14-slim AS processor
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY mc.py ./
COPY ingestors/ ./ingestors/
COPY processors/ ./processors/
COPY indicators/ ./indicators/
COPY publishers/ ./publishers/

ENTRYPOINT ["python", "mc.py"]
CMD ["processors", "stock_features_daily"]

# STAGE 4: Indicators
FROM python:3.14-slim AS indicator
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY mc.py ./
COPY ingestors/ ./ingestors/
COPY processors/ ./processors/
COPY indicators/ ./indicators/
COPY publishers/ ./publishers/

ENTRYPOINT ["python", "mc.py"]
CMD ["indicators", "spx_gold_daily"]

# STAGE 5: Publishers
FROM python:3.14-slim AS publisher
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY mc.py ./
COPY ingestors/ ./ingestors/
COPY processors/ ./processors/
COPY indicators/ ./indicators/
COPY publishers/ ./publishers/

ENTRYPOINT ["python", "mc.py"]
CMD ["publishers", "spx_gold_trend"]
