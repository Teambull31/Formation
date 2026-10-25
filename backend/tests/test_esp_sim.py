"""The fake ESP-IDF runs learner code in virtual time, deterministically, and reports misbehaviour in its trace."""
import importlib.util
import json
import re
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


def run(prog: Path, max_ms: int, scenario: str | None = None) -> list[dict]:
    args = [str(prog), "--max-ms", str(max_ms)]
    if scenario is not None:
        path = prog.parent / "scenario.json"
        path.write_text(scenario, encoding="utf-8")
        args += ["--scenario", str(path)]
    r = subprocess.run(args, capture_output=True, text=True, timeout=30)
    return [json.loads(line) for line in r.stdout.splitlines()]


def compile_and_run(src: str, max_ms: int, lib: Path, tmp_path: Path, scenario: str | None = None) -> list[dict]:
    return run(compile_src(lib, src, tmp_path), max_ms, scenario)


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


@pytest.mark.parametrize("value", [str(((2**63 - 1) >> 12) + 1), "9223372036854775807"])
def test_max_ms_above_the_cap_is_refused(lib, tmp_path, value):
    prog = compile_src(lib, HEADERS + "extern \"C\" void app_main(void) {}\n", tmp_path)
    r = subprocess.run([str(prog), "--max-ms", value], capture_output=True, text=True, timeout=30)
    assert r.returncode == 2 and "--max-ms" in r.stderr and r.stdout == ""


