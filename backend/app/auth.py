"""Mot de passe optionnel (HTTP Basic) pour exposer l'appli hors de la machine locale."""
import base64
import binascii
import hmac
import os
import time
from dataclasses import dataclass

MIN_PASSWORD = 12
MAX_FAILS = 5  # mauvais mots de passe par client dans WINDOW secondes, puis blocage
WINDOW = 300


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

    def __init__(self, app, password: str, clock=time.monotonic):
        self.app, self.password, self.clock = app, password.encode(), clock
        self.fails: dict[str, list[float]] = {}

    def _creds(self, scope) -> bool | None:
        """None = pas d'identifiants (le navigateur les demande), False = mauvais, True = bons."""
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
        return None

    def _recent(self, who: str) -> list[float]:
        now = self.clock()
        stamps = [t for t in self.fails.get(who, []) if now - t < WINDOW]
        if stamps:
            self.fails[who] = stamps
        else:
            self.fails.pop(who, None)
        return stamps

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        # shortcut: derrière un proxy (Caddy, tailscale serve) tous les clients partagent une IP, donc un blocage commun;
        # en-têtes X-Forwarded-For non crus (falsifiables). À revoir si un proxy de confiance est déclaré.
        who = (scope.get("client") or ("?",))[0]
        blocked = len(self._recent(who)) >= MAX_FAILS
        ok = None if blocked else self._creds(scope)
        if ok:
            return await self.app(scope, receive, send)
        if ok is False:
            self.fails.setdefault(who, []).append(self.clock())
        if len(self.fails) > 1000:  # borne la mémoire
            for k in list(self.fails):
                self._recent(k)
        if scope["type"] == "websocket":
            await receive()  # websocket.connect
            return await send({"type": "websocket.close", "code": 1008})
        status, headers = (429, [(b"retry-after", str(WINDOW).encode())]) if blocked else \
            (401, [(b"www-authenticate", b'Basic realm="Formation", charset="UTF-8"')])
        body = ("Trop d'essais, réessayez plus tard" if blocked else "Authentification requise").encode()
        await send({"type": "http.response.start", "status": status, "headers": headers + [
            (b"content-type", b"text/plain; charset=utf-8"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})
