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


# --- FreeRTOS event groups ------------------------------------------------------------------------------

EVG = HEADERS + '#include "freertos/event_groups.h"\n'


def test_event_group_wait_blocks_until_set_and_clears_on_exit(lib, tmp_path):
    trace = compile_and_run(EVG + """
static EventGroupHandle_t g;
static void waiter(void *) {
    EventBits_t b = xEventGroupWaitBits(g, 0x3, pdTRUE, pdFALSE, portMAX_DELAY);  // any of 2 bits, clear on exit
    ESP_LOGI("w", "%x %x", (unsigned)b, (unsigned)xEventGroupWaitBits(g, 0x7, pdFALSE, pdFALSE, 0));
    vTaskDelete(NULL);
}
extern "C" void app_main(void) {
    g = xEventGroupCreate();
    xTaskCreate(waiter, "w", 2048, NULL, 5, NULL);
    vTaskDelay(pdMS_TO_TICKS(300));
    EventBits_t r = xEventGroupSetBits(g, 0x5);  // bit 0 wakes the waiter; bit 2 is not waited for
    ESP_LOGI("m", "%x", (unsigned)r);
}
""", 1000, lib, tmp_path)
    # the clear is applied by the set: its return value has bit 0 gone; the waiter was released with the bits it saw (0x5)
    assert levels(trace) == [(300, "4"), (300, "5 4")]


def test_event_group_timeout_returns_current_bits_without_clearing(lib, tmp_path):
    trace = compile_and_run(EVG + """
extern "C" void app_main(void) {
    EventGroupHandle_t g = xEventGroupCreate();
    xEventGroupSetBits(g, 0x1);
    EventBits_t b = xEventGroupWaitBits(g, 0x3, pdTRUE, pdTRUE, pdMS_TO_TICKS(250));  // needs both: times out
    ESP_LOGI("t", "%x", (unsigned)b);
    b = xEventGroupWaitBits(g, 0x1, pdTRUE, pdTRUE, 0);  // already set: no wait, cleared on exit
    ESP_LOGI("t", "%x %x", (unsigned)b, (unsigned)xEventGroupWaitBits(g, 0x1, pdFALSE, pdFALSE, 0));
}
""", 1000, lib, tmp_path)
    assert levels(trace) == [(250, "1"), (250, "1 0")]


def test_event_group_wait_for_all_bits_needs_every_bit(lib, tmp_path):
    trace = compile_and_run(EVG + """
static EventGroupHandle_t g;
static void setter(void *) {
    vTaskDelay(pdMS_TO_TICKS(100));
    xEventGroupSetBits(g, 0x1);
    vTaskDelay(pdMS_TO_TICKS(100));
    xEventGroupSetBits(g, 0x2);
    vTaskDelete(NULL);
}
extern "C" void app_main(void) {
    g = xEventGroupCreate();
    xTaskCreate(setter, "s", 2048, NULL, 5, NULL);
    EventBits_t b = xEventGroupWaitBits(g, 0x3, pdFALSE, pdTRUE, portMAX_DELAY);
    ESP_LOGI("all", "%x", (unsigned)b);
}
""", 1000, lib, tmp_path)
    assert levels(trace) == [(200, "3")]


def test_event_group_clear_bits_returns_value_before_clearing(lib, tmp_path):
    trace = compile_and_run(EVG + """
extern "C" void app_main(void) {
    EventGroupHandle_t g = xEventGroupCreate();
    xEventGroupSetBits(g, 0x6);
    EventBits_t before = xEventGroupClearBits(g, 0x2);
    ESP_LOGI("c", "%x %x", (unsigned)before, (unsigned)xEventGroupClearBits(g, 0));
    vEventGroupDelete(g);
}
""", 1000, lib, tmp_path)
    assert levels(trace) == [(0, "6 4")]


def test_event_group_one_set_releases_every_waiter_even_with_clear_on_exit(lib, tmp_path):
    # FreeRTOS applies the clear after unblocking all the tasks the set satisfies: both waiters see the bit.
    trace = compile_and_run(EVG + """
static EventGroupHandle_t g;
static void waiter(void *arg) {
    EventBits_t b = xEventGroupWaitBits(g, 0x1, pdTRUE, pdFALSE, portMAX_DELAY);
    ESP_LOGI("w", "%s %x", (const char *)arg, (unsigned)b);
    vTaskDelete(NULL);
}
extern "C" void app_main(void) {
    g = xEventGroupCreate();
    xTaskCreate(waiter, "a", 2048, (void *)"a", 5, NULL);
    xTaskCreate(waiter, "b", 2048, (void *)"b", 5, NULL);
    vTaskDelay(pdMS_TO_TICKS(100));
    xEventGroupSetBits(g, 0x1);
    vTaskDelay(pdMS_TO_TICKS(100));
    ESP_LOGI("m", "%x", (unsigned)xEventGroupWaitBits(g, 0x1, pdFALSE, pdFALSE, 0));
}
""", 1000, lib, tmp_path)
    assert levels(trace) == [(100, "a 1"), (100, "b 1"), (200, "0")]


