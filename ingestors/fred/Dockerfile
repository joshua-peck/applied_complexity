# STAGE 1: Build dependencies
FROM ghcr.io/astral-sh/uv:latest AS uv_bin

# Note: this version of python must match the one used by uv on the local dev machine
FROM python:3.14-slim AS builder

ENV UV_COMPILE_BYTECODE=1 
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=never

WORKDIR /app
COPY --from=uv_bin /uv /uvx /bin/

# Install dependencies using the lockfile
# We use --frozen to ensure we don't accidentally update versions
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# STAGE 2: Final Runtime Image
# Note: this version of python must match the one used by uv on the local dev machine
FROM python:3.14-slim
WORKDIR /app

# Copy the virtual environment from the builder
COPY --from=builder /app/.venv /app/.venv
# COPY --from=builder /app/install /usr/local
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy your ingestion script
COPY main.py .

CMD ["python", "main.py"]
