"""Cartes mémoire, plan de 30 jours, examen final et labo réel."""
import json
import sqlite3
from datetime import date

import pytest

from app import cards as cardlib
from app import plan as planlib
from app import push
from app.content import Lesson
from app.review import INTERVALS
from tests.conftest import app_client

TODAY = date(2026, 11, 21)
BODY = """# Titre

## Section A

Un **Deployment** maintient le nombre de pods voulu, même quand un nœud tombe.

!!Un tag latest change sans prévenir!!

```bash
echo "**pas une carte**" "!!pas un piège!!"
```

| **tableau** | ignoré par les cartes, même avec une phrase assez longue |
"""


def lesson() -> Lesson:
    return Lesson("x1", "Leçon X", 5, BODY, [], None)


def test_cards_from_traps_and_bold_terms_outside_code():
    cs = cardlib.lesson_cards(lesson())
    assert [(c.kind, c.back) for c in cs] == [("terme", "Deployment"), ("piege", "Un tag latest change sans prévenir")]
    term = cs[0]
    assert "＿＿＿" in term.front and "Deployment" not in term.front
    assert cs[1].front.startswith("Section A")
    assert len({c.id for c in cs}) == 2 and all(c.id.startswith("x1-") for c in cs)
    assert [c.id for c in cardlib.lesson_cards(lesson())] == [c.id for c in cs]  # ids stables


def test_card_climbs_boxes_until_mastered_and_falls_back_on_miss(db):
    cid = "x1-abc"
    assert cardlib.record_card(db, cid, True, TODAY)["box"] == 1
    assert cardlib.record_card(db, cid, False, TODAY) == {"box": 0, "due": "2026-11-22", "mastered": False}
    for _ in range(len(INTERVALS)):
        r = cardlib.record_card(db, cid, True, TODAY)
    assert r["mastered"] is True


def test_session_serves_due_then_limits_new_cards(db):
    many = [cardlib.Card(f"x-{i}", "x1", "piege", "f", "b") for i in range(cardlib.NEW_PER_DAY + 5)]
    s = cardlib.session(db, many, TODAY)
    assert len(s["cards"]) == cardlib.NEW_PER_DAY and s["unseen"] == len(many)
    for c in s["cards"][:3]:
        cardlib.record_card(db, c["id"], False, TODAY)
    s = cardlib.session(db, many, TODAY)
    assert len(s["cards"]) == cardlib.NEW_PER_DAY - 3  # 3 nouvelles déjà introduites aujourd'hui, pas encore dues
    s = cardlib.session(db, many, date(2026, 11, 22))
    assert [c["id"] for c in s["cards"][:3]] == ["x-0", "x-1", "x-2"] and s["cards"][0]["box"] == 0


def _done(tmp_path, *steps):
    db = sqlite3.connect(tmp_path / "f.db")
    db.executemany("INSERT OR REPLACE INTO quest_steps(day, kind, lesson_id, done) VALUES ('2026-11-21', ?, ?, 1)", steps)
    db.commit()
    db.close()


def test_cards_api_only_for_studied_lessons(client, tmp_path):
    assert client.get("/api/cards").json()["cards"] == []
    _done(tmp_path, ("lesson", "l1"))
    cards = client.get("/api/cards").json()["cards"]
    assert cards and cards[0]["lesson_id"] == "l1" and cards[0]["box"] is None
    r = client.post(f"/api/cards/{cards[0]['id']}", json={"known": True})
    assert r.status_code == 200 and r.json()["box"] == 1
    assert client.post("/api/cards/l2-inconnue", json={"known": True}).status_code == 404


def _plan(tmp_path):
    days = [{"day": 1, "title": "Démarrer", "lessons": ["l1"], "todo": []},
            {"day": 2, "title": "Réviser", "lessons": [], "todo": ["Cartes du jour"]}]
    (tmp_path / "content" / "plan.json").write_text(json.dumps(days), encoding="utf-8")


def test_plan_start_progress_and_manual_days(client, tmp_path):
    _plan(tmp_path)
    p = client.get("/api/plan").json()
    assert p["started"] is False and p["today"] is None and [d["done"] for d in p["days"]] == [False, False]
    assert client.post("/api/plan/start").status_code == 200
    p = client.get("/api/plan").json()
    assert p["today"] == 1 and p["late"] == 0
    _done(tmp_path, ("lesson", "l1"), ("qcm", "l1"), ("tp", "l1"))
    assert client.get("/api/plan").json()["days"][0]["done"] is True
    assert client.post("/api/plan/day/2", json={"done": True}).status_code == 200
    assert client.get("/api/plan").json()["days"][1]["manual"] is True
    assert client.post("/api/plan/day/3", json={"done": True}).status_code == 404


