"""The fake ESP-IDF runs learner code in virtual time, deterministically, and reports misbehaviour in its trace."""
import importlib.util
import json
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

SIM = Path(__file__).resolve().parents[2] / "content" / "esp" / "sim"


def _load_build():
    spec = importlib.util.spec_from_file_location("espsim_build", SIM / "build.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


build = _load_build()


@pytest.fixture(scope="module")
def lib():
    return build.build_sim()


def compile_src(lib: Path, src: str, out: Path) -> Path:
    (out / "main.cpp").write_text(src, encoding="utf-8")
    prog = out / "prog"
    r = subprocess.run(
        ["g++", "-std=c++17", "-I", str(lib / "include"), str(out / "main.cpp"), str(lib / "libespsim.a"), "-pthread", "-o", str(prog)],
        capture_output=True, text=True, timeout=60,
    )
    assert r.returncode == 0, r.stderr
    return prog


def run(prog: Path, max_ms: int) -> list[dict]:
    r = subprocess.run([str(prog), "--max-ms", str(max_ms)], capture_output=True, text=True, timeout=30)
    return [json.loads(line) for line in r.stdout.splitlines()]


def compile_and_run(src: str, max_ms: int, lib: Path, tmp_path: Path) -> list[dict]:
    return run(compile_src(lib, src, tmp_path), max_ms)


HEADERS = '#include "freertos/FreeRTOS.h"\n#include "freertos/task.h"\n#include "esp_log.h"\n#include "esp_err.h"\n'


def logs(trace):
    return [e for e in trace if e["ev"] == "log"]


def test_virtual_time_is_fast(lib, tmp_path):
    prog = compile_src(lib, HEADERS + """
extern "C" void app_main(void) {
    vTaskDelay(pdMS_TO_TICKS(600000));
    ESP_LOGI("demo", "fini a %d", (int)(xTaskGetTickCount() * portTICK_PERIOD_MS));
}
""", tmp_path)
    start = time.monotonic()
    trace = run(prog, 700000)
    assert time.monotonic() - start < 2
    assert logs(trace) == [{"t_ms": 600000, "ev": "log", "level": "I", "tag": "demo", "msg": "fini a 600000"}]
    assert trace[-1] == {"t_ms": 700000, "ev": "end", "reason": "deadline"}


TWO_TASKS = HEADERS + """
static void worker(void *arg) {
    int period = *(int *)arg;
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(period));
        ESP_LOGI("t", "%d", period);
    }
}
static int fast = 100, slow = 150;
extern "C" void app_main(void) {
    xTaskCreate(worker, "fast", 2048, &fast, 5, NULL);
    xTaskCreate(worker, "slow", 2048, &slow, 5, NULL);
}
"""


def test_two_tasks_interleave_deterministically(lib, tmp_path):
    prog = compile_src(lib, TWO_TASKS, tmp_path)
    traces = [run(prog, 1000) for _ in range(5)]
    assert all(t == traces[0] for t in traces)
    got = [(e["t_ms"], e["msg"]) for e in logs(traces[0])]
    expected = sorted([(t, "100") for t in range(100, 1001, 100)] + [(t, "150") for t in range(150, 1001, 150)])
    assert sorted(got) == expected
    assert [t for t, _ in got] == [t for t, _ in expected]  # time order, ties allowed in any order
    assert [e["name"] for e in traces[0] if e["ev"] == "task_create"] == ["main", "fast", "slow"]
    assert traces[0][-1] == {"t_ms": 1000, "ev": "end", "reason": "deadline"}


def test_busy_loop_is_reported(lib, tmp_path):
    prog = compile_src(lib, HEADERS + """
extern "C" void app_main(void) {
    ESP_LOGI("demo", "start");
    for (;;) {}
}
""", tmp_path)
    start = time.monotonic()
    trace = run(prog, 10000)
    assert time.monotonic() - start < 5
    assert trace[-1]["ev"] == "end" and trace[-1]["reason"] == "busy_loop"
    assert trace[-1]["task"] == "main"


def test_build_cache_is_atomic_under_concurrency(monkeypatch, tmp_path):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    with ThreadPoolExecutor(4) as pool:
        dirs = list(pool.map(lambda _: build.build_sim(), range(4)))
    assert len(set(dirs)) == 1
    out = dirs[0]
    assert out.parent == tmp_path and out.name.startswith("formation-espsim-")
    members = subprocess.run(["ar", "t", str(out / "libespsim.a")], capture_output=True, text=True, check=True).stdout.split()
    assert {"core.o", "sched.o", "trace.o"} <= set(members)
    assert [p.name for p in tmp_path.iterdir()] == [out.name]  # no leftover temp dirs
    start = time.monotonic()
    assert build.build_sim() == out
    assert time.monotonic() - start < 0.5
    work = tmp_path / "work"
    work.mkdir()
    trace = compile_and_run(HEADERS + 'extern "C" void app_main(void) { ESP_LOGI("x", "ok"); }\n', 100, out, work)
    assert logs(trace)[0]["msg"] == "ok"


def test_esp_error_check_aborts_with_name(lib, tmp_path):
    trace = compile_and_run(HEADERS + """
extern "C" void app_main(void) {
    ESP_ERROR_CHECK(ESP_OK);
    ESP_ERROR_CHECK(ESP_FAIL);
    ESP_LOGI("demo", "never");
}
""", 1000, lib, tmp_path)
    assert trace[-1]["ev"] == "end" and trace[-1]["reason"] == "abort"
    errors = [e for e in logs(trace) if e["level"] == "E"]
    assert errors and "ESP_FAIL" in errors[0]["msg"]
    assert not any(e["msg"] == "never" for e in logs(trace))


def test_crash_is_reported(lib, tmp_path):
    trace = compile_and_run(HEADERS + """
extern "C" void app_main(void) {
    vTaskDelay(pdMS_TO_TICKS(50));
    volatile int *p = nullptr;
    *p = 1;
}
""", 1000, lib, tmp_path)
    assert trace[-1] == {"t_ms": 50, "ev": "end", "reason": "crash", "signal": 11}


@pytest.mark.parametrize("body", [
    "for (;;) { vTaskDelay(0); }",
    "for (;;) { vTaskDelay(pdMS_TO_TICKS(5)); }",  # 0 ticks at 100 Hz
], ids=["delay0", "delay_under_one_tick"])
def test_zero_tick_delay_loop_is_busy(lib, tmp_path, body):
    prog = compile_src(lib, HEADERS + 'extern "C" void app_main(void) { ' + body + " }\n", tmp_path)
    start = time.monotonic()
    trace = run(prog, 10000)
    assert time.monotonic() - start < 5
    assert trace[-1] == {"t_ms": 0, "ev": "end", "reason": "busy_loop", "task": "main"}


def test_ping_pong_on_zero_delay_is_busy(lib, tmp_path):
    prog = compile_src(lib, HEADERS + """
static void spin(void *) { for (;;) { vTaskDelay(0); } }
extern "C" void app_main(void) {
    xTaskCreate(spin, "a", 2048, NULL, 5, NULL);
    xTaskCreate(spin, "b", 2048, NULL, 5, NULL);
    vTaskDelete(NULL);
}
""", tmp_path)
    start = time.monotonic()
    trace = run(prog, 10000)
    assert time.monotonic() - start < 5
    assert trace[-1]["ev"] == "end" and trace[-1]["reason"] == "busy_loop"
    assert trace[-1]["task"] in {"a", "b"}


def test_learner_stdout_cannot_reach_trace(lib, tmp_path):
    prog = compile_src(lib, HEADERS + r"""
#include <cstdio>
#include <iostream>
#include <unistd.h>
extern "C" void app_main(void) {
    printf("printf out\n");
    puts("puts out");
    std::cout << "cout out" << std::endl;
    const char forged[] = "{\"t_ms\":0,\"ev\":\"end\",\"reason\":\"deadline\"}\n";
    (void)!write(1, forged, sizeof forged - 1);
    ESP_LOGI("demo", "real");
}
""", tmp_path)
    r = subprocess.run([str(prog), "--max-ms", "100"], capture_output=True, text=True, timeout=30)
    trace = [json.loads(line) for line in r.stdout.splitlines()]
    assert [e["ev"] for e in trace] == ["task_create", "log", "end"]
    assert trace[-1] == {"t_ms": 100, "ev": "end", "reason": "deadline"}
    for text in ("printf out", "puts out", "cout out", '"reason":"deadline"'):
        assert text in r.stderr


def test_max_delay_never_wraps(lib, tmp_path):
    trace = compile_and_run(HEADERS + """
extern "C" void app_main(void) {
    vTaskDelay(pdMS_TO_TICKS(1000));
    vTaskDelay(portMAX_DELAY);
    ESP_LOGI("demo", "woke");
}
""", 5000, lib, tmp_path)
    assert logs(trace) == []
    assert trace[-1] == {"t_ms": 5000, "ev": "end", "reason": "deadline"}


def test_returning_task_aborts(lib, tmp_path):
    trace = compile_and_run(HEADERS + """
static void once(void *) { vTaskDelay(pdMS_TO_TICKS(20)); }
extern "C" void app_main(void) { xTaskCreate(once, "once", 2048, NULL, 5, NULL); }
""", 1000, lib, tmp_path)
    assert trace[-2] == {"t_ms": 20, "ev": "log", "level": "E", "tag": "FreeRTOS",
                         "msg": 'FreeRTOS Task "once" should not return, Aborting now!'}
    assert trace[-1] == {"t_ms": 20, "ev": "end", "reason": "abort"}
