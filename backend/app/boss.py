import sqlite3
from dataclasses import dataclass
from pathlib import Path

from app.content import Tp
from app.tp import run_check


@dataclass
class BossResult:
    won: bool
    phase_reached: int
    failed_pattern: str | None
    remedial_lesson_id: str | None


def attempt_boss(db: sqlite3.Connection, boss: dict, workspace: Path, boss_dir: Path) -> BossResult:
    phases = boss["phases"]
    result = BossResult(True, len(phases), None, None)
    for i, ph in enumerate(phases, 1):
        tp = Tp(id=ph["pattern_id"], title=ph["label"], instructions_md="", check=ph["check"],
                hints=[], timeout_s=ph.get("timeout_s", 30), workspace=".")
        if not run_check(tp, workspace, boss_dir).passed:
            result = BossResult(False, i, ph["pattern_id"], ph.get("remedial_lesson_id"))
            break
    db.execute(
        "INSERT INTO boss_attempts(boss_id, phase_reached, won, failed_pattern, at) "
        "VALUES (?, ?, ?, ?, datetime('now'))",
        (boss["id"], result.phase_reached, int(result.won), result.failed_pattern),
    )
    db.commit()
    return result


def count_attempts(db: sqlite3.Connection, boss_id: str | None = None) -> int:
    if boss_id is None:
        return db.execute("SELECT COUNT(*) AS n FROM boss_attempts").fetchone()["n"]
    return db.execute("SELECT COUNT(*) AS n FROM boss_attempts WHERE boss_id = ?", (boss_id,)).fetchone()["n"]
