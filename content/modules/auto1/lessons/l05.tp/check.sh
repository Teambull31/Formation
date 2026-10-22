#!/usr/bin/env bash
# Contrôle du TP 5 : exécute lister.py sur les fixtures du kit et sur des fichiers JSON/mbox
# générés au hasard (mêmes mails dans les deux formats), source vide, chemin inexistant.
# cwd = dossier du TP.
[ -f lister.py ] || { echo "ECHEC : le fichier lister.py est introuvable dans le dossier du TP."; exit 1; }
[ -f kit/mail_source.py ] || { echo "ECHEC : le dossier kit/ est introuvable (il ne faut pas le supprimer)."; exit 1; }
TP="$PWD"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
TP="$TP" TMP="$TMP" timeout 50 python3 -B - <<'PY'
import json, mailbox, os, random, subprocess, sys
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import format_datetime

TP, TMP = os.environ["TP"], os.environ["TMP"]
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(TP, "kit"))
import mail_source

def fail(msg):
    print("ECHEC : " + msg)
    sys.exit(1)

src = open(os.path.join(TP, "lister.py"), encoding="utf-8", errors="replace").read()
if "mail_source" not in src or "JsonMailSource" not in src or "MboxMailSource" not in src:
    fail("lister.py doit utiliser JsonMailSource et MboxMailSource du module kit/mail_source.py.")

