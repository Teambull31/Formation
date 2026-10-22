#!/usr/bin/env bash
# Solution de référence du TP 6 : écrit ask.py dans le dossier du TP.
cat > ask.py <<'PY'
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "kit"))
from llm import generate, LlmUnavailable

try:
    print(generate(sys.argv[1], timeout=3))
except LlmUnavailable as e:
    print("(secours) Ollama indisponible")
    print(f"raison : {e}", file=sys.stderr)
PY
