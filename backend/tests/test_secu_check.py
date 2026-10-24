"""The security checker must pass the fixed code and refuse each vulnerable or over-eager variant."""
import re
import subprocess
import sys
from pathlib import Path

import pytest

LESSONS = Path(__file__).resolve().parents[2] / "content" / "modules" / "secu" / "lessons"
CHECKER = LESSONS / "_secu_check.py"


def _solution(tp: str) -> tuple[str, str]:
    text = (LESSONS / f"{tp}.tp" / "solution.sh").read_text(encoding="utf-8")
    m = re.search(r"cat > (\S+) <<'EOF'\n(.*?)\nEOF", text, re.S)
    return m.group(1), m.group(2) + "\n"


def _seed(tp: str, name: str) -> str:
    return (LESSONS / f"{tp}.tp" / "seed" / name).read_text(encoding="utf-8")


def run(tmp_path, tp, name, text):
    (tmp_path / name).write_text(text, encoding="utf-8")
    r = subprocess.run([sys.executable, "-I", "-B", str(CHECKER), tp], cwd=tmp_path, capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout


@pytest.mark.parametrize("tp", ["sc1", "sc2", "sc3"])
def test_reference_solution_passes(tmp_path, tp):
    name, text = _solution(tp)
    code, out = run(tmp_path, tp, name, text)
    assert code == 0, out


@pytest.mark.parametrize("tp", ["sc1", "sc2", "sc3"])
def test_vulnerable_seed_refused(tmp_path, tp):
    name, _ = _solution(tp)
    code, out = run(tmp_path, tp, name, _seed(tp, name))
    assert code == 1 and out.startswith("ECHEC"), out


SC1_FIX = '''import subprocess


def find_user(conn, name):
    return conn.execute("SELECT id, name FROM users WHERE name = ?", (name,)).fetchall()
'''

MUT = [
    # sc1 : défenses « maison » ou incomplètes
    ("sc1", 'conn.execute("SELECT id, name FROM users WHERE name = ?", (name,))',
     "conn.execute(\"SELECT id, name FROM users WHERE name = '\" + name + \"'\")", "o'brien"),
    ("sc1", 'conn.execute("SELECT id, name FROM users WHERE name = ?", (name,))',
     "conn.execute(\"SELECT id, name FROM users WHERE name = '\" + name.replace(\"'\", \"\") + \"'\")", "apostrophe"),
    ("sc1", '["wc", "-l", "--", path], capture_output=True, text=True, check=True)',
     '"wc -l " + path, shell=True, capture_output=True, text=True)', "shell=True"),
    ("sc1", '["wc", "-l", "--", path], capture_output=True, text=True, check=True)',
     '"wc -l \'" + path + "\'", shell=True, capture_output=True, text=True)', "shell=True"),
    ("sc1", '["wc", "-l", "--", path], capture_output=True, text=True, check=True).stdout\n    return int(out.split()[0])',
     '["wc", "-l", "--", path.split()[0]], capture_output=True, text=True, check=True).stdout\n    return int(out.split()[0])', "count_lines"),
    # sc2
    ("sc2", "html.escape(author)", "author", "échappez"),
    ("sc2", 'html.escape(text)', "text", "balises"),
    ("sc2", "html.escape(text)", "(text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))", "guillemets"),
    ("sc2", "if os.path.commonpath([base, path]) != base:", "if not path.startswith(base):", "dossier voisin"),
    ("sc2", "os.path.realpath(os.path.join(base, filename))", "os.path.abspath(os.path.join(base, filename))", "lien symbolique"),
    # sc3
    ("sc3", "salt = os.urandom(16)", "salt = b'0123456789abcdef'", "sel"),
    ("sc3", "hmac.compare_digest(_hash(password, salt), expected)", "_hash(password, salt) == expected", "compare_digest"),
    ("sc3", "hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)", "hashlib.sha256(salt + password.encode()).digest()", "hachage lent"),
    ("sc3", "    if len(password) < 8:\n        raise ValueError(\"mot de passe trop court\")\n", "", "moins de 8"),
    ("sc3", "    if entry is None:\n        return False\n", "", "inconnu"),
    ("sc3", 'return os.environ["APP_SECRET_KEY"]', 'return os.environ.get("APP_SECRET_KEY", "dev-secret-123")', "en dur"),
    ("sc3", 'return os.environ["APP_SECRET_KEY"]', 'return os.environ.get("APP_SECRET_KEY", "defaut")', "valeur par défaut"),
]


@pytest.mark.parametrize("tp,old,new,expected", MUT, ids=[f"{m[0]}-{i}" for i, m in enumerate(MUT)])
def test_weak_fix_refused(tmp_path, tp, old, new, expected):
    name, text = _solution(tp)
    assert old in text, old
    code, out = run(tmp_path, tp, name, text.replace(old, new, 1))
    assert code == 1 and expected in out, out
