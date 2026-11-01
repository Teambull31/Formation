import base64
import json
import shutil
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from app.content import ModuleError, load_module
from app.main import create_app

PW = "correct-horse-battery"
REMOTE = "formation.example"
FX = Path(__file__).parent / "fixtures"
AUTH = {"Authorization": "Basic " + base64.b64encode(f"moi:{PW}".encode()).decode()}
PLAIN, FLAGGED = "t1", "t2"  # ids des TP de la fixture demo ; t2 est marque local_only par _app


def _content(tmp_path):
    content = tmp_path / "content"
    shutil.copytree(FX / "demo_module", content / "modules" / "demo")
    shutil.copytree(FX / "demo_boss", content / "boss" / "demo_boss")
    shutil.copy(Path(__file__).parents[2] / "content" / "gacha.json", content / "gacha.json")
    return content


def _set(path: Path, value):
    d = json.loads(path.read_text())
    d["local_only"] = value
    path.write_text(json.dumps(d))


def _app(tmp_path, peer, base_url, **kw):
    content = _content(tmp_path)
    _set(content / "modules/demo/lessons/l2.tp/tp.json", True)
    _set(content / "boss/demo_boss/boss.json", True)
    ws = tmp_path / "ws"
    ws.mkdir()
    app = create_app(str(tmp_path / "f.db"), content, ws, **kw)
    return TestClient(app, base_url=base_url, client=(peer, 50000))


def _remote_app(tmp_path, peer="172.18.0.2"):
    return _app(tmp_path, peer, f"http://{REMOTE}", password=PW, remote_exec=True, allowed_hosts=[REMOTE])


def _post(c, path, host=REMOTE, extra=None):
    return c.post(path, headers={"host": host, **AUTH, **(extra or {})})


def test_fixture_ids(tmp_path):
    ids = [json.loads(p.read_text())["id"] for p in sorted(_content(tmp_path).glob("modules/demo/lessons/*.tp/tp.json"))]
    assert ids == [PLAIN, FLAGGED]


def test_cpp_tp_refused_for_remote_host(tmp_path):
    r = _post(_remote_app(tmp_path), f"/api/tp/{FLAGGED}/check")
    assert r.status_code == 403 and r.json()["detail"] == "Réservé à la machine locale"


def test_plain_tp_still_allowed_remotely(tmp_path):
    c = _remote_app(tmp_path)
    assert _post(c, f"/api/tp/{PLAIN}/check").status_code == 200
    assert _post(c, f"/api/tp/{FLAGGED}/start").status_code == 200  # copie du seed seulement


def test_cpp_tp_allowed_on_loopback(tmp_path):
    c = _app(tmp_path, "127.0.0.1", "http://localhost")
    assert c.post(f"/api/tp/{FLAGGED}/check").status_code == 200


def test_boss_local_only_refused_remotely(tmp_path):
    r = _post(_remote_app(tmp_path), "/api/boss/attempt")
    assert r.status_code == 403 and r.json()["detail"] == "Réservé à la machine locale"


def test_boss_local_only_allowed_on_loopback(tmp_path):
    c = _app(tmp_path, "127.0.0.1", "http://localhost")
    assert c.post("/api/boss/attempt").status_code == 200


def test_loopback_peer_with_remote_host_refused(tmp_path):
    # pair local derriere un proxy, Host = nom distant autorise : exec_ok vrai, strictly_local faux
    c = _remote_app(tmp_path, peer="127.0.0.1")
    assert _post(c, f"/api/tp/{FLAGGED}/check").status_code == 403
    assert _post(c, f"/api/tp/{FLAGGED}/check", extra={"X-Forwarded-For": "127.0.0.1"}).status_code == 403
    assert _post(c, f"/api/tp/{FLAGGED}/check", host="LOCALHOST:8000").status_code == 200
    assert _post(c, f"/api/tp/{FLAGGED}/check", host="localhost", extra={"origin": f"http://{REMOTE}"}).status_code == 403


@pytest.mark.parametrize("header", ["X-Forwarded-For", "Forwarded", "X-Real-IP", "Via"])
def test_relay_header_makes_a_loopback_peer_not_strictly_local(tmp_path, header):
    c = _app(tmp_path, "127.0.0.1", "http://localhost")
    assert c.post(f"/api/tp/{FLAGGED}/check").status_code == 200
    assert c.post(f"/api/tp/{FLAGGED}/check", headers={header: "203.0.113.9"}).status_code == 403


def test_ipv4_mapped_loopback_peer_ok_and_remote_peer_spoofing_host_refused(tmp_path):
    assert _post(_remote_app(tmp_path, "::ffff:127.0.0.1"), f"/api/tp/{FLAGGED}/check", host="localhost").status_code == 200
    assert _post(_remote_app(tmp_path / "b"), f"/api/tp/{FLAGGED}/check", host="localhost").status_code == 403


def test_tp_local_only_must_be_boolean(tmp_path):
    content = _content(tmp_path)
    _set(content / "modules/demo/lessons/l2.tp/tp.json", "oui")
    with pytest.raises(ModuleError, match="local_only"):
        load_module(content / "modules" / "demo")


def test_boss_local_only_must_be_boolean(tmp_path):
    content = _content(tmp_path)
    _set(content / "boss/demo_boss/boss.json", "oui")
    with pytest.raises(ValueError, match="local_only"):
        create_app(str(tmp_path / "f.db"), content, tmp_path)


def test_esp_modules_come_after_the_other_modules(tmp_path):
    """Les modules esp* passent après les autres (même alphabétiquement entre docker et k8s) : ils ne changent pas la quête du jour existante."""
    content = _content(tmp_path)
    for name in ("esp1", "k8s", "docker"):
        shutil.copytree(FX / "demo_module", content / "modules" / name)
        with open(content / "modules" / name / "lessons" / "l1.md", "a", encoding="utf-8") as f:
            f.write(f"\n\nMODULE-{name}\n")
    shutil.rmtree(content / "modules" / "demo")
    c = TestClient(create_app(str(tmp_path / "f.db"), content, tmp_path), base_url="http://localhost", client=("127.0.0.1", 50000))
    assert "MODULE-docker" in c.get("/api/lesson/l1").json()["body_md"]  # le premier trouvé : docker, puis k8s, esp1 en dernier
    shutil.rmtree(content / "modules" / "docker")
    shutil.rmtree(content / "modules" / "k8s")
    assert "MODULE-esp1" in c.get("/api/lesson/l1").json()["body_md"]
