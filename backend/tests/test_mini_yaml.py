"""The minimal YAML reader shared by the cicd and k8s checkers."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "content" / "modules"


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(f"y_{path.parent.parent.name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


Y = _load(ROOT / "cicd" / "lessons" / "_yaml.py")

WORKFLOW = """\
name: CI   # nom
on:
  push:
    branches: [main]
  pull_request:
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - name: Tests
        run: |
          pip install -r requirements.txt
          pytest -q
      - name: Fusion
        run: >
          echo a
          echo b
      - run: echo "${{ secrets.TOKEN }}"
"""


def test_workflow_parses():
    d = Y.load(WORKFLOW)
    assert d["name"] == "CI" and d["on"]["push"]["branches"] == ["main"] and d["on"]["pull_request"] is None
    assert d["permissions"] == {"contents": "read"}
    steps = d["jobs"]["test"]["steps"]
    assert d["jobs"]["test"]["strategy"]["matrix"]["python-version"] == ["3.11", "3.12"]
    assert steps[0] == {"uses": "actions/checkout@v4"}
    assert steps[1]["run"] == "pip install -r requirements.txt\npytest -q\n"
    assert steps[2]["run"] == "echo a echo b\n"
    assert steps[3]["run"] == 'echo "${{ secrets.TOKEN }}"'


def test_literal_keeps_hash_and_blank_lines():
    d = Y.load("run: |\n  echo # reste\n\n  echo fin\nnext: 1\n")
    assert d == {"run": "echo # reste\n\necho fin\n", "next": 1}


def test_multi_document_and_sequences_at_parent_indent():
    docs = Y.load_all("apiVersion: v1\nkind: ConfigMap\ndata:\n  a: \"1\"\n---\nkind: Pod\nitems:\n- a\n- b: 2\n  c: 3\n")
    assert docs[0] == {"apiVersion": "v1", "kind": "ConfigMap", "data": {"a": "1"}}
    assert docs[1] == {"kind": "Pod", "items": ["a", {"b": 2, "c": 3}]}


def test_flow_and_scalars():
    d = Y.load("a: [1, two, 'three']\nb: {x: 1, y: true}\nc: ~\nd: 1.5\ne: no\n")
    assert d == {"a": [1, "two", "three"], "b": {"x": 1, "y": True}, "c": None, "d": 1.5, "e": "no"}


def test_empty_stream_and_comments_only():
    assert Y.load_all("# rien\n\n") == []


@pytest.mark.parametrize("text", [
    "a: 1\na: 2\n",              # clé dupliquée
    "a: [1, 2\n",               # liste non fermée
    "a: &ancre 1\n",            # ancre non gérée
    "\ta: 1\n",                 # tabulation
    "a:\n  b: 1\n c: 2\n",      # indentation incohérente
    "just text\nmore: 1\n",     # scalaire puis clé
])
def test_invalid_yaml_rejected(text):
    with pytest.raises(Y.YamlError):
        Y.load(text)
