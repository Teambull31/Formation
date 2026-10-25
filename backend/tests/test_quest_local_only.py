import json
import shutil
import sqlite3
from pathlib import Path

from starlette.testclient import TestClient

from app.main import create_app
from tests.test_local_only import AUTH, FX, PW, REMOTE

# module "a" (demo) : l2 a un TP local_only ; module "b" : une leçon sans TP
B = {"id": "b", "title": "B", "skill": "b", "lessons": [{"id": "b1", "title": "B1", "minutes": 5}]}


def _client(tmp_path, remote):
    content = tmp_path / "content"
    shutil.copytree(FX / "demo_module", content / "modules" / "a")
    (content / "modules" / "b" / "lessons").mkdir(parents=True)
    (content / "modules" / "b" / "module.json").write_text(json.dumps(B))
    (content / "modules" / "b" / "lessons" / "b1.md").write_text("# B1\n\ntexte\n")
    (content / "modules/b/lessons/b1.qcm.json").write_text(json.dumps(
        [{"id": "bq1", "text": "?", "options": ["a", "b"], "answer": 0, "explain": "e"}]))
    tp = content / "modules/a/lessons/l2.tp/tp.json"
    tp.write_text(json.dumps({**json.loads(tp.read_text()), "local_only": True}))
    shutil.copy(Path(__file__).parents[2] / "content" / "gacha.json", content / "gacha.json")
    ws = tmp_path / "ws"
    ws.mkdir()
    db = str(tmp_path / "f.db")
    kw = dict(password=PW, remote_exec=True, allowed_hosts=[REMOTE]) if remote else {}
    c = TestClient(create_app(db, content, ws, **kw), base_url=f"http://{REMOTE}" if remote else "http://localhost",
                   client=("172.18.0.2" if remote else "127.0.0.1", 50000))
    if remote:
        c.headers.update({**AUTH, "host": REMOTE})
    # état : l1 terminée, l2 leçon+qcm faits, il ne reste que le TP local_only de l2
    con = sqlite3.connect(db)
    con.executemany("INSERT INTO quest_steps(day, kind, lesson_id, done) VALUES ('2026-01-01', ?, ?, 1)",
                    [("lesson", "l1"), ("qcm", "l1"), ("tp", "l1"), ("lesson", "l2"), ("qcm", "l2")])
    con.commit()
    con.close()
    return c


def _kinds(c):
    return [(s["kind"], s["lesson_id"]) for s in c.get("/api/quest").json()["steps"]]


def test_remote_quest_skips_local_only_tp_and_reaches_next_module(tmp_path):
    assert _kinds(_client(tmp_path, True)) == [("lesson", "b1"), ("qcm", "b1")]


def test_local_quest_still_serves_local_only_tp(tmp_path):
    assert _kinds(_client(tmp_path, False)) == [("lesson", "l2"), ("qcm", "l2"), ("tp", "l2")]


def test_remote_quest_still_serves_lesson_and_qcm_of_local_only_lesson(tmp_path):
    c = _client(tmp_path, True)
    con = sqlite3.connect(tmp_path / "f.db")
    con.execute("DELETE FROM quest_steps WHERE lesson_id = 'l2'")
    con.commit()
    con.close()
    assert _kinds(c) == [("lesson", "l2"), ("qcm", "l2")]


def test_remote_quest_step_for_local_only_tp_is_refused_not_409(tmp_path):
    r = _client(tmp_path, True).post("/api/quest/step", json={"kind": "tp", "lesson_id": "l2"})
    assert r.status_code == 403
