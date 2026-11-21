#!/usr/bin/env python3
"""Vérifications du projet fil rouge : un seul dépôt, de l'application à la production.

Analyse statique, en lecture seule, du dossier du TP. Réutilise les vérificateurs des modules CI/CD, Docker,
Kubernetes, Terraform et Ansible. Lancer avec `python3 -I -B`. Usage : _projet_check.py <pr1..pr5> [dossier]
Chaque étape revérifie les précédentes : le projet reste cohérent de bout en bout.
"""
from __future__ import annotations

import os
import re
import sys

MODULES = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _m in ("ansible", "terraform", "docker", "k8s", "cicd"):  # -I retire les dossiers des scripts du chemin
    sys.path.insert(0, os.path.join(MODULES, _m, "lessons"))
import _ansible_check as an  # noqa: E402
import _cicd_check as ci  # noqa: E402
import _docker_check as dk  # noqa: E402
import _hcl_check as hcl  # noqa: E402
import _k8s_check as k8  # noqa: E402

ERRORS = (ci.CheckError, dk.CheckError, k8.CheckError, hcl.CheckError, an.CheckError)


class CheckError(Exception):
    """Erreur affichée à l'apprenant."""


def need(condition, message: str) -> None:
    if not condition:
        raise CheckError(message)


class inside:
    """Exécute un contrôle depuis un sous-dossier du projet (k8s/, infra/, ansible/)."""

    def __init__(self, d: str):
        self.d = d

    def __enter__(self):
        need(os.path.isdir(self.d) and not os.path.islink(self.d), f"le dossier {self.d}/ est introuvable à la racine du projet")
        self.back = os.getcwd()
        os.chdir(self.d)

    def __exit__(self, *exc):
        os.chdir(self.back)


def runs(job: dict) -> str:
    return "\n".join(str(s.get("run", "")) for s in ci.steps_of(job))


# ---- pr1 : l'application et sa CI ----

def check_pr1() -> None:
    need(os.path.isfile(os.path.join("app", "main.py")), "app/main.py est introuvable : gardez l'application à la racine du projet")
    need(any(f.startswith("test_") and f.endswith(".py") for f in os.listdir("app")), "app/ doit contenir des tests (test_*.py)")
    doc = ci.workflow("ci.yml")
    need({"push", "pull_request"} <= ci.triggers(doc), "ci.yml : déclenchez sur push et pull_request")
    perm = doc.get("permissions")
    need(isinstance(perm, dict) and perm and all(v == "read" for v in perm.values()),
         "ci.yml : permissions en lecture seule au niveau du workflow (contents: read)")
    jobs = doc["jobs"]
    need("test" in jobs, "ci.yml : un job test")
    t = jobs["test"]
    need(isinstance(t.get("timeout-minutes"), int) and t["timeout-minutes"] <= 30, "ci.yml : test borné par timeout-minutes (30 au plus)")
    uses = [ci.action_name(ci.uses_of(s)) for s in ci.steps_of(t)]
    need("actions/checkout" in uses, "ci.yml : le job test commence par actions/checkout")
    py = [s for s in ci.steps_of(t) if ci.action_name(ci.uses_of(s)) == "actions/setup-python"]
    need(py and isinstance((py[0].get("with") or {}).get("python-version"), str),
         "ci.yml : actions/setup-python avec python-version entre guillemets (\"3.12\")")
    need("pip install" in runs(t) and "pytest" in runs(t), "ci.yml : le job test installe les dépendances (pip install) puis lance pytest")
    ci.assert_no_leaks(doc)


# ---- pr2 : l'image et sa publication ----

