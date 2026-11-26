import json
from datetime import date

import pytest
from pywebpush import WebPushException

from app import push
from app.db import connect

OK_URL = "https://fcm.googleapis.com/fcm/send/abc"
SUB = {"endpoint": OK_URL, "keys": {"p256dh": "BPk", "auth": "au"}}


@pytest.fixture
def db(tmp_path):
    return connect(str(tmp_path / "t.db"))


@pytest.mark.parametrize("url,ok", [
    (OK_URL, True),
    ("https://updates.push.services.mozilla.com/wpush/v2/x", True),
    ("https://web.push.apple.com/Q", True),
    ("http://fcm.googleapis.com/x", False),            # not https
    ("https://evil.com/fcm.googleapis.com", False),    # host only in the path
    ("https://fcm.googleapis.com.evil.com/x", False),  # look-alike host
    ("https://169.254.169.254/latest", False),         # cloud metadata
    ("https://user@fcm.googleapis.com/x", False),
    ("https://fcm.googleapis.com:8443/x", False),
])
def test_endpoint_allowlist(url, ok):
    assert push.endpoint_ok(url) is ok


def test_vapid_created_once_and_stable(db):
    _, k1 = push.vapid(db)
    _, k2 = push.vapid(db)
    assert k1 == k2 and len(k1) == 87  # 65-byte uncompressed point, base64url without padding


def test_send_prunes_gone_subscriptions(db):
    push.subscribe(db, SUB)
    push.subscribe(db, {**SUB, "endpoint": "https://fcm.googleapis.com/fcm/send/ok"})
    calls = []

    class Gone:
        status_code = 410

    def sender(sub, **kw):
        calls.append(json.loads(kw["data"]))
        if sub["endpoint"] == OK_URL:
            raise WebPushException("gone", response=Gone())

    assert push.send_all(db, "T", "B", sender=sender) == 1
    assert push.count_subs(db) == 1 and calls[0] == {"title": "T", "body": "B"}


def test_network_error_keeps_subscription(db):
    push.subscribe(db, SUB)

    def sender(*a, **k):
        raise OSError("offline")

    assert push.send_all(db, "T", "B", sender=sender) == 0 and push.count_subs(db) == 1


def test_forged_endpoint_in_db_is_never_called(db):
    db.execute("INSERT INTO push_subs VALUES ('https://169.254.169.254/x', 'a', 'b')")
    db.commit()
    assert push.send_all(db, "T", "B", sender=lambda *a, **k: pytest.fail("called")) == 0


def test_reminder_rules(db):
    today = date(2026, 10, 23)
    sent = []
    sender = lambda *a, **k: sent.append(1)  # noqa: E731
    assert push.remind(db, today, 3, sender=sender) == 0  # nobody subscribed
    push.subscribe(db, SUB)
    db.execute("INSERT INTO activity_days VALUES ('2026-10-23')")
    db.commit()
    assert push.remind(db, today, 3, sender=sender) == 0  # already worked today
    db.execute("DELETE FROM activity_days")
    db.execute("INSERT INTO rest_days VALUES ('2026-10-23')")
    db.commit()
    assert push.remind(db, today, 3, sender=sender) == 0  # announced rest
    db.execute("DELETE FROM rest_days")
    db.commit()
    assert push.remind(db, today, 3, sender=sender) == 1
    assert push.remind(db, today, 3, sender=sender) == 0  # once a day
    assert push.remind(db, date(2026, 10, 24), 3, sender=sender) == 1  # next day again
    assert len(sent) == 2


def test_failed_send_does_not_burn_the_day(db):
    push.subscribe(db, SUB)

    def sender(*a, **k):
        raise OSError("offline")

    assert push.remind(db, date(2026, 10, 23), 0, sender=sender) == 0
    assert push.remind(db, date(2026, 10, 23), 0, sender=lambda *a, **k: None) == 1


# ---- API ----

def test_api_key_subscribe_unsubscribe(client):
    k = client.get("/api/push/key").json()
    assert len(k["key"]) == 87 and k["subscribed"] is False
    assert client.post("/api/push/subscribe", json=SUB).status_code == 200
    assert client.get("/api/push/key").json()["subscribed"] is True
    assert client.post("/api/push/unsubscribe", json={"endpoint": OK_URL}).status_code == 200
    assert client.get("/api/push/key").json()["subscribed"] is False


def test_api_rejects_unknown_push_service(client):
    bad = {**SUB, "endpoint": "https://169.254.169.254/x"}
    assert client.post("/api/push/subscribe", json=bad).status_code == 422
    assert client.post("/api/push/subscribe", json={"endpoint": OK_URL}).status_code == 422


def test_api_test_without_subscription_is_503(client):
    assert client.post("/api/push/test").status_code == 503


