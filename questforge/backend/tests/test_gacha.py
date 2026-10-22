import json
from pathlib import Path
from random import Random
import pytest
from app.db import connect
from app.progress import get_profile
from app.gacha import add_tokens, pull, NoTokens

GACHA_FILE = Path(__file__).resolve().parent.parent.parent / "content" / "gacha.json"
POOL = json.loads(GACHA_FILE.read_text(encoding="utf-8"))

@pytest.fixture
def db():
    return connect(":memory:")

def test_pull_spends_one_token_and_returns_item(db):
    add_tokens(db, 2)
    item = pull(db, POOL, Random(1))
    assert get_profile(db).tokens == 1
    assert item in POOL

def test_pull_with_zero_tokens_raises_and_balance_stays_zero(db):
    with pytest.raises(NoTokens):
        pull(db, POOL, Random(1))
    assert get_profile(db).tokens == 0

def test_seeded_rng_is_deterministic(db):
    add_tokens(db, 5)
    item1 = pull(db, POOL, Random(42))
    # Reset db and pull with same seed
    db2 = connect(":memory:")
    add_tokens(db2, 5)
    item2 = pull(db2, POOL, Random(42))
    assert item1["id"] == item2["id"]

def test_pool_has_no_lesson_content():
    assert len(POOL) >= 8
    assert all(i["type"] in {"character", "skin"} for i in POOL)
