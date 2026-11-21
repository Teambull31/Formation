"""Lecteur YAML minimal (bibliothèque standard seule) pour les vérifications de TP.

Couvre ce qu'on écrit à la main dans un workflow GitHub ou un manifeste Kubernetes : tableaux de
correspondances et de listes par indentation, scalaires, chaînes entre guillemets, listes et
correspondances en ligne simples, blocs `|` et `>`, plusieurs documents séparés par `---`.
Ni ancres, ni étiquettes, ni clés complexes : une construction inconnue lève YamlError.
"""
from __future__ import annotations

import json
import re


class YamlError(Exception):
    pass


def _strip_comment(line: str) -> str:
    quote = None
    for i, c in enumerate(line):
        if quote:
            if c == quote:
                quote = None
        elif c in "\"'":
            quote = c
        elif c == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i].rstrip()
    return line.rstrip()


def _scalar(text: str):
    t = text.strip()
    if t == "" or t in ("~", "null"):
        return None
    if t[0] == '"':
        try:
            return json.loads(t)
        except ValueError:
            raise YamlError(f"chaîne invalide : {t[:30]}") from None
    if t[0] == "'":
        if len(t) < 2 or t[-1] != "'":
            raise YamlError(f"chaîne invalide : {t[:30]}")
        return t[1:-1].replace("''", "'")
    if t[0] == "[":
        if t[-1] != "]":
            raise YamlError(f"liste en ligne invalide : {t[:30]}")
        inner = t[1:-1].strip()
        return [_scalar(x) for x in _split_flow(inner)] if inner else []
    if t[0] == "{":
        if t[-1] != "}":
            raise YamlError(f"correspondance en ligne invalide : {t[:30]}")
        inner = t[1:-1].strip()
        out = {}
        for part in _split_flow(inner) if inner else []:
            k, sep, v = part.partition(":")
            if not sep:
                raise YamlError(f"correspondance en ligne invalide : {part[:30]}")
            out[str(_scalar(k))] = _scalar(v)
        return out
    if t in ("true", "True"):
        return True
    if t in ("false", "False"):
        return False
    if re.fullmatch(r"-?\d+", t):
        return int(t)
    if re.fullmatch(r"-?\d+\.\d+", t):
        return float(t)
    if t[0] in "&*!|>%@`":
        raise YamlError(f"construction YAML non gérée : {t[:20]}")
    return t


def _split_flow(inner: str) -> list[str]:
    parts, depth, cur, quote = [], 0, "", None
    for c in inner:
        if quote:
            cur += c
            if c == quote:
                quote = None
        elif c in "\"'":
            quote = c
            cur += c
        elif c in "[{":
            depth += 1
            cur += c
        elif c in "]}":
            depth -= 1
            cur += c
        elif c == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += c
    if cur.strip():
        parts.append(cur)
    return parts


def _split_key(text: str):
    """'cle: valeur' -> (cle, valeur) ; None si ce n'est pas une paire."""
    if text[0] in "\"'":
        q = text[0]
        end = text.find(q, 1)
        if end > 0 and text[end + 1: end + 2] == ":" and text[end + 2: end + 3] in ("", " "):
            return text[1:end], text[end + 2:].strip()
        return None
    m = re.match(r"([^\s:][^:]*?)\s*:(?:\s+(.*)|$)", text)
    if not m or text.startswith(("[", "{")):
        return None
    return m.group(1), (m.group(2) or "").strip()


class _Parser:
    def __init__(self, text: str):
        if "\t" in text.split("\n", 1)[0] or re.search(r"^\t", text, re.M):
            raise YamlError("tabulation en début de ligne : le YAML s'indente avec des espaces")
        self.raw = text.split("\n")
        self.i = 0

    def _skip(self) -> None:
        while self.i < len(self.raw) and not _strip_comment(self.raw[self.i]).strip():
            self.i += 1

    def _peek(self):
        self._skip()
        if self.i >= len(self.raw):
            return None
        line = _strip_comment(self.raw[self.i])
        return len(line) - len(line.lstrip(" ")), line.strip()

    def block(self, indent: int):
        p = self._peek()
        if p is None or p[0] < indent:
            return None
        ind, text = p
        if text == "-" or text.startswith("- "):
            return self.seq(ind)
        if _split_key(text) is not None:
            return self.map(ind)
        self.i += 1
        return _scalar(text)

    def seq(self, ind: int):
        out = []
        while True:
            p = self._peek()
            if p is None or p[0] != ind or not (p[1] == "-" or p[1].startswith("- ")):
                return out
            rest = p[1][1:].strip()
            if not rest:
                self.i += 1
                out.append(self.block(ind + 1))
                continue
            # « - cle: valeur » ouvre une correspondance dont la colonne est celle de « cle »
            offset = len(self.raw[self.i]) - len(self.raw[self.i].lstrip(" ")) + 2
            self.raw[self.i] = " " * offset + rest
            out.append(self.block(offset))

    def map(self, ind: int):
        out: dict = {}
        while True:
            p = self._peek()
            if p is None or p[0] != ind:
                return out
            kv = _split_key(p[1])
            if kv is None:
                raise YamlError(f"ligne {self.i + 1} : « {p[1][:40]} » n'est pas de la forme cle: valeur")
            key, rest = kv
            if key in out:
                raise YamlError(f"ligne {self.i + 1} : la clé {key} est écrite deux fois")
            self.i += 1
            if rest[:1] in ("|", ">"):
                out[key] = self.literal(ind, rest[0] == ">")
            elif rest:
                out[key] = _scalar(rest)
            else:
                q = self._peek()
                if q is not None and (q[0] > ind or (q[0] == ind and (q[1] == "-" or q[1].startswith("- ")))):
                    out[key] = self.block(q[0])
                else:
                    out[key] = None

    def literal(self, parent: int, fold: bool) -> str:
        lines = []
        while self.i < len(self.raw):
            line = self.raw[self.i]
            if line.strip() and len(line) - len(line.lstrip(" ")) <= parent:
                break
            lines.append(line)
            self.i += 1
        while lines and not lines[-1].strip():
            lines.pop()
        if not lines:
            return ""
        base = min(len(l) - len(l.lstrip(" ")) for l in lines if l.strip())
        body = [l[base:] if l.strip() else "" for l in lines]
        return (" ".join(body) if fold else "\n".join(body)) + "\n"


def load_all(text: str) -> list:
    """Tous les documents d'un flux YAML (séparés par une ligne `---`)."""
    docs, cur = [], []
    for line in text.split("\n"):
        if line.rstrip() == "---" or line.startswith("--- "):
            docs.append("\n".join(cur))
            cur = []
        elif line.rstrip() == "...":
            continue
        else:
            cur.append(line)
    docs.append("\n".join(cur))
    out = []
    for d in docs:
        if not _strip_comment(d).strip() and not any(_strip_comment(l).strip() for l in d.split("\n")):
            continue
        parser = _Parser(d)
        value = parser.block(0)
        parser._skip()
        if parser.i < len(parser.raw):
            raise YamlError(f"ligne {parser.i + 1} : contenu inattendu (indentation incohérente ?)")
        out.append(value)
    return out


def load(text: str):
    docs = load_all(text)
    if len(docs) != 1:
        raise YamlError(f"un seul document attendu, {len(docs)} trouvés")
    return docs[0]
