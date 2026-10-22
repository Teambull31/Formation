from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from app.content import Tp
from app.tp import run_check


@dataclass
class BossResult:
    won: bool
    phase_reached: int
    failed_pattern: str | None
    remedial_lesson_id: str | None


def count_attempts(db: sqlite3.Connection, boss_id: str | None = None) -> int:
    if boss_id:
        row = db.execute("SELECT COUNT(*) AS c FROM boss_attempts WHERE boss_id = ?", (boss_id,)).fetchone()
    else:
        row = db.execute("SELECT COUNT(*) AS c FROM boss_attempts").fetchone()
    return row["c"] if row else 0


def attempt_boss(
    db: sqlite3.Connection,
    boss: dict,
    workspace: Path | str,
    boss_dir: Path | str,
) -> BossResult:
    boss_id = boss.get("id", "boss")
    phases = boss.get("phases", [])
    now_iso = datetime.now(timezone.utc).isoformat()

    for idx, phase in enumerate(phases):
        phase_num = idx + 1
        pattern_id = phase.get("pattern_id", f"phase_{phase_num}")
        check_cmd = phase.get("check", "exit 0")
        remedial = phase.get("remedial_lesson_id")

        synthetic_tp = Tp(
            id=f"{boss_id}_{pattern_id}",
            title=phase.get("label", pattern_id),
            instructions_md="",
            check=check_cmd,
            hints=[],
            timeout_s=10,
        )

        res = run_check(synthetic_tp, workspace, boss_dir)
        if not res.passed:
            db.execute(
                """
                INSERT INTO boss_attempts (boss_id, won, phase_reached, failed_pattern, remedial_lesson_id, created_at)
                VALUES (?, 0, ?, ?, ?, ?)
                """,
                (boss_id, phase_num, pattern_id, remedial, now_iso),
            )
            db.commit()
            return BossResult(
                won=False,
                phase_reached=phase_num,
                failed_pattern=pattern_id,
                remedial_lesson_id=remedial,
            )

    total_phases = len(phases)
    db.execute(
        """
        INSERT INTO boss_attempts (boss_id, won, phase_reached, failed_pattern, remedial_lesson_id, created_at)
        VALUES (?, 1, ?, NULL, NULL, ?)
        """,
        (boss_id, total_phases, now_iso),
    )
    db.commit()

    return BossResult(
        won=True,
        phase_reached=total_phases,
        failed_pattern=None,
        remedial_lesson_id=None,
    )