def test_plan_lateness_and_push_line(db):
    days = [{"day": n, "title": f"J{n}", "lessons": ["zz"], "todo": []} for n in (1, 2, 3)]
    assert planlib.today_line(db, days, TODAY) is None
    planlib.start(db, date(2026, 11, 19))
    st = planlib.status(db, days, TODAY, lambda lid: False)
    assert st["today"] == 3 and st["late"] == 2
    assert planlib.today_line(db, days, TODAY) == "Jour 3/3 : J3"
    assert planlib.today_line(db, days, date(2026, 12, 1)) is None


def test_reminder_carries_plan_line(db):
    sent = []
    push.subscribe(db, {"endpoint": "https://fcm.googleapis.com/fcm/send/x", "keys": {"p256dh": "BPk", "auth": "au"}})
    push.remind(db, TODAY, 0, sender=lambda *a, **k: sent.append(json.loads(k["data"])["body"]), plan_line="Jour 3/30 : Docker")
    assert sent and sent[0].startswith("Jour 3/30 : Docker. ")


def test_plan_file_is_valid_and_lessons_exist():
    from pathlib import Path

    from app.content import load_module
    content = Path(__file__).resolve().parents[2] / "content"
    days = planlib.load_plan(content)
    assert len(days) == 30
    ids = {les.id for d in (content / "modules").glob("*/") if (d / "module.json").is_file() for les in load_module(d).lessons}
    planned = [lid for d in days for lid in d["lessons"]]
    assert set(planned) <= ids and len(planned) == len(set(planned))
    for m in ("cicd", "docker", "k8s", "terraform", "ansible", "projet"):
        assert {les.id for les in load_module(content / "modules" / m).lessons} <= set(planned), m


def test_exam_draw_grade_and_best(client):
    exams = client.get("/api/exams").json()
    assert exams == [{"id": "demo", "title": "Module de démonstration", "questions": 3, "best": None}]
    e = client.get("/api/exam/demo").json()
    assert len(e["questions"]) == 3 and "answer" not in e["questions"][0] and e["duration_s"] > 0
    right = {"q1": 1, "q2": 0, "q3": 1}
    r = client.post("/api/exam/demo", json={"answers": right}).json()
    assert r["score"] == 100 and r["passed"] is True and r["xp"] == 100
    r = client.post("/api/exam/demo", json={"answers": {**right, "q1": -1}}).json()
    assert r["score"] == 67 and r["passed"] is False and r["best"] == 100 and r["xp"] == 0
    q1_lesson = next(les for les in ("l1", "l2") if any(q["id"] == "q1" for q in client.get(f"/api/lesson/{les}").json()["qcm"]))
    assert r["to_review"] == [{"lesson_id": q1_lesson, "title": client.get(f"/api/lesson/{q1_lesson}").json()["title"],
                               "count": 1, "focus": next(d["text"] for d in r["detail"] if d["id"] == "q1")}]
    assert next(d for d in r["detail"] if d["id"] == "q1")["answer_text"]
    assert client.get("/api/reviews").json()["boxes"][0] == 1  # la question ratée rejoint les révisions
    assert client.post("/api/exam/demo", json={"answers": {"q1": 1}}).status_code == 400
    assert client.post("/api/exam/demo", json={"answers": {**right, "q3": 9}}).status_code == 400
    assert client.get("/api/exam/nope").status_code == 404


def test_real_lab_runs_module_script(client, tmp_path):
    assert client.get("/api/lesson/l1").json()["tp"]["real"] is False
    assert client.post("/api/tp/t1/real").status_code == 404
    script = tmp_path / "content" / "modules" / "demo" / "lessons" / "_real.sh"
    script.write_text('echo "outil: $PWD"; [ -f ok.txt ]\n', encoding="utf-8")
    assert client.get("/api/lesson/l1").json()["tp"]["real"] is True
    r = client.post("/api/tp/t1/real").json()
    assert r["passed"] is False and "outil:" in r["output"]
    (tmp_path / "ws" / "ok.txt").write_text("", encoding="utf-8")
    assert client.post("/api/tp/t1/real").json()["passed"] is True


def test_real_lab_is_local_only(remote_client):
    assert remote_client.post("/api/tp/t1/real").status_code == 403


@pytest.mark.parametrize("module", ["cicd", "docker", "k8s", "terraform", "ansible", "projet"])
def test_shipped_real_scripts_exist(module):
    from pathlib import Path
    assert (Path(__file__).resolve().parents[2] / "content" / "modules" / module / "lessons" / "_real.sh").is_file()
