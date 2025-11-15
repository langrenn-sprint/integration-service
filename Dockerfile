FROM python:3.13-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*
# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install the application dependencies.
WORKDIR /app
COPY . /app
RUN uv sync --frozen

# Docker label
LABEL org.opencontainers.image.source=https://github.com/langrenn-sprint/integration-service
LABEL org.opencontainers.image.description="integration-service"
LABEL org.opencontainers.image.licenses=Apache-2.0

# Run the application using the venv Python
## Run the application using the virtualenv-managed Python provided by uv (/uvx)
## This ensures packages installed by `uv sync` are available at runtime.
CMD ["/app/.venv/bin/python", "-m", "integration_service.app"]
