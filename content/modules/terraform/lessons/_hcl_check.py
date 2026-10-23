#!/usr/bin/env python3
"""Vérifications des TP et du boss du module Terraform.

Analyse statique, en lecture seule, du dossier de l'apprenant : aucun binaire
terraform, aucun réseau, aucune écriture. Lancer avec `python3 -I -B`.
Usage : _hcl_check.py <tf1|tf2|tf3|boss1|boss2|boss3> [dossier]
Le répertoire courant (ou `dossier`, sous-dossier direct) est le dossier du TP.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import sys
from dataclasses import dataclass, field

IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")
HEREDOC = re.compile(r"<<-?([A-Za-z_][A-Za-z0-9_]*)[ \t]*\n")

SECRET_KEY = re.compile(
    r"(pass(word|wd)?|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|credential)",
    re.I,
)
NOT_A_SECRET_NAME = re.compile(r"(_name|_id|_arn|_path|_file|_length|_version|_ttl|_enabled)$", re.I)
SECRET_IN_STRING = re.compile(
    r"(pass(word|wd)?|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key)\s*[=:]\s*[^\s§\"'{]+",
    re.I,
)


class CheckError(Exception):
    """Erreur affichée à l'apprenant."""


def need(condition, message: str) -> None:
    if not condition:
        raise CheckError(message)


# ---------------------------------------------------------------------------
# Analyse HCL minimale : blocs, attributs, chaînes, commentaires, heredocs
# ---------------------------------------------------------------------------


def skip_braces(s: str, i: int) -> int:
    """s[i] == '{' : renvoie l'index après l'accolade fermante correspondante."""
    depth = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == '"':
            i = skip_string(s, i)
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n


def skip_string(s: str, i: int) -> int:
    """s[i] == '"' : renvoie l'index après la guillemet fermante (interpolations incluses)."""
    i += 1
    n = len(s)
    while i < n:
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == '"':
            return i + 1
        if c in "$%" and s[i + 1 : i + 2] == "{":
            i = skip_braces(s, i + 1)
            continue
        i += 1
    return n


def strip_comments(s: str) -> str:
    out: list[str] = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == '"':
            j = skip_string(s, i)
            out.append(s[i:j])
            i = j
        elif c == "#" or s.startswith("//", i):
            while i < n and s[i] != "\n":
                i += 1
        elif s.startswith("/*", i):
            j = s.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(" " + re.sub(r"[^\n]", "", s[i:j]))
            i = j
        else:
            m = HEREDOC.match(s, i) if s.startswith("<<", i) else None
            if m:
                end = re.compile(r"^[ \t]*" + re.escape(m.group(1)) + r"[ \t]*$", re.M).search(s, m.end())
                j = end.end() if end else n
                out.append(s[i:j])
                i = j
            else:
                out.append(c)
                i += 1
    return "".join(out)


def literal(expr: str | None) -> str | None:
    """Valeur d'une chaîne littérale sans interpolation, sinon None."""
    if expr is None:
        return None
    expr = expr.strip()
    if len(expr) >= 2 and expr[0] == '"' and skip_string(expr, 0) == len(expr):
        if "${" in expr or "%{" in expr:
            return None
        return expr[1:-1]
    return None


@dataclass
class Block:
    type: str
    labels: list[str]
    attrs: dict[str, str] = field(default_factory=dict)
    blocks: list["Block"] = field(default_factory=list)


