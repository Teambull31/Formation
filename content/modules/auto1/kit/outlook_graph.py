"""Outlook / Microsoft 365 via Microsoft Graph. Read-only: scope Mail.Read, GET only."""
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

from _http import default_token_path, get_json, write_private
from mail_source import ConnectorError, Mail, _normalise, _select, _truncate, html_to_text

log = logging.getLogger(__name__)
SCOPES = ["Mail.Read"]  # the least privilege: no send, no delete
FIELDS = "id,subject,from,receivedDateTime,body"


class OutlookGraphSource:
    def __init__(self, client_id, tenant="consumers", token_path=None,
                 base_url="https://graph.microsoft.com/v1.0", auth=None):
        self.client_id, self.tenant, self.base_url, self.auth = client_id, tenant, base_url.rstrip("/"), auth
        self.token_path = Path(token_path) if token_path else default_token_path("graph")

    def _token(self) -> str:
        if self.auth:  # tests and lessons inject a token provider
            return self.auth()
        try:
            import msal  # lazy: the kit works without it
        except ImportError:
            raise RuntimeError("Le paquet 'msal' manque : pip install msal "
                               "(les tests passent un jeton avec auth=, sans msal).") from None
        cache = msal.SerializableTokenCache()
        if self.token_path.exists():
            cache.deserialize(self.token_path.read_text(encoding="utf-8"))
        app = msal.PublicClientApplication(
            self.client_id, authority=f"https://login.microsoftonline.com/{self.tenant}", token_cache=cache)
        accounts = app.get_accounts()
        result = app.acquire_token_silent(SCOPES, account=accounts[0]) if accounts else None
        if not result:
            flow = app.initiate_device_flow(scopes=SCOPES)
            print(flow["message"])  # "go to https://microsoft.com/devicelogin and enter CODE"
            result = app.acquire_token_by_device_flow(flow)
        if cache.has_state_changed:
            write_private(self.token_path, cache.serialize())
        if "access_token" not in result:
            # error_description holds no secret (no token, no mail)
            raise RuntimeError(f"Connexion Microsoft refusée : {result.get('error_description', 'device code')}")
        return result["access_token"]

    def fetch(self, since: datetime | None = None, limit: int = 50) -> list[Mail]:
        if limit <= 0:
            return []
        token = self._token()
        query = urlencode({"$select": FIELDS, "$orderby": "receivedDateTime desc", "$top": min(limit, 50)})
        url, mails, seen = f"{self.base_url}/me/messages?{query}", [], set()
        for _ in range(limit // min(limit, 50) + 2):  # bound: a hostile server must not loop us forever
            if not url or url in seen or len(mails) >= limit:
                break
            seen.add(url)
            page = get_json(url, token, self.base_url)
            if not isinstance(page, dict):
                raise ConnectorError("réponse invalide")
            rows = [m for m in page.get("value", []) if isinstance(m, dict)] if isinstance(page.get("value"), list) else []
            if not rows:
                break
            mails += [self._mail(m) for m in rows]
            url = page.get("@odata.nextLink")
        log.info("outlook: %d mails fetched", len(mails))  # counts only, never content
        return _select(mails, since, limit)

    @staticmethod
    def _mail(m) -> Mail:
        """Any field may be missing or of the wrong type: fall back, never raise."""
        body = m.get("body") if isinstance(m.get("body"), dict) else {}
        sender = m.get("from") if isinstance(m.get("from"), dict) else {}
        addr = sender.get("emailAddress") if isinstance(sender.get("emailAddress"), dict) else {}
        text = body.get("content") if isinstance(body.get("content"), str) else ""
        if body.get("contentType") == "html":
            text = html_to_text(text)
        return Mail(
            id=str(m.get("id") or ""),
            sender=addr.get("address") if isinstance(addr.get("address"), str) and addr.get("address") else "inconnu@example.test",
            subject=m.get("subject") if isinstance(m.get("subject"), str) and m.get("subject") else "(sans objet)",
            received=_normalise(str(m.get("receivedDateTime") or "").replace("Z", "+00:00")),
            body=_truncate(text),
        )
