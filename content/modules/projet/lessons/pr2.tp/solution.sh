#!/usr/bin/env bash
# Solution de référence, étape 2 du projet : l'image et sa publication.
set -euo pipefail
LESSON_DIR="$LESSON_DIR/../pr1.tp" bash "$LESSON_DIR/../pr1.tp/solution.sh"
cat > Dockerfile <<'DF'
FROM python:3.12.7-slim AS deps
WORKDIR /src
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12.7-slim
WORKDIR /srv
COPY --from=deps /install /usr/local
COPY app/ ./app/
RUN useradd --create-home --uid 10001 app
USER 10001
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"
CMD ["python", "-m", "app.main"]
DF
printf '.git\n.github\n.env\n__pycache__\n*.tfstate*\ninfra/.terraform\n' > .dockerignore
cat >> .github/workflows/ci.yml <<'WF'
  image:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    needs: [test]
    if: github.ref == 'refs/heads/main'
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
      - run: echo "$GH_TOKEN" | docker login ghcr.io -u "$GITHUB_ACTOR" --password-stdin
        env:
          GH_TOKEN: ${{ github.token }}
      - run: |
          IMAGE="ghcr.io/${GITHUB_REPOSITORY,,}:${GITHUB_SHA}"
          docker build -t "$IMAGE" .
          docker push "$IMAGE"
WF
