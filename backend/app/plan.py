"""Plan de 30 jours (content/plan.json) : jour courant, jours faits, retard."""
import json
import sqlite3
from datetime import date
from pathlib import Path


def load_plan(content_dir: Path) -> list[dict]:
    path = Path(content_dir) / "plan.json"
    if not path.is_file():
        return []
    days = json.loads(path.read_text(encoding="utf-8"))
    for n, d in enumerate(days, 1):
        if d.get("day") != n or not isinstance(d.get("title"), str) or not isinstance(d.get("lessons", []), list) \
                or not isinstance(d.get("todo", []), list):
            raise ValueError(f"{path}: jour {n} invalide")
    return days


def _setting(db: sqlite3.Connection, key: str) -> str | None:
    row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def start(db: sqlite3.Connection, today: date) -> None:
    db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES ('plan_start', ?)", (today.isoformat(),))
    db.execute("DELETE FROM settings WHERE key LIKE 'plan_done:%'")
    db.commit()


def mark(db: sqlite3.Connection, day: int, done: bool) -> None:
    if done:
        db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, '1')", (f"plan_done:{day}",))
    else:
        db.execute("DELETE FROM settings WHERE key = ?", (f"plan_done:{day}",))
    db.commit()


def status(db: sqlite3.Connection, days: list[dict], today: date, lesson_done) -> dict:
    """lesson_done(lesson_id) -> bool : toutes les étapes applicables de la leçon sont faites."""
    s = _setting(db, "plan_start")
    current = (today - date.fromisoformat(s)).days + 1 if s else None
    out = []
    for d in days:
        lessons = d.get("lessons", [])
        manual = _setting(db, f"plan_done:{d['day']}") is not None
        done = manual or (bool(lessons) and all(lesson_done(lid) for lid in lessons))
        out.append({**d, "lessons": lessons, "todo": d.get("todo", []), "done": done, "manual": manual})
    late = sum(1 for d in out if current is not None and d["day"] < current and not d["done"])
    return {"started": s is not None, "start": s, "today": current, "days": out, "late": late}


def today_line(db: sqlite3.Connection, days: list[dict], today: date) -> str | None:
    """Ligne du rappel push : le titre du jour du plan, s'il est commencé et pas fini."""
    s = _setting(db, "plan_start")
    if not s:
        return None
    n = (today - date.fromisoformat(s)).days + 1
    return f"Jour {n}/{len(days)} : {days[n - 1]['title']}" if 1 <= n <= len(days) else None
