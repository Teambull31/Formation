"""The CI/CD checker must refuse each unsafe or incomplete variant of the reference workflows."""
import re
import subprocess
import sys
from pathlib import Path

import pytest

LESSONS = Path(__file__).resolve().parents[2] / "content" / "modules" / "cicd" / "lessons"
CHECKER = LESSONS / "_cicd_check.py"


def _solution(tp: str) -> tuple[str, str]:
    text = (LESSONS / f"{tp}.tp" / "solution.sh").read_text(encoding="utf-8")
    m = re.search(r"cat > (\S+) <<'EOF'\n(.*?)\nEOF", text, re.S)
    return m.group(1), m.group(2) + "\n"


def run(tmp_path, tp, path, text):
    f = tmp_path / path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    r = subprocess.run([sys.executable, "-I", "-B", str(CHECKER), tp], cwd=tmp_path, capture_output=True, text=True, timeout=20)
    return r.returncode, r.stdout


@pytest.mark.parametrize("tp", ["ci1", "ci2", "ci3"])
def test_reference_solution_passes(tmp_path, tp):
    path, text = _solution(tp)
    code, out = run(tmp_path, tp, path, text)
    assert code == 0, out


MUT = [
    ("ci1", "  pull_request:\n", "", "pull_request"),
    ("ci1", "      - uses: actions/checkout@v4\n", "", "checkout"),
    ("ci1", "actions/checkout@v4", "actions/checkout@main", "épinglez"),
    ("ci1", "      - uses: actions/setup-python@v5\n        with:\n          python-version: \"3.12\"\n", "", "setup-python"),
    ("ci1", "      - run: pip install -r requirements.txt\n", "", "dépendances"),
    ("ci1", "runs-on: ubuntu-latest", "runs-on: windows-latest", "Linux"),
    ("ci1", "      - run: pytest -q\n", "      - run: echo ok\n", "pytest"),
    ("ci1", "jobs:\n", "jobs\n", "YAML"),
    ("ci2", "permissions:\n  contents: read\n", "", "permissions"),
    ("ci2", "contents: read", "contents: write", "permissions"),
    ("ci2", "  cancel-in-progress: true\n", "  cancel-in-progress: false\n", "concurrency"),
    ("ci2", "    needs: test\n", "", "needs"),
    ("ci2", "    timeout-minutes: 10\n    steps:\n      - uses: actions/checkout@v4\n      - run: python", "    steps:\n      - uses: actions/checkout@v4\n      - run: python", "timeout-minutes"),
    ("ci2", "[\"3.11\", \"3.12\"]", "[\"3.12\"]", "au moins deux"),
    ("ci2", "${{ matrix.python-version }}", "\"3.12\"", "matrice"),
    ("ci2", "          cache: pip\n", "", "cache"),
    ("ci2", "actions/checkout@v4\n      - run: python", "actions/checkout@main\n      - run: python", "branche mobile"),
    ("ci3", "  push:\n", "  pull_request_target:\n  push:\n", "pull_request_target"),
    ("ci3", "permissions:\n  contents: read\n", "permissions: write-all\n", "write-all"),
    ("ci3", "${{ secrets.DEPLOY_TOKEN }}", "abc123secret", "secret en clair"),
    ("ci3", "run: echo \"Déploiement de $TITLE\"", "run: echo \"Déploiement de ${{ github.event.pull_request.title }}\"", "injection"),
    ("ci3", "run: echo \"Déploiement de $TITLE\"", "run: ./deploy.sh ${{ secrets.DEPLOY_TOKEN }}", "expose le secret"),
    ("ci3", "@3f1d6a9c5b7e2d4a8c0f1e2d3b4a5c6d7e8f9a0b", "@v1", "SHA complet"),
    ("ci3", "@3f1d6a9c5b7e2d4a8c0f1e2d3b4a5c6d7e8f9a0b", "@3f1d6a9", "SHA complet"),
    ("ci3", "actions/checkout@v4", "actions/checkout@main", "version précise"),
]


@pytest.mark.parametrize("tp,old,new,expected", MUT, ids=[f"{m[0]}-{i}" for i, m in enumerate(MUT)])
def test_unsafe_variant_refused(tmp_path, tp, old, new, expected):
    path, text = _solution(tp)
    assert old in text, old
    code, out = run(tmp_path, tp, path, text.replace(old, new, 1))
    assert code == 1 and expected in out, out
