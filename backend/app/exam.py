"""Examen final d'un module : questions tirées de tous ses QCM, chronométrées, seuil de réussite."""
import random

from app.content import Module, Question

SIZE = 15
PASS_PCT = 80
SECONDS_PER_QUESTION = 45
EXAM_XP = 100  # max par module ; seules les améliorations du meilleur score rapportent


def pool(m: Module) -> list[Question]:
    return [q for les in m.lessons for q in les.qcm]


def draw(m: Module, rng: random.Random, size: int = SIZE) -> list[Question]:
    qs = pool(m)
    return rng.sample(qs, min(size, len(qs)))


def grade(m: Module, answers: dict[str, int], size: int = SIZE) -> tuple[int, list[dict]]:
    """(score en %, détail par question). Lève ValueError si une réponse ne vient pas du module."""
    by_id = {q.id: q for q in pool(m)}
    need = min(size, len(by_id))
    if len(answers) != need or any(qid not in by_id for qid in answers):
        raise ValueError(f"{need} réponses attendues, toutes issues de ce module")
    detail = []
    for qid, chosen in answers.items():
        q = by_id[qid]
        if not -1 <= chosen < len(q.options):  # -1 : sans réponse (temps écoulé)
            raise ValueError(f"choix hors des options pour {qid}")
        detail.append({"id": qid, "text": q.text, "chosen": chosen, "answer": q.answer, "correct": chosen == q.answer,
                       "answer_text": q.options[q.answer],
                       "explain": q.explain, "remedial_lesson_id": q.remedial_lesson_id})
    return round(100 * sum(d["correct"] for d in detail) / need), detail
