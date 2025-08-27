FROM python:3.13-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*
# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install the application dependencies.
WORKDIR /app
COPY . /app

# Create a virtual environment
RUN python -m venv .venv

# Activate the virtual environment and install dependencies
RUN . .venv/bin/activate && uv sync --frozen

# Docker label
LABEL org.opencontainers.image.source=https://github.com/langrenn-sprint/integration-service
LABEL org.opencontainers.image.description="integration-service"
LABEL org.opencontainers.image.licenses=Apache-2.0

# Run the application using the venv Python
CMD ["/app/.venv/bin/python", "-m", "integration_service.app"]
