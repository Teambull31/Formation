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
