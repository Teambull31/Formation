import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from app.content import Module
from app.progress import award_xp

XP = {"lesson": 20, "qcm": 40, "tp": 80, "bonus": 150}
MINUTES = {"lesson": 10, "qcm": 5, "tp": 15, "bonus": 30}
KINDS = ("lesson", "qcm", "tp")


@dataclass
class Step:
    kind: Literal["lesson", "qcm", "tp", "bonus"]
    lesson_id: str
    minutes: int
    xp: int
    done: bool


@dataclass
class Quest:
    day: date
    steps: list[Step]
    bonus: Step | None
    imposed_topic: str | None


def _setting(db: sqlite3.Connection, key: str) -> str | None:
    row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def _is_done(db: sqlite3.Connection, kind: str, lesson_id: str) -> bool:
    return db.execute(
        "SELECT 1 FROM quest_steps WHERE kind = ? AND lesson_id = ? AND done = 1",
        (kind, lesson_id),
    ).fetchone() is not None


def _step(db: sqlite3.Connection, kind: str, lesson_id: str) -> Step:
    return Step(kind, lesson_id, MINUTES[kind], XP[kind], _is_done(db, kind, lesson_id))


def build_daily_quest(db: sqlite3.Connection, module: Module, today: date, minutes: int = 30) -> Quest:
    topic = _setting(db, "imposed_topic")
    ids = [lesson.id for lesson in module.lessons]
    todo = [i for i, lid in enumerate(ids) if not all(_is_done(db, k, lid) for k in KINDS)]
    if not todo:
        return Quest(today, [], None, topic)
    i = todo[0]
    steps = [_step(db, k, ids[i]) for k in KINDS]
    bonus = _step(db, "bonus", ids[i + 1]) if minutes >= 60 and i + 1 < len(ids) else None
    return Quest(today, steps, bonus, topic)


def complete_step(db: sqlite3.Connection, today: date, kind: str, lesson_id: str, skill: str) -> None:
    first = not _is_done(db, kind, lesson_id)
    db.execute(
        "INSERT OR REPLACE INTO quest_steps(day, kind, lesson_id, done) VALUES (?, ?, ?, 1)",
        (today.isoformat(), kind, lesson_id),
    )
    db.execute("INSERT OR IGNORE INTO activity_days(day) VALUES (?)", (today.isoformat(),))
    db.commit()
    if first:
        award_xp(db, skill, XP[kind])


def announce_rest(db: sqlite3.Connection, day: date) -> None:
    db.execute("INSERT OR IGNORE INTO rest_days(day) VALUES (?)", (day.isoformat(),))
    db.commit()


def set_imposed_topic(db: sqlite3.Connection, topic: str | None, today: date) -> None:
    if topic is None:
        db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES ('imposed_end', ?)", (today.isoformat(),))
        db.execute("DELETE FROM settings WHERE key = 'imposed_topic'")
    else:
        db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES ('imposed_topic', ?)", (topic,))
        db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES ('imposed_start', ?)", (today.isoformat(),))
        db.execute("DELETE FROM settings WHERE key = 'imposed_end'")
    db.commit()


def current_streak(db: sqlite3.Connection, today: date) -> int:
    active = {r["day"] for r in db.execute("SELECT day FROM activity_days")}
    if not active:
        return 0
    rest = {r["day"] for r in db.execute("SELECT day FROM rest_days")}
    start, end = _setting(db, "imposed_start"), _setting(db, "imposed_end")
    has_topic = _setting(db, "imposed_topic") is not None
    # shortcut: a single imposed-topic period is tracked; a new one replaces the old
    start_d = date.fromisoformat(start) if start else None
    end_d = date.fromisoformat(end) if end else (today if has_topic else None)

    def covered(d: date) -> bool:
        return d.isoformat() in rest or (start_d is not None and end_d is not None and start_d <= d <= end_d)

    first = min(active)
    streak, d = 0, today
    while d.isoformat() >= first:
        if d.isoformat() in active:
            streak += 1
        elif not covered(d) and d != today:
            break
        d -= timedelta(days=1)
    return streak
