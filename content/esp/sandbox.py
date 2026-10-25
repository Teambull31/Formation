"""Run untrusted learner code (and the compiler) inside bubblewrap, with resource limits.

Isolation: new user/pid/net/ipc/uts/cgroup namespaces, no capabilities, no nested user
namespaces, a root rebuilt from read-only /usr only, minimal /proc and read-only /dev. `cwd` is
bound READ-ONLY at /work (the working directory; argv paths are relative to /work). The only
scratch space is a size-capped tmpfs /tmp (RAM, `tmp_mb`): callers compile AND run in one call
(`sh -c "g++ ... -o /tmp/prog && /tmp/prog"`), so no host directory needs to be writable.
`ro` paths are mounted at their real path (the compiler finds the simulator's include/lib at
the host paths written in argv). `rw` paths are writable at their real path: callers must never
pass a host directory the learner can reach later, since a program can leave symlinks, FIFOs or
huge files there; read anything from an `rw` dir with O_NOFOLLOW, a regular-file check and a
size cap. Fails closed: if bwrap is missing or cannot build the namespaces, SandboxUnavailable
is raised, never a direct run.

Paths: cwd/rw/ro are opened (O_PATH) and bound by file descriptor (--bind-fd), and the fd's real
path must equal the requested absolute path, so a symlink in any component is refused
(UnsafePath) and cannot be swapped in between the check and the mount.

Limits are applied by /usr/bin/prlimit INSIDE the sandbox, not by preexec_fn: RLIMIT_NPROC is
counted per user, so set before bwrap it would count every host process of the backend user
(and makes bwrap's own namespace creation fail); set inside, it counts only sandbox processes.
Memory worst case per call: max_procs processes x mem_mb of address space each (threads share
their process's address space) + tmp_mb of tmpfs, e.g. 8 x 256 MB + 64 MB for a run.

Result.signal is a hint only: bwrap reports a death by signal N as exit status 128+N, so a
program calling exit(139) is reported as SIGSEGV.
"""
import os
import shutil
import signal
import subprocess
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

BWRAP = "/usr/bin/bwrap"
WORK = "/work"
FSIZE_MB = 64  # largest single file (on top of the tmpfs cap): a simulator binary is a few MB
NOFILE = 256
TRUNCATED = "\n[... sortie tronquée ...]\n"
ENV = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "TMPDIR": "/tmp", "LANG": "C.UTF-8"}
# Defaults are for running a simulator program: main + a few FreeRTOS task threads + bwrap's init
# (NPROC counts threads too). /tmp only receives small scratch files at run time.
RUN_MAX_PROCS = 8
RUN_TMP_MB = 64
# Compile+run in one call. Measured with g++ 16 (see the task report): `sh -c "g++ ... && prog"`
# needs 5 processes (init, sh, g++, collect2, ld) and fails at 4; 32 leaves room for the program's
# task threads. The same compile+run succeeds with a 1 MB /tmp (76 KB binary, g++ temporaries
# deleted as it goes); 64 MB leaves room for bigger lessons while bounding RAM per call.
COMPILE_MAX_PROCS = 32
COMPILE_TMP_MB = 64
# Measured with g++ 16: a C++17 file including <iostream>, <thread> and <map> fails to compile
# at 96 MB of address space and passes at 128 MB; 4x margin for bigger lessons, -O2 and g++ 15.
GXX_MEM_MB = 512
FORBIDDEN = {Path(p) for p in ("/", "/home", "/root", "/etc", "/var", "/usr", "/proc", "/sys", "/dev")}


class SandboxUnavailable(RuntimeError):
    pass


class UnsafePath(ValueError):
    pass


@dataclass
class Result:
    rc: int
    out: str
    err: str
    timed_out: bool
    signal: str | None


_probed = False
_probe_lock = threading.Lock()


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


def _open_dir(p: Path) -> int:
    path = Path(os.path.abspath(p))
    if path in FORBIDDEN or path == Path.home():
        raise UnsafePath(f"dossier refusé pour le sandbox (trop large) : {path}")
    try:
        fd = os.open(path, os.O_PATH | os.O_DIRECTORY | os.O_CLOEXEC)
    except OSError as e:
        raise UnsafePath(f"dossier introuvable ou qui n'est pas un dossier : {path} ({e.strerror})") from None
    # bwrap mounts this fd; its real path proves no component was a symlink when it was opened.
    if os.readlink(f"/proc/self/fd/{fd}") != str(path):
        os.close(fd)
        raise UnsafePath(f"chemin refusé pour le sandbox, il passe par un lien symbolique : {path}")
    return fd


