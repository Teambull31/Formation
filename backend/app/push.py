"""Rappel quotidien par notification Web Push (PWA)."""
import base64
import json
import os
import sqlite3
from datetime import date
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid
from pywebpush import WebPushException, webpush

# Le serveur POSTe vers l'endpoint fourni par le navigateur : seuls les services push connus sont acceptés.
PUSH_HOSTS = ("fcm.googleapis.com", "updates.push.services.mozilla.com", "push.apple.com",
              "notify.windows.com", "push.services.mozilla.com")
CONTACT = os.environ.get("FORMATION_PUSH_CONTACT", "mailto:formation@example.test")  # exigé par VAPID


def endpoint_ok(url: str) -> bool:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and parts.port in (None, 443) and not parts.username and \
        any(host == h or host.endswith("." + h) for h in PUSH_HOSTS)


def _setting(db: sqlite3.Connection, key: str) -> str | None:
    row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def _put(db: sqlite3.Connection, key: str, value: str) -> None:
    db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", (key, value))


def vapid(db: sqlite3.Connection) -> tuple[Vapid, str]:
    """Clés VAPID du serveur (créées au premier usage) et clé publique pour PushManager.subscribe."""
    pem = _setting(db, "vapid_private")
    if pem is None:
        v = Vapid()
        v.generate_keys()
        _put(db, "vapid_private", v.private_pem().decode())
        db.commit()
    else:
        v = Vapid.from_pem(pem.encode())
    raw = v.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    return v, base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def subscribe(db: sqlite3.Connection, sub: dict) -> None:
    db.execute("INSERT OR REPLACE INTO push_subs(endpoint, p256dh, auth) VALUES (?, ?, ?)",
               (sub["endpoint"], sub["keys"]["p256dh"], sub["keys"]["auth"]))
    db.commit()


def unsubscribe(db: sqlite3.Connection, endpoint: str) -> None:
    db.execute("DELETE FROM push_subs WHERE endpoint = ?", (endpoint,))
    db.commit()


def count_subs(db: sqlite3.Connection) -> int:
    return db.execute("SELECT COUNT(*) FROM push_subs").fetchone()[0]


def send_all(db: sqlite3.Connection, title: str, body: str, *, sender=webpush) -> int:
    """Envoie à tous les abonnements ; supprime ceux que le service push déclare disparus (404/410). Retourne les envois réussis."""
    v, _ = vapid(db)
    sent = 0
    for endpoint, p256dh, auth in db.execute("SELECT endpoint, p256dh, auth FROM push_subs").fetchall():
        if not endpoint_ok(endpoint):  # base modifiée à la main ? on n'appelle pas
            continue
        try:
            sender({"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}},
                   data=json.dumps({"title": title, "body": body}), vapid_private_key=v,
                   vapid_claims={"sub": CONTACT}, timeout=10)
            sent += 1
        except WebPushException as e:
            if e.response is not None and e.response.status_code in (404, 410):
                unsubscribe(db, endpoint)
        except Exception:  # réseau coupé : on réessaiera au prochain passage
            continue
    return sent


def reminder_due(db: sqlite3.Connection, today: date) -> bool:
    """Rappel seulement s'il y a des abonnés, aucune activité ni repos aujourd'hui, et pas déjà rappelé aujourd'hui."""
    day = today.isoformat()
    if count_subs(db) == 0 or _setting(db, "last_reminder") == day:
        return False
    return not db.execute("SELECT 1 FROM activity_days WHERE day = ? UNION SELECT 1 FROM rest_days WHERE day = ?",
                          (day, day)).fetchone()


def remind(db: sqlite3.Connection, today: date, streak: int, *, sender=webpush) -> int:
    if not reminder_due(db, today):
        return 0
    body = f"Ta série de {streak} jours t'attend : 15 minutes suffisent." if streak else "15 minutes aujourd'hui, et la série démarre."
    n = send_all(db, "Formation : quête du jour", body, sender=sender)
    if n:
        _put(db, "last_reminder", today.isoformat())
        db.commit()
    return n
