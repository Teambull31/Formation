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


def test_first_right_answer_comes_back_in_a_week(db):
    record_answer(db, "q1", True, D1)
    assert due_reviews(db, D1 + timedelta(days=6)) == []
    assert due_reviews(db, D1 + timedelta(days=7)) == ["q1"]
    record_answer(db, "q1", True, D1 + timedelta(days=7))  # box 3 -> 4
    record_answer(db, "q1", True, D1 + timedelta(days=21))  # 4 -> 5 : revient dans 30 jours, pas encore retirée
    assert due_reviews(db, D1 + timedelta(days=50)) == [] and due_reviews(db, D1 + timedelta(days=51)) == ["q1"]
    record_answer(db, "q1", True, D1 + timedelta(days=51))  # 5 -> 6 : dans 60 jours
    record_answer(db, "q1", True, D1 + timedelta(days=111))  # au-delà de la dernière boîte : maîtrisée
    assert db.execute("SELECT COUNT(*) FROM mistakes").fetchone()[0] == 0
    assert tuple(db.execute("SELECT COUNT(*), SUM(correct) FROM review_log").fetchone()) == (4, 4)  # 1re réponse : pas une révision


def test_mastered_removed(db):
    record_answer(db, "q1", False, D1)
    d = D1
    for _ in range(7):  # boxes 0->1..6, then 6->mastered
        d += timedelta(days=30)
        record_answer(db, "q1", True, d)
    assert db.execute("SELECT COUNT(*) FROM mistakes").fetchone()[0] == 0


def test_most_overdue_first(db):
    record_answer(db, "b", False, D1)
    record_answer(db, "a", False, D2)
    assert due_reviews(db, D2 + timedelta(days=5)) == ["b", "a"]


def test_confident_mistake_comes_back_today_and_guess_is_not_known(db):
    record_answer(db, "q1", False, D1, confident=True)
    assert due_reviews(db, D1) == ["q1"]
    record_answer(db, "q2", True, D1, confident=False)
    assert "q2" in due_reviews(db, D2) and "q2" not in due_reviews(db, D1)  # devinée : revient demain, pas dans 7 jours
    assert db.execute("SELECT box FROM mistakes WHERE question_id='q2'").fetchone()[0] == 0
