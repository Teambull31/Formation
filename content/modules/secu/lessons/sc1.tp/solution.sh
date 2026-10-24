#!/usr/bin/env bash
# Solution de référence du TP sc1.
set -euo pipefail
cat > app.py <<'EOF'
import sqlite3
import subprocess


def find_user(conn, name):
    """Renvoie la liste des (id, name) des utilisateurs qui portent ce nom."""
    return conn.execute("SELECT id, name FROM users WHERE name = ?", (name,)).fetchall()


def count_lines(path):
    """Renvoie le nombre de lignes (entier) du fichier path."""
    out = subprocess.run(["wc", "-l", "--", path], capture_output=True, text=True, check=True).stdout
    return int(out.split()[0])
EOF
