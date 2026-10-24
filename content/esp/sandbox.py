"""Run untrusted learner code (and the compiler) inside bubblewrap, with resource limits.

Isolation: new user/pid/net/ipc/uts/cgroup namespaces, no capabilities, no nested user
namespaces, a root rebuilt from read-only /usr only, minimal /proc and read-only /dev, a
size-capped tmpfs /tmp, and writable access to `cwd` and `rw` only. Fails closed: if bwrap is
missing or cannot build the namespaces, SandboxUnavailable is raised, never a direct run.

Limits are applied by /usr/bin/prlimit INSIDE the sandbox, not by preexec_fn: RLIMIT_NPROC is
counted per user, so set before bwrap it would count every host process of the backend user
(and makes bwrap's own namespace creation fail); set inside, it counts only sandbox processes.
"""
import os
import shutil
import signal
import subprocess
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

# Processes AND threads in the sandbox (bwrap's init counts as one). g++ runs at most ~3 at
# once (driver, cc1plus/as, collect2/ld); the simulator uses one thread per FreeRTOS task.
NPROC = 64
FSIZE_MB = 64  # largest single file: a statically linked simulator binary is a few MB
TMP_MB = 128  # tmpfs /tmp lives in RAM: g++ temporaries for one translation unit fit easily
# Measured with g++ 16: a C++17 file including <iostream>, <thread> and <map> fails to compile
# at 96 MB of address space and passes at 128 MB; 4x margin for bigger lessons, -O2 and g++ 15.
GXX_MEM_MB = 512
TRUNCATED = "\n[... sortie tronquée ...]\n"
ENV = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "TMPDIR": "/tmp", "LANG": "C.UTF-8"}


class SandboxUnavailable(RuntimeError):
    pass


@dataclass
class Result:
    rc: int
    out: str
    timed_out: bool
    signal: str | None


_probed = False


def _system_mounts() -> list[str]:
    args = ["--ro-bind", "/usr", "/usr"]
    for d in ("/bin", "/sbin", "/lib", "/lib32", "/lib64"):
        if os.path.islink(d):
            args += ["--symlink", os.readlink(d), d]
        elif os.path.isdir(d):
            args += ["--ro-bind", d, d]
    # Not secrets: the loader cache, and the symlinks /usr/bin/ld (Fedora) or cc (Debian) go through.
    for f in ("/etc/ld.so.cache", "/etc/alternatives"):
        if os.path.exists(f):
            args += ["--ro-bind", f, f]
    return args


def _bwrap_argv(bwrap: str, rw: Sequence[Path], ro: Sequence[Path], chdir: Path) -> list[str]:
    args = [bwrap, "--unshare-all", "--unshare-user", "--disable-userns", "--die-with-parent",
            "--new-session", "--cap-drop", "ALL", "--hostname", "sandbox", *_system_mounts(),
            "--proc", "/proc", "--dev", "/dev", "--remount-ro", "/dev",
            "--size", str(TMP_MB << 20), "--tmpfs", "/tmp"]
    # Parents before children, so a writable cwd nested in a read-only dir stays writable.
    binds = sorted([(Path(p).resolve(), "--ro-bind") for p in ro] + [(Path(p).resolve(), "--bind") for p in rw],
                   key=lambda b: len(b[0].parts))
    for path, flag in binds:
        args += [flag, str(path), str(path)]
    # bwrap's root is an unbounded tmpfs (RAM): freeze it once every mount point exists.
    return args + ["--remount-ro", "/", "--chdir", str(chdir)]


def _limits(cpu_s: int, mem_mb: int) -> list[str]:
    return ["/usr/bin/prlimit", f"--cpu={cpu_s}:{cpu_s + 1}", f"--as={mem_mb << 20}", f"--nproc={NPROC}",
            f"--fsize={FSIZE_MB << 20}", "--core=0", "--"]


def _check_available() -> str:
    global _probed
    bwrap = shutil.which("bwrap")
    if bwrap is None:
        raise SandboxUnavailable("bwrap (bubblewrap) est introuvable : exécution refusée sans sandbox.")
    if not _probed:
        r = subprocess.run([*_bwrap_argv(bwrap, (), (), Path("/")), *_limits(5, 64), "/usr/bin/true"],
                           env=ENV, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            raise SandboxUnavailable(f"bwrap ne peut pas créer le sandbox : {r.stderr.strip()}")
        _probed = True
    return bwrap


def run_sandboxed(argv: list[str], *, cwd: Path, rw: Sequence[Path] = (), ro: Sequence[Path] = (),
                  wall_s: float, cpu_s: int, mem_mb: int, max_out: int = 200_000) -> Result:
    cwd = Path(cwd).resolve()
    if not cwd.is_dir() or Path("/") in (cwd, *(Path(p).resolve() for p in rw)):
        raise ValueError(f"dossier de travail invalide pour le sandbox : {cwd}")
    bwrap = _check_available()
    cmd = [*_bwrap_argv(bwrap, (cwd, *rw), ro, cwd), *_limits(cpu_s, mem_mb), *argv]
    proc = subprocess.Popen(cmd, env=ENV, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, start_new_session=True)
    buf = bytearray()
    truncated = False

    def pump() -> None:
        nonlocal truncated
        # Keep draining past max_out so the child never blocks on a full pipe, but store nothing.
        while chunk := proc.stdout.read1(65536):
            room = max_out - len(buf)
            buf.extend(chunk[:room])
            truncated = truncated or len(chunk) > room

    reader = threading.Thread(target=pump, daemon=True)
    reader.start()
    timed_out = False
    try:
        proc.wait(timeout=wall_s)
    except subprocess.TimeoutExpired:
        timed_out = True
    finally:
        if proc.returncode is None:
            # Killing bwrap kills the namespace's init (--die-with-parent), which takes down every
            # process in the pid namespace.
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
    reader.join(timeout=5)
    proc.stdout.close()
    out = buf.decode("utf-8", errors="replace") + (TRUNCATED if truncated else "")
    return Result(rc=proc.returncode, out=out, timed_out=timed_out, signal=_signal_name(proc.returncode))


def _signal_name(rc: int) -> str | None:
    # bwrap reports a child killed by signal N as exit status 128+N; a negative rc is bwrap itself.
    n = -rc if rc < 0 else rc - 128 if rc > 128 else 0
    try:
        return signal.Signals(n).name if n else None
    except ValueError:
        return None
