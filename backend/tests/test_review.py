from datetime import date, timedelta

from app.review import due_reviews, record_answer

D1 = date(2026, 1, 1)
D2 = D1 + timedelta(days=1)


def test_wrong_answer_due_tomorrow(db):
    record_answer(db, "q1", False, D1)
    assert due_reviews(db, D1) == []
    assert due_reviews(db, D2) == ["q1"]


def test_correct_answers_climb_boxes(db):
    record_answer(db, "q1", False, D1)
    record_answer(db, "q1", True, D2)
    assert due_reviews(db, D2 + timedelta(days=1)) == []
    assert due_reviews(db, D2 + timedelta(days=2)) == ["q1"]


def test_wrong_again_resets_box(db):
    record_answer(db, "q1", False, D1)
    record_answer(db, "q1", True, D2)
    d3 = D2 + timedelta(days=2)
    record_answer(db, "q1", False, d3)
    assert due_reviews(db, d3) == []
    assert due_reviews(db, d3 + timedelta(days=1)) == ["q1"]


def test_never_seen_question_not_due(db):
    assert due_reviews(db, D1) == []


def test_correct_untracked_is_noop(db):
    record_answer(db, "q1", True, D1)
    assert db.execute("SELECT COUNT(*) FROM mistakes").fetchone()[0] == 0


def test_mastered_removed(db):
    record_answer(db, "q1", False, D1)
    d = D1
    for _ in range(5):  # boxes 0->1..4, then 4->mastered
        d += timedelta(days=30)
        record_answer(db, "q1", True, d)
    assert db.execute("SELECT COUNT(*) FROM mistakes").fetchone()[0] == 0


def test_most_overdue_first(db):
    record_answer(db, "b", False, D1)
    record_answer(db, "a", False, D2)
    assert due_reviews(db, D2 + timedelta(days=5)) == ["b", "a"]