class Parser:
    def __init__(self, text: str, commas: bool = False):
        self.s = strip_comments(text)
        self.n = len(self.s)
        self.i = 0
        self.commas = commas

    def where(self) -> str:
        line = self.s.count("\n", 0, self.i) + 1
        return f"ligne {line}"

    def skip_ws(self, newlines: bool = True) -> None:
        chars = " \t\r" + ("\n" if newlines else "") + ("," if self.commas else "")
        while self.i < self.n and self.s[self.i] in chars:
            self.i += 1

    def read_expr(self) -> str:
        self.skip_ws(False)
        start = self.i
        m = HEREDOC.match(self.s, self.i) if self.s.startswith("<<", self.i) else None
        if m:
            end = re.compile(r"^[ \t]*" + re.escape(m.group(1)) + r"[ \t]*$", re.M).search(self.s, m.end())
            self.i = end.end() if end else self.n
            return self.s[start : self.i].strip()
        depth = 0
        while self.i < self.n:
            c = self.s[self.i]
            if c == '"':
                self.i = skip_string(self.s, self.i)
                continue
            if c in "([{":
                depth += 1
            elif c in ")]}":
                if depth == 0:
                    break
                depth -= 1
            elif depth == 0 and (c == "\n" or (c == "," and self.commas)):
                break
            self.i += 1
        expr = self.s[start : self.i].strip()
        if not expr:
            raise CheckError(f"valeur manquante après '=' ({self.where()})")
        return expr

    def parse_body(self, closing: bool) -> Block:
        body = Block("", [])
        while True:
            self.skip_ws()
            if self.i >= self.n:
                need(not closing, "accolade fermante '}' manquante")
                return body
            c = self.s[self.i]
            if c == "}":
                need(closing, f"accolade '}}' inattendue ({self.where()})")
                self.i += 1
                return body
            m = IDENT.match(self.s, self.i)
            if not m and c == '"' and self.commas:
                j = skip_string(self.s, self.i)
                name = self.s[self.i + 1 : j - 1]
                self.i = j
            elif m:
                name = m.group()
                self.i = m.end()
            else:
                raise CheckError(f"syntaxe HCL invalide ({self.where()}) près de : {self.s[self.i:self.i + 20]!r}")
            self.skip_ws(False)
            nxt = self.s[self.i : self.i + 1]
            if nxt in ("=", ":") and not self.s.startswith("==", self.i) and (nxt == "=" or self.commas):
                self.i += 1
                need(name not in body.attrs, f"attribut '{name}' défini deux fois ({self.where()})")
                body.attrs[name] = self.read_expr()
                continue
            labels: list[str] = []
            while True:
                self.skip_ws(False)
                if self.s[self.i : self.i + 1] == '"':
                    j = skip_string(self.s, self.i)
                    labels.append(self.s[self.i + 1 : j - 1])
                    self.i = j
                    continue
                lm = IDENT.match(self.s, self.i)
                if lm:
                    labels.append(lm.group())
                    self.i = lm.end()
                    continue
                break
            need(self.s[self.i : self.i + 1] == "{", f"syntaxe HCL invalide ({self.where()}) : '{name}' doit être suivi de '=' ou d'un bloc '{{ ... }}'")
            self.i += 1
            sub = self.parse_body(True)
            body.blocks.append(Block(name, labels, sub.attrs, sub.blocks))


def parse_text(text: str) -> Block:
    return Parser(text).parse_body(False)


def parse_object(expr: str) -> dict[str, str]:
    expr = expr.strip()
    need(expr.startswith("{") and expr.endswith("}"), "un objet '{ ... }' est attendu")
    return Parser(expr[1:-1], commas=True).parse_body(False).attrs


