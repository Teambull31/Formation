import shutil
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.main import create_app
from app.security import INTERNAL_HEADER, clean_env, is_trusted
from app.terminal import register_terminal

FIXTURES = Path(__file__).parent / "fixtures"
SECRET = "s3cret-interne"
REMOTE = ("203.0.113.9", 50000)
LOCAL = ("127.0.0.1", 50000)


@pytest.fixture
def secret_env(monkeypatch):
    monkeypatch.setenv("QUESTFORGE_INTERNAL_SECRET", SECRET)
    monkeypatch.setenv("QUESTFORGE_PASSWORD", "mot-de-passe-du-serveur")


@pytest.fixture
def app(tmp_path):
    content = tmp_path / "content"
    (content / "modules").mkdir(parents=True)
    shutil.copytree(FIXTURES / "demo_module", content / "modules" / "demo")
    return create_app(db_path=str(tmp_path / "s.db"), content_dir=content, workspace=tmp_path / "ws")


def client_for(app, peer, headers=None):
    return TestClient(app, client=peer, headers=headers or {})


# --- is_trusted ---------------------------------------------------------------


def test_direct_local_access_is_trusted():
    assert is_trusted("127.0.0.1", {})
    assert is_trusted("::1", {})


def test_remote_access_is_not_trusted():
    assert not is_trusted("203.0.113.9", {})


def test_relayed_request_from_loopback_is_not_trusted_without_the_secret():
    # le relais Node tourne sur la même machine : l'adresse source seule ne prouve rien
    assert not is_trusted("127.0.0.1", {"x-forwarded-for": "203.0.113.9"})


def test_secret_header_is_trusted_even_from_a_remote_peer(secret_env):
    assert is_trusted("203.0.113.9", {INTERNAL_HEADER: SECRET})


def test_wrong_secret_is_not_trusted(secret_env):
    assert not is_trusted("203.0.113.9", {INTERNAL_HEADER: "devine"})
    assert not is_trusted("127.0.0.1", {INTERNAL_HEADER: "devine"})


def test_header_alone_proves_nothing_when_no_secret_is_configured(monkeypatch):
    monkeypatch.delenv("QUESTFORGE_INTERNAL_SECRET", raising=False)
    assert not is_trusted("127.0.0.1", {INTERNAL_HEADER: "n-importe-quoi"})
    assert not is_trusted("203.0.113.9", {INTERNAL_HEADER: ""})


# --- routes HTTP ----------------------------------------------------------------

PRIVILEGED = [
    ("post", "/api/tp/tp1/check", None),
    ("post", "/api/boss/attempt", None),
    ("post", "/api/weekly/import", {"path": "/tmp"}),
]


@pytest.mark.parametrize("method, path, body", PRIVILEGED)
def test_privileged_routes_refuse_remote_and_relayed_requests(app, secret_env, method, path, body):
    remote = client_for(app, REMOTE)
    assert getattr(remote, method)(path, json=body).status_code == 403
    relayed = client_for(app, LOCAL, {"x-forwarded-for": "203.0.113.9"})
    assert getattr(relayed, method)(path, json=body).status_code == 403


@pytest.mark.parametrize("method, path, body", PRIVILEGED[:2])
def test_privileged_routes_accept_authenticated_relay(app, secret_env, method, path, body):
    relayed = client_for(app, LOCAL, {"x-forwarded-for": "203.0.113.9", INTERNAL_HEADER: SECRET})
    assert getattr(relayed, method)(path, json=body).status_code != 403


def test_read_only_routes_stay_open_to_remote_clients(app):
    assert client_for(app, REMOTE).get("/api/quest").status_code == 200


# --- terminal -------------------------------------------------------------------


def read_until(ws, target: bytes, timeout: float = 4.0) -> bytes:
    start, out = time.time(), b""
    while time.time() - start < timeout:
        try:
            out += ws.receive_bytes()
        except Exception:
            break
        if target in out:
            break
    return out


@pytest.fixture
def terminal_app(tmp_path):
    app = FastAPI()
    register_terminal(app, tmp_path)
    return app


def test_terminal_refuses_remote_without_secret(terminal_app, secret_env):
    from fastapi import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client_for(terminal_app, REMOTE).websocket_connect("/ws/terminal"):
            pass


def test_terminal_accepts_authenticated_relay_and_hides_server_secrets(terminal_app, secret_env):
    headers = {INTERNAL_HEADER: SECRET, "x-forwarded-for": "203.0.113.9"}
    with client_for(terminal_app, REMOTE, headers).websocket_connect("/ws/terminal") as ws:
        ws.send_text('echo "A[$QUESTFORGE_PASSWORD]B[$QUESTFORGE_INTERNAL_SECRET]C"\n')
        out = read_until(ws, b"C\r\n").replace(b"\r", b"")
    assert b"A[]B[]C" in out
    assert b"mot-de-passe-du-serveur" not in out and SECRET.encode() not in out


# --- environnement des processus de l'apprenant -----------------------------------


def test_clean_env_removes_server_secrets(secret_env):
    env = clean_env()
    assert "QUESTFORGE_PASSWORD" not in env and "QUESTFORGE_INTERNAL_SECRET" not in env
    assert "PATH" in env


def test_tp_check_scripts_cannot_read_server_secrets(tmp_path, secret_env):
    from app.content import Tp
    from app.tp import run_check

    tp = Tp(id="t", title="t", instructions_md="", check='echo "[$QUESTFORGE_PASSWORD][$QUESTFORGE_INTERNAL_SECRET]"; exit 1', hints=["h"])
    res = run_check(tp, tmp_path, tmp_path)
    assert res.output.strip() == "[][]"
