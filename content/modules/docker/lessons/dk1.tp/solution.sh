#!/usr/bin/env bash
# Solution de référence du TP dk1.
set -euo pipefail
cat > Dockerfile <<'EOF'
FROM python:3.12-slim
WORKDIR /app
COPY app.py .
EXPOSE 8000
CMD ["python", "app.py"]
EOF