def read_text(name: str) -> str:
    need(os.path.isfile(name) and not os.path.islink(name), f"{name} introuvable dans le dossier du TP (fichier ordinaire attendu)")
    try:
        with open(name, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        raise CheckError(f"{name} : fichier illisible (texte UTF-8 attendu)") from None


def parse_file(name: str) -> Block:
    text = read_text(name)
    try:
        return parse_text(text)
    except CheckError as e:
        raise CheckError(f"{name} : {e}") from None


def find_blocks(root: Block, type_: str, *labels: str) -> list[Block]:
    return [b for b in root.blocks if b.type == type_ and b.labels == list(labels)]


# ---------------------------------------------------------------------------
# Détection de secrets en dur
# ---------------------------------------------------------------------------


def string_literals(expr: str):
    i = 0
    while i < len(expr):
        if expr[i] == '"':
            j = skip_string(expr, i)
            yield expr[i + 1 : j - 1]
            i = j
        else:
            i += 1


def strip_interpolations(text: str) -> str:
    out, i = [], 0
    while i < len(text):
        if text[i] in "$%" and text[i + 1 : i + 2] == "{":
            i = skip_braces(text, i + 1)
            out.append("§")
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def secret_name(name: str) -> bool:
    return bool(SECRET_KEY.search(name)) and not NOT_A_SECRET_NAME.search(name) and name not in ("sensitive", "description")


def secret_findings_in_expr(name: str, expr: str) -> bool:
    value = literal(expr)
    if value is not None and value.strip() and secret_name(name):
        return True
    for lit in string_literals(expr):
        if SECRET_IN_STRING.search(strip_interpolations(lit)):
            return True
        # "${"texte"}" : une interpolation qui ne contient qu'un littéral sert à cacher un secret
        for m in re.finditer(r"[$%]\{", lit):
            inner = lit[m.start() + 2 : skip_braces(lit, m.start() + 1) - 1]
            if re.fullmatch(r'\s*"[^"]*"\s*', inner):
                return True
    return False


def walk_blocks(block: Block):
    yield block
    for sub in block.blocks:
        yield from walk_blocks(sub)


def scan_hcl_secrets(path: str, text: str) -> list[str]:
    found = []
    root = parse_text(text)
    for blk in walk_blocks(root):
        for name, expr in blk.attrs.items():
            if name not in ("description", "error_message") and secret_findings_in_expr(name, expr):
                found.append(f"{path} : '{name}' contient une valeur secrète littérale")
        if blk.type == "variable" and blk.labels and secret_name(blk.labels[0]):
            default = literal(blk.attrs.get("default"))
            if default and default.strip():
                found.append(f"{path} : la variable '{blk.labels[0]}' a un default secret en dur")
    return found


def scan_json_secrets(path: str, data, key: str = "") -> list[str]:
    found = []
    if isinstance(data, dict):
        for k, v in data.items():
            found += scan_json_secrets(path, v, k)
    elif isinstance(data, list):
        for v in data:
            found += scan_json_secrets(path, v, key)
    elif isinstance(data, str):
        stripped = strip_interpolations(data)
        if (secret_name(key) and data.strip() and not data.startswith("${")) or SECRET_IN_STRING.search(stripped):
            found.append(f"{path} : '{key}' contient une valeur secrète littérale")
    return found


def hcl_files(suffixes: tuple[str, ...]):
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in (".terraform", ".git", "node_modules") and not os.path.islink(os.path.join(root, d))]
        for f in files:
            if f.endswith(suffixes) and not os.path.islink(os.path.join(root, f)):
                yield os.path.normpath(os.path.join(root, f))


def assert_no_hardcoded_secret() -> None:
    problems: list[str] = []
    for path in hcl_files((".tf", ".tfvars")):
        try:
            with open(path, encoding="utf-8") as fh:
                problems += scan_hcl_secrets(path, fh.read())
        except CheckError:
            continue  # la syntaxe est vérifiée séparément sur les fichiers du TP
    for path in hcl_files((".tf.json", ".tfvars.json")):
        try:
            with open(path, encoding="utf-8") as fh:
                problems += scan_json_secrets(path, json.load(fh))
        except (ValueError, OSError):
            continue
    need(
        not problems,
        "secret en dur détecté : "
        + " ; ".join(problems)
        + ". Utilisez une variable sensitive injectée via TF_VAR_*",
    )


# ---------------------------------------------------------------------------
# .gitignore
# ---------------------------------------------------------------------------


def load_gitignore(path: str = ".gitignore") -> list[tuple[str, bool]]:
    need(os.path.isfile(path), ".gitignore introuvable")
    rules: list[tuple[str, bool]] = []
    with open(path, encoding="utf-8") as fh:
        for raw in fh.read().splitlines():
            line = raw.rstrip()
            if not line or line.startswith("#"):
                continue
            negate = line.startswith("!")
            rules.append((line[1:] if negate else line, negate))
    return rules


def rule_matches(pattern: str, path: str) -> bool:
    dir_only = pattern.endswith("/")
    pat = pattern.rstrip("/")
    anchored = pat.startswith("/") or "/" in pat
    pat = pat.lstrip("/")
    while pat.startswith("**/"):
        pat = pat[3:]
        anchored = "/" in pat
    parts = path.split("/")
    for i in range(1, len(parts) + 1):
        is_dir = i < len(parts)
        if dir_only and not is_dir:
            continue
        target = "/".join(parts[:i]) if anchored else parts[i - 1]
        if fnmatch.fnmatchcase(target, pat):
            return True
    return False


def is_ignored(rules: list[tuple[str, bool]], path: str) -> bool:
    ignored = False
    for pattern, negate in rules:
        if rule_matches(pattern, path):
            ignored = not negate
    return ignored


# ---------------------------------------------------------------------------
# Structure d'un module (tous les .tf du dossier)
# ---------------------------------------------------------------------------

VERSION_PART = re.compile(r"(?:>=|<=|~>|!=|=|>|<)?\s*\d+(?:\.\d+){0,2}(?:-[0-9A-Za-z.]+)?")


