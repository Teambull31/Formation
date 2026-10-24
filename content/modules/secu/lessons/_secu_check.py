#!/usr/bin/env python3
"""Vérifications des TP du module Sécurité applicative (OWASP).

Le code de l'apprenant est importé puis attaqué avec des entrées hostiles, dans un dossier temporaire.
Lancer avec `python3 -I -B`. Usage : _secu_check.py <sc1|sc2|sc3> (le répertoire courant est le dossier du TP).
"""
from __future__ import annotations

import importlib.util
import os
import re
import sqlite3
import sys
import tempfile

MAX_BYTES = 200_000


class CheckError(Exception):
    """Erreur affichée à l'apprenant."""


def need(condition, message: str) -> None:
    if not condition:
        raise CheckError(message)


def source(name: str) -> str:
    need(os.path.isfile(name) and not os.path.islink(name), f"{name} est introuvable")
    with open(name, encoding="utf-8") as f:
        text = f.read(MAX_BYTES + 1)
    need(len(text) <= MAX_BYTES, f"{name} est trop gros")
    return text


def code_only(text: str) -> str:
    """Le code sans commentaires de ligne (les motifs interdits dans un commentaire sont sans effet)."""
    return "\n".join(re.sub(r"(^|\s)#.*$", "", l) for l in text.splitlines())


