from pathlib import Path
from app.audio import strip_markdown, synthesize


def test_strip_markdown_removes_markers():
    md = "# T\n**gras** et !!rouge!!"
    assert strip_markdown(md) == "T\ngras et rouge"


def test_synthesize_writes_wav(tmp_path):
    wav_file = tmp_path / "a.wav"
    out = synthesize("bonjour", wav_file)
    assert out.exists()
    assert out.stat().st_size > 1000
