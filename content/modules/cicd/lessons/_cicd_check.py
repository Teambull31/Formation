#!/usr/bin/env python3
"""Vérifications des TP du module CI/CD (GitHub Actions).

Analyse statique, en lecture seule, des workflows de l'apprenant : aucun réseau, aucune exécution.
Lancer avec `python3 -I -B`. Usage : _cicd_check.py <ci1..ci7|boss1..boss3> [dossier] (le répertoire courant est le dossier du TP).
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


def yaml_file(path: str) -> dict:
    name = os.path.basename(path)
    need(os.path.isfile(path) and not os.path.islink(path), f"{path} est introuvable")
    with open(path, encoding="utf-8") as f:
        text = f.read(MAX_BYTES + 1)
    need(len(text) <= MAX_BYTES, f"{path} est trop gros")
    try:
        doc = load(text)
    except YamlError as e:
        raise CheckError(f"{name} n'est pas un YAML valide : {e}") from None
    need(isinstance(doc, dict), f"{name} doit être un document YAML de la forme cle: valeur")
    return doc


def workflow(name: str) -> dict:
    doc = yaml_file(os.path.join(".github", "workflows", name))
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

def assert_no_leaks(doc: dict) -> None:
    """Pas d'injection ni de secret exposé dans un run:, pas de secret en clair, actions tierces sur SHA."""
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
                    need(isinstance(v, str) and v.strip().startswith("${{") and ("secrets." in v or "github.token" in v),
                         f"{k} contient un secret en clair : utilisez ${{{{ secrets.{str(k).upper()} }}}} et définissez-le dans les paramètres du dépôt")
        u = uses_of(s)
        if u and not u.startswith("./"):  # action locale : versionnée avec le dépôt
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
    assert_no_leaks(doc)
    need(any(re.search(r"secrets\.", str(s.get("env")) + str(s.get("with"))) for _, s in all_steps(doc)),
         "le déploiement doit recevoir son jeton depuis ${{ secrets.DEPLOY_TOKEN }} via env: ou with:")


# ---- ci4 : workflow réutilisable et action composite ----

def as_list(v) -> list:
    return v if isinstance(v, list) else [v] if v is not None else []


def check_ci4() -> None:
    action = yaml_file(os.path.join(".github", "actions", "setup", "action.yml"))
    runs = action.get("runs")
    need(isinstance(runs, dict) and runs.get("using") == "composite", "action.yml : runs: using: composite est attendu")
    inp = (action.get("inputs") or {}).get("python-version") if isinstance(action.get("inputs"), dict) else None
    need(isinstance(inp, dict) and inp.get("required") is True, "action.yml : déclarez l'entrée python-version avec required: true")
    steps = runs.get("steps")
    need(isinstance(steps, list) and steps and all(isinstance(x, dict) for x in steps), "action.yml : runs.steps doit lister les étapes")
    for st in steps:
        if "run" in st:
            need(st.get("shell"), "action.yml : chaque étape run: d'une action composite doit déclarer shell: bash")
    sp = [x for x in steps if action_name(uses_of(x)) == "actions/setup-python"]
    need(sp, "action.yml : appelez actions/setup-python@v5")
    w = sp[0].get("with") or {}
    need("inputs.python-version" in str(w.get("python-version", "")), "action.yml : setup-python doit lire ${{ inputs.python-version }}")
    need(str(w.get("cache", "")) == "pip", "action.yml : gardez cache: pip")
    need(any(re.search(r"pip install\b.*-r\s+requirements\.txt", str(x.get("run", ""))) for x in steps),
         "action.yml : installez requirements.txt (run: pip install -r requirements.txt)")

    reu = workflow("reusable-test.yml")
    on = reu.get("on")
    need("workflow_call" in triggers(reu), "reusable-test.yml doit se déclencher par workflow_call")
    need(triggers(reu) == {"workflow_call"}, "reusable-test.yml ne doit avoir que workflow_call comme déclencheur : il n'est lancé que par ses appelants")
    wc = on.get("workflow_call") if isinstance(on, dict) else None
    pv = ((wc or {}).get("inputs") or {}).get("python-version") if isinstance(wc, dict) else None
    need(isinstance(pv, dict) and pv.get("type") == "string" and pv.get("required") is True,
         "reusable-test.yml : entrée python-version avec type: string et required: true")
    need("test" in reu["jobs"], "reusable-test.yml : un job test est attendu")
    job = reu["jobs"]["test"]
    need(str(job.get("runs-on", "")).startswith("ubuntu-"), "reusable-test.yml : le job test tourne sur ubuntu-latest")
    need(isinstance(job.get("timeout-minutes"), int) and 0 < job["timeout-minutes"] <= 30, "reusable-test.yml : timeout-minutes (30 au plus) sur le job test")
    st = steps_of(job)
    names = [action_name(uses_of(x)) for x in st]
    need(names and names[0] == "actions/checkout", "reusable-test.yml : actions/checkout doit être la première étape")
    need("./.github/actions/setup" in names, "reusable-test.yml : appelez l'action locale ./.github/actions/setup")
    loc = st[names.index("./.github/actions/setup")]
    need("inputs.python-version" in str((loc.get("with") or {}).get("python-version", "")),
         "reusable-test.yml : passez with: python-version: ${{ inputs.python-version }} à l'action locale")
    need(any("pytest" in str(x.get("run", "")) for x in st), "reusable-test.yml : lancez pytest")

    ci = workflow("ci.yml")
    need(triggers(ci) >= {"push", "pull_request"}, "ci.yml reste déclenché par push et pull_request")
    perm = ci.get("permissions")
    need(isinstance(perm, dict) and perm.get("contents") == "read", "ci.yml : gardez permissions: contents: read")
    callers = {jid: j for jid, j in ci["jobs"].items() if str(j.get("uses", "")) == "./.github/workflows/reusable-test.yml"}
    need(callers, "ci.yml : un job doit appeler uses: ./.github/workflows/reusable-test.yml")
    for jid, j in ci["jobs"].items():
        need(not any("pytest" in str(x.get("run", "")) for x in steps_of(j)),
             f"ci.yml : le job {jid} recopie encore les étapes de test : remplacez-le par l'appel au workflow réutilisable")
    for jid, j in callers.items():
        need("steps" not in j and "runs-on" not in j, f"ci.yml : le job {jid} appelle un workflow : il n'a ni runs-on ni steps")
        versions = (((j.get("strategy") or {}).get("matrix") or {}).get("python-version"))
        need(isinstance(versions, list) and len(versions) >= 2, f"ci.yml : le job {jid} a besoin d'une matrice python-version d'au moins deux versions")
        need("matrix.python-version" in str((j.get("with") or {}).get("python-version", "")),
             f"ci.yml : le job {jid} passe with: python-version: ${{{{ matrix.python-version }}}}")


