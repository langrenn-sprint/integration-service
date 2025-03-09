FROM python:3.12

RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*
# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the application into the container.
ADD . /app

# Install the application dependencies.
WORKDIR /app
RUN uv sync --frozen

# Expose the application port.
EXPOSE 8080

# Docker label
LABEL org.opencontainers.image.source=https://github.com/langrenn-sprint/integration-service
LABEL org.opencontainers.image.description="integration-service"
LABEL org.opencontainers.image.licenses=Apache-2.0

# Run the application.
CMD ["python", "-m", "integration_service.app"] 
# CMD python3 integration_service/app.py
