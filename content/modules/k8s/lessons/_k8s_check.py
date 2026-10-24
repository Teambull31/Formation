#!/usr/bin/env python3
"""Vérifications des TP du module Kubernetes.

Analyse statique, en lecture seule, des manifestes de l'apprenant : aucun cluster, aucun réseau.
Lancer avec `python3 -I -B`. Usage : _k8s_check.py <k1|k2|k3> (le répertoire courant est le dossier du TP).
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I retire le dossier du script du chemin
from _yaml import YamlError, load_all  # noqa: E402

MAX_BYTES = 200_000


class CheckError(Exception):
    """Erreur affichée à l'apprenant."""


def need(condition, message: str) -> None:
    if not condition:
        raise CheckError(message)


def docs(name: str) -> list[dict]:
    need(os.path.isfile(name) and not os.path.islink(name), f"{name} est introuvable")
    with open(name, encoding="utf-8") as f:
        text = f.read(MAX_BYTES + 1)
    need(len(text) <= MAX_BYTES, f"{name} est trop gros")
    try:
        out = load_all(text)
    except YamlError as e:
        raise CheckError(f"{name} n'est pas un YAML valide : {e}") from None
    for d in out:
        need(isinstance(d, dict) and d.get("kind") and d.get("apiVersion"),
             f"{name} : chaque document doit avoir apiVersion et kind")
    return out


def of_kind(items: list[dict], kind: str) -> list[dict]:
    return [d for d in items if d.get("kind") == kind]


def get(d, *path, default=None):
    for p in path:
        if not isinstance(d, dict) or p not in d:
            return default
        d = d[p]
    return d


def one(items: list[dict], kind: str, where: str) -> dict:
    found = of_kind(items, kind)
    need(len(found) == 1, f"{where} doit contenir exactement un {kind} (trouvé : {len(found)})")
    return found[0]


def labelled(sel) -> bool:
    """Sélecteur non vide dont toutes les valeurs sont renseignées."""
    return isinstance(sel, dict) and bool(sel) and all(isinstance(v, (str, int)) and str(v) != "" for v in sel.values())


def pod_labels(dep: dict) -> dict:
    labels = get(dep, "spec", "template", "metadata", "labels")
    need(isinstance(labels, dict) and labels, "le modèle de pod (spec.template.metadata.labels) doit porter des étiquettes")
    return labels


def containers(dep: dict) -> list[dict]:
    cs = get(dep, "spec", "template", "spec", "containers")
    need(isinstance(cs, list) and cs and all(isinstance(c, dict) for c in cs), "spec.template.spec.containers doit lister au moins un conteneur")
    return cs


def assert_pinned(image) -> None:
    need(isinstance(image, str) and image, "chaque conteneur a besoin d'une image")
    last = image.rsplit("/", 1)[-1]
    if "@sha256:" in image:
        return
    need(":" in last, f"l'image {image} n'a pas de tag : ajoutez une version précise (nginx:1.27)")
    need(last.split(":", 1)[1].lower() != "latest", f"l'image {image} utilise le tag latest : épinglez une version")


def deployment(items: list[dict], where: str) -> dict:
    dep = one(items, "Deployment", where)
    need(dep["apiVersion"] == "apps/v1", "un Deployment utilise apiVersion: apps/v1")
    need(isinstance(get(dep, "metadata", "name"), str), "le Deployment a besoin de metadata.name")
    return dep


# ---- k1 : Deployment ----