def test_event_group_set_from_event_handler_wakes_main(lib, tmp_path):
    # the Wi-Fi station pattern: the handler (task sys_evt) sets a bit, app_main waits for it
    trace = compile_and_run(EVG + """
#include "esp_event.h"
ESP_EVENT_DEFINE_BASE(DEMO_EVENT);
static EventGroupHandle_t g;
static void handler(void *, esp_event_base_t, int32_t id, void *) { xEventGroupSetBits(g, 1 << id); }
extern "C" void app_main(void) {
    g = xEventGroupCreate();
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    ESP_ERROR_CHECK(esp_event_handler_register(DEMO_EVENT, ESP_EVENT_ANY_ID, handler, NULL));
    ESP_ERROR_CHECK(esp_event_post(DEMO_EVENT, 3, NULL, 0, 0));
    EventBits_t b = xEventGroupWaitBits(g, 1 << 3, pdTRUE, pdFALSE, pdMS_TO_TICKS(500));
    ESP_LOGI("m", "%x", (unsigned)b);
}
""", 1000, lib, tmp_path)
    assert levels(trace) == [(0, "8")]


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
    "CONFIG_ESP_WIFI_SSID": "project Kconfig symbol of the official station example (sample value in the sim)",
    "CONFIG_ESP_WIFI_PASSWORD": "project Kconfig symbol of the official station example (sample value in the sim)",
    "ESP_ERROR_CHECK": "real body also depends on NDEBUG and Kconfig options",
    # Not only macros: declarations the sim deliberately shortens (see the comment at the top of the header).
    "WIFI_INIT_CONFIG_DEFAULT": "real initialiser fills ~25 driver-tuning fields and Kconfig-dependent values",
    "wifi_init_config_t": "real struct has the full driver-tuning field list; a learner only passes the macro through",
    "wifi_sta_config_t": "real struct also has the he_*/vht_* bit-fields (HE/VHT tuning, none used by the course)",
    "wifi_ap_config_t": "AP mode is not simulated: shortened field list",
    "wifi_event_t": "enum prefix: values of the listed constants are the real ones, later events are not simulated",
    "wifi_err_reason_t": "subset of the constants (real values); the 802.11 reason codes the sim never raises are left out",
    "esp_mqtt_client_config_t": "no TLS, certificate, ds, ecdsa or tcp_keep_alive fields; the fields present keep the real names and order",
    "esp_mqtt_event_t": "no MQTT 5 properties; the fields present keep the real names and order",
    "esp_mqtt_client_subscribe": "real macro dispatches with _Generic between the single and multiple variants",
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


# ---------------------------------------- NVS, event loop, Wi-Fi, MQTT, watchdog, restarts (Task 15)

SYS = HEADERS + '''#include "driver/gpio.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "esp_task_wdt.h"
#include "nvs_flash.h"
#include "nvs.h"
#include "mqtt_client.h"
#include <string.h>
#include <stdio.h>
'''


def msgs(trace, tag):
    return [e["msg"] for e in logs(trace) if e["tag"] == tag]


def sim_run(src, max_ms, lib, tmp_path, scenario=None):
    return compile_and_run(SYS + src, max_ms, lib, tmp_path, scenario)


NVS_BOOT = """
static int ram = 0;
extern "C" void app_main(void) {
    ram++;
    ESP_ERROR_CHECK(nvs_flash_init());
    nvs_handle_t h;
    ESP_ERROR_CHECK(nvs_open("cfg", NVS_READWRITE, &h));
    uint32_t boots = 0;
    esp_err_t e = nvs_get_u32(h, "boots", &boots);
    int32_t tmp = 0;
    esp_err_t e2 = nvs_get_i32(h, "tmp", &tmp);
    ESP_LOGI("boot", "boots=%u get=%s tmp=%s ram=%d reason=%d", (unsigned)boots, esp_err_to_name(e),
             esp_err_to_name(e2), ram, (int)esp_reset_reason());
    ESP_ERROR_CHECK(nvs_set_u32(h, "boots", boots + 1));
    ESP_ERROR_CHECK(nvs_commit(h));
    ESP_ERROR_CHECK(nvs_set_i32(h, "tmp", 7));  // never committed
    nvs_close(h);
    for (;;) vTaskDelay(pdMS_TO_TICKS(100));
}
"""


def test_nvs_persists_across_scripted_reboot(lib, tmp_path):
    trace = sim_run(NVS_BOOT, 5000, lib, tmp_path, '{"reboots_at_ms": [2000]}')
    # boot 2: committed value survives, uncommitted write and RAM (static) are lost, reason is power-on (1)
    assert msgs(trace, "boot") == [
        "boots=0 get=ESP_ERR_NVS_NOT_FOUND tmp=ESP_ERR_NVS_NOT_FOUND ram=1 reason=1",
        "boots=1 get=ESP_OK tmp=ESP_ERR_NVS_NOT_FOUND ram=1 reason=1",
    ]
    reboots = [e for e in trace if e["ev"] == "reboot"]
    assert [(e["t_ms"], e["reason"]) for e in reboots] == [(2000, "scripted")]
    assert [e["name"] for e in trace if e["ev"] == "task_create"] == ["main", "main"]
    sets = [e for e in trace if e["ev"] == "nvs_set"]
    assert sets[0]["ns"] == "cfg" and sets[0]["key"] == "boots" and sets[0]["value"] == 1
    assert trace[-1]["ev"] == "end" and trace[-1]["reason"] == "deadline"


def test_esp_restart_gives_sw_reason_and_restarts_the_chip_clock(lib, tmp_path):
    trace = sim_run("""
extern "C" void app_main(void) {
    ESP_LOGI("r", "reason=%d t=%d", (int)esp_reset_reason(), (int)(esp_timer_get_time() / 1000));
    vTaskDelay(pdMS_TO_TICKS(500));
    if (esp_reset_reason() == ESP_RST_POWERON) esp_restart();
    vTaskDelay(pdMS_TO_TICKS(100));
}
""", 3000, lib, tmp_path)
    assert msgs(trace, "r") == ["reason=1 t=0", "reason=3 t=0"]  # the chip clock restarts at 0
    assert [(e["t_ms"], e["reason"]) for e in trace if e["ev"] == "reboot"] == [(500, "sw")]
    assert [e["t_ms"] for e in logs(trace)] == [0, 500]  # the trace clock does not


def test_same_scenario_same_trace_across_reboots(lib, tmp_path):
    prog = compile_src(lib, SYS + NVS_BOOT, tmp_path)
    sc = '{"reboots_at_ms": [1000, 1000, 3000]}'
    assert run(prog, 6000, sc) == run(prog, 6000, sc)


