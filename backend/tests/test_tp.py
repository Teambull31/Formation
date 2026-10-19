import time

from app.content import Tp
from app.tp import run_check


def tp(check, timeout_s=10):
    return Tp(id="t", title="t", instructions_md="", check=check, hints=[], timeout_s=timeout_s, workspace=".")


def test_passing_script(tmp_path):
    assert run_check(tp("exit 0"), tmp_path, tmp_path).passed


def test_failing_script_returns_output(tmp_path):
    r = run_check(tp("echo nope; echo err >&2; exit 1"), tmp_path, tmp_path)
    assert not r.passed and "nope" in r.output and "err" in r.output


def test_infinite_loop_is_killed(tmp_path):
    r = run_check(tp("while true; do :; done", timeout_s=1), tmp_path, tmp_path)
    assert not r.passed and "timeout" in r.output.lower()


def test_huge_output_truncated(tmp_path):
    r = run_check(tp("yes | head -c 5000000"), tmp_path, tmp_path)
    assert r.passed and len(r.output) <= 4100


def test_check_runs_in_workspace(tmp_path):
    (tmp_path / "ok.txt").write_text("x")
    assert run_check(tp("test -f ok.txt"), tmp_path, tmp_path).passed


def test_lesson_dir_exported(tmp_path):
    lesson = tmp_path / "les"
    lesson.mkdir()
    r = run_check(tp('echo "$LESSON_DIR"'), tmp_path, lesson)
    assert str(lesson) in r.output


def test_grandchild_killed_on_timeout(tmp_path):
    t = time.monotonic()
    r = run_check(tp("sleep 30 & wait", timeout_s=1), tmp_path, tmp_path)
    assert time.monotonic() - t < 5
    assert not r.passed and "timeout" in r.output.lower()


def test_missing_workspace(tmp_path):
    r = run_check(tp("exit 0"), tmp_path / "nope", tmp_path)
    assert not r.passed and r.output
