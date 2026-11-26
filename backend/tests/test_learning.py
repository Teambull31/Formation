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


def _answer_all_l1(client, right=True):
    for q in client.get("/api/lesson/l1").json()["qcm"]:
        for i in range(len(q["options"])):
            if client.post("/api/qcm/answer", json={"question_id": q["id"], "chosen": i}).json()["correct"] == right:
                break


def test_panne_card_and_oral_answer(client):
    cid = client.post("/api/cards/panne", json={"symptom": "checkout refusé sur le runner", "cause": "dossier appartenant à root",
                                                "fix": "nettoyer le workspace et lancer dans un conteneur"}).json()["id"]
    items = client.get("/api/oral").json()["items"]
    assert any(i["id"] == cid and i["prompt"].startswith("Panne") for i in items)
    r = client.post("/api/oral/answer", json={"kind": "card", "id": cid, "transcript": "je ne sais pas"}).json()
    assert r["correct"] is False and "root" in r["answer"]
    r = client.post("/api/oral/answer", json={"kind": "card", "id": cid,
                                              "transcript": "le dossier appartenait à root, il faut nettoyer le workspace dans un conteneur"}).json()
    assert r["correct"] is True
    assert client.post("/api/oral/answer", json={"kind": "card", "id": "nope", "transcript": "x"}).status_code == 404


def test_oral_qcm_by_letter(client):
    q = client.get("/api/lesson/l1").json()["qcm"][0]
    results = [client.post("/api/oral/answer", json={"kind": "qcm", "id": q["id"], "transcript": f"réponse {'abcdef'[i]}"}).json()["correct"]
               for i in range(len(q["options"]))]
    assert results.count(True) == 1


def test_confidence_flag(client):
    q = client.get("/api/lesson/l1").json()["qcm"][0]
    wrong = [client.post("/api/qcm/answer", json={"question_id": q["id"], "chosen": i, "confident": True}).json()
             for i in range(len(q["options"]))]
    assert any(r["sure_wrong"] for r in wrong) and not any(r["sure_wrong"] and r["correct"] for r in wrong)
    assert q["id"] in client.get("/api/reviews").json()["due"]  # erreur sûre : due aujourd'hui


def test_mixed_exam_and_cert_mock_exam(client, tmp_path):
    assert all(e["id"] != "melange" for e in client.get("/api/exams").json())
    _done(tmp_path, ("lesson", "l1"), ("qcm", "l1"), ("lesson", "l2"), ("qcm", "l2"))
    ids = [e["id"] for e in client.get("/api/exams").json()]
    pool = sum(len(client.get(f"/api/lesson/{l}").json()["qcm"]) for l in ("l1", "l2"))
    if pool >= 5:
        assert "melange" in ids
    assert client.post("/api/cert", json={"key": "nope"}).status_code == 422
    assert client.post("/api/cert", json={"key": "devops", "date": (date.today() + timedelta(days=30)).isoformat()}).status_code == 200
    c = client.get("/api/cert").json()
    assert c["days_left"] == 30 and c["title"].startswith("Entretien")
    if pool >= 5:
        ex = client.get("/api/exam/blanc").json()
        assert ex["duration_s"] == round(45 * 60 / 40 * len(ex["questions"]))


def test_missions_proof_and_local_check(client, tmp_path, monkeypatch):
    (tmp_path / "content" / "missions.json").write_text(json.dumps([
        {"id": "m1", "module": "demo", "title": "T", "goal": "G", "steps": ["a"], "check": "true"},
        {"id": "m2", "module": "demo", "title": "T2", "goal": "G", "steps": ["a"], "check": "false"}]))
    ms = client.get("/api/missions").json()
    assert [m["id"] for m in ms] == ["m1", "m2"] and not ms[0]["ready"]
    assert client.post("/api/missions/m2/check").json()["passed"] is False
    r = client.post("/api/missions/m1/check").json()
    assert r["passed"] and r["xp"] == 200
    assert client.post("/api/missions/m1/check").json()["xp"] == 0  # une seule fois
    assert client.post("/api/missions/m2/done", json={"proof": "pas un lien"}).status_code == 422
    assert client.post("/api/missions/m2/done", json={"proof": "https://github.com/Teambull31/mcs/pull/3"}).json()["xp"] == 200
    assert all(m["done"] for m in client.get("/api/missions").json())


