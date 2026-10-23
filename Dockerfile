# syntax=docker/dockerfile:1
# Formation : front React (construit ici) + backend FastAPI qui sert frontend/dist. Pas de relais Node.

# --- 1. Build du front ---
FROM node:22-bookworm-slim AS build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- 2. Exécution ---
FROM python:3.12-slim-bookworm
# espeak-ng : audio des leçons ; curl, jq : outils des TP.
RUN apt-get update \
 && apt-get install -y --no-install-recommends espeak-ng curl jq ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.8.0 /uv /usr/local/bin/uv

# Même arborescence que le dépôt : main.py cherche ../../frontend/dist et ../../content.
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/app ./app
COPY content /app/content
COPY --from=build /app/frontend/dist /app/frontend/dist

RUN useradd --uid 1000 --create-home --home-dir /data --shell /bin/bash formation \
 && mkdir -p /data/workspace && chown -R formation:formation /data /app/content
ENV PATH="/app/backend/.venv/bin:${PATH}" \
    HOME=/data \
    FORMATION_DB=/data/formation.db \
    FORMATION_WORKSPACE=/data/workspace \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
# /data est chown à l'uid 1000. Avec un APP_UID différent (compose `user:`), un volume nommé neuf
# est créé root : chown-le une fois (docker run --rm -v formation_formation-data:/data alpine chown UID:GID /data)
# ou gardez APP_UID=1000.
VOLUME /data
USER formation

EXPOSE 8000
# 401 = serveur vivant mais mot de passe requis : c'est sain.
COPY --chmod=755 scripts/healthcheck.py /usr/local/bin/healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD ["python", "/usr/local/bin/healthcheck"]

CMD ["uvicorn", "app.main:app_factory", "--factory", "--host", "0.0.0.0", "--port", "8000"]
