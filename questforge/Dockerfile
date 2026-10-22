# QuestForge : front React + relais Node (authentification) + backend FastAPI, dans une seule image.
# syntax=docker/dockerfile:1

# --- 1. Build du front (les leçons de la démo sont lues dans content/ à la compilation) ---
FROM node:22-bookworm-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html vite.config.ts tsconfig.json ./
COPY src ./src
COPY content ./content
RUN npm run build

# --- 2. Image d'exécution ---
FROM node:22-bookworm-slim
# espeak-ng : audio des leçons ; vim, jq : outils proposés dans le terminal des TP.
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv espeak-ng vim jq curl ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir fastapi "uvicorn[standard]" httpx websockets pydantic

WORKDIR /app
COPY package.json package-lock.json ./
# tsx (qui lance server.ts) est une devDependency : on l'installe malgré NODE_ENV=production plus bas.
RUN npm ci --include=dev && npm cache clean --force
COPY server.ts tsconfig.json ./
COPY server ./server
COPY backend/app ./backend/app
COPY content ./content
COPY --from=build /app/dist ./dist

ENV NODE_ENV=production \
    PORT=3000 \
    HOST=0.0.0.0 \
    QUESTFORGE_DATA_DIR=/data \
    PATH="/opt/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# /data : base SQLite et dossier de travail des TP (volume). content/ doit rester inscriptible
# (cache audio, modules importés) : il est aussi monté en volume par docker-compose.
RUN mkdir -p /data && chown -R node:node /data /app/content
USER node

EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:'+(process.env.PORT||3000)+'/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node_modules/.bin/tsx", "server.ts"]
