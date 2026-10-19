import shutil

import pytest

from app.audio import strip_markdown, synthesize


def test_strip_markdown_removes_markers():
    assert strip_markdown("# T\n**gras** et !!rouge!!") == "T\ngras et rouge"


def test_strip_markdown_code_and_lists():
    md = "- item `x`\n```sh\nrm -rf /\n```\n* autre"
    assert strip_markdown(md) == "item x\nautre"


def test_synthesize_unknown_engine(tmp_path):
    with pytest.raises(ValueError):
        synthesize("a", tmp_path / "a.wav", engine="nope")


def test_synthesize_missing_binary(tmp_path, monkeypatch):
    monkeypatch.setattr("app.audio.shutil.which", lambda _: None)
    with pytest.raises(RuntimeError, match="espeak-ng"):
        synthesize("a", tmp_path / "a.wav")


def test_synthesize_writes_wav(tmp_path):
    if shutil.which("espeak-ng") is None:
        pytest.skip("espeak-ng absent")
    out = synthesize("bonjour", tmp_path / "sub" / "a.wav")
    assert out.stat().st_size > 1000


def test_synthesize_text_starting_with_dashes(tmp_path):
    if shutil.which("espeak-ng") is None:
        pytest.skip("espeak-ng absent")
    assert synthesize("--dry-run x", tmp_path / "a.wav").exists()
