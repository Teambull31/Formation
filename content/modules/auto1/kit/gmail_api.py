"""Gmail API. Read-only: scope gmail.readonly, GET only."""
import base64
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from _http import default_token_path, get_json, write_private
from mail_source import EPOCH, ConnectorError, Mail, _iso, _select, _truncate, html_to_text

log = logging.getLogger(__name__)
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]  # no send, no modify


def _b64(data: str) -> str:
    try:
        return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")
    except ValueError:  # binascii.Error: one bad mail must not kill the batch
        return ""


def _find(part, mime):
    if not isinstance(part, dict):
        return None
    data = (part.get("body") or {}).get("data") if isinstance(part.get("body"), dict) else None
    if part.get("mimeType") == mime and isinstance(data, str) and data:
        return _b64(data)
    for sub in part.get("parts") if isinstance(part.get("parts"), list) else []:
        if (found := _find(sub, mime)) is not None:
            return found


def _body(payload) -> str:
    """text/plain first, else text/html converted to text."""
    plain = _find(payload, "text/plain")
    if plain is not None:
        return plain
    page = _find(payload, "text/html")
    return html_to_text(page) if page is not None else ""


class GmailSource:
    def __init__(self, credentials_path, token_path=None, base_url="https://gmail.googleapis.com/gmail/v1", auth=None):
        self.credentials_path, self.token_path = Path(credentials_path), (Path(token_path) if token_path else default_token_path("gmail"))
        self.base_url, self.auth = base_url.rstrip("/"), auth

    def _token(self) -> str:
        if self.auth:
            return self.auth()
        try:  # lazy: the kit works without the Google libraries
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError:
            raise RuntimeError("Les paquets Google manquent : pip install google-auth google-auth-oauthlib "
                               "(les tests passent un jeton avec auth=).") from None
        creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES) if self.token_path.exists() else None
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        elif not creds or not creds.valid:
            creds = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), SCOPES).run_local_server(port=0)
        write_private(self.token_path, creds.to_json())
        return creds.token

    def fetch(self, since: datetime | None = None, limit: int = 50) -> list[Mail]:
        if limit <= 0:
            return []
        token = self._token()
        size = min(limit, 50)
        refs, page_token, seen = [], None, set()
        for _ in range(limit // size + 2):  # bound: a hostile server must not loop us forever
            url = f"{self.base_url}/users/me/messages?maxResults={size}"
            if page_token:
                url += f"&pageToken={quote(page_token, safe='')}"
            listing = get_json(url, token, self.base_url)
            batch = listing.get("messages") if isinstance(listing.get("messages"), list) else []
            refs += [r["id"] for r in batch if isinstance(r, dict) and isinstance(r.get("id"), str) and r["id"]]
            page_token = listing.get("nextPageToken")
            if not batch or len(refs) >= limit or not isinstance(page_token, str) or page_token in seen:
                break
            seen.add(page_token)
        mails = []
        for mid in refs[:limit]:
            # quote: an id like "../x?y" must stay one path segment
            m = get_json(f"{self.base_url}/users/me/messages/{quote(mid, safe='')}?format=full", token, self.base_url)
            payload = m.get("payload") if isinstance(m.get("payload"), dict) else {}
            rows = payload.get("headers") if isinstance(payload.get("headers"), list) else []
            h = {x["name"].lower(): x.get("value") for x in rows if isinstance(x, dict) and isinstance(x.get("name"), str)}
            mails.append(Mail(id=mid, sender=_str(h.get("from"), "inconnu@example.test"),
                              subject=_str(h.get("subject"), "(sans objet)"), received=_received(m.get("internalDate")),
                              body=_truncate(_body(payload))))
        log.info("gmail: %d mails fetched", len(mails))  # counts only
        return _select(mails, since, limit)


def _str(v, default):
    return v if isinstance(v, str) and v else default


def _received(ms) -> str:
    try:
        return _iso(datetime.fromtimestamp(int(ms) / 1000, timezone.utc))
    except (TypeError, ValueError, OverflowError, OSError):  # missing, huge or invalid
        return EPOCH
