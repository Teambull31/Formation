from __future__ import annotations
import sqlite3
from random import Random


class NoTokens(Exception):
    pass


def add_tokens(db: sqlite3.Connection, n: int) -> None:
    db.execute(
        """
        INSERT INTO tokens (id, count) VALUES (1, ?)
        ON CONFLICT(id) DO UPDATE SET count = max(0, count + ?)
        """,
        (max(0, n), n),
    )
    db.commit()


def pull(
    db: sqlite3.Connection,
    pool: list[dict],
    rng: Random | None = None,
) -> dict:
    if rng is None:
        rng = Random()

    row = db.execute("SELECT count FROM tokens WHERE id = 1").fetchone()
    current_tokens = row["count"] if row else 0

    if current_tokens < 1:
        raise NoTokens("Solde de jetons insuffisant pour une invocation.")

    # Déduction du jeton
    db.execute("UPDATE tokens SET count = count - 1 WHERE id = 1")

    # Tirage pondéré
    commons = [i for i in pool if i.get("rarity") == "common"]
    rares = [i for i in pool if i.get("rarity") == "rare"]
    epics = [i for i in pool if i.get("rarity") == "epic"]

    roll = rng.random()
    if roll < 0.70 and commons:
        chosen_pool = commons
    elif roll < 0.95 and rares:
        chosen_pool = rares
    elif epics:
        chosen_pool = epics
    else:
        chosen_pool = pool

    item = rng.choice(chosen_pool)

    # Ajout à l'inventaire
    item_id = item["id"]
    inv_row = db.execute("SELECT count FROM inventory WHERE item_id = ?", (item_id,)).fetchone()
    if inv_row:
        db.execute("UPDATE inventory SET count = count + 1 WHERE item_id = ?", (item_id,))
    else:
        db.execute(
            """
            INSERT INTO inventory (item_id, name, type, rarity, count)
            VALUES (?, ?, ?, ?, 1)
            """,
            (item_id, item["name"], item["type"], item["rarity"]),
        )
    db.commit()

    return item
