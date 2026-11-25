"""Outils d'apprentissage : réponse orale, missions réelles, certifications visées."""
import json
import re
from pathlib import Path

from app.interview import norm

STOP = {"le", "la", "les", "un", "une", "des", "de", "du", "et", "ou", "a", "au", "aux", "en", "dans", "par", "pour",
        "sur", "est", "sont", "qui", "que", "on", "il", "elle", "ce", "cette", "son", "sa", "ses", "se", "ne", "pas"}
DONT_KNOW = ("je sais pas", "je ne sais pas", "aucune idee", "passe", "joker")


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", norm(text)) if w not in STOP and len(w) > 1]


def oral_match(transcript: str, expected: str) -> bool:
    """La réponse dite contient-elle l'essentiel de la réponse attendue ? Tolérant à la dictée (accents, ordre, articles)."""
    said = norm(transcript)
    if not said.strip() or any(d in said for d in DONT_KNOW):
        return False
    want = _words(expected)
    if not want:
        return False
    got = set(_words(transcript))
    hit = sum(1 for w in want if w in got or any(g.startswith(w[:5]) for g in got if len(w) > 5))
    return hit / len(want) >= (1 if len(want) <= 2 else 0.6)


def load_missions(content_dir: Path) -> list[dict]:
    path = Path(content_dir) / "missions.json"
    if not path.is_file():
        return []
    ms = json.loads(path.read_text(encoding="utf-8"))
    for m in ms:
        if not all(isinstance(m.get(k), str) for k in ("id", "module", "title", "goal")) or not isinstance(m.get("steps"), list):
            raise ValueError(f"{path}: mission invalide {m.get('id')}")
    return ms


# certification visée -> modules dont les questions forment l'examen blanc, durée et taille de l'épreuve réelle
CERTS = {
    "terraform": {"title": "HashiCorp Terraform Associate", "modules": ["terraform"], "questions": 57, "minutes": 60},
    "cka": {"title": "Kubernetes CKA (partie théorique)", "modules": ["k8s"], "questions": 40, "minutes": 60},
    "gha": {"title": "GitHub Actions (GH-200)", "modules": ["cicd"], "questions": 65, "minutes": 100},
    "dca": {"title": "Docker Certified Associate", "modules": ["docker"], "questions": 55, "minutes": 90},
    "devops": {"title": "Entretien DevOps junior (tous modules)", "modules": [], "questions": 40, "minutes": 45},
}
