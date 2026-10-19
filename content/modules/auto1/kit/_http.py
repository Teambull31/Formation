"""Shared guards for the cloud connectors (read-only, token never leaked)."""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
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
            data = json.loads(r.read(5_000_000))
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise ConnectorError("authentification refusée (401)") from None
        raise ConnectorError(f"erreur HTTP {e.code}") from None
    except (urllib.error.URLError, OSError, ValueError):
        raise ConnectorError("serveur injoignable ou réponse invalide") from None
    if not isinstance(data, dict):  # every API we call answers with an object
        raise ConnectorError("réponse invalide")
    return data


def default_token_path(name: str) -> Path:
    """Under the home config dir, never relative to the cwd (a repo checkout would commit it)."""
    return Path.home() / ".config" / "formation-auto1" / f"{name}_token.json"


def write_private(path, text: str) -> None:
    """Token cache: owner-only (0600), even if the file already existed wider.

    POSIX only for the mode bits. On Windows chmod is a no-op: the file is protected by the
    ACL of the user profile (Path.home()), so never point token_path outside it."""
    path = Path(path)
    if path.parent.is_symlink():  # a swapped-in directory link could redirect the token elsewhere
        raise ConnectorError("dossier de jeton : lien symbolique refusé")
    if path.parent.exists():
        st = path.parent.stat()
        # only our own dir: never chmod a shared one such as /tmp
        if hasattr(os, "getuid") and st.st_uid == os.getuid() and st.st_mode & 0o077:
            path.parent.chmod(0o700)
    else:
        path.parent.mkdir(parents=True, mode=0o700)
        path.parent.chmod(0o700)  # mkdir's mode is masked by umask
    try:
        # O_NOFOLLOW: a symlink planted at the token path must not redirect our write
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    except OSError:
        raise ConnectorError("écriture du fichier de jeton refusée (lien symbolique ou droits)") from None
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        if hasattr(os, "fchmod"):
            os.fchmod(f.fileno(), 0o600)  # os.open's mode is ignored on an existing file
        f.write(text)
