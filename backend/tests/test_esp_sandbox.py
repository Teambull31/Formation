"""The bwrap sandbox contains hostile learner programs: time, memory, processes, output, files, network.

Set ESP_SANDBOX_REQUIRED=1 (CI, the VPS) to turn "bwrap unavailable" skips into failures, so a
broken sandbox can never pass silently.
"""
import importlib.util
import os
import socket
import subprocess
import uuid
from pathlib import Path

import pytest

ESP = Path(__file__).resolve().parents[2] / "content" / "esp"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sandbox = _load("esp_sandbox", ESP / "sandbox.py")
REQUIRED = os.environ.get("ESP_SANDBOX_REQUIRED") == "1"


@pytest.fixture(scope="module")
def bwrap_ok(tmp_path_factory):
    try:
        sandbox.run_sandboxed(["/usr/bin/true"], cwd=tmp_path_factory.mktemp("probe"), wall_s=30, cpu_s=5, mem_mb=64)
    except sandbox.SandboxUnavailable as e:
        msg = f"bwrap indisponible sur cette machine : {e}"
        if REQUIRED:
            pytest.fail(msg)
        pytest.skip(msg)


@pytest.fixture
def work(tmp_path, bwrap_ok):
    w = tmp_path / "work"
    w.mkdir()
    return w


