import os
import select
import shutil
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


def _tp_dir(tp: Tp, workspace: Path) -> Path:
    d = Path(workspace) / tp.workspace
    d.mkdir(parents=True, exist_ok=True)
    # the learner owns the workspace: refuse a sub-directory swapped for a link leaving it
    if not d.resolve().is_relative_to(Path(workspace).resolve()):
        raise ValueError(f"Dossier de TP hors du workspace : {tp.workspace}")
    return d


def _copy_new(src: str, dst: str) -> None:
    if not os.path.lexists(dst):  # a dangling learner symlink counts as existing
        shutil.copy2(src, dst)


def _check_dest(d: Path, dst: Path) -> None:
    # learner-owned tree: no symlink may sit between the tp dir and dst (dst included)
    for p in [dst, *dst.parents]:
        if p == d:
            break
        if p.is_symlink():
            raise ValueError(f"Lien symbolique refusé dans le workspace : {p.name}")
    if not dst.parent.resolve().is_relative_to(d.resolve()):
        raise ValueError(f"Destination hors du dossier de TP : {dst.name}")


def seed_workspace(tp: Tp, lesson_dir: Path, workspace: Path) -> Path:
    """Copy tp.seed into workspace/tp.workspace, never overwriting; symlinks are refused."""
    d = _tp_dir(tp, workspace)
    for entry in tp.seed:
        src = Path(lesson_dir) / entry
        links = [src, *src.rglob("*")] if src.is_dir() and not src.is_symlink() else [src]
        if any(p.is_symlink() for p in links):
            raise ValueError(f"Lien symbolique refusé dans le kit : {entry}")
        dst = d / src.resolve().name
        pairs = [(p, dst / p.relative_to(src)) for p in sorted(src.rglob("*"))] if src.is_dir() else []
        for s, t in [(src, dst), *pairs]:
            _check_dest(d, t)
            if s.is_dir():
                t.mkdir(exist_ok=True)
            else:
                _copy_new(str(s), str(t))
    return d


_SECRET = ("PASSWORD", "SECRET", "TOKEN", "KEY")


def child_env(**extra: str) -> dict[str, str]:
    """Environnement des processus enfants (shell, scripts de TP) sans les secrets FORMATION_*."""
    env = {k: v for k, v in os.environ.items()
           if not (k.startswith("FORMATION_") and any(w in k for w in _SECRET))}
    return {**env, **extra}


def run_check(tp: Tp, workspace: Path, lesson_dir: Path) -> CheckResult:
    if not Path(workspace).is_dir():
        return CheckResult(False, f"Workspace introuvable : {workspace}")
    try:
        cwd = _tp_dir(tp, workspace)
    except ValueError as e:
        return CheckResult(False, str(e))
    env = child_env(LESSON_DIR=str(lesson_dir))
    proc = subprocess.Popen(
        ["bash", "-c", tp.check],
        cwd=cwd,
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
