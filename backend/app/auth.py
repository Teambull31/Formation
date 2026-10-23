"""Mot de passe optionnel (HTTP Basic) pour exposer l'appli hors de la machine locale."""
import base64
import binascii
import hmac
import os
from dataclasses import dataclass

MIN_PASSWORD = 12


@dataclass(frozen=True)
class Security:
    password: str | None = None
    remote_exec: bool = False
    allowed_hosts: frozenset[str] = frozenset()


def make_security(password: str | None, remote_exec: bool = False, allowed_hosts=()) -> Security:
    """Valide la configuration; les messages ne contiennent jamais le mot de passe."""
    hosts = frozenset(h.strip().lower() for h in allowed_hosts if h.strip())
    if password is not None and len(password) < MIN_PASSWORD:
        raise RuntimeError(f"FORMATION_PASSWORD trop court : {MIN_PASSWORD} caractères minimum. Démarrage refusé.")
    if remote_exec and password is None:
        raise RuntimeError("FORMATION_REMOTE_EXEC=1 exige FORMATION_PASSWORD. Démarrage refusé.")
    if remote_exec and not hosts:
        raise RuntimeError("FORMATION_REMOTE_EXEC=1 exige FORMATION_ALLOWED_HOSTS (noms d'hôte séparés par des virgules). "
                           "Démarrage refusé.")
    return Security(password, remote_exec, hosts if remote_exec else frozenset())


def security_from_env() -> Security:
    return make_security(os.environ.get("FORMATION_PASSWORD"), os.environ.get("FORMATION_REMOTE_EXEC") == "1",
                         os.environ.get("FORMATION_ALLOWED_HOSTS", "").split(","))


class BasicAuth:
    """Middleware ASGI pur (HTTP et websocket) : n'importe quel nom d'utilisateur, mot de passe comparé en temps constant."""

    def __init__(self, app, password: str):
        self.app, self.password = app, password.encode()

    def _ok(self, scope) -> bool:
        for k, v in scope["headers"]:
            if k == b"authorization":
                scheme, _, token = v.partition(b" ")
                if scheme.lower() != b"basic":
                    return False
                try:
                    _, sep, pw = base64.b64decode(token.strip(), validate=True).partition(b":")
                except (binascii.Error, ValueError):
                    return False
                return bool(sep) and hmac.compare_digest(pw, self.password)
        return False

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket") or self._ok(scope):
            return await self.app(scope, receive, send)
        if scope["type"] == "websocket":
            await receive()  # websocket.connect
            return await send({"type": "websocket.close", "code": 1008})
        body = "Authentification requise".encode()
        await send({"type": "http.response.start", "status": 401, "headers": [
            (b"www-authenticate", b'Basic realm="Formation", charset="UTF-8"'),
            (b"content-type", b"text/plain; charset=utf-8"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})
