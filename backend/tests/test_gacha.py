import json
from collections import Counter
from pathlib import Path
from random import Random

import pytest

from app.gacha import NoTokens, add_tokens, pull
from app.progress import get_profile

POOL = json.loads((Path(__file__).parents[2] / "content" / "gacha.json").read_text(encoding="utf-8"))


def inv(db):
    return [r["item_id"] for r in db.execute("SELECT item_id FROM inventory")]


def test_pool_shape():
    assert len(POOL) >= 8 and len({i["id"] for i in POOL}) == len(POOL)
    rarities = Counter(i["rarity"] for i in POOL)
    assert rarities["epic"] >= 2 and rarities["rare"] >= 3
    assert set(rarities) <= {"common", "rare", "epic"}


def test_pool_has_no_lesson_content():
    assert all(i["type"] in {"character", "skin"} for i in POOL)


def test_pull_spends_one_token_and_returns_item(db):
    add_tokens(db, 2)
    item = pull(db, POOL, Random(1))
    assert get_profile(db).tokens == 1 and item in POOL


def test_pull_adds_to_inventory(db):
    add_tokens(db, 1)
    item = pull(db, POOL, Random(1))
    row = db.execute("SELECT * FROM inventory").fetchone()
    assert (row["item_id"], row["name"], row["type"], row["rarity"]) == (
        item["id"], item["name"], item["type"], item["rarity"])
    assert row["obtained_at"]


def test_pull_with_zero_tokens_raises_and_balance_stays_zero(db):
    with pytest.raises(NoTokens):
        pull(db, POOL, Random(1))
    assert get_profile(db).tokens == 0
    assert inv(db) == []


def test_empty_pool_raises_without_spending(db):
    add_tokens(db, 1)
    with pytest.raises(ValueError):
        pull(db, [], Random(1))
    assert get_profile(db).tokens == 1


def test_add_tokens_rejects_non_positive(db):
    for n in (0, -1):
        with pytest.raises(ValueError):
            add_tokens(db, n)


def test_seeded_rng_is_deterministic(db):
    add_tokens(db, 10)
    r1, r2 = Random(7), Random(7)
    assert [pull(db, POOL, r1)["id"] for _ in range(5)] == [pull(db, POOL, r2)["id"] for _ in range(5)]


def test_duplicates_allowed_and_counted(db):
    add_tokens(db, 3)
    one = [i for i in POOL if i["rarity"] == "common"][:1]
    for _ in range(3):
        pull(db, one, Random(1))
    assert inv(db) == [one[0]["id"]] * 3


def test_distribution_commons_outnumber_epics(db):
    add_tokens(db, 2000)
    rng = Random(42)
    c = Counter(pull(db, POOL, rng)["rarity"] for _ in range(2000))
    assert c["common"] > c["rare"] > c["epic"] > 0
