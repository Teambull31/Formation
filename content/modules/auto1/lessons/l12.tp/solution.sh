#!/usr/bin/env bash
# Solution de référence du TP 12 : quotidien.py (digest quotidien idempotent, état, journal, secours Ollama).
cat > quotidien.py <<'PY'
# quotidien.py : digest quotidien prêt à être planifié.
#   python3 quotidien.py --path FICHIER [--source json|mbox] [--date AAAA-MM-JJ]
#                        [--state etat.json] [--out-dir .] [--log quotidien.log]
# Produit digest-AAAA-MM-JJ.md. Idempotent : un mail (par son id) n'est traité qu'une fois, même relancé.
# L'état (id -> résumé) est dans un fichier ; si Ollama est en panne, résumés de secours (sans IA).
import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import digest  # point de départ fourni ; ajoute aussi kit/ au chemin d'import
from llm import LlmUnavailable, generate

ORDRE = {"haute": 0, "normale": 1, "basse": 2}


def charger_etat(path):
    """id -> {date, urgence, resume, suspect}. Fichier absent ou abîmé : on repart de zéro (jamais de plantage)."""
    try:
        traites = json.loads(Path(path).read_text(encoding="utf-8"))["traites"]
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    return traites if isinstance(traites, dict) else {}


def ecrire(path, texte):
    """Écriture atomique : fichier temporaire puis remplacement, jamais de fichier à moitié écrit."""
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(texte)
    os.replace(tmp, path)


def modele_disponible():
    try:
        generate("ping", timeout=3)
        return True
    except LlmUnavailable:
        return False


def une_ligne(texte):
    return " ".join(str(texte).split())


def rendu(jour, traites):
    lignes = [(ORDRE.get(e["urgence"], 1), i, e) for i, e in traites.items() if e["date"] == jour]
    lignes.sort(key=lambda t: t[0])  # tri stable : à urgence égale, ordre de traitement
    corps = [f"- [{e['urgence']}] {une_ligne(i)} : {une_ligne(e['resume'])}" + (" [SUSPECT]" if e["suspect"] else "")
             for _, i, e in lignes] or ["Aucun nouveau mail."]
    return f"# Digest du {jour}\n\n" + "\n".join(corps) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True)
    ap.add_argument("--source", choices=["json", "mbox"], default="json")
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--state", default="etat.json")
    ap.add_argument("--out-dir", default=".")
    ap.add_argument("--log", default="quotidien.log")
    args = ap.parse_args()

    traites = charger_etat(args.state)
    mails = digest.load_mails(args.source, args.path)
    modele = None  # on ne sonde Ollama qu'une fois, et seulement si un mail doit être résumé
    secours = False
    nouveaux = 0
    for m in mails:
        if m.id in traites:
            continue
        if digest.is_suspect(m):
            entry = digest.digest_entry(m)  # jamais envoyé au modèle
        else:
            if modele is None:
                modele = modele_disponible()
            if modele:
                entry = digest.digest_entry(m)
            else:
                secours = True
                entry = {"id": m.id, **digest.fallback_summary(m), "suspect": False}
        traites[m.id] = {"date": args.date, "urgence": entry["urgence"], "resume": entry["resume"], "suspect": entry["suspect"]}
        nouveaux += 1

    os.makedirs(args.out_dir, exist_ok=True)
    ecrire(os.path.join(args.out_dir, f"digest-{args.date}.md"), rendu(args.date, traites))  # d'abord le digest...
    ecrire(args.state, json.dumps({"traites": traites}, ensure_ascii=False, indent=1))  # ...puis l'état
    with open(args.log, "a", encoding="utf-8") as f:  # journal : des compteurs, jamais de contenu
        f.write(f"{datetime.now().isoformat(timespec='seconds')} date={args.date} nouveaux={nouveaux} "
                f"ignores={len(mails) - nouveaux} modele={'secours' if secours else 'ok'}\n")


if __name__ == "__main__":
    main()
PY
