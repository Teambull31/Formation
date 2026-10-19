"""Shared guards for the cloud connectors (read-only, token never leaked)."""
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse

from mail_source import ConnectorError


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # a redirect would resend the token to another host


_OPENER = urllib.request.build_opener(_NoRedirect)


def same_origin(url: str, base_url: str) -> bool:
    a, b = urlparse(url), urlparse(base_url)
    return (a.scheme, a.netloc) == (b.scheme, b.netloc)


def get_json(url: str, token: str, base_url: str):
    """The only HTTP verb the connectors have: GET, pinned to base_url's host."""
    if not same_origin(url, base_url):  # SSRF / token-leak guard (e.g. a hostile nextLink)
        raise ConnectorError("URL hors du serveur configuré : refusée")
    req = urllib.request.Request(url, method="GET", headers={"Authorization": f"Bearer {token}"})
    try:
        with _OPENER.open(req, timeout=15) as r:
            return json.loads(r.read(5_000_000))
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise ConnectorError("authentification refusée (401)") from None
        raise ConnectorError(f"erreur HTTP {e.code}") from None
    except (urllib.error.URLError, OSError, ValueError):
        raise ConnectorError("serveur injoignable ou réponse invalide") from None


def write_private(path, text: str) -> None:
    """Token cache: owner-only (0600), even if the file already existed wider."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        os.fchmod(f.fileno(), 0o600)  # os.open's mode is ignored on an existing file
        f.write(text)
