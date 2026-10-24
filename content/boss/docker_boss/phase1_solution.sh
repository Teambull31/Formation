#!/usr/bin/env bash
# Solution de référence du boss docker, phase 1.
set -euo pipefail
mkdir -p dockerboss
cd dockerboss
echo 'print("ok")' > app.py
cat > Dockerfile <<'EOF'
FROM python:3.12-slim
WORKDIR /app
COPY app.py .
EXPOSE 8000
CMD ["python", "app.py"]
EOF