def test_hardware_state_is_reset_by_reboot(lib, tmp_path):
    trace = sim_run("""
extern "C" void app_main(void) {
    ESP_LOGI("r", "before=%d", gpio_get_level(GPIO_NUM_5));
    gpio_config_t io = {}; io.pin_bit_mask = 1ULL << 5; io.mode = GPIO_MODE_INPUT_OUTPUT;
    ESP_ERROR_CHECK(gpio_config(&io));
    gpio_set_level(GPIO_NUM_5, 1);
    ESP_LOGI("r", "after=%d", gpio_get_level(GPIO_NUM_5));
    vTaskDelay(pdMS_TO_TICKS(1000));
}
""", 3000, lib, tmp_path, '{"reboots_at_ms": [1500]}')
    # the pin is back to its reset state (disabled, reads 0) after the power cycle
    assert msgs(trace, "r") == ["before=0", "after=1", "before=0", "after=1"]


def test_nvs_error_cases(lib, tmp_path):
    trace = sim_run("""
#define R(x) ESP_LOGI("r", "%s", esp_err_to_name(x))
extern "C" void app_main(void) {
    nvs_handle_t h = 0;
    R(nvs_open("cfg", NVS_READWRITE, &h));                 // before nvs_flash_init
    ESP_ERROR_CHECK(nvs_flash_init());
    R(nvs_flash_init());                                   // twice is fine
    R(nvs_open("nope", NVS_READONLY, &h));                 // unknown namespace
    R(nvs_open("a_namespace_too_long", NVS_READWRITE, &h));
    R(nvs_open("", NVS_READWRITE, &h));
    ESP_ERROR_CHECK(nvs_open("cfg", NVS_READWRITE, &h));
    uint8_t u8 = 0; int32_t i32 = 0; char buf[4]; size_t len = sizeof buf;
    R(nvs_get_i32(h, "missing", &i32));                    // unknown key
    R(nvs_set_i32(h, "k", 5));
    R(nvs_get_u8(h, "k", &u8));                            // wrong type
    R(nvs_set_i32(h, "this_key_is_too_long", 1));
    R(nvs_set_str(h, "s", "toolong"));
    R(nvs_get_str(h, "s", buf, &len));                     // buffer too small
    ESP_LOGI("r", "len=%d", (int)len);
    R(nvs_get_str(h, "s", NULL, &len));
    ESP_LOGI("r", "len=%d", (int)len);
    R(nvs_commit(h));
    nvs_close(h);
    R(nvs_set_i32(h, "k", 6));                             // closed handle
    ESP_ERROR_CHECK(nvs_open("cfg", NVS_READONLY, &h));
    R(nvs_set_i32(h, "k", 6));                             // read-only handle
    R(nvs_get_i32(h, "k", &i32));
    ESP_LOGI("r", "k=%d", (int)i32);
    nvs_close(h);
    R(nvs_flash_erase());
    R(nvs_open("cfg", NVS_READONLY, &h));                  // erased: must init again
    ESP_ERROR_CHECK(nvs_flash_init());
    R(nvs_open("cfg", NVS_READONLY, &h));
}
""", 100, lib, tmp_path)
    assert msgs(trace, "r") == [
        "ESP_ERR_NVS_NOT_INITIALIZED", "ESP_OK", "ESP_ERR_NVS_NOT_FOUND", "ESP_ERR_NVS_INVALID_NAME",
        "ESP_ERR_NVS_INVALID_NAME", "ESP_ERR_NVS_NOT_FOUND", "ESP_OK", "ESP_ERR_NVS_TYPE_MISMATCH",
        "ESP_ERR_NVS_KEY_TOO_LONG", "ESP_OK", "ESP_ERR_NVS_INVALID_LENGTH", "len=8", "ESP_OK", "len=8",
        "ESP_OK", "ESP_ERR_NVS_INVALID_HANDLE", "ESP_ERR_NVS_READ_ONLY", "ESP_OK", "k=5",
        "ESP_OK", "ESP_ERR_NVS_NOT_INITIALIZED", "ESP_ERR_NVS_NOT_FOUND",
    ]


WIFI_APP = """
static void on_wifi(void *arg, esp_event_base_t base, int32_t id, void *data) {
    gpio_set_level(GPIO_NUM_2, 1);  // traced with the name of the task running the handler
    if (id == WIFI_EVENT_STA_START) { ESP_LOGI("w", "start"); esp_wifi_connect(); }
    else if (id == WIFI_EVENT_STA_DISCONNECTED) {
        wifi_event_sta_disconnected_t *d = (wifi_event_sta_disconnected_t *)data;
        ESP_LOGI("w", "disconnected reason=%d", d->reason);
        esp_wifi_connect();
    } else if (id == WIFI_EVENT_STA_CONNECTED) ESP_LOGI("w", "connected");
}
static void on_ip(void *arg, esp_event_base_t base, int32_t id, void *data) {
    ip_event_got_ip_t *e = (ip_event_got_ip_t *)data;
    ESP_LOGI("w", "ip " IPSTR, IP2STR(&e->ip_info.ip));
}
static void wifi_up(void) {
    ESP_ERROR_CHECK(nvs_flash_init());
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &on_wifi, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &on_ip, NULL));
    wifi_config_t wc = {};
    strcpy((char *)wc.sta.ssid, "maison");
    strcpy((char *)wc.sta.password, "secret123");
    wc.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wc));
    ESP_ERROR_CHECK(esp_wifi_start());
}
"""
WIFI_MAIN = 'extern "C" void app_main(void) { wifi_up(); for (;;) vTaskDelay(pdMS_TO_TICKS(1000)); }\n'


def test_wifi_fails_n_attempts_then_connects(lib, tmp_path):
    trace = sim_run(WIFI_APP + WIFI_MAIN, 20000, lib, tmp_path, '{"wifi": {"up_from_ms": 0, "fail_attempts": 2}}')
    assert [e["event"] for e in trace if e["ev"] == "wifi"] == [
        "sta_start", "sta_disconnected", "sta_disconnected", "sta_connected", "got_ip"]
    assert msgs(trace, "w") == ["start", "disconnected reason=205", "disconnected reason=205", "connected", "ip 192.168.1.42"]
    assert {e["task"] for e in trace if e["ev"] == "gpio_set"} == {"sys_evt"}  # handlers run in the event-loop task
    times = [e["t_ms"] for e in trace if e["ev"] == "wifi"]
    assert times == sorted(times) and times[0] == 0 and times[-1] < 10000
    assert all(t % 10 == 0 for t in times)


