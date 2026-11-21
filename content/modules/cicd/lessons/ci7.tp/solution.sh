#!/usr/bin/env bash
# Solution de référence du TP ci7.
set -euo pipefail
cat > diagnostic.yaml <<'DIAG'
version-python: yaml
cache: cache
deploy: dependance
release: permissions
pull-request: declencheur
DIAG
cat > .github/workflows/ci.yml <<'WF'
name: CI
on:
  push:
    branches: [main]
    tags: ["v*"]
  pull_request:
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.10"
      - uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: pip-${{ runner.os }}-${{ hashFiles('requirements/*.txt') }}
      - run: pip install -r requirements/base.txt
      - run: pytest -q
  deploy:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    needs: [test]
    if: github.ref == 'refs/heads/main'
    environment: production
    steps:
      - uses: actions/checkout@v4
      - run: ./scripts/deploy.sh
  release:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    needs: [test]
    if: startsWith(github.ref, 'refs/tags/v')
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - run: gh release create "$GITHUB_REF_NAME" --generate-notes
        env:
          GH_TOKEN: ${{ github.token }}
WF
