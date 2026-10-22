#!/usr/bin/env bash
# Solution de référence du TP 3 : écrit client.py dans le dossier du TP.
cat > client.py <<'PY'
import json
import os
import sys
import time
import urllib.error
import urllib.request

TIMEOUT = 2


def fail(message):
    print("Erreur : " + message, file=sys.stderr)
    sys.exit(1)


def call(path, body=None, attempts=1):
    base = os.environ.get("API_URL")
    if not base:
        fail("la variable API_URL n'est pas définie.")
    req = urllib.request.Request(base + path)
    if body is not None:
        req = urllib.request.Request(
            base + path, data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json"})
    for essai in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code < 500:
                fail(f"{path} a répondu {e.code} : requête refusée, inutile de réessayer.")
            erreur = f"{path} a répondu {e.code}"
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            erreur = f"{path} est injoignable ({e})"
        except ValueError:
            fail(f"{path} a renvoyé une réponse illisible.")
        if essai < attempts - 1:
            time.sleep(0.2 * 2 ** essai)
    fail(f"{erreur} après {attempts} tentative(s).")


for t in call("/tasks", attempts=3):
    print(f"{t['id']}: {t['title']}")
print("flaky: " + json.dumps(call("/flaky", attempts=3)))
# POST : une seule tentative, il n'est pas idempotent
created = call("/tasks", body={"title": "Relancer le client"})
print(f"créée: {created['id']}")
PY
