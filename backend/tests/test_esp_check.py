"""The ESP-IDF check driver: source reading, static scan, sandboxed compile+run, trace reading.

Each test runs `python3 -I -B content/esp/esp_check.py <tp_id>` in a temp cwd holding main.cpp,
against the self-test TP checks/_selftest.py (LED on GPIO 2 lit at 500 ms). Tests that compile
need bwrap: they skip when it is unusable, and fail instead with ESP_SANDBOX_REQUIRED=1.
"""
import importlib.util
import json
import os
import subprocess
import sys
import types
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
    assert failed(code, out) and "tronqu" in out and "journalise trop" in out and "1000000 octets" in out, out
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
    "auto f = write; (void)f;",
    "auto f = &std::printf; (void)f;",
    "struct S { void f() { write(3, \"x\", 1); } }; S().f();",
    "struct S { long x = write(3, \"x\", 1); }; S s; (void)s;",
    "struct S { void write(int); void f() { ::write(3, \"x\", 1); } }; S().f();",
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
    "using ::write;\n" + app(""),
    "namespace s = std;\n" + app("s::thread t; (void)t;"),
    "namespace n { using namespace sim; }\n" + app(""),
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


def test_hard_link_source_refused(tmp_path):
    (tmp_path / "real.cpp").write_text(REFERENCE, encoding="utf-8")
    os.link(tmp_path / "real.cpp", tmp_path / "main.cpp")
    code, out = run(tmp_path)
    assert failed(code, out) and "liens physiques" in out, out


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


# ---- fix round 1: internal failures, malformed traces, hints, ordinary identifiers ----

END_OK = '{"t_ms": 1000, "ev": "end", "reason": "deadline"}\n'


