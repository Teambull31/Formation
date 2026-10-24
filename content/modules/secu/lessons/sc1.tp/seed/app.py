import sqlite3
import subprocess


def find_user(conn, name):
    """Renvoie la liste des (id, name) des utilisateurs qui portent ce nom."""
    query = "SELECT id, name FROM users WHERE name = '" + name + "'"
    return conn.execute(query).fetchall()


def count_lines(path):
    """Renvoie le nombre de lignes (entier) du fichier path."""
    out = subprocess.run("wc -l " + path, shell=True, capture_output=True, text=True).stdout
    return int(out.split()[0])
