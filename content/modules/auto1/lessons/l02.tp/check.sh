#!/usr/bin/env bash
# Contrôle du TP 2 : analyse planning.cron avec un petit parseur (aucune exécution cron).
# cwd = dossier du TP.
[ -f planning.cron ] || { echo "ECHEC : le fichier planning.cron est introuvable dans le dossier du TP."; exit 1; }
timeout 20 python3 - <<'PY'
import os, re, shlex, sys

def fail(msg):
    print("ECHEC : " + msg)
    sys.exit(1)

MOIS = {m: i for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}
JOURS = {j: i for i, j in enumerate("sun mon tue wed thu fri sat".split())}

def champ(texte, nom, lo, hi, noms=None):
    """Renvoie l'ensemble des valeurs désignées par un champ cron."""
    def val(s):
        s = s.lower()
        if noms and s in noms:
            return noms[s]
        if not s.isdigit():
            fail(f"champ {nom} : valeur « {s} » invalide.")
        return int(s)
    out = set()
    for part in texte.split(","):
        if not part:
            fail(f"champ {nom} : élément vide dans « {texte} ».")
        base, _, pas = part.partition("/")
        if pas and not pas.isdigit() or pas == "0":
            fail(f"champ {nom} : pas « {pas} » invalide.")
        step = int(pas) if pas else 1
        if base == "*":
            a, b = lo, hi
        elif "-" in base:
            x, y = base.split("-", 1)
            a, b = val(x), val(y)
        else:
            a = val(base)
            b = hi if pas else a
        if not (lo <= a <= hi and lo <= b <= hi):
            fail(f"champ {nom} : valeur hors de la plage {lo}-{hi} dans « {part} ».")
        if a > b:
            fail(f"champ {nom} : intervalle « {part} » à l'envers.")
        out |= set(range(a, b + 1, step))
    return out

lignes = []
for brut in open("planning.cron", encoding="utf-8"):
    l = brut.strip()
    if not l or l.startswith("#") or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", l):
        continue  # commentaire, ligne vide, variable d'environnement (PATH=…)
    lignes.append(l)
if len(lignes) != 1:
    fail(f"planning.cron doit contenir exactement 1 ligne de tâche (trouvé : {len(lignes)}).")
ligne = lignes[0]
if ligne.startswith("@"):
    fail("les raccourcis @daily, @reboot… ne permettent pas « 12 h 15 en semaine » : écrivez les 5 champs.")
champs = ligne.split(None, 5)
if len(champs) < 6:
    fail("une ligne cron = 5 champs (minute heure jour-du-mois mois jour-de-semaine) puis la commande.")
m, h, dom, mois, dow, cmd = champs

minutes = champ(m, "minute", 0, 59)
heures = champ(h, "heure", 0, 23)
doms = champ(dom, "jour du mois", 1, 31)
mo = champ(mois, "mois", 1, 12, MOIS)
sem = champ(dow, "jour de la semaine", 0, 7, JOURS)
sem = {0 if d == 7 else d for d in sem}

if minutes != {15}:
    fail(f"minute : attendu 15, obtenu {sorted(minutes)}.")
if heures != {12}:
    fail(f"heure : attendu 12, obtenu {sorted(heures)}.")
if doms != set(range(1, 32)) or mo != set(range(1, 13)):
    fail("jour du mois et mois doivent valoir * : la tâche tourne toute l'année.")
if sem != {1, 2, 3, 4, 5}:
    noms = "dim lun mar mer jeu ven sam".split()
    print("ECHEC : jours attendus lundi à vendredi, obtenu : " + (", ".join(noms[d] for d in sorted(sem)) or "aucun") + ".")
    sys.exit(1)

# commande : exactement  <tri.sh> <inbox du TP> >> <log> 2>&1  (rien d'autre)
if re.search(r"(?<!\\)%", cmd):
    fail("un % non protégé dans la commande : cron le transforme en saut de ligne. Écrivez \\% ou évitez-le.")
try:
    mots = shlex.split(cmd)
except ValueError:
    fail("guillemets non fermés dans la commande.")
if not mots:
    fail("commande vide.")
tp = os.path.realpath(".")
script = mots[0]
if not os.path.isabs(script):
    fail(f"le chemin « {script} » doit être absolu : cron ne démarre pas dans votre dossier.")
if os.path.basename(script) != "tri.sh":
    fail("la commande doit lancer votre tri.sh.")
if not os.path.isfile(script):
    fail(f"{script} n'existe pas.")
if not os.access(script, os.X_OK):
    fail(f"{script} n'est pas exécutable : lancez chmod +x tri.sh.")
if os.path.realpath(script) != os.path.join(tp, "tri.sh"):
    fail("le chemin doit désigner le tri.sh de ce dossier de TP.")
if len(mots) < 3 or mots[1] in (">>", ">", "2>&1"):
    fail("tri.sh a besoin du dossier à trier, en chemin absolu (le inbox/ du TP), juste après le script.")
if not os.path.isabs(mots[1]) or os.path.realpath(mots[1]) != os.path.join(tp, "inbox"):
    fail("le dossier à trier doit être exactement le inbox/ de ce TP, en chemin absolu.")
reste = mots[2:]
if any(t in (">", "2>", "&>") for t in reste):
    fail("une seule redirection >> est attendue (un > simple écraserait le log).")
if len(reste) < 2 or reste[0] != ">>":
    fail("après le dossier, redirigez la sortie vers un log avec >> (ajout, sans écraser).")
log = reste[1]
if not os.path.isabs(log):
    fail("le fichier de log après >> doit être un chemin absolu.")
rlog = os.path.realpath(log)
if rlog == "/dev/null" or not rlog.startswith(tp + os.sep) or os.path.isdir(rlog):
    fail("le log doit être un fichier dans le dossier du TP (pas /dev/null ni ailleurs).")
if reste[2:] != ["2>&1"]:
    fail("terminez la ligne par 2>&1 juste après le log, sans rien d'autre (pas de &&, ;, &).")

print("OK : planning.cron — du lundi au vendredi à 12 h 15, chemin absolu et log en ajout.")
PY
