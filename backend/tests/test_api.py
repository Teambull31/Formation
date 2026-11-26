import json
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


def test_lessons_index_lists_titles_only(client):
    r = client.get("/api/lessons")
    assert r.status_code == 200
    ids = [les["id"] for m in r.json() for les in m["lessons"]]
    assert "l1" in ids and "body_md" not in r.text and "answer" not in r.text


def test_fiche_listed_and_downloadable(client):
    mods = client.get("/api/lessons").json()
    assert [m["fiche"] for m in mods] == [True]
    r = client.get(f"/api/fiche/{mods[0]['id']}")
    assert r.status_code == 200 and r.json()["body_md"].startswith("# Fiche")
    assert client.get("/api/fiche/nope").status_code == 404


def test_unknown_lesson_404(client):
    assert client.get("/api/lesson/nope").status_code == 404


def test_wrong_answer_returns_explanation_and_remedial(client):
    r = client.post("/api/qcm/answer", json={"question_id": "q1", "chosen": 0}).json()
    assert r["correct"] is False and r["explanation"] and r["remedial_lesson_id"]
    assert client.get("/api/reviews").status_code == 200


def test_reviews_lists_due_questions_and_box_counts(client, monkeypatch):
    from datetime import date, timedelta

    import app.main as m

    class Tomorrow(date):
        @classmethod
        def today(cls):
            return date.today() + timedelta(days=1)

    r = client.get("/api/reviews").json()
    assert r["due"] == [] and r["questions"] == [] and r["boxes"] == [0] * 5 and r["intervals"] == [1, 2, 4, 7, 14]
    client.post("/api/qcm/answer", json={"question_id": "q1", "chosen": 0})  # wrong -> box 0, due tomorrow
    monkeypatch.setattr(m, "date", Tomorrow)
    r = client.get("/api/reviews").json()
    assert r["due"] == ["q1"]
    q = r["questions"][0]
    assert q["id"] == "q1" and q["options"] and q["box"] == 0 and "answer" not in q and "explain" not in q
    assert r["boxes"] == [1, 0, 0, 0, 0]


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
       ("post", "/api/weekly/import"), ("post", "/api/tp/t1/hint"), ("post", "/api/feynman/l1"),
       ("get", "/api/portfolio.zip")]


@pytest.mark.parametrize("method,url", BAD)
@pytest.mark.parametrize("headers", [{"origin": "http://evil.com"}, {"host": "evil.com"}])
def test_local_peer_with_bad_origin_or_host_is_403(client, method, url, headers):
    kw = {"json": {"path": "/tmp/x"}} if "import" in url else {"json": {"level": 1}} if "hint" in url else {"json": {"explanation": "x" * 50}} if "feynman" in url else {}
    assert getattr(client, method)(url, headers=headers, **kw).status_code == 403


def test_remote_cannot_hint(remote_client):
    assert remote_client.post("/api/tp/t1/hint", json={"level": 1}).status_code == 403


def test_audio_failure_leaves_no_partial(client, tmp_path, monkeypatch):
    import app.main as m

    def boom(text, out, engine="espeak"):
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"partial")
        raise RuntimeError("fail")

    monkeypatch.setattr("app.audio.synthesize", boom)
    assert client.get("/api/audio/l1.mp3").status_code == 503
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
    assert isinstance(r["output"], str)


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
    for f in src.rglob("tp.json"):  # un module importé ne peut pas reprendre l'id d'un TP existant
        f.write_text(f.read_text().replace('"id": "t1"', '"id": "wk-t1"').replace('"id": "t2"', '"id": "wk-t2"'))
    r = client.post("/api/weekly/import", json={"path": str(src)})
    assert r.json() == {"module_id": "wk2"}
    assert client.get("/api/lesson/n1").status_code == 200


def test_weekly_brief(client):
    client.post("/api/qcm/answer", json={"question_id": "q1", "chosen": 0})
    b = client.post("/api/weekly/brief", json={"topic": "Docker", "format": "court"}).json()["brief"]
    assert "Docker" in b and "q1" in b


def test_audio_rejects_traversal_and_unknown(client):
    assert client.get("/api/audio/a.b.mp3").status_code == 404
    assert client.get("/api/audio/..%2Fx.mp3").status_code == 404
    assert client.get("/api/audio/nope.mp3").status_code == 404
    assert client.get("/api/audio/l1.ogg").status_code == 404


@pytest.mark.skipif(shutil.which("espeak-ng") is None, reason="espeak-ng absent")
def test_audio_falls_back_to_wav_with_espeak(client):
    r = client.get("/api/audio/l1.mp3")
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav"


