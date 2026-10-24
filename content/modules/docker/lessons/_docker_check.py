#!/usr/bin/env python3
"""Vérifications des TP du module Docker.

Analyse statique, en lecture seule, du dossier de l'apprenant : aucun démon Docker,
aucun réseau, aucune écriture. Lancer avec `python3 -I -B`.
Usage : _docker_check.py <dk1|dk2|dk3> [dossier]
Le répertoire courant (ou `dossier`, sous-dossier direct) est le dossier du TP.
"""
from __future__ import annotations

import json
import os
import re
import sys

MAX_BYTES = 200_000
SECRET_NAME = re.compile(r"(pass(word|wd)?|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key)", re.I)


class CheckError(Exception):
    """Erreur affichée à l'apprenant."""


def need(condition, message: str) -> None:
    if not condition:
        raise CheckError(message)


def read_text(name: str) -> str:
    need(os.path.isfile(name) and not os.path.islink(name), f"{name} est introuvable (ou n'est pas un fichier normal)")
    with open(name, encoding="utf-8") as f:
        text = f.read(MAX_BYTES + 1)
    need(len(text) <= MAX_BYTES, f"{name} est trop gros")
    return text


def instructions(text: str) -> list[tuple[str, str]]:
    """Dockerfile -> [(INSTRUCTION, arguments)], continuations `\\` jointes, commentaires ignorés."""
    out, buf = [], ""
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#") or (not line and not buf):
            continue
        if line.endswith("\\"):
            buf += line[:-1] + " "
            continue
        buf += line
        parts = re.split(r"\s+", buf.strip(), maxsplit=1)
        out.append((parts[0].upper(), parts[1].strip() if len(parts) > 1 else ""))
        buf = ""
    if buf.strip():
        parts = re.split(r"\s+", buf.strip(), maxsplit=1)
        out.append((parts[0].upper(), parts[1].strip() if len(parts) > 1 else ""))
    return out


def dockerfile() -> list[tuple[str, str]]:
    ins = instructions(read_text("Dockerfile"))
    need(ins, "Dockerfile est vide")
    need(ins[0][0] in ("FROM", "ARG"), "un Dockerfile commence par FROM")
    return ins


def from_lines(ins) -> list[tuple[str, str | None]]:
    """[(image, alias)] pour chaque FROM."""
    out = []
    for name, args in ins:
        if name != "FROM":
            continue
        toks = [t for t in args.split() if not t.startswith("--")]
        need(toks, "FROM sans image")
        alias = toks[2] if len(toks) >= 3 and toks[1].upper() == "AS" else None
        out.append((toks[0], alias))
    return out


def assert_pinned_images(ins) -> None:
    stages = set()
    for image, alias in from_lines(ins):
        if image in stages or image == "scratch":
            pass
        else:
            last = image.rsplit("/", 1)[-1]
            need("@sha256:" in image or ":" in last, f"l'image {image} n'a pas de version : ajoutez un tag précis (python:3.12-slim)")
            if "@sha256:" not in image:
                tag = last.split(":", 1)[1]
                need(tag.lower() != "latest", f"l'image {image} utilise le tag latest : il change sans prévenir, épinglez une version")
        if alias:
            stages.add(alias)


def json_list(args: str, what: str) -> list[str]:
    need(args.startswith("["), f"{what} doit être en forme exec (liste JSON) : {what} [\"python\", \"app.py\"]")
    try:
        value = json.loads(args)
    except ValueError:
        raise CheckError(f"{what} : la liste JSON est invalide (guillemets doubles obligatoires)") from None
    need(isinstance(value, list) and value and all(isinstance(x, str) for x in value), f"{what} : liste de chaînes attendue")
    return value


def find(ins, name: str) -> list[int]:
    return [i for i, (n, _) in enumerate(ins) if n == name]


def copy_sources(args: str) -> list[str]:
    toks = [t.strip("\"'") for t in args.split() if not t.startswith("--")]
    return toks[:-1] if len(toks) >= 2 else []


# ---- dk1 : un premier Dockerfile ----