def run(source, path, label):
    env = {"PATH": os.environ["PATH"], "LANG": "C.UTF-8", "HOME": TMP}
    try:
        p = subprocess.run(["python3", "-B", "lister.py", "--source", source, "--path", path], cwd=TP,
                           env=env, capture_output=True, timeout=15, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        fail(f"{label} : lister.py ne se termine pas en 15 s.")
    out, err = p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    if "Traceback" in out + err:
        fail(f"{label} : lister.py affiche une trace Python ; attrapez l'erreur et affichez un message lisible.")
    return p.returncode, out, err

def compare(label, got, want):
    got = got.rstrip("\n").split("\n") if got.strip() else []
    for i in range(max(len(got), len(want))):
        g = got[i] if i < len(got) else "(fin de la sortie)"
        w = want[i] if i < len(want) else "(fin attendue)"
        if g != w:
            fail(f"{label} : ligne {i + 1} différente.\n  attendu : {w}\n  obtenu  : {g}")

def check_ok(label, source, path, want):
    rc, out, err = run(source, path, label)
    if rc != 0:
        fail(f"{label} : code de sortie {rc} au lieu de 0. {err.strip().splitlines()[-1] if err.strip() else ''}")
    compare(label, out, want)
    return out

def write_json(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False)

def write_mbox(path, rows):
    box = mailbox.mbox(path)
    for r in rows:
        m = EmailMessage()
        m["From"], m["To"], m["Subject"] = r["sender"], "moi@example.test", r["subject"]
        m["Date"] = format_datetime(datetime.fromisoformat(r["received"].replace("Z", "+00:00")))
        m["Message-ID"] = f"<{r['id']}@example.test>"
        m.set_content(r["body"])
        box.add(m)
    box.flush()
    box.close()

# ---- 0. lister.py passe bien par le kit : on le rejoue avec un faux mail_source.py ----
import shutil
stub = os.path.join(TMP, "stub")
os.makedirs(os.path.join(stub, "kit"))
shutil.copy(os.path.join(TP, "lister.py"), stub)
STUB_TAG = f"{random.randrange(10**6)}"
open(os.path.join(stub, "kit", "mail_source.py"), "w", encoding="utf-8").write(f'''
class _M:
    def __init__(self, i): self.sender, self.subject = f"bidon{{i}}@example.test", "sujet-{STUB_TAG}-" + str(i)
class _S:
    def __init__(self, path): self.path = path
    def fetch(self, since=None, limit=50): return [_M(i) for i in range(9)][:limit]
class JsonMailSource(_S): pass
class MboxMailSource(_S): pass
''')
open(os.path.join(stub, "x.dat"), "w").write("[]")
for source in ("json", "mbox"):
    p = subprocess.run(["python3", "-B", "lister.py", "--source", source, "--path", "x.dat"], cwd=stub,
                       env={"PATH": os.environ["PATH"], "LANG": "C.UTF-8", "HOME": TMP}, capture_output=True,
                       timeout=15, stdin=subprocess.DEVNULL)
    want = "".join(f"bidon{i}@example.test | sujet-{STUB_TAG}-{i}\n" for i in range(5))
    if p.stdout.decode("utf-8", "replace") != want:
        fail(f"lister.py ({source}) doit afficher les mails renvoyés par source.fetch(limit=5) du kit, "
             "sans relire lui-même le fichier ni coder la sortie.")

# ---- 1. fixtures du kit : attendu calculé avec les sources du kit ----
fx = os.path.join(TP, "kit", "fixtures")
for source, name, cls in (("json", "mails.json", mail_source.JsonMailSource),
                          ("mbox", "inbox.mbox", mail_source.MboxMailSource)):
    want = [f"{m.sender} | {m.subject}" for m in cls(os.path.join(fx, name)).fetch(limit=5)]
    check_ok(f"fixture {source}", source, os.path.join(fx, name), want)

# ---- 2. fichiers aléatoires, mêmes mails en JSON et en mbox ----
SENDERS = ["alice", "bob.durand", "compta", "support", "marie-l", "o.brien", "dev_ops", "zoe", "newsletter"]
SUBJECTS = ["Réunion déplacée", "Facture à régler", "Mise à jour du planning", "Alerte disque 90 %", "Re: devis été",
            "Café ou thé ?", "Bilan | mars", "Ça avance", "Noël : horaires", "Point hebdo", "Relance n° 2", "Accès VPN"]

def random_rows(seed, n):
    rnd = random.Random(seed)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=rnd.randint(0, 200))
    stamps = rnd.sample(range(0, 60 * 24 * 40), n)  # minutes, toutes distinctes
    rows = []
    for i, minutes in enumerate(stamps):
        rows.append({"id": f"r{seed}-{i}", "sender": f"{rnd.choice(SENDERS)}{rnd.randint(1, 99)}@example.test",
                     "subject": rnd.choice(SUBJECTS) + f" {rnd.randint(100, 999)}",
                     "received": (base + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     "body": f"Corps {i}"})
    rnd.shuffle(rows)
    return rows

SEED = random.randrange(1000, 99999)
for label, n in (("beaucoup de mails", 12), ("exactement 5 mails", 5), ("3 mails", 3), ("un seul mail", 1)):
    rows = random_rows(SEED + n, n)
    want = [f"{r['sender']} | {r['subject']}" for r in sorted(rows, key=lambda r: r["received"], reverse=True)[:5]]
    pj, pm = os.path.join(TMP, f"t{n}.json"), os.path.join(TMP, f"t{n}.mbox")
    write_json(pj, rows)
    write_mbox(pm, rows)
    out_j = check_ok(f"{label} (json)", "json", pj, want)
    out_m = check_ok(f"{label} (mbox)", "mbox", pm, want)
    if out_j != out_m:
        fail(f"{label} : les mêmes mails donnent deux sorties différentes en json et en mbox ; le code d'affichage doit être commun.")

# ---- 3. source vide ----
pj, pm = os.path.join(TMP, "vide.json"), os.path.join(TMP, "vide.mbox")
write_json(pj, [])
open(pm, "w").close()
check_ok("source vide (json)", "json", pj, ["(aucun mail)"])
check_ok("source vide (mbox)", "mbox", pm, ["(aucun mail)"])

# ---- 4. chemin inexistant : erreur lisible, code non nul, rien sur stdout ----
for source in ("json", "mbox"):
    bad = os.path.join(TMP, f"nexiste-pas-{SEED}.{source}")
    rc, out, err = run(source, bad, f"chemin inexistant ({source})")
    if rc == 0:
        fail(f"chemin inexistant ({source}) : le code de sortie doit être non nul.")
    if not err.strip():
        fail(f"chemin inexistant ({source}) : affichez un message d'erreur lisible sur stderr.")
    if out.strip():
        fail(f"chemin inexistant ({source}) : rien ne doit être écrit sur stdout (le message va sur stderr).")
    if os.path.exists(bad):
        fail(f"chemin inexistant ({source}) : lister.py ne doit pas créer le fichier.")

print("OK : lister.py affiche les 5 plus récents avec le même code pour JSON et mbox, gère la source vide et l'erreur de chemin.")
PY