def test_audio_serves_edge_mp3(client, monkeypatch):
    monkeypatch.setenv("FORMATION_TTS", "edge")
    def fake_edge(text, out):
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"ID3x")
        return out

    monkeypatch.setattr("app.audio._synthesize_edge", fake_edge)
    r = client.get("/api/audio/l1.mp3")
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and r.content == b"ID3x"


def test_audio_regenerated_when_lesson_changes(client, tmp_path, monkeypatch):
    import os
    monkeypatch.setenv("FORMATION_TTS", "edge")
    texts = []
    def fake_edge(text, out):
        texts.append(text)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(f"ID3-{len(texts)}".encode())
        return out

    monkeypatch.setattr("app.audio._synthesize_edge", fake_edge)
    assert client.get("/api/audio/l1.mp3").content == b"ID3-1"
    assert client.get("/api/audio/l1.mp3").content == b"ID3-1"  # en cache : pas de nouvelle synthèse
    md = next((tmp_path / "content").rglob("l1.md"))
    mp3 = next(tmp_path.rglob("audio/l1.mp3"))
    os.utime(mp3, (1, 1))  # l'audio date d'avant la dernière modification de la leçon
    assert client.get("/api/audio/l1.mp3").content == b"ID3-2" and len(texts) == 2
    monkeypatch.setattr("app.audio._synthesize_edge", lambda *a: (_ for _ in ()).throw(RuntimeError("hors ligne")))
    monkeypatch.setattr("shutil.which", lambda *_: None)
    os.utime(mp3, (1, 1))
    assert client.get("/api/audio/l1.mp3").content == b"ID3-2"  # synthèse impossible : l'ancien audio reste servi
    assert md.exists()


def test_audio_503_without_espeak(client, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda *_: None)
    assert client.get("/api/audio/l1.mp3").status_code == 503


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


def test_two_bosses_selectable_by_id(tmp_path):
    import json
    import shutil
    from pathlib import Path

    from starlette.testclient import TestClient

    from app.main import create_app
    from tests.conftest import app_client
    app_client(tmp_path, "127.0.0.1")  # lays out content/ + ws/ under tmp_path
    other = tmp_path / "content" / "boss" / "zz_boss"
    shutil.copytree(Path(__file__).parent / "fixtures" / "demo_boss", other)
    meta = json.loads((other / "boss.json").read_text())
    meta.update(id="zz_boss", title="Second boss")
    (other / "boss.json").write_text(json.dumps(meta))
    app = create_app(str(tmp_path / "g.db"), tmp_path / "content", tmp_path / "ws")
    c = TestClient(app, base_url="http://localhost", client=("127.0.0.1", 50000))
    assert c.get("/api/boss").json()["id"] == "demo_boss"  # default = first
    b = c.get("/api/boss", params={"id": "zz_boss"}).json()
    assert b["title"] == "Second boss" and [x["id"] for x in b["bosses"]] == ["demo_boss", "zz_boss"]
    assert c.post("/api/boss/attempt", params={"id": "zz_boss"}).json()["attempts"] == 1
    assert c.get("/api/boss").json()["attempts"] == 0  # attempts counted per boss
    assert c.get("/api/boss", params={"id": "nope"}).status_code == 404


def test_qcm_xp_scales_with_first_try_answers(client):
    client.post("/api/qcm/answer", json={"question_id": "q1", "chosen": 0})  # wrong
    client.post("/api/qcm/answer", json={"question_id": "q1", "chosen": 1})  # right later: first try counts
    client.post("/api/quest/step", json={"kind": "qcm", "lesson_id": "l1"})
    assert client.get("/api/team").json()["xp"] == 0


def test_qcm_xp_full_when_first_try_right(client):
    client.post("/api/qcm/answer", json={"question_id": "q1", "chosen": 1})
    client.post("/api/qcm/answer", json={"question_id": "q2", "chosen": 1})  # wrong: half the XP
    client.post("/api/quest/step", json={"kind": "qcm", "lesson_id": "l1"})
    assert client.get("/api/team").json()["xp"] == 20


def test_removed_question_not_counted_as_due(client, tmp_path):
    from app.db import connect
    db = connect(str(tmp_path / "t.db"))
    db.execute("INSERT OR REPLACE INTO mistakes(question_id, box, due) VALUES ('gone', 0, '2000-01-01')")
    db.commit()
    r = client.get("/api/reviews").json()
    assert "gone" not in r["due"] and len(r["due"]) == len(r["questions"])


EXPL = {"explanation": "Une image est un modèle figé, un conteneur est une instance qui tourne à partir d'elle."}


def _grade(monkeypatch, *scores):
    import app.llm as llm
    it = iter(scores)
    monkeypatch.setattr(llm, "grade_explanation", lambda *a, **k: {"score": next(it), "missing": ["x"], "feedback": "ok"})


