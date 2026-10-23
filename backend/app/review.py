import sqlite3
from datetime import date, timedelta

INTERVALS = [1, 2, 4, 7, 14]


def record_answer(db: sqlite3.Connection, question_id: str, correct: bool, today: date) -> None:
    """Track mistakes only: wrong -> box 0, correct on a tracked one climbs; past last box = mastered."""
    if not correct:
        due = (today + timedelta(days=INTERVALS[0])).isoformat()
        db.execute("INSERT OR REPLACE INTO mistakes(question_id, box, due) VALUES (?, 0, ?)", (question_id, due))
    else:
        row = db.execute("SELECT box FROM mistakes WHERE question_id=?", (question_id,)).fetchone()
        if row is None:
            return
        box = row[0] + 1
        if box >= len(INTERVALS):
            db.execute("DELETE FROM mistakes WHERE question_id=?", (question_id,))
        else:
            due = (today + timedelta(days=INTERVALS[box])).isoformat()
            db.execute("UPDATE mistakes SET box=?, due=? WHERE question_id=?", (box, due, question_id))
    db.commit()


def due_reviews(db: sqlite3.Connection, today: date) -> list[str]:
    rows = db.execute(
        "SELECT question_id FROM mistakes WHERE due <= ? ORDER BY due, question_id", (today.isoformat(),)
    )
    return [r[0] for r in rows]


def box_counts(db: sqlite3.Connection) -> list[int]:
    """Tracked mistakes per Leitner box (all of them, due or not)."""
    counts = [0] * len(INTERVALS)
    for box, n in db.execute("SELECT box, COUNT(*) FROM mistakes GROUP BY box"):
        if 0 <= box < len(counts):
            counts[box] = n
    return counts
