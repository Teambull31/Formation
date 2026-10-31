import json
from pathlib import Path

from app.boss import attempt_boss, count_attempts

BOSS_DIR = Path(__file__).parent / "fixtures" / "demo_boss"
BOSS = json.loads((BOSS_DIR / "boss.json").read_text())


def test_boss_stops_at_first_failed_phase(db, tmp_path):
    (tmp_path / "phase1.txt").touch()
    r = attempt_boss(db, BOSS, tmp_path, BOSS_DIR)
    assert not r.won and r.phase_reached == 2
    assert r.failed_pattern == "state_drift" and r.remedial_lesson_id == "l1"
    assert isinstance(r.output, str)


def test_boss_win(db, tmp_path):
    for i in (1, 2, 3):
        (tmp_path / f"phase{i}.txt").touch()
    r = attempt_boss(db, BOSS, tmp_path, BOSS_DIR)
    assert r.won and r.phase_reached == 3
    assert r.failed_pattern is None and r.remedial_lesson_id is None and r.output == ""
    assert db.execute("SELECT won FROM boss_attempts").fetchone()["won"] == 1


def test_boss_failure_returns_the_bounded_output_of_the_failed_phase(db, tmp_path):
    boss = {"id": "b", "phases": [
        {"pattern_id": "p1", "label": "un", "check": "echo ok"},
        {"pattern_id": "p2", "label": "deux", "check": "echo 'ECHEC : scénario k'; head -c 9000 /dev/zero | tr '\\0' x; exit 1"}]}
    r = attempt_boss(db, boss, tmp_path, tmp_path)
    assert not r.won and r.phase_reached == 2
    assert r.output.startswith("ECHEC : scénario k") and r.output.endswith("[... sortie tronquée ...]") and len(r.output) < 4100


def test_boss_unlimited_attempts(db, tmp_path):
    for _ in range(5):
        attempt_boss(db, BOSS, tmp_path, BOSS_DIR)
    assert count_attempts(db) == 5
    assert db.execute("SELECT failed_pattern FROM boss_attempts").fetchone()["failed_pattern"] == "crashloop"