def test_wifi_waits_for_up_from_and_down_windows(lib, tmp_path):
    sc = '{"wifi": {"up_from_ms": 5000, "down": [{"from_ms": 8000, "to_ms": 12000}]}}'
    trace = sim_run(WIFI_APP + WIFI_MAIN, 30000, lib, tmp_path, sc)
    w = [(e["t_ms"], e["event"]) for e in trace if e["ev"] == "wifi"]
    first_ok = next(t for t, ev in w if ev == "got_ip")
    assert first_ok >= 5000
    # the link drops when the window opens, and the learner's reconnect only succeeds after it closes
    drop = next(t for t, ev in w if ev == "sta_disconnected" and t >= first_ok)
    assert 8000 <= drop < 8100
    assert [t for t, ev in w if ev == "got_ip"][-1] >= 12000


def test_esp_wifi_init_requires_nvs(lib, tmp_path):
    # WIFI_INIT_CONFIG_DEFAULT() enables the Wi-Fi NVS (CONFIG_ESP_WIFI_NVS_ENABLED, default y): the driver
    # keeps its configuration there, so the simulator makes esp_wifi_init fail while NVS is not initialised
    trace = sim_run("""
#define R(x) ESP_LOGI("r", "%s", esp_err_to_name(x))
extern "C" void app_main(void) {
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    R(esp_wifi_init(&cfg));
    ESP_ERROR_CHECK(nvs_flash_init());
    R(esp_wifi_init(&cfg));
    cfg.nvs_enable = 0;
    R(esp_wifi_init(&cfg));  // already initialised: the NVS-less path is not reached
}
""", 100, lib, tmp_path)
    assert msgs(trace, "r") == ["ESP_ERR_NVS_NOT_INITIALIZED", "ESP_OK", "ESP_ERR_INVALID_STATE"]


def test_esp_wifi_init_without_wifi_nvs_needs_no_nvs(lib, tmp_path):
    trace = sim_run("""
extern "C" void app_main(void) {
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    cfg.nvs_enable = 0;
    ESP_LOGI("r", "%s", esp_err_to_name(esp_wifi_init(&cfg)));
}
""", 100, lib, tmp_path)
    assert msgs(trace, "r") == ["ESP_OK"]


def test_wifi_and_event_errors_out_of_order(lib, tmp_path):
    trace = sim_run("""
#define R(x) ESP_LOGI("r", "%s", esp_err_to_name(x))
static void h(void *, esp_event_base_t, int32_t, void *) {}
extern "C" void app_main(void) {
    R(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &h, NULL));  // no default loop
    R(esp_event_post(WIFI_EVENT, 1, NULL, 0, 0));
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    R(esp_event_loop_create_default());
    R(esp_wifi_start());       // no esp_wifi_init
    R(esp_wifi_connect());
    R(esp_wifi_set_mode(WIFI_MODE_STA));
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(nvs_flash_init());
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    R(esp_wifi_connect());     // not started
    wifi_config_t wc = {};
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));
    R(esp_wifi_set_config(WIFI_IF_STA, &wc));  // STA interface not enabled
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_start());
    R(esp_wifi_connect());     // empty SSID
    R(esp_event_loop_delete_default());
    R(esp_event_loop_delete_default());
}
""", 100, lib, tmp_path)
    assert msgs(trace, "r") == [
        "ESP_ERR_INVALID_STATE", "ESP_ERR_INVALID_STATE", "ESP_ERR_INVALID_STATE", "ESP_ERR_WIFI_NOT_INIT",
        "ESP_ERR_WIFI_NOT_INIT", "ESP_ERR_WIFI_NOT_INIT", "ESP_ERR_WIFI_NOT_STARTED", "ESP_ERR_WIFI_MODE",
        "ESP_ERR_WIFI_SSID", "ESP_OK", "ESP_ERR_INVALID_STATE"]


def test_default_wifi_sta_needs_the_event_loop(lib, tmp_path):
    prog = compile_src(lib, SYS + 'extern "C" void app_main(void) { esp_netif_init(); esp_netif_create_default_wifi_sta(); }\n', tmp_path)
    trace = run(prog, 100)
    assert trace[-1]["ev"] == "end" and trace[-1]["reason"] == "abort"


MQTT_APP = """
static esp_mqtt_client_handle_t client;
static void on_mqtt(void *arg, esp_event_base_t base, int32_t id, void *data) {
    esp_mqtt_event_handle_t ev = (esp_mqtt_event_handle_t)data;
    switch ((esp_mqtt_event_id_t)id) {
    case MQTT_EVENT_CONNECTED:
        ESP_LOGI("m", "connected");
        esp_mqtt_client_subscribe(client, "home/devices/d1/command", 1);
        esp_mqtt_client_publish(client, "home/devices/d1/status", "online", 0, 1, 1);
        break;
    case MQTT_EVENT_DISCONNECTED: ESP_LOGI("m", "disconnected"); break;
    case MQTT_EVENT_ERROR: ESP_LOGI("m", "error type=%d", (int)ev->error_handle->error_type); break;
    case MQTT_EVENT_DATA:
        ESP_LOGI("m", "data %.*s=%.*s", ev->topic_len, ev->topic, ev->data_len, ev->data);
        gpio_set_level(GPIO_NUM_2, 1);
        break;
    default: break;
    }
}
static void mqtt_up(void) {
    esp_mqtt_client_config_t cfg = {};
    cfg.broker.address.uri = "mqtt://broker.local";
    cfg.credentials.client_id = "d1";
    client = esp_mqtt_client_init(&cfg);
    ESP_ERROR_CHECK(esp_mqtt_client_register_event(client, MQTT_EVENT_ANY, on_mqtt, NULL));
    ESP_ERROR_CHECK(esp_mqtt_client_start(client));
}
static void telemetry_loop(void) {
    for (int i = 0;; ++i) {
        vTaskDelay(pdMS_TO_TICKS(5000));
        char p[16]; snprintf(p, sizeof p, "{\\"n\\":%d}", i);
        int id = esp_mqtt_client_publish(client, "home/devices/d1/telemetry", p, 0, 0, 0);
        ESP_LOGI("m", "pub %d", id);
    }
}
"""
MQTT_MAIN = 'extern "C" void app_main(void) { mqtt_up(); telemetry_loop(); }\n'


