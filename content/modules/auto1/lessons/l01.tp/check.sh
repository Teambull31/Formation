#!/usr/bin/env bash
# Contrôle du TP 1 : exécute ./tri.sh sur des dossiers jetables générés au hasard.
# cwd = dossier du TP ; aucune donnée de l'apprenant n'est modifiée.
set -u

fail() { echo "ECHEC : $*"; exit 1; }

[ -f tri.sh ] || fail "le fichier tri.sh est introuvable dans le dossier du TP."
[ -x tri.sh ] || fail "tri.sh n'est pas exécutable (chmod +x tri.sh)."
head -n1 tri.sh | grep -q '^#!' || fail "tri.sh doit commencer par un shebang (#!/usr/bin/env bash)."
SCRIPT="$PWD/tri.sh"

TMP=$(mktemp -d) || fail "impossible de créer un dossier temporaire."
trap 'rm -rf "$TMP"' EXIT

# 1) sans argument : code 2 + message d'usage
out=$(cd "$TMP" && timeout 20 "$SCRIPT" 2>&1 </dev/null); rc=$?
[ "$rc" -eq 2 ] || fail "sans argument, le script doit sortir avec le code 2 (reçu : $rc)."
echo "$out" | grep -qi 'usage' || fail "sans argument, affichez un message commençant par « Usage »."

# 2) dossier inexistant : code non nul
(cd "$TMP" && timeout 20 "$SCRIPT" "$TMP/n-existe-pas" >/dev/null 2>&1 </dev/null) \
  && fail "un dossier inexistant doit provoquer un code de sortie non nul."

# 3) plusieurs jeux de fichiers aléatoires, dont des noms avec espaces
export TMP SCRIPT
timeout 50 python3 - <<'PY' || exit 1
import hashlib, os, random, subprocess, sys
from pathlib import Path

tmp, script = Path(os.environ["TMP"]), os.environ["SCRIPT"]
rnd = random.Random()
EXTS = ["txt", "pdf", "jpg", "csv", "docx", "gz", "md", "log", "png", "PDF", "JPG", "Txt"]
MOTS = ["facture", "rapport final", "photo  vacances", "notes d'équipe", "budget", "compte rendu", "x", "été 2026"]

def fail(msg):
    print("ECHEC : " + msg)
    sys.exit(1)

def tree(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}

def run(args, cwd):
    return subprocess.run([script, *args], cwd=cwd, capture_output=True, text=True, timeout=20)

for n in range(4):
    base = tmp / f"jeu {n}"
    box = base / "boîte à trier"
    box.mkdir(parents=True)
    names = set()
    while len(names) < rnd.randint(6, 12):
        mot = rnd.choice(MOTS) + f" {rnd.randint(1, 99)}"
        names.add(mot + "." + rnd.choice(EXTS) if rnd.random() > 0.2 else mot)
    names.add("LISEZMOI")  # toujours un fichier sans extension
    names.add("archive.v2.tar.gz")
    names.add("Scan Été.PDF")  # extension en majuscules : dossier en minuscules
    for nm in names:
        (box / nm).write_text(f"contenu {nm} {rnd.random()}\n", encoding="utf-8")
    (box / "déjà rangé").mkdir()  # un sous-dossier existant doit rester intact
    (box / "déjà rangé" / "vieux.txt").write_text("ancien\n")

    expected = {}
    for nm in names:
        ext = nm.rsplit(".", 1)[1].lower() if "." in nm else "sans_extension"
        expected[f"{ext}/{nm}"] = hashlib.sha256((box / nm).read_bytes()).hexdigest()
    expected["déjà rangé/vieux.txt"] = hashlib.sha256(b"ancien\n").hexdigest()

    # dossier donné en chemin relatif, depuis un autre dossier
    r = run([f"{box.name}"], base)
    if r.returncode != 0:
        fail(f"code de sortie {r.returncode} sur un dossier valide. Message : {r.stderr.strip()[:200]}")
    got = tree(box)
    if got != expected:
        manque = sorted(set(expected) - set(got))[:3]
        trop = sorted(set(got) - set(expected))[:3]
        fail(f"l'arborescence obtenue diffère de l'attendue (manquant : {manque} ; en trop : {trop}). "
             "Vérifiez les guillemets autour des noms avec espaces et le dossier sans_extension/.")
    if any(p.is_file() for p in box.iterdir()):
        fail("des fichiers restent à la racine du dossier trié.")
    # le script ne doit rien perdre : mêmes contenus, rien supprimé
    if sorted(got.values()) != sorted(expected.values()):
        fail("des fichiers ont été modifiés ou supprimés.")
    # idempotence : relancer ne change rien et réussit
    r = run([str(box)], base)
    if r.returncode != 0 or tree(box) != expected:
        fail("relancer le script sur un dossier déjà trié doit réussir sans rien changer.")

# dossier vide : réussit sans erreur
vide = tmp / "vide"
vide.mkdir()
if run([str(vide)], tmp).returncode != 0:
    fail("un dossier vide ne doit pas provoquer d'erreur.")
PY

echo "OK : tri.sh range correctement, gère les espaces, le code 2 et ne supprime rien."