def version_ok(value: str | None) -> bool:
    return bool(value) and all(VERSION_PART.fullmatch(p.strip()) for p in value.split(","))


def module_blocks() -> list[Block]:
    """Blocs de premier niveau de tous les *.tf du dossier ; tout fichier doit être syntaxiquement valide."""
    blocks: list[Block] = []
    for name in sorted(f for f in os.listdir(".") if f.endswith(".tf")):
        blocks += parse_file(name).blocks
    seen: set[tuple] = set()
    for b in blocks:
        if b.type in ("variable", "output", "resource", "data"):
            key = (b.type, *b.labels)
            need(key not in seen, f"{b.type} {'.'.join(b.labels)} est déclaré deux fois dans le dossier")
            seen.add(key)
    return blocks


def code_of(expr: str) -> str:
    """Expression sans le texte des chaînes (les interpolations ${...} restent) : seules les vraies références comptent."""
    out, i = [], 0
    while i < len(expr):
        if expr[i] == '"':
            j = skip_string(expr, i)
            k = i + 1
            while k < j - 1:
                if expr[k] in "$%" and expr[k + 1 : k + 2] == "{":
                    e = skip_braces(expr, k + 1)
                    out.append(" " + expr[k + 2 : e - 1] + " ")
                    k = e
                else:
                    k += 2 if expr[k] == "\\" else 1
            i = j
        else:
            out.append(expr[i])
            i += 1
    return "".join(out)


def references(expr: str) -> tuple[set[str], set[tuple[str, str]]]:
    code = code_of(expr)
    variables = set(re.findall(r"\bvar\.([A-Za-z_][\w-]*)", code))
    resources = set(re.findall(r"(?<![\w.])([a-z][a-z0-9]*_[a-z0-9_]+)\.([A-Za-z_][\w-]*)", code))
    return variables, resources


def nonblank(expr: str | None) -> bool:
    """Attribut présent et non vide (une expression non littérale compte)."""
    if expr is None or not expr.strip():
        return False
    value = literal(expr)
    return value is None or bool(value.strip())


# ---------------------------------------------------------------------------
# Vérifications par leçon
# ---------------------------------------------------------------------------


def check_tf1() -> None:
    module_blocks()
    cfg = parse_file("main.tf")
    tf = [b for b in cfg.blocks if b.type == "terraform" and not b.labels]
    need(tf, "bloc 'terraform { ... }' manquant dans main.tf")
    tf = tf[0]
    need(version_ok(literal(tf.attrs.get("required_version"))),
         "'required_version' manquant ou invalide dans le bloc terraform (par exemple \">= 1.5.0\")")
    providers = [b for b in tf.blocks if b.type == "required_providers"]
    need(providers, "bloc 'required_providers' manquant dans le bloc terraform")
    local = providers[0].attrs.get("local")
    need(local, "provider 'local' non déclaré dans required_providers")
    try:
        spec = parse_object(local)
    except CheckError as e:
        raise CheckError(f"main.tf : provider 'local' : {e}") from None
    need(literal(spec.get("source")) == "hashicorp/local", "provider local : 'source = \"hashicorp/local\"' attendu")
    need(version_ok(literal(spec.get("version"))),
         "provider local : contrainte de version manquante ou invalide (par exemple version = \"~> 2.5\")")
    res = find_blocks(cfg, "resource", "local_file", "hello")
    need(res, 'ressource local_file "hello" manquante dans main.tf')
    for attr in ("filename", "content"):
        need(nonblank(res[0].attrs.get(attr)), f"attribut '{attr}' manquant ou vide dans la ressource local_file \"hello\"")


