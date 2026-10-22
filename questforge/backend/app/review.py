from __future__ import annotations
import sqlite3
from datetime import date, timedelta

BOX_INTERVALS = [1, 2, 4, 7, 14]


def record_answer(db: sqlite3.Connection, question_id: str, correct: bool, today: date) -> None:
    row = db.execute("SELECT box FROM mistakes WHERE question_id = ?", (question_id,)).fetchone()

    if not correct:
        # Faux -> boîte 0, échéance demain (+1 jour)
        box = 0
        interval = BOX_INTERVALS[0]
        next_review = today + timedelta(days=interval)
        db.execute(
            """
            INSERT INTO mistakes (question_id, box, next_review) VALUES (?, ?, ?)
            ON CONFLICT(question_id) DO UPDATE SET box = excluded.box, next_review = excluded.next_review
            """,
            (question_id, box, next_review.isoformat()),
        )
    else:
        if row is not None:
            cur_box = row["box"]
            next_box = min(len(BOX_INTERVALS) - 1, cur_box + 1)
            interval = BOX_INTERVALS[next_box]
            next_review = today + timedelta(days=interval)
            db.execute(
                """
                UPDATE mistakes SET box = ?, next_review = ? WHERE question_id = ?
                """,
                (next_box, next_review.isoformat(), question_id),
            )
    db.commit()


def due_reviews(db: sqlite3.Connection, today: date) -> list[str]:
    rows = db.execute(
        """
        SELECT question_id FROM mistakes
        WHERE next_review <= ?
        ORDER BY next_review ASC, box ASC
        """,
        (today.isoformat(),),
    ).fetchall()
    return [row["question_id"] for row in rows]