def check_pr2() -> None:
    ins = dk.dockerfile()
    dk.assert_pinned_images(ins)
    need(len(dk.find(ins, "FROM")) >= 2, "Dockerfile : un build multi-stage (deux FROM : dépendances, puis image finale)")
    stage = dk.final_stage(ins)
    users = [a for n, a in stage if n == "USER"]
    need(users and users[-1].split(":")[0].strip() not in ("root", "0"), "Dockerfile : USER non-root dans l'image finale")
    need([a for n, a in stage if n == "HEALTHCHECK"], "Dockerfile : un HEALTHCHECK sur /healthz")
    cmd = [a for n, a in stage if n == "CMD"]
    need(cmd, "Dockerfile : un CMD qui lance l'application")
    dk.json_list(cmd[-1], "CMD")
    rules = dk.dockerignore_entries()
    need({".git", ".env"} <= {r.strip("/") for r in rules}, ".dockerignore : excluez au moins .git et .env du contexte")
    doc = ci.workflow("ci.yml")
    jobs = doc["jobs"]
    need("image" in jobs, "ci.yml : ajoutez un job image qui construit et publie l'image")
    img = jobs["image"]
    need("test" in ci.as_list(img.get("needs")), "ci.yml : image attend les tests (needs: [test])")
    need("refs/heads/main" in str(img.get("if", "")), "ci.yml : ne publiez que depuis main (if: github.ref == 'refs/heads/main')")
    jp = img.get("permissions")
    need(isinstance(jp, dict) and jp.get("packages") == "write", "ci.yml : le job image reçoit permissions: packages: write (et rien de plus large)")
    blob = runs(img) + "\n" + "\n".join(str(v) for s in ci.steps_of(img) for v in (s.get("with") or {}).values())
    need("ghcr.io/" in blob, "ci.yml : publiez l'image sur ghcr.io/<compte>/<projet>")
    need("github.sha" in blob or "GITHUB_SHA" in blob, "ci.yml : étiquetez l'image avec le commit (${{ github.sha }}), pas latest")
    ci.assert_no_leaks(doc)


# ---- pr3 : Kubernetes ----

def check_pr3() -> None:
    with inside("k8s"):
        dep = k8.deployment(k8.docs("deployment.yaml"), "k8s/deployment.yaml")
        k8.check_deployment_basics(dep)
        spec = k8.get(dep, "spec", "template", "spec")
        need(k8.get(spec, "securityContext", "runAsNonRoot") is True, "k8s/deployment.yaml : securityContext: runAsNonRoot: true au niveau du pod")
        for c in k8.containers(dep):
            need(str(c.get("image", "")).startswith("ghcr.io/"), "k8s/deployment.yaml : l'image vient de ghcr.io, celle que la CI publie")
            k8.probe_ok(c, "readinessProbe")
            k8.probe_ok(c, "livenessProbe")
            need((c.get("securityContext") or {}).get("allowPrivilegeEscalation") is False,
                 "k8s/deployment.yaml : securityContext: allowPrivilegeEscalation: false sur le conteneur")
        svc = k8.of_kind(k8.docs("service.yaml"), "Service")
        need(svc, "k8s/service.yaml doit contenir un Service")
        need(k8.selects(k8.get(svc[0], "spec", "selector"), k8.pod_labels(dep)),
             "k8s/service.yaml : le sélecteur du Service doit correspondre aux étiquettes des pods")
        kz = ci.yaml_file("kustomization.yaml")
        res = [str(r) for r in kz.get("resources") or []]
        need({"deployment.yaml", "service.yaml"} <= set(res), "k8s/kustomization.yaml : resources liste deployment.yaml et service.yaml")


# ---- pr4 : Terraform ----