def check_tf2() -> None:
    blocks = module_blocks()
    variables = {b.labels[0]: b for b in blocks if b.type == "variable" and len(b.labels) == 1}
    resources = {tuple(b.labels) for b in blocks if b.type == "resource" and len(b.labels) == 2}
    need(os.path.isfile("variables.tf") and os.path.isfile("outputs.tf"), "variables.tf et outputs.tf sont attendus")
    in_variables = {b.labels[0] for b in parse_file("variables.tf").blocks if b.type == "variable" and b.labels}

    def variable(name: str) -> Block:
        need(name in variables and name in in_variables, f'variable "{name}" manquante dans variables.tf')
        blk = variables[name]
        need(blk.attrs.get("type", "").strip() == "string", f"{name} : 'type = string' manquant")
        desc = literal(blk.attrs.get("description"))
        need(desc and len(desc.strip()) >= 5, f"{name} : 'description' absente ou vide")
        return blk

    app = variable("app_name")
    need(nonblank(app.attrs.get("default")), "app_name : 'default' manquant (ou vide)")
    env = variable("environment")
    need("default" not in env.attrs, "environment doit être obligatoire : retirez son 'default'")

    outs = [b for b in parse_file("outputs.tf").blocks if b.type == "output" and b.labels == ["config_path"]]
    need(outs, 'output "config_path" manquant dans outputs.tf')
    out = outs[0]
    desc = literal(out.attrs.get("description"))
    need(desc and len(desc.strip()) >= 5, "config_path : 'description' absente ou vide")
    value = out.attrs.get("value")
    need(value, "config_path : 'value' manquant")
    used_vars, used_res = references(value)
    need(used_vars or used_res,
         "config_path : 'value' doit référencer une variable ou une ressource (par exemple local_file.config.filename)")
    for v in used_vars:
        need(v in variables, f"config_path référence var.{v}, qui n'est déclarée nulle part")
    for r in used_res:
        need(r in resources, f"config_path référence {r[0]}.{r[1]}, qui n'est déclarée nulle part")


NEVER_IGNORED = ["main.tf", "variables.tf", "outputs.tf", "secure.tf", ".gitignore", ".terraform.lock.hcl"]


def check_tf3() -> None:
    blocks = module_blocks()
    secure = parse_file("secure.tf")
    found = find_blocks(secure, "variable", "db_password")
    need(found, 'variable "db_password" manquante dans secure.tf')
    var = found[0]
    need(var.attrs.get("type", "").strip() == "string", "db_password : 'type = string' manquant")
    need(var.attrs.get("sensitive", "").strip() == "true", "db_password doit être marquée 'sensitive = true'")
    need("default" not in var.attrs, "db_password ne doit pas avoir de 'default' : un secret ne se code pas en dur")

    res = find_blocks(secure, "resource", "local_sensitive_file", "db")
    need(res, 'ressource local_sensitive_file "db" manquante dans secure.tf')
    need(nonblank(res[0].attrs.get("filename")), "la ressource db a besoin d'un 'filename'")
    uses_var = any(re.search(r"\bvar\.db_password\b", code_of(res[0].attrs.get(a, ""))) for a in ("content", "content_base64"))
    need(uses_var, "la ressource db doit utiliser var.db_password dans son 'content'")

    for b in blocks:  # un output qui expose le secret doit être sensitive
        if b.type == "output":
            v, r = references(b.attrs.get("value", ""))
            if ("db_password" in v or ("local_sensitive_file", "db") in r) and b.attrs.get("sensitive", "").strip() != "true":
                raise CheckError(f"l'output '{b.labels[0] if b.labels else '?'}' expose le secret : ajoutez 'sensitive = true'")

    assert_no_hardcoded_secret()

    rules = load_gitignore()
    samples = {
        "le state (*.tfstate)": "terraform.tfstate",
        "les sauvegardes du state (*.tfstate.*)": "terraform.tfstate.backup",
        "le cache .terraform/": ".terraform/providers/registry/provider.zip",
        "les fichiers *.tfvars": "prod.tfvars",
    }
    for label, sample in samples.items():
        need(is_ignored(rules, sample), f".gitignore : {label} n'est pas exclu de Git")
    for name in NEVER_IGNORED:
        need(not is_ignored(rules, name), f".gitignore : {name} ne doit pas être exclu de Git (règle trop large ?)")


CHECKS = {
    "tf1": ([check_tf1], "main.tf est une configuration Terraform valide."),
    "tf2": ([check_tf2], "le contrat du module est correctement défini."),
    "tf3": ([check_tf3], "secret protégé et state exclu de Git."),
    # le boss est cumulatif : une phase ultérieure revérifie les précédentes
    "boss1": ([check_tf1], "phase 1 : la configuration de base est valide."),
    "boss2": ([check_tf1, check_tf2], "phase 2 : le module a un contrat clair."),
    "boss3": ([check_tf1, check_tf2, check_tf3], "phase 3 : le secret est protégé et le state exclu de Git."),
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
    except (RecursionError, OSError, ValueError) as e:
        print(f"ECHEC : fichier illisible ({type(e).__name__})")
        return 1
    print(f"OK : {success}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
