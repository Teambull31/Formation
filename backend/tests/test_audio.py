import shutil

import pytest

from app.audio import speak, strip_markdown, synthesize


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


def _edge_ok(text, out):
    out.write_bytes(b"ID3x")
    return out


def test_speak_edge_writes_mp3_atomically(tmp_path, monkeypatch):
    monkeypatch.setenv("FORMATION_TTS", "edge")
    monkeypatch.setattr("app.audio._synthesize_edge", _edge_ok)
    out = speak("bonjour", tmp_path / "a")
    assert out == tmp_path / "a.mp3" and out.read_bytes() == b"ID3x"
    assert [p.name for p in tmp_path.iterdir()] == ["a.mp3"]


def test_speak_falls_back_to_espeak_when_edge_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("FORMATION_TTS", "edge")

    def down(text, out):
        raise RuntimeError("réseau")

    def fake_espeak(text, out, engine="espeak"):
        out.write_bytes(b"RIFF")
        return out

    monkeypatch.setattr("app.audio._synthesize_edge", down)
    monkeypatch.setattr("app.audio.synthesize", fake_espeak)
    out = speak("bonjour", tmp_path / "a")
    assert out == tmp_path / "a.wav" and [p.name for p in tmp_path.iterdir()] == ["a.wav"]


def test_synthesize_edge_wraps_errors(tmp_path, monkeypatch):
    import edge_tts

    class Boom:
        def __init__(self, *a, **k): pass
        async def stream(self):
            raise OSError("hors ligne")
            yield

    monkeypatch.setattr(edge_tts, "Communicate", Boom)
    with pytest.raises(RuntimeError, match="edge-tts"):
        synthesize("a", tmp_path / "a.mp3", engine="edge")


def test_chunks_split_long_text_on_lines_and_keep_everything():
    from app.audio import _chunks

    text = "\n".join(f"ligne {i} " + "x" * 40 for i in range(200))
    parts = _chunks(text, size=500)
    assert len(parts) > 1 and all(len(p) <= 500 for p in parts)
    assert "\n".join(parts).split() == text.split()
    assert _chunks("court") == ["court"]
    assert all(len(p) <= 100 for p in _chunks("mot " * 200, size=100))
    assert all(len(p) <= 100 for p in _chunks("x" * 350, size=100))
