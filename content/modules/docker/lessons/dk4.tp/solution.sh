#!/usr/bin/env bash
# Solution de référence du TP dk4.
set -euo pipefail
cat > diagnostic.yaml <<'DIAG'
build: contexte
api: ecoute
worker: memoire
db: volume
proxy: version
DIAG
printf '.git\n__pycache__\n.env\n' > .dockerignore
sed -i 's/"--host", "127.0.0.1"/"--host", "0.0.0.0"/' Dockerfile
cat > docker-compose.yml <<'YML'
services:
  api:
    build: .
    ports:
      - "127.0.0.1:8000:8000"
    environment:
      DATABASE_URL: ${DATABASE_URL}
  worker:
    build: .
    command: ["python", "-m", "app.worker"]
    mem_limit: 256m
  db:
    image: postgres:16.4
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
  proxy:
    image: nginx:1.27.2
    ports:
      - "127.0.0.1:8080:80"
volumes:
  pgdata:
YML
