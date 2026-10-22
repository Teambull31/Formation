#!/usr/bin/env bash
# Solution de référence du TP 4 : écrit rapport.py dans le dossier du TP.
cat > rapport.py <<'PY'
import json
import sys


def sujet(m):
    s = m.get("subject")
    if not isinstance(s, str):
        return "(sans objet)"
    lignes = [l.strip() for l in s.splitlines() if l.strip()]
    if not lignes:
        return "(sans objet)"
    return lignes[0][:40] + "…" if len(lignes[0]) > 40 else lignes[0]


def nom(m):
    s = m.get("sender")
    return (s.split("@")[0].lower() or "inconnu") if isinstance(s, str) and s else "inconnu"


with open(sys.argv[1], encoding="utf-8") as f:
    mails = json.load(f)

groupes = {}
for m in mails:
    groupes.setdefault(nom(m), []).append(m)

n = len(mails)
lignes = ["# Rapport des mails", "", f"Total : {n} mail{'s' if n > 1 else ''}", ""]
for g in sorted(groupes):
    items = sorted(groupes[g], key=lambda m: m["received"], reverse=True)
    lignes.append(f"## {g} ({len(items)})")
    lignes += [f"- {m['received'][:10]} {m['received'][11:16]} — {sujet(m)}" for m in items]
    lignes.append("")

with open("rapport.md", "w", encoding="utf-8") as f:
    f.write("\n".join(lignes).rstrip("\n") + "\n")
PY
