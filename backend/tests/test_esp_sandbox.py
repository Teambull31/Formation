"""The bwrap sandbox contains hostile learner programs: time, memory, processes, output, files, network."""
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


@pytest.fixture(scope="module")
def bwrap_ok(tmp_path_factory):
    try:
        sandbox.run_sandboxed(["/usr/bin/true"], cwd=tmp_path_factory.mktemp("probe"), wall_s=30, cpu_s=5, mem_mb=64)
    except sandbox.SandboxUnavailable as e:
        pytest.skip(f"bwrap indisponible sur cette machine : {e}")


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
    targets = ["/etc/hostname", "/etc/passwd", str(Path.home() / ".bashrc"), str(other / "secret.txt"), str(ESP / "sandbox.py")]
    r = run(work, [f"./{prog}", *targets])
    assert r.rc == 0, r.out
    assert "READABLE" not in r.out, r.out
    assert r.out.count("denied") == len(targets)


def test_cannot_write_outside_workspace(work, tmp_path):
    ro_dir = tmp_path / "ro"
    ro_dir.mkdir()
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
    r = sandbox.run_sandboxed([f"./{prog}", "/evil", "/usr/evil", "/dev/evil", f"{ro_dir}/evil", "/tmp/scratch", "inside"],
                              cwd=work, ro=[ro_dir], wall_s=20, cpu_s=10, mem_mb=256)
    assert r.out.count("denied") == 4, r.out
    assert "/tmp/scratch WRITTEN" in r.out and "inside WRITTEN" in r.out
    assert (work / "inside").exists()
    assert not Path("/tmp/scratch").exists()


def test_file_size_limited(work):
    prog = build(work, r"""
#include <stdio.h>
int main(void){
  static char b[1 << 20];
  FILE *f = fopen("big.bin", "w");
  for (int i = 0; i < 200; i++) fwrite(b, 1, sizeof b, f);
  puts("WROTE_200MB");
  return 0;
}""")
    r = run(work, [f"./{prog}"])
    assert r.signal == "SIGXFSZ", r
    assert (work / "big.bin").stat().st_size <= sandbox.FSIZE_MB << 20


def test_tmp_is_capped(work):
    prog = build(work, r"""
#include <stdio.h>
int main(void){
  static char b[1 << 20];
  char name[32];
  for (int k = 0; k < 100; k++) {
    snprintf(name, sizeof name, "/tmp/f%d", k);
    FILE *f = fopen(name, "w");
    for (int i = 0; i < 16; i++)
      if (!f || fwrite(b, 1, sizeof b, f) != sizeof b || fflush(f)) { printf("full after %d MB\n", k * 16 + i); return 1; }
    fclose(f);
  }
  puts("WROTE_1600MB");
  return 0;
}""")
    r = run(work, [f"./{prog}"])
    assert "WROTE_1600MB" not in r.out, r.out
    assert int(r.out.split()[-2]) <= sandbox.TMP_MB


def test_root_workspace_refused(bwrap_ok):
    with pytest.raises(ValueError):
        sandbox.run_sandboxed(["/usr/bin/true"], cwd=Path("/"), wall_s=5, cpu_s=1, mem_mb=64)


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
    assert "blocked" in r.out and "CONNECTED" not in r.out, r.out


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
    assert "blocked" in r.out and "CONNECTED" not in r.out, r.out


def test_cannot_signal_host_processes(work):
    r = run(work, ["/usr/bin/sh", "-c", f"kill -0 {os.getpid()} && echo VISIBLE || echo hidden; ls /proc | grep -c '^[0-9]'"])
    assert "hidden" in r.out and "VISIBLE" not in r.out, r.out
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
    assert int(r.out.split()[-1]) < sandbox.NPROC
    assert no_survivor(prog)


def test_output_truncated(work):
    prog = build(work, r"""
#include <stdio.h>
int main(void){ for (int i = 0; i < 10000000; i++) fputs("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\n", stdout); return 0; }""")
    r = run(work, [f"./{prog}"], max_out=1000)
    assert sandbox.TRUNCATED in r.out
    assert len(r.out) <= 1000 + len(sandbox.TRUNCATED)


def test_segfault_reports_signal(work):
    prog = build(work, "int main(void){ volatile int *p = 0; return *p; }")
    r = run(work, [f"./{prog}"])
    assert r.signal == "SIGSEGV"


def test_unavailable_when_bwrap_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "")
    with pytest.raises(sandbox.SandboxUnavailable):
        sandbox.run_sandboxed(["/usr/bin/true"], cwd=tmp_path, wall_s=5, cpu_s=1, mem_mb=64)


def test_compiler_runs_inside_sandbox(work):
    sim = _load("espsim_build", ESP / "sim" / "build.py").build_sim()
    (work / "main.cpp").write_text(
        '#include "esp_log.h"\nextern "C" void app_main(void) { ESP_LOGI("t", "bonjour"); }\n', encoding="utf-8")
    r = sandbox.run_sandboxed(
        ["g++", "-std=c++17", "-I", str(sim / "include"), "main.cpp", str(sim / "libespsim.a"), "-pthread", "-o", "prog"],
        cwd=work, ro=[sim], wall_s=120, cpu_s=60, mem_mb=sandbox.GXX_MEM_MB)
    assert r.rc == 0, r.out
    assert (work / "prog").is_file()
    r = run(work, ["./prog", "--max-ms", "10"])
    assert r.rc == 0, r.out
