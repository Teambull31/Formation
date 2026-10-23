import base64

import pytest
from starlette.websockets import WebSocketDisconnect

from tests.conftest import app_client

PW = "correct-horse-battery"


def basic(pw, user="moi"):
    return {"Authorization": "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()}


@pytest.fixture
def secured(tmp_path):
    return app_client(tmp_path, "127.0.0.1", password=PW)


def test_no_password_unchanged(client):
    assert client.get("/api/quest").status_code == 200
    assert client.post("/api/tp/t1/start").status_code == 200


def test_http_requires_credentials(secured):
    for h in (None, basic("wrong-password-xx"), {"Authorization": "Basic !!!"}, {"Authorization": "Bearer x"}):
        r = secured.get("/api/quest", headers=h)
        assert r.status_code == 401
        assert r.headers["www-authenticate"].startswith("Basic")
    assert secured.get("/api/quest", headers=basic(PW)).status_code == 200
    assert secured.get("/api/quest", headers=basic(PW, user="")).status_code == 200


def test_password_with_colon_ok(tmp_path):
    c = app_client(tmp_path, "127.0.0.1", password="a:b:c:d:e:f:g:h")
    assert c.get("/api/quest", headers=basic("a:b:c:d:e:f:g:h")).status_code == 200


def test_ws_requires_credentials(secured):
    for h in ({}, basic("wrong-password-xx")):
        with pytest.raises(WebSocketDisconnect):
            with secured.websocket_connect("/ws/terminal", headers={"host": "localhost", **h}):
                pass
    with secured.websocket_connect("/ws/terminal", headers={"host": "localhost", **basic(PW)}) as ws:
        ws.send_bytes(b"exit\n")


def test_password_never_echoed(secured):
    r = secured.get("/api/quest", headers=basic("wrong-password-xx"))
    assert "wrong-password-xx" not in r.text and PW not in r.text
    assert PW not in secured.get("/api/quest", headers=basic(PW)).text


@pytest.mark.parametrize("pw", ["", "short", "elevenchars"])
def test_short_password_refuses_start(tmp_path, pw):
    with pytest.raises(RuntimeError) as e:
        app_client(tmp_path / "x", "127.0.0.1", password=pw)
    assert "12" in str(e.value)
    assert not pw or pw not in str(e.value)


def test_remote_exec_needs_password_and_hosts(tmp_path):
    with pytest.raises(RuntimeError):
        app_client(tmp_path / "a", "127.0.0.1", remote_exec=True, allowed_hosts=["a.example"])
    with pytest.raises(RuntimeError):
        app_client(tmp_path / "b", "127.0.0.1", password=PW, remote_exec=True)


def test_env_validation(monkeypatch, tmp_path):
    from app.main import app_factory

    monkeypatch.setenv("FORMATION_WORKSPACE", str(tmp_path / "w"))
    monkeypatch.setenv("FORMATION_DB", str(tmp_path / "d" / "f.db"))
    monkeypatch.setenv("FORMATION_PASSWORD", "tooshort")
    with pytest.raises(RuntimeError) as e:
        app_factory()
    assert "tooshort" not in str(e.value)
    monkeypatch.setenv("FORMATION_PASSWORD", PW)
    monkeypatch.setenv("FORMATION_REMOTE_EXEC", "1")
    with pytest.raises(RuntimeError):  # FORMATION_ALLOWED_HOSTS manquant
        app_factory()
    monkeypatch.setenv("FORMATION_ALLOWED_HOSTS", "Formation.Example, localhost")
    app_factory()


REMOTE = "formation.example"
SENSITIVE = [("post", "/api/tp/t1/start"), ("post", "/api/tp/t1/check"), ("post", "/api/boss/attempt"),
             ("post", "/api/weekly/import"), ("post", "/api/tp/t1/hint")]


def req(c, method, path, host, extra=None):
    body = {"json": {"path": "/x"}} if "import" in path else {"json": {"level": 1}} if "hint" in path else {}
    return getattr(c, method)(path, headers={"host": host, **basic(PW), **(extra or {})}, **body)


@pytest.mark.parametrize("method,path", SENSITIVE)
def test_remote_exec_off_refuses_remote_host(tmp_path, method, path):
    c = app_client(tmp_path, "10.0.0.5", base_url=f"http://{REMOTE}", password=PW)
    assert req(c, method, path, REMOTE).status_code == 403


def test_remote_exec_on_only_allowed_host(tmp_path):
    c = app_client(tmp_path, "172.18.0.2", base_url=f"http://{REMOTE}", password=PW,
                   remote_exec=True, allowed_hosts=[REMOTE])
    assert req(c, "post", "/api/tp/t1/start", REMOTE).status_code == 200
    assert req(c, "post", "/api/tp/t1/start", REMOTE.upper() + ":443").status_code == 200
    assert req(c, "post", "/api/tp/t1/start", "evil.example").status_code == 403
    assert req(c, "post", "/api/tp/t1/start", REMOTE, {"origin": "https://evil.example"}).status_code == 403
    assert req(c, "post", "/api/tp/t1/start", REMOTE, {"origin": f"http://{REMOTE}"}).status_code == 200
    assert c.post("/api/tp/t1/start", headers={"host": REMOTE}).status_code == 401
    assert c.get("/api/quest", headers={"host": REMOTE, **basic(PW)}).status_code == 200


def test_remote_exec_ws(tmp_path):
    c = app_client(tmp_path, "172.18.0.2", password=PW, remote_exec=True, allowed_hosts=[REMOTE])
    with c.websocket_connect("/ws/terminal", headers={"host": REMOTE, **basic(PW)}) as ws:
        ws.send_bytes(b"exit\n")
    for h in ({"host": "evil.example", **basic(PW)}, {"host": REMOTE}):
        with pytest.raises(WebSocketDisconnect):
            with c.websocket_connect("/ws/terminal", headers=h):
                pass
