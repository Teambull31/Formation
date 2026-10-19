import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS skills(skill TEXT PRIMARY KEY, xp INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS quest_steps(
    day TEXT, kind TEXT, lesson_id TEXT, done INTEGER,
    PRIMARY KEY(day, kind, lesson_id));
CREATE TABLE IF NOT EXISTS activity_days(day TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS rest_days(day TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS mistakes(question_id TEXT PRIMARY KEY, box INTEGER, due TEXT);
CREATE TABLE IF NOT EXISTS tokens(
    id INTEGER PRIMARY KEY CHECK(id=1),
    count INTEGER NOT NULL CHECK(count>=0));
INSERT OR IGNORE INTO tokens(id, count) VALUES (1, 0);
CREATE TABLE IF NOT EXISTS inventory(
    item_id TEXT, name TEXT, type TEXT, rarity TEXT, obtained_at TEXT);
CREATE TABLE IF NOT EXISTS boss_attempts(
    id INTEGER PRIMARY KEY AUTOINCREMENT, boss_id TEXT, phase_reached INTEGER,
    won INTEGER, failed_pattern TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
"""


def connect(path: str) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    db.commit()
    return db
