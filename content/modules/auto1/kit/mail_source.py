"""Sources de mails : un fichier JSON ou une boîte mbox, même interface."""
import html
import json
import mailbox
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Protocol

MAX_BODY = 20_000
MARKER = "… [tronqué]"
EPOCH = "1970-01-01T00:00:00Z"


@dataclass(frozen=True)
class Mail:
    id: str
    sender: str
    subject: str
    received: str  # ISO 8601 UTC, ex. 2026-03-02T08:15:00Z
    body: str


class MailSource(Protocol):
    def fetch(self, since: datetime | None = None, limit: int = 50) -> list[Mail]: ...


def html_to_text(raw: str) -> str:
    """Retire script/style et balises, décode les entités. Volontairement rudimentaire."""
    raw = re.sub(r"(?is)<(script|style).*?</\1>", "", raw)
    return html.unescape(re.sub(r"(?s)<[^>]*>", "", raw))


def _truncate(body: str) -> str:
    return body if len(body) <= MAX_BODY else body[: MAX_BODY - len(MARKER)] + MARKER


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _iso(dt: datetime) -> str:
    return _utc(dt).strftime("%Y-%m-%dT%H:%M:%SZ")


def _select(mails: list[Mail], since: datetime | None, limit: int) -> list[Mail]:
    """Plus récents d'abord ; garde ceux reçus à partir de `since`, au plus `limit`."""
    mails = sorted(mails, key=lambda m: m.received, reverse=True)
    if since is not None:
        mails = [m for m in mails if m.received >= _iso(since)]
    return mails[:limit]


class JsonMailSource:
    def __init__(self, path):
        self.path = Path(path)

    def fetch(self, since: datetime | None = None, limit: int = 50) -> list[Mail]:
        rows = json.loads(self.path.read_text(encoding="utf-8"))
        mails = [Mail(r["id"], r["sender"], r["subject"], r["received"], _truncate(r["body"])) for r in rows]
        return _select(mails, since, limit)


def _decode(value) -> str:
    return str(make_header(decode_header(str(value)))) if value else ""


def _body(msg) -> str:
    """Texte brut si présent, sinon HTML converti en texte."""
    parts = [p for p in msg.walk() if not p.is_multipart() and p.get_content_disposition() != "attachment"]
    for kind in ("text/plain", "text/html"):
        for p in parts:
            if p.get_content_type() == kind:
                text = p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8", errors="replace")
                return html_to_text(text) if kind == "text/html" else text
    return ""


class MboxMailSource:
    def __init__(self, path):
        self.path = Path(path)

    def fetch(self, since: datetime | None = None, limit: int = 50) -> list[Mail]:
        mails = []
        for i, msg in enumerate(mailbox.mbox(self.path)):
            try:
                received = _iso(parsedate_to_datetime(msg["Date"]))
            except (TypeError, ValueError):  # En-tête Date absent ou illisible
                received = EPOCH
            mails.append(Mail(
                id=(msg["Message-ID"] or "").strip("<> \n") or f"mbox-{i}",
                sender=_decode(msg["From"]) or "inconnu@example.test",
                subject=_decode(msg["Subject"]) or "(sans objet)",
                received=received,
                body=_truncate(_body(msg)),
            ))
        return _select(mails, since, limit)