def check_deployment_basics(dep: dict) -> None:
    replicas = get(dep, "spec", "replicas")
    need(isinstance(replicas, int) and replicas >= 2, "spec.replicas doit valoir au moins 2 : un seul pod tombe avec son nœud")
    sel = get(dep, "spec", "selector", "matchLabels")
    need(isinstance(sel, dict) and sel, "spec.selector.matchLabels est obligatoire")
    labels = pod_labels(dep)
    need(all(labels.get(k) == v for k, v in sel.items()),
         "le sélecteur ne correspond pas aux étiquettes du modèle de pod : le Deployment ne retrouverait pas ses pods")
    for c in containers(dep):
        need(isinstance(c.get("name"), str) and c["name"], "chaque conteneur a besoin d'un nom")
        assert_pinned(c.get("image"))
        ports = c.get("ports") or []
        need(any(isinstance(p, dict) and p.get("containerPort") == 8000 for p in ports), "déclarez le port : ports: - containerPort: 8000")
        res = c.get("resources") or {}
        for kind in ("requests", "limits"):
            for what in ("cpu", "memory"):
                need(get(res, kind, what) is not None, f"resources.{kind}.{what} manque : sans lui le planificateur et le nœud n'ont aucune borne")


def check_k1() -> None:
    check_deployment_basics(deployment(docs("deployment.yaml"), "deployment.yaml"))


# ---- k2 : Service, configuration, secrets, sondes ----

def env_by_name(c: dict) -> dict:
    out = {}
    for e in c.get("env") or []:
        if isinstance(e, dict) and isinstance(e.get("name"), str):
            out[e["name"]] = e
    return out


def probe_ok(c: dict, kind: str) -> None:
    p = c.get(kind)
    need(isinstance(p, dict), f"ajoutez une {kind} au conteneur")
    path = get(p, "httpGet", "path")
    need(isinstance(path, str) and path.startswith("/"), f"{kind} : httpGet avec path (par exemple /healthz)")
    need(get(p, "httpGet", "port") in (8000, "8000", "http"), f"{kind} : httpGet.port doit viser le port de l'application (8000)")


def check_k2() -> None:
    items = docs("app.yaml")
    cm = one(items, "ConfigMap", "app.yaml")
    need(get(cm, "data", "APP_MODE") is not None, "le ConfigMap doit définir data: APP_MODE")
    dep = deployment(items, "app.yaml")
    check_deployment_basics(dep)
    c = containers(dep)[0]
    env = env_by_name(c)
    ref = get(env.get("APP_MODE", {}), "valueFrom", "configMapKeyRef")
    need(isinstance(ref, dict) and ref.get("name") == get(cm, "metadata", "name") and ref.get("key") == "APP_MODE",
         "APP_MODE doit venir du ConfigMap : valueFrom: configMapKeyRef avec name et key")
    pw = env.get("DB_PASSWORD")
    need(pw is not None, "ajoutez la variable DB_PASSWORD")
    need("value" not in pw, "DB_PASSWORD ne doit pas avoir de valeur en clair dans le manifeste : valueFrom: secretKeyRef")
    sref = get(pw, "valueFrom", "secretKeyRef")
    need(isinstance(sref, dict) and sref.get("name") and sref.get("key"), "DB_PASSWORD : valueFrom: secretKeyRef avec name et key")
    for s in of_kind(items, "Secret"):
        need(not s.get("stringData") and not s.get("data"), "ne versionnez jamais un Secret avec ses valeurs : créez-le hors du dépôt")
    svc = one(items, "Service", "app.yaml")
    need(svc["apiVersion"] == "v1", "un Service utilise apiVersion: v1")
    sel = get(svc, "spec", "selector")
    labels = pod_labels(dep)
    need(isinstance(sel, dict) and sel and all(labels.get(k) == v for k, v in sel.items()),
         "le sélecteur du Service doit correspondre aux étiquettes des pods, sinon il ne route vers rien")
    ports = get(svc, "spec", "ports") or []
    need(any(isinstance(p, dict) and p.get("port") == 80 and p.get("targetPort") in (8000, "8000", "http") for p in ports),
         "le Service expose le port 80 vers le port 8000 du conteneur : port: 80 et targetPort: 8000")
    need(get(svc, "spec", "type", default="ClusterIP") == "ClusterIP", "un service interne reste de type ClusterIP (pas NodePort ni LoadBalancer)")
    probe_ok(c, "readinessProbe")
    probe_ok(c, "livenessProbe")
    delay = get(c, "livenessProbe", "initialDelaySeconds")
    need(isinstance(delay, int) and delay >= 5, "livenessProbe.initialDelaySeconds doit valoir au moins 5 : sinon Kubernetes tue une application encore en démarrage")


