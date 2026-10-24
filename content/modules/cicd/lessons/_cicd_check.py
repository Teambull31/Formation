#!/usr/bin/env python3
"""Vérifications des TP du module CI/CD (GitHub Actions).

Analyse statique, en lecture seule, des workflows de l'apprenant : aucun réseau, aucune exécution.
Lancer avec `python3 -I -B`. Usage : _cicd_check.py <ci1|ci2|ci3> (le répertoire courant est le dossier du TP).
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I retire le dossier du script du chemin
from _yaml import YamlError, load  # noqa: E402

MAX_BYTES = 200_000
SECRET_NAME = re.compile(r"(pass(word|wd)?|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key)", re.I)
EXPR = re.compile(r"\$\{\{(.*?)\}\}", re.S)


class CheckError(Exception):
    """Erreur affichée à l'apprenant."""


def need(condition, message: str) -> None:
    if not condition:
        raise CheckError(message)


def workflow(name: str) -> dict:
    path = os.path.join(".github", "workflows", name)
    need(os.path.isfile(path) and not os.path.islink(path), f"{path} est introuvable")
    with open(path, encoding="utf-8") as f:
        text = f.read(MAX_BYTES + 1)
    need(len(text) <= MAX_BYTES, f"{path} est trop gros")
    try:
        doc = load(text)
    except YamlError as e:
        raise CheckError(f"{name} n'est pas un YAML valide : {e}") from None
    need(isinstance(doc, dict), f"{name} doit être un document YAML de la forme cle: valeur")
    need(isinstance(doc.get("jobs"), dict) and doc["jobs"], f"{name} doit contenir un bloc jobs: avec au moins un job")
    for jid, job in doc["jobs"].items():
        need(isinstance(job, dict), f"le job {jid} doit être un bloc de la forme cle: valeur")
        need(isinstance(job.get("steps", []), list), f"jobs.{jid}.steps doit être une liste (lignes commençant par « - »)")
        for s in job.get("steps", []):
            need(isinstance(s, dict), f"chaque étape de {jid} doit être de la forme « - uses: ... » ou « - run: ... »")
    return doc


def triggers(doc: dict) -> set[str]:
    on = doc.get("on")
    if isinstance(on, str):
        return {on}
    if isinstance(on, list):
        return {str(x) for x in on}
    if isinstance(on, dict):
        return set(on)
    return set()


def steps_of(job: dict) -> list[dict]:
    return job.get("steps") or []


def uses_of(step: dict) -> str:
    u = step.get("uses")
    return u if isinstance(u, str) else ""


def action_name(uses: str) -> str:
    return uses.split("@", 1)[0]


def all_steps(doc: dict):
    for jid, job in doc["jobs"].items():
        for s in steps_of(job):
            yield jid, s


# ---- ci1 : un premier workflow ----

def check_ci1() -> None:
    doc = workflow("ci.yml")
    t = triggers(doc)
    need("push" in t, "le workflow doit se déclencher sur push (on: push)")
    need("pull_request" in t, "le workflow doit aussi se déclencher sur pull_request : la CI doit tourner avant la fusion")
    test_jobs = [j for j in doc["jobs"].values() if any("pytest" in str(s.get("run", "")) for s in steps_of(j))]
    need(test_jobs, "aucun job ne lance pytest : ajoutez une étape « run: pytest »")
    job = test_jobs[0]
    ro = str(job.get("runs-on", ""))
    need(ro.startswith("ubuntu-"), "runs-on doit désigner une machine Linux, par exemple ubuntu-latest")
    steps = steps_of(job)
    names = [action_name(uses_of(s)) for s in steps]
    need("actions/checkout" in names, "ajoutez l'étape actions/checkout@v4 : sans elle le code du dépôt n'est pas présent")
    need(names.index("actions/checkout") == min(i for i, s in enumerate(steps) if s), "actions/checkout doit être la première étape")
    need(re.fullmatch(r"actions/checkout@v\d+", uses_of(steps[names.index("actions/checkout")])),
         "épinglez la version : actions/checkout@v4")
    need("actions/setup-python" in names, "ajoutez actions/setup-python@v5 pour choisir la version de Python")
    sp = steps[names.index("actions/setup-python")]
    need(isinstance(sp.get("with"), dict) and sp["with"].get("python-version"), "setup-python a besoin de with: python-version: \"3.12\"")
    runs = [str(s.get("run", "")) for s in steps]
    inst = [i for i, r in enumerate(runs) if re.search(r"pip install\b.*-r\s+requirements\.txt", r)]
    test = [i for i, r in enumerate(runs) if "pytest" in r]
    need(inst, "installez les dépendances : run: pip install -r requirements.txt")
    need(inst[0] < test[0], "installez les dépendances AVANT de lancer pytest")
    need(names.index("actions/setup-python") < inst[0], "setup-python vient avant l'installation des dépendances")


