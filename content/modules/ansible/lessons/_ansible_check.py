#!/usr/bin/env python3
"""Vérifications des TP du module Ansible.

Analyse statique, en lecture seule, de l'inventaire, des playbooks et des rôles de l'apprenant :
aucune connexion SSH, aucun binaire ansible. Lancer avec `python3 -I -B`.
Usage : _ansible_check.py <an1..an6|boss1..boss3> [dossier] (le répertoire courant est le dossier du TP).
"""
from __future__ import annotations

import configparser
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I retire le dossier du script du chemin
from _yaml import YamlError, load  # noqa: E402

MAX_BYTES = 200_000
TASK_KEYS = {
    "name", "when", "loop", "loop_control", "with_items", "with_dict", "with_list", "register", "notify", "become",
    "become_user", "become_method", "tags", "changed_when", "failed_when", "args", "delegate_to", "no_log", "until",
    "retries", "delay", "vars", "ignore_errors", "environment", "block", "rescue", "always", "run_once", "check_mode",
    "listen", "any_errors_fatal", "throttle", "timeout", "diff", "local_action", "async", "poll",
}
SECRET_KEY = re.compile(r"(pass(word|wd)?|secret|token|api[_-]?key|private[_-]?key)", re.I)
JINJA_VAR = re.compile(r"\{\{\s*([A-Za-z_]\w*)")
BUILTIN_VARS = {"item", "inventory_hostname", "groups", "group_names", "hostvars", "ansible_host", "playbook_dir",
                "role_path", "omit", "lookup", "query"}


class CheckError(Exception):
    """Erreur affichée à l'apprenant."""


def need(condition, message: str) -> None:
    if not condition:
        raise CheckError(message)


def read(path: str) -> str:
    need(os.path.isfile(path) and not os.path.islink(path), f"{path} est introuvable")
    with open(path, encoding="utf-8") as f:
        text = f.read(MAX_BYTES + 1)
    need(len(text) <= MAX_BYTES, f"{path} est trop gros")
    return text


def yaml_file(path: str):
    try:
        return load(read(path))
    except YamlError as e:
        raise CheckError(f"{path} n'est pas un YAML valide : {e} (une valeur qui commence par {{{{ doit être entre guillemets)") from None


def var_file(path: str) -> dict:
    d = yaml_file(path)
    need(isinstance(d, dict), f"{path} doit être une correspondance nom: valeur")
    return d


def playbook(path: str) -> list[dict]:
    plays = yaml_file(path)
    need(isinstance(plays, list) and plays and all(isinstance(p, dict) for p in plays),
         f"{path} : un playbook est une liste de plays (chaque play commence par « - name: »)")
    for p in plays:
        need(p.get("hosts"), f"{path} : chaque play indique ses hosts")
    return plays


def task_list(tasks, where: str) -> list[dict]:
    need(tasks is None or isinstance(tasks, list), f"{where} doit être une liste de tâches")
    out = []
    for t in tasks or []:
        need(isinstance(t, dict), f"{where} : chaque tâche est de la forme « - name: ... »")
        out.append(t)
        for sub in ("block", "rescue", "always"):
            if sub in t:
                out += task_list(t[sub], where)
    return out


def play_tasks(play: dict, sections=("pre_tasks", "tasks", "post_tasks", "handlers")) -> list[dict]:
    return [t for s in sections for t in task_list(play.get(s), s)]


def module_of(task: dict) -> str:
    mods = [k for k in task if k not in TASK_KEYS]
    if "block" in task:
        return "block"
    need(len(mods) == 1, f"la tâche « {task.get('name', '?')} » doit appeler un seul module (trouvé : {', '.join(mods) or 'aucun'})")
    return mods[0]


def short(mod: str) -> str:
    return mod.rsplit(".", 1)[-1]


def args_of(task: dict) -> dict:
    a = task.get(module_of(task))
    return a if isinstance(a, dict) else {}


def check_task_style(tasks: list[dict], where: str) -> None:
    for t in tasks:
        if "block" in t:
            continue
        need(isinstance(t.get("name"), str) and t["name"].strip(), f"{where} : chaque tâche a un name (c'est ce qu'on lit dans la sortie)")
        mod = module_of(t)
        need("." in mod, f"{where} : « {t['name']} » : écrivez le nom complet du module (ansible.builtin.{mod})")


