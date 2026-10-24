#!/usr/bin/env bash
# Solution de référence du boss docker, phase 3.
set -euo pipefail
mkdir -p dockerboss
cd dockerboss
cat > Dockerfile <<'EOF'
FROM python:3.12-slim AS build
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
RUN useradd --uid 1000 --create-home app
COPY --from=build /install /usr/local
COPY --chown=app:app . .
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000')"]
CMD ["python", "app.py"]
EOF
cat > docker-compose.yml <<'EOF'
services:
  web:
    build: .
    read_only: true
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true
    ports:
      - "127.0.0.1:8000:8000"
    environment:
      DB_PASSWORD: ${DB_PASSWORD}
EOF
