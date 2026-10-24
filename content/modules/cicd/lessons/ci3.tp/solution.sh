#!/usr/bin/env bash
# Solution de référence du TP ci3.
set -euo pipefail
mkdir -p .github/workflows
cat > .github/workflows/deploy.yml <<'EOF'
name: Deploy
on:
  push:
    branches: [main]
permissions:
  contents: read
jobs:
  deploy:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: acme/deploy-action@3f1d6a9c5b7e2d4a8c0f1e2d3b4a5c6d7e8f9a0b
        with:
          api_token: ${{ secrets.DEPLOY_TOKEN }}
      - name: Annoncer
        env:
          TITLE: ${{ github.event.head_commit.message }}
        run: echo "Déploiement de $TITLE"
EOF