def check_idempotent_commands(tasks: list[dict], where: str) -> None:
    for t in tasks:
        if "block" in t:
            continue
        mod = short(module_of(t))
        if mod not in ("shell", "command", "raw"):
            continue
        cmd = t[module_of(t)] if isinstance(t[module_of(t)], str) else str(args_of(t).get("cmd", ""))
        need(not re.search(r"\b(apt-get|apt|yum|dnf|systemctl|service|useradd)\b", cmd),
             f"{where} : « {t.get('name')} » : un module sait le faire (apt, service, user) : n'utilisez pas {mod}")
        need(not re.search(r"(^|[^>])>\s*/", cmd), f"{where} : « {t.get('name')} » : pour écrire un fichier, utilisez copy ou template, pas une redirection")
        a = t.get("args") if isinstance(t.get("args"), dict) else {}
        need("changed_when" in t or "creates" in a or "removes" in a or "creates" in args_of(t),
             f"{where} : « {t.get('name')} » : une commande est toujours « changed » : ajoutez changed_when (false pour une lecture) ou creates")


def check_file_modes(tasks: list[dict], where: str) -> None:
    for t in tasks:
        if "block" in t or short(module_of(t)) not in ("copy", "template"):
            continue
        a = args_of(t)
        for k in ("owner", "group", "mode"):
            need(a.get(k) is not None, f"{where} : « {t.get('name')} » : précisez {k} (sinon les droits dépendent de la machine)")
        need(isinstance(a["mode"], str) and re.fullmatch(r"0[0-7]{3}|[ugoa]+[=+-][rwx,ugoa=+-]*", a["mode"]),
             f"{where} : « {t.get('name')} » : mode entre guillemets, par exemple mode: \"0644\" (sans guillemets, 0644 devient le nombre 644)")


def notified(tasks: list[dict]) -> set[str]:
    out = set()
    for t in tasks:
        n = t.get("notify")
        out |= set(n) if isinstance(n, list) else {n} if isinstance(n, str) else set()
    return out


def check_handlers(tasks: list[dict], handlers: list[dict], where: str) -> None:
    names = {h.get("name") for h in handlers} | {h.get("listen") for h in handlers if h.get("listen")}
    for n in notified(tasks):
        need(n in names, f"{where} : notify « {n} » ne correspond au name d'aucun handler (majuscules comprises)")


def inventory(path: str = "inventory.ini") -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, dict], dict[str, dict]]:
    """Inventaire INI : (hôtes par groupe, enfants par groupe, variables d'hôte, variables de groupe)."""
    hosts: dict[str, set[str]] = {}
    children: dict[str, set[str]] = {}
    hvars: dict[str, dict] = {}
    gvars: dict[str, dict] = {}
    section = ("ungrouped", "")
    for n, raw in enumerate(read(path).splitlines(), 1):
        line = raw.split("#", 1)[0].split(";", 1)[0].strip() if not raw.lstrip().startswith(("#", ";")) else ""
        if not line:
            continue
        m = re.fullmatch(r"\[([A-Za-z0-9_-]+)(?::(children|vars))?\]", line)
        if m:
            section = (m.group(1), m.group(2) or "")
            continue
        need(not line.startswith("["), f"{path} ligne {n} : en-tête de groupe invalide {line!r}")
        g, kind = section
        if kind == "vars":
            need("=" in line, f"{path} ligne {n} : dans [{g}:vars], une ligne est cle=valeur")
            k, v = line.split("=", 1)
            gvars.setdefault(g, {})[k.strip()] = v.strip()
        elif kind == "children":
            children.setdefault(g, set()).add(line.split()[0])
        else:
            parts = line.split()
            hosts.setdefault(g, set()).add(parts[0])
            for kv in parts[1:]:
                need("=" in kv, f"{path} ligne {n} : variable d'hôte attendue sous la forme cle=valeur ({kv!r})")
                k, v = kv.split("=", 1)
                hvars.setdefault(parts[0], {})[k] = v
    return hosts, children, hvars, gvars


def no_password_in_inventory(hvars: dict, gvars: dict, path: str = "inventory.ini") -> None:
    for scope in list(hvars.values()) + list(gvars.values()):
        for k in scope:
            need(not re.search(r"(password|ssh_pass|become_pass)", k), f"{path} : {k} en clair dans l'inventaire : utilisez des clés SSH (et Vault si besoin)")


def used_vars(text: str) -> set[str]:
    return set(JINJA_VAR.findall(text))


def yml_files(root: str = "."):
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if not x.startswith(".") or x == ".github"]
        for f in files:
            if f.endswith((".yml", ".yaml")):
                yield os.path.join(d, f)