@pytest.fixture
def drv(tmp_path, monkeypatch):
    """The driver loaded in-process, cwd = a TP folder holding the reference main.cpp."""
    d = _load("esp_check_in_process", DRIVER)
    (tmp_path / "main.cpp").write_text(REFERENCE, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return d


def fake_run(drv, monkeypatch, out: str, rc: int = 0, sig: str | None = None):
    """Replace the sandboxed compile+run with a canned run-phase result (no bwrap needed)."""
    result = drv.sandbox.Result(rc=rc, out=out, err="", timed_out=False, signal=sig, phase="run")
    monkeypatch.setattr(drv.sandbox, "compile_and_run", lambda *a, **k: result)


def check_module(drv, monkeypatch, tmp_path, name: str, text: str) -> None:
    checks = tmp_path / "checks"
    checks.mkdir(exist_ok=True)
    (checks / f"{name}.py").write_text(text, encoding="utf-8")
    monkeypatch.setattr(drv, "CHECKS", checks)


def verdict(drv, capsys, tp: str = "_selftest") -> tuple[int, str]:
    code = drv.main(["esp_check.py", tp])
    return code, capsys.readouterr().out


def internal(code: int, out: str) -> bool:
    return code == 1 and out.startswith("ECHEC : erreur interne du contrôle (") and "OK" not in out \
        and "Traceback" not in out


def test_verify_raising_keyerror_is_internal_error(drv, monkeypatch, tmp_path, capsys):
    check_module(drv, monkeypatch, tmp_path, "boom", "SCENARIO = {}\nMAX_MS = 1000\n"
                 "def verify(trace, source):\n    raise KeyError('level')\n")
    fake_run(drv, monkeypatch, END_OK)
    code, out = verdict(drv, capsys, "boom")
    assert internal(code, out) and "KeyError" in out, out


def test_check_module_syntax_error_is_internal_error(drv, monkeypatch, tmp_path, capsys):
    check_module(drv, monkeypatch, tmp_path, "broken", "SCENARIO = {\n")
    code, out = verdict(drv, capsys, "broken")
    assert internal(code, out) and "SyntaxError" in out, out


def test_sim_build_failure_is_internal_error(drv, monkeypatch, capsys):
    def broken():
        raise RuntimeError("échec de compilation du simulateur :\ncore.cpp:1: error: boom")
    monkeypatch.setattr(drv.build, "build_sim", broken)
    code, out = verdict(drv, capsys)
    assert internal(code, out) and "échec de compilation du simulateur" in out and "core.cpp" not in out, out


def test_sandbox_oserror_is_internal_error(drv, monkeypatch, capsys):
    def popen_fails(*a, **k):
        raise OSError(24, "Too many open files")
    monkeypatch.setattr(drv.sandbox, "compile_and_run", popen_fails)
    code, out = verdict(drv, capsys)
    assert internal(code, out) and "OSError" in out, out


def test_forged_gpio_set_without_level_is_ignored(drv, monkeypatch, capsys):
    fake_run(drv, monkeypatch, '{"t_ms": 0, "ev": "gpio_set", "pin": 2}\n' + END_OK)
    code, out = verdict(drv, capsys)
    assert failed(code, out) and "GPIO 2" in out and "interne" not in out, out


def test_trace_drops_malformed_events():
    t = _load("esp_trace_unit", ESP / "trace.py").Trace(
        '{"t_ms": 0, "ev": "gpio_set", "pin": 2}\n{"t_ms": 1, "ev": "gpio_set", "pin": 2, "level": true}\n'
        '{"t_ms": 2, "ev": "gpio_set", "pin": "2", "level": 1}\n{"t_ms": 3, "ev": "log", "level": "I"}\n'
        '{"t_ms": 4, "ev": "end"}\n{"t_ms": 5, "ev": "gpio_set", "pin": 2, "level": 1}\n')
    assert t.gpio_levels(2) == [(5, 1)] and t.logs() == [] and t.last_end() == {} and t.bad_lines == 5


def test_many_malformed_lines_fail_clearly(drv, monkeypatch, capsys):
    fake_run(drv, monkeypatch, '{"t_ms": 0, "ev": "gpio_set", "pin": 2}\n' * 4 + END_OK)
    code, out = verdict(drv, capsys)
    assert failed(code, out) and "illisible" in out, out


# ---- several scenarios per TP: SCENARIOS = {name: (scenario, max_ms)} and verify(traces, source) ----

MULTI = ("SCENARIOS = {'a': ({'k': 1}, 1000), 'b': ({'k': 2}, 2000)}\n"
         "def verify(traces, source):\n"
         "    assert list(traces) == ['a', 'b'] and all(hasattr(t, 'events') for t in traces.values())\n"
         "    n = [len(t.events('end')) for t in traces.values()]\n"
         "    from esp_trace import need\n"
         "    need(n == [1, 1], 'un journal de fin par scénario (relire : la section X)')\n")


def multi_fake(drv, monkeypatch, outs: list[tuple[str, int]], spend: float = 0.0, err: str = ""):
    """Canned run-phase results, one per call; returns the list of (scenario, --max-ms, wall_s) seen.

    The driver clock is fake: each call "takes" `spend` seconds, so the shared wall budget can be observed."""
    seen, it, clock = [], iter(outs), [1000.0]
    monkeypatch.setattr(drv, "time", types.SimpleNamespace(monotonic=lambda: clock[0]))

    def fake(argv, args, **kw):
        seen.append((json.loads((kw["cwd"] / "scenario.json").read_text()), args[args.index("--max-ms") + 1], kw["wall_s"]))
        clock[0] += spend
        out, rc = next(it)
        return drv.sandbox.Result(rc=rc, out=out, err=err, timed_out=False, signal=None, phase="run")

    monkeypatch.setattr(drv.sandbox, "compile_and_run", fake)
    return seen


def test_several_scenarios_run_in_order_and_verify_gets_all_traces(drv, monkeypatch, tmp_path, capsys):
    check_module(drv, monkeypatch, tmp_path, "multi", MULTI)
    seen = multi_fake(drv, monkeypatch, [(END_OK, 0), (END_OK, 0)], spend=30.0)
    code, out = verdict(drv, capsys, "multi")
    assert code == 0 and out.startswith("OK"), out
    assert [(s, m) for s, m, _ in seen] == [({"k": 1}, "1000"), ({"k": 2}, "2000")]
    # run 1 gets the whole budget and "takes" 30 s: run 2 only gets what is left, never a renewed WALL_S
    assert seen[0][2] == drv.WALL_S and seen[1][2] == pytest.approx(drv.WALL_S - 30.0), seen


def test_exhausted_budget_stops_with_a_timeout_message(drv, monkeypatch, tmp_path, capsys):
    check_module(drv, monkeypatch, tmp_path, "multi", MULTI)
    seen = multi_fake(drv, monkeypatch, [(END_OK, 0), (END_OK, 0)], spend=drv.WALL_S + 5.0)
    code, out = verdict(drv, capsys, "multi")
    assert failed(code, out) and out.startswith("ECHEC : scénario « b » : ") and "temps d'exécution autorisé" in out, out
    assert len(seen) == 1, seen  # the second run is never started


def test_budget_at_the_one_second_floor_is_not_enough_but_a_bit_more_is(drv, monkeypatch, tmp_path, capsys):
    check_module(drv, monkeypatch, tmp_path, "multi", MULTI)
    seen = multi_fake(drv, monkeypatch, [(END_OK, 0), (END_OK, 0)], spend=drv.WALL_S - 1.0)
    code, out = verdict(drv, capsys, "multi")
    assert failed(code, out) and len(seen) == 1, (out, seen)
    seen = multi_fake(drv, monkeypatch, [(END_OK, 0), (END_OK, 0)], spend=drv.WALL_S - 1.5)
    code, out = verdict(drv, capsys, "multi")
    assert code == 0 and seen[1][2] == pytest.approx(1.5), (out, seen)


def test_multi_verify_failure_shows_no_stderr_of_another_run(drv, monkeypatch, tmp_path, capsys):
    check_module(drv, monkeypatch, tmp_path, "multi", MULTI.replace("[1, 1]", "[9, 9]"))
    multi_fake(drv, monkeypatch, [(END_OK, 0), (END_OK, 0)], err="sortie du dernier scénario")
    code, out = verdict(drv, capsys, "multi")
    assert failed(code, out) and "un journal de fin par scénario" in out and "sortie du dernier" not in out, out


def test_failed_run_names_its_scenario(drv, monkeypatch, tmp_path, capsys):
    check_module(drv, monkeypatch, tmp_path, "multi", MULTI)
    multi_fake(drv, monkeypatch, [(END_OK, 0), ('{"t_ms": 5, "ev": "end", "reason": "crash", "signal": 11}\n', 1)])
    code, out = verdict(drv, capsys, "multi")
    assert failed(code, out) and out.startswith("ECHEC : scénario « b » : ") and "SIGSEGV" in out, out


def test_single_scenario_modules_are_unchanged(drv, monkeypatch, tmp_path, capsys):
    check_module(drv, monkeypatch, tmp_path, "one", "SCENARIO = {}\nMAX_MS = 1000\n"
                 "def verify(trace, source):\n    assert hasattr(trace, 'events')\n")
    fake_run(drv, monkeypatch, END_OK)
    code, out = verdict(drv, capsys, "one")
    assert code == 0 and out.startswith("OK"), out


def test_crash_without_signal_message(drv, monkeypatch, capsys):
    fake_run(drv, monkeypatch, '{"t_ms": 5, "ev": "end", "reason": "crash"}\n', rc=1)
    code, out = verdict(drv, capsys)
    assert failed(code, out) and "brutalement" in out and "None" not in out, out


def test_driver_messages_carry_a_hint(tmp_path):
    code, out = run(tmp_path, HEAD + "void setup(void) {}\n")
    assert failed(code, out) and "(relire : " in out, out


def test_verify_messages_keep_their_own_hint(tmp_path, bwrap_ok):
    code, out = run(tmp_path, LED_OFF)
    assert failed(code, out) and "(relire : la section GPIO)" in out and "Pièges" not in out, out


ORDINARY = HEAD + r'''
struct Writer {
    int written = 0;
    void write(int v);
    int read() const { return written; }
};
void Writer::write(int v) { written += v; }
enum class Mode { read, write, open, close };

extern "C" void app_main(void) {
    int thread_count = 1, async_flag = 0, sim = 2, tee = 3, gnu = 4, thread = 5;
    bool open = false;
    Writer w;
    w.write(1);
    Writer *pw = &w;
    pw->write(thread_count + async_flag + sim + tee + gnu + thread);
    if (open || w.read() < 0 || Mode::write == Mode::read) return;
    gpio_set_direction(GPIO_NUM_2, GPIO_MODE_OUTPUT);
    vTaskDelay(pdMS_TO_TICKS(400));
    gpio_set_level(GPIO_NUM_2, 1);
    ESP_LOGI("led", "total %d", w.read());
}
'''


def test_ordinary_identifiers_do_not_trigger_the_scan(tmp_path, bwrap_ok):
    code, out = run(tmp_path, ORDINARY)
    assert code == 0 and out.startswith("OK"), out


# ---- value-tier names in value positions, #define, and learner-declared names ----

VALUE_USES = [
    "#define W write\n" + app("W(3, \"x\", 1);", HEAD + "#include <unistd.h>\n"),
    "#define P printf\n" + app('P("x");', HEAD + "#include <cstdio>\n"),
    "#define S system\n" + app('S("ls");'),
    "#define D(x) dup(x)\n" + app("D(1);", HEAD + "#include <unistd.h>\n"),
    "using W = long (*)(int, const void *, unsigned long);\n" + app("W f = (W)write; (void)f;", HEAD + "#include <unistd.h>\n"),
    "using W = long (*)(int, const void *, unsigned long);\n" + app("W f = reinterpret_cast<W>(write); (void)f;"),
    app("auto fs = {write, dup}; (void)fs;"),
    app("void *fs[] = {(void *)write}; (void)fs;"),
    app("bool c = true; auto f = c ? write : dup; (void)f;"),
    app("auto f = +write; (void)f;"),
    app("auto f = *write; (void)f;"),
    app("auto f = !write; (void)f;"),
    app("auto f = (long)printf; (void)f;"),
    app("auto f = true && write; (void)f;"),
    app("auto f = true and write; (void)f;"),
    app("auto f = false or system; (void)f;"),
    app("auto f = not execl; (void)f;"),
    "auto get() { return write; }\n" + app(""),
    "struct S { auto f() { return *write; } };\n" + app(""),
    "struct S { void *write(int); };\n" + app(""),  # `*` is not a type name: not a member declaration
    "struct S { void write(int); };\n" + app("auto f = (long)write; (void)f;"),
    "extern char write[];\n" + app("auto f = (long)write; (void)f;"),
]


@pytest.mark.parametrize("src", VALUE_USES, ids=range(len(VALUE_USES)))
def test_value_tier_names_refused_in_value_positions(tmp_path, src):
    code, out = run(tmp_path, src)
    assert failed(code, out) and "interdit" in out, out


def test_define_of_value_name_refused_even_without_use(tmp_path):
    code, out = run(tmp_path, "#define W write\n" + app(""))
    assert failed(code, out) and "interdit ligne 1 : write" in out, out


LEARNER = HEAD + r'''
class Porte {
    bool open = false;
    int write = 0;
public:
    Porte() : open(false), write(1) {}
    void close() { write += 1; }
    int ecrit() const { return write; }
};
struct Journal {
    bool read;
    Journal() : read{false} {}
    void tee() { read = true; }
    void go() { tee(); }
};

extern "C" void app_main(void) {
    int sim = 1, tee = 2, gnu = 3, write = 4, dup = 5;
    int total = sim + tee + gnu + write - dup;
    Porte p;
    Journal j;
    j.go();
    gpio_set_direction(GPIO_NUM_2, GPIO_MODE_OUTPUT);
    vTaskDelay(pdMS_TO_TICKS(400));
    gpio_set_level(GPIO_NUM_2, 1);
    ESP_LOGI("led", "total %d %d", total, p.ecrit());
}
'''


def test_learner_members_and_constructor_initialisers_pass(tmp_path, bwrap_ok):
    code, out = run(tmp_path, LEARNER)
    assert code == 0 and out.startswith("OK"), out


def test_sibling_member_call_passes(tmp_path, bwrap_ok):
    src = HEAD + ("struct Porte { bool ouverte = false; void open() { ouverte = true; }\n"
                  "  void run() { open(); } };\n"
                  'extern "C" void app_main(void) { Porte p; p.run(); gpio_set_direction(GPIO_NUM_2, GPIO_MODE_OUTPUT);'
                  " vTaskDelay(pdMS_TO_TICKS(400)); gpio_set_level(GPIO_NUM_2, 1); }\n")
    code, out = run(tmp_path, src)
    assert code == 0 and out.startswith("OK"), out


def test_ternary_after_paren_is_not_a_constructor_initialiser(tmp_path):
    src = "struct S { int write; };\n" + app("bool c = true; auto f = c ? (1) : write(3, \"x\", 1); (void)f;")
    code, out = run(tmp_path, src, )
    assert failed(code, out) and "interdit" in out, out


def test_compile_error_has_only_the_relire_hint(tmp_path, bwrap_ok):
    code, out = run(tmp_path, app("int x = ;"))
    assert failed(code, out) and out.count("relire") == 1 and "relisez" not in out, out


def test_internal_error_cause_has_no_absolute_path(drv, monkeypatch, capsys):
    def boom(*a, **k):
        raise OSError("cannot open /home/secret/dir/sim/libespsim.a")
    monkeypatch.setattr(drv.build, "build_sim", boom)
    code, out = verdict(drv, capsys)
    assert internal(code, out) and "/home" not in out and "libespsim.a" in out, out


# ---- TP es1 (LED et journaux) : solution livrée + variantes fautives ----

ES1 = Path(__file__).resolve().parents[2] / "content" / "modules" / "esp1" / "lessons" / "es1.tp"


def _es1_reference() -> str:
    text = (ES1 / "solution.sh").read_text(encoding="utf-8")
    return text.split("<<'EOF'\n", 1)[1].rsplit("\nEOF", 1)[0] + "\n"


def _mutant(old: str, new: str) -> str:
    ref = _es1_reference()
    assert old in ref, old
    return ref.replace(old, new)


def _es1_run(tmp_path, src: str) -> tuple[int, str]:
    return run(tmp_path, src, tp="es1-tp")


def test_es1_tp_reference_passes(tmp_path, bwrap_ok):
    code, out = _es1_run(tmp_path, _es1_reference())
    assert code == 0 and out.startswith("OK"), out


def test_es1_tp_seed_refused(tmp_path, bwrap_ok):
    code, out = _es1_run(tmp_path, (ES1 / "seed" / "main.cpp").read_text(encoding="utf-8"))
    assert failed(code, out) and "GPIO 2 jamais configurée en sortie" in out and "relire" in out, out


# nom -> (fragment remplacé, remplacement, fragment de message attendu)
ES1_MUTANTS = {
    "no_direction": ("    ESP_ERROR_CHECK(gpio_config(&io));\n", "", "GPIO 2 jamais configurée en sortie"),
    "period_1000": ("vTaskDelay(pdMS_TO_TICKS(500))", "vTaskDelay(pdMS_TO_TICKS(1000))", "période observée de 1000 ms"),
    "loge_instead_of_logi": ("ESP_LOGI(", "ESP_LOGE(", "ESP_LOGE"),
    "busy_loop": ("        vTaskDelay(pdMS_TO_TICKS(500));\n", "", "journalise trop"),
    "busy_empty_loop": ("for (;;) {", "for (;;) {} for (;;) {", "ne rend jamais la main"),
    "wrong_pin": ("GPIO_NUM_2", "GPIO_NUM_4", "GPIO 2 jamais configurée en sortie"),
    "level_never_changes": ("level = !level;", "level = 1;", "n'a jamais changé après le premier"),
    "no_log": ('        ESP_LOGI(TAG, "LED %s", level ? "allumée" : "éteinte");\n', "", "aucun journal"),
    "starts_low": ("int level = 0;", "int level = 1;", "premier niveau écrit sur GPIO 2 est 0"),
    "wrong_tag": ('TAG = "blink"', 'TAG = "led"', "au lieu de « blink »"),
    "level_on_wrong_pin_only": ("gpio_set_level(GPIO_NUM_2", "gpio_set_level(GPIO_NUM_4", "aucune écriture sur GPIO 2"),
}


@pytest.mark.parametrize("old,new,expected", ES1_MUTANTS.values(), ids=ES1_MUTANTS.keys())
def test_es1_tp_mutant(tmp_path, bwrap_ok, old, new, expected):
    code, out = _es1_run(tmp_path, _mutant(old, new))
    assert failed(code, out) and expected in out and "relire" in out, out


def test_es1_check_sections_exist_in_lesson():
    """Chaque « relire : <section> » du contrôle renvoie à un titre réel de la leçon."""
    import re
    lesson = (ES1.parent / "es1.md").read_text(encoding="utf-8")
    titles = set(re.findall(r"^## (.+)$", lesson, re.M))
    cited = set(re.findall(r"relire : « ([^»]+) »", (ESP / "checks" / "es1-tp.py").read_text(encoding="utf-8")))
    assert cited and cited <= titles, cited - titles


# ---- TP es2 (bouton et anti-rebond) : solution livrée + variantes fautives ----

ES2 = Path(__file__).resolve().parents[2] / "content" / "modules" / "esp1" / "lessons" / "es2.tp"


def _es2_reference() -> str:
    text = (ES2 / "solution.sh").read_text(encoding="utf-8")
    return text.split("<<'EOF'\n", 1)[1].rsplit("\nEOF", 1)[0] + "\n"


def _es2_mutant(old: str, new: str) -> str:
    ref = _es2_reference()
    assert old in ref, old
    return ref.replace(old, new)


def _es2_run(tmp_path, src: str) -> tuple[int, str]:
    return run(tmp_path, src, tp="es2-tp")


def test_es2_tp_reference_passes(tmp_path, bwrap_ok):
    code, out = _es2_run(tmp_path, _es2_reference())
    assert code == 0 and out.startswith("OK"), out


def test_es2_tp_seed_refused(tmp_path, bwrap_ok):
    code, out = _es2_run(tmp_path, (ES2 / "seed" / "main.cpp").read_text(encoding="utf-8"))
    assert failed(code, out) and "GPIO 2 jamais configurée en sortie" in out and "relire" in out, out


ES2_MUTANTS = {
    "no_debounce": ("STABLE_MS = 30", "STABLE_MS = 0", "plus d'un changement pour l'appui n°1"),
    "poll_500ms": ("POLL_MS = 10", "POLL_MS = 500", "l'appui n°1 (de 1130 à 1250 ms) n'a provoqué aucun changement"),
    "reacts_to_release": ("if (stable == 0) {", "if (stable == 0 || stable == 1) {", "plus d'un changement pour l'appui n°1"),
    "no_pullup": ("    btn.pull_up_en = GPIO_PULLUP_ENABLE;\n", "", "sans pull-up"),
    "debounce_2s_pause": ("gpio_set_level(GPIO_NUM_2, led_level);", "gpio_set_level(GPIO_NUM_2, led_level); vTaskDelay(pdMS_TO_TICKS(2000));",
                          "l'appui n°2 (de 1530 à 1650 ms) n'a provoqué aucun changement"),
    "stable_2000ms": ("STABLE_MS = 30", "STABLE_MS = 2000", "l'appui n°1 (de 1130 à 1250 ms) n'a provoqué aucun changement"),
    "led_never_configured": ("    ESP_ERROR_CHECK(gpio_config(&led));\n", "", "GPIO 2 jamais configurée en sortie"),
    "button_wrong_pin": ("GPIO_NUM_4", "GPIO_NUM_5", "GPIO 4 jamais configurée en entrée"),
    "button_as_output": ("btn.mode = GPIO_MODE_INPUT;", "btn.mode = GPIO_MODE_OUTPUT;", "GPIO 4 jamais configurée en entrée"),
}


@pytest.mark.parametrize("old,new,expected", ES2_MUTANTS.values(), ids=ES2_MUTANTS.keys())
def test_es2_tp_mutant(tmp_path, bwrap_ok, old, new, expected):
    code, out = _es2_run(tmp_path, _es2_mutant(old, new))
    assert failed(code, out) and expected in out and "relire" in out, out


def test_es2_check_sections_exist_in_lesson():
    """Chaque « relire : <section> » du contrôle renvoie à un titre réel de la leçon."""
    import re
    lesson = (ES2.parent / "es2.md").read_text(encoding="utf-8")
    titles = set(re.findall(r"^## (.+)$", lesson, re.M))
    cited = set(re.findall(r"relire : « ([^»]+) »", (ESP / "checks" / "es2-tp.py").read_text(encoding="utf-8")))
    assert cited and cited <= titles, cited - titles


# ---- TP es3 (tâches FreeRTOS et files) : solution livrée + variantes fautives ----

ES3 = Path(__file__).resolve().parents[2] / "content" / "modules" / "esp1" / "lessons" / "es3.tp"


def _es3_reference() -> str:
    text = (ES3 / "solution.sh").read_text(encoding="utf-8")
    return text.split("<<'EOF'\n", 1)[1].rsplit("\nEOF", 1)[0] + "\n"


def _es3_mutant(*edits: tuple[str, str]) -> str:
    src = _es3_reference()
    for old, new in edits:
        assert old in src, old
        src = src.replace(old, new)
    return src


def _es3_run(tmp_path, src: str) -> tuple[int, str]:
    return run(tmp_path, src, tp="es3-tp")


def test_es3_tp_reference_passes(tmp_path, bwrap_ok):
    code, out = _es3_run(tmp_path, _es3_reference())
    assert code == 0 and out.startswith("OK"), out


def test_es3_tp_seed_refused(tmp_path, bwrap_ok):
    code, out = _es3_run(tmp_path, (ES3 / "seed" / "main.cpp").read_text(encoding="utf-8"))
    assert failed(code, out) and "0 tâche(s) créée(s) par xTaskCreate" in out and "relire" in out, out


ES3_LED_TASK = ('    if (xTaskCreate(tache_led, "led", 4096, NULL, 5, NULL) != pdPASS) {\n'
                '        ESP_LOGE(TAG, "tâche led non créée");\n    }\n')
# nom -> (remplacements (ancien, nouveau), fragment de message attendu)
ES3_MUTANTS = {
    "single_task": ([(ES3_LED_TASK, "")], "1 tâche(s) créée(s) par xTaskCreate (« bouton »)"),
    "global_without_queue": ([
        ("static QueueHandle_t appuis;", "static QueueHandle_t appuis;\nstatic volatile int appui_en_attente = 0;"),
        ("if (xQueueSend(appuis, &numero, 0) != pdTRUE) {", "appui_en_attente = 1;\n                if (false) {"),
        ("if (xQueueReceive(appuis, &numero, portMAX_DELAY) == pdTRUE) {",
         "vTaskDelay(pdMS_TO_TICKS(POLL_MS));\n        if (appui_en_attente) {\n            appui_en_attente = 0;"),
    ], "aucun événement n'est passé par la file"),
    "receive_zero_wait": ([("portMAX_DELAY", "0")], "votre tâche « led » ne rend jamais la main"),
    "stack_256": ([('tache_bouton, "bouton", 4096', 'tache_bouton, "bouton", 256')],
                  "la tâche « bouton » est créée avec une pile de 256 octets"),
    "stack_in_words": ([('tache_led, "led", 4096', 'tache_led, "led", 1024')],
                       "la tâche « led » est créée avec une pile de 1024 octets"),
    "poll_zero": ([("POLL_MS = 10;", "POLL_MS = 0;")], "votre tâche « bouton » ne rend jamais la main"),
    "send_from_app_main": ([('if (xTaskCreate(tache_bouton, "bouton", 4096, NULL, 5, NULL) != pdPASS) {',
                             "tache_bouton(NULL);\n    if (false) {")],
                           "xQueueSend est appelé depuis app_main"),
    "no_debounce": ([("STABLE_MS = 30", "STABLE_MS = 0")], "changements de la LED pour l'appui n°1"),
    # Le bouton inverse lui-même la LED (comme au TP 2) et envoie aussi ; la tâche LED reçoit sans rien faire.
    "led_toggled_by_sender": ([
        ("    int numero = 0;      // numéro de l'appui, envoyé dans la file\n",
         "    int numero = 0;      // numéro de l'appui, envoyé dans la file\n    int led_level = 0;\n"),
        ("                numero++;\n",
         "                numero++;\n                led_level = !led_level;\n                gpio_set_level(GPIO_NUM_2, led_level);\n"),
        ("            led_level = !led_level;\n            gpio_set_level(GPIO_NUM_2, led_level);\n            ESP_LOGI",
         "            ESP_LOGI"),
    ], "la LED est changée par la tâche « bouton », qui envoie dans la file"),
}


@pytest.mark.parametrize("edits,expected", ES3_MUTANTS.values(), ids=ES3_MUTANTS.keys())
def test_es3_tp_mutant(tmp_path, bwrap_ok, edits, expected):
    code, out = _es3_run(tmp_path, _es3_mutant(*edits))
    assert failed(code, out) and expected in out and "relire" in out, out


def test_es3_check_sections_exist_in_lesson():
    """Chaque « relire : <section> » du contrôle renvoie à un titre réel de la leçon."""
    import re
    lesson = (ES3.parent / "es3.md").read_text(encoding="utf-8")
    titles = set(re.findall(r"^## (.+)$", lesson, re.M))
    cited = set(re.findall(r"relire : « ([^»]+) »", (ESP / "checks" / "es3-tp.py").read_text(encoding="utf-8")))
    assert cited and cited <= titles, cited - titles


# ---- TP es4 (lire un capteur analogique, ADC) : solution livrée + variantes fautives ----

ES4 = Path(__file__).resolve().parents[2] / "content" / "modules" / "esp2" / "lessons" / "es4.tp"


def _es4_reference() -> str:
    text = (ES4 / "solution.sh").read_text(encoding="utf-8")
    return text.split("<<'EOF'\n", 1)[1].rsplit("\nEOF", 1)[0] + "\n"


def _es4_mutant(*edits: tuple[str, str]) -> str:
    src = _es4_reference()
    for old, new in edits:
        assert old in src, old
        src = src.replace(old, new)
    return src


def _es4_run(tmp_path, src: str) -> tuple[int, str]:
    return run(tmp_path, src, tp="es4-tp")


def test_es4_tp_reference_passes(tmp_path, bwrap_ok):
    code, out = _es4_run(tmp_path, _es4_reference())
    assert code == 0 and out.startswith("OK"), out


def test_es4_tp_seed_refused(tmp_path, bwrap_ok):
    code, out = _es4_run(tmp_path, (ES4 / "seed" / "main.cpp").read_text(encoding="utf-8"))
    assert failed(code, out) and "aucune lecture réussie du canal 6" in out and "relire" in out, out


# nom -> (remplacements (ancien, nouveau), fragment de message attendu)
ES4_MUTANTS = {
    "no_calibration": ([("float pct = (mv - 500.0f) * 100.0f / 2500.0f;", "float pct = raw * 100.0f / 4095.0f;")],
                       "division par 4095"),
    "no_averaging": ([("somme += raw;", "somme = raw;"), ("return lues > 0 ? somme / lues : -1;", "return lues > 0 ? somme : -1;")],
                     "moyenne de 8 échantillons"),
    "single_read": ([("ECHANTILLONS = 8;", "ECHANTILLONS = 1;")], "seulement 1 lecture"),
    "channel_not_configured": ([("    ESP_ERROR_CHECK(adc_oneshot_config_channel(adc, CANAL, &chan_cfg));\n", "")],
                               "aucune lecture réussie du canal 6"),
    "scale_3v3": ([("* 100.0f / 2500.0f;", "* 100.0f / 2800.0f;")], "échelle de 3,3 V"),
    "no_log": ([('ESP_LOGI(TAG, "level=%d%%", pct);', "(void)pct;")], "aucun journal level=NN%"),
    "log_every_2s": ([("PERIODE_MS = 1000;", "PERIODE_MS = 2000;")], "journaux espacés de 2000 ms"),
    "wrong_channel": ([("ADC_CHANNEL_6", "ADC_CHANNEL_3")], "lectures sur le canal 3 au lieu du canal 6"),
    "bad_format": ([('"level=%d%%"', '"niveau %d%%"')], "aucun journal level=NN%"),
    "no_delay": ([("ATTENTE_MS = 10;", "ATTENTE_MS = 0;")], "aucune pause"),
    "delay_5ms": ([("ATTENTE_MS = 10;", "ATTENTE_MS = 5;")], "aucune pause"),  # pdMS_TO_TICKS(5) vaut 0 tick à 100 Hz
}

# Variantes légitimes qui doivent passer : plus de mesures, ou des mesures plus espacées.
ES4_VARIANTS = {
    "16_samples_10ms": [("ECHANTILLONS = 8;", "ECHANTILLONS = 16;")],
    "8_samples_20ms": [("ATTENTE_MS = 10;", "ATTENTE_MS = 20;")],
    "8_samples_30ms": [("ATTENTE_MS = 10;", "ATTENTE_MS = 30;")],
}


@pytest.mark.parametrize("edits", ES4_VARIANTS.values(), ids=ES4_VARIANTS.keys())
def test_es4_tp_legitimate_variant_passes(tmp_path, bwrap_ok, edits):
    code, out = _es4_run(tmp_path, _es4_mutant(*edits))
    assert code == 0 and out.startswith("OK"), out


@pytest.mark.parametrize("edits,expected", ES4_MUTANTS.values(), ids=ES4_MUTANTS.keys())
def test_es4_tp_mutant(tmp_path, bwrap_ok, edits, expected):
    code, out = _es4_run(tmp_path, _es4_mutant(*edits))
    assert failed(code, out) and expected in out and "relire" in out, out


def test_es4_check_sections_exist_in_lesson():
    """Chaque « relire : <section> » du contrôle renvoie à un titre réel de la leçon."""
    import re
    lesson = (ES4.parent / "es4.md").read_text(encoding="utf-8")
    titles = set(re.findall(r"^## (.+)$", lesson, re.M))
    cited = set(re.findall(r"relire : « ([^»]+) »", (ESP / "checks" / "es4-tp.py").read_text(encoding="utf-8")))
    assert cited and cited <= titles, cited - titles


# ---- TP es5 (relais et capteur I2C avec gestion d'erreur) : solution livrée + variantes fautives ----

ES5 = Path(__file__).resolve().parents[2] / "content" / "modules" / "esp2" / "lessons" / "es5.tp"


def _es5_reference() -> str:
    text = (ES5 / "solution.sh").read_text(encoding="utf-8")
    return text.split("<<'EOF'\n", 1)[1].rsplit("\nEOF", 1)[0] + "\n"


def _es5_mutant(*edits: tuple[str, str]) -> str:
    src = _es5_reference()
    for old, new in edits:
        assert old in src, old
        src = src.replace(old, new)
    return src


def _es5_run(tmp_path, src: str) -> tuple[int, str]:
    return run(tmp_path, src, tp="es5-tp")


def test_es5_tp_reference_passes(tmp_path, bwrap_ok):
    code, out = _es5_run(tmp_path, _es5_reference())
    assert code == 0 and out.startswith("OK"), out


def test_es5_tp_seed_refused(tmp_path, bwrap_ok):
    code, out = _es5_run(tmp_path, (ES5 / "seed" / "main.cpp").read_text(encoding="utf-8"))
    assert failed(code, out) and "aucun transfert I2C" in out and "relire" in out, out


# nom -> (remplacements (ancien, nouveau), fragment de message attendu)
ES5_MUTANTS = {
    "error_check_on_read": ([("esp_err_t err = lire_temperature(&dixiemes);", "esp_err_t err = lire_temperature(&dixiemes);\n        ESP_ERROR_CHECK(err);")],
                            "ESP_ERROR_CHECK a arrêté le programme"),
    "relay_off_on_error": ([("en_panne = true;", "en_panne = true;\n            gpio_set_level(RELAIS_GPIO, 0);")],
                           "pendant la panne du capteur"),
    "relay_on_on_error": ([("en_panne = true;", "en_panne = true;\n            gpio_set_level(RELAIS_GPIO, 1);")],
                          "pendant la panne du capteur"),
    "threshold_25": ([("SEUIL_DIXIEMES = 280;", "SEUIL_DIXIEMES = 250;")], "seuil trop bas"),
    "threshold_28_5": ([("SEUIL_DIXIEMES = 280;", "SEUIL_DIXIEMES = 285;")], "seuil trop haut"),
    "tie_greater_or_equal": ([("dixiemes > SEUIL_DIXIEMES", "dixiemes >= SEUIL_DIXIEMES")], "pile à 28,0"),
    "bytes_swapped": ([("(octets[0] << 8) | octets[1]", "(octets[1] << 8) | octets[0]")], "conversion fausse"),
    "no_offset": ([("brut - 400", "brut")], "conversion fausse"),
    "log_spam": ([("} else if (!en_panne) {", "} else {")], "journaux d'erreur pendant la même panne"),
    "no_error_log": ([('ESP_LOGE(TAG, "lecture du capteur échouée : %s", esp_err_to_name(err));',
                       'ESP_LOGI(TAG, "lecture échouée");')], "aucun journal d'erreur"),
    "flag_never_reset": ([("                en_panne = false;\n", "")], "aucun journal d'erreur"),
    "wrong_address": ([("ADRESSE_CAPTEUR = 0x44;", "ADRESSE_CAPTEUR = 0x45;")], "adresse 0x45"),
    "relay_inverted": ([("relais_allume ? 1 : 0", "relais_allume ? 0 : 1")], "niveau 1 = relais allumé"),
    "relay_not_configured": ([("    ESP_ERROR_CHECK(gpio_config(&relais_cfg));\n", "")], "pas configurée en sortie"),
    "period_10s": ([("PERIODE_MS = 5000;", "PERIODE_MS = 10000;")], "espacées de 10000 ms"),
}

# Variantes légitimes qui doivent passer.
ES5_VARIANTS = {
    "float_compare": [("dixiemes > SEUIL_DIXIEMES", "dixiemes / 10.0f > 28.0f")],
    "warning_level": [("ESP_LOGE(TAG, \"lecture", "ESP_LOGW(TAG, \"lecture")],
    "transmit_receive": [("i2c_master_receive(capteur, octets, sizeof octets, TIMEOUT_I2C_MS)",
                          "i2c_master_transmit_receive(capteur, octets, 1, octets, sizeof octets, TIMEOUT_I2C_MS)")],
}


@pytest.mark.parametrize("edits", ES5_VARIANTS.values(), ids=ES5_VARIANTS.keys())
def test_es5_tp_legitimate_variant_passes(tmp_path, bwrap_ok, edits):
    code, out = _es5_run(tmp_path, _es5_mutant(*edits))
    assert code == 0 and out.startswith("OK"), out


@pytest.mark.parametrize("edits,expected", ES5_MUTANTS.values(), ids=ES5_MUTANTS.keys())
def test_es5_tp_mutant(tmp_path, bwrap_ok, edits, expected):
    code, out = _es5_run(tmp_path, _es5_mutant(*edits))
    assert failed(code, out) and expected in out and "relire" in out, out


def test_es5_check_sections_exist_in_lesson():
    """Chaque « relire : <section> » du contrôle renvoie à un titre réel de la leçon."""
    import re
    lesson = (ES5.parent / "es5.md").read_text(encoding="utf-8")
    titles = set(re.findall(r"^## (.+)$", lesson, re.M))
    cited = set(re.findall(r"relire : « ([^»]+) »", (ESP / "checks" / "es5-tp.py").read_text(encoding="utf-8")))
    assert cited and cited <= titles, cited - titles


# ---- TP es6 (régulation du niveau d'une piscine) : solution livrée + variantes fautives ----

ES6 = Path(__file__).resolve().parents[2] / "content" / "modules" / "esp2" / "lessons" / "es6.tp"


def _es6_reference() -> str:
    text = (ES6 / "solution.sh").read_text(encoding="utf-8")
    return text.split("<<'EOF'\n", 1)[1].rsplit("\nEOF", 1)[0] + "\n"


def _es6_mutant(*edits: tuple[str, str]) -> str:
    src = _es6_reference()
    for old, new in edits:
        assert old in src, old
        src = src.replace(old, new)
    return src


def _es6_run(tmp_path, src: str) -> tuple[int, str]:
    return run(tmp_path, src, tp="es6-tp")


def test_es6_tp_reference_passes(tmp_path, bwrap_ok):
    code, out = _es6_run(tmp_path, _es6_reference())
    assert code == 0 and out.startswith("OK"), out


def test_es6_tp_seed_refused(tmp_path, bwrap_ok):
    code, out = _es6_run(tmp_path, (ES6 / "seed" / "main.cpp").read_text(encoding="utf-8"))
    assert failed(code, out) and "scénario a" in out and "pas configurée en sortie" in out and "relire" in out, out


LOCKED = "pompe(false);  // verrouillé : rien d'autre à faire jusqu'au redémarrage"
SAFE_START = "pompe(false);  // état sûr : pompe éteinte avant la première lecture"

# nom -> (remplacements (ancien, nouveau), fragments de message attendus)
ES6_MUTANTS = {
    # seuils
    "no_hysteresis_stop_at_60": ([("niveau > SEUIL_HAUT) {  // FILLING", "niveau >= SEUIL_BAS) {  // FILLING")],
                                 ["scénario a", "s'éteint à", "seulement", "Un seul seuil fait battre"]),
    "no_hysteresis_single_80": ([("if (niveau < SEUIL_BAS) {", "if (niveau < SEUIL_HAUT) {")],
                                ["scénario a", "s'allume à", "dans la zone entre 60 % et 80 %"]),
    "inverted_thresholds": ([("SEUIL_BAS = 60;", "SEUIL_BAS = 80;"), ("SEUIL_HAUT = 80;", "SEUIL_HAUT = 60;")],
                            ["scénario a", "s'allume à", "dans la zone entre 60 % et 80 %"]),
    "stop_at_100_overflow": ([("niveau > SEUIL_HAUT) {  // FILLING", "niveau >= 100) {  // FILLING")],
                             ["scénario a", "restée allumée", "déborde"]),
    "stop_at_85": ([("niveau > SEUIL_HAUT) {  // FILLING", "niveau > 85) {  // FILLING")],
                   ["scénario a", "restée allumée", "déborde"]),
    "start_at_65": ([("if (niveau < SEUIL_BAS) {", "if (niveau < 65) {")],
                    ["scénario a", "s'allume à", "dans la zone entre 60 % et 80 %"]),
    # délai maximal et capteur figé
    "no_max_time_no_frozen": ([("t - debut_ms >= DELAI_MAX_MS", "false"), ("t - brut_change_ms >= FIGE_MS", "false")],
                              ["scénario b", "au plus 10 min 15 s", "délai maximal"]),  # la pompe ne s'arrête qu'au retour du capteur (16 min)
    "no_max_time_only_frozen": ([("t - debut_ms >= DELAI_MAX_MS", "false")],
                                ["scénario d", "la pompe tourne encore à 15 min 00 s", "ne remplit presque rien"]),
    "no_frozen_detection": ([("t - brut_change_ms >= FIGE_MS", "false")], ["scénario c", "aucune alarme", "identique pendant 10 min"]),
    "max_time_5min": ([("DELAI_MAX_MS = 10 * 60 * 1000", "DELAI_MAX_MS = 5 * 60 * 1000")],
                      ["scénario b", "seulement 5 min 00 s après son démarrage"]),
    "max_time_15min": ([("DELAI_MAX_MS = 10 * 60 * 1000", "DELAI_MAX_MS = 15 * 60 * 1000")],
                       ["scénario d", "au plus 10 min 15 s", "esp_timer_get_time"]),
    "frozen_window_3min": ([("FIGE_MS = 10 * 60 * 1000", "FIGE_MS = 3 * 60 * 1000")],
                           ["scénario b", "seulement 3 min 00 s après son démarrage"]),
    "run_timer_never_restarted": (
        [("niveau >= niveau_debut + HAUSSE_MIN", "false"),
         ("                    debut_ms = t;\n                    niveau_debut = niveau;\n                    etat = Etat::FILLING;",
          "                    if (debut_ms == 0) {\n                        debut_ms = t;\n                    }\n"
          "                    niveau_debut = niveau;\n                    etat = Etat::FILLING;")],
        ["scénario a", "fausse alarme", "repartir de zéro"]),
    # alarme et état sûr
    "alarm_without_cut": ([("    pompe(false);\n    etat = Etat::ALARM;", "    etat = Etat::ALARM;"), (LOCKED, "(void)0;  // verrouillé")],
                          ["scénario b", "la pompe tourne encore à 30 min 00 s"]),
    "cut_without_alarm_log": ([('ESP_LOGE(TAG, "ALARME', 'ESP_LOGI(TAG, "ALARME')], ["scénario b", "aucune alarme", "ESP_LOGE de tag « pool »"]),
    "alarm_wrong_tag": ([('ESP_LOGE(TAG, "ALARME', 'ESP_LOGE("piscine", "ALARME')], ["scénario b", "aucune alarme"]),
    "alarm_logged_every_cycle": ([(LOCKED, LOCKED + '\n            ESP_LOGE(TAG, "toujours en alarme");')],
                                 ["scénario b", "lignes d'alarme", "au lieu d'une"]),
    "alarm_not_latched": ([(LOCKED, LOCKED + "\n            if (brut >= 0 && brut != dernier_brut) {\n                etat = Etat::IDLE;\n"
                           "                dernier_brut = brut;\n                brut_change_ms = t;\n            }")],
                          ["scénario b", "rallumée", "verrouillée"]),
    "relay_on_at_startup": ([(SAFE_START, "pompe(true);")], ["scénario a", "premier gpio_set_level", "met la pompe en marche (niveau 1) à 0 ms"]),
    "no_safe_state_at_startup": ([("    " + SAFE_START + "\n", "")], ["scénario a", "premier gpio_set_level", "met la pompe en marche (niveau 1)"]),
    "relay_active_low": ([("allumee ? 1 : 0", "allumee ? 0 : 1")], ["scénario a", "premier gpio_set_level", "met la pompe en marche"]),
    "relay_not_configured": ([("    ESP_ERROR_CHECK(gpio_config(&pompe_cfg));\n", "")], ["scénario a", "pas configurée en sortie"]),
    # lecture
    "wrong_channel": ([("ADC_CHANNEL_6;", "ADC_CHANNEL_3;")], ["scénario a", "canal 3"]),
    "sampling_every_20s": ([("PERIODE_MS = 5000;", "PERIODE_MS = 20000;")], ["scénario a", "sans lire le capteur", "toutes les 10 s"]),
}

def _MANY_READS(extra: int) -> list[tuple[str, str]]:
    """Lectures supplémentaires à chaque tour (moyenne de plusieurs mesures) : la trace grossit très vite."""
    return [("int brut = lire_brut();", f"for (int i = 0; i < {extra}; i++) lire_brut();\n        int brut = lire_brut();")]


# Variantes légitimes qui doivent passer.
ES6_VARIANTS = {
    "period_10s": [("PERIODE_MS = 5000;", "PERIODE_MS = 10000;")],
    "period_1s": [("PERIODE_MS = 5000;", "PERIODE_MS = 1000;")],
    "period_1s_8_reads": [("PERIODE_MS = 5000;", "PERIODE_MS = 1000;"), *_MANY_READS(7)],
    "period_1s_16_reads": [("PERIODE_MS = 5000;", "PERIODE_MS = 1000;"), *_MANY_READS(15)],
    "period_2s_8_reads": [("PERIODE_MS = 5000;", "PERIODE_MS = 2000;"), *_MANY_READS(7)],
    "period_5s_16_reads": [*_MANY_READS(15)],
    "max_run_time_without_rise_reset": [("niveau >= niveau_debut + HAUSSE_MIN", "false")],
    "stop_inclusive": [("niveau > SEUIL_HAUT) {  // FILLING", "niveau >= SEUIL_HAUT) {  // FILLING")],
    "start_inclusive": [("if (niveau < SEUIL_BAS) {", "if (niveau <= SEUIL_BAS) {")],
    "rounded_percent": [("(raw - RAW_0_PCT) * 100 / (RAW_100_PCT - RAW_0_PCT);",
                         "((raw - RAW_0_PCT) * 100 + (RAW_100_PCT - RAW_0_PCT) / 2) / (RAW_100_PCT - RAW_0_PCT);")],
    "alarm_message_reworded": [("ESP_LOGE(TAG, \"ALARME : %s, pompe coupée jusqu'au redémarrage\", raison);",
                                "ESP_LOGE(TAG, \"alarme %s\", raison);")],
}


@pytest.mark.parametrize("edits", ES6_VARIANTS.values(), ids=ES6_VARIANTS.keys())
def test_es6_tp_legitimate_variant_passes(tmp_path, bwrap_ok, edits):
    code, out = _es6_run(tmp_path, _es6_mutant(*edits))
    assert code == 0 and out.startswith("OK"), out


def test_es6_tp_logging_flood_still_fails_with_the_wide_cap(tmp_path, bwrap_ok):
    src = _es6_mutant(("PERIODE_MS = 5000;", "PERIODE_MS = 10;"),
                      ("int brut = lire_brut();", 'int brut = lire_brut();\n        ESP_LOGI(TAG, "mesure %d", brut);'))
    code, out = _es6_run(tmp_path, src)
    assert failed(code, out) and "12000000 octets" in out and "trop d'événements" in out and "scénario « a »" in out, out
    assert len(out) <= 4000, len(out)


@pytest.mark.parametrize("edits,expected", ES6_MUTANTS.values(), ids=ES6_MUTANTS.keys())
def test_es6_tp_mutant(tmp_path, bwrap_ok, edits, expected):
    code, out = _es6_run(tmp_path, _es6_mutant(*edits))
    assert failed(code, out) and all(fragment in out for fragment in expected) and "relire" in out, out


def test_es6_check_sections_exist_in_lesson():
    """Chaque « relire : <section> » du contrôle renvoie à un titre réel de la leçon."""
    import re
    lesson = (ES6.parent / "es6.md").read_text(encoding="utf-8")
    titles = set(re.findall(r"^## (.+)$", lesson, re.M))
    source = (ESP / "checks" / "es6-tp.py").read_text(encoding="utf-8")
    constants = dict(re.findall(r'^(S_\w+) = "([^"]+)"$', source, re.M))
    cited = set(re.findall(r"relire : « ([^»{]+) »", source)) | set(constants.values())
    assert cited and cited <= titles, cited - titles


# ---- restarts and the thread budget under the sandbox (Task 15, fix round 1) ----

SYS_HEAD = HEAD + ('#include "esp_system.h"\n#include "esp_event.h"\n#include "esp_netif.h"\n#include "esp_wifi.h"\n'
                   '#include "nvs_flash.h"\n#include "nvs.h"\n#include "mqtt_client.h"\n#include <string.h>\n')


def sandboxed(drv, src: str, scenario: dict, max_ms: int):
    """(trace, None) when the run is accepted, (None, learner message) when the driver refuses it."""
    try:
        return drv._run_once(src, scenario, max_ms, 30, "", drv.MAX_OUT)[0], None
    except drv.CheckError as e:
        return None, str(e)


def test_scripted_reboot_keeps_committed_nvs_in_the_sandbox(drv, bwrap_ok):
    src = SYS_HEAD + r'''
extern "C" void app_main(void) {
    ESP_ERROR_CHECK(nvs_flash_init());
    nvs_handle_t h;
    ESP_ERROR_CHECK(nvs_open("cfg", NVS_READWRITE, &h));
    uint32_t boots = 0;
    nvs_get_u32(h, "boots", &boots);
    ESP_LOGI("boot", "boots=%u", (unsigned)boots);
    ESP_ERROR_CHECK(nvs_set_u32(h, "boots", boots + 1));
    ESP_ERROR_CHECK(nvs_commit(h));
    for (;;) vTaskDelay(pdMS_TO_TICKS(100));
}
'''
    trace, message = sandboxed(drv, src, {"reboots_at_ms": [1000, 2000]}, 3000)
    assert message is None, message
    assert [e["msg"] for e in trace.logs("boot")] == ["boots=0", "boots=1", "boots=2"]
    assert [e["reason"] for e in trace.events("reboot")] == ["scripted", "scripted"]


def test_restart_at_boot_is_a_boot_loop_not_a_busy_loop(drv, bwrap_ok):
    trace, message = sandboxed(drv, app("esp_restart();", SYS_HEAD), {}, 1000)
    assert trace is None
    assert "redémarre en boucle" in message and "esp_restart" in message, message
    assert "ajoutez un vTaskDelay" not in message and "ne rend jamais la main" not in message, message


def test_fast_restart_loop_is_reported_as_restarts_not_adc_flood(drv, bwrap_ok):
    trace, message = sandboxed(drv, app("vTaskDelay(1);\nesp_restart();", SYS_HEAD), {}, 60000)
    assert trace is None
    assert "redémarre" in message and "esp_restart" in message, message
    assert "lectures ADC" not in message, message


def test_wifi_mqtt_and_four_tasks_fit_the_thread_budget(drv, bwrap_ok):
    src = SYS_HEAD + r'''
static void worker(void *) { for (;;) vTaskDelay(pdMS_TO_TICKS(100)); }
static void on_event(void *, esp_event_base_t, int32_t, void *) {}
extern "C" void app_main(void) {
    ESP_ERROR_CHECK(nvs_flash_init());
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &on_event, NULL));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_start());
    esp_mqtt_client_config_t mc = {};
    mc.broker.address.uri = "mqtt://broker.local";
    esp_mqtt_client_handle_t c = esp_mqtt_client_init(&mc);
    ESP_ERROR_CHECK(esp_mqtt_client_register_event(c, MQTT_EVENT_ANY, on_event, NULL));
    ESP_ERROR_CHECK(esp_mqtt_client_start(c));
    for (int i = 0; i < 4; i++) xTaskCreate(worker, "worker", 2048, nullptr, 1, nullptr);
    vTaskDelay(pdMS_TO_TICKS(2000));
    ESP_LOGI("end", "all alive");
}
'''
    trace, message = sandboxed(drv, src, {"reboots_at_ms": [500]}, 3000)
    assert message is None, message
    assert [e["msg"] for e in trace.logs("end")] == ["all alive"]


def test_too_many_tasks_message_is_exact(drv):
    msg = drv.MSG_TOO_MANY_TASKS
    assert "au moins 4" in msg and "Wi-Fi" in msg and "MQTT" in msg


# ---- TP es7 (Wi-Fi : NVS, événements, reconnexion à attente croissante) : solution livrée + variantes ----

ES7 = Path(__file__).resolve().parents[2] / "content" / "modules" / "esp3" / "lessons" / "es7.tp"


def _es7_reference() -> str:
    text = (ES7 / "solution.sh").read_text(encoding="utf-8")
    return text.split("<<'EOF'\n", 1)[1].rsplit("\nEOF", 1)[0] + "\n"


def _es7_mutant(*edits: tuple[str, str]) -> str:
    src = _es7_reference()
    for old, new in edits:
        assert old in src, old
        src = src.replace(old, new)
    return src


def _es7_run(tmp_path, src: str) -> tuple[int, str]:
    return run(tmp_path, src, tp="es7-tp")


def test_es7_tp_reference_passes(tmp_path, bwrap_ok):
    code, out = _es7_run(tmp_path, _es7_reference())
    assert code == 0 and out.startswith("OK"), out


def test_es7_tp_seed_refused(tmp_path, bwrap_ok):
    code, out = _es7_run(tmp_path, (ES7 / "seed" / "main.cpp").read_text(encoding="utf-8"))
    assert failed(code, out) and "motif d'initialisation de la NVS est incomplet" in out and "relire" in out, out


NVS_CALL = "    init_nvs();\n"
REGISTER_WIFI = ("    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &gestionnaire, NULL, "
                 "&inst_wifi));\n")
REGISTER_IP = ("    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &gestionnaire, NULL, "
               "&inst_ip));\n")
TAG_LINE = 'static const char *TAG = "wifi";'
PASSWORD_COPY = "CONFIG_ESP_WIFI_PASSWORD, sizeof(conf.sta.password) - 1"
IP_LOG = '        ESP_LOGI(TAG, "adresse IP : " IPSTR, IP2STR(&ev->ip_info.ip));\n'
ABANDON_RETURN = "                return;\n"
START_CONNECT = "        esp_wifi_connect();\n    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED)"

# nom -> (remplacements (ancien, nouveau), fragments de message attendus)
ES7_MUTANTS = {
    # NVS
    "nvs_not_initialised": ([(NVS_CALL, "")], ["ESP_ERROR_CHECK a arrêté le programme", "NVS_NOT_INITIALIZED"]),
    "nvs_pattern_incomplete": ([("ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND", "ret != ESP_OK")],
                               ["motif d'initialisation de la NVS est incomplet", "La NVS d'abord"]),
    # attentes
    "tight_loop_reconnect_in_handler": ([("        xEventGroupSetBits(groupe, BIT_PERDU);", "        esp_wifi_connect();")],
                                        ["scénario a", "attente de 0 s", "il en faut 1 s", "attente croissante"]),
    "wait_one_tick": ([("vTaskDelay(pdMS_TO_TICKS(ms));", "vTaskDelay(1);")],
                      ["scénario a", "attente de 0,01 s", "il en faut 1 s"]),
    "wait_in_ticks_not_ms": ([("vTaskDelay(pdMS_TO_TICKS(ms));", "vTaskDelay(ms);")],
                             ["scénario a", "attente de 10 s", "il en faut 1 s"]),
    "constant_wait_1s": ([("        ms *= 2;", "        ms += 0;")], ["scénario a", "attente de 1 s", "il en faut 2 s"]),
    "no_cap_on_wait": ([("i < n && ms < ATTENTE_MAX_MS", "i < n"), ("return ms > ATTENTE_MAX_MS ? ATTENTE_MAX_MS : ms;", "return ms;")],
                       ["scénario b", "seulement", "tentative(s)"]),
    "cap_at_4s": ([("ATTENTE_MAX_MS = 8000;", "ATTENTE_MAX_MS = 4000;")],
                  ["scénario b", "attente de 4 s", "échec n°4", "il en faut 8 s"]),
    "linear_wait": ([("        ms *= 2;", "        ms += 1000;")], ["scénario a", "attente de 3 s", "il en faut 4 s"]),
    # nombre d'essais
    "no_attempt_limit": ([("if (echecs >= MAX_TENTATIVES) {", "if (false) {")],
                         ["scénario b", "tentatives en 120 s au lieu de 10", "abandonner"]),
    "limit_9": ([("MAX_TENTATIVES = 10;", "MAX_TENTATIVES = 9;")], ["scénario b", "seulement 9 tentative(s)"]),
    "limit_11": ([("MAX_TENTATIVES = 10;", "MAX_TENTATIVES = 11;")], ["scénario b", "11 tentatives en 120 s au lieu de 10"]),
    "give_up_after_first_failure": ([("MAX_TENTATIVES = 10;", "MAX_TENTATIVES = 1;")],
                                    ["scénario a", "jamais connecté", "1 échec(s)", "plus aucune tentative"]),
    "one_more_connect_after_giving_up": ([(ABANDON_RETURN, "                esp_wifi_connect();\n" + ABANDON_RETURN)],
                                         ["scénario b", "11 tentatives", "ne plus jamais rappeler"]),
    "restart_on_giving_up": ([(ABANDON_RETURN, "                esp_restart();\n"),
                              ('#include "nvs_flash.h"', '#include "nvs_flash.h"\n#include "esp_system.h"')],
                             ["scénario b", "la carte a redémarré", "abandonner proprement"]),
    # gestionnaires et pile réseau
    "handlers_not_registered": ([(REGISTER_WIFI, ""), (REGISTER_IP, "")],
                                ["scénario a", "STA_START", "aucune tentative de connexion", "AVANT esp_wifi_start"]),
    "ip_handler_not_registered": ([(REGISTER_IP, "")], ["scénario a", "n'est pas journalisée", "adresse IP : 192.168.1.42"]),
    "sta_start_does_not_connect": ([(START_CONNECT, "        ESP_LOGI(TAG, \"démarré\");\n    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED)")],
                                   ["scénario a", "aucune tentative de connexion"]),
    "no_default_sta_netif": ([("    esp_netif_create_default_wifi_sta();\n", "")], ["scénario a", "l'adresse IP n'est jamais arrivée"]),
    # mot de passe et adresse en dur (analyse statique)
    "password_literal": ([(PASSWORD_COPY, '"abcdefgh12", sizeof(conf.sta.password) - 1')],
                         ["mot de passe en dur", "CONFIG_ESP_WIFI_PASSWORD", "Le mot de passe ne s'écrit jamais"]),
    "password_in_named_constant": ([(TAG_LINE, TAG_LINE + '\nstatic const char *MDP = "unsecret123";'),
                                    (PASSWORD_COPY, "MDP, sizeof(conf.sta.password) - 1")],
                                   ["mot de passe en dur", "MDP"]),
    "password_in_define": ([(TAG_LINE, TAG_LINE + '\n#define WIFI_PWD "unsecret123"')], ["mot de passe en dur", "#define"]),
    "sample_password_written": ([(TAG_LINE, TAG_LINE + '\nstatic const char *X = "exemple-motdepasse";')],
                                ["mot de passe d'exemple est écrit dans main.cpp"]),
    "password_not_read_from_config": ([("    strncpy((char *)conf.sta.password, CONFIG_ESP_WIFI_PASSWORD, sizeof(conf.sta.password) - 1);\n", "")],
                                      ["doit être lu avec CONFIG_ESP_WIFI_PASSWORD"]),
    "ip_literal": ([(IP_LOG, '        ESP_LOGI(TAG, "adresse IP : 192.168.1.42");\n')], ["192.168.1.42 est écrite en dur", "Journaliser l'adresse"]),
    # journaux
    "ip_wrong_format": ([('"adresse IP : " IPSTR', '"ip obtenue " IPSTR')], ["scénario a", "n'est pas journalisée", "ip obtenue 192.168.1.42"]),
    "ip_logged_twice": ([(IP_LOG, IP_LOG + IP_LOG)], ["scénario a", "2 lignes", "au lieu d'une"]),
    "error_log_on_every_failure": ([('ESP_LOGW(TAG, "échec', 'ESP_LOGE(TAG, "échec')],
                                   ["scénario a", "ESP_LOGE de tag « wifi »", "alors que la connexion réussit"]),
    "no_error_log_on_giving_up": ([('ESP_LOGE(TAG, "abandon', 'ESP_LOGW(TAG, "abandon')], ["scénario b", "aucune ligne d'erreur"]),
    "error_log_of_another_tag_on_every_failure": ([('ESP_LOGW(TAG, "échec', 'ESP_LOGE("reco", "échec')],
                                                  ["scénario a", "ESP_LOGE", "alors que la connexion réussit"]),
    "extra_error_log_of_another_tag_on_giving_up": ([(ABANDON_RETURN, '                ESP_LOGE("reco", "fin");\n' + ABANDON_RETURN)],
                                                    ["scénario b", "2 lignes ESP_LOGE", "au lieu d'une"]),
    "wrong_tag_on_giving_up": ([('ESP_LOGE(TAG, "abandon', 'ESP_LOGE("reseau", "abandon')], ["scénario b", "aucune ligne d'erreur"]),
}


@pytest.mark.parametrize("edits,expected", ES7_MUTANTS.values(), ids=ES7_MUTANTS.keys())
def test_es7_tp_mutant(tmp_path, bwrap_ok, edits, expected):
    code, out = _es7_run(tmp_path, _es7_mutant(*edits))
    assert failed(code, out) and all(fragment in out for fragment in expected) and "relire" in out, out


# Variante valide écrite autrement : le compteur et la décision sont dans le gestionnaire, une tâche dédiée attend et rappelle.
ES7_TASK_VARIANT = r'''
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "esp_log.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "nvs_flash.h"
#include "sdkconfig.h"

static const char *TAG = "wifi";
static const EventBits_t BIT_RECONNEXION = 1 << 0;
static EventGroupHandle_t groupe;
static int tentatives = 0;      // tentatives de connexion lancées
static int prochaine_attente_ms = 0;

static void tache_reconnexion(void *) {
    for (;;) {
        xEventGroupWaitBits(groupe, BIT_RECONNEXION, pdTRUE, pdFALSE, portMAX_DELAY);
        vTaskDelay(pdMS_TO_TICKS(prochaine_attente_ms));
        tentatives++;
        esp_wifi_connect();
    }
}

static void gestionnaire(void *arg, esp_event_base_t base, int32_t id, void *data) {
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        tentatives = 1;
        esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        if (tentatives >= 10) {
            ESP_LOGE(TAG, "on abandonne après %d tentatives", tentatives);
        } else {
            prochaine_attente_ms = 1000 << (tentatives - 1);
            if (prochaine_attente_ms > 8000) prochaine_attente_ms = 8000;
            ESP_LOGI(TAG, "tentative %d échouée, on attend %d ms", tentatives, prochaine_attente_ms);
            xEventGroupSetBits(groupe, BIT_RECONNEXION);
        }
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *ev = (ip_event_got_ip_t *)data;
        ESP_LOGI(TAG, "adresse IP : " IPSTR, IP2STR(&ev->ip_info.ip));
        tentatives = 0;
    }
}

extern "C" void app_main(void) {
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);
    groupe = xEventGroupCreate();
    xTaskCreate(tache_reconnexion, "reconnexion", 3072, NULL, 5, NULL);
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &gestionnaire, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &gestionnaire, NULL));
    wifi_config_t conf = {};
    memcpy(conf.sta.ssid, CONFIG_ESP_WIFI_SSID, strlen(CONFIG_ESP_WIFI_SSID));
    memcpy(conf.sta.password, CONFIG_ESP_WIFI_PASSWORD, strlen(CONFIG_ESP_WIFI_PASSWORD));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &conf));
    ESP_ERROR_CHECK(esp_wifi_start());
}
'''

ES7_VARIANTS = {
    "wait_polling_in_100ms_steps": [("vTaskDelay(pdMS_TO_TICKS(ms));",
                                     "for (int t = 0; t < ms; t += 100) {\n                vTaskDelay(pdMS_TO_TICKS(100));\n            }")],
    "wait_a_little_longer": [("vTaskDelay(pdMS_TO_TICKS(ms));", "vTaskDelay(pdMS_TO_TICKS(ms + 300));")],
    "wait_a_little_shorter": [("vTaskDelay(pdMS_TO_TICKS(ms));", "vTaskDelay(pdMS_TO_TICKS(ms - 30));")],
    "retry_logged_at_info_level": [('ESP_LOGW(TAG, "échec', 'ESP_LOGI(TAG, "échec')],
    "plain_handler_registration": [
        (REGISTER_WIFI, "    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &gestionnaire, NULL));\n"),
        (REGISTER_IP, "    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &gestionnaire, NULL));\n")],
    "password_through_a_macro_alias": [(TAG_LINE, TAG_LINE + "\n#define MON_SECRET CONFIG_ESP_WIFI_PASSWORD"),
                                       (PASSWORD_COPY, "MON_SECRET, sizeof(conf.sta.password) - 1")],
    "password_with_memcpy": [("    strncpy((char *)conf.sta.password, CONFIG_ESP_WIFI_PASSWORD, sizeof(conf.sta.password) - 1);",
                              "    memcpy(conf.sta.password, CONFIG_ESP_WIFI_PASSWORD, strlen(CONFIG_ESP_WIFI_PASSWORD));")],
    "pdpass_check_on_a_task_creation": [
        ("    demarrer_wifi();\n", '    demarrer_wifi();\n    if (xTaskCreate([](void *) { vTaskDelete(NULL); }, "aux", 2048, NULL, 5, NULL) != pdPASS) {\n'
                                  '        ESP_LOGW(TAG, "tâche auxiliaire impossible");\n    }\n')],
    "password_length_test_with_warning": [
        ("    demarrer_wifi();\n", '    if (strlen(CONFIG_ESP_WIFI_PASSWORD) < 8) ESP_LOGW(TAG, "mot de passe trop court");\n    demarrer_wifi();\n')],
    "auth_mode_logged": [
        ("    demarrer_wifi();\n", '    ESP_LOGI(TAG, "auth %d", (int)WIFI_AUTH_WPA2_PSK);\n    demarrer_wifi();\n')],
    "extra_info_log_when_giving_up": [(ABANDON_RETURN, '                ESP_LOGI(TAG, "plus de tentative");\n' + ABANDON_RETURN)],
    "comment_inside_the_nvs_pattern": [("        ESP_ERROR_CHECK(nvs_flash_erase());",
                                        "        // NVS pleine ou trop récente : on l'efface\n        ESP_ERROR_CHECK(nvs_flash_erase());")],
}


@pytest.mark.parametrize("edits", ES7_VARIANTS.values(), ids=ES7_VARIANTS.keys())
def test_es7_tp_legitimate_variant_passes(tmp_path, bwrap_ok, edits):
    code, out = _es7_run(tmp_path, _es7_mutant(*edits))
    assert code == 0 and out.startswith("OK"), out


def test_es7_tp_task_and_handler_state_variant_passes(tmp_path, bwrap_ok):
    code, out = _es7_run(tmp_path, ES7_TASK_VARIANT)
    assert code == 0 and out.startswith("OK"), out


def test_es7_check_sections_exist_in_lesson():
    """Chaque « relire : <section> » du contrôle renvoie à un titre réel de la leçon."""
    import re
    lesson = (ES7.parent / "es7.md").read_text(encoding="utf-8")
    titles = set(re.findall(r"^## (.+)$", lesson, re.M))
    source = (ESP / "checks" / "es7-tp.py").read_text(encoding="utf-8")
    constants = dict(re.findall(r'^(S_\w+) = "([^"]+)"$', source, re.M))
    cited = set(re.findall(r"relire : « ([^»{]+) »", source)) | set(constants.values())
    assert cited and cited <= titles, cited - titles


# ---- TP es8 (MQTT : télémétrie, statut avec testament, commandes bornées par la limite de sécurité) ----

ES8 = Path(__file__).resolve().parents[2] / "content" / "modules" / "esp3" / "lessons" / "es8.tp"


def _es8_reference() -> str:
    text = (ES8 / "solution.sh").read_text(encoding="utf-8")
    return text.split("<<'EOF'\n", 1)[1].rsplit("\nEOF", 1)[0] + "\n"


def _es8_mutant(*edits: tuple[str, str]) -> str:
    src = _es8_reference()
    for old, new in edits:
        assert old in src, old
        src = src.replace(old, new)
    return src


def _es8_run(tmp_path, src: str) -> tuple[int, str]:
    return run(tmp_path, src, tp="es8-tp")


def test_es8_tp_reference_passes(tmp_path, bwrap_ok):
    code, out = _es8_run(tmp_path, _es8_reference())
    assert code == 0 and out.startswith("OK"), out


def test_es8_tp_seed_refused(tmp_path, bwrap_ok):
    code, out = _es8_run(tmp_path, (ES8 / "seed" / "main.cpp").read_text(encoding="utf-8"))
    assert failed(code, out) and "aucun événement MQTT" in out and "relire" in out, out


JSON_FMT = '"{\\"level\\": %.1f, \\"relay\\": %s}"'
PUBLISH_ONLINE = '        esp_mqtt_client_publish(ev->client, TOPIC_STATUT, "online", 0, 1, 1);\n'
SUBSCRIBE = "        esp_mqtt_client_subscribe_single(ev->client, TOPIC_COMMANDE, 1);\n"
LWT_LINES = ('    cfg.session.last_will.topic = TOPIC_STATUT;\n    cfg.session.last_will.msg = "offline";\n'
             "    cfg.session.last_will.qos = 1;\n    cfg.session.last_will.retain = true;\n")
START = "    ESP_ERROR_CHECK(esp_mqtt_client_start(client));\n"
REFUSE_LOG = 'ESP_LOGW(TAG, "command refused: level=%d%%", (int)niveau);'
SET_RELAY = "    regler_relais(voulu);\n}"
NOT_A_COMMAND = "        return;  // pas une commande : on ignore"
TELE_LOOP = "        publier_telemetrie();\n        vTaskDelay(pdMS_TO_TICKS(PERIODE_MS));"

# nom -> (remplacements (ancien, nouveau), fragments de message attendus)
ES8_MUTANTS = {
    # télémétrie
    "wrong_telemetry_topic": ([('"home/devices/pool-ctl/telemetry"', '"home/devices/pool/telemetry"')],
                              ["scénario a", "aucun message sur le topic", "home/devices/pool/telemetry"]),
    "json_keys_not_quoted": ([(JSON_FMT, '"{level: %.1f, relay: %s}"')], ["scénario a", "n'est pas un JSON valide", "level: 72.5"]),
    "json_trailing_comma": ([(JSON_FMT, '"{\\"level\\": %.1f, \\"relay\\": %s,}"')], ["scénario a", "n'est pas un JSON valide"]),
    "json_relay_as_string": ([(JSON_FMT, '"{\\"level\\": %.1f, \\"relay\\": \\"%s\\"}"')],
                             ["scénario a", "« relay » doit être true ou false sans guillemets"]),
    "json_relay_as_number": ([('relais_actif ? "true" : "false"', 'relais_actif ? "1" : "0"')],
                             ["scénario a", "« relay » doit être true ou false"]),
    "json_relay_capitalised": ([('relais_actif ? "true" : "false"', 'relais_actif ? "True" : "False"')],
                               ["scénario a", "n'est pas un JSON valide"]),
    "json_extra_key": ([(JSON_FMT, '"{\\"level\\": %.1f, \\"relay\\": %s, \\"v\\": 1}"')],
                       ["scénario a", "exactement les clés « level » et « relay »"]),
    "json_nan_level": ([("niveau, relais_actif ?", "0.0 / 0.0, relais_actif ?")], ["scénario a", "n'est pas un JSON valide", "nan"]),
    "level_hard_coded": ([("lire_niveau(), relais);", "72.5, relais);")], ["scénario b", "niveau publié 72,5 %", "85,3 %"]),
    "level_in_raw_counts": ([("lire_niveau(), relais);", "lire_niveau() * 40.95, relais);")], ["scénario a", "niveau publié 2968"]),
    "relay_hard_coded_false": ([("lire_niveau(), relais);", "lire_niveau(), false);")],
                              ["scénario a", "annonce relay=false alors que le relais est allumé"]),
    "period_1s": ([("PERIODE_MS = 10000;", "PERIODE_MS = 1000;")], ["scénario a", "seulement 1 s entre deux messages", "10 s"]),
    "period_15s": ([("PERIODE_MS = 10000;", "PERIODE_MS = 15000;")], ["scénario a", "premier message de télémétrie", "toutes les 10 s"]),
    "period_5s": ([("PERIODE_MS = 10000;", "PERIODE_MS = 5000;")], ["scénario a", "seulement 5 s entre deux messages"]),
    "telemetry_stops_after_a_while": ([(TELE_LOOP, TELE_LOOP + "\n        if (xTaskGetTickCount() > pdMS_TO_TICKS(15000)) { vTaskDelay(portMAX_DELAY); }")],
                                      ["scénario a", "plus aucun message de télémétrie"]),
    # statut et testament
    "status_not_retained": ([(PUBLISH_ONLINE, PUBLISH_ONLINE.replace("0, 1, 1)", "0, 1, 0)"))],
                            ["scénario a", "sans le drapeau retain", "Le statut et le testament"]),
    "status_wrong_payload": ([('"online", 0, 1, 1', '"ONLINE", 0, 1, 1')], ["scénario a", "« ONLINE » au lieu de « online »"]),
    "status_wrong_topic": ([(PUBLISH_ONLINE, PUBLISH_ONLINE.replace("TOPIC_STATUT", '"home/devices/pool-ctl/state"'))],
                           ["scénario a", "aucun statut publié"]),
    "status_never_published": ([(PUBLISH_ONLINE, "")], ["scénario a", "aucun statut publié", "MQTT_EVENT_CONNECTED"]),
    "status_published_once_at_start": ([(PUBLISH_ONLINE, ""),
                                        (START, START + '    esp_mqtt_client_publish(client, TOPIC_STATUT, "online", 0, 1, 1);\n')],
                                       ["scénario c", "aucun statut publié", "reconnexions comprises"]),
    "no_last_will": ([(LWT_LINES, "")], ["scénario a", "n'a aucun testament"]),
    "last_will_not_retained": ([("last_will.retain = true;", "last_will.retain = false;")],
                               ["scénario a", "le testament n'est pas retenu"]),
    "last_will_wrong_message": ([('last_will.msg = "offline";', 'last_will.msg = "Offline";')],
                                ["scénario a", "« Offline » au lieu de « offline »"]),
    "last_will_wrong_topic": ([("last_will.topic = TOPIC_STATUT;", 'last_will.topic = "home/devices/pool-ctl/lwt";')],
                              ["scénario a", "le testament est publié sur"]),
    # abonnement et commandes
    "no_subscription": ([(SUBSCRIBE, "")], ["scénario a", "aucun abonnement à", "session est propre"]),
    "subscribe_wrong_topic": ([(SUBSCRIBE, SUBSCRIBE.replace("TOPIC_COMMANDE", '"home/devices/pool-ctl/cmd"'))],
                              ["scénario a", "aucun abonnement"]),
    "subscribe_before_connected": ([(SUBSCRIBE, ""), (START, START + "    esp_mqtt_client_subscribe_single(client, TOPIC_COMMANDE, 1);\n")],
                                   ["scénario a", "aucun abonnement"]),
    "subscribe_only_once": ([(SUBSCRIBE, "        if (!abonne) { abonne = true; esp_mqtt_client_subscribe_single(ev->client, TOPIC_COMMANDE, 1); }\n"),
                             ("static esp_mqtt_client_handle_t client;", "static esp_mqtt_client_handle_t client;\nstatic bool abonne = false;")],
                            ["scénario c", "aucun abonnement", "qui suivent la connexion de"]),
    "subscribe_only_in_telemetry_loop": ([(SUBSCRIBE, ""),
                                          ("    char json[64];\n", "    char json[64];\n    esp_mqtt_client_subscribe_single(client, TOPIC_COMMANDE, 1);\n")],
                                         ["scénario a", "aucun abonnement", "dans les 5 s"]),
    "topic_compared_with_strcmp": ([("strncmp(ev->topic, TOPIC_COMMANDE, ev->topic_len) == 0", "strcmp(ev->topic, TOPIC_COMMANDE) == 0")],
                                   ["scénario a", "devait allumer le relais", "topic_len"]),
    "space_after_colon_not_skipped": ([("while (*p == ' ' || *p == ':') {", "while (*p == ':') {")],
                                      ["scénario a", "devait allumer le relais", "avec ou sans espace"]),
    "exact_text_expected": ([('strstr(msg, "\\"relay\\"")', 'strstr(msg, "\\"relay\\": ")')],
                            ["scénario a", "devait éteindre le relais"]),
    "garbage_switches_relay_off": ([(NOT_A_COMMAND, "        regler_relais(false);\n        return;")],
                                   ["scénario a", "le relais passe à 0 à 50 s sans commande valide"]),
    "relay_changes_late": ([(SET_RELAY, "    vTaskDelay(pdMS_TO_TICKS(2000));\n" + SET_RELAY)],
                           ["scénario a", "n'a changé le relais qu'à 32 s", "dans la seconde"]),
    "off_command_ignored": ([(SET_RELAY, "    if (voulu) {\n        regler_relais(true);\n    }\n}")],
                            ["scénario a", "devait éteindre le relais"]),
    # limite de sécurité
    "command_executed_above_limit": ([("if (niveau > LIMITE_PCT) {", "if (false) {")],
                                     ["scénario b", "le relais est allumé à 30 s", "85 %", "limite de sécurité"]),
    "limit_too_low": ([("LIMITE_PCT = 80.0;", "LIMITE_PCT = 70.0;")], ["scénario a", "devait allumer le relais"]),
    "limit_too_high": ([("LIMITE_PCT = 80.0;", "LIMITE_PCT = 90.0;")], ["scénario b", "le relais est allumé"]),
    "refusal_not_logged": ([(REFUSE_LOG, 'ESP_LOGI(TAG, "ignorée");')], ["scénario b", "n'est pas journalisé comme demandé"]),
    "refusal_wrong_format": ([(REFUSE_LOG, 'ESP_LOGW(TAG, "commande refusée : niveau=%d%%", (int)niveau);')],
                             ["scénario b", "n'est pas journalisé comme demandé", "command refused: level=85%", "refusée"]),
    "refusal_wrong_level": ([(REFUSE_LOG, 'ESP_LOGW(TAG, "command refused: level=%d%%", (int)LIMITE_PCT);')],
                            ["scénario b", "n'est pas journalisé comme demandé"]),
    "refusal_with_error_level": ([('ESP_LOGW(TAG, "command refused', 'ESP_LOGE(TAG, "command refused')],
                                 ["scénario b", "n'est pas journalisé comme demandé", "niveau E"]),
    "refusal_wrong_tag": ([('ESP_LOGW(TAG, "command refused', 'ESP_LOGW("relais", "command refused')],
                          ["scénario b", "n'est pas journalisé comme demandé"]),
    "refusal_logged_twice": ([(REFUSE_LOG, REFUSE_LOG + "\n            " + REFUSE_LOG)], ["scénario b", "2 lignes de refus"]),
    "refusal_logged_for_accepted_command": ([(SET_RELAY, '    ESP_LOGW(TAG, "command refused: level=%d%%", 0);\n' + SET_RELAY)],
                                            ["scénario a", "journalisée comme refusée"]),
    # reconnexion et redémarrage
    "auto_reconnect_disabled": ([(LWT_LINES, LWT_LINES + "    cfg.network.disable_auto_reconnect = true;\n")],
                                ["scénario c", "une seule connexion", "reconnexion"]),
    "restart_on_disconnect": ([("    case MQTT_EVENT_DATA:", "    case MQTT_EVENT_DISCONNECTED:\n        esp_restart();\n        break;\n    case MQTT_EVENT_DATA:"),
                               ('#include "mqtt_client.h"', '#include "mqtt_client.h"\n#include "esp_system.h"')],
                              ["scénario c", "la carte a redémarré"]),
    "no_broker_address": ([("cfg.broker.address.uri = URI_COURTIER;\n", "")], ["ESP_ERROR_CHECK a arrêté le programme", "esp_mqtt_client_start"]),
}


@pytest.mark.parametrize("edits,expected", ES8_MUTANTS.values(), ids=ES8_MUTANTS.keys())
def test_es8_tp_mutant(tmp_path, bwrap_ok, edits, expected):
    code, out = _es8_run(tmp_path, _es8_mutant(*edits))
    assert failed(code, out) and all(fragment in out for fragment in expected) and "relire" in out, out


# Variante valide, écrite autrement : télémétrie publiée par une tâche dédiée, JSON bâti avec std::string, abonnement par
# un filtre à joker, statut en QoS 0, testament avec msg_len, niveau en entier, refus qui éteint aussi le relais.
ES8_TASK_VARIANT_EDITS = [
    ("    for (;;) {\n        publier_telemetrie();\n        vTaskDelay(pdMS_TO_TICKS(PERIODE_MS));\n    }\n}\n",
     '    xTaskCreate(tache_telemetrie, "telemetrie", 4096, NULL, 5, NULL);\n}\n'),
    ("#include <string.h>", "#include <string.h>\n#include <string>"),
    ("    return snprintf(buf, taille, " + JSON_FMT + ", niveau, relais_actif ? \"true\" : \"false\");",
     '    char nombre[16];\n    snprintf(nombre, sizeof(nombre), "%.1f", niveau);\n'
     '    std::string s = std::string("{\\"level\\": ") + nombre + ", \\"relay\\": " + (relais_actif ? "true" : "false") + "}";\n'
     '    return snprintf(buf, taille, "%s", s.c_str());'),
    ("static void demarrer_mqtt(void) {", "static void tache_telemetrie(void *) {\n    for (;;) {\n        publier_telemetrie();\n"
                                          "        vTaskDelay(pdMS_TO_TICKS(PERIODE_MS));\n    }\n}\n\nstatic void demarrer_mqtt(void) {"),
    ("esp_mqtt_client_subscribe_single(ev->client, TOPIC_COMMANDE, 1);", 'esp_mqtt_client_subscribe_single(ev->client, "home/devices/+/command", 0);'),
    ('"online", 0, 1, 1', '"online", 0, 0, 1'),
    ("last_will.qos = 1;", "last_will.qos = 1;\n    cfg.session.last_will.msg_len = 7;"),
]


def test_es8_tp_task_variant_passes(tmp_path, bwrap_ok):
    code, out = _es8_run(tmp_path, _es8_mutant(*ES8_TASK_VARIANT_EDITS))
    assert code == 0 and out.startswith("OK"), out


ES8_VARIANTS = {
    "level_with_no_decimal": [(JSON_FMT, '"{\\"level\\": %.0f, \\"relay\\": %s}"')],
    "telemetry_in_qos_1": [("esp_mqtt_client_publish(client, TOPIC_TELEMETRIE, json, 0, 0, 0)", "esp_mqtt_client_publish(client, TOPIC_TELEMETRIE, json, 0, 1, 0)")],
    "subscription_in_qos_0": [("TOPIC_COMMANDE, 1);\n        break;", "TOPIC_COMMANDE, 0);\n        break;")],
    "default_client_id": [('    cfg.credentials.client_id = "pool-ctl";\n', "")],
    "refusal_also_switches_the_relay_off": [(REFUSE_LOG + "\n            return;", REFUSE_LOG + "\n            regler_relais(false);\n            return;")],
    "received_message_logged_with_its_length": [(NOT_A_COMMAND, '        ESP_LOGI(TAG, "reçu : %.*s", len, data);\n' + NOT_A_COMMAND)],
    "level_compared_as_an_integer": [("if (niveau > LIMITE_PCT) {", "if ((int)niveau > (int)LIMITE_PCT) {")],
    "publication_refused_logged_in_english": [('ESP_LOGI(TAG, "télémétrie non envoyée : client déconnecté");', 'ESP_LOGI(TAG, "publish refused: client offline");')],
    "telemetry_not_sent_message_dropped": [('ESP_LOGI(TAG, "télémétrie non envoyée : client déconnecté");', "")],
    "event_loop_all_cases_listed": [("    default:\n        break;\n    }\n}\n\n// Configure",
                                    '    case MQTT_EVENT_DISCONNECTED:\n        ESP_LOGW(TAG, "déconnecté du courtier");\n        break;\n'
                                    '    case MQTT_EVENT_ERROR:\n        ESP_LOGW(TAG, "erreur de connexion");\n        break;\n    default:\n        break;\n    }\n}\n\n// Configure'),],
    "wake_up_with_a_short_period_task_delay": [("vTaskDelay(pdMS_TO_TICKS(PERIODE_MS));", "vTaskDelay(pdMS_TO_TICKS(PERIODE_MS - 20));")],
}


@pytest.mark.parametrize("edits", ES8_VARIANTS.values(), ids=ES8_VARIANTS.keys())
def test_es8_tp_legitimate_variant_passes(tmp_path, bwrap_ok, edits):
    code, out = _es8_run(tmp_path, _es8_mutant(*edits))
    assert code == 0 and out.startswith("OK"), out


def test_es8_check_sections_exist_in_lesson():
    """Chaque « relire : <section> » du contrôle renvoie à un titre réel de la leçon."""
    import re
    lesson = (ES8.parent / "es8.md").read_text(encoding="utf-8")
    titles = set(re.findall(r"^## (.+)$", lesson, re.M))
    source = (ESP / "checks" / "es8-tp.py").read_text(encoding="utf-8")
    constants = dict(re.findall(r'^(S_\w+) = "([^"]+)"$', source, re.M))
    cited = set(re.findall(r"relire : « ([^»{]+) »", source)) | set(constants.values())
    assert cited and cited <= titles, cited - titles


# ---- TP es9 (robustesse : réabonnement, consigne en NVS, watchdog de tâche, publication sans ESP_ERROR_CHECK) ----

ES9 = Path(__file__).resolve().parents[2] / "content" / "modules" / "esp3" / "lessons" / "es9.tp"


def _es9_reference() -> str:
    text = (ES9 / "solution.sh").read_text(encoding="utf-8")
    return text.split("<<'EOF'\n", 1)[1].rsplit("\nEOF", 1)[0] + "\n"


def _es9_mutant(*edits: tuple[str, str]) -> str:
    src = _es9_reference()
    for old, new in edits:
        assert old in src, old
        src = src.replace(old, new)
    return src


def _es9_run(tmp_path, src: str) -> tuple[int, str]:
    return run(tmp_path, src, tp="es9-tp")


def test_es9_tp_reference_passes(tmp_path, bwrap_ok):
    code, out = _es9_run(tmp_path, _es9_reference())
    assert code == 0 and out.startswith("OK"), out


def test_es9_tp_seed_refused(tmp_path, bwrap_ok):
    code, out = _es9_run(tmp_path, (ES9 / "seed" / "main.cpp").read_text(encoding="utf-8"))
    assert failed(code, out) and "app_main ne fait rien après les initialisations" in out and "étape 8" in out, out


RESTORE = "    haut = charger_consigne();\n"
SUBSCRIBE9 = "        esp_mqtt_client_subscribe_single(ev->client, TOPIC_COMMANDE, 1);\n"
WDT_RESET = "        ESP_ERROR_CHECK(esp_task_wdt_reset());\n"
COMMIT = "    if (err == ESP_OK) {\n        err = nvs_commit(h);\n    }\n"
PUBLISH9 = "    if (esp_mqtt_client_publish(client, TOPIC_TELEMETRIE, json, 0, 0, 0) < 0) {"
REFUSE9 = 'ESP_LOGW(TAG, "setpoint refused: high=%ld", valeur);'
WDT_ADD = "    ESP_ERROR_CHECK(esp_task_wdt_add(NULL));\n"
SAVE_CALL = "    sauver_consigne((int)valeur);\n"
RANGE9 = '    if (valeur < HAUT_MIN || valeur > HAUT_MAX) {\n        ESP_LOGW(TAG, "setpoint'
APP_INIT = "    init_relais();\n    init_adc();\n    init_nvs();\n"

ES9_MUTANTS = {
    # consigne et NVS
    "setpoint_lost_at_reboot": ([(RESTORE, "    haut = HAUT_DEFAUT;\n")], ["scénario a", "après le redémarrage de 120 s", "enregistrée en NVS"]),
    "write_without_commit": ([(COMMIT, "")], ["scénario a", "n'est pas suivie de nvs_commit", "Sauvegarder en NVS"]),
    "setpoint_never_saved": ([(SAVE_CALL, "")], ["scénario a", "après le redémarrage de 120 s"]),
    "nothing_saved_gives_zero": ([("return HAUT_DEFAUT;  // espace de noms pas encore créé", "return 0;  // espace de noms pas encore créé")],
                                 ["scénario a", "annonce la consigne 0"]),
    "refused_value_saved": ([(RANGE9, "    sauver_consigne((int)valeur);\n" + RANGE9)], ["scénario c", "refusée", "enregistrée en NVS"]),
    # relais au démarrage
    "relay_on_at_boot_before_restore": ([(APP_INIT, "    init_relais();\n    gpio_set_level(RELAIS_GPIO, 1);\n    init_adc();\n    init_nvs();\n")],
                                        ["scénario a", "n'est pas éteint au démarrage", "Restaurer au démarrage"]),
    "relay_driven_before_restore": ([(RESTORE, "    appliquer_consigne();\n" + RESTORE)], ["scénario b", "après le redémarrage de 60 s", "(40 %)", "AVANT de piloter le relais"]),
    "relay_lit_by_default_then_corrected": ([(RESTORE, RESTORE + "    regler_relais(true);\n    vTaskDelay(pdMS_TO_TICKS(50));\n    appliquer_consigne();\n")],
                                            ["scénario", "relais"]),
    # réabonnement
    "subscribe_only_once": ([(SUBSCRIBE9, "        if (!abonne) { abonne = true; esp_mqtt_client_subscribe_single(ev->client, TOPIC_COMMANDE, 1); }\n"),
                             ("static esp_mqtt_client_handle_t client;", "static esp_mqtt_client_handle_t client;\nstatic bool abonne = false;")],
                            ["scénario a", "aucun abonnement", "après la reconnexion"]),
    "no_subscription": ([(SUBSCRIBE9, "")], ["scénario a", "aucun abonnement"]),
    "subscribe_after_start_only": ([(SUBSCRIBE9, ""), ("    demarrer_mqtt();\n", "    demarrer_mqtt();\n    esp_mqtt_client_subscribe_single(client, TOPIC_COMMANDE, 1);\n")],
                                   ["scénario a", "aucun abonnement"]),
    "topic_compared_with_strcmp": ([("strncmp(ev->topic, TOPIC_COMMANDE, ev->topic_len) == 0", "strcmp(ev->topic, TOPIC_COMMANDE) == 0")],
                                   ["scénario a", "après la commande de 115 s", "topic_len"]),
    # watchdog
    "watchdog_never_fed": ([(WDT_RESET, "")], ["scénario a", "watchdog de tâche s'est déclenché", "Le watchdog de tâche"]),
    "watchdog_fed_once": ([(WDT_RESET, ""), ("    for (int tour = 0;; tour++) {\n", "    esp_task_wdt_reset();\n    for (int tour = 0;; tour++) {\n")],
                          ["scénario a", "watchdog de tâche s'est déclenché"]),
    "watchdog_never_used": ([(WDT_RESET, "        esp_task_wdt_reset();\n"), (WDT_ADD, "")],
                            ["aucun appel à esp_task_wdt_add", "Le watchdog de tâche"]),
    "watchdog_only_in_a_comment": ([(WDT_RESET, "        // esp_task_wdt_reset();\n"), (WDT_ADD, "    // esp_task_wdt_add(NULL);\n")],
                                   ["aucun appel à esp_task_wdt_add"]),
    "watchdog_names_only_in_strings": ([(WDT_RESET, '        ESP_LOGI(TAG, "esp_task_wdt_reset()");\n'), (WDT_ADD, '    ESP_LOGI(TAG, "esp_task_wdt_add(NULL)");\n')],
                                       ["aucun appel à esp_task_wdt_add"]),
    "watchdog_fed_too_late": ([("vTaskDelay(pdMS_TO_TICKS(PAS_MS));\n    }", "vTaskDelay(pdMS_TO_TICKS(PAS_MS));\n        if (tour == 20) { vTaskDelay(pdMS_TO_TICKS(20000)); }\n    }")],
                              ["scénario a", "watchdog de tâche s'est déclenché"]),
    "restart_on_error": ([('ESP_LOGI(TAG, "télémétrie non envoyée (hors connexion)");', "if (xTaskGetTickCount() > pdMS_TO_TICKS(5000)) esp_restart();")], ["scénario a", "redémarrage(s) inattendu(s)", "(sw)"]),
    # gestion d'erreur
    "error_check_on_publish": ([(PUBLISH9, "    ESP_ERROR_CHECK(esp_mqtt_client_publish(client, TOPIC_TELEMETRIE, json, 0, 0, 0) < 0 ? ESP_FAIL : ESP_OK);\n    if (false) {")],
                               ["ESP_ERROR_CHECK a arrêté le programme"]),
    "error_check_on_publish_during_outage": ([(PUBLISH9, "    if (esp_mqtt_client_publish(client, TOPIC_TELEMETRIE, json, 0, 0, 0) < 0 && xTaskGetTickCount() > pdMS_TO_TICKS(5000)) {\n        ESP_ERROR_CHECK(ESP_FAIL);\n    }\n    if (false) {")],
                                              ["ESP_ERROR_CHECK a arrêté le programme"]),
    "telemetry_stops_after_a_failure": ([(PUBLISH9, "    static bool arret = false;\n    if (arret) return;\n    if (esp_mqtt_client_publish(client, TOPIC_TELEMETRIE, json, 0, 0, 0) < 0 && (arret = true)) {")],
                                        ["scénario a", "aucun message sur"]),
    "telemetry_hard_coded_setpoint": ([("lire_niveau(), relais, haut);", "lire_niveau(), relais, HAUT_DEFAUT);")], ["scénario a", "annonce la consigne 60"]),
    "telemetry_relay_always_false": ([("lire_niveau(), relais, haut);", "lire_niveau(), false, haut);")], ["scénario a", "annonce relay=false"]),
    "telemetry_period_1s": ([("TOURS_TELEMETRIE = 10;", "TOURS_TELEMETRIE = 1;")], ["scénario a", "entre deux télémétries"]),
    # bornes de sécurité
    "setpoint_above_limit_accepted": ([("HAUT_MAX = 80;", "HAUT_MAX = 100;")], ["scénario c", "setpoint refused: high=95"]),
    "setpoint_80_refused": ([("HAUT_MAX = 80;", "HAUT_MAX = 79;")], ["scénario c", "refuse une commande"]),
    "setpoint_10_refused": ([("HAUT_MIN = 10;", "HAUT_MIN = 11;")], ["scénario c", "refuse une commande"]),
    "setpoint_too_low_accepted": ([("HAUT_MIN = 10;", "HAUT_MIN = 0;")], ["scénario c", "setpoint refused: high=5"]),
    "refusal_not_logged": ([(REFUSE9, 'ESP_LOGI(TAG, "ignorée");')], ["scénario c", "setpoint refused: high=95"]),
    "refusal_wrong_format": ([(REFUSE9, 'ESP_LOGW(TAG, "consigne refusée : %ld", valeur);')], ["scénario c", "setpoint refused: high=95", "refusée"]),
    "refusal_wrong_level": ([(REFUSE9, 'ESP_LOGE(TAG, "setpoint refused: high=%ld", valeur);')], ["scénario c", "niveau E"]),
    "garbage_logged_as_refusal": ([("    if (p == NULL) {\n        return;  // pas une commande : on ignore", '    if (p == NULL) {\n        ESP_LOGW(TAG, "setpoint refused: high=0");\n        return;')],
                                  ["scénario c", "refuse une commande"]),
    "relay_threshold_far_too_high": ([("lire_niveau() < haut;", "lire_niveau() < haut + 20;")], ["scénario a", "relais"]),
}


@pytest.mark.parametrize("edits,expected", ES9_MUTANTS.values(), ids=ES9_MUTANTS.keys())
def test_es9_tp_mutant(tmp_path, bwrap_ok, edits, expected):
    code, out = _es9_run(tmp_path, _es9_mutant(*edits))
    assert failed(code, out) and all(fragment in out for fragment in expected) and "relire" in out, out


# Variante valide, écrite autrement : consigne en u8, lecture de la commande avec sscanf, télémétrie par une tâche dédiée
# elle aussi abonnée au watchdog, relais aussi piloté dès la commande, session non propre avec réabonnement.
ES9_TASK_VARIANT_EDITS = [
    ("    for (int tour = 0;; tour++) {\n        ESP_ERROR_CHECK(esp_task_wdt_reset());\n        appliquer_consigne();\n        if (tour % TOURS_TELEMETRIE == 0) {\n            publier_telemetrie();\n        }\n        vTaskDelay(pdMS_TO_TICKS(PAS_MS));\n    }\n",
     '    xTaskCreate(tache_telemetrie, "telemetrie", 4096, NULL, 5, NULL);\n    for (;;) {\n        ESP_ERROR_CHECK(esp_task_wdt_reset());\n        appliquer_consigne();\n        vTaskDelay(pdMS_TO_TICKS(PAS_MS));\n    }\n'),
    ("// ---- Fourni : le Wi-Fi", "static void appliquer_consigne(void);\n\n// ---- Fourni : le Wi-Fi"),
    ("// Étape 6 :", 'static void tache_telemetrie(void *) {\n    ESP_ERROR_CHECK(esp_task_wdt_add(NULL));\n    for (;;) {\n        esp_task_wdt_reset();\n        publier_telemetrie();\n        vTaskDelay(pdMS_TO_TICKS(PAS_MS * TOURS_TELEMETRIE));\n    }\n}\n\n// Étape 6 :'),
    ("nvs_set_i32(h, NVS_CLE, valeur)", "nvs_set_u8(h, NVS_CLE, (uint8_t)valeur)"),
    ("    int32_t valeur = HAUT_DEFAUT;\n    esp_err_t err = nvs_get_i32(h, NVS_CLE, &valeur);", "    uint8_t valeur = HAUT_DEFAUT;\n    esp_err_t err = nvs_get_u8(h, NVS_CLE, &valeur);"),
    ("    char *fin;\n    long valeur = strtol(p, &fin, 10);\n    if (fin == p) {", "    int lu = 0;\n    long valeur;\n    if (sscanf(p, \"%d\", &lu) != 1) {"),
    ('    if (valeur < HAUT_MIN || valeur > HAUT_MAX) {\n        ESP_LOGW(TAG, "setpoint', '    valeur = lu;\n    if (valeur < HAUT_MIN || valeur > HAUT_MAX) {\n        ESP_LOGW(TAG, "setpoint'),
    ("    sauver_consigne((int)valeur);\n", "    sauver_consigne((int)valeur);\n    appliquer_consigne();\n"),
    ('    cfg.credentials.client_id = "pool-ctl";\n    client', '    cfg.credentials.client_id = "pool-ctl";\n    cfg.session.disable_clean_session = true;\n    client'),
]


def test_es9_tp_task_variant_passes(tmp_path, bwrap_ok):
    code, out = _es9_run(tmp_path, _es9_mutant(*ES9_TASK_VARIANT_EDITS))
    assert code == 0 and out.startswith("OK"), out


ES9_VARIANTS = {
    "log_mentioning_a_refused_publication": [('ESP_LOGI(TAG, "télémétrie non envoyée (hors connexion)");', 'ESP_LOGI(TAG, "publication refusée (hors connexion)");')],
    "log_mentioning_a_refused_publication_in_english": [('ESP_LOGI(TAG, "télémétrie non envoyée (hors connexion)");', 'ESP_LOGI(TAG, "publish refused (offline)");')],
    "idle_mask_of_one_core_only": [("cfg.idle_core_mask = (1 << 0) | (1 << 1);", "cfg.idle_core_mask = 1;")],
    "slow_down_to_100ms_loop": [("PAS_MS = 1000;", "PAS_MS = 100;"), ("TOURS_TELEMETRIE = 10;", "TOURS_TELEMETRIE = 100;")],
    "default_watchdog_configuration": [("    ESP_ERROR_CHECK(esp_task_wdt_reconfigure(&cfg));\n", "")],
    "watchdog_fed_through_a_helper": [(WDT_RESET, "        nourrir();\n"), ("static void configurer_watchdog(void) {", "static void nourrir(void) { ESP_ERROR_CHECK(esp_task_wdt_reset()); }\n\nstatic void configurer_watchdog(void) {")],
    "load_with_read_write_handle": [("nvs_open(NVS_ESPACE, NVS_READONLY, &h) != ESP_OK", "nvs_open(NVS_ESPACE, NVS_READWRITE, &h) != ESP_OK")],
    "two_writes_one_commit": [("    err = nvs_set_i32(h, NVS_CLE, valeur);", '    err = nvs_set_i32(h, NVS_CLE, valeur);\n    nvs_set_u8(h, "ecrit", 1);')],
    "subscription_with_wildcard_in_qos_0": [("TOPIC_COMMANDE, 1);\n        break;", '"home/devices/+/command", 0);\n        break;')],
    "telemetry_in_qos_1": [("json, 0, 0, 0)", "json, 0, 1, 0)")],
    "wake_up_slightly_early": [("vTaskDelay(pdMS_TO_TICKS(PAS_MS));\n    }", "vTaskDelay(pdMS_TO_TICKS(PAS_MS - 20));\n    }")],
    "reset_reason_not_logged": [('    ESP_LOGI(TAG, "démarrage, motif %d, consigne %d %%", (int)esp_reset_reason(), (int)haut);\n', "")],
    "relay_driven_only_after_wifi": [("    appliquer_consigne();\n    wifi_connecter();", "    wifi_connecter();\n    appliquer_consigne();")],
}


@pytest.mark.parametrize("edits", ES9_VARIANTS.values(), ids=ES9_VARIANTS.keys())
def test_es9_tp_legitimate_variant_passes(tmp_path, bwrap_ok, edits):
    code, out = _es9_run(tmp_path, _es9_mutant(*edits))
    assert code == 0 and out.startswith("OK"), out


def test_es9_check_sections_exist_in_lesson():
    """Chaque « relire : <section> » du contrôle renvoie à un titre réel de la leçon."""
    import re
    lesson = (ES9.parent / "es9.md").read_text(encoding="utf-8")
    titles = set(re.findall(r"^## (.+)$", lesson, re.M))
    source = (ESP / "checks" / "es9-tp.py").read_text(encoding="utf-8")
    constants = dict(re.findall(r'^(S_\w+) = "([^"]+)"$', source, re.M))
    cited = set(re.findall(r"relire : « ([^»{]+) »", source)) | set(constants.values())
    assert cited and cited <= titles, cited - titles


def test_es9_reconnection_instant_matches_the_simulator_constants():
    """« reconnexion vers 110,6 s » (leçon, énoncé, docstring) se déduit de mqtt.cpp : dérive détectée ici."""
    import re
    sim = (ESP / "sim" / "src" / "mqtt.cpp").read_text(encoding="utf-8")
    connect = int(re.search(r"kConnectMs = (\d+);", sim).group(1))
    retry = int(re.search(r"kDefaultReconnectMs = (\d+);", sim).group(1))
    import sys
    sys.modules.setdefault("esp_trace", _load("esp_trace_probe", ESP / "trace.py"))
    check = _load("es9_check_probe", ESP / "checks" / "es9-tp.py")
    down_from, down_to = check.DOWN["a"]
    begin = down_from + retry  # le courtier tombe : première tentative une période plus tard
    while begin < down_to:
        begin += connect + retry  # tentative échouée, la suivante vient après la période
    connected = begin + connect
    assert connected == 110_600, connected
    for path in (ES9.parent / "es9.md", ES9 / "tp.json", ESP / "checks" / "es9-tp.py"):
        assert "110,6 s" in path.read_text(encoding="utf-8"), path


# ---- Task 19: the test certificate is made at run time by the driver ----

TLS_CLIENT = '#include "esp_log.h"\n#include "mqtt_client.h"\n#include "freertos/FreeRTOS.h"\n#include "freertos/task.h"\n' + r'''
extern "C" const char _binary_server_cert_pem_start[];
extern "C" void app_main(void) {
    esp_mqtt_client_config_t cfg = {};
    cfg.broker.address.uri = "mqtts://broker.local";
    cfg.broker.verification.certificate = %s;
    esp_mqtt_client_handle_t c = esp_mqtt_client_init(&cfg);
    esp_mqtt_client_start(c);
    vTaskDelay(pdMS_TO_TICKS(1500));
}
'''


def test_generated_certificate_reaches_the_simulator_and_the_program(tmp_path, bwrap_ok):
    code, out = run(tmp_path, TLS_CLIENT % "_binary_server_cert_pem_start", tp="_selftest_tls")
    assert code == 0 and out.startswith("OK"), out
    code, out = run(tmp_path, TLS_CLIENT % "NULL", tp="_selftest_tls")  # no verification option: refused at setup
    assert failed(code, out) and "poignée de main TLS" in out, out
    code, out = run(tmp_path, TLS_CLIENT % '"-----BEGIN CERTIFICATE-----\\nAAAA\\n-----END CERTIFICATE-----\\n"', tp="_selftest_tls")
    assert failed(code, out) and "poignée de main TLS" in out, out  # another certificate than the broker's


def test_materialize_makes_a_fresh_public_certificate_only():
    driver = _load("esp_check_materialize", ESP / "esp_check.py")
    base = {"tls": {"server_cert": "@generate", "server_cn": "mqtt.local", "public_ca": False}, "mqtt": {}}
    a, b = driver.materialize(base), driver.materialize(base)
    assert base["tls"]["server_cert"] == "@generate"  # the check module's own dict is left alone
    for s in (a, b):
        pem = s["tls"]["server_cert"]
        assert pem.startswith("-----BEGIN CERTIFICATE-----") and "PRIVATE" not in pem and s["tls"]["server_cn"] == "mqtt.local"
        assert s["mqtt"] == {} and s["tls"]["public_ca"] is False
    assert a["tls"]["server_cert"] != b["tls"]["server_cert"]  # fresh at each run
    assert driver.materialize({"tls": {"server_cert": "x"}}) == {"tls": {"server_cert": "x"}}
    assert driver.materialize({}) == {}
    assert driver.materialize({"tls": {"server_cert": "@generate"}})["tls"]["server_cn"] == "broker.local"


def test_no_certificate_or_key_is_stored_in_content():
    stored = [p for p in ESP.rglob("*") if p.is_file() and p.suffix in {".pem", ".key", ".crt", ".cer", ".der", ".p12"}]
    assert not stored
    for p in ESP.rglob("*"):
        if p.is_file() and "__pycache__" not in p.parts and p.suffix in {".py", ".json", ".h", ".cpp", ".md"}:
            assert "PRIVATE KEY-----\n" not in p.read_text(encoding="utf-8", errors="replace"), p


def test_make_certificate_refuses_a_name_that_is_not_a_host_name():
    driver = _load("esp_check_cn", ESP / "esp_check.py")
    for cn in ("a/O=b", "a+b", "", "x" * 65, "a\nb", "a b"):
        with pytest.raises(driver.CheckError):
            driver.make_certificate(cn)
    assert driver.make_certificate("broker-1.local").startswith("-----BEGIN CERTIFICATE-----")


def test_missing_openssl_is_an_internal_error_not_a_traceback(monkeypatch):
    driver = _load("esp_check_noopenssl", ESP / "esp_check.py")
    monkeypatch.setattr(driver.shutil, "which", lambda name: None)
    with pytest.raises(driver.CheckError, match="openssl") as e:
        driver.materialize({"tls": {"server_cert": "@generate"}})
    assert e.value.hint == ""  # not the learner's fault: no lesson to re-read


def test_a_tls_section_without_server_cert_is_refused():
    driver = _load("esp_check_guard", ESP / "esp_check.py")
    with pytest.raises(driver.CheckError, match="server_cert"):
        driver.materialize({"tls": {"handshake_fail": []}})


# ---- TP es10 (MQTT sur TLS : certificat vérifié, identifiants en NVS, attente croissante, relais en état sûr) ----

ES10 = Path(__file__).resolve().parents[2] / "content" / "modules" / "esp4" / "lessons" / "es10.tp"


def _es10_reference() -> str:
    text = (ES10 / "solution.sh").read_text(encoding="utf-8")
    return text.split("<<'EOF'\n", 1)[1].rsplit("\nEOF", 1)[0] + "\n"


def _es10_mutant(*edits: tuple[str, str]) -> str:
    src = _es10_reference()
    for old, new in edits:
        assert old in src, old
        src = src.replace(old, new)
    return src


def _es10_run(tmp_path, src: str) -> tuple[int, str]:
    return run(tmp_path, src, tp="es10-tp")


def test_es10_tp_reference_passes(tmp_path, bwrap_ok):
    code, out = _es10_run(tmp_path, _es10_reference())
    assert code == 0 and out.startswith("OK"), out


def test_es10_tp_seed_refused(tmp_path, bwrap_ok):
    code, out = _es10_run(tmp_path, (ES10 / "seed" / "main.cpp").read_text(encoding="utf-8"))
    assert failed(code, out) and "aucun événement MQTT" in out and "relire" in out, out


CERT_LINE = "    cfg.broker.verification.certificate = _binary_server_cert_pem_start;\n"
USER_LINE = "    cfg.credentials.username = utilisateur;\n"
PASS_LINE = "    cfg.credentials.authentication.password = mot_de_passe;\n"
RELAY_OFF = '    if (relais) {\n        regler_relais(false);\n        ESP_LOGW(TAG, "liaison perdue : relais éteint (état sûr)");\n    }\n'
RESET_FAILS = "        echecs = 0;\n"
WAIT_LINE = "    vTaskDelay(pdMS_TO_TICKS(attente));\n"
SUBSCRIBE10 = "        esp_mqtt_client_subscribe_single(ev->client, TOPIC_COMMANDE, 1);\n"
ERR_FORMAT = '"échec TLS : esp_err 0x%x, pile TLS 0x%x, drapeaux du certificat 0x%x"'
RECONNECT = ('    esp_err_t err = esp_mqtt_client_reconnect(client);\n    if (err != ESP_OK) {\n'
             '        ESP_LOGE(TAG, "esp_mqtt_client_reconnect : %s", esp_err_to_name(err));\n    }\n')
START10 = "    ESP_ERROR_CHECK(esp_mqtt_client_start(client));\n"

# nom -> (remplacements, fragments de message attendus)
ES10_MUTANTS = {
    # la vérification
    "skip_common_name_check": ([(CERT_LINE, CERT_LINE + "    cfg.broker.verification.skip_cert_common_name_check = true;\n")],
                               ["skip_cert_common_name_check", "homme du milieu"]),
    "skip_common_name_check_through_a_variable": ([(CERT_LINE, CERT_LINE + "    bool vite = true;\n    cfg.broker.verification.skip_cert_common_name_check = vite;\n")],
                                                  ["skip_cert_common_name_check"]),
    "certificate_not_provided": ([(CERT_LINE, "")], ["scénario a", "n'a jamais pu se connecter", "fatal error"]),
    "certificate_empty_text": ([(CERT_LINE, '    cfg.broker.verification.certificate = "";\n')], ["scénario a", "n'a jamais pu se connecter", "pas un PEM valide"]),
    "certificate_text_of_ones_own": ([(CERT_LINE, '    cfg.broker.verification.certificate = "-----BEGIN CERTIFICATE-----\\nAAAA\\n-----END CERTIFICATE-----\\n";\n')],
                                     ["scénario a", "n'a jamais pu se connecter"]),
    "public_bundle_instead_of_the_brokers_certificate": ([(CERT_LINE, "    cfg.broker.verification.crt_bundle_attach = esp_crt_bundle_attach;\n"),
                                                          ('#include "sdkconfig.h"', '#include "sdkconfig.h"\n#include "esp_crt_bundle.h"')],
                                                         ["scénario a", "n'a jamais pu se connecter", "paquet de certificats public"]),
    "tls_insecure_option_named_in_code": ([(CERT_LINE, CERT_LINE + "#ifdef CONFIG_ESP_TLS_INSECURE\n    cfg.broker.verification.certificate = NULL;\n#endif\n")],
                                          ["CONFIG_ESP_TLS_INSECURE"]),
    "plain_mqtt_uri": ([('"mqtts://broker.local:8883"', '"mqtt://broker.local:1883"')], ["scénario a", "aucune poignée de main TLS", "mqtts://"]),
    # les identifiants
    "credentials_written_in_the_code": ([(USER_LINE, '    cfg.credentials.username = "piscine-ctl-07";\n'),
                                         (PASS_LINE, '    cfg.credentials.authentication.password = "Pz9-ke4N-77qL";\n')],
                                        ["en clair", "NVS"]),
    "password_literal_in_the_code": ([(PASS_LINE, '    cfg.credentials.authentication.password = "hunter2hunter";\n')],
                                     ["cfg.credentials.authentication.password", "valeur écrite dans le programme"]),
    "username_literal_in_the_code": ([(USER_LINE, '    cfg.credentials.username = "admin";\n')],
                                     ["cfg.credentials.username", "valeur écrite dans le programme"]),
    "credentials_in_a_designated_initializer": ([("    esp_mqtt_client_config_t cfg = {};\n", '    esp_mqtt_client_config_t cfg = {.credentials = {.username = "admin", .authentication = {.password = "hunter2hunter"}}};\n')],
                                                ["valeur écrite dans le programme"]),
    "credentials_in_the_uri": ([('"mqtts://broker.local:8883"', '"mqtts://admin:hunter2@broker.local:8883"')], ["URI du courtier", "NVS"]),
    "credentials_copied_from_a_literal": ([("    return true;\n}\n\n// Étape 2", '    strcpy(mot_de_passe, "motdepasse-maison");\n    return true;\n}\n\n// Étape 2')],
                                          ["mot_de_passe", "valeur écrite dans le programme"]),
    "credentials_not_given_to_the_client": ([(USER_LINE, ""), (PASS_LINE, "")], ["scénario a", "ne transmet pas d'identifiants"]),
    "credentials_never_loaded": ([("    if (charger_identifiants()) {", "    if (true) {")], ["scénario a", "ne transmet pas d'identifiants"]),
    # la panne
    "abandons_after_a_few_failures": ([("    int n = ++echecs;\n", "    int n = ++echecs;\n    if (n > 4) {\n        return;\n    }\n")],
                                      ["scénario b", "ne s'est pas reconnecté"]),
    "reconnect_never_called": ([(RECONNECT, "")], ["scénario b", "aucune tentative de poignée de main"]),
    "tight_reconnect_loop": ([(WAIT_LINE, "")], ["scénario b", "première attente", "boucle serrée"]),
    "relay_left_on_during_the_outage": ([(RELAY_OFF, "")], ["scénario b", "relais est encore allumé après la perte"]),
    "relay_cut_only_after_the_third_failure": ([(RELAY_OFF, RELAY_OFF.replace("if (relais)", "if (relais && echecs >= 3)"))],
                                               ["scénario b", "relais est encore allumé après la perte"]),
    "fails_counter_not_reset_after_a_connection": ([(RESET_FAILS, "")], ["scénario b", "première attente", "repartir de 1 s"]),
    "constant_wait": ([("    int attente = attente_ms(n);\n", "    int attente = 2000;\n")], ["scénario b", "au moins 1,5 fois"]),
    "wait_without_a_cap": ([("ms < 8000", "ms < 800000")], ["scénario b", "dépasse 35 s"]),
    "wait_starting_too_high": ([("    int ms = 1000;\n", "    int ms = 5000;\n")], ["scénario b", "première attente"]),
    "wait_shrinks_back": ([("    int attente = attente_ms(n);\n", "    int attente = n == 1 ? 2000 : n == 2 ? 1000 : 8000;\n")], ["scénario b", "raccourcit"]),
    "wait_never_reaches_8s": ([("ms < 8000", "ms < 4000")], ["scénario b", "n'a pas atteint 8 s"]),
    "only_the_librarys_fixed_10_s_retry": ([("    cfg.network.disable_auto_reconnect = true;  // c'est le programme qui décide quand réessayer (étape 4)\n", ""), (RECONNECT, "")],
                                           ["scénario b", "première attente"]),
    "error_not_logged": ([("        ESP_LOGW(TAG, " + ERR_FORMAT, "        (void)(" + ERR_FORMAT)], ["scénario c", "journalisé avec son code"]),
    "not_subscribed": ([(SUBSCRIBE10, "")], ["scénario a", "aucun abonnement"]),
    "subscribed_once_at_start": ([(SUBSCRIBE10, ""), (START10, START10 + "    esp_mqtt_client_subscribe_single(client, TOPIC_COMMANDE, 1);\n")],
                                 ["abonnement"]),
    "relay_switched_on_when_the_link_drops": ([("    case MQTT_EVENT_DISCONNECTED:\n", "    case MQTT_EVENT_DISCONNECTED:\n        regler_relais(true);\n")],
                                              ["relais"]),
    "telemetry_never_published": ([("            publier_telemetrie();\n", "")], ["scénario a", "aucun message sur"]),
    "telemetry_reports_a_wrong_relay": ([('relais ? "true" : "false"', '"false"')], ["scénario a", "ce n'est pas l'état réel du relais"]),
}


@pytest.mark.parametrize("edits,expected", ES10_MUTANTS.values(), ids=ES10_MUTANTS.keys())
def test_es10_tp_mutant(tmp_path, bwrap_ok, edits, expected):
    code, out = _es10_run(tmp_path, _es10_mutant(*edits))
    assert failed(code, out) and all(fragment in out for fragment in expected) and "relire" in out, out


# Variantes valides, écrites autrement.
ES10_VARIANTS = {
    "common_name_check_explicitly_enabled": [(CERT_LINE, CERT_LINE + "    cfg.broker.verification.skip_cert_common_name_check = false;\n")],
    "bundle_function_named_in_a_comment": [(CERT_LINE, CERT_LINE + "    // pas de crt_bundle_attach : le courtier est privé, il n'est pas dans le paquet\n")],
    "credentials_read_with_the_length_protocol": [
        ("    size_t taille_user = sizeof(utilisateur);\n    size_t taille_mdp = sizeof(mot_de_passe);\n",
         "    size_t taille_user = 0;\n    size_t taille_mdp = 0;\n    if (nvs_get_str(h, NVS_CLE_USER, NULL, &taille_user) != ESP_OK || taille_user > sizeof(utilisateur) ||\n"
         "        nvs_get_str(h, NVS_CLE_MDP, NULL, &taille_mdp) != ESP_OK || taille_mdp > sizeof(mot_de_passe)) {\n"
         '        nvs_close(h);\n        ESP_LOGE(TAG, "identifiants absents ou trop longs");\n        return false;\n    }\n')],
    "nvs_key_names_in_secret_looking_constants": [('static const char *NVS_CLE_USER = "user";', 'static const char *K_USER = "user";\nstatic const char *NVS_CLE_USER = K_USER;'),
                                                  ('static const char *NVS_CLE_MDP = "pass";', 'static const char *K_PASS = "pass";\nstatic const char *NVS_CLE_MDP = K_PASS;')],
    "common_name_check_disabled_with_a_cast_to_false": [(CERT_LINE, CERT_LINE + "    cfg.broker.verification.skip_cert_common_name_check = (bool)false;\n")],
    "variables_named_login_message_and_password_hint": [(CERT_LINE, CERT_LINE + '    const char *login_msg = "connexion sécurisée";\n    const char *password_hint = "lu en NVS";\n    (void)login_msg;\n    (void)password_hint;\n')],
    "doubling_computed_by_a_shift": [("    int attente = attente_ms(n);\n", "    int attente = 1000 << (n < 4 ? n - 1 : 3);\n")],
    "first_wait_of_2_seconds": [("    int attente = attente_ms(n);\n", "    int attente = 2000 << (n < 3 ? n - 1 : 2);\n")],
    "loss_polled_instead_of_waited": [("        EventBits_t bits = xEventGroupWaitBits(groupe_liaison, BIT_PERDU, pdTRUE, pdFALSE, pdMS_TO_TICKS(PAS_MS));\n",
                                       "        vTaskDelay(pdMS_TO_TICKS(PAS_MS));\n        EventBits_t bits = xEventGroupClearBits(groupe_liaison, BIT_PERDU);\n")],
    "library_retry_left_on_with_the_programs_own_waits": [("    cfg.network.disable_auto_reconnect = true;  // c'est le programme qui décide quand réessayer (étape 4)\n", "")],
    "english_log_with_decimal_codes": [(ERR_FORMAT, '"handshake failed: err=%u stack=%u flags=%u"')],
    "relay_cut_in_the_handler_too": [("    case MQTT_EVENT_DISCONNECTED:\n", "    case MQTT_EVENT_DISCONNECTED:\n        regler_relais(false);\n")],
    "comment_and_string_naming_the_bypass_option": [(CERT_LINE, CERT_LINE + "    // skip_cert_common_name_check = true : NON, voir la leçon\n    const char *note = \"skip_cert_common_name_check\";\n    (void)note;\n")],
}


@pytest.mark.parametrize("edits", ES10_VARIANTS.values(), ids=ES10_VARIANTS.keys())
def test_es10_tp_legitimate_variant_passes(tmp_path, bwrap_ok, edits):
    code, out = _es10_run(tmp_path, _es10_mutant(*edits))
    assert code == 0 and out.startswith("OK"), out


def _es10_check_module():
    import sys
    sys.modules.setdefault("esp_trace", _load("esp_trace_probe", ESP / "trace.py"))
    return _load("es10_check_probe", ESP / "checks" / "es10-tp.py")


@pytest.mark.parametrize("src", [
    'static const char *NVS_CLE_MDP = "pass";',
    'static const char *K_PASS = "pass";\nconst char *K_USER = "user";',
    'if (xTaskCreate(f, "t", 4096, NULL, 5, NULL) != pdPASS) { }',
    'cfg.broker.verification.skip_cert_common_name_check = false;',
    'cfg.broker.verification.skip_cert_common_name_check = 0;',
    '// skip_cert_common_name_check = true est interdit\nint x = 1;',
    '/* skip_cert_common_name_check = true */ int y = 2;',
    'ESP_LOGI(TAG, "skip_cert_common_name_check = true ? non");',
    'static char mot_de_passe[64];\nstatic char utilisateur[32];',
    'nvs_get_str(h, "pass", mot_de_passe, &t);',
    'const char *espace_mdp = "mqtt";',
    'cfg.credentials.client_id = "pool-ctl";',
    'ESP_LOGE(TAG, "mot de passe illisible");',
    'int tokens = 3;',
    'char *p = strstr(msg, "password");',
    'cfg.broker.verification.skip_cert_common_name_check = (bool)false;',
    'const char *login_msg = "connexion";\nconst char *password_hint = "lu en NVS";\nconst char *secret_label = "x";',
])
def test_es10_source_scan_does_not_refuse_legitimate_idioms(src):
    _es10_check_module()._check_source(src)


@pytest.mark.parametrize("src", [
    "cfg.broker.verification.skip_cert_common_name_check = true;",
    "cfg.broker.verification.skip_cert_common_name_check=1;",
    "cfg.broker.verification.skip_cert_common_name_check = vite;",
    "cfg.broker.verification.skip_cert_common_name_check = !false;",
    "#define SKIP skip_cert_common_name_check",
    "#ifdef CONFIG_ESP_TLS_SKIP_SERVER_CERT_VERIFY\n#endif",
    "cfg.skip_server_cert_verify = true;",
    'esp_mqtt_client_config_t c = {.credentials = {.username = "admin"}};',
    'esp_mqtt_client_config_t c = {.credentials = {.authentication = {.password = "hunter2"}}};',
    "cfg.skip_common_name = true;",
    'const char *mdp = "abc";',
    'char *password = "abc";',
    'cfg.credentials.authentication.password = "x1";',
    'strcpy(utilisateur, "admin");',
    'const char *uri = "mqtts://u:p@h";',
    'ESP_LOGI(TAG, "x"); /* c */ const char *secret = "s";',
])
def test_es10_source_scan_refuses_bypasses_and_clear_text_credentials(src):
    import sys
    module = _es10_check_module()
    with pytest.raises(sys.modules["esp_trace"].CheckError):
        module._check_source(src)


def test_es10_check_sections_exist_in_lesson():
    """Chaque « relire : <section> » du contrôle renvoie à un titre réel de la leçon."""
    import re
    lesson = (ES10.parent / "es10.md").read_text(encoding="utf-8")
    titles = set(re.findall(r"^## (.+)$", lesson, re.M))
    source = (ESP / "checks" / "es10-tp.py").read_text(encoding="utf-8")
    constants = dict(re.findall(r'^(S_\w+) = "([^"]+)"$', source, re.M))
    cited = set(re.findall(r"relire : « ([^»{]+) »", source)) | set(constants.values())
    assert cited and cited <= titles, cited - titles


def test_es10_test_credentials_live_only_in_the_check_module():
    """Le contrôle cherche les identifiants d'essai dans le programme de l'apprenant : ils ne doivent figurer dans aucun fichier du TP."""
    check = _es10_check_module()
    for path in (ES10 / "seed" / "main.cpp", ES10 / "solution.sh", ES10 / "tp.json", ES10.parent / "es10.md", ES10.parent / "es10.qcm.json"):
        text = path.read_text(encoding="utf-8")
        assert check.USER not in text and check.PASS not in text, path


# ---- TP es11 (mises à jour OTA : version strictement plus récente, https vérifié, relais sûr, redémarrage après succès) ----

ES11 = Path(__file__).resolve().parents[2] / "content" / "modules" / "esp4" / "lessons" / "es11.tp"


def _es11_reference() -> str:
    text = (ES11 / "solution.sh").read_text(encoding="utf-8")
    return text.split("<<'EOF'\n", 1)[1].rsplit("\nEOF", 1)[0] + "\n"


def _es11_mutant(*edits: tuple[str, str]) -> str:
    src = _es11_reference()
    for old, new in edits:
        assert old in src, old
        src = src.replace(old, new)
    return src


def _es11_run(tmp_path, src: str) -> tuple[int, str]:
    return run(tmp_path, src, tp="es11-tp")


def test_es11_tp_reference_passes(tmp_path, bwrap_ok):
    code, out = _es11_run(tmp_path, _es11_reference())
    assert code == 0 and out.startswith("OK"), out


def test_es11_tp_seed_refused(tmp_path, bwrap_ok):
    code, out = _es11_run(tmp_path, (ES11 / "seed" / "main.cpp").read_text(encoding="utf-8"))
    assert failed(code, out) and "scénario a" in out and "aucun téléchargement commencé" in out and "relire" in out, out


VPR_OLD = _es11_reference()[_es11_reference().index("static bool version_plus_recente"):_es11_reference().index("// Fourni (TP 10) : lire")]
RELAY_SAFE = "    regler_relais(false);  // état sûr pendant toute la mise à jour : il ne se rallume que sur une nouvelle commande\n"
FAIL_LOG = '        ESP_LOGE(TAG, "mise à jour échouée : %s", esp_err_to_name(err));\n'
OTA_CALL = "    esp_err_t err = esp_https_ota(&cfg);\n"
CERT_OTA = "    http.cert_pem = _binary_server_cert_pem_start;  // le certificat du serveur : la vérification complète, comme pour MQTT\n"
HTTPS_TEST = '    if (strncmp(url, "https://", 8) != 0) {\n'
STEP2 = "        if (url_dans_commande(ev->data, ev->data_len)) {  // étape 2 : ne rien télécharger ici, lever le drapeau\n            xEventGroupSetBits(groupe_liaison, BIT_OTA);\n        }\n"
RESTART = "    esp_restart();\n}\n"

# nom -> (remplacements, fragments de message attendus)
ES11_MUTANTS = {
    "same_version_accepted": ([("    return false;  // identique : pas de mise à jour\n", "    return true;\n")],
                              ["scénario c", "n'est pas strictement plus récente"]),
    "older_version_accepted": ([("return n[i] > c[i];", "return n[i] != c[i];")], ["scénario e", "n'est pas strictement plus récente"]),
    "always_newer": ([(VPR_OLD, "static bool version_plus_recente(const char *nouvelle, const char *courante) {\n    (void)nouvelle;\n    (void)courante;\n    return true;\n}\n\n")],
                     ["scénario c", "n'est pas strictement plus récente"]),
    "versions_compared_as_text": ([(VPR_OLD, "static bool version_plus_recente(const char *nouvelle, const char *courante) {\n    return strcmp(nouvelle, courante) > 0;\n}\n\n")],
                                  ["scénario a", "aucun téléchargement commencé", "comparaison des nombres"]),
    "restart_despite_the_failure": ([(FAIL_LOG + "        return;\n", FAIL_LOG)], ["scénario b", "malgré l'échec"]),
    "failure_not_logged": ([(FAIL_LOG, "        (void)err;\n")], ["scénario b", "n'est pas journalisé", "ESP_ERR_OTA_VALIDATE_FAILED"]),
    "failure_logged_without_the_code": ([(FAIL_LOG, '        ESP_LOGE(TAG, "mise à jour échouée");\n')], ["scénario b", "n'est pas journalisé"]),
    "failure_logged_at_info_level": ([(FAIL_LOG, FAIL_LOG.replace("ESP_LOGE", "ESP_LOGI"))], ["scénario b", "n'est pas journalisé"]),
    "esp_error_check_on_the_update": ([(OTA_CALL, "    ESP_ERROR_CHECK(esp_https_ota(&cfg));\n    esp_err_t err = ESP_OK;\n")], ["ESP_ERROR_CHECK", "esp_https_ota"]),
    "common_name_not_verified": ([(CERT_OTA, CERT_OTA + "    http.skip_cert_common_name_check = true;\n")], ["skip_cert_common_name_check"]),
    "certificate_not_provided": ([(CERT_OTA, "")], ["scénario a", "aucun téléchargement commencé", "ESP_ERR_INVALID_ARG"]),
    "public_bundle_instead_of_the_certificate": ([(CERT_OTA, "    http.crt_bundle_attach = esp_crt_bundle_attach;\n"),
                                                  ('#include "sdkconfig.h"', '#include "sdkconfig.h"\n#include "esp_crt_bundle.h"')],
                                                 ["scénario a", "paquet de certificats public"]),
    "cleartext_http_accepted": ([(HTTPS_TEST, "    if (false) {\n")], ["scénario f", "http://", "ne refuse pas ce schéma"]),
    "relay_left_on_during_the_update": ([(RELAY_SAFE, "")], ["scénario a", "relais n'est pas éteint pendant la mise à jour"]),
    "relay_switched_on_again_after_the_failure": ([(FAIL_LOG + "        return;\n", FAIL_LOG + "        regler_relais(true);\n        return;\n")],
                                                  ["scénario b", "relais n'est pas éteint pendant la mise à jour"]),
    "relay_cut_before_the_checks": ([(RELAY_SAFE, ""), ("static void mettre_a_jour(const char *url) {\n", "static void mettre_a_jour(const char *url) {\n    regler_relais(false);\n")],
                                    ["scénario c", "une demande refusée ne touche pas à la pompe"]),
    "relay_command_obeyed_during_the_update": ([("    if (voulu && ota_demandee) {\n", "    if (false) {\n")],
                                               ["scénario a", "relais n'est pas éteint pendant la mise à jour"]),
    "patch_number_ignored": ([("    for (int i = 0; i < 3; i++) {\n        if (n[i] < 0", "    for (int i = 0; i < 2; i++) {\n        if (n[i] < 0")],
                             ["scénario d", "aucun téléchargement commencé"]),
    "every_number_at_least_as_big": ([(VPR_OLD, "static bool version_plus_recente(const char *nouvelle, const char *courante) {\n    int n[3], c[3];\n    char reste;\n"
                                      '    if (sscanf(nouvelle, "%d.%d.%d%c", &n[0], &n[1], &n[2], &reste) != 3 || sscanf(courante, "%d.%d.%d%c", &c[0], &c[1], &c[2], &reste) != 3) {\n'
                                      "        return false;\n    }\n    for (int i = 0; i < 3; i++) {\n        if (n[i] < c[i]) {\n            return false;\n        }\n    }\n"
                                      "    return n[0] != c[0] || n[1] != c[1] || n[2] != c[2];\n}\n\n")],
                                     ["scénario b", "aucun téléchargement commencé"]),
    "version_form_not_checked": ([('sscanf(nouvelle, "%d.%d.%d%c", &n[0], &n[1], &n[2], &reste) != 3', 'sscanf(nouvelle, "%d.%d.%d", &n[0], &n[1], &n[2]) != 3')],
                                 ["scénario g", "forme x.y.z"]),
    "download_made_in_the_mqtt_handler": ([("// Fourni (TP 10) : le gestionnaire des événements MQTT (tâche mqtt_task, il ne bloque jamais).\n",
                                            "static void mettre_a_jour(const char *url);\n// Fourni (TP 10) : le gestionnaire des événements MQTT (tâche mqtt_task, il ne bloque jamais).\n"),
                                           (STEP2, "        if (url_dans_commande(ev->data, ev->data_len)) {\n            mettre_a_jour(url_ota);\n            ota_demandee = false;\n        }\n")],
                                          ["scénario b", "gestionnaire MQTT"]),
    "no_restart_after_success": ([(RESTART, "}\n")], ["scénario a", "0 redémarrage"]),
    "restart_too_late": ([(RESTART, "    vTaskDelay(pdMS_TO_TICKS(15000));\n" + RESTART)], ["scénario a", "au plus 10 s accordées"]),
    "handler_never_asks_for_the_update": ([(STEP2, "")], ["scénario a", "aucun téléchargement commencé"]),
    "a_second_attempt_after_the_failure": ([(OTA_CALL, OTA_CALL + "    if (err != ESP_OK) {\n        err = esp_https_ota(&cfg);\n    }\n")], ["scénario b", "2 téléchargements"]),
    "refusal_not_logged": ([('        ESP_LOGW(TAG, "mise à jour refusée : version proposée %s, version courante %s", version, courante);\n', "")],
                           ["scénario c", "le refus n'est pas journalisé"]),
    "https_refusal_not_logged": ([('        ESP_LOGW(TAG, "mise à jour refusée : %s n\'est pas une adresse https://", url);\n', "")],
                                 ["scénario f", "le refus n'est pas journalisé"]),
    "update_started_from_the_wrong_url": ([("    http.url = url;\n", '    http.url = "https://broker.local:8443/firmware/pool-ctl-1.10.0.bin";\n')],
                                           ["scénario b", "au lieu de l'adresse de la commande"]),
}


@pytest.mark.parametrize("edits,expected", ES11_MUTANTS.values(), ids=ES11_MUTANTS.keys())
def test_es11_tp_mutant(tmp_path, bwrap_ok, edits, expected):
    code, out = _es11_run(tmp_path, _es11_mutant(*edits))
    assert failed(code, out) and all(fragment in out for fragment in expected) and "relire" in out, out


STRTOL_VERSION = '''static bool version_plus_recente(const char *nouvelle, const char *courante) {
    long v[2][3];
    const char *texte[2] = {nouvelle, courante};
    for (int k = 0; k < 2; k++) {
        const char *p = texte[k];
        for (int i = 0; i < 3; i++) {
            char *suite;
            if (*p < '0' || *p > '9') {
                return false;
            }
            v[k][i] = strtol(p, &suite, 10);
            p = suite;
            if (i < 2) {
                if (*p != '.') {
                    return false;
                }
                p++;
            }
        }
        if (*p != '\\0') {
            return false;
        }
    }
    for (int i = 0; i < 3; i++) {
        if (v[0][i] != v[1][i]) {
            return v[0][i] > v[1][i];
        }
    }
    return false;
}

'''
CMP_VERSION = '''static int comparer_versions(const char *a, const char *b) {
    int x[3], y[3];
    char z;
    if (sscanf(a, "%d.%d.%d%c", &x[0], &x[1], &x[2], &z) != 3 || sscanf(b, "%d.%d.%d%c", &y[0], &y[1], &y[2], &z) != 3) {
        return -1;
    }
    long ka = (long)x[0] << 40 | (long)x[1] << 20 | x[2];
    long kb = (long)y[0] << 40 | (long)y[1] << 20 | y[2];
    return ka > kb ? 1 : ka < kb ? -1 : 0;
}

static bool version_plus_recente(const char *nouvelle, const char *courante) {
    return comparer_versions(nouvelle, courante) > 0;
}

'''

# Variantes valides, écrites autrement.
ES11_VARIANTS = {
    "version_parsed_with_strtol": [(VPR_OLD, STRTOL_VERSION)],
    "version_packed_in_one_number": [(VPR_OLD, CMP_VERSION)],
    "refusals_logged_in_english": [('"mise à jour refusée : version proposée %s, version courante %s"', '"update refused: new %s, current %s"')],
    "restart_after_a_short_pause": [(RESTART, "    vTaskDelay(pdMS_TO_TICKS(1000));\n" + RESTART)],
    "http_client_with_keep_alive_and_timeout": [(CERT_OTA, CERT_OTA + "    http.keep_alive_enable = true;\n    http.timeout_ms = 10000;\n")],
    "common_name_check_explicitly_enabled": [(CERT_OTA, CERT_OTA + "    http.skip_cert_common_name_check = false;\n")],
    "https_tested_with_strstr": [(HTTPS_TEST, '    if (strstr(url, "https://") != url) {\n')],
    "relay_cut_through_the_pin": [(RELAY_SAFE, "    gpio_set_level(RELAIS_GPIO, 0);\n    relais = false;\n")],
    "failure_logged_with_the_numeric_code_too": [(FAIL_LOG, '        ESP_LOGE(TAG, "mise à jour échouée : %s (0x%x)", esp_err_to_name(err), (unsigned)err);\n')],
    "bypass_option_named_in_a_comment_and_a_string": [(CERT_OTA, CERT_OTA + '    // pas de skip_cert_common_name_check = true : voir la leçon\n    const char *note = "ESP_ERROR_CHECK(esp_https_ota(&cfg))";\n    (void)note;\n')],
}


@pytest.mark.parametrize("edits", ES11_VARIANTS.values(), ids=ES11_VARIANTS.keys())
def test_es11_tp_legitimate_variant_passes(tmp_path, bwrap_ok, edits):
    code, out = _es11_run(tmp_path, _es11_mutant(*edits))
    assert code == 0 and out.startswith("OK"), out


def _es11_check_module():
    import sys
    sys.modules.setdefault("esp_trace", _load("esp_trace_probe", ESP / "trace.py"))
    return _load("es11_check_probe", ESP / "checks" / "es11-tp.py")


@pytest.mark.parametrize("src", [
    "esp_err_t err = esp_https_ota(&cfg);",
    "cfg.skip_cert_common_name_check = false;",
    "// ESP_ERROR_CHECK(esp_https_ota(&cfg)) est interdit\nint x = 1;",
    'ESP_LOGI(TAG, "skip_cert_common_name_check = true ? non");',
    "ESP_ERROR_CHECK(esp_restart_prepare());\nESP_ERROR_CHECK(esp_https_ota_helper(&cfg));",
])
def test_es11_source_scan_does_not_refuse_legitimate_idioms(src):
    _es11_check_module()._check_source(src)


@pytest.mark.parametrize("src", [
    "ESP_ERROR_CHECK(esp_https_ota(&cfg));",
    "ESP_ERROR_CHECK( esp_https_ota (&cfg) );",
    "http.skip_cert_common_name_check = true;",
    "http.skip_cert_common_name_check = vite;",
    "#ifdef CONFIG_ESP_TLS_INSECURE\n#endif",
    "cfg.skip_server_cert_verify = true;",
])
def test_es11_source_scan_refuses_bypasses_and_checked_updates(src):
    import sys
    module = _es11_check_module()
    with pytest.raises(sys.modules["esp_trace"].CheckError):
        module._check_source(src)


def test_es11_check_sections_exist_in_lesson():
    """Chaque « relire : <section> » du contrôle renvoie à un titre réel de la leçon."""
    import re
    lesson = (ES11.parent / "es11.md").read_text(encoding="utf-8")
    titles = set(re.findall(r"^## (.+)$", lesson, re.M))
    source = (ESP / "checks" / "es11-tp.py").read_text(encoding="utf-8")
    constants = dict(re.findall(r'^(S_\w+) = "([^"]+)"$', source, re.M))
    cited = set(re.findall(r"relire : « ([^»{]+) »", source)) | set(constants.values())
    assert cited and cited <= titles, cited - titles


# ---- TP es12 (retour arrière et état sûr : relais d'abord, auto-test, validation ou annulation, coupure de courant) ----

ES12 = Path(__file__).resolve().parents[2] / "content" / "modules" / "esp4" / "lessons" / "es12.tp"


def _es12_reference() -> str:
    text = (ES12 / "solution.sh").read_text(encoding="utf-8")
    return text.split("<<'EOF'\n", 1)[1].rsplit("\nEOF", 1)[0] + "\n"


def _es12_mutant(*edits: tuple[str, str]) -> str:
    src = _es12_reference()
    for old, new in edits:
        assert old in src, old
        src = src.replace(old, new)
    return src


def _es12_run(tmp_path, src: str) -> tuple[int, str]:
    return run(tmp_path, src, tp="es12-tp")


def test_es12_tp_reference_passes(tmp_path, bwrap_ok):
    code, out = _es12_run(tmp_path, _es12_reference())
    assert code == 0 and out.startswith("OK"), out


def test_es12_tp_seed_refused(tmp_path, bwrap_ok):
    code, out = _es12_run(tmp_path, (ES12 / "seed" / "main.cpp").read_text(encoding="utf-8"))
    assert failed(code, out) and "init_adc" in out and "relire" in out, out


def test_es12_tp_seed_with_the_relay_first_is_refused_for_the_missing_confirmation(tmp_path, bwrap_ok):
    seed = (ES12 / "seed" / "main.cpp").read_text(encoding="utf-8")
    seed = seed.replace("    init_relais();  // à déplacer", "    // déplacé").replace("    // TODO étape 1 : tout premier geste", "    init_relais();\n    // TODO étape 1 : tout premier geste")
    code, out = _es12_run(tmp_path, seed)
    assert failed(code, out) and "scénario a" in out and "n'est jamais confirmée" in out and "relire" in out, out


INIT_FIRST = "    init_relais();  // étape 1 : tout premier geste, avant la NVS, le Wi-Fi et le reste\n"
CONCLURE_CALL = "        conclure_autotest(autotest_reussi());\n"
SENSOR_GATE = "    if (!capteur_lisible()) {\n        return false;\n    }\n"
WAIT = "pdMS_TO_TICKS(DELAI_AUTOTEST_MS)"
MARK_INVALID = "    esp_err_t err = esp_ota_mark_app_invalid_rollback_and_reboot();"
MARK_VALID = "        esp_err_t err = esp_ota_mark_app_valid_cancel_rollback();\n"
RANGE_TEST = "    if (raw < RAW_MIN_OK || raw > RAW_MAX_OK) {\n"
GET_STATE = "    esp_err_t err = esp_ota_get_state_partition(esp_ota_get_running_partition(), &etat);\n"
NOT_CONNECTED = '        ESP_LOGW(TAG, "auto-test : MQTT non connecté après %d ms", DELAI_AUTOTEST_MS);\n        return false;\n'
LOG_SENSOR = ('        ESP_LOGW(TAG, "auto-test : lecture du capteur impossible (%s)", esp_err_to_name(err));\n',
              '        ESP_LOGW(TAG, "auto-test : valeur brute %d hors de [%d, %d]", raw, RAW_MIN_OK, RAW_MAX_OK);\n',
              '        ESP_LOGW(TAG, "auto-test : MQTT non connecté après %d ms", DELAI_AUTOTEST_MS);\n',
              '    ESP_LOGE(TAG, "auto-test échoué : retour à la version précédente");\n')
WIFI_LINE = "    wifi_connecter();\n"

# nom -> (remplacements, fragments de message attendus)
ES12_MUTANTS = {
    "immediate_validation_without_selftest": ([(CONCLURE_CALL, "        conclure_autotest(true);\n")], ["scénario a", "n'a pas attendu MQTT"]),
    "validated_before_the_selftest": ([("    if (image_a_confirmer()) {\n", "    esp_ota_mark_app_valid_cancel_rollback();\n    if (image_a_confirmer()) {\n")],
                                      ["scénario a", "n'a pas attendu MQTT"]),
    "no_rollback_on_failure": ([(MARK_INVALID, "    esp_err_t err = ESP_OK;")], ["scénario b", "aucun retour arrière n'est demandé"]),
    "plain_restart_instead_of_the_rollback_call": ([(MARK_INVALID, "    esp_restart();\n    esp_err_t err = ESP_OK;")], ["scénario b", "aucun retour arrière n'est demandé"]),
    "infinite_selftest_delay": ([(WAIT, "portMAX_DELAY")], ["scénario c", "délai fini"]),
    "selftest_delay_too_short": ([("DELAI_AUTOTEST_MS = 60000", "DELAI_AUTOTEST_MS = 20000")], ["scénario c", "55 s"]),
    "selftest_without_waiting_for_mqtt": ([(WAIT, "0")], ["scénario a", "marquée invalide"]),
    "relay_after_the_wifi": ([(INIT_FIRST, ""), (WIFI_LINE, WIFI_LINE + "    init_relais();\n")], ["init_adc", "avant l'initialisation du relais"]),
    "relay_after_the_nvs_and_the_sensor": ([(INIT_FIRST, ""), ("    init_nvs();\n", "    init_nvs();\n    init_relais();\n")], ["init_adc", "avant l'initialisation du relais"]),
    "selftest_ignores_the_sensor": ([(SENSOR_GATE, "")], ["scénario a", "capteur n'a pas été lu"]),
    "sensor_value_not_range_checked": ([(RANGE_TEST, "    if (false) {\n")], ["scénario b", "capteur est muet"]),
    "contradictory_calls": ([(MARK_INVALID, "    esp_ota_mark_app_valid_cancel_rollback();\n" + MARK_INVALID)], ["scénario b", "appels de marquage"]),
    "validated_on_timeout": ([(NOT_CONNECTED, NOT_CONNECTED.replace("return false", "return true"))], ["scénario c", "confirmée"]),
    "never_validated_after_success": ([(MARK_VALID, "        esp_err_t err = ESP_OK;\n")], ["scénario a", "n'est jamais confirmée"]),
    "selftest_at_every_boot": ([("    if (image_a_confirmer()) {\n", "    if (true) {\n")], ["scénario c", "appels de marquage", "déjà confirmée"]),
    "state_not_compared": ([("    return etat == ESP_OTA_IMG_PENDING_VERIFY;\n", "    return true;\n")], ["scénario c", "appels de marquage", "déjà confirmée"]),
    "error_check_on_the_state": ([(GET_STATE, "    ESP_ERROR_CHECK(esp_ota_get_state_partition(esp_ota_get_running_partition(), &etat));\n    esp_err_t err = ESP_OK;\n")],
                                 ["ESP_ERROR_CHECK"]),
    "failure_not_logged": ([(LOG_SENSOR[0], "        (void)err;\n"), (LOG_SENSOR[1], ""), (LOG_SENSOR[2], ""), (LOG_SENSOR[3], "")],
                           ["scénario b", "n'est pas journalisé"]),
    "success_marked_invalid": ([(MARK_VALID, "        esp_err_t err = esp_ota_mark_app_invalid_rollback_and_reboot();\n")], ["scénario a", "marquée invalide"]),
}


@pytest.mark.parametrize("edits,expected", ES12_MUTANTS.values(), ids=ES12_MUTANTS.keys())
def test_es12_tp_mutant(tmp_path, bwrap_ok, edits, expected):
    code, out = _es12_run(tmp_path, _es12_mutant(*edits))
    assert failed(code, out) and all(fragment in out for fragment in expected) and "relire" in out, out


POLLED_WAIT = '''    for (int i = 0; i < DELAI_AUTOTEST_MS / 1000; i++) {
        if (xEventGroupGetBits(groupe_liaison) & BIT_CONNECTE) {
            return true;
        }
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
    ESP_LOGW(TAG, "auto-test : MQTT non connecté après %d ms", DELAI_AUTOTEST_MS);
    return false;
}'''
WAIT_BLOCK = '''    EventBits_t bits = xEventGroupWaitBits(groupe_liaison, BIT_CONNECTE, pdFALSE, pdFALSE, pdMS_TO_TICKS(DELAI_AUTOTEST_MS));
    if ((bits & BIT_CONNECTE) == 0) {
        ESP_LOGW(TAG, "auto-test : MQTT non connecté après %d ms", DELAI_AUTOTEST_MS);
        return false;
    }
    return true;
}'''
INLINE_RELAY = ('    gpio_config_t sortie = {};\n    sortie.pin_bit_mask = 1ULL << GPIO_NUM_5;\n    sortie.mode = GPIO_MODE_OUTPUT;\n'
                '    gpio_config(&sortie);\n    gpio_set_level(GPIO_NUM_5, 0);\n')
SENSOR_RETRY = ('static bool capteur_lisible(void) {\n    for (int essai = 0; essai < 3; essai++) {\n        int raw = 0;\n'
                '        if (adc_oneshot_read(adc, CANAL, &raw) == ESP_OK && raw >= RAW_MIN_OK && raw <= RAW_MAX_OK) {\n            return true;\n        }\n'
                '        vTaskDelay(pdMS_TO_TICKS(1000));\n    }\n    ESP_LOGW(TAG, "auto-test : capteur illisible après 3 essais");\n    return false;\n}\n\n'
                'static bool capteur_lisible_une_fois(void) {')

# Variantes valides, écrites autrement.
ES12_VARIANTS = {
    "mqtt_polled_every_second": [(WAIT_BLOCK, POLLED_WAIT)],
    "relay_configured_inline_first": [(INIT_FIRST, INLINE_RELAY)],
    "sensor_read_three_times": [("static bool capteur_lisible(void) {", SENSOR_RETRY)],
    "state_logged_and_switch": [("    return etat == ESP_OTA_IMG_PENDING_VERIFY;\n",
                                 '    ESP_LOGI(TAG, "état de l\'image : %d", (int)etat);\n    switch (etat) {\n    case ESP_OTA_IMG_PENDING_VERIFY:\n        return true;\n    default:\n        return false;\n    }\n')],
    "relay_not_cut_before_the_rollback": [('    regler_relais(false);\n    ESP_LOGE(TAG, "auto-test échoué', '    ESP_LOGE(TAG, "auto-test échoué')],
    "english_logs": [('"auto-test : MQTT non connecté après %d ms"', '"self-test: MQTT not connected after %d ms"')],
    "init_calls_named_in_comments_and_strings": [("    init_adc();\n", '    // init_adc() vient après init_relais()\n    const char *note = "wifi_connecter() plus tard";\n    (void)note;\n    init_adc();\n')],
    "first_telemetry_before_the_selftest": [("    if (image_a_confirmer()) {\n", "    publier_telemetrie();\n    if (image_a_confirmer()) {\n")],
}


@pytest.mark.parametrize("edits", ES12_VARIANTS.values(), ids=ES12_VARIANTS.keys())
def test_es12_tp_legitimate_variant_passes(tmp_path, bwrap_ok, edits):
    code, out = _es12_run(tmp_path, _es12_mutant(*edits))
    assert code == 0 and out.startswith("OK"), out


def _es12_check_module():
    import sys
    sys.modules.setdefault("esp_trace", _load("esp_trace_probe", ESP / "trace.py"))
    return _load("es12_check_probe", ESP / "checks" / "es12-tp.py")


@pytest.mark.parametrize("src", [
    'extern "C" void app_main(void) {\n    init_relais();\n    init_adc();\n    init_nvs();\n    wifi_connecter();\n}',
    'extern "C" void app_main(void) {\n    gpio_config(&c);\n    gpio_set_level(GPIO_NUM_5, 0);\n    init_nvs();\n}',
    'extern "C" void app_main(void) {\n    demarrage();\n}',
    'extern "C" void app_main(void) {\n    // init_nvs() plus tard\n    init_relais();\n    ESP_LOGI(TAG, "init_adc");\n    init_adc();\n}',
    'static void f() { init_nvs(); }\nextern "C" void app_main(void) {\n    init_relais();\n    f();\n}',
])
def test_es12_source_scan_does_not_refuse_legitimate_idioms(src):
    _es12_check_module()._check_source(src)


@pytest.mark.parametrize("src", [
    'extern "C" void app_main(void) {\n    init_adc();\n    init_relais();\n}',
    'extern "C" void app_main(void) {\n    init_nvs();\n    wifi_connecter();\n}',
    'extern "C" void app_main(void) {\n    nvs_flash_init();\n    gpio_set_level(GPIO_NUM_5, 0);\n}',
    'extern "C" void app_main(void) {\n    esp_wifi_init(&cfg);\n    init_relais();\n}',
])
def test_es12_source_scan_refuses_a_relay_initialised_late(src):
    import sys
    module = _es12_check_module()
    with pytest.raises(sys.modules["esp_trace"].CheckError):
        module._check_source(src)


def test_es12_relay_order_is_judged_on_every_boot():
    """Le relais doit être prêt avant le Wi-Fi à CHAQUE démarrage, pas seulement au premier."""
    import json
    import sys
    module = _es12_check_module()
    boot = [{"ev": "gpio_config", "t_ms": 0, "pin": 5, "mode": "output"}, {"ev": "gpio_set", "t_ms": 0, "pin": 5, "level": 0},
            {"ev": "wifi", "t_ms": 10, "event": "sta_start"}]
    late = [{"ev": "wifi", "t_ms": 20, "event": "sta_start"}, {"ev": "gpio_config", "t_ms": 20, "pin": 5, "mode": "output"},
            {"ev": "gpio_set", "t_ms": 20, "pin": 5, "level": 0}]
    reboot = [{"ev": "reboot", "t_ms": 15, "reason": "scripted"}]

    def trace(evs):
        return sys.modules["esp_trace"].Trace("\n".join(json.dumps(e) for e in evs))

    module._relay_first(trace(boot + reboot + boot), "x")
    with pytest.raises(sys.modules["esp_trace"].CheckError, match="démarrage n° 2"):
        module._relay_first(trace(boot + reboot + late), "x")


def test_es12_check_sections_exist_in_lesson():
    """Chaque « relire : <section> » du contrôle renvoie à un titre réel de la leçon."""
    import re
    lesson = (ES12.parent / "es12.md").read_text(encoding="utf-8")
    titles = set(re.findall(r"^## (.+)$", lesson, re.M))
    source = (ESP / "checks" / "es12-tp.py").read_text(encoding="utf-8")
    constants = dict(re.findall(r'^(S_\w+) = "([^"]+)"$', source, re.M))
    cited = set(re.findall(r"relire : « ([^»{]+) »", source)) | set(constants.values())
    assert cited and cited <= titles, cited - titles