def test_article_needs_passed_exam_listing_and_goes_to_portfolio(client):
    assert client.get("/api/articles").json() == []
    text = "mot " * 120
    assert client.put("/api/articles/demo", json={"text": text}).json()["xp"] == 50
    assert client.put("/api/articles/demo", json={"text": text + "fin"}).json()["xp"] == 0
    assert client.put("/api/articles/nope", json={"text": text}).status_code == 404
    import io, zipfile
    z = zipfile.ZipFile(io.BytesIO(client.get("/api/portfolio.zip").content))
    assert "articles/demo.md" in z.namelist()


def test_relisten_spaced(client, tmp_path):
    p = tmp_path / "content" / "podcast"
    p.mkdir()
    (p / "episodes.json").write_text(json.dumps([{"file": "ep01.mp3", "title": "Un", "minutes": 9, "module": "autre"}]))
    (p / "ep01.mp3").write_bytes(b"ID3")
    client.post("/api/podcast/ep01.mp3/done")
    labels = lambda: [s["label"] for s in client.get("/api/quest").json()["suggestions"]]
    assert not any("Réécouter" in x for x in labels())  # J+1 pas encore
    con = sqlite3.connect(next(tmp_path.glob("*.db")))
    con.execute("UPDATE settings SET value = ? WHERE key = 'listened:ep01.mp3'", ((date.today() - timedelta(days=1)).isoformat() + "|1",))
    con.commit()
    con.close()
    assert any("Réécouter (rappel n°1)" in x for x in labels())


def test_pace_from_retention(client, tmp_path):
    assert client.get("/api/quest").json()["pace"] == "normal"
    con = sqlite3.connect(next(tmp_path.glob("*.db")))
    con.executemany("INSERT INTO review_log(day, correct) VALUES (?, ?)", [(date.today().isoformat(), 0)] * 8 + [(date.today().isoformat(), 1)] * 2)
    con.commit()
    con.close()
    assert client.get("/api/quest").json()["pace"] == "consolidate"


def test_habit_cue_in_reminder(db):
    from app import push
    from tests.test_push import SUB
    push.subscribe(db, SUB)
    db.execute("INSERT INTO settings(key, value) VALUES ('habit_cue', 'Quand je démarre la voiture')")
    sent = []
    push.remind(db, date(2026, 10, 23), 0, sender=lambda *a, **k: sent.append(a), hour=None)
    assert sent


def test_cert_pace_spreads_remaining_lessons_until_last_week(client, tmp_path):
    client.post("/api/cert", json={"key": "devops", "date": (date.today() + timedelta(days=21)).isoformat()})
    p = client.get("/api/cert").json()["pace"]
    left = p["left"]
    assert left >= 1 and p["per_week"] == -(-left * 7 // 14) and p["recent"] == 0 and not p["on_track"]
    con = sqlite3.connect(next(tmp_path.glob("*.db")))
    con.executemany("INSERT INTO quest_steps(day, kind, lesson_id, done) VALUES (?, ?, 'l1', 1)",
                    [(date.today().isoformat(), k) for k in ("lesson", "qcm")])
    con.commit()
    con.close()
    p = client.get("/api/cert").json()["pace"]
    assert p["left"] == left - 1 and p["recent"] == 1
    client.post("/api/cert", json={"key": "devops", "date": (date.today() + timedelta(days=3)).isoformat()})
    assert client.get("/api/cert").json()["pace"]["advice"].startswith("Dernière ligne droite")
    client.post("/api/cert", json={"key": "devops", "date": (date.today() - timedelta(days=1)).isoformat()})
    assert "passée" in client.get("/api/cert").json()["pace"]["advice"]
    client.post("/api/cert", json={"key": "devops"})  # objectif sans date : pas de rythme
    client.post("/api/cert", json={"key": None})
    assert client.get("/api/cert").json()["pace"] is None