def scan_plain_secrets(data, path: str, key: str = "") -> None:
    if isinstance(data, dict):
        for k, v in data.items():
            scan_plain_secrets(v, path, str(k))
    elif isinstance(data, list):
        for v in data:
            scan_plain_secrets(v, path, key)
    elif isinstance(data, str) and key and SECRET_KEY.search(key) and not key.startswith("vault_"):
        need("{{" in data or data == "", f"{path} : {key} contient un secret en clair : rangez-le chiffré (vault_{key} dans vault.yml) et référencez-le")


# ---- an1 : inventaire et premier playbook ----

def check_an1() -> None:
    hosts, children, hvars, gvars = inventory()
    no_password_in_inventory(hvars, gvars)
    need(hosts.get("web") == {"web1", "web2"}, "inventory.ini : le groupe [web] contient web1 et web2")
    need(hosts.get("db") == {"db1"}, "inventory.ini : le groupe [db] contient db1")
    need(not hosts.get("ungrouped"), "inventory.ini : chaque hôte est rangé sous un groupe [web] ou [db]")
    for h in ("web1", "web2", "db1"):
        need(hvars.get(h, {}).get("ansible_host"), f"inventory.ini : {h} garde son ansible_host")
    need(children.get("prod") == {"web", "db"}, "inventory.ini : [prod:children] regroupe web et db")
    need(gvars.get("all", {}).get("ansible_user") == "deploy", "inventory.ini : [all:vars] avec ansible_user=deploy")
    plays = playbook("site.yml")
    web = [p for p in plays if p.get("hosts") == "web"]
    need(web, "site.yml : un play vise hosts: web")
    p = web[0]
    need(isinstance(p.get("name"), str) and p["name"].strip(), "site.yml : le play a un name")
    need(p.get("become") is True, "site.yml : installer des paquets demande become: true")
    tasks = play_tasks(p)
    need(tasks, "site.yml : le play liste des tasks")
    check_task_style(tasks, "site.yml")
    check_idempotent_commands(tasks, "site.yml")
    pkg = [t for t in tasks if short(module_of(t)) in ("apt", "package") and "nginx" in str(args_of(t).get("name"))]
    need(pkg and args_of(pkg[0]).get("state") == "present", "site.yml : installez nginx avec ansible.builtin.apt (name: nginx, state: present)")
    svc = [t for t in tasks if short(module_of(t)) in ("service", "systemd_service", "systemd") and args_of(t).get("name") == "nginx"]
    need(svc and args_of(svc[0]).get("state") == "started" and args_of(svc[0]).get("enabled") is True,
         "site.yml : ansible.builtin.service avec name: nginx, state: started et enabled: true")


# ---- an2 : idempotence, handlers, variables ----

def check_an2() -> None:
    gv = var_file(os.path.join("group_vars", "web.yml"))
    need("nginx_port" in gv, "group_vars/web.yml : définissez nginx_port (les valeurs vivent par groupe)")
    p = [x for x in playbook("site.yml") if x.get("hosts") == "web"]
    need(p, "site.yml : un play vise hosts: web")
    p = p[0]
    need("nginx_port" not in (p.get("vars") or {}), "site.yml : retirez nginx_port de vars: du play, il vient de group_vars/web.yml")
    tasks = play_tasks(p, ("pre_tasks", "tasks", "post_tasks"))
    handlers = play_tasks(p, ("handlers",))
    check_task_style(tasks + handlers, "site.yml")
    check_idempotent_commands(tasks, "site.yml")
    check_file_modes(tasks, "site.yml")
    for t in tasks:
        need(str(args_of(t).get("state", "")) not in ("restarted", "reloaded"),
             f"site.yml : « {t.get('name')} » redémarre à chaque lancement : faites-en un handler notifié")
    conf = [t for t in tasks if short(module_of(t)) in ("copy", "template") and args_of(t).get("dest") == "/etc/nginx/conf.d/app.conf"]
    need(conf, "site.yml : déposez /etc/nginx/conf.d/app.conf avec ansible.builtin.copy (ou template)")
    need(conf[0].get("notify"), "site.yml : la tâche de configuration notifie le handler (notify:)")
    need(handlers, "site.yml : ajoutez une section handlers:")
    check_handlers(tasks, handlers, "site.yml")
    need(any(short(module_of(h)) == "service" and args_of(h).get("state") in ("reloaded", "restarted") for h in handlers),
         "site.yml : le handler recharge nginx (ansible.builtin.service, state: reloaded)")
    for v in used_vars(read("site.yml")):
        need(v in gv or v in (p.get("vars") or {}) or v.startswith("ansible_") or v in BUILTIN_VARS,
             f"site.yml utilise {{{{ {v} }}}}, qui n'est défini ni dans group_vars/web.yml ni dans le play")


