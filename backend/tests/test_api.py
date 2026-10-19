import shutil
from pathlib import Path

import pytest

from tests.conftest import app_client


def xp(c):
    return c.get("/api/team").json()["xp"]


def test_quest_endpoint_returns_three_steps(client):
    assert len(client.get("/api/quest").json()["steps"]) == 3


def test_quest_bad_minutes_rejected(client):
    assert client.get("/api/quest?minutes=45").status_code == 422
    assert client.get("/api/quest?minutes=60").status_code == 200


def test_qcm_answer_does_not_leak_answers_in_lesson(client):
    r = client.get("/api/lesson/l1")
    assert r.status_code == 200 and "answer" not in r.text
    assert "explain" not in r.text and "remedial" not in r.text


def test_lesson_never_leaks_check_or_hints(client):
    t = client.get("/api/lesson/l1").json()
    assert "check.sh" not in str(t) and "hints" not in str(t) and "Utilisez la commande touch" not in str(t)
    assert t["tp"]["id"] == "t1" and t["tp"]["timeout_s"] == 10


def test_unknown_lesson_404(client):
    assert client.get("/api/lesson/nope").status_code == 404


def test_wrong_answer_returns_explanation_and_remedial(client):
    r = client.post("/api/qcm/answer", json={"question_id": "q1", "chosen": 0}).json()
    assert r["correct"] is False and r["explanation"] and r["remedial_lesson_id"]
    assert client.get("/api/reviews").status_code == 200


def test_right_answer(client):
    r = client.post("/api/qcm/answer", json={"question_id": "q1", "chosen": 1}).json()
    assert r["correct"] is True and r["remedial_lesson_id"] is None


def test_qcm_validation(client):
    assert client.post("/api/qcm/answer", json={"question_id": "q1", "chosen": 3}).status_code == 400
    assert client.post("/api/qcm/answer", json={"question_id": "q1", "chosen": -1}).status_code == 400
    assert client.post("/api/qcm/answer", json={"question_id": "zz", "chosen": 0}).status_code == 404


def test_hint_costs_ten_xp(client):
    client.post("/api/quest/step", json={"kind": "lesson", "lesson_id": "l1"})  # earn 20 XP first (XP floors at 0)
    before = xp(client)
    r = client.post("/api/tp/t1/hint", json={"level": 1})
    assert r.json()["cost"] == 10 and r.json()["hint"]
    assert xp(client) == before - 10


def test_hint_bad_level_and_unknown_tp(client):
    assert client.post("/api/tp/t1/hint", json={"level": 0}).status_code == 422
    assert client.post("/api/tp/nope/hint", json={"level": 1}).status_code == 404


def test_quest_step_validation(client):
    assert client.post("/api/quest/step", json={"kind": "x", "lesson_id": "l1"}).status_code == 400
    assert client.post("/api/quest/step", json={"kind": "lesson", "lesson_id": "zz"}).status_code == 404
    assert client.post("/api/quest/step", json={"kind": "lesson", "lesson_id": "l1"}).status_code == 200
    assert xp(client) == 20


def test_quest_step_tp_requires_passing_check(client, tmp_path):
    step = {"kind": "tp", "lesson_id": "l1"}
    assert client.post("/api/quest/step", json=step).status_code == 409
    client.post("/api/tp/t1/check")  # fails: no ok.txt
    assert client.post("/api/quest/step", json=step).status_code == 409
    (tmp_path / "ws" / "ok.txt").write_text("x")
    assert client.post("/api/tp/t1/check").json()["passed"] is True
    assert client.post("/api/quest/step", json=step).status_code == 200
    assert xp(client) == 80


BAD = [("post", "/api/tp/t1/check"), ("post", "/api/boss/attempt"),
       ("post", "/api/weekly/import"), ("post", "/api/tp/t1/hint")]


@pytest.mark.parametrize("method,url", BAD)
@pytest.mark.parametrize("headers", [{"origin": "http://evil.com"}, {"host": "evil.com"}])
def test_local_peer_with_bad_origin_or_host_is_403(client, method, url, headers):
    kw = {"json": {"path": "/tmp/x"}} if "import" in url else {"json": {"level": 1}} if "hint" in url else {}
    assert getattr(client, method)(url, headers=headers, **kw).status_code == 403


