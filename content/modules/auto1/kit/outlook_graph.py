"""Outlook / Microsoft 365 via Microsoft Graph. Read-only: scope Mail.Read, GET only."""
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

from _http import get_json, write_private
from mail_source import Mail, _normalise, _select, _truncate, html_to_text

log = logging.getLogger(__name__)
SCOPES = ["Mail.Read"]  # the least privilege: no send, no delete
FIELDS = "id,subject,from,receivedDateTime,body"


class OutlookGraphSource:
    def __init__(self, client_id, tenant="consumers", token_path="graph_token.json",
                 base_url="https://graph.microsoft.com/v1.0", auth=None):
        self.client_id, self.tenant, self.base_url, self.auth = client_id, tenant, base_url.rstrip("/"), auth
        self.token_path = Path(token_path)

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
            raise RuntimeError("Connexion Microsoft refusée (device code).")
        return result["access_token"]

    def fetch(self, since: datetime | None = None, limit: int = 50) -> list[Mail]:
        token = self._token()
        query = urlencode({"$select": FIELDS, "$orderby": "receivedDateTime desc", "$top": min(limit, 50)})
        url, mails = f"{self.base_url}/me/messages?{query}", []
        while url and len(mails) < limit:
            page = get_json(url, token, self.base_url)
            mails += [self._mail(m) for m in page.get("value", []) if isinstance(m, dict)]
            url = page.get("@odata.nextLink")
        log.info("outlook: %d mails fetched", len(mails))  # counts only, never content
        return _select(mails, since, limit)

    @staticmethod
    def _mail(m) -> Mail:
        body = m.get("body") or {}
        text = str(body.get("content") or "")
        if body.get("contentType") == "html":
            text = html_to_text(text)
        return Mail(
            id=str(m.get("id") or ""),
            sender=((m.get("from") or {}).get("emailAddress") or {}).get("address") or "inconnu@example.test",
            subject=m.get("subject") or "(sans objet)",
            received=_normalise(str(m.get("receivedDateTime") or "").replace("Z", "+00:00")),
            body=_truncate(text),
        )
