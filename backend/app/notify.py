"""Rappel quotidien, à lancer par un timer : `python -m app.notify` (FORMATION_DB comme l'appli)."""
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

from app.content import ModuleError, load_module
from app.db import connect
from app.plan import load_plan, today_line
from app.push import remind, streak_saver, tp_digest, weekly_digest
from app.quests import current_streak, pending_tps
from app.review import due_reviews


def modules(content: Path) -> list:
    out = []
    for d in sorted((content / "modules").glob("*/")):
        try:
            out.append(load_module(d))
        except ModuleError:
            continue
    return out


def question_of_day(db, content: Path, today) -> str | None:
    """Texte de la première question de révision due aujourd'hui, ou None."""
    due = due_reviews(db, today)
    if not due:
        return None
    for mod in modules(content):
        for les in mod.lessons:
            for q in les.qcm:
                if q.id == due[0]:
                    return q.text
    return None


def main() -> int:
    db = connect(os.environ.get("FORMATION_DB", str(Path.home() / ".formation" / "formation.db")))
    now = datetime.now(ZoneInfo(os.environ.get("FORMATION_TZ", "Europe/Paris")))
    today = now.date()
    content = Path(os.environ.get("FORMATION_CONTENT", Path(__file__).resolve().parents[2] / "content"))
    try:
        line = today_line(db, load_plan(content), today)
    except (OSError, ValueError):  # plan illisible : le rappel part quand même
        line = None
    n = remind(db, today, current_streak(db, today), plan_line=line, hour=now.hour,
               question=question_of_day(db, content, today))
    n += weekly_digest(db, today, hour=now.hour)
    n += streak_saver(db, today, current_streak(db, today), hour=now.hour)
    n += tp_digest(db, today, [lid for m in modules(content) for lid in pending_tps(db, m)], hour=now.hour)
    print(f"{n} notification(s) envoyée(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
