#!/usr/bin/env bash
# Solution de référence du boss docker, phase 2.
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
COPY --from=build /install /usr/local
COPY . .
EXPOSE 8000
CMD ["python", "app.py"]
EOF
cat > .dockerignore <<'EOF'
.git
.env
__pycache__
EOF
