import re

import httpx

from app.content import Question, Tp

URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:14b"


def _ask(prompt: str, post) -> str:
    r = post(
        URL,
        json={"model": MODEL, "messages": [{"role": "user", "content": prompt}], "stream": False, "think": False},
        timeout=8,
    )
    r.raise_for_status()
    text = re.sub(r"<think>.*?</think>", "", r.json()["message"]["content"], flags=re.S)
    return text.strip()


def _fallback_hint(tp: Tp, level: int) -> str:
    if not tp.hints:
        return "Relis les instructions du TP."
    return tp.hints[min(level, len(tp.hints)) - 1]


def hint(tp: Tp, level: int, last_output: str, *, post=httpx.post) -> str:
    level = max(1, level)
    prompt = (
        f"Tu es un tuteur Linux/DevOps. Donne un indice de niveau {level} "
        f"(sur {len(tp.hints)}) pour guider l'apprenant vers la solution, "
        "sans jamais donner la commande finale. Réponds en français, en deux phrases maximum.\n\n"
        f"Consignes du TP :\n{tp.instructions_md}\n\n"
        f"Dernière sortie du terminal de l'apprenant :\n{last_output[:2000]}"
    )
    try:
        return _ask(prompt, post) or _fallback_hint(tp, level)
    except Exception:
        return _fallback_hint(tp, level)


def explain_error(q: Question, chosen: int, *, post=httpx.post) -> str:
    try:
        if not 0 <= chosen < len(q.options):  # no negative wraparound
            return q.explain
        options = "\n".join(f"{i}. {o}" for i, o in enumerate(q.options))
        prompt = (
            "Tu es un tuteur Linux/DevOps. Explique en français, en quelques phrases courtes, "
            "pourquoi la réponse choisie est fausse (ou confirme qu'elle est juste).\n\n"
            f"Question : {q.text}\nOptions :\n{options}\n"
            f"Bonne réponse : {q.options[q.answer]}\nRéponse choisie : {q.options[chosen]}"
        )
        return _ask(prompt, post) or q.explain
    except Exception:
        return q.explain
