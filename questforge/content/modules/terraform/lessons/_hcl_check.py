#!/usr/bin/env python3
"""Vérifications des TP du module Terraform.

Analyse statique de l'espace de travail de l'apprenant : aucun binaire
terraform ni accès réseau n'est nécessaire. Usage : _hcl_check.py <tf1|tf2|tf3>
Le répertoire courant est l'espace de travail.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import subprocess
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
                body.attrs.setdefault(name, self.read_expr())
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


def parse_file(name: str) -> Block:
    need(os.path.isfile(name), f"{name} introuvable dans l'espace de travail")
    try:
        with open(name, encoding="utf-8") as fh:
            return parse_text(fh.read())
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
            if secret_findings_in_expr(name, expr):
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
        dirs[:] = [d for d in dirs if d not in (".terraform", ".git", "node_modules")]
        for f in files:
            if f.endswith(suffixes):
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
# Vérifications par leçon
# ---------------------------------------------------------------------------


def check_tf1() -> list[str]:
    cfg = parse_file("main.tf")
    tf = [b for b in cfg.blocks if b.type == "terraform" and not b.labels]
    need(tf, "bloc 'terraform { ... }' manquant")
    tf = tf[0]
    need(literal(tf.attrs.get("required_version")), "attribut 'required_version' manquant (ou vide) dans le bloc terraform")
    providers = [b for b in tf.blocks if b.type == "required_providers"]
    need(providers, "bloc 'required_providers' manquant dans le bloc terraform")
    local = providers[0].attrs.get("local")
    need(local, "provider 'local' non déclaré dans required_providers")
    try:
        spec = parse_object(local)
    except CheckError as e:
        raise CheckError(f"main.tf : provider 'local' : {e}") from None
    need(literal(spec.get("source")) == "hashicorp/local", "provider local : 'source = \"hashicorp/local\"' attendu")
    need(literal(spec.get("version")), "provider local : contrainte de version manquante (par exemple version = \"~> 2.5\")")
    res = find_blocks(cfg, "resource", "local_file", "hello")
    need(res, 'ressource local_file "hello" manquante')
    for attr in ("filename", "content"):
        need(res[0].attrs.get(attr), f"attribut '{attr}' manquant dans la ressource local_file \"hello\"")
    return ["main.tf"]


REFERENCE = re.compile(r"\b(var|local|module|data)\.[A-Za-z_]\w*|\b[a-z][a-z0-9]*_[a-z0-9_]+\.[A-Za-z_]\w*")


def check_tf2() -> list[str]:
    variables = parse_file("variables.tf")
    outputs = parse_file("outputs.tf")

    def variable(name: str) -> Block:
        found = find_blocks(variables, "variable", name)
        need(found, f'variable "{name}" manquante dans variables.tf')
        blk = found[0]
        need(blk.attrs.get("type", "").strip() == "string", f"{name} : 'type = string' manquant")
        desc = literal(blk.attrs.get("description"))
        need(desc and desc.strip(), f"{name} : 'description' absente ou vide")
        return blk

    app = variable("app_name")
    need("default" in app.attrs, "app_name : 'default' manquant")
    env = variable("environment")
    need("default" not in env.attrs, "environment doit être obligatoire : retirez son 'default'")

    out = find_blocks(outputs, "output", "config_path")
    need(out, 'output "config_path" manquant dans outputs.tf')
    desc = literal(out[0].attrs.get("description"))
    need(desc and desc.strip(), "config_path : 'description' absente ou vide")
    value = out[0].attrs.get("value")
    need(value, "config_path : 'value' manquant")
    need(REFERENCE.search(value), "config_path : 'value' doit référencer une variable ou une ressource (par exemple local_file.config.filename)")
    return ["variables.tf", "outputs.tf"]


def check_tf3() -> list[str]:
    secure = parse_file("secure.tf")
    found = find_blocks(secure, "variable", "db_password")
    need(found, 'variable "db_password" manquante dans secure.tf')
    var = found[0]
    need(var.attrs.get("type", "").strip() == "string", "db_password : 'type = string' manquant")
    need(var.attrs.get("sensitive", "").strip() == "true", "db_password doit être marquée 'sensitive = true'")
    need("default" not in var.attrs, "db_password ne doit pas avoir de 'default' : un secret ne se code pas en dur")

    res = find_blocks(secure, "resource", "local_sensitive_file", "db")
    need(res, 'ressource local_sensitive_file "db" manquante')
    uses_var = any(re.search(r"\bvar\.db_password\b", res[0].attrs.get(a, "")) for a in ("content", "content_base64"))
    need(uses_var, "la ressource db doit utiliser var.db_password dans son 'content'")

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
    return ["secure.tf"]


CHECKS = {
    "tf1": (check_tf1, "main.tf est une configuration Terraform valide."),
    "tf2": (check_tf2, "le contrat du module est correctement défini."),
    "tf3": (check_tf3, "secret protégé et state exclu de Git."),
}


def fmt_advice(files: list[str]) -> str | None:
    """Conseil de formatage non bloquant : ne dépend pas de la présence du binaire."""
    if not shutil.which("terraform"):
        return None
    try:
        proc = subprocess.run(
            ["terraform", "fmt", "-check", *files],
            capture_output=True,
            timeout=4,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return "Conseil : lancez 'terraform fmt' pour formater vos fichiers (non bloquant)."
    return None


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in CHECKS:
        print(f"Usage: {argv[0]} <{'|'.join(CHECKS)}>", file=sys.stderr)
        return 2
    check, success = CHECKS[argv[1]]
    try:
        files = check()
    except CheckError as e:
        print(f"Erreur: {e}", file=sys.stderr)
        return 1
    print(f"Vérification réussie : {success}")
    advice = fmt_advice(files)
    if advice:
        print(advice)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