# ---- k3 : durcissement ----

def check_k3() -> None:
    dep = deployment(docs("deployment.yaml"), "deployment.yaml")
    check_deployment_basics(dep)
    spec = get(dep, "spec", "template", "spec")
    for flag in ("hostNetwork", "hostPID", "hostIPC"):
        need(spec.get(flag) is not True, f"{flag}: true casse l'isolation du pod : retirez-le")
    need(not any(isinstance(v, dict) and "hostPath" in v for v in spec.get("volumes") or []),
         "un volume hostPath donne accès au disque du nœud : utilisez emptyDir ou un volume persistant")
    need(get(spec, "securityContext", "runAsNonRoot") is True, "ajoutez securityContext: runAsNonRoot: true au niveau du pod")
    need(spec.get("automountServiceAccountToken") is False,
         "ajoutez automountServiceAccountToken: false : l'application n'a pas besoin de parler à l'API Kubernetes")
    for c in containers(dep):
        sc = c.get("securityContext") or {}
        need(sc.get("privileged") is not True, f"le conteneur {c['name']} ne doit pas être privileged")
        need(sc.get("allowPrivilegeEscalation") is False, "securityContext: allowPrivilegeEscalation: false")
        need(sc.get("readOnlyRootFilesystem") is True, "securityContext: readOnlyRootFilesystem: true")
        drop = get(sc, "capabilities", "drop") or []
        need("ALL" in drop, "securityContext: capabilities: drop: [\"ALL\"]")
    pols = of_kind(docs("networkpolicy.yaml"), "NetworkPolicy")
    need(pols, "networkpolicy.yaml doit contenir des NetworkPolicy")
    deny = [p for p in pols if get(p, "spec", "podSelector") == {} and "Ingress" in (get(p, "spec", "policyTypes") or [])
            and not get(p, "spec", "ingress")]
    need(deny, "ajoutez une politique « tout refuser » : podSelector: {}, policyTypes: [Ingress] et aucune règle ingress")
    labels = pod_labels(dep)
    allow = []
    for p in pols:
        if p in deny:
            continue
        sel = get(p, "spec", "podSelector", "matchLabels")
        if isinstance(sel, dict) and sel and all(labels.get(k) == v for k, v in sel.items()):
            allow.append(p)
    need(allow, "ajoutez une politique qui autorise l'accès aux pods de l'application (podSelector.matchLabels = leurs étiquettes)")
    ok = False
    for p in allow:
        for rule in get(p, "spec", "ingress") or []:
            frm = rule.get("from") if isinstance(rule, dict) else None
            ports = rule.get("ports") if isinstance(rule, dict) else None
            if (isinstance(frm, list) and frm and all(isinstance(f, dict) and labelled(get(f, "podSelector", "matchLabels")) for f in frm)
                    and isinstance(ports, list) and any(isinstance(q, dict) and q.get("port") in (8000, "8000") for q in ports)):
                ok = True
    need(ok, "la politique d'autorisation doit nommer qui peut entrer (from: podSelector.matchLabels) et sur quel port (8000), pas « tout le monde »")


CHECKS = {
    "k1": (check_k1, "Deployment redondant, borné et bien étiqueté."),
    "k2": (check_k2, "service, configuration, secret et sondes en place."),
    "k3": (check_k3, "pod durci et réseau fermé par défaut."),
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
        print(f"ECHEC : manifeste inattendu ({type(e).__name__}) : vérifiez l'indentation et la forme des blocs")
        return 1
    print(f"OK : {success}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
