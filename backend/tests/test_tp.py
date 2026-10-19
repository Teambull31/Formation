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


def test_seed_workspace_dir_and_file_no_overwrite(tmp_path):
    from app.tp import seed_workspace
    lesson = tmp_path / "m" / "lessons" / "l.tp"
    lesson.mkdir(parents=True)
    (tmp_path / "m" / "kit" / "sub").mkdir(parents=True)
    (tmp_path / "m" / "kit" / "a.txt").write_text("kit")
    (tmp_path / "m" / "kit" / "sub" / "b.txt").write_text("kit")
    (lesson / "one.txt").write_text("one")
    t = tp("true")
    t.workspace, t.seed = "w", ["../../kit", "one.txt"]
    ws = tmp_path / "ws"
    ws.mkdir()
    d = seed_workspace(t, lesson, ws)
    assert d == ws / "w" and (d / "kit" / "a.txt").read_text() == "kit" and (d / "kit" / "sub" / "b.txt").exists()
    assert (d / "one.txt").read_text() == "one"
    (d / "kit" / "a.txt").write_text("mine")
    seed_workspace(t, lesson, ws)
    assert (d / "kit" / "a.txt").read_text() == "mine"


def test_seed_workspace_refuses_symlink(tmp_path):
    import pytest
    from app.tp import seed_workspace
    lesson = tmp_path / "l"
    lesson.mkdir()
    (lesson / "x").symlink_to("/etc/passwd")
    t = tp("true")
    t.seed = ["x"]
    with pytest.raises(ValueError):
        seed_workspace(t, lesson, tmp_path)


def test_run_check_cwd_is_tp_workspace(tmp_path):
    t = tp("test -f here.txt")
    t.workspace = "sub"
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "here.txt").write_text("x")
    assert run_check(t, tmp_path, tmp_path).passed
    t.workspace = "other"
    assert not run_check(t, tmp_path, tmp_path).passed and (tmp_path / "other").is_dir()
