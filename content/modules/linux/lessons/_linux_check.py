#!/usr/bin/env python3
"""Vérifications des TP du module Linux et réseau.

Lecture seule du dossier de l'apprenant. lx2 exécute les scripts de l'apprenant dans un dossier
temporaire, sur des journaux que l'apprenant ne voit pas. Lancer avec `python3 -I -B`.
Usage : _linux_check.py <lx1|lx2|lx3>   (le répertoire courant est le dossier du TP)
"""
from __future__ import annotations

import os
import random
import re
import stat
import subprocess
import sys
import tempfile

MAX_BYTES = 200_000


class CheckError(Exception):
    """Erreur affichée à l'apprenant."""


def need(condition, message: str) -> None:
    if not condition:
        raise CheckError(message)


def regular(name: str) -> os.stat_result:
    need(os.path.lexists(name), f"{name} est introuvable")
    st = os.lstat(name)
    need(stat.S_ISREG(st.st_mode), f"{name} n'est pas un fichier normal")
    return st


def read_text(name: str) -> str:
    regular(name)
    with open(name, encoding="utf-8") as f:
        text = f.read(MAX_BYTES + 1)
    need(len(text) <= MAX_BYTES, f"{name} est trop gros")
    return text


def mode_of(name: str) -> int:
    return stat.S_IMODE(os.lstat(name).st_mode)


# ---- lx1 : fichiers et permissions ----

def check_lx1() -> None:
    regular("secrets.env")
    m = mode_of("secrets.env")
    need(m == 0o600, f"secrets.env a les droits {m:04o} : seul son propriétaire doit pouvoir le lire et l'écrire (600)")
    regular("deploy.sh")
    m = mode_of("deploy.sh")
    need(m & 0o100, f"deploy.sh (droits {m:04o}) n'est pas exécutable par son propriétaire")
    need(not m & 0o002, f"deploy.sh (droits {m:04o}) est modifiable par tout le monde : retirez l'écriture pour les autres")
    need(not m & 0o020, f"deploy.sh (droits {m:04o}) est modifiable par le groupe : un script de déploiement ne se partage pas en écriture")
    need(os.path.isdir("shared") and not os.path.islink("shared"), "le dossier shared/ est introuvable")
    m = mode_of("shared")
    need(m == 0o770, f"shared/ a les droits {m:04o} : le propriétaire et le groupe y travaillent, les autres n'ont aucun accès (770)")


# ---- lx2 : filtres sur les journaux ----

def make_log(rng: random.Random, n_ips: int, lines: int) -> tuple[str, list[tuple[int, str]], int]:
    ips = [f"10.{rng.randrange(1, 250)}.{rng.randrange(1, 250)}.{rng.randrange(1, 250)}" for _ in range(n_ips)]
    ips = list(dict.fromkeys(ips))
    # fréquences toutes distinctes : aucun ex æquo
    weights = list(range(len(ips), 0, -1))
    rows, errors = [], 0
    for ip, w in zip(ips, weights):
        for _ in range(w * 3):
            status = rng.choice([200, 200, 200, 301, 404, 500, 502, 503])
            errors += status >= 500
            rows.append(f'{ip} - - [12/Mar/2026:10:{rng.randrange(60):02d}:00 +0000] "GET /p{rng.randrange(9)} HTTP/1.1" {status} {rng.randrange(100, 9000)}')
    rng.shuffle(rows)
    top = sorted(((w * 3, ip) for ip, w in zip(ips, weights)), reverse=True)[:3]
    return "\n".join(rows) + "\n", top, errors


