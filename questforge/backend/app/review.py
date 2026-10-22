from __future__ import annotations
import sqlite3
from datetime import date, timedelta

BOX_INTERVALS = [1, 2, 4, 7, 14]


REVIEW_XP = 15


def record_answer(db: sqlite3.Connection, question_id: str, correct: bool, today: date) -> bool:
    """Enregistre une réponse. Renvoie True si c'est une révision réussie (question ratée
    auparavant, arrivée à échéance, cette fois correcte) : seule celle-ci donne de l'XP."""
    row = db.execute("SELECT box, next_review FROM mistakes WHERE question_id = ?", (question_id,)).fetchone()
    review_success = bool(correct and row is not None and row["next_review"] <= today.isoformat())

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
    return review_success


def box_counts(db: sqlite3.Connection) -> list[int]:
    counts = [0] * len(BOX_INTERVALS)
    for row in db.execute("SELECT box, COUNT(*) AS n FROM mistakes GROUP BY box"):
        counts[min(row["box"], len(counts) - 1)] += row["n"]
    return counts


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


def weak_notions(db: sqlite3.Connection, limit: int = 10) -> list[str]:
    """Questions ratées et pas encore consolidées (boîtes 0 à 2), les plus fragiles d'abord.

    Contrairement à due_reviews, une erreur du jour est incluse : elle n'est révisable que
    demain, mais c'est déjà une notion à renforcer pour préparer la semaine.
    """
    rows = db.execute(
        """
        SELECT question_id FROM mistakes
        WHERE box <= 2
        ORDER BY box ASC, next_review ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [row["question_id"] for row in rows]