# ---- an3 : template, boucles, conditions ----

def check_template_file(path: str) -> None:
    text = read(path)
    need("{{ nginx_port }}" in re.sub(r"\{\{\s*(\w+)\s*\}\}", r"{{ \1 }}", text), f"{path} : utilisez {{{{ nginx_port }}}}")
    need(re.search(r"\{%-?\s*for\s+\w+\s+in\s+nginx_sites\s*-?%\}", text) and re.search(r"\{%-?\s*endfor\s*-?%\}", text),
         f"{path} : une boucle {{% for site in nginx_sites %}} ... {{% endfor %}}")
    need(re.search(r"\{\{\s*site\.domain\s*\}\}", text), f"{path} : chaque bloc server utilise {{{{ site.domain }}}}")
    need(re.search(r"#.*[Aa]nsible", text.splitlines()[0] if text else ""), f"{path} : première ligne : un commentaire « Géré par Ansible »")


def check_role_tasks(tasks: list[dict], where: str, template_dir: str) -> None:
    check_task_style(tasks, where)
    check_idempotent_commands(tasks, where)
    check_file_modes(tasks, where)
    for t in tasks:
        need("with_items" not in t, f"{where} : « {t.get('name')} » : remplacez with_items par loop")
    pk = [t for t in tasks if short(module_of(t)) in ("apt", "package")]
    need(pk, f"{where} : une tâche installe base_packages")
    need("loop" not in pk[0] and "base_packages" in str(args_of(pk[0]).get("name")),
         f"{where} : passez la liste entière au module, name: \"{{{{ base_packages }}}}\", sans boucle (une seule transaction apt)")
    when = str(pk[0].get("when", ""))
    need("ansible_os_family" in when and "{{" not in when, f"{where} : l'installation ne tourne que sur Debian : when: ansible_os_family == \"Debian\" (sans accolades)")
    us = [t for t in tasks if short(module_of(t)) == "user"]
    need(us and "admins" in str(us[0].get("loop", "")) and "item.name" in str(args_of(us[0]).get("name")),
         f"{where} : créez les comptes avec ansible.builtin.user et loop: \"{{{{ admins }}}}\" (name: \"{{{{ item.name }}}}\")")
    tp = [t for t in tasks if short(module_of(t)) == "template"]
    need(tp, f"{where} : nginx.conf est généré par ansible.builtin.template")
    a = args_of(tp[0])
    src = str(a.get("src", ""))
    need(src.endswith("nginx.conf.j2"), f"{where} : template src: nginx.conf.j2")
    check_template_file(os.path.join(template_dir, os.path.basename(src)))
    need("%s" in str(a.get("validate", "")), f"{where} : validate: nginx -t -c %s teste le fichier avant de le mettre en place")
    need(tp[0].get("notify"), f"{where} : le template notifie le rechargement de nginx")


def check_an3() -> None:
    var_file(os.path.join("group_vars", "web.yml"))
    p = [x for x in playbook("site.yml") if x.get("hosts") == "web"]
    need(p, "site.yml : un play vise hosts: web")
    tasks = play_tasks(p[0], ("pre_tasks", "tasks", "post_tasks"))
    check_role_tasks(tasks, "site.yml", "templates")
    check_handlers(tasks, play_tasks(p[0], ("handlers",)), "site.yml")


# ---- an4 : rôle ----