def load(name: str, *functions: str):
    path = os.path.abspath(name)
    source(name)
    spec = importlib.util.spec_from_file_location("learner_" + os.path.basename(name).removesuffix(".py"), path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except SyntaxError as e:
        raise CheckError(f"{name} : erreur de syntaxe ligne {e.lineno} ({e.msg})") from None
    except Exception as e:  # le code de l'apprenant peut lever n'importe quoi
        raise CheckError(f"{name} ne se charge pas : {type(e).__name__}: {e}") from None
    for fn in functions:
        need(callable(getattr(mod, fn, None)), f"{name} doit définir la fonction {fn}()")
    return mod


def call(fn, *args, what: str):
    try:
        return fn(*args)
    except Exception as e:
        raise CheckError(f"{what} a levé {type(e).__name__} : {str(e)[:120]}") from None


# ---- sc1 : injections SQL et de commandes ----

def check_sc1() -> None:
    text = code_only(source("app.py"))
    need("shell=True" not in text.replace(" ", ""), "shell=True fait interpréter le texte par un shell : passez une liste d'arguments à subprocess.run")
    mod = load("app.py", "find_user", "count_lines")
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
    conn.executemany("INSERT INTO users (name) VALUES (?)", [("alice",), ("bob",), ("o'brien",)])
    conn.commit()
    rows = call(mod.find_user, conn, "alice", what="find_user(conn, 'alice')")
    need([tuple(r) for r in rows] == [(1, "alice")], f"find_user(conn, 'alice') doit renvoyer [(1, 'alice')], pas {rows!r}")
    rows = call(mod.find_user, conn, "o'brien", what="find_user(conn, \"o'brien\")")
    need([tuple(r) for r in rows] == [(3, "o'brien")], "un nom avec une apostrophe est un nom valide : find_user doit le retrouver (liaison de paramètre, pas échappement maison)")
    for payload in ("' OR '1'='1", "x' OR 1=1 --", "alice' --", "x'; DROP TABLE users; --"):
        try:
            rows = mod.find_user(conn, payload)
        except Exception:
            rows = []
        need(not rows, f"find_user(conn, {payload!r}) renvoie des lignes : la requête est injectable (utilisez ? et un paramètre)")
    try:
        conn.execute("SELECT COUNT(*) FROM users").fetchone()
    except sqlite3.Error:
        raise CheckError("la table users a disparu : l'injection SQL a réussi") from None

    with tempfile.TemporaryDirectory() as tmp:
        here = os.getcwd()
        os.chdir(tmp)
        try:
            with open("data.txt", "w", encoding="utf-8") as f:
                f.write("a\nb\nc\n")
            with open("mon fichier.txt", "w", encoding="utf-8") as f:
                f.write("1\n2\n")
            n = call(mod.count_lines, "data.txt", what="count_lines('data.txt')")
            need(n == 3 and isinstance(n, int), f"count_lines('data.txt') doit renvoyer l'entier 3, pas {n!r}")
            n = call(mod.count_lines, "mon fichier.txt", what="count_lines('mon fichier.txt')")
            need(n == 2, "un nom de fichier avec une espace doit fonctionner (un seul argument, pas du texte découpé par un shell)")
            for payload in ("data.txt; touch PWNED", "data.txt && touch PWNED", "$(touch PWNED)", "`touch PWNED`", "data.txt\ntouch PWNED"):
                try:
                    mod.count_lines(payload)
                except Exception:
                    pass
                need(not os.path.exists("PWNED"), f"count_lines({payload!r}) a exécuté une commande : l'injection a réussi (liste d'arguments, sans shell)")
        finally:
            os.chdir(here)


# ---- sc2 : XSS et traversée de chemin ----

def check_sc2() -> None:
    mod = load("web.py", "render_comment", "read_upload")
    out = call(mod.render_comment, "<script>alert(1)</script>", "<img src=x onerror=alert(1)>", what="render_comment(...)")
    need(isinstance(out, str), "render_comment doit renvoyer une chaîne")
    low = out.lower()
    need("<script" not in low and "<img" not in low, "render_comment laisse passer des balises : échappez le texte avant de l'insérer dans la page (html.escape)")
    need("&lt;script&gt;" in out, "l'auteur doit être échappé aussi, pas seulement le texte")
    out = call(mod.render_comment, "Alice", "salut & merci \"à bientôt\"", what="render_comment('Alice', ...)")
    need("&amp;" in out and "Alice" in out, "le & doit devenir &amp; ; le texte normal doit rester lisible")
    out = call(mod.render_comment, "x", '" onmouseover="alert(1)', what="render_comment(guillemets)")
    need('" onmouseover=' not in out, "les guillemets doivent être échappés (html.escape) : sinon ils sortent d'un attribut HTML")

    with tempfile.TemporaryDirectory() as tmp:
        base = os.path.join(tmp, "base")
        sibling = os.path.join(tmp, "base2")
        os.makedirs(os.path.join(base, "sub"))
        os.makedirs(sibling)
        with open(os.path.join(base, "ok.txt"), "w", encoding="utf-8") as f:
            f.write("hello")
        with open(os.path.join(base, "sub", "a.txt"), "w", encoding="utf-8") as f:
            f.write("deep")
        with open(os.path.join(tmp, "secret.txt"), "w", encoding="utf-8") as f:
            f.write("TOP-SECRET")
        with open(os.path.join(sibling, "f.txt"), "w", encoding="utf-8") as f:
            f.write("SIBLING")
        os.symlink(os.path.join(tmp, "secret.txt"), os.path.join(base, "link.txt"))
        need(call(mod.read_upload, base, "ok.txt", what="read_upload(base, 'ok.txt')") == "hello", "read_upload(base, 'ok.txt') doit renvoyer le contenu du fichier")
        need(call(mod.read_upload, base, "sub/a.txt", what="read_upload(base, 'sub/a.txt')") == "deep", "un fichier dans un sous-dossier autorisé doit rester lisible")
        for attempt, label in (("../secret.txt", "../secret.txt"), (os.path.join(tmp, "secret.txt"), "un chemin absolu"),
                               ("../base2/f.txt", "../base2/f.txt (dossier voisin au nom préfixé)"),
                               ("sub/../../secret.txt", "sub/../../secret.txt"), ("link.txt", "un lien symbolique qui sort du dossier")):
            try:
                got = mod.read_upload(base, attempt)
            except Exception:
                continue
            need(got not in ("TOP-SECRET", "SIBLING"), f"read_upload laisse lire {label} : vérifiez que le chemin résolu reste dans le dossier de base")


# ---- sc3 : mots de passe et secrets ----

def check_sc3() -> None:
    text = code_only(source("auth.py"))
    need("dev-secret-123" not in text, "la clé secrète est écrite en dur dans le code : lisez-la depuis une variable d'environnement")
    need(re.search(r"scrypt|pbkdf2_hmac|argon2|bcrypt", text), "stockez un hachage lent et salé : hashlib.scrypt ou hashlib.pbkdf2_hmac")
    need(re.search(r"compare_digest", text), "comparez les hachages avec hmac.compare_digest, qui ne révèle rien par le temps de réponse")
    need(not re.search(r"hashlib\.(md5|sha1)\b", text), "md5 et sha1 sont cassés et trop rapides pour des mots de passe")
    mod = load("auth.py", "register", "check", "get_secret_key")
    users: dict = {}
    pw = "correct horse battery"
    call(mod.register, users, "alice", pw, what="register(users, 'alice', ...)")
    call(mod.register, users, "bob", pw, what="register(users, 'bob', ...)")
    stored = repr(users)
    need(pw not in stored and "correct" not in stored, "le mot de passe apparaît en clair dans les données stockées")
    need(users.get("alice") != users.get("bob"), "deux comptes avec le même mot de passe doivent avoir des valeurs stockées différentes : ajoutez un sel aléatoire par utilisateur")
    need(call(mod.check, users, "alice", pw, what="check(users, 'alice', bon mot de passe)") is True, "check doit renvoyer True pour le bon mot de passe")
    need(call(mod.check, users, "alice", pw + "x", what="check(mauvais mot de passe)") is False, "check doit renvoyer False pour un mauvais mot de passe")
    need(call(mod.check, users, "inconnu", pw, what="check(utilisateur inconnu)") is False, "un utilisateur inconnu doit renvoyer False, pas lever d'exception")
    try:
        mod.register(users, "carol", "court")
        too_short = False
    except Exception:
        too_short = True
    need(too_short, "register doit refuser un mot de passe de moins de 8 caractères (ValueError)")
    os.environ.pop("APP_SECRET_KEY", None)
    try:
        mod.get_secret_key()
        missing_ok = True
    except Exception:
        missing_ok = False
    need(not missing_ok, "sans variable APP_SECRET_KEY, get_secret_key doit lever une exception plutôt que de retomber sur une valeur par défaut")
    os.environ["APP_SECRET_KEY"] = "une-valeur-de-test-longue"
    need(call(mod.get_secret_key, what="get_secret_key()") == "une-valeur-de-test-longue", "get_secret_key doit renvoyer la valeur de APP_SECRET_KEY")


CHECKS = {
    "sc1": (check_sc1, "les injections SQL et de commandes échouent."),
    "sc2": (check_sc2, "le HTML est échappé et les chemins restent dans leur dossier."),
    "sc3": (check_sc3, "mots de passe hachés et sel, secret hors du code."),
}


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in CHECKS:
        print(f"Usage: {argv[0]} <{'|'.join(CHECKS)}>", file=sys.stderr)
        return 2
    try:
        check, success = CHECKS[argv[1]]
        check()
    except CheckError as e:
        print(f"ECHEC : {e}")
        return 1
    except (OSError, ValueError) as e:
        print(f"ECHEC : fichier illisible ({type(e).__name__})")
        return 1
    print(f"OK : {success}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