def build(work: Path, src: str) -> str:
    """Compile an attack program with the host g++, OUTSIDE the sandbox; return its name in work/."""
    name = f"prog_{uuid.uuid4().hex[:12]}"
    (work / "a.c").write_text(src, encoding="utf-8")
    r = subprocess.run(["g++", "-x", "c", "-O0", "a.c", "-o", name], cwd=work, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return name


def run(work: Path, argv: list[str], **kw):
    opts = {"wall_s": 20, "cpu_s": 10, "mem_mb": 256} | kw
    return sandbox.run_sandboxed(argv, cwd=work, **opts)


def no_survivor(name: str) -> bool:
    return subprocess.run(["pgrep", "-f", name], capture_output=True).returncode == 1


def test_infinite_loop_killed(work):
    prog = build(work, "int main(void){ for(;;){} }")
    r = run(work, [f"./{prog}"], wall_s=2, cpu_s=60)
    assert r.timed_out
    assert no_survivor(prog)


def test_cpu_limit(work):
    prog = build(work, "int main(void){ for(;;){} }")
    r = run(work, [f"./{prog}"], wall_s=30, cpu_s=1)
    assert not r.timed_out
    assert r.signal in ("SIGXCPU", "SIGKILL")


def test_memory_bomb_stopped(work):
    prog = build(work, r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(void){
  size_t n = (size_t)4 << 30;
  char *p = malloc(n);
  if (!p) { puts("ALLOC_REFUSED"); return 1; }
  memset(p, 1, n);
  puts("ALLOC_OK");
  return 0;
}""")
    r = run(work, [f"./{prog}"], mem_mb=256)
    assert "ALLOC_OK" not in r.out
    assert r.rc != 0


def test_memory_across_processes_bounded(work):
    prog = build(work, r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
int main(void){
  int n = 0, ready[2];
  char c;
  pipe(ready);
  for (int i = 0; i < 20; i++) {
    pid_t p = fork();
    if (p == 0) {
      if (malloc((size_t)200 << 20)) { puts("BIG_OK"); fflush(stdout); }
      char *m = malloc((size_t)100 << 20);
      if (m) { memset(m, 1, (size_t)100 << 20); puts("child 100MB"); fflush(stdout); }
      write(ready[1], "r", 1);  /* handshake: this child is done allocating */
      pause();
      _exit(0);
    }
    if (p < 0) break;
    n++;
  }
  for (int i = 0; i < n; i++) read(ready[0], &c, 1);
  printf("forked %d\n", n);
  return 0;
}""")
    r = run(work, [f"./{prog}"], mem_mb=128, max_procs=4)
    # 4 processes = bwrap's init + parent + 2 children; each child stays under 128 MB.
    assert "BIG_OK" not in r.out, r
    assert r.out.count("child 100MB") == int(r.out.split()[-1]) == 2, r
    assert no_survivor(prog)


def test_cannot_read_host_files(work, tmp_path):
    other = tmp_path / "other_workspace"
    other.mkdir()
    (other / "secret.txt").write_text("SECRET", encoding="utf-8")
    prog = build(work, r"""
#include <stdio.h>
int main(int argc, char **argv){
  for (int i = 1; i < argc; i++) {
    FILE *f = fopen(argv[i], "r");
    printf("%s %s\n", argv[i], f ? "READABLE" : "denied");
  }
  return 0;
}""")
    targets = ["/etc/hostname", "/etc/passwd", str(Path.home() / ".bashrc"), str(other / "secret.txt"),
               str(ESP / "sandbox.py"), str(work / "a.c")]
    r = run(work, [f"./{prog}", *targets])
    assert r.rc == 0, r
    assert "READABLE" not in r.out, r.out
    assert r.out.count("denied") == len(targets)


def test_cannot_write_outside_tmp(work, tmp_path):
    ro_dir = tmp_path / "ro"
    rw_dir = tmp_path / "rw"
    ro_dir.mkdir()
    rw_dir.mkdir()
    prog = build(work, r"""
#include <stdio.h>
int main(int argc, char **argv){
  for (int i = 1; i < argc; i++) {
    FILE *f = fopen(argv[i], "w");
    printf("%s %s\n", argv[i], f ? "WRITTEN" : "denied");
    if (f) fclose(f);
  }
  return 0;
}""")
    r = sandbox.run_sandboxed(
        [f"./{prog}", "/evil", "/usr/evil", "/dev/evil", f"{ro_dir}/evil", "inside", "/work/inside", "/tmp/scratch",
         f"{rw_dir}/explicit"],
        cwd=work, ro=[ro_dir], rw=[rw_dir], wall_s=20, cpu_s=10, mem_mb=256)
    assert r.out.count("denied") == 6, r.out
    assert "/tmp/scratch WRITTEN" in r.out and f"{rw_dir}/explicit WRITTEN" in r.out
    assert not (work / "inside").exists()
    assert (rw_dir / "explicit").exists()
    assert not Path("/tmp/scratch").exists()


def test_file_size_limited(work):
    prog = build(work, r"""
#include <stdio.h>
int main(void){
  static char b[1 << 20];
  FILE *f = fopen("/tmp/big.bin", "w");
  for (int i = 0; i < 200; i++) fwrite(b, 1, sizeof b, f);
  puts("WROTE_200MB");
  return 0;
}""")
    r = run(work, [f"./{prog}"], tmp_mb=4 * sandbox.FSIZE_MB)
    assert r.signal == "SIGXFSZ", r


def test_tmp_is_capped(work):
    prog = build(work, r"""
#include <errno.h>
#include <stdio.h>
#include <string.h>
int main(void){
  static char b[1 << 20];
  char name[32];
  for (int k = 0; k < 100; k++) {
    snprintf(name, sizeof name, "/tmp/f%d", k);
    FILE *f = fopen(name, "w");
    for (int i = 0; i < 16; i++)
      if (!f || fwrite(b, 1, sizeof b, f) != sizeof b || fflush(f)) {
        printf("%s after %d MB\n", errno == ENOSPC ? "ENOSPC" : strerror(errno), k * 16 + i);
        return 1;
      }
    fclose(f);
  }
  puts("WROTE_1600MB");
  return 0;
}""")
    r = run(work, [f"./{prog}"], tmp_mb=32)
    assert r.out.startswith("ENOSPC after"), r
    assert int(r.out.split()[-2]) <= 32


@pytest.mark.parametrize("path", ["/", "/home", "/etc", "/usr", "/proc", str(Path.home())])
def test_broad_dirs_refused(work, path):
    for kw in ({"cwd": Path(path)}, {"cwd": work, "rw": [Path(path)]}):
        with pytest.raises(sandbox.UnsafePath, match="refusé"):
            sandbox.run_sandboxed(["/usr/bin/true"], wall_s=5, cpu_s=1, mem_mb=64, **kw)


@pytest.mark.parametrize("role", ["cwd", "rw", "ro", "parent"])
def test_symlinked_paths_refused(work, tmp_path, role):
    host = tmp_path / "host_dir"
    (host / "sub").mkdir(parents=True)
    link = tmp_path / "planted"
    link.symlink_to(host)
    args = {"cwd": link / "sub"} if role == "parent" else {"cwd": link} if role == "cwd" else {"cwd": work, role: [link]}
    with pytest.raises(sandbox.UnsafePath, match="lien symbolique"):
        sandbox.run_sandboxed(["/usr/bin/true"], wall_s=5, cpu_s=1, mem_mb=64, **args)


def test_non_directory_refused(work):
    (work / "f").write_text("x", encoding="utf-8")
    with pytest.raises(sandbox.UnsafePath):
        sandbox.run_sandboxed(["/usr/bin/true"], cwd=work / "f", wall_s=5, cpu_s=1, mem_mb=64)


def test_workspace_seen_at_fixed_path(work):
    r = run(work, ["/usr/bin/sh", "-c", "pwd; tr '\\0' ' ' < /proc/1/cmdline"])
    assert r.out.splitlines()[0] == "/work", r
    assert str(work) not in r.out


def test_nofile_limited(work):
    r = run(work, ["/usr/bin/sh", "-c", "ulimit -n"])
    assert r.out.strip() == str(sandbox.NOFILE)


def test_env_is_minimal(work, monkeypatch):
    monkeypatch.setenv("FORMATION_SECRET_TOKEN", "leak-me")
    r = run(work, ["/usr/bin/env"])
    assert "FORMATION" not in r.out and "leak-me" not in r.out
    assert "PATH=" in r.out


def test_no_network(work):
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen()
    port = srv.getsockname()[1]
    prog = build(work, r"""
#include <stdio.h>
#include <stdlib.h>
#include <arpa/inet.h>
#include <sys/socket.h>
int main(int argc, char **argv){
  int s = socket(AF_INET, SOCK_STREAM, 0);
  struct sockaddr_in a = {0};
  a.sin_family = AF_INET; a.sin_port = htons(atoi(argv[1])); a.sin_addr.s_addr = inet_addr("127.0.0.1");
  puts(s >= 0 && connect(s, (struct sockaddr *)&a, sizeof a) == 0 ? "CONNECTED" : "blocked");
  return 0;
}""")
    try:
        r = run(work, [f"./{prog}", str(port)])
    finally:
        srv.close()
    assert "blocked" in r.out and "CONNECTED" not in r.out, r


def test_no_abstract_unix_socket(work):
    name = f"formation-test-{uuid.uuid4().hex}"
    srv = socket.socket(socket.AF_UNIX)
    srv.bind("\0" + name)
    srv.listen()
    prog = build(work, r"""
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
int main(int argc, char **argv){
  int s = socket(AF_UNIX, SOCK_STREAM, 0);
  struct sockaddr_un a = {0};
  a.sun_family = AF_UNIX;
  size_t n = strlen(argv[1]);
  memcpy(a.sun_path + 1, argv[1], n);
  puts(connect(s, (struct sockaddr *)&a, sizeof(sa_family_t) + 1 + n) == 0 ? "CONNECTED" : "blocked");
  return 0;
}""")
    try:
        r = run(work, [f"./{prog}", name])
    finally:
        srv.close()
    assert "blocked" in r.out and "CONNECTED" not in r.out, r


def test_cannot_signal_host_processes(work):
    r = run(work, ["/usr/bin/sh", "-c", f"kill -0 {os.getpid()} && echo VISIBLE || echo hidden; ls /proc | grep -c '^[0-9]'"])
    assert "hidden" in r.out and "VISIBLE" not in r.out, r
    assert int(r.out.split()[-1]) < 10


def test_fork_bomb_bounded(work):
    prog = build(work, r"""
#include <stdio.h>
#include <unistd.h>
int main(void){
  int n = 0;
  for (int i = 0; i < 100000; i++) {
    pid_t p = fork();
    if (p == 0) { pause(); _exit(0); }
    if (p < 0) break;
    n++;
  }
  printf("forked %d\n", n);
  return 0;
}""")
    r = run(work, [f"./{prog}"])
    assert not r.timed_out
    # bwrap's init and the parent count too.
    assert int(r.out.split()[-1]) <= sandbox.RUN_MAX_PROCS - 2, r
    assert no_survivor(prog)


def test_output_truncated(work):
    prog = build(work, r"""
#include <stdio.h>
int main(void){
  for (int i = 0; i < 5000000; i++) {
    fputs("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\n", stdout);
    fputs("yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy\n", stderr);
  }
  return 0;
}""")
    r = run(work, [f"./{prog}"], max_out=1000)
    for text, other in ((r.out, "y"), (r.err, "x")):
        assert text.endswith(sandbox.TRUNCATED)
        assert len(text) <= 1000 + len(sandbox.TRUNCATED)
        assert other not in text


def test_stdout_and_stderr_separate(work):
    r = run(work, ["/usr/bin/sh", "-c", "echo TRACE; echo LEARNER >&2"])
    assert (r.out, r.err) == ("TRACE\n", "LEARNER\n")


def test_segfault_reports_signal(work):
    prog = build(work, "int main(void){ volatile int *p = 0; return *p; }")
    r = run(work, [f"./{prog}"])
    assert r.signal == "SIGSEGV"


def test_unavailable_when_bwrap_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox, "BWRAP", str(tmp_path / "absent"))
    monkeypatch.setenv("PATH", "")
    with pytest.raises(sandbox.SandboxUnavailable):
        sandbox.run_sandboxed(["/usr/bin/true"], cwd=tmp_path, wall_s=5, cpu_s=1, mem_mb=64)


