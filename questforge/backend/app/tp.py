from __future__ import annotations
import os
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from app.content import Tp

MAX_OUTPUT_CHARS = 4000


@dataclass
class CheckResult:
    passed: bool
    output: str


def run_check(tp: Tp, workspace: Path | str, lesson_dir: Path | str) -> CheckResult:
    ws_path = Path(workspace).resolve()
    les_dir = Path(lesson_dir).resolve()
    ws_path.mkdir(parents=True, exist_ok=True)

    # Determine command
    possible_script = les_dir / tp.check
    if possible_script.is_file():
        cmd = ["bash", str(possible_script.resolve())]
    elif Path(tp.check).is_file():
        cmd = ["bash", str(Path(tp.check).resolve())]
    else:
        cmd = ["bash", "-c", tp.check]

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(ws_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, _ = proc.communicate(timeout=tp.timeout_s)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                pass
            proc.communicate()
            return CheckResult(passed=False, output=f"Erreur: délai d'exécution dépassé (timeout {tp.timeout_s}s)")
    except Exception as e:
        return CheckResult(passed=False, output=f"Erreur lors de l'exécution: {e}")

    output = stdout or ""
    if len(output) > MAX_OUTPUT_CHARS:
        output = output[:MAX_OUTPUT_CHARS] + "\n... [sortie tronquée]"

    return CheckResult(
        passed=(proc.returncode == 0),
        output=output,
    )
