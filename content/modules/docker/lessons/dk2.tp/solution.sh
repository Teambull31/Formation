#!/usr/bin/env bash
# Solution de référence du TP dk2.
set -euo pipefail
cat > Dockerfile <<'EOF'
FROM python:3.12-slim AS build
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
COPY --from=build /install /usr/local
COPY . .
CMD ["python", "app.py"]
EOF
cat > .dockerignore <<'EOF'
.git
.env
__pycache__
EOF
