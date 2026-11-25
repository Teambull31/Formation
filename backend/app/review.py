import sqlite3
from datetime import date, timedelta

INTERVALS = [1, 2, 4, 7, 14]


FIRST_RIGHT_BOX = 3  # réussi du premier coup : revient dans INTERVALS[3] jours, pour vérifier que ça tient


def record_answer(db: sqlite3.Connection, question_id: str, correct: bool, today: date,
                  confident: bool | None = None) -> None:
    """Wrong -> box 0 ; right on a tracked one climbs (past last box = mastered) ; right on an untracked one
    enters a high box : les bonnes réponses aussi reviennent, sinon on les oublie sans le voir.
    `confident` (facultatif) : une erreur commise en étant sûr revient le jour même ; une bonne réponse devinée
    ne compte pas comme sue (elle revient demain, sans monter de boîte)."""
    tracked = db.execute("SELECT box FROM mistakes WHERE question_id=?", (question_id,)).fetchone()
    if tracked is not None:
        db.execute("INSERT INTO review_log(day, correct) VALUES (?, ?)", (today.isoformat(), int(correct)))
    tomorrow = (today + timedelta(days=INTERVALS[0])).isoformat()
    if not correct:
        due = today.isoformat() if confident else tomorrow
        db.execute("INSERT OR REPLACE INTO mistakes(question_id, box, due) VALUES (?, 0, ?)", (question_id, due))
    elif confident is False:  # juste, mais au hasard
        db.execute("INSERT OR REPLACE INTO mistakes(question_id, box, due) VALUES (?, ?, ?)",
                   (question_id, tracked[0] if tracked else 0, tomorrow))
    elif tracked is None:
        due = (today + timedelta(days=INTERVALS[FIRST_RIGHT_BOX])).isoformat()
        db.execute("INSERT INTO mistakes(question_id, box, due) VALUES (?, ?, ?)", (question_id, FIRST_RIGHT_BOX, due))
    else:
        box = tracked[0] + 1
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
