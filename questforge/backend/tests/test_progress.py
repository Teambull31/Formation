import pytest
from app.db import connect
from app.progress import level_for_xp, rank_for_total_xp, award_xp, get_profile, RANKS

@pytest.fixture
def db():
    return connect(":memory:")

def test_level_for_xp():
    assert [level_for_xp(x) for x in (0, 49, 50, 200)] == [1, 1, 2, 3]

def test_rank_thresholds():
    assert rank_for_total_xp(999) == "Bronze"
    assert rank_for_total_xp(1000) == "Argent"
    assert rank_for_total_xp(2000) == "Or"
    assert rank_for_total_xp(3000) == "Platine"
    assert rank_for_total_xp(4000) == "Expert"
    assert rank_for_total_xp(9999) == "Expert"

def test_award_xp_accumulates_per_skill(db):
    award_xp(db, "docker", 40)
    award_xp(db, "docker", 10)
    assert get_profile(db).skills["docker"] == 50
    assert get_profile(db).total_xp == 50

def test_xp_never_negative(db):
    award_xp(db, "docker", 5)
    award_xp(db, "docker", -10)
    assert get_profile(db).skills["docker"] == 0
    assert get_profile(db).total_xp == 0
