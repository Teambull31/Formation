from datetime import date, timedelta
from pathlib import Path

import pytest

from app.content import load_module
from app.progress import get_profile
from app.quests import (announce_rest, build_daily_quest, complete_step,
                        current_streak, set_imposed_topic)

D1 = date(2026, 1, 1)
D2, D3 = D1 + timedelta(days=1), D1 + timedelta(days=2)


@pytest.fixture
def demo():
    return load_module(Path(__file__).parent / "fixtures" / "demo_module")


def activity(db, day, lesson="l1", kind="lesson"):
    complete_step(db, day, kind, lesson, "demo")


def finish_all(db, demo, day, lesson="l1"):
    for k in ("lesson", "qcm", "tp"):
        complete_step(db, day, k, lesson, "demo")


def test_default_quest_has_three_steps_30min(db, demo):
    q = build_daily_quest(db, demo, D1)
    assert [s.kind for s in q.steps] == ["lesson", "qcm", "tp"]
    assert sum(s.minutes for s in q.steps) == 30 and q.bonus is None
    assert [s.xp for s in q.steps] == [20, 40, 80]


def test_60min_adds_bonus(db, demo):
    b = build_daily_quest(db, demo, D1, 60).bonus
    assert b.xp == 150 and b.kind == "bonus" and b.lesson_id == "l2"


def test_completed_lesson_moves_quest_to_next(db, demo):
    finish_all(db, demo, D1)
    q = build_daily_quest(db, demo, D2)
    assert q.steps[0].lesson_id == "l2"
    assert build_daily_quest(db, demo, D2, 60).bonus is None


def test_all_finished_gives_empty_quest(db, demo):
    finish_all(db, demo, D1, "l1")
    finish_all(db, demo, D1, "l2")
    q = build_daily_quest(db, demo, D2, 60)
    assert q.steps == [] and q.bonus is None


def test_complete_step_awards_xp_once_and_marks_done(db, demo):
    activity(db, D1)
    activity(db, D1)
    assert get_profile(db).skills["demo"] == 20
    assert build_daily_quest(db, demo, D1).steps[0].done


def test_streak_counts_consecutive_days(db):
    activity(db, D1)
    activity(db, D2, "l2")
    assert current_streak(db, D2) == 2


def test_announced_rest_keeps_streak(db):
    activity(db, D1)
    announce_rest(db, D2)
    activity(db, D3, "l2")
    assert current_streak(db, D3) == 2


def test_unannounced_gap_resets_streak(db):
    activity(db, D1)
    activity(db, D3, "l2")
    assert current_streak(db, D3) == 1


def test_imposed_topic_does_not_break_streak(db):
    activity(db, D1)
    set_imposed_topic(db, "Helm", D2)
    assert current_streak(db, D2) == 1
    activity(db, D3, "l2")
    assert current_streak(db, D3) == 2


def test_cleared_topic_stops_covering(db):
    activity(db, D1)
    set_imposed_topic(db, "Helm", D2)
    set_imposed_topic(db, None, D2)
    d = D1 + timedelta(days=3)
    activity(db, d, "l2")
    assert current_streak(db, d) == 1


def test_imposed_topic_in_quest(db, demo):
    set_imposed_topic(db, "Helm", D1)
    assert build_daily_quest(db, demo, D1).imposed_topic == "Helm"
    set_imposed_topic(db, None, D1)
    assert build_daily_quest(db, demo, D1).imposed_topic is None


def test_many_rest_days_never_penalized(db):
    activity(db, D1)
    for i in range(1, 8):
        announce_rest(db, D1 + timedelta(days=i))
    d = D1 + timedelta(days=8)
    activity(db, d, "l2")
    assert current_streak(db, d) == 2


def test_replaced_topic_keeps_first_period_covered(db):
    activity(db, D1)
    set_imposed_topic(db, "A", D2)
    set_imposed_topic(db, None, D2)
    set_imposed_topic(db, "B", D3)
    d4 = D1 + timedelta(days=3)
    activity(db, d4, "l2")
    assert current_streak(db, d4) == 2  # D2 (A) and D3 (B) covered


def test_resetting_same_topic_keeps_start(db):
    activity(db, D1)
    set_imposed_topic(db, "A", D2)
    set_imposed_topic(db, "A", D3)
    d4 = D1 + timedelta(days=3)
    activity(db, d4, "l2")
    assert current_streak(db, d4) == 2


def test_clear_without_active_topic_is_noop(db):
    activity(db, D1)
    set_imposed_topic(db, None, D2)
    set_imposed_topic(db, None, D3)
    activity(db, D3, "l2")
    assert current_streak(db, D3) == 1
    set_imposed_topic(db, "A", D2)
    set_imposed_topic(db, None, D2)
    set_imposed_topic(db, None, D3)  # second clear must not extend coverage
    d5 = D1 + timedelta(days=4)
    activity(db, d5, "l2")
    assert current_streak(db, d5) == 1


def _bare(demo, no_tp=False, no_qcm=False):
    import dataclasses
    les = [dataclasses.replace(l, tp=None if no_tp else l.tp, qcm=[] if no_qcm else l.qcm) for l in demo.lessons]
    return dataclasses.replace(demo, lessons=les)


def test_quest_only_applicable_steps_and_advances(db, demo):
    m = _bare(demo, no_tp=True)
    q = build_daily_quest(db, m, D1)
    assert [s.kind for s in q.steps] == ["lesson", "qcm"]
    for k in ("lesson", "qcm"):
        complete_step(db, D1, k, "l1", "demo", ("lesson", "qcm"))
    assert build_daily_quest(db, m, D2).steps[0].lesson_id == "l2"


def test_empty_qcm_lesson_completes(db, demo):
    m = _bare(demo, no_qcm=True)
    assert [s.kind for s in build_daily_quest(db, m, D1).steps] == ["lesson", "tp"]
    for k in ("lesson", "tp"):
        complete_step(db, D1, k, "l1", "demo", ("lesson", "tp"))
    assert build_daily_quest(db, m, D2).steps[0].lesson_id == "l2"


def tokens(db):
    return get_profile(db).tokens


def test_token_when_all_applicable_steps_done_once(db):
    complete_step(db, D1, "lesson", "l1", "demo")
    complete_step(db, D1, "qcm", "l1", "demo")
    assert tokens(db) == 0
    complete_step(db, D1, "tp", "l1", "demo")
    assert tokens(db) == 1
    complete_step(db, D1, "tp", "l1", "demo")
    assert tokens(db) == 1


def test_token_with_reduced_kinds(db):
    complete_step(db, D1, "lesson", "l1", "demo", ("lesson",))
    assert tokens(db) == 1


def test_bonus_gives_one_token_once(db):
    complete_step(db, D1, "bonus", "l2", "demo")
    complete_step(db, D1, "bonus", "l2", "demo")
    assert tokens(db) == 1