# ---- ci5 : environnements et déploiement continu ----

def env_name(job: dict):
    e = job.get("environment")
    return e.get("name") if isinstance(e, dict) else e


def reads_version(job: dict) -> bool:
    return any("needs.build.outputs.version" in str((x.get("env") or {}).get("VERSION", "")) for x in steps_of(job))


def check_ci5(name: str = "deploy.yml") -> None:
    doc = workflow(name)
    t = triggers(doc)
    need(not t & {"pull_request", "pull_request_target"},
         f"{name} : un déploiement ne se déclenche pas sur une pull request (code non relu)")
    push = doc["on"].get("push") if isinstance(doc.get("on"), dict) else None
    need(isinstance(push, dict) and as_list(push.get("branches")) == ["main"], f"{name} : déclenchez sur push avec branches: [main] uniquement")
    need("workflow_dispatch" in t, f"{name} : ajoutez workflow_dispatch pour pouvoir redéployer à la main")
    perm = doc.get("permissions")
    need(isinstance(perm, dict) and perm.get("contents") == "read", f"{name} : permissions: contents: read au niveau du workflow")
    jobs = doc["jobs"]
    for jid in ("build", "deploy-staging", "deploy-production"):
        need(jid in jobs, f"{name} : le job {jid} est attendu")
    for jid, job in jobs.items():
        need(isinstance(job.get("timeout-minutes"), int) and 0 < job["timeout-minutes"] <= 30, f"{name} : timeout-minutes (30 au plus) sur le job {jid}")
    for _, x in all_steps(doc):
        need("::set-output" not in str(x.get("run", "")), f"{name} : ::set-output est désactivé : écrivez dans \"$GITHUB_OUTPUT\"")
    build = jobs["build"]
    need("steps.meta.outputs.version" in str((build.get("outputs") or {}).get("version", "")),
         f"{name} : build doit déclarer outputs: version: ${{{{ steps.meta.outputs.version }}}}")
    meta = [x for x in steps_of(build) if x.get("id") == "meta"]
    need(meta and "GITHUB_OUTPUT" in str(meta[0].get("run", "")) and "version=" in str(meta[0].get("run", "")),
         f"{name} : l'étape meta écrit version=... dans \"$GITHUB_OUTPUT\"")
    stg, prod = jobs["deploy-staging"], jobs["deploy-production"]
    need("build" in as_list(stg.get("needs")), f"{name} : deploy-staging attend build (needs: build)")
    need(env_name(stg) == "staging", f"{name} : deploy-staging porte environment: staging")
    pn = as_list(prod.get("needs"))
    need("deploy-staging" in pn, f"{name} : deploy-production attend deploy-staging")
    need("build" in pn, f"{name} : deploy-production lit needs.build.outputs : build doit figurer dans ses needs")
    need(env_name(prod) == "production", f"{name} : deploy-production porte l'environnement production")
    cond = re.sub(r"\s+", "", str(prod.get("if", ""))).replace('"', "'")
    need("github.ref=='refs/heads/main'" in cond, f"{name} : deploy-production ne tourne que si github.ref == 'refs/heads/main'")
    for jid, job in (("deploy-staging", stg), ("deploy-production", prod)):
        need(reads_version(job), f"{name} : {jid} lit la version par env: VERSION: ${{{{ needs.build.outputs.version }}}}")
    for where, conc in (("le workflow", doc.get("concurrency")), ("deploy-production", prod.get("concurrency"))):
        need(not (isinstance(conc, dict) and conc.get("cancel-in-progress") is True),
             f"{name} : {where} ne doit pas annuler un déploiement en cours (cancel-in-progress: false)")
    conc = prod.get("concurrency")
    need(isinstance(conc, dict) and conc.get("group"), f"{name} : deploy-production sérialise ses déploiements avec concurrency: group")


