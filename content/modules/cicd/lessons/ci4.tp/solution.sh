#!/usr/bin/env bash
# Solution de référence du TP ci4.
set -euo pipefail
mkdir -p .github/workflows .github/actions/setup
cat > .github/actions/setup/action.yml <<'EOF'
name: Préparer Python
inputs:
  python-version:
    description: Version de Python
    required: true
runs:
  using: composite
  steps:
    - uses: actions/setup-python@v5
      with:
        python-version: ${{ inputs.python-version }}
        cache: pip
    - run: pip install -r requirements.txt
      shell: bash
EOF
cat > .github/workflows/reusable-test.yml <<'EOF'
name: Tests réutilisables
on:
  workflow_call:
    inputs:
      python-version:
        type: string
        required: true
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/setup
        with:
          python-version: ${{ inputs.python-version }}
      - run: pytest -q
EOF
cat > .github/workflows/ci.yml <<'EOF'
name: CI
on:
  push:
  pull_request:
permissions:
  contents: read
jobs:
  test:
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    uses: ./.github/workflows/reusable-test.yml
    with:
      python-version: ${{ matrix.python-version }}
EOF