def test_remote_cannot_hint(remote_client):
    assert remote_client.post("/api/tp/t1/hint", json={"level": 1}).status_code == 403


def test_audio_failure_leaves_no_partial(client, tmp_path, monkeypatch):
    import app.main as m

    def boom(text, out):
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"partial")
        raise RuntimeError("fail")

    monkeypatch.setattr(m, "synthesize", boom)
    assert client.get("/api/audio/l1.wav").status_code == 503
    assert list((tmp_path / "audio").glob("*")) == []


def test_rest_and_topic(client):
    assert client.post("/api/rest").status_code == 200
    assert client.post("/api/topic", json={"topic": "k8s"}).status_code == 200
    assert client.get("/api/quest").json()["imposed_topic"] == "k8s"
    client.post("/api/topic", json={"topic": None})
    assert client.get("/api/quest").json()["imposed_topic"] is None


def test_tp_check_local_runs_pure(client, tmp_path):
    assert client.post("/api/tp/t1/check").json()["passed"] is False
    (tmp_path / "ws" / "ok.txt").write_text("x")
    assert client.post("/api/tp/t1/check").json()["passed"] is True
    assert xp(client) == 0  # check does not award


def test_remote_cannot_run_tp_check(remote_client):
    assert remote_client.post("/api/tp/t1/check").status_code == 403


def test_remote_cannot_attempt_boss(remote_client):
    assert remote_client.post("/api/boss/attempt").status_code == 403


def test_remote_cannot_import_module(remote_client):
    assert remote_client.post("/api/weekly/import", json={"path": "/tmp/x"}).status_code == 403


def test_remote_can_read_quest_and_lesson(remote_client):
    assert remote_client.get("/api/quest").status_code == 200
    assert remote_client.get("/api/lesson/l1").status_code == 200
    assert remote_client.get("/api/team").status_code == 200


@pytest.mark.parametrize("url", ["/api/rest", "/api/gacha/pull"])
def test_cross_origin_post_is_403(client, url):
    assert client.post(url, headers={"origin": "http://evil.com"}).status_code == 403


def test_same_origin_post_passes(client):
    assert client.post("/api/rest", headers={"origin": "http://localhost"}).status_code == 200
    assert client.post("/api/rest").status_code == 200


def test_team_has_skill_levels(client):
    client.post("/api/quest/step", json={"kind": "lesson", "lesson_id": "l1"})
    t = client.get("/api/team").json()
    assert t["skills"]["demo"] == 20 and t["skill_levels"]["demo"] == 1


def test_finishing_lesson_via_api_earns_token(client, tmp_path):
    client.post("/api/quest/step", json={"kind": "lesson", "lesson_id": "l1"})
    client.post("/api/quest/step", json={"kind": "qcm", "lesson_id": "l1"})
    (tmp_path / "ws" / "ok.txt").write_text("x")
    client.post("/api/tp/t1/check")
    assert client.get("/api/team").json()["tokens"] == 0
    client.post("/api/quest/step", json={"kind": "tp", "lesson_id": "l1"})
    assert client.get("/api/team").json()["tokens"] == 1


def test_gacha_without_tokens_is_409(client):
    assert client.post("/api/gacha/pull").status_code == 409


def test_gacha_with_token(client, tmp_path):
    from app.db import connect
    from app.gacha import add_tokens

    db = connect(str(tmp_path / "f.db"))
    add_tokens(db, 1)
    db.close()
    assert client.post("/api/gacha/pull").json()["id"]
    assert len(client.get("/api/team").json()["inventory"]) == 1


def test_boss_get_hides_checks_and_attempt_counts(client):
    b = client.get("/api/boss")
    assert b.status_code == 200 and "test -f" not in b.text and "check" not in b.text
    assert len(b.json()["phases"]) == 3 and b.json()["attempts"] == 0
    r = client.post("/api/boss/attempt").json()
    assert r["won"] is False and r["attempts"] == 1