# ---- ci6 : artefacts, release, OIDC ----

def check_ci6(name: str = "release.yml") -> None:
    doc = workflow(name)
    push = doc["on"].get("push") if isinstance(doc.get("on"), dict) else None
    tags = as_list(push.get("tags")) if isinstance(push, dict) else []
    need(any(str(x).startswith("v") for x in tags), f"{name} : déclenchez sur les tags : push: tags: [\"v*\"]")
    perm = doc.get("permissions")
    need(isinstance(perm, dict) and perm and all(v == "read" for v in perm.values()),
         f"{name} : au niveau du workflow, permissions en lecture seule (contents: read)")
    jobs = doc["jobs"]
    need("build" in jobs and "publish" in jobs, f"{name} : deux jobs, build puis publish")
    build, pub = jobs["build"], jobs["publish"]
    up = [x for x in steps_of(build) if action_name(uses_of(x)) == "actions/upload-artifact"]
    need(up, f"{name} : build téléverse dist/ avec actions/upload-artifact@v4")
    uw = up[0].get("with") or {}
    need(uw.get("name") and uw.get("path"), f"{name} : upload-artifact a besoin de name et path")
    rd = uw.get("retention-days")
    need(isinstance(rd, int) and 0 < rd <= 30, f"{name} : retention-days (30 au plus) sur l'artefact")
    need("build" in as_list(pub.get("needs")), f"{name} : publish attend build (needs: build)")
    down = [x for x in steps_of(pub) if action_name(uses_of(x)) == "actions/download-artifact"]
    need(down and (down[0].get("with") or {}).get("name") == uw["name"],
         f"{name} : publish télécharge l'artefact avec actions/download-artifact@v4 et le même name")
    jp = pub.get("permissions")
    need(isinstance(jp, dict) and jp.get("contents") == "write" and jp.get("id-token") == "write",
         f"{name} : le job publish reçoit contents: write et id-token: write")
    for jid, job in jobs.items():
        if jid != "publish":
            need(not (isinstance(job.get("permissions"), dict) and job["permissions"].get("id-token") == "write"),
                 f"{name} : id-token: write est réservé au job publish")
    for jid, x in all_steps(doc):
        keys = {str(k).lower() for k in (x.get("with") or {})} | {str(k).lower() for k in (x.get("env") or {})}
        need(not any("access-key" in k or "access_key" in k for k in keys),
             f"{name} : clé cloud statique dans le job {jid} : supprimez aws-access-key-id / aws-secret-access-key, l'OIDC suffit")
    aws = [x for x in steps_of(pub) if action_name(uses_of(x)) == "aws-actions/configure-aws-credentials"]
    need(aws and (aws[0].get("with") or {}).get("role-to-assume"), f"{name} : connectez-vous par OIDC : configure-aws-credentials avec role-to-assume")
    assert_no_leaks(doc)
    rel = [x for x in steps_of(pub) if "gh release create" in str(x.get("run", ""))]
    need(rel, f"{name} : une étape crée la release : gh release create \"$GITHUB_REF_NAME\" dist/*")
    need("GITHUB_REF_NAME" in str(rel[0]["run"]), f"{name} : utilisez \"$GITHUB_REF_NAME\" pour le nom du tag")
    need("github.token" in str((rel[0].get("env") or {}).get("GH_TOKEN", "")), f"{name} : passez GH_TOKEN: ${{{{ github.token }}}} dans env:")


# ---- ci7 : répare la panne ----

