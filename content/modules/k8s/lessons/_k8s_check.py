#!/usr/bin/env python3
"""Vérifications des TP du module Kubernetes.

Analyse statique, en lecture seule, des manifestes de l'apprenant : aucun cluster, aucun réseau.
Lancer avec `python3 -I -B`. Usage : _k8s_check.py <k1..k7|boss1..boss3> [dossier] (le répertoire courant est le dossier du TP).
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


# ---- k4 : StatefulSet, stockage, CronJob ----

UNITS = {"Ki": 2**10, "Mi": 2**20, "Gi": 2**30, "Ti": 2**40, "k": 10**3, "K": 10**3, "M": 10**6, "G": 10**9, "T": 10**12}


def mem_bytes(q) -> float | None:
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([KMGT]i?|k)?", str(q).strip())
    return float(m.group(1)) * UNITS.get(m.group(2) or "", 1) if m else None


def check_k4() -> None:
    items = docs("db.yaml")
    need(not of_kind(items, "Deployment"), "une base de données ne tourne pas dans un Deployment : remplacez-le par un StatefulSet")
    sts = one(items, "StatefulSet", "db.yaml")
    need(sts["apiVersion"] == "apps/v1", "un StatefulSet utilise apiVersion: apps/v1")
    spec = sts.get("spec") or {}
    sel = get(spec, "selector", "matchLabels")
    labels = pod_labels(sts)
    need(isinstance(sel, dict) and sel and all(labels.get(k) == v for k, v in sel.items()),
         "le sélecteur du StatefulSet doit correspondre aux étiquettes de son modèle de pod")
    tpl = get(spec, "template", "spec") or {}
    need(not any(isinstance(v, dict) and "emptyDir" in v for v in tpl.get("volumes") or []),
         "le volume emptyDir disparaît avec le pod : les données doivent venir de volumeClaimTemplates")
    vcts = spec.get("volumeClaimTemplates")
    need(isinstance(vcts, list) and vcts, "ajoutez volumeClaimTemplates : chaque pod reçoit son propre disque persistant")
    names = set()
    for v in vcts:
        names.add(get(v, "metadata", "name"))
        need("ReadWriteOnce" in (get(v, "spec", "accessModes") or []), "le modèle de volume demande accessModes: [\"ReadWriteOnce\"]")
        need(get(v, "spec", "resources", "requests", "storage"), "le modèle de volume demande une taille : resources.requests.storage")
    c = containers(sts)[0]
    assert_pinned(c.get("image"))
    mounts = {m.get("name"): m.get("mountPath") for m in c.get("volumeMounts") or [] if isinstance(m, dict)}
    need(any(n in names and mounts.get(n) == "/var/lib/postgresql/data" for n in mounts),
         "le conteneur monte le volume du modèle (même name) sur /var/lib/postgresql/data")
    pw = env_by_name(c).get("POSTGRES_PASSWORD") or {}
    need("value" not in pw and isinstance(get(pw, "valueFrom", "secretKeyRef"), dict),
         "POSTGRES_PASSWORD vient d'un Secret : valueFrom: secretKeyRef, jamais de value en clair")
    svc_name = spec.get("serviceName")
    need(svc_name, "le StatefulSet a besoin de serviceName (son Service headless)")
    svcs = [x for x in of_kind(items, "Service") if get(x, "metadata", "name") == svc_name]
    need(svcs, f"ajoutez le Service {svc_name} désigné par serviceName")
    svc = svcs[0]
    need(get(svc, "spec", "clusterIP") == "None", f"le Service {svc_name} est headless : clusterIP: None")
    ssel = get(svc, "spec", "selector")
    need(isinstance(ssel, dict) and ssel and all(labels.get(k) == v for k, v in ssel.items()),
         f"le sélecteur du Service {svc_name} doit correspondre aux pods de la base")
    cj = one(items, "CronJob", "db.yaml")
    need(cj["apiVersion"] == "batch/v1", "un CronJob utilise apiVersion: batch/v1")
    sched = str(get(cj, "spec", "schedule", default=""))
    need(re.fullmatch(r"(\S+\s+){4}\S+", sched.strip()) and all(re.fullmatch(r"[\d*/,-]+", f) for f in sched.split()),
         "schedule doit être une expression cron à 5 champs, par exemple \"0 3 * * *\"")
    need(get(cj, "spec", "concurrencyPolicy") == "Forbid", "concurrencyPolicy: Forbid : deux sauvegardes ne doivent pas se chevaucher")
    js = get(cj, "spec", "jobTemplate", "spec") or {}
    bl = js.get("backoffLimit")
    need(isinstance(bl, int) and 0 <= bl <= 5, "jobTemplate.spec.backoffLimit (5 au plus) borne les nouvelles tentatives")
    ad = js.get("activeDeadlineSeconds")
    need(isinstance(ad, int) and ad > 0, "jobTemplate.spec.activeDeadlineSeconds : une sauvegarde bloquée doit être tuée")
    need(get(js, "template", "spec", "restartPolicy") in ("OnFailure", "Never"), "le pod d'un Job utilise restartPolicy: OnFailure ou Never, jamais Always")


# ---- k5 : Ingress, rollout, HPA, PDB ----

def selects(sel, labels: dict) -> bool:
    return isinstance(sel, dict) and bool(sel) and all(labels.get(k) == v for k, v in sel.items())


def check_web(name: str = "web.yaml") -> None:
    items = docs(name)
    dep = deployment(items, name)
    labels = pod_labels(dep)
    need(selects(get(dep, "spec", "selector", "matchLabels"), labels), f"{name} : le sélecteur du Deployment doit correspondre à ses pods")
    c = containers(dep)[0]
    assert_pinned(c.get("image"))
    need(get(c, "resources", "requests", "cpu") is not None, f"{name} : resources.requests.cpu est indispensable : l'HPA calcule son pourcentage dessus")
    probe_ok(c, "readinessProbe")
    ru = get(dep, "spec", "strategy", "rollingUpdate") or {}
    need(get(dep, "spec", "strategy", "type", default="RollingUpdate") == "RollingUpdate", f"{name} : strategy.type: RollingUpdate")
    need(ru.get("maxUnavailable") in (0, "0", "0%"), f"{name} : rollingUpdate.maxUnavailable: 0, on ne retire aucun pod avant que le nouveau soit prêt")
    need(ru.get("maxSurge") not in (None, 0, "0", "0%"), f"{name} : rollingUpdate.maxSurge d'au moins 1, sinon la mise à jour ne peut pas avancer")
    svc = one(items, "Service", name)
    need(selects(get(svc, "spec", "selector"), labels), f"{name} : le sélecteur du Service doit correspondre aux pods")
    need(get(svc, "spec", "type", default="ClusterIP") == "ClusterIP", f"{name} : derrière un Ingress, le Service reste ClusterIP (pas de LoadBalancer payant)")
    svc_name = get(svc, "metadata", "name")
    svc_ports = {p.get("port") for p in get(svc, "spec", "ports") or [] if isinstance(p, dict)}
    ing = one(items, "Ingress", name)
    need(ing["apiVersion"] == "networking.k8s.io/v1", f"{name} : un Ingress utilise apiVersion: networking.k8s.io/v1")
    need(get(ing, "spec", "ingressClassName"), f"{name} : ingressClassName choisit le contrôleur d'Ingress (nginx, traefik)")
    rules = get(ing, "spec", "rules") or []
    hosts = [r.get("host") for r in rules if isinstance(r, dict) and r.get("host")]
    need(hosts, f"{name} : chaque règle d'Ingress nomme son host")
    ok = False
    for r in rules:
        for pth in get(r, "http", "paths") or []:
            b = get(pth, "backend", "service") or {}
            need(pth.get("pathType") in ("Prefix", "Exact", "ImplementationSpecific"), f"{name} : chaque chemin déclare pathType: Prefix")
            if b.get("name") == svc_name and get(b, "port", "number") in svc_ports:
                ok = True
    need(ok, f"{name} : l'Ingress envoie vers le Service {svc_name} et l'un de ses ports (backend.service.port.number)")
    tls = get(ing, "spec", "tls") or []
    need(any(isinstance(t, dict) and t.get("secretName") and set(hosts) <= set(t.get("hosts") or []) for t in tls),
         f"{name} : terminez le TLS : spec.tls avec secretName et les mêmes hosts")
    hpa = one(items, "HorizontalPodAutoscaler", name)
    need(hpa["apiVersion"] == "autoscaling/v2", f"{name} : l'HPA utilise apiVersion: autoscaling/v2")
    ref = get(hpa, "spec", "scaleTargetRef") or {}
    need(ref.get("kind") == "Deployment" and ref.get("name") == get(dep, "metadata", "name"), f"{name} : scaleTargetRef désigne le Deployment")
    mn, mx = get(hpa, "spec", "minReplicas"), get(hpa, "spec", "maxReplicas")
    need(isinstance(mn, int) and mn >= 2, f"{name} : minReplicas d'au moins 2, un seul pod tombe avec son nœud")
    need(isinstance(mx, int) and mx > mn, f"{name} : maxReplicas doit dépasser minReplicas")
    util = [get(m, "resource", "target", "averageUtilization") for m in get(hpa, "spec", "metrics") or []
            if isinstance(m, dict) and get(m, "resource", "name") == "cpu"]
    need(util and isinstance(util[0], int) and 30 <= util[0] <= 90, f"{name} : une métrique cpu avec averageUtilization entre 30 et 90")
    need(get(dep, "spec", "replicas") is None, f"{name} : retirez spec.replicas du Deployment : l'HPA décide, sinon chaque apply écrase sa décision")
    pdb = one(items, "PodDisruptionBudget", name)
    need(pdb["apiVersion"] == "policy/v1", f"{name} : un PodDisruptionBudget utilise apiVersion: policy/v1")
    need(get(pdb, "spec", "minAvailable") is not None or get(pdb, "spec", "maxUnavailable") is not None,
         f"{name} : le PodDisruptionBudget fixe minAvailable (ou maxUnavailable)")
    need(selects(get(pdb, "spec", "selector", "matchLabels"), labels), f"{name} : le sélecteur du PodDisruptionBudget doit viser les pods, sinon il ne protège rien")


def check_k5() -> None:
    check_web("web.yaml")


# ---- k6 : dépannage ----

CAUSES = {"api": "image", "worker": "application", "batch": "planification", "cache": "memoire", "front": "selecteur"}
REGISTRY_TAGS = {"1.26.3", "1.27.0", "1.27.1"}


def check_k6() -> None:
    diag = docs_plain("diagnostic.yaml")
    for comp, cause in CAUSES.items():
        got = str(diag.get(comp, "?")).strip().lower()
        need(got != "?", f"diagnostic.yaml : donnez une cause pour {comp}")
        need(got == cause, f"diagnostic.yaml : la cause de {comp} n'est pas la bonne, relisez les Events et les journaux de ce composant")
    items = docs("manifests.yaml")
    deps = {get(d, "metadata", "name"): d for d in of_kind(items, "Deployment")}
    need(set(CAUSES) <= set(deps), "manifests.yaml doit garder les cinq Deployments")
    img = containers(deps["api"])[0].get("image", "")
    need(img.rsplit(":", 1)[-1] in REGISTRY_TAGS, "api : l'image doit utiliser un tag qui existe dans le registre (voir incidents/02-api.txt)")
    w = env_by_name(containers(deps["worker"])[0]).get("DATABASE_URL") or {}
    ref = get(w, "valueFrom", "secretKeyRef") or {}
    need(ref.get("name") == "worker-db" and ref.get("key") == "url",
         "worker : ajoutez DATABASE_URL depuis le Secret worker-db, clé url (valueFrom: secretKeyRef)")
    breq = mem_bytes(get(containers(deps["batch"])[0], "resources", "requests", "memory"))
    need(breq is not None and breq <= 4 * 2**30, "batch : la demande de mémoire dépasse ce qu'un nœud peut offrir (7944Mi) : 4Gi au plus")
    cres = get(containers(deps["cache"])[0], "resources") or {}
    lim, req = mem_bytes(get(cres, "limits", "memory")), mem_bytes(get(cres, "requests", "memory"))
    need(lim is not None and lim >= 128 * 2**20, "cache : limits.memory est trop basse, le conteneur est tué (OOMKilled) : 128Mi au moins")
    need(req is not None and req <= lim, "cache : requests.memory ne peut pas dépasser limits.memory")
    front = [x for x in of_kind(items, "Service") if get(x, "metadata", "name") == "front"]
    need(front, "manifests.yaml doit garder le Service front")
    need(selects(get(front[0], "spec", "selector"), pod_labels(deps["front"])),
         "front : le sélecteur du Service ne correspond toujours pas aux étiquettes des pods front")


def docs_plain(name: str) -> dict:
    need(os.path.isfile(name) and not os.path.islink(name), f"{name} est introuvable")
    with open(name, encoding="utf-8") as f:
        text = f.read(MAX_BYTES + 1)
    try:
        d = load_all(text)
    except YamlError as e:
        raise CheckError(f"{name} n'est pas un YAML valide : {e}") from None
    need(len(d) == 1 and isinstance(d[0], dict), f"{name} : une correspondance composant: cause est attendue")
    return d[0]


# ---- k7 : Kustomize et RBAC ----

def check_k7(prefix: str = "") -> None:
    base = docs(prefix + "base/kustomization.yaml")
    need(len(base) == 1 and base[0].get("kind") == "Kustomization", "base/kustomization.yaml : un document kind: Kustomization")
    res = base[0].get("resources") or []
    need({"deployment.yaml", "service.yaml"} <= set(res), "base/kustomization.yaml : resources liste deployment.yaml et service.yaml")
    for r in res:
        need(os.path.isfile(os.path.join(prefix + "base", r)), f"base/kustomization.yaml : la ressource {r} n'existe pas")
    ov = docs(prefix + "overlays/prod/kustomization.yaml")
    need(len(ov) == 1 and ov[0].get("kind") == "Kustomization", "overlays/prod/kustomization.yaml : un document kind: Kustomization")
    ov = ov[0]
    need(ov.get("namespace") == "prod", "overlay prod : namespace: prod")
    need(any(str(r).rstrip("/") == "../../base" for r in ov.get("resources") or []), "overlay prod : resources: [../../base]")
    imgs = [i for i in ov.get("images") or [] if isinstance(i, dict) and i.get("name") == "registry.example.test/web"]
    need(imgs and imgs[0].get("newTag"), "overlay prod : images: fixe newTag pour registry.example.test/web")
    need(str(imgs[0]["newTag"]).lower() != "latest", "overlay prod : jamais latest en production, un tag précis")
    reps = [r for r in ov.get("replicas") or [] if isinstance(r, dict) and r.get("name") == "web"]
    need(reps and isinstance(reps[0].get("count"), int) and reps[0]["count"] >= 3, "overlay prod : replicas: - name: web, count: 3 au moins")
    items = docs(prefix + "rbac.yaml")
    for b in of_kind(items, "ClusterRoleBinding") + of_kind(items, "RoleBinding"):
        need(get(b, "roleRef", "name") != "cluster-admin", "rbac.yaml : ne liez jamais cluster-admin au compte de déploiement")
    need(not of_kind(items, "ClusterRoleBinding"), "rbac.yaml : le déployeur n'a besoin que du namespace prod : RoleBinding, pas ClusterRoleBinding")
    sa = [x for x in of_kind(items, "ServiceAccount") if get(x, "metadata", "name") == "deployer"]
    need(sa and get(sa[0], "metadata", "namespace") == "prod", "rbac.yaml : ServiceAccount deployer dans le namespace prod")
    roles = {get(r, "metadata", "name"): r for r in of_kind(items, "Role")}
    need(roles, "rbac.yaml : ajoutez un Role (droits limités au namespace)")
    for rn, r in roles.items():
        need(get(r, "metadata", "namespace") == "prod", f"rbac.yaml : le Role {rn} est dans le namespace prod")
        rules = r.get("rules") or []
        need(rules, f"rbac.yaml : le Role {rn} liste ses rules")
        for rule in rules:
            for key in ("apiGroups", "resources", "verbs"):
                need("*" not in (rule.get(key) or []), f"rbac.yaml : pas de \"*\" dans {key} : listez les droits un par un")
            need("secrets" not in (rule.get("resources") or []), "rbac.yaml : le déployeur n'a pas à lire les secrets")
            need(not set(rule.get("verbs") or []) & {"delete", "deletecollection", "escalate", "bind", "impersonate"},
                 "rbac.yaml : le déployeur met à jour, il ne supprime pas et n'élève pas ses droits")
    ok = False
    for b in of_kind(items, "RoleBinding"):
        ref = b.get("roleRef") or {}
        subj = [x for x in b.get("subjects") or [] if isinstance(x, dict)]
        if ref.get("kind") == "Role" and ref.get("name") in roles and any(
                x.get("kind") == "ServiceAccount" and x.get("name") == "deployer" and x.get("namespace") == "prod" for x in subj):
            need(get(b, "metadata", "namespace") == "prod", "rbac.yaml : le RoleBinding est dans le namespace prod")
            ok = True
    need(ok, "rbac.yaml : un RoleBinding donne le Role au ServiceAccount deployer (subjects avec namespace: prod)")
    rules = [rule for r in roles.values() for rule in r.get("rules") or []]
    need(any("apps" in (x.get("apiGroups") or []) and "deployments" in (x.get("resources") or []) and
             {"update", "patch"} & set(x.get("verbs") or []) for x in rules),
         "rbac.yaml : le Role permet de mettre à jour les deployments (apiGroups: [apps], verbs: update ou patch)")


# ---- boss : cumulatif, dans k8sboss/ ----


CHECKS = {
    "k1": ([check_k1], "Deployment redondant, borné et bien étiqueté."),
    "k2": ([check_k2], "service, configuration, secret et sondes en place."),
    "k3": ([check_k3], "pod durci et réseau fermé par défaut."),
    "k4": ([check_k4], "base de données persistante et sauvegarde planifiée sans chevauchement."),
    "k5": ([check_k5], "exposée en TLS, mise à jour sans coupure, autoscaling et budget de perturbation."),
    "k6": ([check_k6], "cinq incidents diagnostiqués et corrigés dans les manifestes."),
    "k7": ([check_k7], "overlay de production et droits de déploiement minimaux."),
    # le boss est cumulatif : une phase ultérieure revérifie les précédentes
    "boss1": ([check_k2], "phase 1 : l'application est configurée, exposée et sondée."),
    "boss2": ([check_k2, check_k5], "phase 2 : trafic TLS, zéro coupure et autoscaling."),
    "boss3": ([check_k2, check_k5, check_k7], "phase 3 : livraison par environnement et droits minimaux."),
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
        print(f"ECHEC : manifeste inattendu ({type(e).__name__}) : vérifiez l'indentation et la forme des blocs")
        return 1
    print(f"OK : {success}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