def check_pr4() -> None:
    rules = hcl.load_gitignore(".gitignore") if os.path.isfile(".gitignore") else []
    for p in ("infra/terraform.tfstate", "infra/.terraform/providers"):
        need(hcl.is_ignored(rules, p), f".gitignore : {p} doit être ignoré (le state et .terraform/ ne vont jamais dans Git)")
    for p in ("infra/main.tf", "infra/.terraform.lock.hcl"):
        need(not hcl.is_ignored(rules, p), f".gitignore : {p} doit rester versionné")
    with inside("infra"):
        blocks = hcl.module_blocks()
        tf = [b for b in blocks if b.type == "terraform"]
        need(tf, "infra/ : un bloc terraform avec required_version et required_providers")
        need(hcl.version_ok(hcl.literal(tf[0].attrs.get("required_version"))), "infra/ : required_version, par exemple \">= 1.6\"")
        rp = [b for b in tf[0].blocks if b.type == "required_providers"]
        need(rp and rp[0].attrs, "infra/ : required_providers avec au moins un provider")
        for name, spec in rp[0].attrs.items():
            need(hcl.version_ok(hcl.literal(hcl.parse_object(spec).get("version"))), f"infra/ : le provider {name} a besoin d'une version (~> X.Y)")
        be = [b for b in tf[0].blocks if b.type == "backend"]
        need(be, "infra/ : déclarez un backend distant (s3, gcs, azurerm…) : le state ne reste pas sur un poste")
        for bad in ("access_key", "secret_key", "token", "password"):
            need(bad not in be[0].attrs, f"infra/ : backend : supprimez {bad}, les identifiants viennent de l'environnement ou d'OIDC")
        env = [b for b in blocks if b.type == "variable" and b.labels == ["environment"]]
        need(env and [b for b in env[0].blocks if b.type == "validation"], "infra/ : variable environment avec un bloc validation")
        need([b for b in blocks if b.type == "output"], "infra/ : au moins un output (ce qu'Ansible ou la CI lira)")
        hcl.assert_no_hardcoded_secret()


# ---- pr5 : Ansible et README ----

def check_pr5() -> None:
    with inside("ansible"):
        hosts, _, hvars, gvars = an.inventory("inventory.ini")
        need(any(g != "ungrouped" and h for g, h in hosts.items()), "ansible/inventory.ini : rangez les hôtes dans au moins un groupe")
        an.no_password_in_inventory(hvars, gvars)
        plays = an.playbook("site.yml")
        for p in plays:
            tasks = an.play_tasks(p, ("pre_tasks", "tasks", "post_tasks"))
            handlers = an.task_list(p.get("handlers"), "handlers")
            need(tasks or p.get("roles"), "ansible/site.yml : chaque play a des tâches ou des rôles")
            an.check_task_style(tasks + handlers, "ansible/site.yml")
            an.check_idempotent_commands(tasks, "ansible/site.yml")
            an.check_file_modes(tasks, "ansible/site.yml")
            an.check_handlers(tasks, handlers, "ansible/site.yml")
        for f in an.yml_files():
            an.scan_plain_secrets(an.yaml_file(f), f)
    need(os.path.isfile("README.md"), "README.md est introuvable à la racine du projet")
    with open("README.md", encoding="utf-8") as fh:
        text = fh.read(200_000)
    heads = [h.lower() for h in re.findall(r"^#{1,3}\s+(.+)$", text, re.M)]
    for want, words in (("Architecture", ("architecture",)), ("Démarrer", ("démarrer", "demarrer", "lancer", "installer")),
                        ("Déployer", ("déployer", "deployer", "déploiement", "deploiement"))):
        need(any(any(w in h for w in words) for h in heads), f"README.md : ajoutez une section « {want} »")
    need(len(text) >= 400, "README.md : expliquez le projet en quelques paragraphes (400 caractères au moins)")


CHECKS = {
    "pr1": ([check_pr1], "étape 1 : l'application est testée par une CI sûre."),
    "pr2": ([check_pr1, check_pr2], "étape 2 : l'image est durcie et publiée par la CI."),
    "pr3": ([check_pr1, check_pr2, check_pr3], "étape 3 : l'application tourne sur Kubernetes."),
    "pr4": ([check_pr1, check_pr2, check_pr3, check_pr4], "étape 4 : l'infrastructure est décrite en Terraform."),
    "pr5": ([check_pr1, check_pr2, check_pr3, check_pr4, check_pr5], "projet complet : de l'application à la production, documenté."),
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
    except (CheckError, *ERRORS) as e:
        print(f"ECHEC : {e}")
        return 1
    except (OSError, ValueError, AttributeError, TypeError, RecursionError) as e:
        print(f"ECHEC : fichier inattendu ({type(e).__name__}) : vérifiez l'indentation et la forme des fichiers")
        return 1
    print(f"OK : {success}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
