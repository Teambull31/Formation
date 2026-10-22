#!/usr/bin/env bash
# Contrôle du TP 4 : exécute rapport.py sur plusieurs jeux de mails aléatoires (dossier jetable)
# et compare rapport.md à un rapport calculé ici, de façon indépendante. cwd = dossier du TP.
[ -f rapport.py ] || { echo "ECHEC : le fichier rapport.py est introuvable dans le dossier du TP."; exit 1; }
TP="$PWD"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
TP="$TP" TMP="$TMP" timeout 40 python3 -B - <<'PY'
import hashlib, json, os, random, subprocess, sys
from datetime import datetime, timedelta

TP, TMP = os.environ["TP"], os.environ["TMP"]

def fail(msg):
    print("ECHEC : " + msg)
    sys.exit(1)

def expected(rows):
    """Rapport attendu, calculé à part de toute solution d'apprenant."""
    groups = {}
    for r in rows:
        s = r.get("sender")
        name = s.split("@")[0].lower() if isinstance(s, str) and s else "inconnu"
        groups.setdefault(name or "inconnu", []).append(r)
    def subject(r):
        s = r.get("subject")
        if not isinstance(s, str):
            return "(sans objet)"
        first = next((l.strip() for l in s.splitlines() if l.strip()), "")
        if not first:
            return "(sans objet)"
        return first[:40] + "…" if len(first) > 40 else first
    n = len(rows)
    out = ["# Rapport des mails", "", f"Total : {n} mail{'s' if n > 1 else ''}", ""]
    for name in sorted(groups):
        items = sorted(groups[name], key=lambda r: r["received"], reverse=True)
        out.append(f"## {name} ({len(items)})")
        out += [f"- {r['received'][:10]} {r['received'][11:16]} — {subject(r)}" for r in items]
        out.append("")
    return out

NAMES = ["alice", "bob.durand", "compta", "support", "x+news", "marie-l", "o.brien", "dev_ops"]
SUBJECTS = [
    "Réunion jeudi", "Facture 2026-04 à régler", "Mise à jour du planning de la semaine prochaine",
    "Alerte disque", "Re: devis", "  Bonjour  ", "\nObjet après saut de ligne\nsuite",
    ("Quarante " * 6)[:40], ("Quarante " * 6)[:41],
    "Ça marche très bien, merci beaucoup à toute l'équipe pour ce travail",
]

def random_set(seed):
    rnd = random.Random(seed)
    base = datetime(2026, 1, 1) + timedelta(days=rnd.randint(0, 200))
    names = rnd.sample(NAMES, rnd.randint(2, 5))
    stamps = rnd.sample(range(0, 60 * 24 * 60), rnd.randint(8, 16))  # minutes, toutes distinctes
    rows = []
    for i, minutes in enumerate(stamps):
        name = rnd.choice(names)
        if rnd.random() < 0.3:
            name = name.capitalize()
        row = {"id": f"t{seed}-{i}", "sender": f"{name}@example.test",
               "received": (base + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "body": "corps"}
        roll = rnd.random()
        if roll < 0.2:
            pass                      # clé subject absente
        elif roll < 0.3:
            row["subject"] = None
        elif roll < 0.35:
            row["subject"] = "   "
        else:
            row["subject"] = rnd.choice(SUBJECTS)
        if rnd.random() < 0.08:
            del row["sender"]
        if rnd.random() < 0.2:
            del row["body"]
        rows.append(row)
    rnd.shuffle(rows)
    return rows

fixture = json.load(open(os.path.join(TP, "kit", "fixtures", "mails.json"), encoding="utf-8"))
SEED = random.randrange(1000, 99999)
cases = [("jeu A", random_set(SEED)), ("jeu B", random_set(SEED + 1)),
         ("jeu C", random_set(SEED + 2)), ("liste vide", []), ("un seul mail", random_set(SEED + 3)[:1]),
         ("fixture du kit", fixture)]

for label, rows in cases:
    work = os.path.join(TMP, "dossier test " + label.replace(" ", "_"))
    os.makedirs(work)
    src = os.path.join(work, "entree.json")
    with open(src, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False)
    digest = hashlib.sha256(open(src, "rb").read()).hexdigest()
    env = {"PATH": os.environ["PATH"], "LANG": "C.UTF-8", "HOME": TMP}
    try:
        p = subprocess.run(["python3", "-B", os.path.join(TP, "rapport.py"), src], cwd=work, env=env,
                           capture_output=True, timeout=15, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        fail(f"{label} : rapport.py ne se termine pas en 15 s.")
    if p.returncode != 0:
        err = (p.stderr.decode("utf-8", "replace").strip().splitlines() or ["(aucun message)"])[-1]
        fail(f"{label} : rapport.py a échoué (code {p.returncode}) : {err}")
    if hashlib.sha256(open(src, "rb").read()).hexdigest() != digest:
        fail(f"{label} : rapport.py a modifié le fichier d'entrée, il ne doit que le lire.")
    out = os.path.join(work, "rapport.md")
    if not os.path.isfile(out):
        fail(f"{label} : rapport.md n'a pas été créé dans le dossier courant.")
    try:
        got = open(out, encoding="utf-8").read()
    except UnicodeDecodeError:
        fail(f"{label} : rapport.md doit être écrit en UTF-8.")
    got = [l.rstrip() for l in got.rstrip("\n").split("\n")]
    want = expected(rows)
    while want and not want[-1]:
        want.pop()
    for i in range(max(len(got), len(want))):
        g = got[i] if i < len(got) else "(fin du fichier)"
        w = want[i] if i < len(want) else "(fin attendue)"
        if g != w:
            fail(f"{label} : ligne {i + 1} différente.\n  attendu : {w}\n  obtenu  : {g}")

print("OK : rapport.md est correct sur 6 jeux de données différents (clés manquantes, casse, tri, troncature).")
PY