def test_import_broken_module_is_422_with_errors(client, broken_module):
    r = client.post("/api/weekly/import", json={"path": broken_module})
    assert r.status_code == 422 and r.json()["errors"]


def test_import_ok_then_lesson_available(client, tmp_path):
    src = tmp_path / "newmod"
    shutil.copytree(Path(__file__).parent / "fixtures" / "demo_module", src)
    (src / "module.json").write_text(
        (src / "module.json").read_text().replace('"id": "demo"', '"id": "wk2"').replace('"l1"', '"n1"').replace('"l2"', '"n2"'))
    for f in list((src / "lessons").iterdir()):
        f.rename(f.with_name(f.name.replace("l1", "n1").replace("l2", "n2")))
    for f in src.rglob("*.qcm.json"):
        f.write_text(f.read_text().replace("q1", "p1").replace("q2", "p2").replace('"l2"', '"n2"'))
    r = client.post("/api/weekly/import", json={"path": str(src)})
    assert r.json() == {"module_id": "wk2"}
    assert client.get("/api/lesson/n1").status_code == 200


def test_weekly_brief(client):
    client.post("/api/qcm/answer", json={"question_id": "q1", "chosen": 0})
    b = client.post("/api/weekly/brief", json={"topic": "Docker", "format": "court"}).json()["brief"]
    assert "Docker" in b and "q1" in b


def test_audio_rejects_traversal_and_unknown(client):
    assert client.get("/api/audio/a.b.wav").status_code == 404
    assert client.get("/api/audio/..%2Fx.wav").status_code == 404
    assert client.get("/api/audio/nope.wav").status_code == 404


@pytest.mark.skipif(shutil.which("espeak-ng") is None, reason="espeak-ng absent")
def test_audio_generates_wav(client):
    r = client.get("/api/audio/l1.wav")
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav"


def test_audio_503_without_espeak(client, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda *_: None)
    assert client.get("/api/audio/l1.wav").status_code == 503


def test_broken_module_skipped(client, tmp_path):
    bad = tmp_path / "content" / "modules" / "bad"
    bad.mkdir()
    (bad / "module.json").write_text("{")
    assert client.get("/api/lesson/l1").status_code == 200


def test_static_served_after_api(tmp_path):
    d = tmp_path / "dist"
    d.mkdir()
    (d / "index.html").write_text("<h1>hi</h1>")
    c = app_client(tmp_path, "127.0.0.1", static_dir=d)
    assert "hi" in c.get("/").text and c.get("/api/team").status_code == 200


def _seeded(tmp_path):
    import json
    mod = tmp_path / "content" / "modules" / "demo"
    (mod / "kit").mkdir()
    (mod / "kit" / "a.txt").write_text("kit")
    p = mod / "lessons" / "l1.tp" / "tp.json"
    d = json.loads(p.read_text())
    d.update(seed=["../../kit"], workspace="tp1")
    p.write_text(json.dumps(d))


def test_start_copies_seed_without_overwrite(client, tmp_path):
    _seeded(tmp_path)
    r = client.post("/api/tp/t1/start")
    assert r.status_code == 200 and r.json() == {"dir": "tp1"}
    f = tmp_path / "ws" / "tp1" / "kit" / "a.txt"
    assert f.read_text() == "kit"
    f.write_text("mine")
    assert client.post("/api/tp/t1/start").status_code == 200
    assert f.read_text() == "mine"


def test_start_default_workspace_and_unknown(client):
    assert client.post("/api/tp/t1/start").json() == {"dir": "."}
    assert client.post("/api/tp/nope/start").status_code == 404


def test_remote_cannot_start_tp(remote_client):
    assert remote_client.post("/api/tp/t1/start").status_code == 403


def test_start_bad_origin_403(client):
    assert client.post("/api/tp/t1/start", headers={"origin": "http://evil.com"}).status_code == 403


def test_check_runs_in_tp_workspace(client, tmp_path):
    _seeded(tmp_path)
    client.post("/api/tp/t1/start")
    assert client.post("/api/tp/t1/check").json()["passed"] is False
    (tmp_path / "ws" / "tp1" / "ok.txt").write_text("x")
    assert client.post("/api/tp/t1/check").json()["passed"] is True
