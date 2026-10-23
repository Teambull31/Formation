import io
import json
import zipfile

import pytest

from app.portfolio import leak_reason


@pytest.mark.parametrize("text,why", [
    ("hello world", None),
    ("contact: moi@example.test", None),
    ("contact: jean.dupont@gmail.com", "adresse e-mail"),
    ("DB_PASSWORD=hunter2222", "secret en clair"),
    ('api_key = "sk-abcdef123456"', "secret en clair"),
    ("DB_PASSWORD: ${DB_PASSWORD}", None),
    ("password = var.db_password", None),
    ("token: <votre-jeton>", None),
    ('{"db_password": "hunter2222"}', "secret en clair"),
    ("ENV API_TOKEN abcdef123456", "secret en clair"),
    ("ARG DB_PASSWORD=hunter2222", "secret en clair"),
    ("ENV API_TOKEN ${API_TOKEN}", None),
    ('variable "db" {\n  sensitive = true\n  default   = "x"\n}', "secret en clair"),
    ('variable "db" {\n  sensitive = true\n}', None),
    ("secret_key = abcdef123456", "secret en clair"),
])
def test_leak_reason(text, why):
    assert leak_reason(text) == why


def _flag_demo(tmp_path):
    p = tmp_path / "content" / "modules" / "demo" / "module.json"
    meta = json.loads(p.read_text(encoding="utf-8"))
    meta["portfolio"] = True
    p.write_text(json.dumps(meta), encoding="utf-8")


def _zip(client):
    r = client.get("/api/portfolio.zip")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert "attachment" in r.headers["content-disposition"]
    return zipfile.ZipFile(io.BytesIO(r.content))


def _pass_t1(client, tmp_path):
    client.post("/api/tp/t1/start")
    (tmp_path / "ws" / "ok.txt").write_text("x")
    assert client.post("/api/tp/t1/check").json()["passed"]


def test_zip_has_readme_even_when_nothing_done(client):
    z = _zip(client)
    assert z.namelist() == ["README.md"]
    assert "Aucun pour l'instant" in z.read("README.md").decode()


def test_unflagged_module_is_never_exported(client, tmp_path):
    _pass_t1(client, tmp_path)
    assert _zip(client).namelist() == ["README.md"]  # demo module has no "portfolio": true


def test_passed_tp_files_are_exported_and_leaks_excluded(client, tmp_path):
    _flag_demo(tmp_path)
    _pass_t1(client, tmp_path)
    target = tmp_path / "ws"
    (target / "main.tf").write_text('resource "x" "y" {}\n')
    (target / "notes.txt").write_text("mon mail: vrai.nom@gmail.com\n")
    (target / "creds.txt").write_text("API_TOKEN=abcdef123456\n")
    (target / ".env").write_text("A=1\n")
    (target / "terraform.tfstate").write_text("{}")
    (target / "prod.tfvars.json").write_text("{}")
    (target / "x.auto.tfvars").write_text("a = 1\n")
    (target / "terraform.tfstate.backup").write_text("{}")
    (target / ".gitignore").write_text("*.tfstate\n")
    (target / "link").symlink_to("/etc/passwd")
    z = _zip(client)
    names = z.namelist()
    readme = z.read("README.md").decode()
    exported = [n for n in names if n != "README.md"]
    assert any(n.endswith("main.tf") for n in exported) and any(n.endswith(".gitignore") for n in exported)
    for bad in ("notes.txt", "creds.txt", ".env", "terraform.tfstate", "prod.tfvars.json", "x.auto.tfvars", "terraform.tfstate.backup", "link"):
        assert not any(n.endswith(bad) for n in exported), bad
    assert "adresse e-mail détecté" in readme and "secret en clair détecté" in readme
    assert "vrai.nom@gmail.com" not in readme and "abcdef123456" not in readme  # excluded content never leaks into the README


def test_readme_lists_rank_skills(client, tmp_path):
    _flag_demo(tmp_path)
    client.post("/api/quest/step", json={"kind": "lesson", "lesson_id": "l1"})
    readme = _zip(client).read("README.md").decode()
    assert "**Rang :** Bronze" in readme and "| demo | 20 |" in readme
