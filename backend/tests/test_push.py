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
