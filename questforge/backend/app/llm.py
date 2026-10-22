from __future__ import annotations
from typing import Callable, Any
import httpx
from app.content import Question, Tp

OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_MODEL = "qwen3:14b"


def hint(
    tp: Tp,
    level: int,
    last_output: str,
    *,
    post: Callable[..., Any] = httpx.post,
) -> str:
    if not tp.hints:
        fallback = ""
    else:
        idx = max(0, min(len(tp.hints) - 1, level - 1))
        fallback = tp.hints[idx]

    try:
        payload = {
            "model": DEFAULT_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Tu es un formateur technique bienveillant et concis. "
                        "Donne un indice pédagogique en français pour orienter l'étudiant "
                        "sans lui donner la solution brute."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"TP: {tp.title}\n"
                        f"Consignes: {tp.instructions_md}\n"
                        f"Indice niveau {level}/{len(tp.hints)}\n"
                        f"Sortie terminal précédente: {last_output}\n"
                        f"Indice de cadrage: {fallback}"
                    ),
                },
            ],
            "stream": False,
        }
        resp = post(OLLAMA_URL, json=payload, timeout=8.0)
        if resp.status_code == 200:
            data = resp.json()
            content = data.get("message", {}).get("content", "").strip()
            if content:
                return content
    except Exception:
        pass

    return fallback


def explain_error(
    q: Question,
    chosen: int,
    *,
    post: Callable[..., Any] = httpx.post,
) -> str:
    fallback = q.explain
    chosen_text = q.options[chosen] if 0 <= chosen < len(q.options) else "Option inconnue"

    try:
        payload = {
            "model": DEFAULT_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Tu es un instructeur technique. Explique pourquoi le choix "
                        "de l'étudiant est incorrect et rappelle brièvement la bonne notion en français."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Question posée: {q.text}\n"
                        f"Choix de l'élève: {chosen_text}\n"
                        f"Explication officielle: {fallback}"
                    ),
                },
            ],
            "stream": False,
        }
        resp = post(OLLAMA_URL, json=payload, timeout=8.0)
        if resp.status_code == 200:
            data = resp.json()
            content = data.get("message", {}).get("content", "").strip()
            if content:
                return content
    except Exception:
        pass

    return fallback
