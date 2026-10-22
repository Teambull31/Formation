#!/usr/bin/env bash
# Solution de référence du TP 10 : outlook_digest.py (OutlookGraphSource vers mock_graph + digest).
cat > outlook_digest.py <<'PY'
# outlook_digest.py : digest des mails Outlook (Microsoft Graph, lecture seule) via le simulateur.
#   GRAPH_URL=http://127.0.0.1:PORT/v1.0 python3 outlook_digest.py [--out digest.json]
# Code de sortie 1 et message lisible sur stderr si la connexion échoue ; jamais de jeton ni de corps de mail affichés.
import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import digest  # point de départ fourni ; ajoute aussi kit/ au chemin d'import
from mail_source import ConnectorError
from outlook_graph import OutlookGraphSource


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="digest.json")
    args = ap.parse_args()
    url = os.environ.get("GRAPH_URL")
    if not url:
        print("Erreur : la variable GRAPH_URL n'est pas définie (adresse du simulateur Graph).", file=sys.stderr)
        return 1
    source = OutlookGraphSource(
        "client-id-fictif", tenant="consumers",
        token_path=HERE / "graph_token.json",  # à côté du script, jamais dans un dépôt partagé
        base_url=url,
        auth=lambda: "jeton-fictif",  # le vrai device code flow est l'essai manuel facultatif
    )
    try:
        mails = source.fetch(limit=10_000)
    except (ConnectorError, RuntimeError) as e:
        print(f"Erreur Outlook : {e}", file=sys.stderr)  # le message du kit ne contient ni jeton ni mail
        return 1
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump([digest.digest_entry(m) for m in mails], f, ensure_ascii=False, indent=2)
    print(f"{len(mails)} mails traités.")  # un nombre, jamais de contenu
    return 0


if __name__ == "__main__":
    sys.exit(main())
PY
