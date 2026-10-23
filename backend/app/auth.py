"""Mot de passe optionnel (HTTP Basic) pour exposer l'appli hors de la machine locale."""
import asyncio
import base64
import binascii
import hmac
import os
import time
from collections import deque
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
        self.fails: deque[float] = deque(maxlen=MAX_FAILS)  # horodatages des derniers mauvais mots de passe, tous clients
        self.waiting = 0  # requêtes avec identifiants en attente de leur tour
        self.slow = asyncio.Lock()

    @staticmethod
    def _header(scope) -> bytes | None:
        return next((v for k, v in scope["headers"] if k == b"authorization"), None)

    def _check(self, header: bytes) -> bool:
        scheme, _, token = header.partition(b" ")
        if scheme.lower() != b"basic":
            return False
        try:
            _, sep, pw = base64.b64decode(token.strip(), validate=True).partition(b":")
        except (binascii.Error, ValueError):
            return False
        return bool(sep) and hmac.compare_digest(pw, self.password)

    def _under_attack(self) -> bool:
        return len(self.fails) == MAX_FAILS and self.clock() - self.fails[0] < WINDOW

    async def _wait_turn(self) -> bool:
        """En rafale d'échecs, chaque essai attend son tour (1 s) AVANT d'être vérifié. False = file pleine (non vérifié)."""
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
        header = self._header(scope)
        # Pas de blocage par adresse : derrière un proxy (Caddy, tailscale serve) tous les clients la partagent et un
        # attaquant verrouillerait le vrai utilisateur. On plafonne plutôt le débit global des essais, vérification comprise.
        # Un 429 ne dit donc rien du mot de passe : l'essai n'a pas été vérifié.
        full = header is not None and self._under_attack() and not await self._wait_turn()
        if not full and header is not None:
            if self._check(header):
                return await self.app(scope, receive, send)
            self.fails.append(self.clock())
        if scope["type"] == "websocket":
            await receive()  # websocket.connect
            return await send({"type": "websocket.close", "code": 1008})
        status, headers = (429, [(b"retry-after", str(DELAY).encode())]) if full else \
            (401, [(b"www-authenticate", b'Basic realm="Formation", charset="UTF-8"')])
        body = ("Trop d'essais, réessayez plus tard" if full else "Authentification requise").encode()
        await send({"type": "http.response.start", "status": status, "headers": headers + [
            (b"content-type", b"text/plain; charset=utf-8"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})