def check_dk1() -> None:
    ins = dockerfile()
    assert_pinned_images(ins)
    work = [a for n, a in ins if n == "WORKDIR"]
    need(work and work[-1].startswith("/"), "ajoutez WORKDIR avec un chemin absolu (par exemple /app)")
    copies = [copy_sources(a) for n, a in ins if n == "COPY"]
    need(any("app.py" in s or "." in s for s in copies), "copiez app.py dans l'image avec COPY")
    expose = [a for n, a in ins if n == "EXPOSE"]
    need(any(re.fullmatch(r"8000(/tcp)?", t) for a in expose for t in a.split()), "documentez le port avec EXPOSE 8000")
    cmds = [a for n, a in ins if n == "CMD"]
    need(cmds, "ajoutez un CMD qui lance l'application")
    words = json_list(cmds[-1], "CMD")
    need(words[0].startswith("python"), "CMD doit lancer python")
    need("app.py" in words, "CMD doit lancer app.py")


# ---- dk2 : cache, taille, multi-stage ----

def dockerignore_entries() -> set[str]:
    out = set()
    for line in read_text(".dockerignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        line = line.lstrip("/").removeprefix("**/").rstrip("/")
        out.add(line)
    return out


def check_dk2() -> None:
    ins = dockerfile()
    assert_pinned_images(ins)
    stages = from_lines(ins)
    need(len(stages) >= 2, "utilisez un build multi-stage : un FROM ... AS build pour installer, un FROM final pour exécuter")
    aliases = {a for _, a in stages if a}
    need(aliases, "nommez l'étape de build : FROM python:3.12-slim AS build")
    need(any(n == "COPY" and any(t.startswith("--from=") and t[7:] in aliases for t in a.split()) for n, a in ins),
         "l'image finale doit récupérer le résultat du build avec COPY --from=build")
    pips = [i for i, (n, a) in enumerate(ins) if n == "RUN" and "pip install" in a]
    need(pips, "installez les dépendances avec RUN pip install")
    for i in pips:
        args = ins[i][1]
        need("--no-cache-dir" in args, "pip install doit utiliser --no-cache-dir (sinon le cache pip alourdit l'image)")
        need(re.search(r"-r\s+requirements\.txt", args), "pip install doit lire requirements.txt (-r requirements.txt)")
    first_pip = pips[0]
    req = [i for i, (n, a) in enumerate(ins) if n == "COPY" and "requirements.txt" in copy_sources(a)]
    need(req and req[0] < first_pip, "copiez requirements.txt AVANT pip install, pour que la couche des dépendances reste en cache")
    full = [i for i, (n, a) in enumerate(ins) if n == "COPY" and any(s in (".", "./") for s in copy_sources(a))]
    need(full, "copiez le code de l'application avec COPY . .")
    need(all(i > first_pip for i in full), "COPY . . doit venir APRÈS pip install : sinon chaque modification du code refait l'installation")
    for n, a in ins:
        if n == "RUN" and "apt-get install" in a:
            need("apt-get update" in a, "apt-get update et apt-get install vont dans le même RUN")
            need("--no-install-recommends" in a, "apt-get install doit utiliser --no-install-recommends")
            need("rm -rf /var/lib/apt/lists" in a, "nettoyez le cache apt dans le même RUN : rm -rf /var/lib/apt/lists/*")
    wanted = {".git", ".env", "__pycache__"}
    missing = sorted(wanted - dockerignore_entries())
    need(not missing, f".dockerignore doit exclure : {', '.join(missing)}")


# ---- dk3 : sécurité ----

def final_stage(ins):
    last_from = find(ins, "FROM")[-1]
    return ins[last_from:]


def check_dockerfile_security() -> None:
    ins = dockerfile()
    assert_pinned_images(ins)
    for n, a in ins:
        if n in ("ENV", "ARG"):
            for tok in re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(\S+)", a) or re.findall(r"^(\S+)\s+(\S+)", a):
                name, value = tok
                need(not (SECRET_NAME.search(name) and value.strip("\"'")),
                     f"{n} {name} contient un secret en clair : il reste dans l'image. Passez-le à l'exécution (variable d'environnement)")
    stage = final_stage(ins)
    users = [a for n, a in stage if n == "USER"]
    need(users, "ajoutez USER dans l'image finale : sans lui, l'application tourne en root")
    user = users[-1].split(":")[0].strip()
    need(user not in ("root", "0"), "USER ne doit pas être root")
    if not user.isdigit():
        created = any(n == "RUN" and re.search(rf"(useradd|adduser)\b.*\b{re.escape(user)}\b", a) for n, a in ins)
        need(created, f"l'utilisateur {user} n'est créé nulle part : ajoutez RUN useradd ... {user}")
    health = [a for n, a in stage if n == "HEALTHCHECK"]
    need(health and (health[-1].split() or ["NONE"])[0].upper() != "NONE","ajoutez un HEALTHCHECK pour que Docker sache si l'application répond")


def strip_yaml_comments(text: str) -> str:
    return "\n".join(re.sub(r"\s+#.*$", "", l) if not l.lstrip().startswith("#") else "" for l in text.splitlines())


def check_compose() -> None:
    text = strip_yaml_comments(read_text("docker-compose.yml"))
    need(not re.search(r"^\s*privileged:\s*true\b", text, re.M), "privileged: true donne presque tous les droits de l'hôte : retirez-le")
    need("docker.sock" not in text, "ne montez jamais docker.sock : c'est un accès root à la machine")
    need(re.search(r"^\s*read_only:\s*true\b", text, re.M), "ajoutez read_only: true (système de fichiers du conteneur en lecture seule)")
    need(re.search(r"no-new-privileges", text), "ajoutez security_opt: [no-new-privileges:true]")
    need(re.search(r"cap_drop:\s*(\[\s*[\"']?ALL[\"']?\s*\]|\n(\s*-\s*\S+\s*\n)*?\s*-\s*[\"']?ALL[\"']?\s*(\n|$))", text),
         "ajoutez cap_drop: - ALL (retirez toutes les capacités Linux)")
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(\s*)ports:\s*$", line)
        if not m:
            continue
        for entry in lines[i + 1:]:
            if not entry.strip():
                continue
            if len(entry) - len(entry.lstrip()) <= len(m.group(1)) or not entry.lstrip().startswith("-"):
                break
            port = entry.lstrip()[1:].strip().strip("\"'")
            need(port.startswith("127.0.0.1:") or port.startswith("[::1]:"),
                 f"le port {port} est publié sur toutes les interfaces : préfixez 127.0.0.1: (\"127.0.0.1:8000:8000\")")
    for line in lines:
        m = re.match(r"^\s*-?\s*([A-Za-z_][A-Za-z0-9_]*)\s*[:=]\s*(\S.*)$", line)
        if m and SECRET_NAME.search(m.group(1)):
            value = m.group(2).strip().strip("\"'")
            need(value.startswith("${") or value in ("", "|"),
                 f"{m.group(1)} contient un secret en clair dans le compose : utilisez ${{{m.group(1)}}} et un fichier .env non versionné")


def check_dk3() -> None:
    check_dockerfile_security()
    check_compose()


def check_boss2() -> None:
    check_dk1()
    check_dk2()


def check_boss3() -> None:
    check_dk1()
    check_dk2()
    check_dk3()


CHECKS = {
    "dk1": (check_dk1, "le Dockerfile est valide et reproductible."),
    "dk2": (check_dk2, "le build est rapide, léger et le contexte filtré."),
    "dk3": (check_dk3, "conteneur non-root, sans secret en clair et durci."),
    # boss : cumulatif, chaque phase revérifie les précédentes
    "boss1": (check_dk1, "Dockerfile valide et reproductible."),
    "boss2": (check_boss2, "build multi-stage, rapide et contexte filtré."),
    "boss3": (check_boss3, "conteneur non-root, sans secret et durci."),
}


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3) or argv[1] not in CHECKS:
        print(f"Usage: {argv[0]} <{'|'.join(CHECKS)}> [dossier]", file=sys.stderr)
        return 2
    try:
        if len(argv) == 3:
            d = argv[2]
            need(os.path.isdir(d) and not os.path.islink(d) and "/" not in d and d not in ("", ".", ".."),
                 f"le dossier {d}/ est introuvable à la racine de l'espace de travail")
            os.chdir(d)
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
