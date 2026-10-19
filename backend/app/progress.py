import sqlite3
from dataclasses import dataclass

RANKS = ["Bronze", "Argent", "Or", "Platine", "Expert"]
XP_PER_RANK = 1000


def level_for_xp(xp: int) -> int:
    return int((xp / 50) ** 0.5) + 1


def rank_for_total_xp(total: int) -> str:
    return RANKS[min(total // XP_PER_RANK, len(RANKS) - 1)]


def award_xp(db: sqlite3.Connection, skill: str, amount: int) -> None:
    db.execute("INSERT OR IGNORE INTO skills(skill, xp) VALUES (?, 0)", (skill,))
    db.execute("UPDATE skills SET xp = MAX(0, xp + ?) WHERE skill = ?", (amount, skill))
    db.commit()


@dataclass
class Profile:
    total_xp: int
    rank: str
    skills: dict[str, int]
    tokens: int


def get_profile(db: sqlite3.Connection) -> Profile:
    skills = {r["skill"]: r["xp"] for r in db.execute("SELECT skill, xp FROM skills")}
    total = sum(skills.values())
    tokens = db.execute("SELECT count FROM tokens WHERE id = 1").fetchone()["count"]
    return Profile(total, rank_for_total_xp(total), skills, tokens)
