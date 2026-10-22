import json
from pathlib import Path
import pytest
from starlette.testclient import TestClient
from app.db import connect
from app.main import create_app
from app.progress import award_xp, get_profile

FIXTURES_DIR = Path(__file__).parent / "fixtures"
DEMO_MODULE = FIXTURES_DIR / "demo_module"
DEMO_BOSS = FIXTURES_DIR / "demo_boss"


@pytest.fixture
def app_env(tmp_path):
    db_path = str(tmp_path / "test.db")
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    modules_dir = content_dir / "modules"
    modules_dir.mkdir()
    
    # Copie du module démo dans modules
    import shutil
    shutil.copytree(DEMO_MODULE, modules_dir / "demo")
    shutil.copytree(DEMO_BOSS, content_dir / "bosses" / "demo_boss")

    # Copie gacha.json
    gacha_src = Path(__file__).resolve().parent.parent.parent / "content" / "gacha.json"
    shutil.copy(gacha_src, content_dir / "gacha.json")

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    app = create_app(db_path=db_path, content_dir=content_dir, workspace=workspace)
    return app, db_path, tmp_path


@pytest.fixture
def client(app_env):
    app, _, _ = app_env
    return TestClient(app, client=("127.0.0.1", 50000))


@pytest.fixture
def remote_client(app_env):
    app, _, _ = app_env
    return TestClient(app, client=("192.168.1.20", 50000))


def xp(client):
    res = client.get("/api/team").json()
    return res["profile"]["total_xp"]


def test_quest_endpoint_returns_three_steps(client):
    res = client.get("/api/quest").json()
    assert len(res["steps"]) == 3


def test_qcm_answer_does_not_leak_answers_in_lesson(client):
    res = client.get("/api/lesson/l1")
    assert res.status_code == 200
    assert "answer" not in res.text


def test_wrong_answer_returns_explanation_and_remedial(client):
    r = client.post("/api/qcm/answer", json={"question_id": "q1", "chosen": 0}).json()
    assert r["correct"] is False
    assert r["explanation"]
    assert r["remedial_lesson_id"]


def test_hint_costs_ten_xp(client, app_env):
    _, db_path, _ = app_env
    db = connect(db_path)
    award_xp(db, "automation", 50)
    db.close()

    before = xp(client)
    res = client.get("/api/tp/tp1/hint?level=1")
    assert res.status_code == 200
    assert xp(client) == before - 10


def test_remote_cannot_run_tp_check(remote_client):
    assert remote_client.post("/api/tp/tp1/check").status_code == 403


def test_remote_cannot_attempt_boss(remote_client):
    assert remote_client.post("/api/boss/attempt").status_code == 403


def test_remote_cannot_import_module(remote_client):
    assert remote_client.post("/api/weekly/import", json={"path": "/tmp/x"}).status_code == 403


def test_remote_can_read_quest_and_lesson(remote_client):
    assert remote_client.get("/api/quest").status_code == 200


def test_gacha_without_tokens_is_409(client):
    assert client.post("/api/gacha/pull").status_code == 409


def test_import_broken_module_is_422_with_errors(client, tmp_path):
    broken_dir = tmp_path / "broken_mod"
    broken_dir.mkdir()
    (broken_dir / "module.json").write_text(json.dumps({
        "id": "broken",
        "title": "Broken",
        "skill": "dev",
        "lessons": [{"id": "bad", "title": "Bad", "minutes": 10}]
    }))
    r = client.post("/api/weekly/import", json={"path": str(broken_dir)})
    assert r.status_code == 422
    assert r.json()["errors"]
