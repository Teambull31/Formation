"""Simulateur d'entretien : banque de questions et notation hors ligne par mots-clés."""
import json
import re
import unicodedata
from pathlib import Path

REQUIRED = ("id", "role", "question", "time_limit", "keywords", "model_answer")


def norm(text: str) -> str:
    """Minuscules sans accents, pour comparer sans se soucier de la frappe."""
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


def load_questions(content_dir: Path) -> list[dict]:
    path = Path(content_dir) / "interview" / "questions.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    ids = set()
    for q in data:
        missing = [k for k in REQUIRED if k not in q]
        if missing or q["id"] in ids or not re.fullmatch(r"[A-Za-z0-9_-]+", q["id"]) or not q["keywords"]:
            raise ValueError(f"{path}: question invalide {q.get('id')!r} {missing}")
        ids.add(q["id"])
    return data


def keyword_grade(answer: str, keywords: list[list[str]]) -> tuple[int, list[str]]:
    """(score 0-100, libellés des idées absentes). Chaque mot-clé = [libellé, motifs alternatifs séparés par |]."""
    text = norm(answer)
    missing = [label for label, patterns in keywords if not any(p and p in text for p in norm(patterns).split("|"))]
    return round(100 * (len(keywords) - len(missing)) / len(keywords)), missing
