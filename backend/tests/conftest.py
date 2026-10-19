import pytest

from app.db import connect


@pytest.fixture
def db():
    conn = connect(":memory:")
    yield conn
    conn.close()


def _terminal_client(tmp_path, host):
    from fastapi import FastAPI
    from starlette.testclient import TestClient

    from app.terminal import register_terminal

    app = FastAPI()
    register_terminal(app, workspace=tmp_path)
    class LocalhostClient(TestClient):
        # TestClient envoie Host: testserver pour les websockets; on simule un navigateur sur localhost
        def websocket_connect(self, url, subprotocols=None, **kw):
            kw["headers"] = {"host": "localhost:8000", **kw.get("headers", {})}
            return super().websocket_connect(url, subprotocols, **kw)

    return LocalhostClient(app, client=(host, 50000))


@pytest.fixture
def terminal_client(tmp_path):
    return _terminal_client(tmp_path, "127.0.0.1")


@pytest.fixture
def terminal_remote_client(tmp_path):
    return _terminal_client(tmp_path, "192.168.1.20")
