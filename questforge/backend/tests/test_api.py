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


def test_step_with_unknown_kind_is_rejected(client):
    res = client.post("/api/quest/step", json={"kind": "nimportequoi", "lesson_id": "l1"})
    assert res.status_code == 422


def test_step_with_unknown_lesson_is_404_and_awards_nothing(client, app_env):
    _, db_path, _ = app_env
    res = client.post("/api/quest/step", json={"kind": "lesson", "lesson_id": "zzz"})
    assert res.status_code == 404
    assert get_profile(connect(db_path)).total_xp == 0


def test_qcm_answer_out_of_range_is_422_and_not_recorded(client, app_env):
    _, db_path, _ = app_env
    res = client.post("/api/qcm/answer", json={"question_id": "q1", "chosen": 99})
    assert res.status_code == 422
    assert connect(db_path).execute("SELECT COUNT(*) FROM mistakes").fetchone()[0] == 0


def test_audio_without_speech_engine_is_503(client, monkeypatch):
    def missing_engine(*args, **kwargs):
        raise FileNotFoundError("espeak-ng")

    monkeypatch.setattr("app.main.synthesize", missing_engine)
    res = client.get("/api/audio/l1.wav")
    assert res.status_code == 503
    assert "espeak-ng" in res.json()["detail"]


def test_quest_without_any_module_is_503_not_500(tmp_path):
    content_dir = tmp_path / "content"
    (content_dir / "modules").mkdir(parents=True)
    app = create_app(db_path=str(tmp_path / "t.db"), content_dir=content_dir, workspace=tmp_path / "ws")
    res = TestClient(app, client=("127.0.0.1", 50000)).get("/api/quest")
    assert res.status_code == 503


def test_default_content_dir_does_not_depend_on_cwd(monkeypatch, tmp_path):
    import importlib

    import app.main as main_module

    monkeypatch.chdir(tmp_path)
    reloaded = importlib.reload(main_module)
    try:
        res = TestClient(reloaded.app, client=("127.0.0.1", 50000)).get("/api/lesson/l1")
        assert res.status_code == 200
    finally:
        monkeypatch.undo()
        importlib.reload(main_module)


def test_connection_is_usable_from_another_thread(tmp_path):
    """FastAPI ouvre la connexion (dépendance) et exécute l'endpoint dans des threads différents."""
    from concurrent.futures import ThreadPoolExecutor

    conn = connect(tmp_path / "threads.db")
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(lambda: conn.execute("SELECT 1").fetchone()[0]).result() == 1
    conn.close()


def test_quest_exposes_real_activity_history_and_due_reviews(client):
    client.post("/api/quest/step", json={"kind": "lesson", "lesson_id": "l1"})
    client.post("/api/rest")
    data = client.get("/api/quest").json()
    history = data["activityHistory"]
    assert len(history) == 28
    assert history[-1]["count"] == 1
    # le repos annoncé aujourd'hui prime sur l'activité du jour
    assert history[-1]["status"] == "rest"
    assert all(day["status"] == "idle" for day in history[:-1])
    assert data["dueReviewsCount"] == 0
    assert data["profile"]["active_module_id"] == "demo"


def test_completing_all_steps_of_a_lesson_awards_one_token(client):
    def step(kind):
        return client.post("/api/quest/step", json={"kind": kind, "lesson_id": "l1"}).json()

    assert step("lesson")["tokensAwarded"] == 0
    assert step("qcm")["tokensAwarded"] == 0
    assert step("tp")["tokensAwarded"] == 1
    # rejouer une étape ne redonne ni XP ni jeton
    assert step("tp") == {"ok": True, "alreadyCompleted": True, "tokensAwarded": 0}
    assert client.get("/api/team").json()["profile"]["tokens"] == 1
    assert client.post("/api/gacha/pull").status_code == 200
    assert client.get("/api/team").json()["profile"]["tokens"] == 0


def test_weekly_brief_mentions_a_mistake_made_today(client):
    client.post("/api/qcm/answer", json={"question_id": "q1", "chosen": 0})
    brief = client.post("/api/weekly/brief", json={"topic": "Terraform", "format": "TP guidé"}).json()["brief"]
    assert "q1" in brief


def test_due_review_answered_correctly_awards_xp_once(client, app_env):
    from datetime import date, timedelta
    _, db_path, _ = app_env
    client.post("/api/qcm/answer", json={"question_id": "q1", "chosen": 0})  # erreur : due demain
    db = connect(db_path)
    db.execute("UPDATE mistakes SET next_review = ? WHERE question_id = 'q1'", ((date.today() - timedelta(days=1)).isoformat(),))
    db.commit()

    due = client.get("/api/reviews").json()
    assert due["due"] == ["q1"]
    assert due["boxesCount"] == [1, 0, 0, 0, 0]
    review = due["reviews"][0]
    assert review["box"] == 0 and review["remedial_lesson_id"] == "l1"
    assert "answer" not in review

    res = client.post("/api/qcm/answer", json={"question_id": "q1", "chosen": 1}).json()
    assert res["correct"] is True and res["xpAwarded"] == 15
    again = client.post("/api/qcm/answer", json={"question_id": "q1", "chosen": 1}).json()
    assert again["xpAwarded"] == 0
    assert get_profile(connect(db_path)).total_xp == 15


def test_first_correct_answer_awards_no_review_xp(client):
    res = client.post("/api/qcm/answer", json={"question_id": "q1", "chosen": 1}).json()
    assert res["correct"] is True and res["xpAwarded"] == 0
