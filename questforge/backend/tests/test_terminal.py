import time
from pathlib import Path
import pytest
from fastapi import FastAPI, WebSocketDisconnect
from starlette.testclient import TestClient
from app.terminal import is_local, register_terminal


def test_is_local():
    assert is_local("127.0.0.1")
    assert is_local("::1")
    assert not is_local("192.168.1.20")
    assert not is_local(None)


def read_until(ws, target: bytes, timeout: float = 3.0) -> bytes:
    start = time.time()
    accum = b""
    while time.time() - start < timeout:
        try:
            data = ws.receive_bytes()
            accum += data
            if target in accum:
                return accum
        except Exception:
            break
    return accum


@pytest.fixture
def local_app(tmp_path):
    app = FastAPI()
    register_terminal(app, tmp_path)
    return app


@pytest.fixture
def client(local_app):
    return TestClient(local_app, client=("127.0.0.1", 50000))


@pytest.fixture
def remote_client(local_app):
    return TestClient(local_app, client=("192.168.1.20", 50000))


def test_terminal_echoes_command_output(client):
    with client.websocket_connect("/ws/terminal") as ws:
        # Give bash a moment to spawn and echo prompt
        time.sleep(0.1)
        ws.send_bytes(b"echo salut\n")
        out = read_until(ws, b"salut", timeout=3.0)
        assert b"salut" in out


def test_terminal_rejects_remote_client(remote_client):
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with remote_client.websocket_connect("/ws/terminal") as ws:
            ws.receive_bytes()
    assert exc_info.value.code == 1008
