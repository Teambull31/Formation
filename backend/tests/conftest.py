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


def app_client(tmp_path, host, static_dir=None, base_url="http://localhost", **kw):
    import shutil
    from pathlib import Path

    from starlette.testclient import TestClient

    from app.main import create_app

    fx = Path(__file__).parent / "fixtures"
    content = tmp_path / "content"
    shutil.copytree(fx / "demo_module", content / "modules" / "demo")
    shutil.copytree(fx / "demo_boss", content / "boss" / "demo_boss")
    shutil.copy(Path(__file__).parents[2] / "content" / "gacha.json", content / "gacha.json")
    ws = tmp_path / "ws"
    ws.mkdir()
    app = create_app(str(tmp_path / "f.db"), content, ws, static_dir=static_dir, **kw)
    return TestClient(app, base_url=base_url, client=(host, 50000))


@pytest.fixture
def client(tmp_path):
    return app_client(tmp_path, "127.0.0.1")


@pytest.fixture
def remote_client(tmp_path):
    return app_client(tmp_path, "192.168.1.20")


@pytest.fixture
def broken_module(tmp_path):
    d = tmp_path / "broken"
    d.mkdir()
    (d / "module.json").write_text("{not json")
    return str(d)
