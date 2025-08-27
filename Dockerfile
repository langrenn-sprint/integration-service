FROM python:3.13-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    requests \
    && rm -rf /var/lib/apt/lists/*
# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install the application dependencies.
WORKDIR /app
COPY . /app

# Install dependencies
RUN uv sync --frozen

# Docker label
LABEL org.opencontainers.image.source=https://github.com/langrenn-sprint/integration-service
LABEL org.opencontainers.image.description="integration-service"
LABEL org.opencontainers.image.licenses=Apache-2.0

# Run the application using the venv Python
CMD ["python", "-m", "integration_service.app"]
