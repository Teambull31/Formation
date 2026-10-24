"""The Linux module checker must refuse each wrong variant of the reference solutions."""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

LESSONS = Path(__file__).resolve().parents[2] / "content" / "modules" / "linux" / "lessons"
CHECKER = LESSONS / "_linux_check.py"


def _heredocs(tp: str) -> dict[str, str]:
    text = (LESSONS / f"{tp}.tp" / "solution.sh").read_text(encoding="utf-8")
    return {m.group(1): m.group(2) + "\n" for m in re.finditer(r"cat > (\S+) <<'EOF'\n(.*?)\nEOF", text, re.S)}


def run(cwd, tp):
    r = subprocess.run([sys.executable, "-I", "-B", str(CHECKER), tp], cwd=cwd, capture_output=True, text=True, timeout=30)
    return r.returncode, r.stdout


def lx1_dir(tmp_path, deploy=0o750, secrets=0o600, shared=0o770):
    (tmp_path / "deploy.sh").write_text("#!/bin/sh\n")
    (tmp_path / "secrets.env").write_text("A=1\n")
    (tmp_path / "shared").mkdir()
    os.chmod(tmp_path / "deploy.sh", deploy)
    os.chmod(tmp_path / "secrets.env", secrets)
    os.chmod(tmp_path / "shared", shared)
    return tmp_path


def test_lx1_reference_passes(tmp_path):
    assert run(lx1_dir(tmp_path), "lx1")[0] == 0


@pytest.mark.parametrize("kw,expected", [
    ({"secrets": 0o644}, "secrets.env"),
    ({"secrets": 0o640}, "secrets.env"),
    ({"deploy": 0o640}, "exécutable"),
    ({"deploy": 0o770}, "groupe"),
    ({"deploy": 0o757}, "tout le monde"),
    ({"shared": 0o777}, "shared/"),
    ({"shared": 0o750}, "shared/"),
])
def test_lx1_wrong_modes_refused(tmp_path, kw, expected):
    code, out = run(lx1_dir(tmp_path, **kw), "lx1")
    assert code == 1 and expected in out, out


def test_lx1_symlink_refused(tmp_path):
    d = lx1_dir(tmp_path)
    (d / "secrets.env").unlink()
    (d / "secrets.env").symlink_to("/etc/hostname")
    assert run(d, "lx1")[0] == 1


def _lx2(tmp_path, top, err):
    (tmp_path / "top_ips.sh").write_text(top)
    (tmp_path / "errors_5xx.sh").write_text(err)
    return run(tmp_path, "lx2")


def test_lx2_reference_passes(tmp_path):
    files = _heredocs("lx2")
    assert _lx2(tmp_path, files["top_ips.sh"], files["errors_5xx.sh"])[0] == 0


@pytest.mark.parametrize("which,old,new,expected", [
    ("top", "sort -rn | head -3", "sort -n | head -3", "top_ips.sh donne"),
    ("top", "head -3", "head -2", "exactement 3 lignes"),
    ("top", "sort | uniq -c", "uniq -c", "top_ips.sh donne"),
    ("err", ">= 500", "== 500", "errors_5xx.sh compte"),
    ("err", "print n+0", "print n", "quand il n'y a aucune erreur"),
])
def test_lx2_wrong_filters_refused(tmp_path, which, old, new, expected):
    files = _heredocs("lx2")
    top, err = files["top_ips.sh"], files["errors_5xx.sh"]
    if which == "top":
        assert old in top
        top = top.replace(old, new, 1)
    else:
        assert old in err
        err = err.replace(old, new, 1)
    code, out = _lx2(tmp_path, top, err)
    assert code == 1 and expected in out, out


def test_lx2_hardcoded_answer_refused(tmp_path):
    code, out = _lx2(tmp_path, "#!/bin/bash\necho '9 10.0.0.5'\necho '6 10.0.0.9'\necho '4 10.0.0.23'\n", "#!/bin/bash\necho 5\n")
    assert code == 1


def test_lx2_hanging_script_refused(tmp_path):
    code, out = _lx2(tmp_path, "#!/bin/bash\nsleep 30\n", "#!/bin/bash\necho 0\n")
    assert code == 1 and "ne se termine pas" in out


def _lx3(tmp_path, files):
    for name, text in files.items():
        (tmp_path / name).write_text(text)
    return run(tmp_path, "lx3")


def test_lx3_reference_passes(tmp_path):
    assert _lx3(tmp_path, _heredocs("lx3"))[0] == 0


MUT = [
    ("sshd_config", "PermitRootLogin no", "PermitRootLogin yes", "PermitRootLogin"),
    ("sshd_config", "PasswordAuthentication no", "PasswordAuthentication yes", "PasswordAuthentication"),
    ("sshd_config", "MaxAuthTries 3", "MaxAuthTries 10", "MaxAuthTries"),
    ("sshd_config", "X11Forwarding no", "X11Forwarding yes", "X11Forwarding"),
    ("sshd_config", "AllowUsers deploy\n", "", "AllowUsers"),
    # première valeur gagnante : une ancienne ligne permissive placée avant annule le durcissement
    ("sshd_config", "Port 22\n", "Port 22\nPermitRootLogin yes\n", "PermitRootLogin"),
    ("firewall.nft", "policy drop", "policy accept", "policy drop"),
    ("firewall.nft", "    iif \"lo\" accept\n", "", "boucle locale"),
    ("firewall.nft", "ct state established,related accept\n", "", "established"),
    ("firewall.nft", "{ 22, 443 }", "{ 22 }", "443"),
    ("firewall.nft", "{ 22, 443 }", "{ 22, 443, 5432 }", "5432"),
    ("firewall.nft", "    tcp dport", "    accept\n    tcp dport", "sans condition"),
]


@pytest.mark.parametrize("name,old,new,expected", MUT, ids=[f"{m[0]}-{i}" for i, m in enumerate(MUT)])
def test_lx3_insecure_variant_refused(tmp_path, name, old, new, expected):
    files = _heredocs("lx3")
    assert old in files[name], name
    files[name] = files[name].replace(old, new, 1)
    code, out = _lx3(tmp_path, files)
    assert code == 1 and expected in out, out