def test_bwrap_not_owned_by_root_refused(tmp_path, monkeypatch):
    fake = tmp_path / "bwrap"
    fake.write_text('#!/bin/sh\nexec "$@"\n', encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setattr(sandbox, "BWRAP", str(tmp_path / "absent"))
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(sandbox.SandboxUnavailable, match="root"):
        sandbox.run_sandboxed(["/usr/bin/true"], cwd=tmp_path, wall_s=5, cpu_s=1, mem_mb=64)


def test_probe_hang_is_unavailable(tmp_path, monkeypatch):
    if not Path(sandbox.BWRAP).exists():
        pytest.skip("pas de /usr/bin/bwrap")

    def hang(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))

    monkeypatch.setattr(sandbox, "_probed", False)
    monkeypatch.setattr(sandbox.subprocess, "run", hang)
    with pytest.raises(sandbox.SandboxUnavailable, match="ne répond pas"):
        sandbox.run_sandboxed(["/usr/bin/true"], cwd=tmp_path, wall_s=5, cpu_s=1, mem_mb=64)


@pytest.fixture(scope="module")
def sim():
    return _load("espsim_build", ESP / "sim" / "build.py").build_sim()


def compile_and_run(work: Path, sim: Path, src: str, run_args=("--max-ms", "10"), with_sim=True):
    (work / "main.cpp").write_text(src, encoding="utf-8")
    argv = ["g++", "-std=c++17", "main.cpp"] + (["-I", f"{sim}/include", f"{sim}/libespsim.a", "-pthread"] if with_sim else [])
    return sandbox.compile_and_run(argv, list(run_args), cwd=work, ro=[sim], wall_s=120)


