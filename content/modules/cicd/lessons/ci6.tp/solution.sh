#!/usr/bin/env bash
# Solution de référence du TP ci6.
set -euo pipefail
mkdir -p .github/workflows
cat > .github/workflows/release.yml <<'EOF'
name: Release
on:
  push:
    tags: ["v*"]
permissions:
  contents: read
jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - run: mkdir -p dist && tar czf dist/app.tar.gz app.py requirements.txt
      - uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/
          retention-days: 7
  publish:
    needs: build
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: write
      id-token: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/
      - uses: aws-actions/configure-aws-credentials@e3dd6a429d7300a6a4c196c26e071d42e0343502
        with:
          role-to-assume: arn:aws:iam::123456789012:role/release
          aws-region: eu-west-3
      - run: aws s3 cp dist/app.tar.gz s3://releases-exemple/
      - env:
          GH_TOKEN: ${{ github.token }}
        run: gh release create "$GITHUB_REF_NAME" dist/*
EOF
