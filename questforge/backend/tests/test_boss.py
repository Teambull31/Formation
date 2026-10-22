from pathlib import Path
import pytest
from app.db import connect
from app.boss import attempt_boss, count_attempts, BossResult

BOSS_DIR = Path(__file__).parent / "fixtures" / "demo_boss"

@pytest.fixture
def db():
    return connect(":memory:")

@pytest.fixture
def boss_all_pass():
    return {
        "id": "boss1",
        "title": "Pass Boss",
        "phases": [
            {"pattern_id": "p1", "label": "P1", "check": "exit 0", "remedial_lesson_id": "l1"},
            {"pattern_id": "p2", "label": "P2", "check": "exit 0", "remedial_lesson_id": "l2"},
        ]
    }

@pytest.fixture
def boss_fail_on_2():
    return {
        "id": "boss_fail",
        "title": "Fail Boss",
        "phases": [
            {"pattern_id": "p1", "label": "P1", "check": "exit 0", "remedial_lesson_id": "l1"},
            {"pattern_id": "crashloop", "label": "P2 Crash", "check": "exit 1", "remedial_lesson_id": "l2"},
        ]
    }

def test_boss_stops_at_first_failed_phase(db, tmp_path, boss_fail_on_2):
    r = attempt_boss(db, boss_fail_on_2, tmp_path, BOSS_DIR)
    assert not r.won
    assert r.phase_reached == 2
    assert r.failed_pattern == "crashloop"
    assert r.remedial_lesson_id == "l2"

def test_boss_win(db, tmp_path, boss_all_pass):
    r = attempt_boss(db, boss_all_pass, tmp_path, BOSS_DIR)
    assert r.won
    assert r.phase_reached == 2
    assert r.failed_pattern is None

def test_boss_unlimited_attempts(db, tmp_path, boss_fail_on_2):
    for _ in range(5):
        attempt_boss(db, boss_fail_on_2, tmp_path, BOSS_DIR)
    assert count_attempts(db) == 5
