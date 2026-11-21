#!/usr/bin/env bash
# Solution de référence du TP ci5.
set -euo pipefail
mkdir -p .github/workflows
cat > .github/workflows/deploy.yml <<'EOF'
name: Deploy
on:
  push:
    branches: [main]
  workflow_dispatch:
permissions:
  contents: read
jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    outputs:
      version: ${{ steps.meta.outputs.version }}
    steps:
      - uses: actions/checkout@v4
      - id: meta
        run: echo "version=1.0.${GITHUB_RUN_NUMBER}" >> "$GITHUB_OUTPUT"
  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    timeout-minutes: 15
    environment: staging
    steps:
      - env:
          VERSION: ${{ needs.build.outputs.version }}
        run: ./deploy.sh staging "$VERSION"
  deploy-production:
    needs: [build, deploy-staging]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    timeout-minutes: 15
    environment:
      name: production
      url: https://app.example.test
    concurrency:
      group: deploy-production
      cancel-in-progress: false
    steps:
      - env:
          VERSION: ${{ needs.build.outputs.version }}
        run: ./deploy.sh production "$VERSION"
EOF