# ---- ci2 : cache, matrice, dépendances entre jobs, moindre privilège ----

FLOATING = {"main", "master", "latest", "head", "dev", "develop"}


def check_ci2() -> None:
    doc = workflow("ci.yml")
    perm = doc.get("permissions")
    need(isinstance(perm, dict) and perm.get("contents") == "read",
         "ajoutez au niveau du workflow : permissions: contents: read (le jeton ne doit pas pouvoir écrire dans le dépôt)")
    need(all(v == "read" or k == "id-token" for k, v in perm.items()), "permissions : lecture seule, sauf id-token si nécessaire")
    conc = doc.get("concurrency")
    need(isinstance(conc, dict) and conc.get("group") and conc.get("cancel-in-progress") is True,
         "ajoutez concurrency: avec group et cancel-in-progress: true : une nouvelle exécution annule l'ancienne")
    jobs = doc["jobs"]
    need("test" in jobs and "build" in jobs, "il faut deux jobs : test, puis build")
    test, build = jobs["test"], jobs["build"]
    needs = build.get("needs")
    need(needs == "test" or (isinstance(needs, list) and "test" in needs), "le job build doit attendre le job test : needs: test")
    for jid, job in jobs.items():
        need(isinstance(job.get("timeout-minutes"), int) and 0 < job["timeout-minutes"] <= 30,
             f"le job {jid} doit avoir timeout-minutes (30 au plus) : un job bloqué consomme des minutes sans fin")
    matrix = ((test.get("strategy") or {}).get("matrix") or {})
    versions = matrix.get("python-version")
    need(isinstance(versions, list) and len(versions) >= 2, "testez au moins deux versions : strategy: matrix: python-version: [\"3.11\", \"3.12\"]")
    sp = [s for s in steps_of(test) if action_name(uses_of(s)) == "actions/setup-python"]
    need(sp, "le job test utilise actions/setup-python")
    w = sp[0].get("with") or {}
    need("matrix.python-version" in str(w.get("python-version", "")), "python-version doit lire la matrice : ${{ matrix.python-version }}")
    need(str(w.get("cache", "")) == "pip", "activez le cache des dépendances : with: cache: pip")
    for jid, s in all_steps(doc):
        u = uses_of(s)
        if u:
            need("@" in u, f"l'action {u} n'a pas de version : ajoutez @v4 (ou un SHA)")
            need(u.split("@", 1)[1].lower() not in FLOATING, f"l'action {u} suit une branche mobile : épinglez une version")
    check_ci1_steps(doc)


def check_ci1_steps(doc: dict) -> None:
    """Les exigences de ci1 qui restent valables avec une matrice."""
    test = doc["jobs"]["test"]
    steps = steps_of(test)
    names = [action_name(uses_of(s)) for s in steps]
    need(names and names[0] == "actions/checkout", "actions/checkout doit rester la première étape du job test")
    runs = [str(s.get("run", "")) for s in steps]
    need(any("pytest" in r for r in runs), "le job test doit lancer pytest")
    need(any(re.search(r"pip install\b.*-r\s+requirements\.txt", r) for r in runs), "le job test doit installer requirements.txt")
    need(triggers(doc) >= {"push", "pull_request"}, "le workflow reste déclenché par push et pull_request")


