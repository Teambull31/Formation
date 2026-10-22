#!/usr/bin/env bash
# Solution de référence du TP 5 : écrit lister.py dans le dossier du TP.
cat > lister.py <<'PY'
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "kit"))
from mail_source import JsonMailSource, MboxMailSource

parser = argparse.ArgumentParser()
parser.add_argument("--source", choices=["json", "mbox"], required=True)
parser.add_argument("--path", required=True)
args = parser.parse_args()

if not os.path.isfile(args.path):
    print(f"Erreur : fichier introuvable : {args.path}", file=sys.stderr)
    sys.exit(2)

source = JsonMailSource(args.path) if args.source == "json" else MboxMailSource(args.path)
mails = source.fetch(limit=5)
if not mails:
    print("(aucun mail)")
for m in mails:
    print(f"{m.sender} | {m.subject}")
PY