def test_compiler_runs_inside_sandbox(work, sim):
    """Compile AND run in one call, with the workspace read-only: only the tmpfs /tmp is written."""
    r = compile_and_run(work, sim, '#include <cstdio>\n#include "esp_log.h"\n'
                        'extern "C" void app_main(void) { ESP_LOGI("t", "bonjour"); std::printf("learner says hi\\n"); std::fflush(stdout); }\n')
    assert (r.phase, r.rc) == ("run", 0), r
    assert '"msg": "bonjour"' in r.out and "learner" not in r.out
    assert "learner says hi" in r.err and "bonjour" not in r.err
    assert sorted(p.name for p in work.iterdir()) == ["main.cpp"]


def test_program_gets_run_limits_not_compile_limits(work, sim):
    r = compile_and_run(work, sim, r"""
#include <cstdio>
#include <cstdlib>
#include <sys/resource.h>
int main() {
  rlimit as, np;
  getrlimit(RLIMIT_AS, &as);
  getrlimit(RLIMIT_NPROC, &np);
  std::printf("AS=%llu NPROC=%llu %s\n", (unsigned long long)as.rlim_max, (unsigned long long)np.rlim_max,
              std::malloc(size_t(400) << 20) ? "ALLOC_400MB_OK" : "alloc refused");
}""", run_args=(), with_sim=False)
    # g++ needed GXX_MEM_MB (> RUN_MEM_MB) to build this; the program only gets the run limits.
    assert sandbox.GXX_MEM_MB > sandbox.RUN_MEM_MB
    assert (r.phase, r.rc) == ("run", 0), r
    assert r.out == f"AS={sandbox.RUN_MEM_MB << 20} NPROC={sandbox.RUN_MAX_PROCS} alloc refused\n"


def test_compile_error_is_compile_phase(work, sim):
    r = compile_and_run(work, sim, 'extern "C" void app_main(void) { this is not C++ }\n')
    assert r.phase == "compile" and r.rc != 0, r
    assert "error" in r.err and r.out == ""


def test_program_segfault_is_run_phase(work, sim):
    r = compile_and_run(work, sim, "int main() { volatile int *p = nullptr; return *p; }\n", run_args=(), with_sim=False)
    assert (r.phase, r.signal) == ("run", "SIGSEGV"), r


def test_program_exit_status_is_reported(work, sim):
    r = compile_and_run(work, sim, "int main() { return 7; }\n", run_args=(), with_sim=False)
    assert (r.phase, r.rc, r.signal) == ("run", 7, None), r