def _bwrap_argv(bwrap: str, tmp_mb: int, binds: list[tuple[str, int, str]]) -> list[str]:
    args = [bwrap, "--unshare-all", "--unshare-user", "--disable-userns", "--die-with-parent",
            "--new-session", "--cap-drop", "ALL", "--hostname", "sandbox", *_system_mounts(),
            "--proc", "/proc", "--dev", "/dev", "--remount-ro", "/dev",
            "--size", str(tmp_mb << 20), "--tmpfs", "/tmp"]
    # Parents before children, so a writable dir nested in a read-only one stays writable.
    for flag, fd, dest in sorted(binds, key=lambda b: len(Path(b[2]).parts)):
        args += [flag, str(fd), dest]
    # bwrap's root is an unbounded tmpfs (RAM): freeze it once every mount point exists.
    return args + ["--remount-ro", "/", "--chdir", WORK if any(b[2] == WORK for b in binds) else "/"]


def _limits(cpu_s: int, mem_mb: int, max_procs: int) -> list[str]:
    return ["/usr/bin/prlimit", f"--cpu={cpu_s}:{cpu_s + 1}", f"--as={mem_mb << 20}", f"--nproc={max_procs}",
            f"--fsize={FSIZE_MB << 20}", f"--nofile={NOFILE}", "--core=0", "--"]


def _check_available() -> str:
    global _probed
    bwrap = BWRAP if os.path.exists(BWRAP) else shutil.which("bwrap")
    if bwrap is None:
        raise SandboxUnavailable("bwrap (bubblewrap) est introuvable : exécution refusée sans sandbox.")
    if os.stat(bwrap).st_uid != 0:
        raise SandboxUnavailable(f"{bwrap} n'appartient pas à root : exécution refusée.")
    with _probe_lock:
        if not _probed:
            try:
                r = subprocess.run([*_bwrap_argv(bwrap, 1, []), *_limits(5, 64, 4), "/usr/bin/true"],
                                   env=ENV, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
            except subprocess.TimeoutExpired:
                raise SandboxUnavailable("bwrap ne répond pas (sonde bloquée plus de 30 s).") from None
            if r.returncode != 0:
                raise SandboxUnavailable(f"bwrap ne peut pas créer le sandbox : {r.stderr.strip()}")
            _probed = True
    return bwrap


def _drain(stream, max_out: int, sink: list[str]) -> None:
    # Keep reading past max_out so the child never blocks on a full pipe, but store nothing more.
    buf = bytearray()
    cut = False
    while chunk := stream.read1(65536):
        room = max_out - len(buf)
        buf.extend(chunk[:room])
        cut = cut or len(chunk) > room
    sink.append(buf.decode("utf-8", errors="replace") + (TRUNCATED if cut else ""))


def run_sandboxed(argv: list[str], *, cwd: Path, rw: Sequence[Path] = (), ro: Sequence[Path] = (),
                  wall_s: float, cpu_s: int, mem_mb: int, max_out: int = 200_000,
                  tmp_mb: int = RUN_TMP_MB, max_procs: int = RUN_MAX_PROCS) -> Result:
    fds: list[int] = []
    try:
        binds = []
        for flag, paths in (("--ro-bind-fd", ro), ("--bind-fd", rw)):
            for p in paths:
                fds.append(_open_dir(p))
                binds.append((flag, fds[-1], os.path.abspath(p)))
        fds.append(_open_dir(cwd))
        binds.append(("--ro-bind-fd", fds[-1], WORK))
        bwrap = _check_available()
        cmd = [*_bwrap_argv(bwrap, tmp_mb, binds), *_limits(cpu_s, mem_mb, max_procs), *argv]
        proc = subprocess.Popen(cmd, env=ENV, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, start_new_session=True, pass_fds=fds)
    finally:
        for fd in fds:
            os.close(fd)
    out: list[str] = []
    err: list[str] = []
    readers = [threading.Thread(target=_drain, args=(s, max_out, sink), daemon=True)
               for s, sink in ((proc.stdout, out), (proc.stderr, err))]
    for t in readers:
        t.start()
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
    for t in readers:
        t.join(timeout=5)
    proc.stdout.close()
    proc.stderr.close()
    return Result(rc=proc.returncode, out="".join(out), err="".join(err), timed_out=timed_out,
                  signal=_signal_name(proc.returncode))


def _signal_name(rc: int) -> str | None:
    # A child killed by signal N comes back as 128+N; a negative rc means bwrap itself was killed.
    n = -rc if rc < 0 else rc - 128 if rc > 128 else 0
    try:
        return signal.Signals(n).name if n else None
    except ValueError:
        return None
