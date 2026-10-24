import os

SECRET_KEY = "dev-secret-123"


def register(users, name, password):
    """Enregistre un utilisateur dans le dictionnaire users."""
    users[name] = password


def check(users, name, password):
    """Renvoie True si le mot de passe est correct pour cet utilisateur, sinon False."""
    return users.get(name) == password


def get_secret_key():
    """Renvoie la clé secrète de l'application."""
    return SECRET_KEY