def run_script(script: str, log: str, tmp: str, timeout: float = 6) -> list[str]:
    need(os.path.isfile(script) and not os.path.islink(script), f"{script} est introuvable")
    with open(script, encoding="utf-8") as f:
        text = f.read(MAX_BYTES + 1)
    need(len(text) <= MAX_BYTES, f"{script} est trop gros")
    copy = os.path.join(tmp, script)
    with open(copy, "w", encoding="utf-8") as f:
        f.write(text)
    path = os.path.join(tmp, "access.log")
    with open(path, "w", encoding="utf-8") as f:
        f.write(log)
    try:
        proc = subprocess.run(["bash", copy, path], cwd=tmp, stdin=subprocess.DEVNULL, capture_output=True,
                              timeout=timeout, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
    except subprocess.TimeoutExpired:
        raise CheckError(f"{script} ne se termine pas (il lit peut-être l'entrée standard au lieu du fichier $1)") from None
    need(proc.returncode == 0, f"{script} se termine en erreur (code {proc.returncode}) : {proc.stderr.decode(errors='replace')[:200]}")
    return proc.stdout.decode(errors="replace").strip().splitlines()


def check_lx2() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        for seed in (11, 42):
            log, top, errors = make_log(random.Random(seed), 6, 0)
            out = run_script("top_ips.sh", log, tmp)
            need(len(out) == 3, f"top_ips.sh doit afficher exactement 3 lignes (il en affiche {len(out)})")
            got = []
            for line in out:
                parts = line.split()
                need(len(parts) == 2 and parts[0].isdigit(), f"ligne inattendue : {line!r} (attendu : NOMBRE ADRESSE_IP)")
                got.append((int(parts[0]), parts[1]))
            need(got == top, f"top_ips.sh donne {got} au lieu de {top} sur un journal de contrôle (triez du plus fréquent au moins fréquent)")
            out = run_script("errors_5xx.sh", log, tmp)
            need(len(out) == 1 and out[0].strip().isdigit(), "errors_5xx.sh doit afficher un seul nombre")
            need(int(out[0]) == errors, f"errors_5xx.sh compte {out[0]} erreurs 5xx au lieu de {errors} sur un journal de contrôle")
        calm = re.sub(r'" 5\d\d ', '" 200 ', log)  # aucune erreur : le script doit afficher 0, pas une ligne vide
        out = run_script("errors_5xx.sh", calm, tmp)
        need(out and out[0].strip() == "0", "errors_5xx.sh doit afficher 0 quand il n'y a aucune erreur 5xx")


# ---- lx3 : SSH et pare-feu ----

def sshd_options(text: str) -> dict[str, str]:
    """Comme sshd : la première valeur d'un mot-clé l'emporte ; on s'arrête au premier bloc Match."""
    opts: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = re.split(r"[\s=]+", line, maxsplit=1)
        key = parts[0].lower()
        if key == "match":
            break
        opts.setdefault(key, parts[1].strip() if len(parts) > 1 else "")
    return opts


def check_sshd() -> None:
    o = sshd_options(read_text("sshd_config"))
    need(o.get("permitrootlogin", "").lower() == "no", "PermitRootLogin doit valoir no : on ne se connecte jamais en root par SSH")
    need(o.get("passwordauthentication", "").lower() == "no", "PasswordAuthentication doit valoir no : clés SSH uniquement")
    need(o.get("pubkeyauthentication", "").lower() == "yes", "PubkeyAuthentication doit valoir yes")
    tries = o.get("maxauthtries", "")
    need(tries.isdigit() and 1 <= int(tries) <= 4, "MaxAuthTries doit être un nombre entre 1 et 4")
    need(o.get("x11forwarding", "").lower() == "no", "X11Forwarding doit valoir no sur un serveur")
    need(o.get("allowusers", "").strip(), "AllowUsers doit lister les comptes autorisés à se connecter (par exemple AllowUsers deploy)")


DANGEROUS_PORTS = ("5432", "3306", "6379", "27017")


def strip_nft(text: str) -> str:
    return "\n".join(re.sub(r"#.*$", "", l) for l in text.splitlines())


def input_chain(text: str) -> str:
    m = re.search(r"chain\s+input\s*\{(.*?)\n\s*\}", text, re.S)
    need(m, "il faut une chaîne input : chain input { ... }")
    return m.group(1)


def check_nft() -> None:
    text = strip_nft(read_text("firewall.nft"))
    body = input_chain(text)
    need(re.search(r"hook\s+input", body), "la chaîne input doit être accrochée au hook input")
    need(re.search(r"policy\s+drop\b", body), "la chaîne input doit avoir policy drop : tout ce qui n'est pas autorisé est refusé")
    need(re.search(r"ct\s+state\s+(established,\s*related|related,\s*established)\s+accept", body),
         "autorisez le trafic de réponse : ct state established,related accept")
    need(re.search(r'iif(name)?\s+"?lo"?\s+accept', body), 'autorisez la boucle locale : iif "lo" accept')
    ports = set()
    for line in body.splitlines():
        s = line.strip()
        need(s != "accept", "une règle accept sans condition ouvre tout le pare-feu : retirez-la")
        m = re.search(r"tcp\s+dport\s+(\{[^}]*\}|\d+)\s+(?:.*\s)?accept\b", s)
        if m:
            ports.update(re.findall(r"\d+", m.group(1)))
    need("22" in ports, "autorisez SSH : tcp dport 22 accept")
    need("443" in ports, "autorisez HTTPS : tcp dport 443 accept")
    open_db = sorted(ports & set(DANGEROUS_PORTS))
    need(not open_db, f"le port {open_db[0]} (base de données) ne doit pas être ouvert à Internet" if open_db else "")


def check_lx3() -> None:
    check_sshd()
    check_nft()


CHECKS = {
    "lx1": (check_lx1, "les droits sont justes : secrets fermés, script exécutable, dossier partagé."),
    "lx2": (check_lx2, "vos filtres donnent le bon résultat sur des journaux inconnus."),
    "lx3": (check_lx3, "SSH durci et pare-feu en refus par défaut."),
}


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in CHECKS:
        print(f"Usage: {argv[0]} <{'|'.join(CHECKS)}>", file=sys.stderr)
        return 2
    try:
        check, success = CHECKS[argv[1]]
        check()
    except CheckError as e:
        print(f"ECHEC : {e}")
        return 1
    except (OSError, ValueError) as e:
        print(f"ECHEC : fichier illisible ({type(e).__name__})")
        return 1
    print(f"OK : {success}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
