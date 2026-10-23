"""Mot de passe optionnel (HTTP Basic) pour exposer l'appli hors de la machine locale."""
import asyncio
import base64
import binascii
import hmac
import os
import time
from dataclasses import dataclass

MIN_PASSWORD = 12
MAX_FAILS = 5  # mauvais mots de passe dans WINDOW secondes, puis ralentissement
WINDOW = 300
DELAY = 1  # secondes par mauvais essai une fois ralenti
MAX_WAITING = 20  # au-delà, réponse 429 immédiate (borne la mémoire et les connexions tenues)


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

    def __init__(self, app, password: str, clock=time.monotonic, sleep=asyncio.sleep):
        self.app, self.password, self.clock, self.sleep = app, password.encode(), clock, sleep
        self.fails: list[float] = []  # horodatages des mauvais mots de passe récents, tous clients confondus
        self.waiting = 0  # mauvais essais en attente de leur tour
        self.slow = asyncio.Lock()

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

    async def _throttle(self) -> bool:
        """Après MAX_FAILS échecs récents, les mauvais essais passent un par un, 1 s chacun. False = file pleine."""
        now = self.clock()
        self.fails = [t for t in self.fails if now - t < WINDOW]
        self.fails.append(now)
        if len(self.fails) <= MAX_FAILS:
            return True
        if self.waiting >= MAX_WAITING:
            return False
        self.waiting += 1
        try:
            async with self.slow:
                await self.sleep(DELAY)
        finally:
            self.waiting -= 1
        return True

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        # Le bon mot de passe passe toujours : un blocage par adresse verrouillerait le vrai utilisateur derrière un proxy
        # (Caddy, tailscale serve) où tous les clients partagent la même adresse. On ralentit seulement les mauvais essais.
        ok = self._creds(scope)
        if ok:
            return await self.app(scope, receive, send)
        full = ok is False and not await self._throttle()
        if scope["type"] == "websocket":
            await receive()  # websocket.connect
            return await send({"type": "websocket.close", "code": 1008})
        status, headers = (429, [(b"retry-after", str(DELAY).encode())]) if full else \
            (401, [(b"www-authenticate", b'Basic realm="Formation", charset="UTF-8"')])
        body = ("Trop d'essais, réessayez plus tard" if full else "Authentification requise").encode()
        await send({"type": "http.response.start", "status": status, "headers": headers + [
            (b"content-type", b"text/plain; charset=utf-8"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})
