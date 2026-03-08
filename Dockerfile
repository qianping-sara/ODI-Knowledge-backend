FROM --platform=linux/amd64 python:3.11-slim

ENV UV_PROJECT_ENV=.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_INSTALL_DIR=/usr/local/bin \
    UV_NO_MODIFY_PATH=1

WORKDIR /app

# Install curl for fetching uv, then install uv (lock-aware package manager)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates gnupg bash && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    rm -rf /var/lib/apt/lists/*

# Copy project files and install dependencies from uv.lock (no dev extras)
COPY . .
RUN uv sync --frozen --no-dev

EXPOSE 8000

# Start FastAPI service
CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