def test_reminder_only_at_chosen_hour(db):
    sent = []
    push.subscribe(db, SUB)
    sender = lambda *a, **k: sent.append(1)  # noqa: E731
    assert push.remind(db, date(2026, 10, 23), 0, sender=sender, hour=18) == 0  # défaut : 19 h
    assert push.remind(db, date(2026, 10, 23), 0, sender=sender, hour=19) == 1
    db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES ('remind_hour', '7')")
    assert push.remind(db, date(2026, 10, 24), 0, sender=sender, hour=7) == 1


def test_reminder_carries_question_url_and_actions(db):
    import json as _json
    push.subscribe(db, SUB)
    sent = []
    push.remind(db, date(2026, 10, 23), 0, sender=lambda *a, **k: sent.append(_json.loads(k["data"])), question="Où vit un workflow ?")
    assert sent[0]["title"].endswith("question du jour") and sent[0]["body"].startswith("Où vit un workflow ?")
    assert sent[0]["url"] == "/?tab=revisions" and [a["action"] for a in sent[0]["actions"]] == ["ecoute", "mini"]


def test_question_of_day_reads_due_question(db, tmp_path):
    import shutil
    from pathlib import Path
    from app.notify import question_of_day
    from app.review import record_answer
    shutil.copytree(Path(__file__).parent / "fixtures" / "demo_module", tmp_path / "modules" / "demo")
    qid = _json_first_qid(tmp_path)
    assert question_of_day(db, tmp_path, date(2026, 1, 2)) is None
    record_answer(db, qid, False, date(2026, 1, 1))
    assert question_of_day(db, tmp_path, date(2026, 1, 2))


def _json_first_qid(root):
    import json as _json
    return _json.loads((root / "modules" / "demo" / "lessons" / "l1.qcm.json").read_text())[0]["id"]


def test_weekly_digest_on_sunday_once(db):
    import json as _json
    push.subscribe(db, SUB)
    sun = date(2026, 11, 29)
    db.executemany("INSERT INTO activity_days VALUES (?)", [("2026-11-24",), ("2026-11-26",), ("2026-11-29",)])
    db.executemany("INSERT INTO review_log(day, correct) VALUES (?, ?)", [("2026-11-26", 1)] * 3 + [("2026-11-26", 0)])
    sent = []
    s = lambda *a, **k: sent.append(_json.loads(k["data"]))  # noqa: E731
    assert push.weekly_digest(db, date(2026, 11, 28), sender=s) == 0  # samedi
    assert push.weekly_digest(db, sun, sender=s, hour=8) == 0  # pas l'heure choisie (19 h)
    assert push.weekly_digest(db, sun, sender=s, hour=19) == 1
    assert push.weekly_digest(db, sun, sender=s, hour=19) == 0  # une fois par semaine
    assert sent[0]["body"].startswith("3 jour(s) actif(s) sur 7") and "75 %" in sent[0]["body"] and "4 jours" in sent[0]["body"]
    assert sent[0]["url"] == "/?tab=semaine"


def test_tp_digest_saturday_morning_once(db):
    import json as _json
    push.subscribe(db, SUB)
    sent = []
    s = lambda *a, **k: sent.append(_json.loads(k["data"]))  # noqa: E731
    sat = date(2026, 11, 28)
    assert push.tp_digest(db, sat, [], sender=s, hour=10) == 0  # rien en attente
    assert push.tp_digest(db, date(2026, 11, 27), ["ci3"], sender=s, hour=10) == 0  # vendredi
    assert push.tp_digest(db, sat, ["ci3"], sender=s, hour=9) == 0
    assert push.tp_digest(db, sat, ["ci3", "ci5"], sender=s, hour=10) == 1
    assert push.tp_digest(db, sat, ["ci3", "ci5"], sender=s, hour=10) == 0
    assert sent[0]["title"].endswith("2 TP t'attendent") and "ci3, ci5" in sent[0]["body"]


def test_streak_saver_at_21h_only_if_streak_and_nothing_done(db):
    import json as _json
    push.subscribe(db, SUB)
    sent = []
    s = lambda *a, **k: sent.append(_json.loads(k["data"]))  # noqa: E731
    d = date(2026, 11, 26)
    assert push.streak_saver(db, d, 0, sender=s, hour=21) == 0  # pas de série à perdre
    assert push.streak_saver(db, d, 3, sender=s, hour=20) == 0
    assert push.streak_saver(db, d, 3, sender=s, hour=21) == 1
    assert push.streak_saver(db, d, 3, sender=s, hour=21) == 0  # une fois par soir
    assert sent[0]["url"].endswith("mini=1") and sent[0]["actions"][0]["action"] == "mini"
    db.execute("INSERT INTO activity_days VALUES ('2026-11-27')")
    assert push.streak_saver(db, date(2026, 11, 27), 4, sender=s, hour=21) == 0  # déjà travaillé
