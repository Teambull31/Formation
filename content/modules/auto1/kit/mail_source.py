"""Sources de mails : un fichier JSON ou une boîte mbox, même interface."""
import json
import mailbox
from dataclasses import dataclass
from datetime import datetime, timezone
from email.header import decode_header
from html.parser import HTMLParser
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


class _TextOnly(HTMLParser):
    """Garde le texte visible ; ignore le contenu de <script> et <style>. Temps linéaire."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        self.skip += tag in ("script", "style")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_text(raw: str) -> str:
    """Retire script/style et balises, décode les entités. Entrée plafonnée à MAX_BODY*4 caractères."""
    parser = _TextOnly()
    parser.feed(raw[: MAX_BODY * 4])
    parser.close()
    return "".join(parser.parts)


def _text(data: bytes | None, charset: str | None) -> str:
    """Décode des octets ; charset inconnu ou invalide -> utf-8 avec remplacement."""
    try:
        return (data or b"").decode(charset or "utf-8", errors="replace")
    except (LookupError, UnicodeError):
        return (data or b"").decode("utf-8", errors="replace")


def _fallback(value, default: str) -> str:
    return value if isinstance(value, str) and value else default


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


def _normalise(received) -> str:
    """Date ISO 8601 (avec ou sans décalage) -> forme UTC en Z ; illisible -> 1970."""
    try:
        return _iso(datetime.fromisoformat(received))
    except (TypeError, ValueError):
        return EPOCH


class JsonMailSource:
    """Fichier absent, vide ou illisible -> liste vide. Champs manquants -> valeurs de repli."""

    def __init__(self, path):
        self.path = Path(path)

    def fetch(self, since: datetime | None = None, limit: int = 50) -> list[Mail]:
        try:
            rows = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):  # ValueError couvre JSON invalide et UnicodeDecodeError
            return []
        mails = []
        for i, r in enumerate(rows if isinstance(rows, list) else []):
            if not isinstance(r, dict):
                continue
            body = r.get("body")
            mails.append(Mail(
                id=_fallback(r.get("id"), f"json-{i}"),
                sender=_fallback(r.get("sender"), "inconnu@example.test"),
                subject=_fallback(r.get("subject"), "(sans objet)"),
                received=_normalise(r.get("received")),
                body=_truncate(body if isinstance(body, str) else ""),
            ))
        return _select(mails, since, limit)


def _decode(value) -> str:
    """En-tête MIME décodé (RFC 2047) ; charset inconnu -> utf-8 avec remplacement."""
    if not value:
        return ""
    try:
        pairs = decode_header(str(value))
    except Exception:  # en-tête mal formé : on garde le texte brut
        return str(value)
    return "".join(_text(p, cs) if isinstance(p, bytes) else p for p, cs in pairs)


def _body(msg) -> str:
    """Texte brut si présent, sinon HTML converti en texte."""
    parts = [p for p in msg.walk() if not p.is_multipart() and p.get_content_disposition() != "attachment"]
    for kind in ("text/plain", "text/html"):
        for p in parts:
            if p.get_content_type() == kind:
                text = _text(p.get_payload(decode=True), p.get_content_charset())
                return html_to_text(text) if kind == "text/html" else text
    return ""


class MboxMailSource:
    def __init__(self, path):
        self.path = Path(path)

    def fetch(self, since: datetime | None = None, limit: int = 50) -> list[Mail]:
        try:
            box = mailbox.mbox(self.path, create=False)  # ne crée jamais le fichier
        except mailbox.NoSuchMailboxError:
            return []
        mails = []
        for i, msg in enumerate(box):
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
