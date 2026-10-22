"""Garde des actions sensibles (terminal, vérification de TP, boss, import de module).

Ces actions exécutent des commandes sur la machine qui héberge le backend. Elles ne sont donc
autorisées que dans deux cas :

- la requête arrive directement depuis la machine elle-même (loopback), sans passer par un relais ;
- la requête a été relayée par le serveur Node *après* authentification : il ajoute alors l'en-tête
  `x-questforge-internal` contenant le secret partagé `QUESTFORGE_INTERNAL_SECRET`.

Sans cet en-tête, une requête relayée (elle porte `x-forwarded-for`) est refusée : le relais tourne
sur la même machine, donc l'adresse source seule ne prouve rien.
"""
from __future__ import annotations

import hmac
import os
from collections.abc import Mapping

LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}
INTERNAL_HEADER = "x-questforge-internal"
# Variables que le terminal et les scripts de TP ne doivent jamais voir.
SECRET_ENV_VARS = ("QUESTFORGE_PASSWORD", "QUESTFORGE_INTERNAL_SECRET")


def is_local(host: str | None) -> bool:
    return bool(host) and host in LOCAL_HOSTS


def is_trusted(client_host: str | None, headers: Mapping[str, str]) -> bool:
    secret = os.environ.get("QUESTFORGE_INTERNAL_SECRET")
    given = headers.get(INTERNAL_HEADER, "")
    if secret and given and hmac.compare_digest(given.encode(), secret.encode()):
        return True
    # Accès direct depuis la machine : aucune trace de relais.
    return is_local(client_host) and "x-forwarded-for" not in headers and INTERNAL_HEADER not in headers


def clean_env(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """Environnement transmis aux processus lancés pour l'apprenant, sans les secrets du serveur."""
    env = dict(os.environ if base is None else base)
    for name in SECRET_ENV_VARS:
        env.pop(name, None)
    return env
