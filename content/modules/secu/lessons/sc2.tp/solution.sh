#!/usr/bin/env bash
# Solution de référence du TP sc2.
set -euo pipefail
cat > web.py <<'EOF'
import html
import os


def render_comment(author, text):
    """Renvoie le HTML d'un commentaire."""
    return "<p><b>" + html.escape(author) + "</b>: " + html.escape(text) + "</p>"


def read_upload(base_dir, filename):
    """Renvoie le contenu du fichier filename, situé dans base_dir."""
    base = os.path.realpath(base_dir)
    path = os.path.realpath(os.path.join(base, filename))
    if os.path.commonpath([base, path]) != base:
        raise ValueError("chemin en dehors du dossier autorisé")
    with open(path, encoding="utf-8") as f:
        return f.read()
EOF
