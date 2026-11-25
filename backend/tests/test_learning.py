"""Parcours d'apprentissage : TP différé, quête qui suit le plan, révisions du jour, suggestions, rétention."""
import json
import sqlite3
from datetime import date, timedelta


def _done(tmp_path, *steps):
    con = sqlite3.connect(next(tmp_path.glob("*.db")))
    con.executemany("INSERT INTO quest_steps(day, kind, lesson_id, done) VALUES ('2026-01-01', ?, ?, 1)", steps)
    con.commit()
    con.close()


def _kinds(c):
    return [(s["kind"], s["lesson_id"]) for s in c.get("/api/quest").json()["steps"]]


def test_tp_pending_does_not_block_next_lesson(client, tmp_path):
    _done(tmp_path, ("lesson", "l1"), ("qcm", "l1"))
    q = client.get("/api/quest").json()
    assert q["steps"][0]["lesson_id"] == "l2" and q["pending_tp"] == ["l1"]


def test_quest_follows_the_plan(client, tmp_path):
    (tmp_path / "content" / "plan.json").write_text(json.dumps(
        [{"day": 1, "title": "Deux d'abord", "lessons": ["l2"]}, {"day": 2, "title": "Un", "lessons": ["l1"]}]))
    assert _kinds(client)[0] == ("lesson", "l1")  # plan pas commencé : ordre du module
    client.post("/api/plan/start")
    assert _kinds(client)[0] == ("lesson", "l2")


def test_plan_rebase_removes_the_lateness(client, tmp_path):
    (tmp_path / "content" / "plan.json").write_text(json.dumps(
        [{"day": 1, "title": "Un", "lessons": ["l1"]}, {"day": 2, "title": "Deux", "lessons": ["l2"]}]))
    client.post("/api/plan/start")
    con = sqlite3.connect(next(tmp_path.glob("*.db")))
    con.execute("UPDATE settings SET value = ? WHERE key = 'plan_start'", ((date.today() - timedelta(days=5)).isoformat(),))
    con.commit()
    con.close()
    assert client.get("/api/plan").json()["late"] == 2
    _done(tmp_path, ("lesson", "l1"), ("qcm", "l1"))  # TP en attente : le jour 1 compte quand même
    assert client.post("/api/plan/rebase").status_code == 200
    p = client.get("/api/plan").json()
    assert p["today"] == 2 and p["late"] == 0


def test_review_step_and_daily_xp(client):
    q = client.get("/api/lesson/l1").json()["qcm"][0]
    wrong = next(i for i in range(len(q["options"]))
                 if not client.post("/api/qcm/answer", json={"question_id": q["id"], "chosen": i}).json()["correct"])
    import app.main as m
    tomorrow = date.today() + timedelta(days=1)
    m_date = type("D", (), {"today": staticmethod(lambda: tomorrow), "fromisoformat": staticmethod(date.fromisoformat)})
    import pytest
    mp = pytest.MonkeyPatch()
    mp.setattr(m, "date", m_date)
    try:
        assert client.get("/api/quest").json()["review"] == {"due": 1, "done": False}
        xp = client.get("/api/team").json()["xp"]
        right = next(i for i in range(len(q["options"])) if i != wrong and
                     client.post("/api/qcm/answer", json={"question_id": q["id"], "chosen": i}).json()["correct"])
        assert right is not None
        assert client.get("/api/quest").json()["review"] == {"due": 0, "done": True}
        assert client.get("/api/team").json()["xp"] == xp + m.REVIEW_XP
        r = client.get("/api/retention").json()
        assert r["answered7"] >= 1 and r["rate7"] is not None
    finally:
        mp.undo()


def test_revision_express_done_counts_once(client):
    assert client.post("/api/revision/done").json() == {"xp": 15}
    assert client.post("/api/revision/done").json() == {"xp": 0}


def test_suggestions_interview_feynman_exam(client, tmp_path):
    kinds = lambda: [s["kind"] for s in client.get("/api/quest").json()["suggestions"]]
    assert "interview" in kinds() and "feynman" not in kinds() and "exam" not in kinds()
    _done(tmp_path, ("lesson", "l1"), ("qcm", "l1"), ("tp", "l1"), ("lesson", "l2"), ("qcm", "l2"))
    assert "feynman" in kinds() and "exam" in kinds()


def test_episode_suggested_then_marked_listened(client, tmp_path):
    p = tmp_path / "content" / "podcast"
    p.mkdir()
    (p / "episodes.json").write_text(json.dumps([{"file": "ep01.mp3", "title": "Un", "minutes": 9, "module": "demo"}]))
    (p / "ep01.mp3").write_bytes(b"ID3")
    sug = lambda: [s for s in client.get("/api/quest").json()["suggestions"] if s["kind"] == "episode"]
    assert sug()[0]["id"] == "ep01.mp3"
    assert client.post("/api/podcast/ep01.mp3/done").status_code == 200
    assert sug() == []
    assert client.post("/api/podcast/nope.mp3/done").status_code == 404


def test_push_hour_setting(client):
    assert client.get("/api/push/key").json()["hour"] == 19
    assert client.post("/api/push/hour", json={"hour": 7}).status_code == 200
    assert client.get("/api/push/key").json()["hour"] == 7
    assert client.post("/api/push/hour", json={"hour": 24}).status_code == 422
