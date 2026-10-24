#!/usr/bin/env bash
# Solution de référence du TP sc3.
set -euo pipefail
cat > auth.py <<'EOF'
import hashlib
import hmac
import os


def _hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)


def register(users, name, password):
    """Enregistre un utilisateur dans le dictionnaire users."""
    if len(password) < 8:
        raise ValueError("mot de passe trop court")
    salt = os.urandom(16)
    users[name] = (salt, _hash(password, salt))


def check(users, name, password):
    """Renvoie True si le mot de passe est correct pour cet utilisateur, sinon False."""
    entry = users.get(name)
    if entry is None:
        return False
    salt, expected = entry
    return hmac.compare_digest(_hash(password, salt), expected)


def get_secret_key():
    """Renvoie la clé secrète de l'application."""
    return os.environ["APP_SECRET_KEY"]
EOF
