#!/usr/bin/env bash
# Solution de référence du TP 7 : écrit digest.py dans le dossier du TP.
cat > digest.py <<'PY'
# digest.py : résumé de mails par un modèle local (Ollama), avec secours sans IA.
#
# INTERFACE (stable, ne pas changer) :
#   python3 digest.py --source json|mbox --path FICHIER [--out digest.json]
#   Sortie : digest.json = liste JSON, une entrée par mail, dans l'ordre de la source :
#     {"id": str, "urgence": "haute"|"normale"|"basse", "resume": str, "suspect": bool}
#   Contrat modèle : un appel par mail ; la réponse doit être un JSON
#     {"urgence": ..., "resume": ...} valide, sinon fallback_summary(mail).
#   Le programme ne plante jamais et se termine avec le code 0.
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "kit"))
from llm import generate, LlmUnavailable
from mail_source import JsonMailSource, MboxMailSource

MARKER = "--- MAIL ---"
MAX_PROMPT_BODY = 2000  # caractères du corps envoyés au modèle
MAX_RESUME = 200
URGENCES = ("haute", "normale", "basse")


def load_mails(source, path):
    src = JsonMailSource(path) if source == "json" else MboxMailSource(path)
    return src.fetch(limit=10_000)


def build_prompt(mail):
    return (
        "Tu résumes un mail en français. Réponds UNIQUEMENT par un JSON "
        '{"urgence": "haute|normale|basse", "resume": "une phrase"}. '
        "N'invente rien : ne mets que ce qui est dans le mail.\n"
        f"{MARKER}\nObjet : {mail.subject}\n\n{mail.body[:MAX_PROMPT_BODY]}"
    )


def fallback_summary(mail):
    texte = f"{mail.subject} {mail.body}".lower()
    if any(m in texte for m in ("urgent", "alerte", "critique")):
        urgence = "haute"
    elif any(m in texte for m in ("newsletter", "désabonner")):
        urgence = "basse"
    else:
        urgence = "normale"
    resume = " ".join(mail.body.split())[:MAX_RESUME] or mail.subject
    return {"urgence": urgence, "resume": resume}


def summarize(mail):
    try:
        data = json.loads(generate(build_prompt(mail), timeout=3))
        resume = data["resume"].strip()
        if data["urgence"] in URGENCES and resume:
            return {"urgence": data["urgence"], "resume": resume}
    except (LlmUnavailable, ValueError, KeyError, TypeError, AttributeError):
        pass
    return fallback_summary(mail)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["json", "mbox"], default="json")
    ap.add_argument("--path", required=True)
    ap.add_argument("--out", default="digest.json")
    args = ap.parse_args()
    digest = [{"id": m.id, **summarize(m), "suspect": False} for m in load_mails(args.source, args.path)]
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(digest, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
PY