CI7_CAUSES = {"version-python": "yaml", "cache": "cache", "deploy": "dependance",
              "release": "permissions", "pull-request": "declencheur"}


def check_diagnostic(causes: dict[str, str]) -> None:
    diag = yaml_file("diagnostic.yaml")
    for comp, cause in causes.items():
        got = str(diag.get(comp, "?")).strip().lower()
        need(got != "?", f"diagnostic.yaml : donnez une cause pour {comp}")
        need(got == cause, f"diagnostic.yaml : la cause de {comp} n'est pas la bonne, relisez le fichier d'incident correspondant")


def check_ci7() -> None:
    check_diagnostic(CI7_CAUSES)
    doc = workflow("ci.yml")
    on = doc.get("on") if isinstance(doc.get("on"), dict) else {}
    need("pull_request" in triggers(doc), "ci.yml : aucun check sur les pull requests, ajoutez le déclencheur pull_request")
    push = on.get("push") if isinstance(on.get("push"), dict) else {}
    branches = [str(b) for b in as_list(push.get("branches"))]
    need("main" in branches and "master" not in branches,
         "ci.yml : la branche par défaut s'appelle main depuis le renommage, push: branches doit viser main")
    need(any(str(t).startswith("v") for t in as_list(push.get("tags"))), "ci.yml : gardez le déclenchement sur les tags v*")
    jobs = doc["jobs"]
    need({"test", "deploy", "release"} <= set(jobs), "ci.yml : gardez les trois jobs test, deploy et release")
    py = [x for x in steps_of(jobs["test"]) if action_name(uses_of(x)) == "actions/setup-python"]
    need(py, "ci.yml : gardez l'étape actions/setup-python dans test")
    ver = (py[0].get("with") or {}).get("python-version")
    need(isinstance(ver, str) and re.fullmatch(r"3\.\d+", ver.strip()),
         "ci.yml : python-version non quoté est lu comme un nombre (3.10 devient 3.1) : écrivez \"3.10\" entre guillemets")
    cache = [x for x in steps_of(jobs["test"]) if action_name(uses_of(x)) == "actions/cache"]
    need(cache, "ci.yml : gardez l'étape actions/cache")
    key = str((cache[0].get("with") or {}).get("key", ""))
    need("hashFiles(" in key and "requirements/" in key,
         "ci.yml : la clé de cache hache requirements.txt, qui n'existe pas : hashez requirements/*.txt pour qu'elle change avec les dépendances")
    need("test" in as_list(jobs["deploy"].get("needs")), "ci.yml : deploy part en parallèle des tests, ajoutez needs: [test]")
    perm = doc.get("permissions")
    need(isinstance(perm, dict) and perm and all(v == "read" for v in perm.values()),
         "ci.yml : gardez permissions: contents: read au niveau du workflow")
    jp = jobs["release"].get("permissions")
    need(isinstance(jp, dict) and jp.get("contents") == "write",
         "ci.yml : la release échoue en 403, donnez permissions: contents: write au seul job release")
    for jid, job in jobs.items():
        if jid != "release":
            need(not (isinstance(job.get("permissions"), dict) and "write" in job["permissions"].values()),
                 f"ci.yml : le job {jid} n'a pas besoin de droits en écriture")
    assert_no_leaks(doc)


# ---- boss : cumulatif, dans ciboss/ ----

def boss_security() -> None:
    for name in ("ci.yml", "deploy.yml", "release.yml"):
        assert_no_leaks(workflow(name))


CHECKS = {
    "ci1": ([check_ci1], "le workflow installe, teste, et tourne sur push et pull request."),
    "ci2": ([check_ci2], "workflow rapide, parallèle, borné et en lecture seule."),
    "ci3": ([check_ci3], "pipeline de déploiement sans secret en clair ni injection."),
    "ci4": ([check_ci4], "CI factorisée : action composite et workflow réutilisable."),
    "ci5": ([check_ci5], "chaîne build, staging, production sûre et sérialisée."),
    "ci6": ([check_ci6], "release sur tag, artefacts et OIDC sans clé statique."),
    "ci7": ([check_ci7], "les cinq pannes sont diagnostiquées et le pipeline est réparé."),
    # le boss est cumulatif : une phase ultérieure revérifie les précédentes
    "boss1": ([check_ci2], "phase 1 : la CI est rapide, bornée et en lecture seule."),
    "boss2": ([check_ci2, check_ci5], "phase 2 : la chaîne de déploiement est sûre."),
    "boss3": ([check_ci2, check_ci5, check_ci6, boss_security], "phase 3 : la release est publiée sans clé ni fuite."),
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
        checks, success = CHECKS[argv[1]]
        for check in checks:
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