# ---- ci3 : secrets et sécurité du pipeline ----

def check_ci3() -> None:
    doc = workflow("deploy.yml")
    t = triggers(doc)
    need("pull_request_target" not in t,
         "pull_request_target donne des secrets et des droits d'écriture à du code venu d'un fork : utilisez pull_request ou un déclencheur sur main")
    perm = doc.get("permissions")
    need(perm is not None, "ajoutez permissions: contents: read au niveau du workflow")
    need(perm != "write-all" and isinstance(perm, dict), "permissions: write-all donne tous les droits au jeton : listez seulement ce qui est nécessaire")
    need(perm.get("contents") == "read", "permissions : contents: read")
    for jid, job in doc["jobs"].items():
        jp = job.get("permissions")
        need(jp != "write-all", f"le job {jid} ne doit pas utiliser write-all")
    for jid, s in all_steps(doc):
        run = str(s.get("run", ""))
        for expr in EXPR.findall(run):
            e = expr.strip()
            need(not re.search(r"github\.(event|head_ref)", e),
                 f"{{{{ {e} }}}} dans un run: est une injection de commande (le titre d'une PR peut contenir du shell). Passez-le par env: puis lisez $VARIABLE")
            need(not e.startswith("secrets."),
                 f"{{{{ {e} }}}} dans un run: expose le secret dans le script. Passez-le par env: ")
        for block in ("env", "with"):
            for k, v in (s.get(block) or {}).items() if isinstance(s.get(block), dict) else []:
                if SECRET_NAME.search(str(k)):
                    need(isinstance(v, str) and v.strip().startswith("${{") and "secrets." in v,
                         f"{k} contient un secret en clair : utilisez ${{{{ secrets.{str(k).upper()} }}}} et définissez-le dans les paramètres du dépôt")
        u = uses_of(s)
        if u:
            owner = u.split("/", 1)[0]
            ref = u.split("@", 1)[1] if "@" in u else ""
            if owner not in ("actions", "github"):
                need(re.fullmatch(r"[0-9a-f]{40}", ref),
                     f"l'action tierce {action_name(u)} doit être épinglée sur un SHA complet de 40 caractères : un tag ou une branche peut être déplacé par son auteur")
            else:
                need(ref and ref.lower() not in FLOATING, f"l'action {u} doit avoir une version précise")
    for jid, job in doc["jobs"].items():
        for k, v in (job.get("env") or {}).items() if isinstance(job.get("env"), dict) else []:
            if SECRET_NAME.search(str(k)):
                need(isinstance(v, str) and "secrets." in v, f"{k} contient un secret en clair dans le job {jid}")
    for k, v in (doc.get("env") or {}).items() if isinstance(doc.get("env"), dict) else []:
        if SECRET_NAME.search(str(k)):
            need(isinstance(v, str) and "secrets." in v, f"{k} contient un secret en clair dans env")
    need(any(re.search(r"secrets\.", str(s.get("env")) + str(s.get("with"))) for _, s in all_steps(doc)),
         "le déploiement doit recevoir son jeton depuis ${{ secrets.DEPLOY_TOKEN }} via env: ou with:")


CHECKS = {
    "ci1": (check_ci1, "le workflow installe, teste, et tourne sur push et pull request."),
    "ci2": (check_ci2, "workflow rapide, parallèle, borné et en lecture seule."),
    "ci3": (check_ci3, "pipeline de déploiement sans secret en clair ni injection."),
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
    except (OSError, ValueError, AttributeError, TypeError) as e:
        print(f"ECHEC : workflow inattendu ({type(e).__name__}) : vérifiez l'indentation et la forme des blocs")
        return 1
    print(f"OK : {success}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
