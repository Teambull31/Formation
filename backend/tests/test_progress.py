from app.db import connect
from app.progress import RANKS, award_xp, get_profile, level_for_xp, rank_for_total_xp


def test_level_for_xp():
    assert [level_for_xp(x) for x in (0, 49, 50, 200)] == [1, 1, 2, 3]


def test_rank_thresholds():
    assert rank_for_total_xp(999) == "Bronze" and rank_for_total_xp(1000) == "Argent"
    assert rank_for_total_xp(10**6) == RANKS[-1] == "Expert"


def test_award_xp_accumulates_per_skill(db):
    award_xp(db, "docker", 40)
    award_xp(db, "docker", 10)
    assert get_profile(db).skills["docker"] == 50


def test_xp_never_negative(db):
    award_xp(db, "docker", 5)
    award_xp(db, "docker", -10)
    assert get_profile(db).skills["docker"] == 0


def test_profile_totals_and_tokens(db):
    award_xp(db, "docker", 600)
    award_xp(db, "git", 500)
    p = get_profile(db)
    assert (p.total_xp, p.rank, p.tokens) == (1100, "Bronze", 0)  # no boss beaten yet
    assert p.rank_capped
    db.execute("INSERT INTO boss_attempts(boss_id, phase_reached, won, at) VALUES ('b1', 3, 1, 'x')")
    p = get_profile(db)
    assert (p.rank, p.rank_capped) == ("Argent", False)
    db.execute("INSERT INTO boss_attempts(boss_id, phase_reached, won, at) VALUES ('b1', 3, 1, 'y')")
    assert get_profile(db).rank == "Argent"  # same boss twice counts once


def test_connect_idempotent_on_file(tmp_path):
    path = str(tmp_path / "t.db")
    award_xp(connect(path), "git", 7)
    assert get_profile(connect(path)).skills == {"git": 7}