def test_max_ms_at_the_cap_is_accepted(lib, tmp_path):
    prog = compile_src(lib, HEADERS + "extern \"C\" void app_main(void) {}\n", tmp_path)
    r = subprocess.run([str(prog), "--max-ms", str((2**63 - 1) >> 12)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0 and '"reason":"deadline"' in r.stdout.replace(" ", "")


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


GPIO = HEADERS + '#include "driver/gpio.h"\n'


def test_gpio_output_traced(lib, tmp_path):
    trace = compile_and_run(GPIO + """
extern "C" void app_main(void) {
    gpio_config_t io = {};
    io.pin_bit_mask = 1ULL << GPIO_NUM_2;
    io.mode = GPIO_MODE_OUTPUT;
    io.pull_up_en = GPIO_PULLUP_DISABLE;
    io.pull_down_en = GPIO_PULLDOWN_DISABLE;
    io.intr_type = GPIO_INTR_DISABLE;
    ESP_ERROR_CHECK(gpio_config(&io));
    ESP_ERROR_CHECK(gpio_set_level(GPIO_NUM_2, 1));
    vTaskDelay(pdMS_TO_TICKS(250));
    ESP_ERROR_CHECK(gpio_set_level(GPIO_NUM_2, 0));
}
""", 1000, lib, tmp_path)
    assert [e for e in trace if e["ev"].startswith("gpio")] == [
        {"t_ms": 0, "ev": "gpio_config", "pin": 2, "mode": "output", "pull_up": False},
        {"t_ms": 0, "ev": "gpio_set", "pin": 2, "level": 1, "task": "main"},
        {"t_ms": 250, "ev": "gpio_set", "pin": 2, "level": 0, "task": "main"},
    ]


READ_LOOP = GPIO + """
extern "C" void app_main(void) {
    gpio_config_t io = {};
    io.pin_bit_mask = 1ULL << 4;
    io.mode = GPIO_MODE_INPUT;
    io.pull_up_en = %s;
    ESP_ERROR_CHECK(gpio_config(&io));
    int at[] = {0, 990, 1000, 1010, 2000};
    int prev = 0;
    for (int t : at) {
        vTaskDelay(pdMS_TO_TICKS(t - prev));
        prev = t;
        ESP_LOGI("in", "%%d", gpio_get_level(GPIO_NUM_4));
    }
}
"""


def levels(trace):
    return [(e["t_ms"], e["msg"]) for e in logs(trace)]


def test_gpio_input_follows_scenario(lib, tmp_path):
    trace = compile_and_run(READ_LOOP % "GPIO_PULLUP_DISABLE", 3000, lib, tmp_path,
                            '{"gpio_in": [{"t_ms": 1000, "pin": 4, "level": 1}, {"t_ms": 1005, "pin": 4, "level": 0}, '
                            '{"t_ms": 1500, "pin": 5, "level": 1}], "future": {"a": [1, 2.5e1, null, true, "x\\u00e9"]}}')
    # reads at 0, 990, 1000, 1010 and 2000 ms (10 ms ticks); the 1005 entry is already in force at 1010
    assert levels(trace) == [(0, "0"), (990, "0"), (1000, "1"), (1010, "0"), (2000, "0")]


def test_floating_input_reads_zero_without_pullup(lib, tmp_path):
    trace = compile_and_run(READ_LOOP % "GPIO_PULLUP_DISABLE", 3000, lib, tmp_path)
    assert {m for _, m in levels(trace)} == {"0"}


def test_pullup_input_reads_one_by_default(lib, tmp_path):
    trace = compile_and_run(READ_LOOP % "GPIO_PULLUP_ENABLE", 3000, lib, tmp_path,
                            '{"gpio_in": [{"t_ms": 1500, "pin": 4, "level": 0}]}')
    assert levels(trace) == [(0, "1"), (990, "1"), (1000, "1"), (1010, "1"), (2000, "0")]


def test_gpio_invalid_pin_and_input_only(lib, tmp_path):
    trace = compile_and_run(GPIO + """
extern "C" void app_main(void) {
    ESP_LOGI("r", "%s", esp_err_to_name(gpio_set_level((gpio_num_t)40, 1)));
    ESP_LOGI("r", "%s", esp_err_to_name(gpio_set_direction((gpio_num_t)-1, GPIO_MODE_INPUT)));
    ESP_LOGI("r", "%s", esp_err_to_name(gpio_set_direction(GPIO_NUM_34, GPIO_MODE_OUTPUT)));
    ESP_LOGI("r", "%d", gpio_get_level((gpio_num_t)99));
}
""", 100, lib, tmp_path)
    assert [m for _, m in levels(trace)] == ["ESP_ERR_INVALID_ARG"] * 3 + ["0"]


@pytest.mark.parametrize("scenario", ["{", '{"gpio_in": 3}', '{"gpio_in": [{"t_ms": 1}]}', '[1,2]', '{"a": 1} x'])
def test_malformed_scenario_fails_cleanly(lib, tmp_path, scenario):
    prog = compile_src(lib, GPIO + 'extern "C" void app_main(void) {}\n', tmp_path)
    path = tmp_path / "bad.json"
    path.write_text(scenario)
    r = subprocess.run([str(prog), "--scenario", str(path)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 2 and r.stdout == "" and "scénario" in r.stderr


def test_missing_scenario_file_fails_cleanly(lib, tmp_path):
    prog = compile_src(lib, GPIO + 'extern "C" void app_main(void) {}\n', tmp_path)
    r = subprocess.run([str(prog), "--scenario", str(tmp_path / "nope.json")], capture_output=True, text=True, timeout=30)
    assert r.returncode == 2 and "scénario" in r.stderr


# --- FreeRTOS queues -----------------------------------------------------------------------------------

QUEUE = HEADERS + '#include "freertos/queue.h"\n'


def test_queue_blocks_until_item(lib, tmp_path):
    trace = compile_and_run(QUEUE + """
static QueueHandle_t q;
static void consumer(void *) {
    int v = 0;
    BaseType_t ok = xQueueReceive(q, &v, pdMS_TO_TICKS(1000));
    ESP_LOGI("rx", "%d %d", (int)ok, v);
    vTaskDelete(NULL);
}
extern "C" void app_main(void) {
    q = xQueueCreate(4, sizeof(int));
    xTaskCreate(consumer, "rx", 2048, NULL, 5, NULL);
    vTaskDelay(pdMS_TO_TICKS(300));
    int v = 42;
    xQueueSend(q, &v, 0);
}
""", 2000, lib, tmp_path)
    assert levels(trace) == [(300, "1 42")]
    assert trace[-1] == {"t_ms": 2000, "ev": "end", "reason": "deadline"}


def test_queue_receive_timeout_returns_pdFALSE(lib, tmp_path):
    trace = compile_and_run(QUEUE + """
extern "C" void app_main(void) {
    QueueHandle_t q = xQueueCreate(2, sizeof(int));
    int v = 7;
    ESP_LOGI("rx", "%d", (int)xQueueReceive(q, &v, 0));
    ESP_LOGI("rx", "%d", (int)xQueueReceive(q, &v, pdMS_TO_TICKS(250)));
    ESP_LOGI("rx", "%d %d", v, (int)(xQueueReceive(q, &v, 0) == pdFALSE));
}
""", 1000, lib, tmp_path)
    assert levels(trace) == [(0, "0"), (250, "0"), (250, "7 1")]


def test_queue_full_send_times_out(lib, tmp_path):
    trace = compile_and_run(QUEUE + """
extern "C" void app_main(void) {
    QueueHandle_t q = xQueueCreate(1, sizeof(int));
    int a = 1, b = 2;
    ESP_LOGI("tx", "%d", (int)xQueueSend(q, &a, 0));
    ESP_LOGI("tx", "%d", (int)(xQueueSendToBack(q, &b, pdMS_TO_TICKS(100)) == errQUEUE_FULL));
    ESP_LOGI("tx", "%u", (unsigned)uxQueueMessagesWaiting(q));
}
""", 1000, lib, tmp_path)
    assert levels(trace) == [(0, "1"), (100, "1"), (100, "1")]


def test_queue_is_fifo_and_full_sender_waits_for_space(lib, tmp_path):
    trace = compile_and_run(QUEUE + """
static QueueHandle_t q;
static void producer(void *) {
    for (int i = 1; i <= 4; i++) {
        xQueueSend(q, &i, portMAX_DELAY);  // the 4th waits for room, freed by the first receive
        ESP_LOGI("tx", "%d", i);
    }
    vTaskDelete(NULL);
}
extern "C" void app_main(void) {
    q = xQueueCreate(3, sizeof(int));
    xTaskCreate(producer, "tx", 2048, NULL, 5, NULL);
    vTaskDelay(pdMS_TO_TICKS(100));
    int v;
    for (int n = 0; n < 4; n++) {
        xQueueReceive(q, &v, 0);
        ESP_LOGI("rx", "%d", v);
        vTaskDelay(pdMS_TO_TICKS(10));
    }
    vQueueDelete(q);
}
""", 1000, lib, tmp_path)
    assert [(e["t_ms"], e["tag"], e["msg"]) for e in logs(trace)] == [
        (0, "tx", "1"), (0, "tx", "2"), (0, "tx", "3"),
        (100, "rx", "1"), (100, "tx", "4"), (110, "rx", "2"), (120, "rx", "3"), (130, "rx", "4")]
    assert trace[-1]["reason"] == "deadline"


def test_queue_max_delay_receiver_woken_by_sender_task(lib, tmp_path):
    trace = compile_and_run(QUEUE + """
static QueueHandle_t q;
static void led(void *) {
    int v;
    for (;;) {
        if (xQueueReceive(q, &v, portMAX_DELAY) == pdTRUE) ESP_LOGI("rx", "%d", v);
    }
}
static void button(void *) {
    for (int i = 1;; i++) {
        vTaskDelay(pdMS_TO_TICKS(100));
        xQueueSend(q, &i, 0);
    }
}
extern "C" void app_main(void) {
    q = xQueueCreate(4, sizeof(int));
    xTaskCreate(led, "led", 4096, NULL, 5, NULL);
    xTaskCreate(button, "bouton", 3072, NULL, 4, NULL);
}
""", 350, lib, tmp_path)
    assert levels(trace) == [(100, "1"), (200, "2"), (300, "3")]
    assert [e for e in trace if e["ev"] == "task_create"] == [
        {"t_ms": 0, "ev": "task_create", "name": "main"},
        {"t_ms": 0, "ev": "task_create", "name": "led", "stack": 4096, "priority": 5},
        {"t_ms": 0, "ev": "task_create", "name": "bouton", "stack": 3072, "priority": 4},
    ]
    queue_events = [e for e in trace if e["ev"].startswith("queue")]
    assert queue_events[0] == {"t_ms": 0, "ev": "queue_create", "queue": 1, "length": 4, "item_size": 4}
    assert queue_events[1:3] == [
        {"t_ms": 100, "ev": "queue_send", "queue": 1, "task": "bouton", "ok": True},
        {"t_ms": 100, "ev": "queue_receive", "queue": 1, "task": "led", "ok": True},
    ]
    assert trace[-1] == {"t_ms": 350, "ev": "end", "reason": "deadline"}


def test_queue_zero_timeout_spin_is_busy(lib, tmp_path):
    prog = compile_src(lib, QUEUE + """
static QueueHandle_t q;
static void producer(void *) {
    vTaskDelay(pdMS_TO_TICKS(100));
    int v = 1;
    xQueueSend(q, &v, 0);
    vTaskDelete(NULL);
}
extern "C" void app_main(void) {
    q = xQueueCreate(1, sizeof(int));
    xTaskCreate(producer, "tx", 2048, NULL, 5, NULL);
    int x;
    while (!xQueueReceive(q, &x, 0)) {}
}
""", tmp_path)
    start = time.monotonic()
    trace = run(prog, 10000)
    assert time.monotonic() - start < 5
    assert trace[-1] == {"t_ms": 0, "ev": "end", "reason": "busy_loop", "task": "main"}
    assert not [e for e in trace if e["ev"] == "queue_receive"]  # failed zero-wait polls are not traced


# --- Fidelity of the exposed API to the real ESP-IDF -------------------------------------------------
# Learners copy their code to a real ESP-IDF project, so every declaration of sim/include must match
# the official API. signatures.json holds one entry per function, type or macro, with the official
# docs URL and the ESP-IDF version it was checked against. The parser below is deliberately small:
# comments and #include/#if/#pragma/#error lines are dropped, every other statement outside braces
# (function prototype, typedef, #define) is one declaration, compared with all whitespace removed.
# Enum constants and struct fields are covered by their enclosing typedef text.

INCLUDE = SIM / "include"
SIGNATURES = SIM / "signatures.json"

# Macros not compared with the real text, one reason each. Anything else must be in the table.
SKIPPED_MACROS = {
    "INC_FREERTOS_H": "include guard, same name as the real FreeRTOS.h",
    "CONFIG_FREERTOS_HZ": "sdkconfig (Kconfig) symbol, ESP-IDF default 100",
    "ESP_LOGE": "real expansion goes through ESP_LOG_LEVEL_LOCAL and the tag level filter; the form (tag, format, ...) is identical",
    "ESP_LOGW": "same as ESP_LOGE",
    "ESP_LOGI": "same as ESP_LOGE",
    "ESP_LOGD": "same as ESP_LOGE",
    "ESP_LOGV": "same as ESP_LOGE",
    "ESP_ERROR_CHECK": "real body also depends on NDEBUG and Kconfig options",
}


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s)


def parse_header(text: str) -> dict[str, str]:
    """name -> declaration text for the public functions, typedefs and macros of one header."""
    text = re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.S)
    text = text.replace("\\\n", " ")
    found: dict[str, str] = {}
    body = []
    for line in text.splitlines():
        s = line.strip()
        m = re.match(r"#\s*define\s+(\w+)", s)
        if m:
            found[m.group(1)] = "#define " + s.split(None, 1)[1]
        elif not s.startswith("#"):
            body.append(line)
    code = re.sub(r'extern\s+"C"\s*\{', "", "\n".join(body))
    depth, start = 0, 0
    for i, ch in enumerate(code):
        if ch == "{":
            depth += 1
        elif ch == "}":
            if depth == 0:  # closing brace of extern "C"
                start = i + 1
            else:
                depth -= 1
        elif ch == ";" and depth == 0:
            stmt = code[start:i + 1].strip()
            start = i + 1
            if stmt.startswith("typedef"):
                m = re.search(r"\(\s*\*\s*(\w+)\s*\)", stmt) or re.search(r"(\w+)\s*;$", stmt)
            else:
                m = re.search(r"(\w+)\s*\(", stmt)
            assert m, f"unparsable statement: {stmt!r}"
            found[m.group(1)] = stmt
    return found


def exposed_declarations() -> dict[tuple[str, str], str]:
    out = {}
    for h in sorted(INCLUDE.rglob("*.h")):
        rel = h.relative_to(INCLUDE).as_posix()
        for name, decl in parse_header(h.read_text(encoding="utf-8")).items():
            if name not in SKIPPED_MACROS:
                out[(rel, name)] = decl
    return out


def load_signatures() -> dict[tuple[str, str], dict]:
    entries = json.loads(SIGNATURES.read_text(encoding="utf-8"))
    table = {(e["header"], e["name"]): e for e in entries}
    assert len(table) == len(entries), "duplicate (header, name) in signatures.json"
    return table


def test_every_exposed_function_has_a_verified_signature():
    table, problems = load_signatures(), []
    for key, decl in exposed_declarations().items():
        e = table.get(key)
        if e is None:
            problems.append(f"{key}: no entry in signatures.json")
        elif not e["source"].startswith("https://docs.espressif.com/projects/esp-idf/") or not e["idf"]:
            problems.append(f"{key}: source must be an Espressif docs URL and idf set")
        elif _squash(e["decl"]) != _squash(decl):
            problems.append(f"{key}: sim has {decl!r}, official is {e['decl']!r}")
    assert not problems, "\n".join(problems)


def test_no_stale_signature():
    exposed = exposed_declarations()
    stale = [k for k in load_signatures() if k not in exposed]
    assert not stale, f"entries without a declaration in sim/include: {stale}"
    all_names = {n for h in INCLUDE.rglob("*.h") for n in parse_header(h.read_text(encoding="utf-8"))}
    assert not set(SKIPPED_MACROS) - all_names, "stale SKIPPED_MACROS entries"


# ---------------------------------------------------------------- ADC, I2C and the pool-tank plant

ADC = HEADERS + '#include "driver/gpio.h"\n#include "esp_adc/adc_oneshot.h"\n'
I2C = HEADERS + '#include "driver/i2c_master.h"\n'

ADC_READER = ADC + """
extern "C" void app_main(void) {
    adc_oneshot_unit_handle_t adc;
    adc_oneshot_unit_init_cfg_t ucfg = {};
    ucfg.unit_id = ADC_UNIT_1;
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&ucfg, &adc));
    adc_oneshot_chan_cfg_t ccfg = {};
    ccfg.atten = ADC_ATTEN_DB_12;
    ccfg.bitwidth = ADC_BITWIDTH_DEFAULT;
    ESP_ERROR_CHECK(adc_oneshot_config_channel(adc, ADC_CHANNEL_0, &ccfg));
    gpio_config_t io = {};
    io.pin_bit_mask = 1ULL << 5;
    io.mode = GPIO_MODE_OUTPUT;
    ESP_ERROR_CHECK(gpio_config(&io));
    int at[] = {%s};  // read times (ms); a negative one first sets the relay (|t|) instead of reading
    int prev = 0;
    for (int t : at) {
        int when = t == -1 ? 0 : t < 0 ? -t : t;
        vTaskDelay(pdMS_TO_TICKS(when - prev));
        prev = when;
        if (t < 0) { ESP_ERROR_CHECK(gpio_set_level(GPIO_NUM_5, 1)); continue; }
        int raw = -1;
        esp_err_t err = adc_oneshot_read(adc, ADC_CHANNEL_0, &raw);
        ESP_LOGI("adc", "%%d %%d", (int)err, raw);
    }
}
"""
RELAY_ON = "-1"  # entry of `at`: relay on right at 0 ms


def adc_reads(trace):
    return [int(e["msg"].split()[1]) for e in logs(trace) if e["tag"] == "adc"]


def test_adc_follows_scenario_interpolated(lib, tmp_path):
    trace = compile_and_run(ADC_READER % "0, 500, 1500, 2000, 3000", 5000, lib, tmp_path,
                            '{"adc": [{"t_ms": 2000, "channel": 0, "raw": 4000}, {"t_ms": 1000, "channel": 0, "raw": 1000}, '
                            '{"t_ms": 0, "channel": 0, "raw": 0}, {"t_ms": 0, "channel": 3, "raw": 9}]}')
    # linear between points, clamped after the last one; the 12-bit range is 0..4095
    assert adc_reads(trace) == [0, 500, 2500, 4000, 4000]
    assert [(e["t_ms"], e["channel"], e["raw"]) for e in trace if e["ev"] == "adc_read"][:2] == [(0, 0, 0), (500, 0, 500)]


def test_adc_clamps_before_first_point_and_without_points(lib, tmp_path):
    trace = compile_and_run(ADC_READER % "0, 100", 1000, lib, tmp_path, '{"adc": [{"t_ms": 50, "channel": 0, "raw": 700}]}')
    assert adc_reads(trace) == [700, 700]
    assert adc_reads(compile_and_run(ADC_READER % "100", 1000, lib, tmp_path)) == [0]


def test_adc_unconfigured_channel_and_bad_handles(lib, tmp_path):
    trace = compile_and_run(ADC + """
extern "C" void app_main(void) {
    adc_oneshot_unit_handle_t adc;
    adc_oneshot_unit_init_cfg_t ucfg = {};
    ucfg.unit_id = ADC_UNIT_1;
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&ucfg, &adc));
    int raw = 7;
    adc_oneshot_chan_cfg_t ccfg = {};
    ccfg.atten = ADC_ATTEN_DB_12;
    ccfg.bitwidth = ADC_BITWIDTH_12;
    ESP_LOGI("r", "%d", (int)adc_oneshot_read(adc, ADC_CHANNEL_4, &raw));            // never configured
    ESP_LOGI("r", "%d", (int)adc_oneshot_read(nullptr, ADC_CHANNEL_4, &raw));        // no handle
    ESP_LOGI("r", "%d", (int)adc_oneshot_config_channel(adc, ADC_CHANNEL_4, nullptr));
    ESP_LOGI("r", "%d", (int)adc_oneshot_config_channel(adc, ADC_CHANNEL_4, &ccfg));
    ESP_LOGI("r", "%d", (int)adc_oneshot_read(adc, ADC_CHANNEL_4, nullptr));         // no out_raw
    ESP_LOGI("r", "%d", (int)adc_oneshot_read(adc, ADC_CHANNEL_4, &raw));            // now fine
    ESP_LOGI("r", "%d", (int)adc_oneshot_new_unit(&ucfg, &adc));                     // unit already claimed
    ESP_LOGI("r", "%d", (int)adc_oneshot_del_unit(adc));
    ESP_LOGI("r", "%d", (int)adc_oneshot_read(adc, ADC_CHANNEL_4, &raw));            // deleted handle
    ESP_LOGI("r", "%d", (int)adc_oneshot_del_unit(adc));
}
""", 1000, lib, tmp_path)
    inv, nf = 0x102, 0x105
    assert [e["msg"] for e in logs(trace)] == [str(c) for c in (inv, inv, inv, 0, inv, 0, nf, 0, inv, inv)]
    assert len([e for e in trace if e["ev"] == "adc_read"]) == 1  # only the successful read is traced


I2C_PROBE = I2C + """
extern "C" void app_main(void) {
    i2c_master_bus_config_t bcfg = {};
    bcfg.i2c_port = I2C_NUM_0;
    bcfg.sda_io_num = GPIO_NUM_21;
    bcfg.scl_io_num = GPIO_NUM_22;
    bcfg.clk_source = I2C_CLK_SRC_DEFAULT;
    bcfg.glitch_ignore_cnt = 7;
    i2c_master_bus_handle_t bus;
    ESP_ERROR_CHECK(i2c_new_master_bus(&bcfg, &bus));
    i2c_device_config_t dcfg = {};
    dcfg.dev_addr_length = I2C_ADDR_BIT_LEN_7;
    dcfg.device_address = %s;
    dcfg.scl_speed_hz = 100000;
    i2c_master_dev_handle_t dev;
    ESP_ERROR_CHECK(i2c_master_bus_add_device(bus, &dcfg, &dev));
    int at[] = {0, 1500, 2000};
    int prev = 0;
    for (int t : at) {
        vTaskDelay(pdMS_TO_TICKS(t - prev));
        prev = t;
        uint8_t w = 0xE0, r[3] = {1, 1, 1};
        esp_err_t err = i2c_master_transmit_receive(dev, &w, 1, r, 3, 100);
        ESP_LOGI("i2c", "%%d %%d %%d %%d", (int)err, r[0], r[1], r[2]);
    }
}
"""
I2C_SCENARIO = '{"i2c": {"0x44": {"bytes": [18, 52], "nack": [{"from_ms": 1000, "to_ms": 2000}]}}}'
TIMEOUT = "263"  # ESP_ERR_TIMEOUT = 0x107


def test_i2c_nack_returns_timeout(lib, tmp_path):
    trace = compile_and_run(I2C_PROBE % "0x44", 5000, lib, tmp_path, I2C_SCENARIO)
    # scenario bytes first, zero padded; NACK window [1000, 2000) fails and leaves the buffer alone
    assert [e["msg"] for e in logs(trace)] == ["0 18 52 0", f"{TIMEOUT} 1 1 1", "0 18 52 0"]
    assert [(e["t_ms"], e["addr"], e["ok"]) for e in trace if e["ev"] == "i2c_xfer"] == [
        (0, 0x44, True), (1500, 0x44, False), (2000, 0x44, True)]


def test_i2c_series_changes_bytes_over_time(lib, tmp_path):
    # step function: the last step with t_ms <= now wins (unsorted input is fine); before the first step, "bytes"
    series = '[{"t_ms": 1800, "bytes": [3, 4]}, {"t_ms": 1000, "bytes": [1]}]'
    trace = compile_and_run(I2C_PROBE % "0x44", 5000, lib, tmp_path, '{"i2c": {"0x44": {"bytes": [18, 52], "series": %s}}}' % series)
    assert [e["msg"] for e in logs(trace)] == ["0 18 52 0", "0 1 0 0", "0 3 4 0"]
    # series alone: the device answers zeros before the first step
    trace = compile_and_run(I2C_PROBE % "0x44", 5000, lib, tmp_path, '{"i2c": {"0x44": {"series": [{"t_ms": 1000, "bytes": [9]}]}}}')
    assert [e["msg"] for e in logs(trace)] == ["0 0 0 0", "0 9 0 0", "0 9 0 0"]


def test_i2c_unknown_address_returns_timeout(lib, tmp_path):
    trace = compile_and_run(I2C_PROBE % "0x45", 5000, lib, tmp_path, I2C_SCENARIO)
    assert [e["msg"] for e in logs(trace)] == [f"{TIMEOUT} 1 1 1"] * 3
    assert {(e["addr"], e["ok"]) for e in trace if e["ev"] == "i2c_xfer"} == {(0x45, False)}


def test_i2c_split_transfers_and_bad_handles(lib, tmp_path):
    trace = compile_and_run(I2C + """
extern "C" void app_main(void) {
    i2c_master_bus_config_t bcfg = {};
    bcfg.i2c_port = -1;
    bcfg.sda_io_num = GPIO_NUM_21;
    bcfg.scl_io_num = GPIO_NUM_22;
    bcfg.clk_source = I2C_CLK_SRC_DEFAULT;
    i2c_master_bus_handle_t bus;
    ESP_ERROR_CHECK(i2c_new_master_bus(&bcfg, &bus));
    i2c_device_config_t dcfg = {};
    dcfg.dev_addr_length = I2C_ADDR_BIT_LEN_7;
    dcfg.device_address = 0x44;
    dcfg.scl_speed_hz = 100000;
    i2c_master_dev_handle_t dev;
    ESP_ERROR_CHECK(i2c_master_bus_add_device(bus, &dcfg, &dev));
    uint8_t w[2] = {1, 2}, r[2] = {0, 0};
    ESP_LOGI("r", "%d", (int)i2c_master_transmit(dev, w, 2, -1));
    ESP_LOGI("r", "%d", (int)i2c_master_receive(dev, r, 2, 100));
    ESP_LOGI("r", "%d %d", r[0], r[1]);
    ESP_LOGI("r", "%d", (int)i2c_master_transmit(nullptr, w, 2, 100));
    ESP_LOGI("r", "%d", (int)i2c_master_receive(dev, nullptr, 2, 100));
    ESP_LOGI("r", "%d", (int)i2c_master_bus_add_device(nullptr, &dcfg, &dev));
    ESP_LOGI("r", "%d", (int)i2c_master_bus_rm_device(dev));
    ESP_LOGI("r", "%d", (int)i2c_master_transmit(dev, w, 2, 100));
    ESP_LOGI("r", "%d", (int)i2c_del_master_bus(bus));
    ESP_LOGI("r", "%d", (int)i2c_del_master_bus(bus));
}
""", 1000, lib, tmp_path, I2C_SCENARIO)
    assert [e["msg"] for e in logs(trace)] == ["0", "0", "18 52", "258", "258", "258", "0", "258", "0", "258"]


def test_scenario_without_adc_i2c_plant_is_unchanged(lib, tmp_path):
    trace = compile_and_run(ADC_READER % "100", 1000, lib, tmp_path, '{"gpio_in": []}')
    assert adc_reads(trace) == [0]


@pytest.mark.parametrize("scenario", [
    '{"adc": 3}', '{"adc": [{"t_ms": 0, "channel": 0}]}', '{"adc": [{"t_ms": 0, "channel": 0, "raw": 4096}]}',
    '{"i2c": []}', '{"i2c": {"zz": {"bytes": []}}}', '{"i2c": {"0x44": {"bytes": [256]}}}',
    '{"i2c": {"0x44": {"bytes": [1], "nack": [{"from_ms": 5}]}}}', '{"i2c": {"0x44": {}}}',
    '{"i2c": {"0x44": {"series": 3}}}', '{"i2c": {"0x44": {"series": [{"t_ms": 0}]}}}',
    '{"i2c": {"0x44": {"series": [{"t_ms": 0, "bytes": [300]}]}}}', '{"i2c": {"0x44": {"series": [{"bytes": [1]}]}}}',
    '{"plant": {"tank": {"level_pct0": 120}}}', '{"plant": []}',
])
def test_malformed_adc_i2c_plant_scenario_fails_cleanly(lib, tmp_path, scenario):
    prog = compile_src(lib, ADC_READER % "100", tmp_path)
    (tmp_path / "s.json").write_text(scenario, encoding="utf-8")
    r = subprocess.run([str(prog), "--scenario", str(tmp_path / "s.json")], capture_output=True, text=True, timeout=30)
    assert r.returncode == 2 and r.stdout == "" and r.stderr


def tank(level0=50, fill=60, loss=30, extra=""):
    return ('{"plant": {"tank": {"level_pct0": %s, "fill_pct_per_min": %s, "loss_pct_per_min": %s, "relay_pin": 5, '
            '"adc_channel": 0, "raw_at_0": 0, "raw_at_100": 4000%s}}}' % (level0, fill, loss, extra))


# 60 %/min = 1 %/s; raw_at_100 = 4000, so 40 raw per %

def test_plant_level_rises_when_relay_on(lib, tmp_path):
    trace = compile_and_run(ADC_READER % f"{RELAY_ON}, 10000, 20000", 30000, lib, tmp_path, tank())
    assert adc_reads(trace) == [2400, 2400 + 400]


def test_plant_loses_level_when_relay_off(lib, tmp_path):
    # 30 %/min: 50 % -> 45 % after 10 s; then relay on 5 s (+5): 50 %
    trace = compile_and_run(ADC_READER % "0, 10000, -10000, 15000", 30000, lib, tmp_path, tank())
    assert adc_reads(trace) == [2000, 1800, 2000]


def test_plant_level_clamped(lib, tmp_path):
    trace = compile_and_run(ADC_READER % f"{RELAY_ON}, 10000, 20000", 30000, lib, tmp_path, tank(level0=95))
    assert adc_reads(trace) == [4000, 4000]
    trace = compile_and_run(ADC_READER % "10000, 20000", 30000, lib, tmp_path, tank(level0=5, loss=60))
    assert adc_reads(trace) == [0, 0]


def test_plant_stuck_sensor_holds_value(lib, tmp_path):
    stuck = ', "stuck": [{"from_ms": 5000, "to_ms": 15000}]'
    trace = compile_and_run(ADC_READER % f"{RELAY_ON}, 4000, 5000, 12000, 15000", 30000, lib, tmp_path,
                            tank(level0=0, extra=stuck))
    # from 0 % at 1 %/s: 4 % -> 160, frozen at the 5 % reached when the window opens (200), live again at 15 s (15 % = 600)
    assert adc_reads(trace) == [160, 200, 200, 600]


def test_plant_integration_is_exact_and_drift_free(lib, tmp_path):
    # 6 %/min = 0.1 %/s: 1 s -> 0.1 % (raw 4), 10 min -> 60 % (raw 2400), whatever the read pattern
    reads = ", ".join(str(t) for t in range(1000, 11000, 1000)) + ", 600000"
    trace = compile_and_run(ADC_READER % f"{RELAY_ON}, {reads}", 700000, lib, tmp_path, tank(level0=0, fill=6, loss=0))
    assert adc_reads(trace)[0] == 4 and adc_reads(trace)[-1] == 2400


PIN_BEFORE_CONFIG = ADC + """
extern "C" void app_main(void) {
    adc_oneshot_unit_handle_t adc;
    adc_oneshot_unit_init_cfg_t ucfg = {};
    ucfg.unit_id = ADC_UNIT_1;
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&ucfg, &adc));
    adc_oneshot_chan_cfg_t ccfg = {};
    ccfg.atten = ADC_ATTEN_DB_12;
    ccfg.bitwidth = ADC_BITWIDTH_DEFAULT;
    ESP_ERROR_CHECK(adc_oneshot_config_channel(adc, ADC_CHANNEL_0, &ccfg));
    gpio_set_level(GPIO_NUM_5, 1);            // not an output yet: drives nothing
    vTaskDelay(pdMS_TO_TICKS(10000));
    %s
    vTaskDelay(pdMS_TO_TICKS(5000));
    int raw = -1;
    ESP_ERROR_CHECK(adc_oneshot_read(adc, ADC_CHANNEL_0, &raw));
    ESP_LOGI("adc", "0 %%d", raw);
}
"""
CONFIG_OUT = "gpio_config_t io = {}; io.pin_bit_mask = 1ULL << 5; io.mode = GPIO_MODE_OUTPUT; ESP_ERROR_CHECK(gpio_config(&io));"
DIRECTION_OUT = "ESP_ERROR_CHECK(gpio_set_direction(GPIO_NUM_5, GPIO_MODE_OUTPUT));"


@pytest.mark.parametrize("make_output", [CONFIG_OUT, DIRECTION_OUT], ids=["gpio_config", "gpio_set_direction"])
def test_plant_synced_when_pin_becomes_output(lib, tmp_path, make_output):
    # 1 %/s: the relay drives the tank only once the pin is an output, i.e. 5 s -> 5 % (raw 200), not 15 % (600)
    trace = compile_and_run(PIN_BEFORE_CONFIG % make_output, 30000, lib, tmp_path, tank(level0=0, loss=0))
    assert adc_reads(trace) == [200]


def test_plant_synced_when_output_is_disabled(lib, tmp_path):
    # driven high for 20 s (20 %), then the pin is released: the tank stops filling, 5 s of loss (30 %/min) follow
    src = PIN_BEFORE_CONFIG % (CONFIG_OUT + " gpio_set_level(GPIO_NUM_5, 1); vTaskDelay(pdMS_TO_TICKS(20000)); "
                               "ESP_ERROR_CHECK(gpio_set_direction(GPIO_NUM_5, GPIO_MODE_DISABLE));")
    trace = compile_and_run(src, 50000, lib, tmp_path, tank(level0=50))
    # 50 % - 5 (10 s of loss, 0.5 %/s, pin not yet an output) = 45 ; +20 s fill = 65 ; -2.5 (5 s of loss) = 62.5 -> raw 2500
    assert adc_reads(trace) == [2500]
