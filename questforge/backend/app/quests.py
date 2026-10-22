from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from app.content import Module, Lesson
from app.progress import award_xp

StepKind = Literal["lesson", "qcm", "tp", "bonus"]

XP_MAP: dict[StepKind, int] = {
    "lesson": 20,
    "qcm": 40,
    "tp": 80,
    "bonus": 150,
}


@dataclass
class Step:
    kind: StepKind
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


def build_daily_quest(
    db: sqlite3.Connection,
    module: Module,
    today: date,
    minutes: int = 30,
) -> Quest:
    today_str = today.isoformat()

    # Get completed steps for today or previously
    rows = db.execute("SELECT kind, lesson_id, day FROM quest_steps").fetchall()
    completed_keys = {(r["lesson_id"], r["kind"]) for r in rows}
    completed_today = {(r["lesson_id"], r["kind"]) for r in rows if r["day"] == today_str}

    # Find first lesson not fully completed
    target_idx = 0
    for idx, les in enumerate(module.lessons):
        req_steps = {"lesson", "qcm"}
        if les.tp:
            req_steps.add("tp")
        all_done = all((les.id, k) in completed_keys for k in req_steps)
        if not all_done:
            target_idx = idx
            break
    else:
        target_idx = max(0, len(module.lessons) - 1)

    cur_lesson = module.lessons[target_idx]

    # Standard 30 min quest: 3 steps (lesson, qcm, tp)
    steps: list[Step] = [
        Step(
            kind="lesson",
            lesson_id=cur_lesson.id,
            minutes=10,
            xp=XP_MAP["lesson"],
            done=(cur_lesson.id, "lesson") in completed_today or (cur_lesson.id, "lesson") in completed_keys,
        ),
        Step(
            kind="qcm",
            lesson_id=cur_lesson.id,
            minutes=10,
            xp=XP_MAP["qcm"],
            done=(cur_lesson.id, "qcm") in completed_today or (cur_lesson.id, "qcm") in completed_keys,
        ),
        Step(
            kind="tp",
            lesson_id=cur_lesson.id,
            minutes=10,
            xp=XP_MAP["tp"],
            done=(cur_lesson.id, "tp") in completed_today or (cur_lesson.id, "tp") in completed_keys,
        ),
    ]

    bonus_step: Step | None = None
    if minutes == 60:
        # 60 min adds bonus step (TP or bonus challenge of next lesson or current lesson)
        bonus_lesson = module.lessons[target_idx + 1] if target_idx + 1 < len(module.lessons) else cur_lesson
        bonus_step = Step(
            kind="bonus",
            lesson_id=bonus_lesson.id,
            minutes=30,
            xp=XP_MAP["bonus"],
            done=(bonus_lesson.id, "bonus") in completed_today or (bonus_lesson.id, "bonus") in completed_keys,
        )

    # Imposed topic check
    topic_row = db.execute("SELECT value FROM settings WHERE key = 'imposed_topic'").fetchone()
    imposed_topic = topic_row["value"] if topic_row else None

    return Quest(
        day=today,
        steps=steps,
        bonus=bonus_step,
        imposed_topic=imposed_topic,
    )


def complete_step(
    db: sqlite3.Connection,
    today: date,
    kind: StepKind,
    lesson_id: str,
    skill: str = "general",
) -> bool:
    # Check if this step is already completed to avoid awarding duplicate XP
    already = db.execute(
        "SELECT 1 FROM quest_steps WHERE kind = ? AND lesson_id = ?",
        (kind, lesson_id),
    ).fetchone()
    if already:
        return False

    xp_to_award = XP_MAP.get(kind, 20)
    award_xp(db, skill, xp_to_award)

    today_str = today.isoformat()
    now_iso = datetime.now(timezone.utc).isoformat()
    db.execute(
        "INSERT INTO quest_steps (day, kind, lesson_id, created_at) VALUES (?, ?, ?, ?)",
        (today_str, kind, lesson_id, now_iso),
    )
    db.execute("INSERT OR IGNORE INTO activity_days (day) VALUES (?)", (today_str,))
    db.commit()
    return True


def announce_rest(db: sqlite3.Connection, day: date) -> None:
    db.execute("INSERT OR IGNORE INTO rest_days (day) VALUES (?)", (day.isoformat(),))
    db.commit()


def set_imposed_topic(db: sqlite3.Connection, topic: str | None) -> None:
    if topic is None or topic.strip() == "":
        db.execute("DELETE FROM settings WHERE key = 'imposed_topic'")
    else:
        db.execute(
            """
            INSERT INTO settings (key, value) VALUES ('imposed_topic', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (topic.strip(),),
        )
    db.commit()


def activity_history(db: sqlite3.Connection, today: date, days: int = 28) -> list[dict]:
    """Activité réelle des `days` derniers jours (étapes validées, jours de repos)."""
    steps_by_day = {
        r["day"]: r["n"] for r in db.execute("SELECT day, COUNT(*) AS n FROM quest_steps GROUP BY day")
    }
    active = {r["day"] for r in db.execute("SELECT day FROM activity_days")}
    rest = {r["day"] for r in db.execute("SELECT day FROM rest_days")}
    history = []
    for offset in range(days - 1, -1, -1):
        day = (today - timedelta(days=offset)).isoformat()
        if day in rest:
            status = "rest"
        elif day in active or steps_by_day.get(day):
            status = "active"
        else:
            status = "idle"
        history.append({"date": day, "count": steps_by_day.get(day, 0), "status": status})
    return history


def current_streak(db: sqlite3.Connection, today: date) -> int:
    act_rows = db.execute("SELECT day FROM activity_days").fetchall()
    if not act_rows:
        return 0
    activity_set = {r["day"] for r in act_rows}
    min_date = min(date.fromisoformat(d) for d in activity_set)

    rest_rows = db.execute("SELECT day FROM rest_days").fetchall()
    rest_set = {r["day"] for r in rest_rows}

    topic_row = db.execute("SELECT value FROM settings WHERE key = 'imposed_topic'").fetchone()
    has_topic = topic_row is not None and bool(topic_row["value"])

    cur = today
    streak = 0

    while cur >= min_date:
        cur_str = cur.isoformat()
        if cur_str in activity_set:
            streak += 1
            cur -= timedelta(days=1)
        elif cur_str in rest_set:
            # Announced rest day does not add to streak count, but keeps it alive
            cur -= timedelta(days=1)
        elif has_topic:
            # Active imposed topic keeps streak alive without breaking
            cur -= timedelta(days=1)
        else:
            break

    return streak

