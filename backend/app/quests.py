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


def applicable_kinds(lesson) -> tuple[str, ...]:
    return tuple(k for k in KINDS if (k != "tp" or lesson.tp) and (k != "qcm" or lesson.qcm))


def build_daily_quest(db: sqlite3.Connection, module: Module, today: date, minutes: int = 30) -> Quest:
    topic = _setting(db, "imposed_topic")
    ids = [lesson.id for lesson in module.lessons]
    kinds = [applicable_kinds(lesson) for lesson in module.lessons]
    todo = [i for i, lid in enumerate(ids) if not all(_is_done(db, k, lid) for k in kinds[i])]
    if not todo:
        return Quest(today, [], None, topic)
    i = todo[0]
    steps = [_step(db, k, ids[i]) for k in kinds[i]]
    bonus = _step(db, "bonus", ids[i + 1]) if minutes >= 60 and i + 1 < len(ids) else None
    return Quest(today, steps, bonus, topic)


def complete_step(db: sqlite3.Connection, today: date, kind: str, lesson_id: str, skill: str,
                  kinds: tuple[str, ...] = KINDS) -> None:
    first = not _is_done(db, kind, lesson_id)
    db.execute(
        "INSERT OR REPLACE INTO quest_steps(day, kind, lesson_id, done) VALUES (?, ?, ?, 1)",
        (today.isoformat(), kind, lesson_id),
    )
    db.execute("INSERT OR IGNORE INTO activity_days(day) VALUES (?)", (today.isoformat(),))
    if first:
        # one token per finished lesson (all applicable steps) and per bonus; same commit as the XP
        if kind == "bonus" or (kind in kinds and all(_is_done(db, k, lesson_id) for k in kinds)):
            db.execute("UPDATE tokens SET count = count + 1 WHERE id = 1")
        award_xp(db, skill, XP[kind])  # commits the step rows and the XP in one transaction
    else:
        db.commit()


def announce_rest(db: sqlite3.Connection, day: date) -> None:
    db.execute("INSERT OR IGNORE INTO rest_days(day) VALUES (?)", (day.isoformat(),))
    db.commit()


def set_imposed_topic(db: sqlite3.Connection, topic: str | None, today: date) -> None:
    active = db.execute("SELECT 1 FROM imposed_periods WHERE end IS NULL").fetchone() is not None
    if topic is None:
        db.execute("UPDATE imposed_periods SET end = ? WHERE end IS NULL", (today.isoformat(),))
        db.execute("DELETE FROM settings WHERE key = 'imposed_topic'")
    else:
        db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES ('imposed_topic', ?)", (topic,))
        if not active:  # re-setting while active keeps the original start
            db.execute("INSERT INTO imposed_periods(start, end) VALUES (?, NULL)", (today.isoformat(),))
    db.commit()


def current_streak(db: sqlite3.Connection, today: date) -> int:
    active = {r["day"] for r in db.execute("SELECT day FROM activity_days")}
    if not active:
        return 0
    rest = {r["day"] for r in db.execute("SELECT day FROM rest_days")}
    periods = [
        (date.fromisoformat(r["start"]), date.fromisoformat(r["end"]) if r["end"] else today)
        for r in db.execute("SELECT start, end FROM imposed_periods")
    ]

    def covered(d: date) -> bool:
        return d.isoformat() in rest or any(s <= d <= e for s, e in periods)

    first = min(active)
    streak, d = 0, today
    while d.isoformat() >= first:
        if d.isoformat() in active:
            streak += 1
        elif not covered(d) and d != today:
            break
        d -= timedelta(days=1)
    return streak
