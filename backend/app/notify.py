"""Rappel quotidien, à lancer par un timer : `python -m app.notify` (FORMATION_DB comme l'appli)."""
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

from app.db import connect
from app.plan import load_plan, today_line
from app.push import remind
from app.quests import current_streak


def main() -> int:
    db = connect(os.environ.get("FORMATION_DB", str(Path.home() / ".formation" / "formation.db")))
    now = datetime.now(ZoneInfo(os.environ.get("FORMATION_TZ", "Europe/Paris")))
    today = now.date()
    content = Path(os.environ.get("FORMATION_CONTENT", Path(__file__).resolve().parents[2] / "content"))
    try:
        line = today_line(db, load_plan(content), today)
    except (OSError, ValueError):  # plan illisible : le rappel part quand même
        line = None
    n = remind(db, today, current_streak(db, today), plan_line=line, hour=now.hour)
    print(f"{n} notification(s) envoyée(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
