#!/usr/bin/env bash
# Solution de référence, étape 1 du projet : la CI de test.
set -euo pipefail
for f in app requirements.txt; do [ -e "$f" ] || cp -r "$LESSON_DIR/seed/$f" .; done
mkdir -p .github/workflows
cat > .github/workflows/ci.yml <<'WF'
name: CI
on:
  push:
    branches: [main]
  pull_request:
permissions:
  contents: read
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install -r requirements.txt
      - run: pytest -q
WF