def test_mqtt_publish_traced_with_flags(lib, tmp_path):
    trace = sim_run(MQTT_APP + MQTT_MAIN, 12000, lib, tmp_path)
    pubs = [e for e in trace if e["ev"] == "mqtt_publish"]
    assert pubs[0]["topic"] == "home/devices/d1/status" and pubs[0]["payload"] == "online"
    assert pubs[0]["retain"] is True and pubs[0]["qos"] == 1
    assert pubs[1]["topic"] == "home/devices/d1/telemetry" and pubs[1]["payload"] == '{"n":0}'
    assert pubs[1]["retain"] is False and pubs[1]["qos"] == 0 and pubs[1]["t_ms"] == 5000
    subs = [e for e in trace if e["ev"] == "mqtt_subscribe"]
    assert [(e["topic"], e["qos"]) for e in subs] == [("home/devices/d1/command", 1)]
    assert msgs(trace, "m")[:2] == ["connected", "pub 0"]  # qos 0 publish returns msg_id 0


def test_mqtt_incoming_is_delivered_only_when_subscribed(lib, tmp_path):
    sc = ('{"mqtt": {"incoming": [{"t_ms": 100, "topic": "home/devices/d1/command", "payload": "early"},'
          '{"t_ms": 2000, "topic": "home/devices/d1/command", "payload": "{\\"on\\":true}"},'
          '{"t_ms": 2500, "topic": "home/devices/other/command", "payload": "x"}]}}')
    trace = sim_run(MQTT_APP + MQTT_MAIN, 4000, lib, tmp_path, sc)
    assert [m for m in msgs(trace, "m") if m.startswith("data")] == ['data home/devices/d1/command={"on":true}']
    assert [e["task"] for e in trace if e["ev"] == "gpio_set"] == ["mqtt_task"]


def test_mqtt_reconnect_after_broker_outage(lib, tmp_path):
    trace = sim_run(MQTT_APP + MQTT_MAIN, 60000, lib, tmp_path, '{"mqtt": {"broker_down": [{"from_ms": 3000, "to_ms": 25000}]}}')
    m = [(e["t_ms"], e["event"]) for e in trace if e["ev"] == "mqtt"]
    m = [(t, n) for t, n in m if n in ("before_connect", "connected", "disconnected", "error")]
    names = [n for _, n in m]
    assert names[:3] == ["before_connect", "connected", "disconnected"]
    assert 3000 <= m[2][0] < 3100
    # reconnect_timeout_ms defaults to 10 s: the attempts at 13 s and 23 s fail, the one at 33 s works
    errors = [t for t, n in m if n == "error"]
    assert len(errors) == 2 and 13000 <= errors[0] < 13500 and 23000 <= errors[1] < 23500
    back = [t for t, n in m if n == "connected"][-1]
    assert 33000 <= back < 33500
    assert msgs(trace, "m").count("connected") == 2
    # a clean session forgets subscriptions: the handler subscribed again, and publishes resumed
    assert len([e for e in trace if e["ev"] == "mqtt_subscribe"]) == 2
    assert any(e["topic"].endswith("telemetry") and e["t_ms"] > back for e in trace if e["ev"] == "mqtt_publish")
    assert not any(e["topic"].endswith("telemetry") and 3000 <= e["t_ms"] < back for e in trace if e["ev"] == "mqtt_publish")
    assert "pub -1" in msgs(trace, "m")  # qos 0 publish while disconnected fails


def test_mqtt_waits_for_wifi_when_wifi_is_used(lib, tmp_path):
    main = 'extern "C" void app_main(void) { wifi_up(); mqtt_up(); telemetry_loop(); }\n'
    trace = sim_run(WIFI_APP + MQTT_APP + main, 30000, lib, tmp_path, '{"wifi": {"up_from_ms": 4000}}')
    ev = [(e["t_ms"], e["event"]) for e in trace if e["ev"] == "mqtt"]
    up = next(e["t_ms"] for e in trace if e["ev"] == "wifi" and e["event"] == "got_ip")
    assert up >= 4000
    assert [t for t, n in ev if n == "connected"][0] > up
    assert "error" in [n for _, n in ev]  # the first attempts found no network


def test_mqtt_api_errors(lib, tmp_path):
    trace = sim_run("""
#define R(x) ESP_LOGI("r", "%s", esp_err_to_name(x))
extern "C" void app_main(void) {
    esp_mqtt_client_config_t cfg = {};
    esp_mqtt_client_handle_t c = esp_mqtt_client_init(&cfg);
    R(esp_mqtt_client_start(c));                 // no broker address
    R(esp_mqtt_client_stop(c));                  // never started
    cfg.broker.address.uri = "mqtt://x";
    c = esp_mqtt_client_init(&cfg);
    ESP_LOGI("r", "%d", esp_mqtt_client_publish(c, "t", "x", 0, 0, 0));   // not connected, qos 0
    ESP_LOGI("r", "%d", esp_mqtt_client_publish(c, "t", "x", 0, 3, 0));   // bad qos
    R(esp_mqtt_client_start(c));
    R(esp_mqtt_client_start(c));                 // twice
    R(esp_mqtt_client_stop(c));
    R(esp_mqtt_client_destroy(c));
    R(esp_mqtt_client_start(NULL));
    ESP_LOGI("r", "%d", esp_mqtt_client_init(NULL) == NULL);
}
""", 100, lib, tmp_path)
    assert msgs(trace, "r") == ["ESP_ERR_INVALID_ARG", "ESP_FAIL", "-1", "-1", "ESP_OK", "ESP_FAIL", "ESP_OK", "ESP_OK",
                                "ESP_ERR_INVALID_ARG", "1"]


