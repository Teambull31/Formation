"""The ESP-IDF check driver: source reading, static scan, sandboxed compile+run, trace reading.

Each test runs `python3 -I -B content/esp/esp_check.py <tp_id>` in a temp cwd holding main.cpp,
against the self-test TP checks/_selftest.py (LED on GPIO 2 lit at 500 ms). Tests that compile
need bwrap: they skip when it is unusable, and fail instead with ESP_SANDBOX_REQUIRED=1.
"""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ESP = Path(__file__).resolve().parents[2] / "content" / "esp"
DRIVER = ESP / "esp_check.py"
REQUIRED = os.environ.get("ESP_SANDBOX_REQUIRED") == "1"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def bwrap_ok(tmp_path_factory):
    sandbox = _load("esp_sandbox_probe", ESP / "sandbox.py")
    try:
        sandbox.run_sandboxed(["/usr/bin/true"], cwd=tmp_path_factory.mktemp("probe"), wall_s=30, cpu_s=5, mem_mb=64)
    except sandbox.SandboxUnavailable as e:
        msg = f"bwrap indisponible sur cette machine : {e}"
        if REQUIRED:
            pytest.fail(msg)
        pytest.skip(msg)


HEAD = '#include "freertos/FreeRTOS.h"\n#include "freertos/task.h"\n#include "driver/gpio.h"\n#include "esp_log.h"\n'

REFERENCE = HEAD + r'''
// Ni sleep_for, ni printf, ni std::thread ici : un commentaire ne déclenche pas l'analyse.
/* usleep(10); system("x"); */
extern "C" void app_main(void) {
    gpio_set_direction(GPIO_NUM_2, GPIO_MODE_OUTPUT);
    gpio_set_level(GPIO_NUM_2, 0);
    vTaskDelay(pdMS_TO_TICKS(400));
    gpio_set_level(GPIO_NUM_2, 1);
    ESP_LOGI("led", "allumée (pas de printf(\"%d\") ni de sleep(1) ici)");
}
'''

LED_OFF = REFERENCE.replace("gpio_set_level(GPIO_NUM_2, 1);", "gpio_set_level(GPIO_NUM_2, 0);")


def app(body: str, head: str = HEAD) -> str:
    return head + 'extern "C" void app_main(void) {\n' + body + "\n}\n"