def test_feynman_pays_only_improvements(client, monkeypatch):
    _grade(monkeypatch, 50, 50, 100, 20)
    xps = [client.post("/api/feynman/l1", json=EXPL).json() for _ in range(4)]
    assert [x["xp"] for x in xps] == [30, 0, 30, 0]  # 60 max per lesson, never negative
    assert [x["best"] for x in xps] == [50, 50, 100, 100]
    assert client.get("/api/team").json()["xp"] == 60


def test_feynman_validation_and_unknown_lesson(client, monkeypatch):
    _grade(monkeypatch, 80)
    assert client.post("/api/feynman/l1", json={"explanation": "trop court"}).status_code == 422
    assert client.post("/api/feynman/zz", json=EXPL).status_code == 404


def test_feynman_503_when_ollama_down(client, monkeypatch):
    import app.llm as llm

    def down(*a, **k):
        raise llm.LlmUnavailable("Ollama indisponible")

    monkeypatch.setattr(llm, "grade_explanation", down)
    r = client.post("/api/feynman/l1", json=EXPL)
    assert r.status_code == 503 and "Ollama" in r.json()["detail"]
    assert client.get("/api/team").json()["xp"] == 0


def test_remote_cannot_feynman(remote_client):
    assert remote_client.post("/api/feynman/l1", json=EXPL).status_code == 403


def test_podcast_lists_present_episodes_and_serves_them(client, tmp_path):
    assert client.get("/api/podcast").json() == []  # fixture sans dossier podcast
    assert client.get("/api/podcast/..%2Fgacha.json").status_code == 404
    assert client.get("/api/podcast/nope.mp3").status_code == 404
    p = tmp_path / "content" / "podcast"
    p.mkdir()
    (p / "episodes.json").write_text('[{"file": "ep01.mp3", "title": "Un", "minutes": 10}, {"file": "ep02.mp3", "title": "Absent", "minutes": 9}]')
    (p / "ep01.mp3").write_bytes(b"ID3fake")
    assert [e["file"] for e in client.get("/api/podcast").json()] == ["ep01.mp3"]
    client.post("/api/podcast/ep01.mp3/done")
    assert client.get("/api/podcast").json()[0]["listened"] == 1
    r = client.get("/api/podcast/ep01.mp3")
    assert r.status_code == 200 and r.content == b"ID3fake" and r.headers["content-type"] == "audio/mpeg"


def _fake_edge(monkeypatch):
    texts = []
    monkeypatch.setenv("FORMATION_TTS", "edge")

    def fake(text, out):
        texts.append(text)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"ID3")
        return out

    monkeypatch.setattr("app.audio._synthesize_edge", fake)
    return texts


def test_fiche_audio(client, monkeypatch):
    texts = _fake_edge(monkeypatch)
    mid = next(m["id"] for m in client.get("/api/lessons").json() if m["fiche"])
    r = client.get(f"/api/fiche-audio/{mid}.mp3")
    assert r.status_code == 200 and texts[0].startswith("Fiche de révision")
    assert client.get("/api/fiche-audio/nope.mp3").status_code == 404
    assert client.get("/api/fiche-audio/..%2Fx.mp3").status_code == 404


def test_revision_express_reads_due_mistakes(client, monkeypatch):
    texts = _fake_edge(monkeypatch)
    assert client.get("/api/revision").json() == {"items": 0, "key": None}
    les = client.get("/api/lesson/l1").json()
    q = les["qcm"][0]
    wrong = next(i for i in range(len(q["options"])) if not client.post("/api/qcm/answer", json={"question_id": q["id"], "chosen": i}).json()["correct"])
    assert wrong is not None
    import app.main as m  # l'erreur est due demain : on avance la date
    from datetime import date, timedelta
    monkeypatch.setattr(m, "date", type("D", (), {"today": staticmethod(lambda: date.today() + timedelta(days=30))}))
    info = client.get("/api/revision").json()
    assert info["items"] >= 1 and info["key"]
    assert client.get("/api/revision/deadbeef.mp3").status_code == 404  # clé périmée
    assert client.get(f"/api/revision/{info['key']}.mp3").status_code == 200
    assert q["text"] in texts[0] and "Réponse :" in texts[0]


def test_wrong_answer_points_back_to_its_lesson(client):
    q = client.get("/api/lesson/l1").json()["qcm"][0]
    rs = [client.post("/api/qcm/answer", json={"question_id": q["id"], "chosen": i}).json() for i in range(len(q["options"]))]
    wrong = next(r for r in rs if not r["correct"])
    right = next(r for r in rs if r["correct"])
    assert wrong["lesson_id"] == "l1" and wrong["answer"] in q["options"]
    assert right["lesson_id"] is None and right["answer"] is None


