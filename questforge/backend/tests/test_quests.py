from datetime import date, timedelta
from pathlib import Path
import pytest
from app.content import load_module
from app.db import connect
from app.quests import (
    build_daily_quest,
    complete_step,
    announce_rest,
    set_imposed_topic,
    current_streak,
    Step,
    Quest,
)

DEMO_PATH = Path(__file__).parent / "fixtures" / "demo_module"
D1 = date(2026, 10, 1)
D2 = date(2026, 10, 2)
D3 = date(2026, 10, 3)

@pytest.fixture
def db():
    return connect(":memory:")

@pytest.fixture
def demo():
    return load_module(DEMO_PATH)

def finish_all(db, demo_mod, day: date):
    l1 = demo_mod.lessons[0]
    complete_step(db, day, "lesson", l1.id, demo_mod.skill)
    complete_step(db, day, "qcm", l1.id, demo_mod.skill)
    complete_step(db, day, "tp", l1.id, demo_mod.skill)

def activity(db, day: date):
    db.execute("INSERT OR IGNORE INTO activity_days (day) VALUES (?)", (day.isoformat(),))
    db.commit()

def test_default_quest_has_three_steps_30min(db, demo):
    q = build_daily_quest(db, demo, D1)
    assert [s.kind for s in q.steps] == ["lesson", "qcm", "tp"]
    assert sum(s.minutes for s in q.steps) == 30
    assert q.bonus is None

def test_60min_adds_bonus(db, demo):
    q = build_daily_quest(db, demo, D1, 60)
    assert q.bonus is not None
    assert q.bonus.xp == 150

def test_completed_lesson_moves_quest_to_next(db, demo):
    finish_all(db, demo, D1)
    q = build_daily_quest(db, demo, D2)
    assert q.steps[0].lesson_id == "l2"

def test_streak_counts_consecutive_days(db):
    activity(db, D1)
    activity(db, D2)
    assert current_streak(db, D2) == 2

def test_announced_rest_keeps_streak(db):
    activity(db, D1)
    announce_rest(db, D2)
    activity(db, D3)
    assert current_streak(db, D3) == 2

def test_unannounced_gap_resets_streak(db):
    activity(db, D1)
    activity(db, D3)
    assert current_streak(db, D3) == 1

def test_imposed_topic_does_not_break_streak(db):
    activity(db, D1)
    set_imposed_topic(db, "Helm")
    assert current_streak(db, D2) == 1
    activity(db, D3)
    assert current_streak(db, D3) == 2

def test_many_rest_days_never_penalized(db):
    activity(db, D1)
    for i in range(1, 8):
        announce_rest(db, D1 + timedelta(days=i))
    activity(db, D1 + timedelta(days=8))
    assert current_streak(db, D1 + timedelta(days=8)) == 2
