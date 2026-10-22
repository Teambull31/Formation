from datetime import date, timedelta
import pytest
from app.db import connect
from app.review import record_answer, due_reviews

D1 = date(2026, 10, 1)
D2 = date(2026, 10, 2)

@pytest.fixture
def db():
    return connect(":memory:")

def test_wrong_answer_due_tomorrow(db):
    record_answer(db, "q1", False, D1)
    assert due_reviews(db, D1) == []
    assert due_reviews(db, D2) == ["q1"]

def test_correct_answers_climb_boxes(db):
    record_answer(db, "q1", False, D1)
    record_answer(db, "q1", True, D2)
    # Box 1 has interval 2 days from D2 -> D2 + 2 days
    assert due_reviews(db, D2 + timedelta(days=1)) == []
    assert due_reviews(db, D2 + timedelta(days=2)) == ["q1"]

def test_wrong_again_resets_box(db):
    record_answer(db, "q1", False, D1)
    record_answer(db, "q1", True, D2)
    # Wrong again on D4 resets to box 0, due on D5
    d4 = D2 + timedelta(days=2)
    record_answer(db, "q1", False, d4)
    assert due_reviews(db, d4) == []
    assert due_reviews(db, d4 + timedelta(days=1)) == ["q1"]

def test_never_seen_question_not_due(db):
    assert due_reviews(db, D1) == []


def test_weak_notions_include_todays_mistakes_but_not_consolidated_ones(tmp_path):
    from datetime import date
    from app.db import connect
    from app.review import due_reviews, record_answer, weak_notions

    db = connect(tmp_path / "r.db")
    today = date(2026, 10, 22)
    record_answer(db, "q_new", False, today)
    for _ in range(4):
        record_answer(db, "q_old", False, today)
        record_answer(db, "q_old", True, today)
    for _ in range(3):
        record_answer(db, "q_old", True, today)  # monte jusqu'à la dernière boîte
    # l'erreur du jour n'est pas encore due, mais c'est bien une notion à renforcer
    assert due_reviews(db, today) == []
    assert weak_notions(db) == ["q_new"]


def test_record_answer_reports_review_success_only_when_due(tmp_path):
    from datetime import date, timedelta
    from app.db import connect
    from app.review import record_answer

    db = connect(tmp_path / "s.db")
    d1 = date(2026, 10, 22)
    assert record_answer(db, "q1", True, d1) is False       # jamais ratée : pas une révision
    assert record_answer(db, "q1", False, d1) is False      # erreur
    assert record_answer(db, "q1", True, d1) is False       # retentée le jour même : pas encore due
    assert record_answer(db, "q1", False, d1) is False
    assert record_answer(db, "q1", True, d1 + timedelta(days=1)) is True   # due demain : succès
    assert record_answer(db, "q1", True, d1 + timedelta(days=1)) is False  # plus due : pas de farm


def test_box_counts_has_one_slot_per_box(tmp_path):
    from datetime import date
    from app.db import connect
    from app.review import box_counts, record_answer

    db = connect(tmp_path / "b.db")
    record_answer(db, "qa", False, date(2026, 10, 22))
    record_answer(db, "qb", False, date(2026, 10, 22))
    assert box_counts(db) == [2, 0, 0, 0, 0]
