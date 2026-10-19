import random
import sqlite3
from datetime import datetime

WEIGHTS = {"common": 70, "rare": 25, "epic": 5}


class NoTokens(Exception):
    pass


def add_tokens(db: sqlite3.Connection, n: int) -> None:
    if n <= 0:
        raise ValueError("n must be > 0")
    with db:
        db.execute("UPDATE tokens SET count = count + ? WHERE id = 1", (n,))


def pull(db: sqlite3.Connection, pool: list[dict], rng: random.Random) -> dict:
    if not pool:
        raise ValueError("empty pool")
    by_rarity: dict[str, list[dict]] = {}
    for item in pool:
        by_rarity.setdefault(item["rarity"], []).append(item)
    rarities = [r for r in WEIGHTS if r in by_rarity]
    rarity = rng.choices(rarities, [WEIGHTS[r] for r in rarities])[0]
    item = rng.choice(by_rarity[rarity])
    with db:  # one transaction: spend and grant, or neither
        spent = db.execute("UPDATE tokens SET count = count - 1 WHERE id = 1 AND count > 0")
        if spent.rowcount == 0:
            raise NoTokens("no tokens left")
        db.execute(
            "INSERT INTO inventory(item_id, name, type, rarity, obtained_at) VALUES (?,?,?,?,?)",
            (item["id"], item["name"], item["type"], item["rarity"],
             datetime.now().isoformat(timespec="seconds")),
        )
    return item