def check_an4() -> None:
    r = os.path.join("roles", "nginx")
    tasks = task_list(yaml_file(os.path.join(r, "tasks", "main.yml")), "roles/nginx/tasks/main.yml")
    need(tasks, "roles/nginx/tasks/main.yml : la liste des tâches du rôle (point d'entrée)")
    check_role_tasks(tasks, "roles/nginx/tasks/main.yml", os.path.join(r, "templates"))
    handlers = task_list(yaml_file(os.path.join(r, "handlers", "main.yml")), "roles/nginx/handlers/main.yml")
    check_handlers(tasks, handlers, "roles/nginx")
    defaults = var_file(os.path.join(r, "defaults", "main.yml"))
    need("nginx_port" in defaults, "roles/nginx/defaults/main.yml : nginx_port a une valeur par défaut")
    vpath = os.path.join(r, "vars", "main.yml")
    if os.path.exists(vpath):
        need("nginx_port" not in (var_file(vpath) or {}), "roles/nginx/vars/main.yml : nginx_port doit rester surchargeable : sa place est dans defaults/")
    meta = var_file(os.path.join(r, "meta", "main.yml"))
    need(isinstance(meta.get("galaxy_info"), dict) and meta["galaxy_info"].get("description"), "roles/nginx/meta/main.yml : galaxy_info avec une description")
    need(not os.path.exists(os.path.join("templates", "nginx.conf.j2")), "déplacez templates/nginx.conf.j2 dans roles/nginx/templates/")
    plays = [x for x in playbook("site.yml") if x.get("hosts") == "web"]
    need(plays, "site.yml : un play vise hosts: web")
    p = plays[0]
    roles = [x.get("role") if isinstance(x, dict) else x for x in p.get("roles") or []]
    need("nginx" in roles, "site.yml : le play applique le rôle (roles: - role: nginx)")
    need(not play_tasks(p), "site.yml : les tâches et handlers vivent dans le rôle, plus dans le playbook")
    req = var_file("requirements.yml")
    entries = [(kind, e) for kind in ("collections", "roles") for e in req.get(kind) or []]
    need(entries, "requirements.yml : listez les collections")
    for kind, e in entries:
        name = e.get("name") if isinstance(e, dict) else e
        need(isinstance(e, dict) and e.get("version"), f"requirements.yml : {name} sans version : épinglez-la (version: \"9.4.0\")")


# ---- an5 : vault ----

VAULT_HEADER = re.compile(r"\$ANSIBLE_VAULT;1\.[12];AES256(;[\w-]+)?")


def check_an5() -> None:
    vars_path = os.path.join("group_vars", "db", "vars.yml")
    vault_path = os.path.join("group_vars", "db", "vault.yml")
    vs = var_file(vars_path)
    need(str(vs.get("db_password", "")).replace(" ", "") == "{{vault_db_password}}",
         "group_vars/db/vars.yml : db_password: \"{{ vault_db_password }}\" (la valeur vient du coffre)")
    lines = read(vault_path).splitlines()
    need(lines and VAULT_HEADER.fullmatch(lines[0].strip()),
         "group_vars/db/vault.yml n'est pas chiffré : lancez ansible-vault encrypt group_vars/db/vault.yml")
    need(len(lines) > 1 and all(re.fullmatch(r"[0-9a-f]+", x.strip()) for x in lines[1:] if x.strip()),
         "group_vars/db/vault.yml : le contenu chiffré a été modifié à la main, rechiffrez-le")
    for f in yml_files():
        if os.path.abspath(f) != os.path.abspath(vault_path):
            scan_plain_secrets(yaml_file(f), f)
    plays = [x for x in playbook("db.yml") if x.get("hosts") == "db"]
    need(plays, "db.yml : un play vise hosts: db")
    p = plays[0]
    need(p.get("become") is not True, "db.yml : pas de become: true sur tout le play : mettez-le sur les tâches qui en ont besoin")
    tasks = play_tasks(p)
    check_task_style(tasks, "db.yml")
    need(any(t.get("become") is True for t in tasks), "db.yml : les tâches qui touchent au système portent become: true")
    for t in tasks:
        if "db_password" in str(t) or "vault_" in str(t):
            need(t.get("no_log") is True, f"db.yml : « {t.get('name')} » manipule un secret : ajoutez no_log: true")
    if os.path.exists("ansible.cfg"):
        cfg = configparser.ConfigParser(interpolation=None)
        try:
            cfg.read_string(read("ansible.cfg"))
        except configparser.Error as e:
            raise CheckError(f"ansible.cfg illisible : {e}") from None
        hk = cfg.get("defaults", "host_key_checking", fallback="True").strip().lower()
        need(hk not in ("false", "0", "no", "off"), "ansible.cfg : host_key_checking = False accepte n'importe quel serveur : retirez la ligne")
    ign = [x.strip() for x in read(".gitignore").splitlines()] if os.path.exists(".gitignore") else []
    need(any(x.lstrip("/") in (".vault_pass", ".vault_pass*", ".vault*", "*.vault_pass") for x in ign),
         ".gitignore : excluez le fichier de mot de passe du coffre (.vault_pass)")


# ---- an6 : déploiement progressif et CI ----

