"""Les petits utilitaires partagés par les checks ESP (content/esp/trace.py)."""
import importlib.util
import sys
from pathlib import Path

ESP = Path(__file__).resolve().parents[2] / "content" / "esp"
sys.path.insert(0, str(ESP))
spec = importlib.util.spec_from_file_location("esp_trace", ESP / "trace.py")
esp_trace = importlib.util.module_from_spec(spec)
sys.modules["esp_trace"] = esp_trace
spec.loader.exec_module(esp_trace)


def _trace(*sets: tuple[int, int, int]) -> "esp_trace.Trace":
    return esp_trace.Trace("\n".join(f'{{"ev":"gpio_set","t_ms":{t},"pin":{p},"level":{lv}}}' for t, p, lv in sets))


def test_formats_use_french_decimal_comma():
    assert esp_trace.fmt_s(2500) == "2,5 s"
    assert esp_trace.fmt_s(3000) == "3 s"
    assert esp_trace.fmt_pct(62.5) == "62,5"


def test_topic_match_wildcards():
    assert esp_trace.topic_match("a/+/c", "a/b/c")
    assert esp_trace.topic_match("a/#", "a/b/c")
    assert not esp_trace.topic_match("a/+", "a/b/c")
    assert not esp_trace.topic_match("a/b/c", "a/b")


def test_code_only_strips_comments_and_strings():
    out = esp_trace.code_only('int x; // note\n/* bloc */ f("texte \\" ici"); g();')
    assert "note" not in out and "bloc" not in out and "texte" not in out
    assert "int x;" in out and "g();" in out


def test_relay_changes_ignores_repeated_levels_and_other_pins():
    tr = _trace((10, 5, 0), (20, 5, 1), (30, 5, 1), (35, 4, 1), (40, 5, 0))
    assert esp_trace.relay_changes(tr) == [(20, 1), (40, 0)]
    assert esp_trace.relay_changes(tr, pin=4) == [(35, 1)]


def test_relay_states_accepts_both_orders_on_the_same_millisecond():
    changes = [(20, 1), (40, 0)]
    assert esp_trace.relay_states(changes, 10) == {0}
    assert esp_trace.relay_states(changes, 20) == {0, 1}
    assert esp_trace.relay_states(changes, 30) == {1}


def test_load_check_returns_the_same_module_each_time():
    a = esp_trace.load_check("es6-tp")
    assert a is esp_trace.load_check("es6-tp")
    assert hasattr(a, "verify")