def run(cwd: Path, src: str | bytes | None = None, tp: str = "_selftest") -> tuple[int, str]:
    if isinstance(src, str):
        (cwd / "main.cpp").write_text(src, encoding="utf-8")
    elif isinstance(src, bytes):
        (cwd / "main.cpp").write_bytes(src)
    r = subprocess.run([sys.executable, "-I", "-B", str(DRIVER), tp], cwd=cwd, capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout + r.stderr


def failed(code: int, out: str) -> bool:
    return code == 1 and out.startswith("ECHEC")


# ---- runs in the sandbox ----

def test_reference_passes(tmp_path, bwrap_ok):
    code, out = run(tmp_path, REFERENCE)
    assert code == 0 and out.startswith("OK"), out


def test_wrong_behaviour_fails_verify(tmp_path, bwrap_ok):
    code, out = run(tmp_path, LED_OFF)
    assert failed(code, out) and "GPIO 2" in out, out


def test_missing_app_main_message(tmp_path):
    code, out = run(tmp_path, HEAD + "void setup(void) {}\n")
    assert failed(code, out) and "app_main" in out, out


def test_app_main_without_extern_c_message(tmp_path):
    code, out = run(tmp_path, HEAD + "void app_main(void) {}\n")
    assert failed(code, out) and 'extern "C"' in out, out


def test_app_main_outside_extern_c_found_by_linker(tmp_path, bwrap_ok):
    code, out = run(tmp_path, HEAD + 'extern "C" int helper(void);\nvoid app_main(void) {}\n')
    assert failed(code, out) and 'extern "C" void app_main(void)' in out, out


@pytest.mark.parametrize("extra", ["int main() { app_main(); return 0; }\n", "int (main)() { return 0; }\n"])
def test_defines_main_message(tmp_path, bwrap_ok, extra):
    code, out = run(tmp_path, REFERENCE + extra)
    assert failed(code, out) and "ne définissez pas main()" in out, out


def test_literals_do_not_trigger_the_scan(tmp_path, bwrap_ok):
    src = REFERENCE.replace('ESP_LOGI("led"', 'ESP_LOGI("led", "%s", R"x(un ")" printf(1) sleep(2))x");\n    ESP_LOGI("led"')
    code, out = run(tmp_path, src.replace("vTaskDelay(pdMS_TO_TICKS(400));", "vTaskDelay(pdMS_TO_TICKS(1'0'0 * 4));"))
    assert code == 0 and out.startswith("OK"), out


def test_compile_error_summarised(tmp_path, bwrap_ok):
    code, out = run(tmp_path, app("int x = ;\nundeclared_thing();\nint y = ;\nint z = ;\nint w = ;\nint v = ;"))
    assert failed(code, out) and "main.cpp" in out, out
    assert len([l for l in out.splitlines() if "error" in l]) <= 5, out
    assert "/tmp/" not in out and "formation-espsim" not in out, out


def test_segfault_message(tmp_path, bwrap_ok):
    code, out = run(tmp_path, app("volatile int *p = nullptr;\n*p = 1;"))
    assert failed(code, out) and "SIGSEGV" in out, out


def test_busy_loop_message(tmp_path, bwrap_ok):
    code, out = run(tmp_path, app("volatile int n = 0;\nfor (;;) n = n + 1;"))
    assert failed(code, out) and "vTaskDelay" in out, out


def test_esp_error_check_message(tmp_path, bwrap_ok):
    code, out = run(tmp_path, app("ESP_ERROR_CHECK(gpio_set_level(GPIO_NUM_34, 1));"))
    assert failed(code, out) and "ESP_ERROR_CHECK" in out and "ESP_ERR_INVALID_ARG" in out, out


def test_too_many_tasks_message(tmp_path, bwrap_ok):
    src = HEAD + '''
static void blink(void *) { for (;;) vTaskDelay(pdMS_TO_TICKS(100)); }
extern "C" void app_main(void) {
    for (int i = 0; i < 10; i++) xTaskCreate(blink, "t", 2048, nullptr, 1, nullptr);
}
'''
    code, out = run(tmp_path, src)
    assert failed(code, out) and "trop de tâches" in out, out


def test_output_flood_truncated(tmp_path, bwrap_ok):
    code, out = run(tmp_path, app('for (;;) ESP_LOGI("flood", "encore une ligne de journal pour remplir la sortie");'))
    assert failed(code, out) and "tronqu" in out, out
    assert len(out) <= 4000, len(out)


def test_concurrent_checks_do_not_collide(tmp_path, bwrap_ok):
    dirs = []
    for name, src in (("a", REFERENCE), ("b", LED_OFF), ("c", REFERENCE)):
        d = tmp_path / name
        d.mkdir()
        (d / "main.cpp").write_text(src, encoding="utf-8")
        dirs.append(d)
    procs = [subprocess.Popen([sys.executable, "-I", "-B", str(DRIVER), "_selftest"], cwd=d, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True) for d in dirs]
    results = [(p.wait(timeout=60), p.stdout.read()) for p in procs]
    assert [r[0] for r in results] == [0, 1, 0], results
    for d in dirs:
        assert sorted(p.name for p in d.iterdir()) == ["main.cpp"]


def test_sandbox_unavailable_fails_closed(tmp_path, monkeypatch, capsys):
    """Without bwrap, the driver fails with a message and never runs the program directly."""
    drv = _load("esp_check_under_test", DRIVER)
    monkeypatch.setattr(drv.sandbox, "BWRAP", str(tmp_path / "no-bwrap"))
    monkeypatch.setenv("PATH", "")
    (tmp_path / "main.cpp").write_text(REFERENCE, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert drv.main(["esp_check.py", "_selftest"]) == 1
    out = capsys.readouterr().out
    assert out.startswith("ECHEC") and "sandbox" in out and "OK" not in out, out


# ---- static scan (no compilation) ----

TIMING = [
    "std::this_thread::sleep_for(std::chrono::milliseconds(500));",
    "usleep(500000);",
    "sleep(1);",
    "struct timespec ts{0, 1}; nanosleep(&ts, nullptr);",
    "using namespace std; thread t([]{}); t.join();",
    "std::thread t([]{}); t.join();",
    "auto t0 = std::chrono::steady_clock::now(); (void)t0;",
    "using namespace std::chrono; auto t0 = system_clock::now(); (void)t0;",
    "long t0 = time(nullptr); (void)t0;",
    "struct timespec ts; clock_gettime(0, &ts);",
    "auto f = std::async([]{ return 1; }); (void)f;",
]


@pytest.mark.parametrize("body", TIMING, ids=range(len(TIMING)))
def test_sleep_for_refused_mentions_vtaskdelay(tmp_path, body):
    code, out = run(tmp_path, app(body, HEAD + "#include <chrono>\n#include <thread>\n#include <ctime>\n"))
    assert failed(code, out) and "vTaskDelay" in out, out


OUTPUT = [
    'printf("{\\"t_ms\\": 500, \\"ev\\": \\"gpio_set\\", \\"pin\\": 2, \\"level\\": 1}\\n");',
    'write(3, "x", 1);',
    'auto w = &::write; (void)w;',
    'std::cout << "x";',
    'puts("x");',
    'FILE *f = fopen("/tmp/x", "w"); (void)f;',
    'int fd = dup(1); (void)fd;',
    'const char *e = getenv("HOME"); (void)e;',
    "int x = 1'000; (void)x; printf(\"x\");",  # a digit separator is not a character literal
    'fputs_unlocked("x", stdout);',
    'int fd = open64("x", 0); (void)fd;',
    'std::basic_filebuf<char> fb; fb.open("x", std::ios::out);',
    'const char *p = "/pro" "c/self/fd/3"; (void)p;',
]


@pytest.mark.parametrize("body", OUTPUT, ids=range(len(OUTPUT)))
def test_direct_output_refused_mentions_esp_log(tmp_path, body):
    code, out = run(tmp_path, app(body, HEAD + "#include <cstdio>\n#include <unistd.h>\n#include <iostream>\n"))
    assert failed(code, out) and "ESP_LOGI" in out, out


OTHER = [
    app('system("ls");'),
    app("if (fork() == 0) {}"),
    app('execl("/bin/sh", "sh", nullptr);'),
    app('asm("nop");'),
    app('__asm__("nop");'),
    "#define CAT(a, b) a##b\n" + app('CAT(pri, ntf)("x");'),
    "static int w(int, const void *, unsigned long) __attribute__((weakref(\"write\")));\n" + app(""),
    app('const char *p = "/proc/self/fd/3"; (void)p;'),
    "#embed \"main.cpp\"\n" + app(""),
    app('pr\\u0069ntf("x");'),
    "extern int _ZN3sim8trace_fdE;\n" + app(""),
    "namespace s = sim;\n" + app(""),
    app('__builtin_printf("x");'),
    app('_Pragma("message(\\"x\\")")'),
    "[[gnu::weakref(\"write\")]] static int w(int, const void *, unsigned long);\n" + app(""),
    app('auto f = &::system; (void)f;'),
    "#define F \"/etc/passwd\"\n#include F\n" + app(""),
]


@pytest.mark.parametrize("src", OTHER, ids=range(len(OTHER)))
def test_dangerous_constructs_refused(tmp_path, src):
    code, out = run(tmp_path, src)
    assert failed(code, out) and "interdit" in out, out


@pytest.mark.parametrize("inc", ['#include "/etc/passwd"', "#include <../../etc/passwd>", '%:include "/etc/passwd"',
                                 '#  include "sub/../../x.h"'])
def test_absolute_include_refused(tmp_path, inc):
    code, out = run(tmp_path, inc + "\n" + REFERENCE)
    assert failed(code, out) and "#include" in out, out


# ---- reading main.cpp ----

def test_non_utf8_source_refused(tmp_path):
    code, out = run(tmp_path, REFERENCE.encode() + b"// \xff\xfe\n")
    assert failed(code, out) and "UTF-8" in out, out


def test_symlink_source_refused(tmp_path):
    (tmp_path / "real.cpp").write_text(REFERENCE, encoding="utf-8")
    (tmp_path / "main.cpp").symlink_to(tmp_path / "real.cpp")
    code, out = run(tmp_path)
    assert failed(code, out) and "lien symbolique" in out, out


def test_oversized_source_refused(tmp_path):
    code, out = run(tmp_path, REFERENCE + "//" + "x" * 200_000 + "\n")
    assert failed(code, out) and "trop gros" in out, out


def test_fifo_source_refused(tmp_path):
    os.mkfifo(tmp_path / "main.cpp")
    code, out = run(tmp_path)
    assert failed(code, out) and "fichier ordinaire" in out, out


def test_missing_source_refused(tmp_path):
    code, out = run(tmp_path)
    assert failed(code, out) and "main.cpp" in out, out


@pytest.mark.parametrize("tp", ["../sandbox", "_selftest/..", "a b", "", "inconnu"])
def test_bad_tp_id_is_usage_error(tmp_path, tp):
    code, out = run(tmp_path, REFERENCE, tp=tp)
    assert code == 2 and "Usage" in out, out
