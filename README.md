### integration-service
Service for pushing and pulling messages and file to cloud services such as PubSub and Drive

### If required - virtual environment
```Zsh
curl <https://pyenv.run> | bash
python -m venv .venv
pyenv install 3.13
source .venv/bin/activate
```

### Start service in virtual env:
```Zsh
set -a
source .env
set +a
.venv/bin/python3 -m integration_service.app
```

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
RACE_HOST_SERVER=localhost
RACE_HOST_PORT=8088
USERS_HOST_SERVER=localhost
USERS_HOST_PORT=8086
GOOGLE_APPLICATION_CREDENTIALS=/Users/name/github/secrets/application_default_credentials.json
GOOGLE_CLOUD_PROJECT=sigma-celerity-257719
GOOGLE_PUBSUB_NUM_MESSAGES=10
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

### Innstillinger i google cloud
- Create OAuth2.0 client Id: <https://console.cloud.google.com/apis/credentials>
- Hints1: Javascript origins: http://localhost:8080 and http://localhost
- Hints2: Redirect URI: http://localhost:8080/photos_adm and http://localhost/photos_adm
- Download client_secret.json and save it in secrets folder, remember to add it to .env file
- Set up conset screen
- PUBSUB: Create topic and subscription
- Install python libraries: pip install --upgrade google-cloud-pubsub
- Set upp application default credentials: https://cloud.google.com/docs/authentication/provide-credentials-adc#how-to
- Cloud storage: Bucket - https://storage.googleapis.com/langrenn-photo/result2.jpg
  - Hint: Set to publicly available and allUsers principals, role Viewer

Denne fila _skal_ ligge i .dockerignore og .gitignore

## Referanser
Dokumentasjon: <https://langrenn-sprint.github.io/docs/>
aiohttp: <https://docs.aiohttp.org/>
Googel OAuth2: <https://developers.google.com/identity/protocols/oauth2>
Google Photos API: <https://developers.google.com/photos/library/guides/get-started>


## Docker clean up
docker compose down
docker network prune
docker container prune
docker rmi $(docker images -q)
