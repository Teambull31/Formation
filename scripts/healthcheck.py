"""Healthcheck Docker : 200 ou 401 (mot de passe requis) = serveur vivant."""
import sys
import urllib.error
import urllib.request

try:
    urllib.request.urlopen("http://127.0.0.1:8000/manifest.webmanifest", timeout=4)
except urllib.error.HTTPError as e:
    sys.exit(0 if e.code == 401 else 1)
except Exception:
    sys.exit(1)
