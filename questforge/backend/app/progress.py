from __future__ import annotations
import sqlite3
from dataclasses import dataclass

RANKS = ["Bronze", "Argent", "Or", "Platine", "Expert"]


def level_for_xp(xp: int) -> int:
    if xp <= 0:
        return 1
    return int((xp / 50) ** 0.5) + 1


def rank_for_total_xp(total: int) -> str:
    if total < 0:
        return RANKS[0]
    idx = total // 1000
    if idx >= len(RANKS):
        idx = len(RANKS) - 1
    return RANKS[idx]


def award_xp(db: sqlite3.Connection, skill: str, amount: int) -> None:
    row = db.execute("SELECT xp FROM skills_xp WHERE skill = ?", (skill,)).fetchone()
    current_xp = row["xp"] if row else 0
    new_xp = max(0, current_xp + amount)
    db.execute(
        """
        INSERT INTO skills_xp (skill, xp) VALUES (?, ?)
        ON CONFLICT(skill) DO UPDATE SET xp = excluded.xp
        """,
        (skill, new_xp),
    )
    db.commit()


@dataclass
class Profile:
    total_xp: int
    rank: str
    skills: dict[str, int]
    tokens: int


def get_profile(db: sqlite3.Connection) -> Profile:
    rows = db.execute("SELECT skill, xp FROM skills_xp").fetchall()
    skills = {row["skill"]: row["xp"] for row in rows}
    total_xp = sum(skills.values())
    rank = rank_for_total_xp(total_xp)

    token_row = db.execute("SELECT count FROM tokens WHERE id = 1").fetchone()
    tokens = token_row["count"] if token_row else 0

    return Profile(
        total_xp=total_xp,
        rank=rank,
        skills=skills,
        tokens=tokens,
    )
