import os
import select
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from app.content import Tp

MAX_CHARS = 4000
READ_CAP = 64 * 1024  # bytes kept in memory; the rest is drained and dropped
MARKER = "\n[... sortie tronquée ...]"


@dataclass
class CheckResult:
    passed: bool
    output: str


def _clip(raw: bytes, dropped: bool) -> str:
    text = raw.decode(errors="replace")
    if len(text) > MAX_CHARS or dropped:
        text = text[:MAX_CHARS] + MARKER
    return text


def run_check(tp: Tp, workspace: Path, lesson_dir: Path) -> CheckResult:
    if not Path(workspace).is_dir():
        return CheckResult(False, f"Workspace introuvable : {workspace}")
    env = {**os.environ, "LESSON_DIR": str(lesson_dir)}
    proc = subprocess.Popen(
        ["bash", "-c", tp.check],
        cwd=workspace,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    fd = proc.stdout.fileno()
    buf = b""
    dropped = False
    deadline = time.monotonic() + tp.timeout_s
    timed_out = False
    while True:
        left = deadline - time.monotonic()
        if left <= 0:
            timed_out = True
            break
        if not select.select([fd], [], [], left)[0]:
            continue
        chunk = os.read(fd, 65536)
        if not chunk:
            break
        if len(buf) < READ_CAP:
            buf += chunk[: READ_CAP - len(buf)]
            dropped = dropped or len(buf) == READ_CAP
        else:
            dropped = True
    if timed_out:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    proc.stdout.close()
    proc.wait()
    out = _clip(buf, dropped)
    if timed_out:
        return CheckResult(False, f"Timeout après {tp.timeout_s}s\n{out}")
    return CheckResult(proc.returncode == 0, out)
