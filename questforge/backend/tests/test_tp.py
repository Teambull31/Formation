from pathlib import Path
import pytest
from app.content import Tp
from app.tp import run_check, CheckResult


def make_tp(check: str, timeout_s: int = 5) -> Tp:
    return Tp(
        id="tptest",
        title="Test TP",
        instructions_md="Test",
        check=check,
        hints=["Hint"],
        timeout_s=timeout_s,
    )


def test_passing_script(tmp_path):
    tp = make_tp("exit 0")
    res = run_check(tp, tmp_path, tmp_path)
    assert res.passed


def test_failing_script_returns_output(tmp_path):
    tp = make_tp("echo nope; exit 1")
    res = run_check(tp, tmp_path, tmp_path)
    assert not res.passed
    assert "nope" in res.output


def test_infinite_loop_is_killed(tmp_path):
    tp = make_tp("while true; do :; done", timeout_s=1)
    res = run_check(tp, tmp_path, tmp_path)
    assert not res.passed
    assert "timeout" in res.output.lower()


def test_huge_output_truncated(tmp_path):
    tp = make_tp("yes | head -c 5000000")
    res = run_check(tp, tmp_path, tmp_path)
    assert len(res.output) <= 4100


def test_check_runs_in_workspace(tmp_path):
    (tmp_path / "ok.txt").write_text("x")
    tp = make_tp("test -f ok.txt")
    res = run_check(tp, tmp_path, tmp_path)
    assert res.passed
