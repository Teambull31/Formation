import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS skills_xp (
    skill TEXT PRIMARY KEY,
    xp INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tokens (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS quest_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day TEXT NOT NULL,
    kind TEXT NOT NULL,
    lesson_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity_days (
    day TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS rest_days (
    day TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS mistakes (
    question_id TEXT PRIMARY KEY,
    box INTEGER NOT NULL DEFAULT 0,
    next_review TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id TEXT NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    rarity TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS boss_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    boss_id TEXT NOT NULL,
    won INTEGER NOT NULL,
    phase_reached INTEGER NOT NULL,
    failed_pattern TEXT,
    remedial_lesson_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

def connect(path: str | Path = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    # Ensure tokens row exists
    conn.execute("INSERT OR IGNORE INTO tokens (id, count) VALUES (1, 0)")
    conn.commit()
    return conn
