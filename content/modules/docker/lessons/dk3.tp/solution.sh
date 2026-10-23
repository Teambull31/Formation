#!/usr/bin/env bash
# Solution de référence du TP dk3.
set -euo pipefail
cat > Dockerfile <<'EOF'
FROM python:3.12-slim
WORKDIR /app
RUN useradd --uid 1000 --create-home app
COPY --chown=app:app app.py .
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
