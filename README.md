### integration-service
Service for pushing and pulling messages and file to cloud services such as PubSub and Drive

### Start service:
```Zsh
python3 -m integration_service.app

### But first, start dependencies (services & db):

```Zsh
docker-compose up event-service user-service photo-service mongodb

## Requirement for development

Install [uv](https://docs.astral.sh/uv/), e.g.:

```Zsh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then install the dependencies:

```Zsh
uv sync
```
### If required - virtual environment

```Zsh
curl <https://pyenv.run> | bash
python -m venv .venv
pyenv install 3.12
source .venv/bin/activate

### Install

```Zsh
git clone <https://github.com/heming-langrenn/vision-ai-service.git>
cd vision-ai-service

### Prepare .env filer (dummy parameter values supplied)

LOGGING_LEVEL=INFO
ADMIN_USERNAME=admin
ADMIN_PASSWORD=password
EVENTS_HOST_SERVER=localhost
EVENTS_HOST_PORT=8082
PHOTOS_HOST_SERVER=localhost
PHOTOS_HOST_PORT=8092
USERS_HOST_SERVER=localhost
USERS_HOST_PORT=8086
GOOGLE_APPLICATION_CREDENTIALS=/Users/name/github/secrets/application_default_credentials.json
GOOGLE_CLOUD_PROJECT=sigma-celerity-257719
GOOGLE_PUBSUB_NUM_MESSAGES=1
GOOGLE_PUBSUB_TOPIC_ID=langrenn-sprint
GOOGLE_PUBSUB_SUBSCRIPTION_ID=langrenn-sprint-sub
GOOGLE_STORAGE_BUCKET=langrenn-sprint
GOOGLE_STORAGE_SERVER=https://storage.googleapis.com

## Running tests

We use [pytest](https://docs.pytest.org/en/latest/) for contract testing.

To run linters, checkers and tests:

```Zsh
% uv run poe release
```

To run tests with logging, do:

```Zsh
% uv run pytest -m integration -- --log-cli-level=DEBUG
```

### Push to docker registry manually (CLI)

docker-compose build
docker login ghcr.io -u github
password: Use a generated access token from GitHub (https://github.com/settings/tokens/1878556677)
docker tag ghcr.io/langrenn-sprint/vision-ai-service:test ghcr.io/langrenn-sprint/vision-ai-service:latest
docker push ghcr.io/langrenn-sprint/vision-ai-service:latest
