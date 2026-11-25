"""Cartes mémoire tirées des leçons étudiées : pièges (!!...!!) et termes clés (**...**), révisés en boîtes Leitner."""
import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

from app.content import Lesson
from app.review import INTERVALS

NEW_PER_DAY = 10
MASTERED = "9999-12-31"
CODE = re.compile(r"```.*?```", re.S)
BOLD = re.compile(r"\*\*([^*\n]+)\*\*")
TRAP = re.compile(r"!!([^!\n]+)!!")
BLANK = "＿＿＿"


@dataclass
class Card:
    id: str
    lesson_id: str
    kind: str  # "piege" | "terme"
    front: str
    back: str


def _card(lid: str, kind: str, front: str, back: str) -> Card:
    return Card(f"{lid}-{hashlib.sha1(f'{kind}|{front}|{back}'.encode()).hexdigest()[:10]}", lid, kind, front, back)


def lesson_cards(les: Lesson) -> list[Card]:
    out, section, seen = [], les.title, set()
    for raw in CODE.sub("", les.body_md).splitlines():
        line = raw.strip()
        if line.startswith("#"):
            section = line.lstrip("#").strip()
            continue
        if not line or line.startswith("|"):
            continue
        for m in TRAP.finditer(line):
            out.append(_card(les.id, "piege", f"{section} : quel piège retenir ?", m.group(1).strip()))
        text = TRAP.sub("", re.sub(r"^(?:[-*]|\d+\.)\s+", "", line))
        for sent in re.split(r"(?<=[.!?])\s+", text):
            for term in BOLD.findall(sent):
                plain = BOLD.sub(lambda m: m.group(1), sent)
                if not 2 <= len(term) <= 40 or len(plain) < 40 or term in seen:
                    continue
                seen.add(term)
                front = BOLD.sub(lambda m: BLANK if m.group(1) == term else m.group(1), sent, count=0)
                out.append(_card(les.id, "terme", front.strip(), term))
    return out


def _box_due(today: date, box: int) -> tuple[int, str]:
    if box >= len(INTERVALS):
        return len(INTERVALS), MASTERED
    return box, (today + timedelta(days=INTERVALS[box])).isoformat()


def record_card(db: sqlite3.Connection, card_id: str, known: bool, today: date) -> dict:
    row = db.execute("SELECT box FROM cards WHERE card_id = ?", (card_id,)).fetchone()
    if row:  # carte déjà vue : c'est une révision, elle compte pour le taux de rétention
        db.execute("INSERT INTO review_log(day, correct) VALUES (?, ?)", (today.isoformat(), int(known)))
    box = (row[0] + 1 if row else 1) if known else 0
    box, due = _box_due(today, box)
    if row:
        db.execute("UPDATE cards SET box = ?, due = ? WHERE card_id = ?", (box, due, card_id))
    else:
        db.execute("INSERT INTO cards(card_id, box, due, intro) VALUES (?, ?, ?, ?)", (card_id, box, due, today.isoformat()))
    db.commit()
    return {"box": box, "due": due, "mastered": due == MASTERED}


def session(db: sqlite3.Connection, studied: list[Card], today: date) -> dict:
    """Cartes dues (déjà vues) puis nouvelles cartes des leçons étudiées, NEW_PER_DAY au plus par jour."""
    rows = {r[0]: (r[1], r[2]) for r in db.execute("SELECT card_id, box, due FROM cards")}
    by_id = {c.id: c for c in studied}
    due = sorted((c for c in studied if c.id in rows and rows[c.id][1] <= today.isoformat()), key=lambda c: rows[c.id][1])
    intro_today = db.execute("SELECT COUNT(*) FROM cards WHERE intro = ?", (today.isoformat(),)).fetchone()[0]
    fresh = [c for c in studied if c.id not in rows][: max(0, NEW_PER_DAY - intro_today)]
    boxes = [0] * (len(INTERVALS) + 1)
    for cid, (box, _) in rows.items():
        if cid in by_id and 0 <= box <= len(INTERVALS):
            boxes[box] += 1
    return {"cards": [{**c.__dict__, "box": rows[c.id][0] if c.id in rows else None} for c in due + fresh],
            "boxes": boxes, "total": len(studied), "unseen": sum(1 for c in studied if c.id not in rows)}