WDT_APP = """
extern "C" void app_main(void) {
    esp_task_wdt_config_t cfg = {};
    cfg.timeout_ms = 1000; cfg.idle_core_mask = 0; cfg.trigger_panic = %s;
    ESP_LOGI("r", "init=%%s", esp_err_to_name(esp_task_wdt_init(&cfg)));   // already initialised at boot
    ESP_ERROR_CHECK(esp_task_wdt_reconfigure(&cfg));
    ESP_LOGI("r", "reason=%%d", (int)esp_reset_reason());
    ESP_ERROR_CHECK(esp_task_wdt_add(NULL));
    for (int i = 0; i < 3; ++i) { vTaskDelay(pdMS_TO_TICKS(400)); ESP_ERROR_CHECK(esp_task_wdt_reset()); }
    vTaskDelay(pdMS_TO_TICKS(5000));              // stops feeding
    ESP_LOGI("r", "alive");
}
"""


def test_wdt_fires_when_task_not_fed(lib, tmp_path):
    trace = sim_run(WDT_APP % "true", 8000, lib, tmp_path)
    fired = [e for e in trace if e["ev"] == "wdt_reset"]
    # the program restarts and starves the watchdog again: one expiry and one reboot per boot, 2.2 s apart
    assert [e["t_ms"] for e in fired] == [2200, 4400, 6600]
    assert fired[0]["tasks"] == "main" and fired[0]["panic"] is True
    assert [(e["t_ms"], e["reason"]) for e in trace if e["ev"] == "reboot"] == [(t, "task_wdt") for t in (2200, 4400, 6600)]
    assert msgs(trace, "r")[:4] == ["init=ESP_ERR_INVALID_STATE", "reason=1", "init=ESP_ERR_INVALID_STATE", "reason=6"]
    assert "alive" not in msgs(trace, "r")
    assert any(e["tag"] == "task_wdt" and "Task watchdog got triggered" in e["msg"] for e in logs(trace))


def test_wdt_without_panic_only_warns_and_repeats(lib, tmp_path):
    trace = sim_run(WDT_APP % "false", 8000, lib, tmp_path)
    fired = [e for e in trace if e["ev"] == "wdt_reset"]
    assert [e["t_ms"] for e in fired][:2] == [2200, 3200] and not fired[0]["panic"]
    assert not [e for e in trace if e["ev"] == "reboot"]
    assert "alive" in msgs(trace, "r")


def test_wdt_fed_task_never_fires_and_api_errors(lib, tmp_path):
    trace = sim_run("""
#define R(x) ESP_LOGI("r", "%s", esp_err_to_name(x))
extern "C" void app_main(void) {
    R(esp_task_wdt_reset());                    // not subscribed
    R(esp_task_wdt_status(NULL));
    R(esp_task_wdt_delete(NULL));
    ESP_ERROR_CHECK(esp_task_wdt_add(NULL));
    R(esp_task_wdt_add(NULL));                  // twice
    R(esp_task_wdt_status(NULL));
    esp_task_wdt_config_t cfg = {};
    cfg.timeout_ms = 1000;
    R(esp_task_wdt_deinit());                   // a task is still subscribed
    for (int i = 0; i < 20; ++i) { vTaskDelay(pdMS_TO_TICKS(900)); esp_task_wdt_reset(); }
    ESP_ERROR_CHECK(esp_task_wdt_delete(NULL));
    ESP_ERROR_CHECK(esp_task_wdt_deinit());
    R(esp_task_wdt_reset());
    R(esp_task_wdt_status(NULL));
    R(esp_task_wdt_reconfigure(&cfg));
    R(esp_task_wdt_init(&cfg));
    vTaskDelay(pdMS_TO_TICKS(30000));
}
""", 60000, lib, tmp_path)
    assert not [e for e in trace if e["ev"] in ("wdt_reset", "reboot")]
    assert msgs(trace, "r") == [
        "ESP_ERR_NOT_FOUND", "ESP_ERR_NOT_FOUND", "ESP_ERR_NOT_FOUND", "ESP_ERR_INVALID_ARG", "ESP_OK",
        "ESP_ERR_INVALID_STATE", "ESP_ERR_INVALID_STATE", "ESP_ERR_INVALID_STATE", "ESP_ERR_INVALID_STATE", "ESP_OK"]


def test_wdt_names_every_unfed_task(lib, tmp_path):
    trace = sim_run("""
static void lazy(void *) { esp_task_wdt_add(NULL); vTaskDelay(pdMS_TO_TICKS(100000)); }
extern "C" void app_main(void) {
    esp_task_wdt_config_t cfg = {}; cfg.timeout_ms = 1000; cfg.trigger_panic = false;
    ESP_ERROR_CHECK(esp_task_wdt_reconfigure(&cfg));
    xTaskCreate(lazy, "lazy", 2048, NULL, 5, NULL);
    ESP_ERROR_CHECK(esp_task_wdt_add(NULL));
    for (;;) { vTaskDelay(pdMS_TO_TICKS(300)); esp_task_wdt_reset(); }
}
""", 1500, lib, tmp_path)
    fired = [e for e in trace if e["ev"] == "wdt_reset"]
    assert len(fired) == 1 and fired[0]["tasks"] == "lazy"  # main fed, lazy never did


