"""Rappel quotidien, à lancer par un timer : `python -m app.notify` (FORMATION_DB comme l'appli)."""
import os
from datetime import date
from pathlib import Path

from app.db import connect
from app.push import remind
from app.quests import current_streak


def main() -> int:
    db = connect(os.environ.get("FORMATION_DB", str(Path.home() / ".formation" / "formation.db")))
    today = date.today()
    n = remind(db, today, current_streak(db, today))
    print(f"{n} notification(s) envoyée(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
