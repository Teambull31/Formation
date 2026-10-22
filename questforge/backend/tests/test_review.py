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