@pytest.mark.parametrize("scenario", [
    '{"wifi": 3}', '{"wifi": {"up_from_ms": -1}}', '{"wifi": {"fail_attempts": -2}}', '{"wifi": {"fail_attempts": 1.5}}',
    '{"wifi": {"down": [{"from_ms": 5, "to_ms": 1}]}}', '{"wifi": {"down": 1}}',
    '{"mqtt": []}', '{"mqtt": {"broker_down": [{"from_ms": 1}]}}', '{"mqtt": {"incoming": [{"t_ms": 1, "payload": "x"}]}}',
    '{"mqtt": {"incoming": [{"t_ms": 1, "topic": "", "payload": "x"}]}}',
    '{"mqtt": {"incoming": [{"t_ms": 1, "topic": "a", "payload": 3}]}}', '{"mqtt": {"incoming": {}}}',
    '{"reboots_at_ms": 5}', '{"reboots_at_ms": [-1]}', '{"reboots_at_ms": ["a"]}', '{"reboots_at_ms": [2251799813685248]}',
])
def test_malformed_sys_scenario_fails_cleanly(lib, tmp_path, scenario):
    prog = compile_src(lib, SYS + 'extern "C" void app_main(void) {}\n', tmp_path)
    path = tmp_path / "bad.json"
    path.write_text(scenario)
    r = subprocess.run([str(prog), "--scenario", str(path)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 2 and r.stdout == "" and "scénario" in r.stderr


def test_restart_loop_is_bounded_by_the_deadline(lib, tmp_path):
    trace = sim_run('extern "C" void app_main(void) { vTaskDelay(pdMS_TO_TICKS(100)); esp_restart(); }\n', 1000, lib, tmp_path)
    assert trace[-1]["ev"] == "end" and trace[-1]["reason"] == "deadline"
    assert len([e for e in trace if e["ev"] == "reboot"]) == 10


def test_plant_level_survives_reboot(lib, tmp_path):
    # 1 %/s for 4 s with the relay on, a power cycle at 5 s (the relay drops), no loss: the level is kept
    sc = tank(level0=0, loss=0).replace('{"plant"', '{"reboots_at_ms": [5000], "plant"')
    prog = compile_src(lib, ADC + """
extern "C" void app_main(void) {
    adc_oneshot_unit_handle_t adc;
    adc_oneshot_unit_init_cfg_t ucfg = {};
    ucfg.unit_id = ADC_UNIT_1;
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&ucfg, &adc));
    adc_oneshot_chan_cfg_t ccfg = {};
    ccfg.atten = ADC_ATTEN_DB_12;
    ccfg.bitwidth = ADC_BITWIDTH_DEFAULT;
    ESP_ERROR_CHECK(adc_oneshot_config_channel(adc, ADC_CHANNEL_0, &ccfg));
    gpio_config_t io = {}; io.pin_bit_mask = 1ULL << 5; io.mode = GPIO_MODE_OUTPUT;
    ESP_ERROR_CHECK(gpio_config(&io));
    gpio_set_level(GPIO_NUM_5, 1);
    vTaskDelay(pdMS_TO_TICKS(4000));
    int raw = -1;
    ESP_ERROR_CHECK(adc_oneshot_read(adc, ADC_CHANNEL_0, &raw));
    ESP_LOGI("adc", "0 %d", raw);
    vTaskDelay(pdMS_TO_TICKS(20000));
}
""", tmp_path)
    trace = run(prog, 12000, sc)
    # boot 1: relay on 0-5 s (read 160 at 4 s). The cycle at 5 s drops the relay and the level (5 %) is kept.
    # Boot 2 drives the relay again for 4 s: 9 % -> 360
    assert adc_reads(trace) == [160, 360]


def test_new_fields_are_known_to_the_trace_reader():
    import importlib.util
    spec = importlib.util.spec_from_file_location("esp_trace", SIM.parent / "trace.py")
    esp_trace = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(esp_trace)
    good = esp_trace.Trace('{"t_ms": 1, "ev": "mqtt_publish", "topic": "a", "payload": "b", "retain": true, "qos": 1}\n'
                           '{"t_ms": 2, "ev": "mqtt_publish", "topic": "a", "payload": "b", "retain": 1, "qos": 1}\n')
    assert len(good.events("mqtt_publish")) == 1 and good.bad_lines == 1


# ---------------------------------------- Task 15, fix round 1

def test_nvs_canonical_init_pattern_compiles_and_runs(lib, tmp_path):
    # The sim never returns NO_FREE_PAGES / NEW_VERSION_FOUND, but the code every ESP-IDF example uses must build.
    trace = sim_run("""
extern "C" void app_main(void) {
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);
    ESP_LOGI("r", "%s 0x%x", esp_err_to_name(ESP_ERR_NVS_NEW_VERSION_FOUND), (unsigned)ESP_ERR_NVS_NEW_VERSION_FOUND);
}
""", 100, lib, tmp_path)
    assert msgs(trace, "r") == ["ESP_ERR_NVS_NEW_VERSION_FOUND 0x1110"]


def test_mqtt_data_event_buffers_are_not_nul_terminated(lib, tmp_path):
    app = MQTT_APP.replace('ESP_LOGI("m", "data %.*s=%.*s", ev->topic_len, ev->topic, ev->data_len, ev->data);', """
        ESP_LOGI("m", "strcmp=%d strncmp=%d contiguous=%d", strcmp(ev->topic, "home/devices/d1/command") == 0,
                 strncmp(ev->topic, "home/devices/d1/command", ev->topic_len) == 0, ev->data == ev->topic + ev->topic_len);
        ESP_LOGI("m", "after_topic=%d after_data=%d", ev->topic[ev->topic_len] != 0, ev->data[ev->data_len] != 0);
        ESP_LOGI("m", "data %.*s=%.*s", ev->topic_len, ev->topic, ev->data_len, ev->data);""")
    assert app != MQTT_APP
    sc = '{"mqtt": {"incoming": [{"t_ms": 2000, "topic": "home/devices/d1/command", "payload": "{\\"on\\":true}"}]}}'
    trace = sim_run(app + MQTT_MAIN, 3000, lib, tmp_path, sc)
    assert [m for m in msgs(trace, "m") if m.startswith(("strcmp", "after", "data"))] == [
        "strcmp=0 strncmp=1 contiguous=1", "after_topic=1 after_data=1", 'data home/devices/d1/command={"on":true}']


def test_mqtt_wildcard_hash_matches_parent_level(lib, tmp_path):
    app = MQTT_APP.replace('esp_mqtt_client_subscribe(client, "home/devices/d1/command", 1);', """
        esp_mqtt_client_subscribe(client, "a/#", 0);
        esp_mqtt_client_subscribe(client, "b/+", 0);""")
    sc = ('{"mqtt": {"incoming": [{"t_ms": 1000, "topic": "a", "payload": "1"}, {"t_ms": 1100, "topic": "a/x/y", "payload": "2"},'
          '{"t_ms": 1200, "topic": "b", "payload": "3"}, {"t_ms": 1300, "topic": "ab", "payload": "4"}]}}')
    trace = sim_run(app + MQTT_MAIN, 3000, lib, tmp_path, sc)
    assert [m for m in msgs(trace, "m") if m.startswith("data")] == ["data a=1", "data a/x/y=2"]


def test_mqtt_last_will_fully_traced(lib, tmp_path):
    trace = sim_run("""
extern "C" void app_main(void) {
    esp_mqtt_client_config_t cfg = {};
    cfg.broker.address.uri = "mqtt://broker.local";
    cfg.credentials.client_id = "d1";
    cfg.session.last_will.topic = "home/devices/d1/status";
    cfg.session.last_will.msg = "offline";
    cfg.session.last_will.qos = 1;
    cfg.session.last_will.retain = true;
    esp_mqtt_client_handle_t c = esp_mqtt_client_init(&cfg);
    ESP_ERROR_CHECK(esp_mqtt_client_start(c));
    for (;;) vTaskDelay(pdMS_TO_TICKS(1000));
}
""", 1000, lib, tmp_path)
    conn = next(e for e in trace if e["ev"] == "mqtt" and e["event"] == "connected")
    assert (conn["lwt_topic"], conn["lwt_msg"], conn["lwt_retain"], conn["lwt_qos"]) == ("home/devices/d1/status", "offline", True, 1)


def test_wifi_event_lost_when_queue_full_is_traced_as_not_delivered(lib, tmp_path):
    # the handler blocks on the first event, so only 32 later events fit in the loop's queue
    app = WIFI_APP.replace("static void on_wifi(void *arg, esp_event_base_t base, int32_t id, void *data) {",
                           "static void on_wifi(void *arg, esp_event_base_t base, int32_t id, void *data) {\n"
                           "    if (id == WIFI_EVENT_STA_START) { ESP_LOGI(\"w\", \"start\"); vTaskDelay(portMAX_DELAY); }")
    main = 'extern "C" void app_main(void) { wifi_up(); for (int i = 0; i < 40; i++) { esp_wifi_connect(); vTaskDelay(pdMS_TO_TICKS(1100)); } }\n'
    trace = sim_run(app + main, 60000, lib, tmp_path, '{"wifi": {"fail_attempts": 1000}}')
    w = [e for e in trace if e["ev"] == "wifi" and e["event"] == "sta_disconnected"]
    assert len(w) == 40
    assert [e.get("delivered", True) for e in w] == [True] * 32 + [False] * 8


@pytest.mark.parametrize("scenario", [
    '{"wifi": {"fail_attempt": 3}}', '{"wifi": {"up_from_ms": 1, "downs": []}}',
    '{"mqtt": {"broker_downs": []}}', '{"mqtt": {"incoming": [], "retained": []}}',
    '{"mqtt": {"incoming": [{"t_ms": 1, "topic": "a", "payload": "x", "qos_level": 1}]}}',
])
def test_unknown_wifi_mqtt_keys_are_refused(lib, tmp_path, scenario):
    prog = compile_src(lib, SYS + 'extern "C" void app_main(void) {}\n', tmp_path)
    path = tmp_path / "bad.json"
    path.write_text(scenario)
    r = subprocess.run([str(prog), "--scenario", str(path)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 2 and r.stdout == "" and "scénario" in r.stderr


def test_nvs_get_blob_without_length_reports_invalid_length(lib, tmp_path):
    trace = sim_run("""
#define R(x) ESP_LOGI("r", "%s", esp_err_to_name(x))
extern "C" void app_main(void) {
    ESP_ERROR_CHECK(nvs_flash_init());
    nvs_handle_t h;
    ESP_ERROR_CHECK(nvs_open("cfg", NVS_READWRITE, &h));
    char buf[8];
    R(nvs_get_str(h, "s", buf, NULL));                   // key missing: NOT_FOUND comes first
    ESP_ERROR_CHECK(nvs_set_str(h, "s", "x"));
    ESP_ERROR_CHECK(nvs_set_blob(h, "b", "xy", 2));
    R(nvs_get_str(h, "s", buf, NULL));
    R(nvs_get_blob(h, "b", buf, NULL));
    R(nvs_get_blob(h, "b", NULL, NULL));
}
""", 100, lib, tmp_path)
    assert msgs(trace, "r") == ["ESP_ERR_NVS_NOT_FOUND"] + ["ESP_ERR_NVS_INVALID_LENGTH"] * 3


def test_learner_fds_do_not_leak_across_restarts(lib, tmp_path):
    src = """
#include <fcntl.h>
#include <unistd.h>
extern "C" void app_main(void) {
    int n = 0;
    for (int fd = 3; fd < 64; ++fd) if (fcntl(fd, F_GETFD) != -1) ++n;
    ESP_LOGI("fd", "open=%d", n);
    open("/dev/null", O_RDONLY);  // leaked on purpose, no O_CLOEXEC
    vTaskDelay(pdMS_TO_TICKS(100));
    esp_restart();
}
"""
    trace = sim_run(src, 450, lib, tmp_path)
    counts = msgs(trace, "fd")
    assert len(counts) >= 4 and len(set(counts)) == 1, counts


def test_restart_at_boot_ends_with_boot_loop(lib, tmp_path):
    trace = sim_run('extern "C" void app_main(void) { esp_restart(); }\n', 1000, lib, tmp_path)
    assert trace[-1] == {"t_ms": 0, "ev": "end", "reason": "boot_loop"}
    assert len([e for e in trace if e["ev"] == "reboot"]) == 51


def test_restart_every_tick_ends_with_boot_loop(lib, tmp_path):
    trace = sim_run('extern "C" void app_main(void) { vTaskDelay(1); esp_restart(); }\n', 60000, lib, tmp_path)
    assert trace[-1]["ev"] == "end" and trace[-1]["reason"] == "boot_loop"
    assert len([e for e in trace if e["ev"] == "reboot"]) == 301  # the 301st is traced, then refused