def check_an6() -> None:
    plays = [x for x in playbook("deploy.yml") if x.get("hosts") == "web"]
    need(plays, "deploy.yml : un play vise hosts: web")
    p = plays[0]
    s = p.get("serial")
    need(s is not None and s not in (0, "0", "100%"), "deploy.yml : serial: 1 (ou \"25%\") pour déployer par lots")
    need(p.get("max_fail_percentage") == 0, "deploy.yml : max_fail_percentage: 0, le premier échec arrête le déploiement")
    roles = [x.get("role") if isinstance(x, dict) else x for x in p.get("roles") or []]
    need("app" in roles, "deploy.yml : le play applique toujours le rôle app")
    pre, post = task_list(p.get("pre_tasks"), "pre_tasks"), task_list(p.get("post_tasks"), "post_tasks")
    check_task_style(pre + post, "deploy.yml")
    need(any(t.get("delegate_to") == "localhost" for t in pre), "deploy.yml : un pre_task retire l'hôte du répartiteur (delegate_to: localhost)")
    need(any(t.get("delegate_to") == "localhost" for t in post), "deploy.yml : un post_task remet l'hôte dans le répartiteur (delegate_to: localhost)")
    health = [t for t in post if short(module_of(t)) == "uri" and "until" in t]
    need(health and isinstance(health[0].get("retries"), int) and health[0]["retries"] > 0,
         "deploy.yml : un post_task vérifie la santé avec ansible.builtin.uri, register, until et retries")
    need(post.index(health[0]) < max(i for i, t in enumerate(post) if t.get("delegate_to") == "localhost"),
         "deploy.yml : vérifiez la santé AVANT de remettre l'hôte dans le répartiteur")
    wf = yaml_file(os.path.join(".github", "workflows", "ansible.yml"))
    need(isinstance(wf, dict) and isinstance(wf.get("jobs"), dict), ".github/workflows/ansible.yml : un workflow avec jobs:")
    on = wf.get("on")
    need("pull_request" in (on if isinstance(on, (dict, list)) else [on]), "workflow : déclenché sur pull_request")
    perm = wf.get("permissions")
    need(isinstance(perm, dict) and perm and all(v == "read" for v in perm.values()), "workflow : permissions: contents: read")
    runs = []
    for jid, job in wf["jobs"].items():
        need(isinstance(job, dict) and isinstance(job.get("timeout-minutes"), int) and 0 < job["timeout-minutes"] <= 30,
             f"workflow : timeout-minutes (30 au plus) sur le job {jid}")
        steps = [x for x in job.get("steps") or [] if isinstance(x, dict)]
        need(steps and str(steps[0].get("uses", "")).startswith("actions/checkout@v"), f"workflow : le job {jid} commence par actions/checkout@v4")
        runs += [str(x.get("run", "")) for x in steps]
    all_runs = "\n".join(runs)
    for tool in ("ansible-core", "ansible-lint"):
        need(re.search(rf"\b{tool}==\d", all_runs), f"workflow : installez {tool} avec une version épinglée ({tool}==X.Y.Z)")
    need(re.search(r"^\s*ansible-lint\b", all_runs, re.M), "workflow : une étape lance ansible-lint")
    need(re.search(r"ansible-playbook\b.*deploy\.yml.*--syntax-check|ansible-playbook\b.*--syntax-check.*deploy\.yml", all_runs),
         "workflow : une étape lance ansible-playbook ... deploy.yml --syntax-check")


CHECKS = {
    "an1": ([check_an1], "inventaire rangé en groupes et premier playbook idempotent."),
    "an2": ([check_an2], "playbook idempotent, handler notifié et variables de groupe."),
    "an3": ([check_an3], "template validé, boucles et conditions bien placées."),
    "an4": ([check_an4], "rôle nginx complet et dépendances épinglées."),
    "an5": ([check_an5], "secret chiffré au coffre, masqué à l'exécution, connexion vérifiée."),
    "an6": ([check_an6], "déploiement par lots qui s'arrête au premier échec, et CI de lint."),
    # le boss est cumulatif : une phase ultérieure revérifie les précédentes
    "boss1": ([check_an4], "phase 1 : le rôle nginx est propre et réutilisable."),
    "boss2": ([check_an4, check_an5], "phase 2 : les secrets de la base sont au coffre."),
    "boss3": ([check_an4, check_an5, check_an6], "phase 3 : le déploiement est progressif et vérifié en CI."),
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
    except (OSError, ValueError, AttributeError, TypeError, RecursionError) as e:
        print(f"ECHEC : fichier inattendu ({type(e).__name__}) : vérifiez l'indentation et la forme des blocs")
        return 1
    print(f"OK : {success}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
