"""Gmail API. Read-only: scope gmail.readonly, GET only."""
import base64
import logging
from datetime import datetime, timezone
from pathlib import Path

from _http import get_json, write_private
from mail_source import Mail, _iso, _select, _truncate, html_to_text

log = logging.getLogger(__name__)
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]  # no send, no modify


def _b64(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")


def _find(part, mime):
    if part.get("mimeType") == mime and part.get("body", {}).get("data"):
        return _b64(part["body"]["data"])
    for sub in part.get("parts", []):
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
    def __init__(self, credentials_path, token_path, base_url="https://gmail.googleapis.com/gmail/v1", auth=None):
        self.credentials_path, self.token_path = Path(credentials_path), Path(token_path)
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
        token = self._token()
        listing = get_json(f"{self.base_url}/users/me/messages?maxResults={min(limit, 50)}", token, self.base_url)
        mails = []
        for ref in listing.get("messages", [])[:limit]:
            m = get_json(f"{self.base_url}/users/me/messages/{ref['id']}?format=full", token, self.base_url)
            h = {x["name"].lower(): x["value"] for x in m.get("payload", {}).get("headers", [])}
            received = _iso(datetime.fromtimestamp(int(m.get("internalDate", 0)) / 1000, timezone.utc))
            mails.append(Mail(id=m["id"], sender=h.get("from", "inconnu@example.test"),
                              subject=h.get("subject", "(sans objet)"), received=received,
                              body=_truncate(_body(m.get("payload", {})))))
        log.info("gmail: %d mails fetched", len(mails))  # counts only
        return _select(mails, since, limit)
