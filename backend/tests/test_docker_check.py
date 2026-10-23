"""The Docker module checker must refuse each insecure variant of the reference solutions."""
import re
import subprocess
import sys
from pathlib import Path

import pytest

LESSONS = Path(__file__).resolve().parents[2] / "content" / "modules" / "docker" / "lessons"
CHECKER = LESSONS / "_docker_check.py"


def _solution_files(tp: str) -> dict[str, str]:
    """Run the reference solution text through bash heredoc parsing without executing it: parse cat > f <<'EOF'."""
    text = (LESSONS / f"{tp}.tp" / "solution.sh").read_text(encoding="utf-8")
    return {m.group(1): m.group(2) + "\n" for m in re.finditer(r"cat > (\S+) <<'EOF'\n(.*?)\nEOF", text, re.S)}


def run(tmp_path, tp, files):
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    r = subprocess.run([sys.executable, "-I", "-B", str(CHECKER), tp], cwd=tmp_path, capture_output=True, text=True, timeout=20)
    return r.returncode, r.stdout


@pytest.mark.parametrize("tp", ["dk1", "dk2", "dk3"])
def test_reference_solution_passes(tmp_path, tp):
    code, out = run(tmp_path, tp, _solution_files(tp))
    assert code == 0, out


MUTATIONS = [
    ("dk1", "Dockerfile", "python:3.12-slim", "python", "version"),
    ("dk1", "Dockerfile", 'CMD ["python", "app.py"]', "CMD python app.py", "forme exec"),
    ("dk1", "Dockerfile", 'CMD ["python", "app.py"]', "CMD ['python', 'app.py']", "JSON"),
    ("dk1", "Dockerfile", "WORKDIR /app", "WORKDIR app", "WORKDIR"),
    ("dk2", "Dockerfile", "--no-cache-dir ", "", "no-cache-dir"),
    ("dk2", "Dockerfile", "COPY requirements.txt .\n", "COPY . .\n", "AVANT pip install"),
    ("dk2", ".dockerignore", ".env\n", "", ".env"),
    ("dk3", "Dockerfile", "USER app\n", "", "USER"),
    ("dk3", "Dockerfile", "USER app\n", "USER root\n", "root"),
    ("dk3", "Dockerfile", "RUN useradd --uid 1000 --create-home app\n", "", "créé nulle part"),
    ("dk3", "Dockerfile", "EXPOSE 8000\n", "EXPOSE 8000\nENV API_TOKEN=abc123\n", "secret en clair"),
    ("dk3", "Dockerfile", "HEALTHCHECK --interval=30s CMD", "HEALTHCHECK NONE #", "HEALTHCHECK"),
    ("dk3", "docker-compose.yml", "    read_only: true\n", "", "read_only"),
    ("dk3", "docker-compose.yml", "      - ALL\n", "      - NET_RAW\n", "cap_drop"),
    ("dk3", "docker-compose.yml", "      - no-new-privileges:true\n", "      - seccomp=unconfined\n", "no-new-privileges"),
    ("dk3", "docker-compose.yml", "127.0.0.1:8000:8000", "8000:8000", "toutes les interfaces"),
    ("dk3", "docker-compose.yml", "    build: .\n", "    build: .\n    privileged: true\n", "privileged"),
    ("dk3", "docker-compose.yml", "    build: .\n", "    build: .\n    volumes:\n      - /var/run/docker.sock:/var/run/docker.sock\n", "docker.sock"),
    ("dk3", "docker-compose.yml", "${DB_PASSWORD}", "hunter2", "secret en clair"),
]


@pytest.mark.parametrize("tp,name,old,new,expected", MUTATIONS, ids=[f"{m[0]}-{m[4]}-{i}" for i, m in enumerate(MUTATIONS)])
def test_insecure_variant_refused(tmp_path, tp, name, old, new, expected):
    files = _solution_files(tp)
    assert old in files[name], f"mutation does not apply to {name}"
    files[name] = files[name].replace(old, new, 1)
    code, out = run(tmp_path, tp, files)
    assert code == 1 and expected in out, out