def test_lesson_keys_lists_lesson_cards(client, tmp_path):
    md = next((tmp_path / "content").rglob("l1.md"))
    md.write_text(md.read_text() + "\n\n!!Ne jamais committer un secret.!!\n\nUn **runner** exécute les jobs.\n")
    keys = client.get("/api/lesson/l1/keys").json()
    assert keys and all({"front", "back", "kind"} <= set(k) for k in keys)
    assert client.get("/api/lesson/nope/keys").status_code == 404


def test_reviews_offer_questions_ahead_when_nothing_due(client):
    assert client.get("/api/reviews").json()["ahead"] == []
    for q in client.get("/api/lesson/l1").json()["qcm"]:
        r = next(i for i in range(len(q["options"])) if client.post("/api/qcm/answer", json={"question_id": q["id"], "chosen": i}).json()["correct"])
        assert r is not None
    d = client.get("/api/reviews").json()
    assert d["questions"] == [] and 1 <= len(d["ahead"]) <= 3 and "answer" not in str(d["ahead"])


def test_weak_points_group_fragile_mistakes_by_lesson(client):
    assert client.get("/api/weak").json() == []
    q = client.get("/api/lesson/l1").json()["qcm"][0]
    next(i for i in range(len(q["options"])) if not client.post("/api/qcm/answer", json={"question_id": q["id"], "chosen": i}).json()["correct"])
    w = client.get("/api/weak").json()
    assert w[0]["lesson_id"] == "l1" and w[0]["count"] >= 1


def test_cards_per_day_setting(client):
    for i in range(3):
        client.post("/api/cards/panne", json={"symptom": f"panne numéro {i}", "cause": "cause", "fix": "correction"})
    assert client.get("/api/cards").json()["per_day"] == 10
    assert len(client.get("/api/cards").json()["cards"]) == 3
    assert client.post("/api/cards/per-day", json={"per_day": 2}).status_code == 200
    d = client.get("/api/cards").json()
    assert d["per_day"] == 2 and len(d["cards"]) == 2
    assert client.post("/api/cards/per-day", json={"per_day": 99}).status_code == 422


def test_revision_express_always_has_an_interview_question(client, tmp_path, monkeypatch):
    texts = _fake_edge(monkeypatch)
    (tmp_path / "content" / "interview").mkdir()
    (tmp_path / "content" / "interview" / "questions.json").write_text(json.dumps([
        {"id": "iv1", "role": "DevOps", "question": "Qu'est-ce que l'idempotence ?", "time_limit": 90,
         "keywords": [["idée", "idempot"]], "model_answer": "Rejouer sans changer le résultat. Exemple : terraform apply. Fin. Ignoré."}]))
    info = client.get("/api/revision").json()
    assert info["key"]  # rien d'autre à réviser : la question d'entretien suffit
    assert client.get(f"/api/revision/{info['key']}.mp3").status_code == 200
    assert "Question d'entretien : Qu'est-ce que l'idempotence ?" in texts[0]
    assert "Réponse type : Rejouer sans changer le résultat. Exemple : terraform apply. Fin." in texts[0] and "Ignoré" not in texts[0]


def test_rephrase_endpoint(client, monkeypatch):
    import app.llm as llm
    monkeypatch.setattr(llm, "rephrase", lambda title, text: f"Autrement : {title}")
    assert client.post("/api/lesson/l1/rephrase", json={"text": "une page de cours assez longue"}).json()["text"].startswith("Autrement")
    def down(title, text):
        raise llm.LlmUnavailable("indispo")
    monkeypatch.setattr(llm, "rephrase", down)
    assert client.post("/api/lesson/l1/rephrase", json={"text": "une page de cours assez longue"}).status_code == 503
    assert client.post("/api/lesson/nope/rephrase", json={"text": "une page de cours assez longue"}).status_code == 404


def test_unclear_pages_noted_listed_and_cleared(client):
    for _ in range(2):  # deux fois la même page : une seule ligne
        assert client.post("/api/unclear", json={"lesson_id": "l1", "excerpt": "Partie 1"}).status_code == 200
    items = client.get("/api/unclear").json()
    assert len(items) == 1 and items[0]["lesson_id"] == "l1" and items[0]["excerpt"] == "Partie 1"
    assert client.post("/api/unclear", json={"lesson_id": "nope", "excerpt": "x"}).status_code == 404
    client.delete(f"/api/unclear/{items[0]['id']}")
    assert client.get("/api/unclear").json() == []


def test_today_recap(client):
    r = client.get("/api/today").json()
    assert r == {"lessons": [], "reviewed": 0, "correct": 0, "tomorrow": 0}
    q = client.get("/api/lesson/l1").json()["qcm"][0]
    next(i for i in range(len(q["options"])) if not client.post("/api/qcm/answer", json={"question_id": q["id"], "chosen": i}).json()["correct"])
    assert client.get("/api/today").json()["tomorrow"] >= 1  # l'erreur revient (due aujourd'hui, donc aussi demain)
